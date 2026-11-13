"""One bounded batch for visible viewers; stored crawler files stay read-only."""
from collections import Counter, OrderedDict, deque
from datetime import datetime, timedelta, timezone
import math
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import time

from .validation import normalize_quote
from .session import SessionGate

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
                 now=None, poll_seconds=5, lease_seconds=20, cache_seconds=60, manual_fetch=None, history_fetch=None,
                 tracked_symbols=(), snapshot_sink=None, background_seconds=60, budget_path=None, max_wait_seconds=0):
        for value, minimum in ((poll_seconds, 5), (lease_seconds, 15), (cache_seconds, 1), (max_wait_seconds, 0)):
            if type(value) not in (int, float) or not math.isfinite(value) or value < minimum:
                raise ValueError("Cấu hình thời gian không hợp lệ.")
        if type(background_seconds) not in (int,float) or not math.isfinite(background_seconds) or background_seconds<poll_seconds:
            raise ValueError("Chu kỳ thu nền phải lớn hơn hoặc bằng chu kỳ đang xem.")
        self.fetch, self.gate, self.repository = fetch, gate, repository
        self.manual_fetch = manual_fetch or fetch
        self.history_fetch = history_fetch
        self._histories = {}
        self.clock = clock
        self.now = now or (lambda: datetime.now(VN))
        self.poll_seconds, self.lease_seconds, self.cache_seconds = poll_seconds, lease_seconds, cache_seconds
        # Seconds a user-initiated lookup may queue behind another fetch instead of failing at once.
        # 0 keeps the old fail-fast behaviour; the per-source spacing and budget are never relaxed.
        self.max_wait_seconds = max_wait_seconds
        self._lock, self._fetch_lock = threading.RLock(), threading.Lock()
        self._viewers = {}
        self._overlays = OrderedDict()
        self._calls = deque()
        self._next_attempt = 0
        self._failures = 0
        self._tracked = (dict(tracked_symbols) if isinstance(tracked_symbols,dict)
                         else {symbol:'HOSE' for symbol in tracked_symbols})
        if len(self._tracked)>100 or any(stock_symbol(s)!=s or e not in EXCHANGES for s,e in self._tracked.items()):
            raise ValueError('Invalid tracked stock mapping')
        self.snapshot_sink=snapshot_sink
        self.persistence_error=None
        self.background_seconds=background_seconds
        self._background_due=0
        self._last_dispatch=None
        self._last_accepted=set()
        self._missing_tracked=set(self._tracked)
        self._last_batch_symbols=[]
        self._last_batch_seconds=None
        self._budget_path=Path(budget_path) if budget_path is not None else None
        self._budget_error=None
        self._restore_budget()

    def _restore_budget(self):
        if self._budget_path is None or not self._budget_path.exists():return
        current,wall=self.clock(),time.time()
        try:
            blob=self._budget_path.read_bytes()
            if len(blob)>4096:raise ValueError('Oversized budget')
            saved=json.loads(blob)
            values=saved['attempts'];retry=saved['retry_at']
            if (not isinstance(values,list) or len(values)>16 or
                any(type(v) not in (int,float) or not math.isfinite(v) or v>wall+1 for v in values) or
                type(retry) not in (int,float) or not math.isfinite(retry)):
                raise ValueError('Invalid budget')
            self._calls=deque(current-max(0,wall-v) for v in sorted(values) if wall-v<60)
            self._next_attempt=current+max(0,min(60,retry-wall))
        except (OSError,ValueError,KeyError,TypeError):
            # Unknown recent usage must age out before this process dispatches anything.
            self._next_attempt=current+60
            self._budget_error='Chưa đọc được hạn mức gần nhất; chờ 60 giây.'

    def _save_budget(self):
        if self._budget_path is None:return
        current,wall=self.clock(),time.time()
        data={'attempts':[wall-(current-v) for v in self._calls if current-v<60],
              'retry_at':wall+max(0,self._next_attempt-current)}
        temporary=None
        try:
            self._budget_path.parent.mkdir(parents=True,exist_ok=True)
            fd,temporary=tempfile.mkstemp(dir=self._budget_path.parent,prefix='.budget-')
            with os.fdopen(fd,'w',encoding='utf-8') as stream:json.dump(data,stream)
            os.replace(temporary,self._budget_path)
            self._budget_error=None
        except OSError:
            self._next_attempt=max(self._next_attempt,current+60)
            self._budget_error='Chưa lưu được hạn mức lấy giá; tạm ngừng gọi nguồn.'
            raise RuntimeError(self._budget_error) from None
        finally:
            if temporary is not None:
                try:Path(temporary).unlink(missing_ok=True)
                except OSError:pass

    def set_tracked_symbols(self,mapping):
        if not isinstance(mapping,dict) or any(stock_symbol(s)!=s or e not in EXCHANGES for s,e in mapping.items()):
            raise ValueError('Invalid tracked stock mapping')
        with self._lock:
            if len(set(mapping)|self._active())>100:raise OverflowError('Too many tracked stocks')
            self._tracked=dict(mapping)
            self._missing_tracked.intersection_update(mapping)
            self._background_due=0

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
            if len(other | set(self._tracked) | {symbol}) > 100:
                raise OverflowError("Đã đạt giới hạn 100 mã đang xem.")
            self._viewers[viewer_id] = (symbol, self.clock() + self.lease_seconds)

    def unwatch(self, viewer_id):
        with self._lock:
            self._viewers.pop(viewer_id, None)

    def _is_open(self, symbol):
        entry = self._overlays.get(symbol)
        if entry:return self.gate(entry[0]['exchange'])
        if symbol in self._tracked:return self.gate(self._tracked[symbol])
        return any(self.gate(e) for e in EXCHANGES)

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
        self._save_budget()  # Persist attempted requests before provider I/O, including failures.
        self._last_dispatch=current

    def _failed(self):
        with self._lock:
            self._failures=min(5,self._failures+1)
            self._next_attempt=self.clock()+min(60,5*2**(self._failures-1))
            try:self._save_budget()
            except RuntimeError:pass

    def _watched_open(self):
        return {s for s in self._active() if self._is_open(s)}

    def has_live_viewers(self):
        with self._lock:return bool(self._watched_open())

    def _acquire_fetch(self, end):
        """Take the single fetch slot; queue for it until `end` when waiting is enabled."""
        if self._fetch_lock.acquire(blocking=False):
            return True
        remaining = end - self.clock()
        return remaining > 0 and self._fetch_lock.acquire(timeout=remaining)

    def _wait_turn(self, end):
        """Reserve a source call, sleeping until the existing spacing allows it, never past `end`."""
        while True:
            try:
                with self._lock:
                    self._reserve()
                return
            except BusyError as exc:
                if self.clock() + exc.wait_seconds > end:
                    raise
                time.sleep(exc.wait_seconds)

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
        accepted_symbols=set()
        snapshots=[]
        for row in rows:
            if not isinstance(row, dict):
                continue
            symbol = row.get("symbol")
            if not isinstance(symbol, str) or symbol not in symbols or counts[symbol] != 1:
                continue
            with self._lock:
                if automatic and (symbol not in self._active() | set(self._tracked) or not self.gate(row.get("exchange"))):
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
                    accepted_symbols.add(symbol)
                    # Only tracked project stocks are archived; a viewer's other symbols stay cache-only.
                    if symbol in self._tracked:
                        snapshots.append({'symbol':symbol,'fetched_at':result['fetched_at'],'rows':[dict(row)]})
                except (ValueError, TypeError, KeyError, OSError):
                    continue
        if self.snapshot_sink is not None:
            errors=0
            for snapshot in snapshots:
                try:self.snapshot_sink(snapshot)
                except Exception:errors+=1
            with self._lock:self.persistence_error='Không lưu được bản quan sát ngày.' if errors else None
        with self._lock:self._last_accepted=accepted_symbols
        return accepted

    def _request(self, symbols, automatic, wait_until=None):
        if wait_until is None:
            with self._lock:
                self._reserve()
        else:
            self._wait_turn(wait_until)
        with self._lock:
            self._last_accepted=set()
        try:
            result = (self.fetch if automatic else self.manual_fetch)(symbols)
            accepted = self._ingest(result, symbols, automatic)
            if not accepted:
                raise ValueError("Không có giá hợp lệ cho các mã đang xem.")
        except Exception:
            self._failed()
            raise RuntimeError("Nguồn chưa trả giá hợp lệ; giữ dữ liệu gần nhất và thử lại sau.") from None
        with self._lock:
            self._failures, self._next_attempt = 0, 0
        return accepted

    def tick(self):
        if not self._fetch_lock.acquire(blocking=False):
            return {"status": "busy"}
        try:
            with self._lock:
                current=self.clock()
                background={s for s in self._tracked if self._is_open(s)} if current>=self._background_due else set()
                symbols=sorted(self._watched_open()|background)
                previous_dispatch=self._last_dispatch
            if not symbols:
                return {"status": "idle"}
            try:
                accepted = self._request(symbols, True)
            finally:
                with self._lock:
                    if self._last_dispatch!=previous_dispatch:
                        self._last_batch_symbols=symbols
                        self._last_batch_seconds=max(0,self.clock()-current)
                        if background:
                            self._background_due=self._last_dispatch+self.background_seconds
                            self._missing_tracked=background-self._last_accepted
            return {"status": "ok", "accepted": accepted}
        except BusyError as exc:
            return {"status": "waiting", "wait_seconds": exc.wait_seconds}
        except RuntimeError:
            return {"status": "error"}
        finally:
            self._fetch_lock.release()

    def capture_tracked(self):
        """One manual batch for the tracked stocks, so the day's closing activity is archived
        even when nobody watched and the automatic collector had already stopped."""
        with self._lock:
            symbols = sorted(self._tracked)
        if not symbols:
            return 0
        if not self._fetch_lock.acquire(blocking=False):
            raise BusyError(self.poll_seconds)
        try:
            return self._request(symbols, False)
        finally:
            self._fetch_lock.release()

    def _fresh_overlay(self, symbol):
        with self._lock:
            entry = self._overlays.get(symbol)
            return bool(entry and self.clock() - entry[3] < self.cache_seconds
                        and datetime.fromisoformat(entry[2]).astimezone(VN).date() == self.now().astimezone(VN).date())

    def refresh(self, symbol):
        stock_symbol(symbol)
        if self._fresh_overlay(symbol):
            return self.read(symbol, 250)
        with self._lock:
            if self._watched_open():  # live viewers keep priority over a manual refresh
                raise BusyError(self.poll_seconds)
        end = self.clock() + self.max_wait_seconds
        if not self._acquire_fetch(end):
            raise BusyError(self.poll_seconds)
        try:
            # Another request may have just fetched this symbol while we queued.
            if self._fresh_overlay(symbol):
                return self.read(symbol, 250)
            self._request([symbol], False, wait_until=end if self.max_wait_seconds else None)
            return self.read(symbol, 250)
        finally:
            self._fetch_lock.release()

    def history_for_refresh(self,symbol):
        """Raw SDK history through the same quota and lock; live viewers have priority."""
        from .history import INDEX_NAMES
        if symbol not in INDEX_NAMES:stock_symbol(symbol)
        if self.history_fetch is None:raise RuntimeError('Chưa bật nguồn lịch sử.')
        if not self._fetch_lock.acquire(blocking=False):raise BusyError(self.poll_seconds)
        try:
            with self._lock:
                if self._watched_open():raise BusyError(self.poll_seconds)
                self._reserve()
            try:result=self.history_fetch(symbol)
            except Exception:
                self._failed()
                raise RuntimeError('Chưa lấy được lịch sử; giữ dữ liệu đã lưu.') from None
            with self._lock:self._failures,self._next_attempt=0,0
            return result
        finally:self._fetch_lock.release()

    def index_history(self, symbol):
        from .history import INDEX_NAMES, normalize_index_history
        if symbol not in INDEX_NAMES:
            raise ValueError("Chỉ số không được hỗ trợ.")
        def fresh():
            with self._lock:
                cached = self._histories.get(symbol)
                return cached[0] if cached and self.clock() - cached[1] < self.cache_seconds else None
        if (hit := fresh()) is not None:
            return hit
        if self.history_fetch is None:
            raise RuntimeError("Chưa bật nguồn lịch sử chỉ số.")
        end = self.clock() + self.max_wait_seconds
        if not self._acquire_fetch(end):
            raise BusyError(self.poll_seconds)
        try:
            if (hit := fresh()) is not None:
                return hit
            if self.max_wait_seconds:
                self._wait_turn(end)
            else:
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
            try:self.repository.write_index_history(symbol,result)
            except OSError:
                import logging
                logging.getLogger(__name__).warning('index_history_cache_write_failed')
            return result
        finally:
            self._fetch_lock.release()

    def saved_index_history(self,symbol):
        from .history import INDEX_NAMES
        if symbol not in INDEX_NAMES:raise ValueError('Chỉ số không được hỗ trợ.')
        with self._lock:cached=self._histories.get(symbol)
        if cached:
            data=cached[0];fresh=0<=self.clock()-cached[1]<self.cache_seconds
        else:
            data=self.repository.read_index_history(symbol);fresh=False
            if data.get('fetched_at'):
                age=(self.now()-datetime.fromisoformat(data['fetched_at'])).total_seconds()
                fresh=0<=age<self.cache_seconds
        return {**data,'refresh':{'needed':not fresh,'stale':not fresh}}

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
        end = self.clock() + self.max_wait_seconds
        if not self._acquire_fetch(end):
            raise BusyError(self.poll_seconds)
        try:
            if self.max_wait_seconds:
                recheck = self.repository.runtime_read(symbol, "history")
                try:
                    if recheck and 0 <= (self.now() - datetime.fromisoformat(recheck["fetched_at"])).total_seconds() < self.cache_seconds:
                        return self.read(symbol, 250)
                except (KeyError, TypeError, ValueError):
                    pass
                self._wait_turn(end)
            else:
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
            session_status = ("OPEN" if is_open else
                              self.gate.status(entry[0]["exchange"] if entry else None)
                              if isinstance(self.gate, SessionGate) else "UNKNOWN_CALENDAR")
            session_reason = {
                "CLOSED": "Ngoài giờ cập nhật giá tự động theo lịch đã cấu hình. Bạn vẫn có thể bấm Làm mới biểu đồ.",
                "BREAK": "Đang nghỉ giữa phiên theo lịch đã cấu hình. Bạn vẫn có thể bấm Làm mới biểu đồ.",
                "HALTED": "Lịch đã cấu hình ghi nhận tạm ngừng giao dịch; đang giữ dữ liệu đã lưu. Bạn vẫn có thể bấm Làm mới biểu đồ.",
            }.get(session_status, "Chưa xác nhận được lịch giao dịch; tạm dừng tự cập nhật giá. Bạn vẫn có thể bấm Làm mới biểu đồ.")
            stale = not valid or self.clock() - entry[3] > 2 * self.poll_seconds or bool(self._failures)
            reason = ("Chỉ số hiện đọc dữ liệu đã lưu; chưa tham gia nhóm cập nhật cổ phiếu." if not supported
                      else session_reason if not is_open
                      else "Chưa đăng ký tự cập nhật; đang hiển thị dữ liệu gần nhất." if not active
                      else "Nguồn có thể trễ; giữ giá hợp lệ gần nhất." if stale
                      else "Đang tự cập nhật giá theo nhóm mã.")
            live = {"enabled": supported, "active": active and is_open, "stale": stale,
                    "session_status": session_status,
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
                    "wait_seconds": max(0, math.ceil(self._next_attempt - self.clock())),
                    'tracked_symbols':sorted(self._tracked),'persistence_error':self.persistence_error,
                    'background_seconds':self.background_seconds,'background_due_in':max(0,self._background_due-self.clock()),
                    'missing_tracked_symbols':sorted(self._missing_tracked),'last_batch_symbols':self._last_batch_symbols,
                    'last_batch_seconds':self._last_batch_seconds,
                    'requests_last60s':sum(v>self.clock()-60 for v in self._calls),'budget_error':self._budget_error}
