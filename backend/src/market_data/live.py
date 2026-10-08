"""One bounded batch for visible viewers; stored crawler files stay read-only."""
from collections import Counter, OrderedDict, deque
from datetime import datetime, timedelta, timezone
import math
import re
import threading
import time

from .validation import normalize_quote

VN = timezone(timedelta(hours=7))
EXCHANGES = ("HOSE", "HNX", "UPCOM")


def stock_symbol(symbol):
    if not isinstance(symbol, str) or not re.fullmatch(r"[A-Z]{3}", symbol):
        raise ValueError("Tự cập nhật chỉ hỗ trợ mã cổ phiếu gồm 3 chữ cái.")
    return symbol


class BusyError(RuntimeError):
    def __init__(self, wait_seconds=5):
        self.wait_seconds = max(1, math.ceil(wait_seconds))
        super().__init__("Đang chờ hạn mức lấy giá dùng chung; vui lòng thử lại sau.")


class LiveCoordinator:
    def __init__(self, fetch, gate, repository, *, clock=time.monotonic,
                 now=None, poll_seconds=5, lease_seconds=20, cache_seconds=60, manual_fetch=None, history_fetch=None):
        for value, minimum in ((poll_seconds, 5), (lease_seconds, 15), (cache_seconds, 1)):
            if type(value) not in (int, float) or not math.isfinite(value) or value < minimum:
                raise ValueError("Cấu hình thời gian không hợp lệ.")
        self.fetch, self.gate, self.repository = fetch, gate, repository
        self.manual_fetch = manual_fetch or fetch
        self.history_fetch = history_fetch
        self._histories = {}
        self.clock = clock
        self.now = now or (lambda: datetime.now(VN))
        self.poll_seconds, self.lease_seconds, self.cache_seconds = poll_seconds, lease_seconds, cache_seconds
        self._lock, self._fetch_lock = threading.RLock(), threading.Lock()
        self._viewers = {}
        self._overlays = OrderedDict()
        self._calls = deque()
        self._next_attempt = 0
        self._failures = 0

    def _active(self):
        expired = [key for key, (_, expiry) in self._viewers.items() if expiry <= self.clock()]
        for key in expired:
            del self._viewers[key]
        return {symbol for symbol, _ in self._viewers.values()}

    def watch(self, viewer_id, symbol):
        stock_symbol(symbol)
        with self._lock:
            self._active()
            if viewer_id not in self._viewers and len(self._viewers) >= 1000:
                raise OverflowError("Đã đạt giới hạn số người xem.")
            # Account for this viewer switching away from its previous symbol.
            other = {s for key, (s, _) in self._viewers.items() if key != viewer_id}
            if len(other | {symbol}) > 100:
                raise OverflowError("Đã đạt giới hạn 100 mã đang xem.")
            self._viewers[viewer_id] = (symbol, self.clock() + self.lease_seconds)

    def unwatch(self, viewer_id):
        with self._lock:
            self._viewers.pop(viewer_id, None)

    def _is_open(self, symbol):
        entry = self._overlays.get(symbol)
        return self.gate(entry[0]["exchange"]) if entry else any(self.gate(e) for e in EXCHANGES)

    def _reserve(self):
        current = self.clock()
        while self._calls and self._calls[0] <= current - 60:
            self._calls.popleft()
        wait = max(0, self._next_attempt - current)
        if self._calls:
            wait = max(wait, self._calls[-1] + self.poll_seconds - current)
        if len(self._calls) >= 16:
            wait = max(wait, self._calls[0] + 60 - current)
        if wait > 0:
            raise BusyError(wait)
        # Failed requests retain their reservation, and changing ticker never resets it.
        self._calls.append(current)

    def _previous(self, symbol):
        data = self.repository.get_ohlcv(symbol, 250)
        bars = data.get("bars", [])
        return max(bars, key=lambda bar: bar["date"]) if bars else None

    def _ingest(self, result, symbols, automatic):
        stamp = datetime.fromisoformat(result["fetched_at"])
        current = self.now().astimezone(VN)
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError("Thiếu múi giờ nguồn.")
        if stamp.astimezone(VN).date() != current.date() or not -30 <= (current - stamp).total_seconds() <= 120:
            raise ValueError("Thời điểm lấy giá đã cũ hoặc nằm trong tương lai.")
        rows = result.get("rows")
        if not isinstance(rows, list):
            raise ValueError("Bảng giá không hợp lệ.")
        counts = Counter(row.get("symbol") for row in rows if isinstance(row, dict) and isinstance(row.get("symbol"), str))
        accepted = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            symbol = row.get("symbol")
            if not isinstance(symbol, str) or symbol not in symbols or counts[symbol] != 1:
                continue
            with self._lock:
                if automatic and (symbol not in self._active() or not self.gate(row.get("exchange"))):
                    continue
                try:
                    previous = self._previous(symbol)
                    bar = normalize_quote(row, result["fetched_at"], today=current.date(),
                                          automatic=automatic, previous=previous)
                    existing = self._overlays.get(symbol)
                    if existing:
                        if stamp < datetime.fromisoformat(existing[2]):
                            continue
                        other = normalize_quote(row, result["fetched_at"], today=current.date(),
                                                automatic=automatic, previous=existing[1])
                        if other["status"] == "pending_reconciliation":
                            bar["status"] = "pending_reconciliation"
                    self._overlays[symbol] = (dict(row), bar, result["fetched_at"], self.clock())
                    self._overlays.move_to_end(symbol)
                    while len(self._overlays) > 100:
                        self._overlays.popitem(last=False)
                    accepted += 1
                except (ValueError, TypeError, KeyError, OSError):
                    continue
        return accepted

    def _request(self, symbols, automatic):
        with self._lock:
            self._reserve()
        try:
            result = (self.fetch if automatic else self.manual_fetch)(symbols)
            accepted = self._ingest(result, symbols, automatic)
            if not accepted:
                raise ValueError("Không có giá hợp lệ cho các mã đang xem.")
        except Exception:
            with self._lock:
                self._failures = min(5, self._failures + 1)
                self._next_attempt = self.clock() + min(60, 5 * 2 ** (self._failures - 1))
            raise RuntimeError("Nguồn chưa trả giá hợp lệ; giữ dữ liệu gần nhất và thử lại sau.") from None
        with self._lock:
            self._failures, self._next_attempt = 0, 0
        return accepted

    def tick(self):
        if not self._fetch_lock.acquire(blocking=False):
            return {"status": "busy"}
        try:
            with self._lock:
                symbols = sorted(symbol for symbol in self._active() if self._is_open(symbol))
            if not symbols:
                return {"status": "idle"}
            accepted = self._request(symbols, True)
            return {"status": "ok", "accepted": accepted}
        except BusyError as exc:
            return {"status": "waiting", "wait_seconds": exc.wait_seconds}
        except RuntimeError:
            return {"status": "error"}
        finally:
            self._fetch_lock.release()

    def refresh(self, symbol):
        stock_symbol(symbol)
        with self._lock:
            entry = self._overlays.get(symbol)
            if entry and self.clock() - entry[3] < self.cache_seconds and datetime.fromisoformat(entry[2]).astimezone(VN).date() == self.now().astimezone(VN).date():
                return self.read(symbol, 250)
        if not self._fetch_lock.acquire(blocking=False):
            raise BusyError(self.poll_seconds)
        try:
            self._request([symbol], False)
            return self.read(symbol, 250)
        finally:
            self._fetch_lock.release()

    def index_history(self, symbol):
        from .history import INDEX_NAMES, normalize_index_history
        if symbol not in INDEX_NAMES:
            raise ValueError("Chỉ số không được hỗ trợ.")
        with self._lock:
            cached = self._histories.get(symbol)
            if cached and self.clock() - cached[1] < self.cache_seconds:
                return cached[0]
        if self.history_fetch is None:
            raise RuntimeError("Chưa bật nguồn lịch sử chỉ số.")
        if not self._fetch_lock.acquire(blocking=False):
            raise BusyError(self.poll_seconds)
        try:
            with self._lock:
                self._reserve()
            try:
                result = normalize_index_history(symbol, self.history_fetch(symbol))
            except Exception:
                with self._lock:
                    self._next_attempt = max(self._next_attempt, self.clock() + 5)
                raise RuntimeError("Chưa lấy được lịch sử chỉ số; vui lòng thử lại sau.") from None
            with self._lock:
                self._histories[symbol] = (result, self.clock())
            return result
        finally:
            self._fetch_lock.release()

    def stock_history(self, symbol):
        from .history import normalize_history
        stock_symbol(symbol)
        cached = self.repository.runtime_read(symbol, "history")
        if cached:
            try:
                age = (self.now() - datetime.fromisoformat(cached["fetched_at"])).total_seconds()
                if 0 <= age < self.cache_seconds:
                    return self.read(symbol, 250)
            except (KeyError, TypeError, ValueError):
                pass
        if self.history_fetch is None:
            raise RuntimeError("Chưa bật nguồn lịch sử.")
        if not self._fetch_lock.acquire(blocking=False):
            raise BusyError(self.poll_seconds)
        try:
            with self._lock:
                self._reserve()
            try:
                data = normalize_history(symbol, self.history_fetch(symbol))
                self.repository.runtime_write(symbol, "history", data)
            except Exception:
                with self._lock:
                    self._next_attempt = max(self._next_attempt, self.clock() + 5)
                raise RuntimeError("Chưa tải được lịch sử; giữ biểu đồ đã có và thử lại sau.") from None
            return self.read(symbol, 250)
        finally:
            self._fetch_lock.release()

    def read(self, symbol, limit, *, repository=None):
        data = (repository or self.repository).get_ohlcv(symbol, 250)
        bars = {bar["date"]: dict(bar) for bar in data["bars"]}
        with self._lock:
            entry = self._overlays.get(symbol)
            active = symbol in self._active()
            valid = False
            if entry:
                raw, bar, stamp, seen = entry
                try:
                    previous = max(bars.values(), key=lambda item: item["date"]) if bars else None
                    checked = normalize_quote(raw, stamp, today=datetime.fromisoformat(stamp).astimezone(VN).date(),
                                              automatic=bar["status"] == "open", previous=previous)
                    # Recheck against a file that may have been updated by an independent crawler.
                    bars[bar["date"]] = checked
                    valid = True
                except (ValueError, TypeError, KeyError):
                    pass
            supported = bool(re.fullmatch(r"[A-Z]{3}", symbol))
            is_open = self._is_open(symbol) if supported else False
            stale = not valid or self.clock() - entry[3] > 2 * self.poll_seconds or bool(self._failures)
            reason = ("Chỉ số hiện đọc dữ liệu đã lưu; chưa tham gia nhóm cập nhật cổ phiếu." if not supported
                      else "Ngoài phiên hoặc lịch chưa xác nhận; dùng nút Làm mới giá/tin." if not is_open
                      else "Chưa đăng ký tự cập nhật; đang hiển thị dữ liệu gần nhất." if not active
                      else "Nguồn có thể trễ; giữ giá hợp lệ gần nhất." if stale
                      else "Đang tự cập nhật giá theo nhóm mã.")
            live = {"enabled": supported, "active": active and is_open, "stale": stale,
                    "last_success_at": entry[2] if valid else None,
                    "poll_seconds": self.poll_seconds, "reason": reason}
        ordered = sorted(bars.values(), key=lambda bar: bar["date"])
        return {**data, "bars": ordered[-limit:],
                "source": "vnstock_kbs" if valid else data.get("source"),
                "fetched_at": entry[2] if valid else data.get("fetched_at"), "live": live}

    def status(self):
        with self._lock:
            active = sorted(self._active())
            return {"viewers": len(self._viewers), "symbols": active,
                    "poll_seconds": self.poll_seconds, "cached_symbols": len(self._overlays),
                    "wait_seconds": max(0, math.ceil(self._next_attempt - self.clock()))}
