from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo
import re

from ohlcv.core.models import Bar
from ohlcv.core.state import CandleBook, UpdateResult

_SYMBOL_RE = re.compile(r"^[A-Z0-9]{1,10}\Z")
_ALLOWED_EXCHANGES = {"HOSE", "HNX", "UPCOM"}
_VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
_MAX_RECOVER_DAYS = 366


@dataclass(frozen=True, slots=True)
class IngestRejection:
    accepted: bool = False
    reason: str = "rejected"
    bar: Bar | None = None


class DailyPipeline:
    def __init__(
        self,
        store: Any,
        calendar: Any,
        provider: Any,
        symbol_exchanges: Mapping[str, str],
        paths: Any = None,
    ) -> None:
        self._store = store
        self._calendar = calendar
        self._provider = provider
        self._paths = paths
        self._symbol_exchanges = self._validate_universe(symbol_exchanges)
        self._book = CandleBook(self._load_universe_latest())
        self._stats: dict[str, int] = {
            "stream_accepted": 0,
            "stream_rejected": 0,
            "recover_calls": 0,
            "recover_applied": 0,
        }

    @property
    def book(self) -> CandleBook:
        return self._book

    @property
    def calendar(self):
        return self._calendar

    @property
    def universe(self):
        return dict(self._symbol_exchanges)

    def _validate_universe(self, symbol_exchanges: Mapping[str, str]) -> dict[str, str]:
        universe: dict[str, str] = {}
        for symbol, exchange in symbol_exchanges.items():
            if not isinstance(symbol, str) or not _SYMBOL_RE.fullmatch(symbol):
                raise ValueError(f"Invalid symbol in mapping: {symbol!r}")
            if not isinstance(exchange, str) or exchange not in _ALLOWED_EXCHANGES:
                raise ValueError(f"Invalid exchange in mapping: {exchange!r}")
            universe[symbol] = exchange
        return universe

    def _load_universe_latest(self) -> list[Bar]:
        latest_bars = self._store.latest()
        return [b for b in latest_bars if b.symbol in self._symbol_exchanges and b.exchange == self._symbol_exchanges[b.symbol]]

    def _validate_aware(self, dt: datetime, name: str) -> None:
        if not isinstance(dt, datetime) or dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
            raise ValueError(f"{name} must be an aware datetime")

    def ingest_stream(self, payload: Any, now: datetime) -> UpdateResult | IngestRejection | None:
        self._validate_aware(now, "now")
        decoded = self._provider.decode_stream(payload, self._symbol_exchanges, now)
        if decoded is None:
            self._stats["stream_rejected"] += 1
            return None

        symbol = decoded.symbol
        if symbol not in self._symbol_exchanges or decoded.exchange != self._symbol_exchanges[symbol]:
            self._stats["stream_rejected"] += 1
            return IngestRejection(reason="unknown_symbol_or_exchange")

        exchange = self._symbol_exchanges[symbol]
        trade_date = decoded.trade_date
        local_today = now.astimezone(_VN_TZ).date()

        if trade_date != local_today:
            self._stats["stream_rejected"] += 1
            return IngestRejection(reason="not_local_today")

        if not self._calendar.is_known(trade_date):
            self._stats["stream_rejected"] += 1
            return IngestRejection(reason="unknown_day")

        if not self._calendar.trading_day(exchange, trade_date):
            self._stats["stream_rejected"] += 1
            return IngestRejection(reason="nontrading_day")

        is_collecting = self._calendar.is_collecting(exchange, now)
        has_ended = self._calendar.has_ended(exchange, now)
        is_bc_event = isinstance(payload, dict) and payload.get("T") == "bc"

        if not is_collecting and not (has_ended and is_bc_event):
            self._stats["stream_rejected"] += 1
            return IngestRejection(reason="session_not_collecting")

        is_authoritative_close = False
        target_bar = decoded

        if is_bc_event and has_ended:
            session_end = self._calendar.session_end(exchange, trade_date)
            if (decoded.source_updated_at is None or session_end is None
                    or decoded.source_updated_at < session_end or decoded.source_updated_at > now):
                self._stats["stream_rejected"] += 1
                return IngestRejection(reason="invalid_bc_source_timestamp")
            if (decoded.source == 'dnse' and decoded.price_basis != "unknown"
                    and decoded.volume_basis != "unknown" and decoded.quality in {'complete', 'no_trade'}):
                is_authoritative_close = True
                target_bar = replace(decoded, status="closed", reconciled_at=now)
            else:
                target_bar = replace(decoded, status="pending_reconciliation", reconciled_at=None)
        else:
            if decoded.status == "closed":
                target_bar = replace(decoded, status="open", reconciled_at=None)

        existing_current = self._book.current.get(symbol)
        if existing_current and existing_current.trade_date == trade_date and existing_current.status == "closed":
            self._stats["stream_rejected"] += 1
            return IngestRejection(reason="candle_already_closed")

        existing_db = self._store.get(symbol, trade_date)
        candidate_book = CandleBook([existing_db] if existing_db is not None else [])
        result = candidate_book.apply(target_bar, authoritative=is_authoritative_close)
        if not result.accepted or result.bar is None:
            self._stats["stream_rejected"] += 1
            return result

        persisted_bar = result.bar
        self._store.upsert_batch([persisted_bar])
        self._book.current[symbol] = persisted_bar
        self._stats["stream_accepted"] += 1
        return result

    def recover(self, start: date, end: date, now: datetime) -> dict[str, Any]:
        self._validate_aware(now, "now")
        if type(start) is not date or type(end) is not date:
            raise ValueError('Recovery boundaries must be dates')
        if end > now.astimezone(_VN_TZ).date():
            raise ValueError('Recovery cannot request future dates')
        if start > end:
            raise ValueError(f"Invalid range: start ({start}) > end ({end})")
        if (end - start).days > _MAX_RECOVER_DAYS:
            raise ValueError(f"Recovery date range exceeds limit of {_MAX_RECOVER_DAYS} days")

        self._stats["recover_calls"] += 1
        local_today = now.astimezone(_VN_TZ).date()
        expected_dates = self._calendar.trading_dates(start, end)

        summary: dict[str, Any] = {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "total_symbols": len(self._symbol_exchanges),
            "applied_bars": 0,
            "skipped_duplicates": 0,
            "missing_expected": [],
        }

        for symbol, exchange in self._symbol_exchanges.items():
            try:
                raw_bars = self._provider.history(symbol, exchange, start, end, now)
            except Exception as exc:
                raise RuntimeError(f"Provider recovery failed for {symbol}: {exc.__class__.__name__}") from None

            received_by_date: dict[date, Bar] = {}
            for b in raw_bars:
                if (not isinstance(b, Bar) or b.symbol != symbol or b.exchange != exchange
                        or not start <= b.trade_date <= end or b.trade_date > local_today
                        or b.status != 'open' or b.source != 'dnse'):
                    raise ValueError('Invalid recovery provider row')
                if not self._calendar.is_known(b.trade_date) or not self._calendar.trading_day(exchange, b.trade_date):
                    raise ValueError('Recovery row is not a covered trading date')
                if b.trade_date in received_by_date:
                    raise ValueError('Duplicate recovery date')
                received_by_date[b.trade_date] = b

            for expected_day in expected_dates:
                if self._calendar.trading_day(exchange, expected_day) and expected_day not in received_by_date:
                    summary["missing_expected"].append({"symbol": symbol, "trade_date": expected_day.isoformat()})

            bars_to_persist: list[Bar] = []
            for trade_date in sorted(received_by_date.keys()):
                b = received_by_date[trade_date]
                existing_db = self._store.get(symbol, trade_date)
                session_end = self._calendar.session_end(exchange, trade_date)
                has_ended = session_end is not None and now >= session_end

                if trade_date < local_today:
                    can_close = (
                        b.source == "dnse"
                        and b.price_basis != "unknown"
                        and b.volume_basis != "unknown"
                        and b.quality in {'complete', 'no_trade'}
                        and has_ended
                    )
                    target_status = "closed" if can_close else "pending_reconciliation"
                else:
                    target_status = "pending_reconciliation" if has_ended else "open"

                target_reconciled = now
                target_source_updated = existing_db.source_updated_at if (b.source_updated_at is None and existing_db is not None) else b.source_updated_at

                if existing_db is not None and existing_db.status == "closed":
                    if trade_date == local_today or target_status != 'closed':
                        summary['skipped_duplicates'] += 1
                        continue
                    target_status = "closed"
                    target_reconciled = existing_db.reconciled_at

                normalized_bar = replace(
                    b,
                    status=target_status,
                    reconciled_at=target_reconciled,
                    source_updated_at=target_source_updated,
                    received_at=now if b.received_at is None else b.received_at,
                )

                if existing_db is not None:
                    # Re-observing identical business data is idempotent even though
                    # the local recovery receipt is newer.
                    if replace(normalized_bar, reconciled_at=existing_db.reconciled_at).payload_tuple() == existing_db.payload_tuple():
                        summary["skipped_duplicates"] += 1
                        continue
                    if existing_db.status == "closed" and normalized_bar.status != "closed":
                        summary["skipped_duplicates"] += 1
                        continue

                candidate_book = CandleBook([existing_db] if existing_db is not None else [])
                res = candidate_book.apply(normalized_bar, authoritative=True)
                if res.accepted and res.bar is not None:
                    bars_to_persist.append(res.bar)
                else:
                    summary["skipped_duplicates"] += 1

            if bars_to_persist:
                self._store.upsert_batch(bars_to_persist)
                summary["applied_bars"] += len(bars_to_persist)
                self._stats["recover_applied"] += len(bars_to_persist)
                self._book = CandleBook(self._load_universe_latest())

        self._book = CandleBook(self._load_universe_latest())
        return summary

    def export(self, relative_path: str, closed_only: bool = True, start: date | None = None, end: date | None = None) -> int:
        if self._paths is None:
            raise ValueError("ProjectPaths required for export")

        all_bars: list[Bar] = []
        for symbol in sorted(self._symbol_exchanges.keys()):
            hist = self._store.history(symbol, start=start, end=end, closed_only=closed_only)
            for b in hist:
                if b.exchange == self._symbol_exchanges[symbol]:
                    all_bars.append(b)

        all_bars.sort(key=lambda x: (x.symbol, x.trade_date))
        payload = {
            "version": 1,
            "count": len(all_bars),
            "bars": [b.to_dict() for b in all_bars],
        }
        self._paths.atomic_json(relative_path, payload)
        return len(all_bars)

    def status(self, now: datetime) -> dict[str, Any]:
        self._validate_aware(now, "now")
        phases = {}
        for exchange in sorted(set(self._symbol_exchanges.values())):
            phases[exchange] = self._calendar.phase(exchange, now)

        by_status: dict[str, int] = {}
        by_quality: dict[str, int] = {}
        for bar in self._book.current.values():
            by_status[bar.status] = by_status.get(bar.status, 0) + 1
            by_quality[bar.quality] = by_quality.get(bar.quality, 0) + 1

        return {
            "phases": phases,
            "active_symbols": len(self._book.current),
            "status_counts": by_status,
            "quality_counts": by_quality,
            "stats": dict(self._stats),
        }
