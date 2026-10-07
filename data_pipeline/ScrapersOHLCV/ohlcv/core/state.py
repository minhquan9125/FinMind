from dataclasses import dataclass, replace
from typing import Iterable

from ohlcv.core.models import Bar


@dataclass(frozen=True, slots=True)
class UpdateResult:
    accepted: bool
    reason: str
    bar: Bar | None = None


class CandleBook:
    """In-memory active state book holding the latest bar per symbol.

    Pending Rows Semantic:
    - If an existing bar has status == 'pending_reconciliation', ordinary updates
      are accepted if strictly ordered by source_updated_at (and monotonic), while
      preserving the existing bar's 'pending_reconciliation' status unless explicitly
      finalized by an authoritative update.

    New Day Support Precondition:
    - When a bar arrives with a newer trade_date than current state, the book accepts
      it and initializes revision=1. The caller/pipeline is responsible for persisting
      and flushing the previous day's dirty state before advancing.
    """

    def __init__(self, initial: Iterable[Bar] = ()) -> None:
        self.current: dict[str, Bar] = {}
        self.dirty: set[str] = set()
        self._restore(initial)

    def _restore(self, initial: Iterable[Bar]) -> None:
        # Group initial bars by symbol
        by_symbol: dict[str, list[Bar]] = {}
        for bar in initial:
            by_symbol.setdefault(bar.symbol, []).append(bar)

        for symbol, bars in by_symbol.items():
            max_date = max(b.trade_date for b in bars)
            latest_date_bars = [b for b in bars if b.trade_date == max_date]

            # Check for conflicting restore records with the same latest trade_date
            first = latest_date_bars[0]
            for b in latest_date_bars[1:]:
                if b.payload_tuple() != first.payload_tuple() or b.revision != first.revision:
                    raise ValueError(f"Conflicting restore records for symbol {symbol} on {max_date}")

            self.current[symbol] = first

    def apply(self, bar: Bar, authoritative: bool = False) -> UpdateResult:
        existing = self.current.get(bar.symbol)

        if existing is None:
            if not authoritative and bar.status == "closed":
                return UpdateResult(accepted=False, reason="ordinary_cannot_close")
            new_bar = replace(bar, revision=1)
            self.current[bar.symbol] = new_bar
            self.dirty.add(bar.symbol)
            return UpdateResult(accepted=True, reason="initial_candle", bar=new_bar)

        if bar.trade_date < existing.trade_date:
            return UpdateResult(accepted=False, reason="older_trade_date")

        if bar.trade_date > existing.trade_date:
            if not authoritative and bar.status == "closed":
                return UpdateResult(accepted=False, reason="ordinary_cannot_close")
            new_bar = replace(bar, revision=1)
            self.current[bar.symbol] = new_bar
            self.dirty.add(bar.symbol)
            return UpdateResult(accepted=True, reason="new_trade_date", bar=new_bar)

        # Same trade_date
        if (
            bar.exchange != existing.exchange
            or bar.source != existing.source
            or bar.price_basis != existing.price_basis
            or bar.volume_basis != existing.volume_basis
        ):
            return UpdateResult(accepted=False, reason="basis_or_source_mismatch")

        if authoritative:
            if existing.status == "closed" and bar.status != "closed":
                return UpdateResult(accepted=False, reason="authoritative_cannot_reopen_closed")
            if bar.payload_tuple() == existing.payload_tuple():
                return UpdateResult(accepted=False, reason="duplicate")
            new_revision = existing.revision + 1
            new_bar = replace(bar, revision=new_revision)
            self.current[bar.symbol] = new_bar
            self.dirty.add(bar.symbol)
            return UpdateResult(accepted=True, reason="authoritative_applied", bar=new_bar)

        # Ordinary update
        if existing.status == "closed":
            return UpdateResult(accepted=False, reason="closed_candle_immutable")
        if bar.status == "closed":
            return UpdateResult(accepted=False, reason="ordinary_cannot_close")

        # Reconciliation is an observation barrier, never a fabricated source timestamp.
        # After REST initialization, only an actual source update newer than this
        # barrier can establish stream ordering. This also rejects buffered replays.
        if existing.reconciled_at is not None:
            if bar.source_updated_at is None or bar.source_updated_at <= existing.reconciled_at:
                return UpdateResult(accepted=False, reason="before_reconciliation_observation")
            bar = replace(bar, reconciled_at=existing.reconciled_at)

        # Timestamp ordering checks
        if bar.source_updated_at is None or (existing.source_updated_at is None and existing.reconciled_at is None):
            if bar.payload_tuple() == existing.payload_tuple():
                return UpdateResult(accepted=False, reason="duplicate")
            return UpdateResult(accepted=False, reason="unorderable_missing_timestamp_conflict")

        if existing.source_updated_at is not None and bar.source_updated_at < existing.source_updated_at:
            return UpdateResult(accepted=False, reason="older_source_timestamp")

        if existing.source_updated_at is not None and bar.source_updated_at == existing.source_updated_at:
            if bar.payload_tuple() == existing.payload_tuple():
                return UpdateResult(accepted=False, reason="duplicate")
            return UpdateResult(accepted=False, reason="same_timestamp_conflict")

        # Monotonicity & OHLC validity checks
        if existing.quality != "no_trade":
            if bar.quality == "no_trade":
                return UpdateResult(accepted=False, reason="cannot_regress_to_no_trade")
            if bar.open != existing.open:
                return UpdateResult(accepted=False, reason="open_price_changed")
            if bar.high is not None and existing.high is not None and bar.high < existing.high:
                return UpdateResult(accepted=False, reason="high_regressed")
            if bar.low is not None and existing.low is not None and bar.low > existing.low:
                return UpdateResult(accepted=False, reason="low_regressed")
            if bar.volume < existing.volume:
                return UpdateResult(accepted=False, reason="volume_regressed")
            if bar.open is None or bar.high is None or bar.low is None or bar.close is None:
                return UpdateResult(accepted=False, reason="cannot_remove_known_ohlc")

        # Pending status retention policy: if existing is pending_reconciliation and incoming is open,
        # retain pending_reconciliation status
        target_status = existing.status if existing.status == "pending_reconciliation" and bar.status == "open" else bar.status
        new_revision = existing.revision + 1
        new_bar = replace(bar, status=target_status, revision=new_revision)
        self.current[bar.symbol] = new_bar
        self.dirty.add(bar.symbol)
        return UpdateResult(accepted=True, reason="applied", bar=new_bar)
