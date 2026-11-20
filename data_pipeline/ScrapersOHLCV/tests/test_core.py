from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from ohlcv.core.models import Bar
from ohlcv.core.state import CandleBook


NOW = datetime(2026, 10, 6, 3, 0, tzinfo=timezone.utc)


def candle(**changes):
    values = dict(symbol="FPT", exchange="HOSE", trade_date=date(2026, 10, 6),
                  open=Decimal("100"), high=Decimal("105"), low=Decimal("99"),
                  close=Decimal("102"), volume=1000, source_updated_at=NOW,
                  received_at=NOW)
    values.update(changes)
    return Bar(**values)


def test_cumulative_volume_replaces_and_open_stays_fixed():
    book = CandleBook()
    book.apply(candle())
    result = book.apply(candle(close=Decimal("104"), volume=1300, source_updated_at=NOW + timedelta(seconds=2)))
    assert result.accepted
    assert result.bar.volume == 1300
    assert result.bar.open == Decimal("100")
    assert result.bar.revision == 2
    assert len(book.current) == 1


def test_duplicate_does_not_dirty_or_increment_revision():
    book = CandleBook([candle(revision=8)])
    result = book.apply(candle(received_at=NOW + timedelta(seconds=5)))
    assert not result.accepted
    assert book.current["FPT"].revision == 8
    assert not book.dirty


@pytest.mark.parametrize("changes", [
    {"source_updated_at": NOW - timedelta(seconds=1)},
    {"volume": 900, "source_updated_at": NOW + timedelta(seconds=1)},
    {"open": Decimal("101"), "source_updated_at": NOW + timedelta(seconds=1)},
    {"high": Decimal("104"), "source_updated_at": NOW + timedelta(seconds=1)},
    {"low": Decimal("100"), "source_updated_at": NOW + timedelta(seconds=1)},
    {"close": Decimal("103")},
    {"source": "other", "source_updated_at": NOW + timedelta(seconds=1)},
    {"price_basis": "adjusted", "source_updated_at": NOW + timedelta(seconds=1)},
    {"trade_date": date(2026, 10, 5)},
])
def test_untrusted_regressions_conflicts_and_basis_changes_are_rejected(changes):
    book = CandleBook([candle()])
    assert not book.apply(candle(**changes)).accepted
    assert book.current["FPT"] == candle()


def test_authoritative_eod_corrects_extremes_and_closes():
    book = CandleBook([candle()])
    official = candle(high=Decimal("104"), volume=950, status="closed", reconciled_at=NOW + timedelta(hours=6))
    assert book.apply(official, authoritative=True).accepted
    assert book.current["FPT"].status == "closed"
    assert not book.apply(candle(source_updated_at=NOW + timedelta(hours=7))).accepted


def test_ordinary_source_closed_event_does_not_finalize():
    book = CandleBook([candle()])
    official = candle(status="closed", reconciled_at=NOW + timedelta(hours=6))
    assert not book.apply(official).accepted


def test_new_day_starts_independent_volume():
    book = CandleBook([candle(status="closed", reconciled_at=NOW)])
    tomorrow = candle(trade_date=date(2026, 10, 7), volume=100, source_updated_at=NOW + timedelta(days=1))
    assert book.apply(tomorrow).accepted
    assert book.current["FPT"].volume == 100


def test_no_trade_becomes_first_real_trade():
    empty = candle(open=None, high=None, low=None, close=None, volume=0, quality="no_trade")
    book = CandleBook([empty])
    assert book.apply(candle(source_updated_at=NOW + timedelta(seconds=2))).accepted
    assert book.current["FPT"].quality == "complete"


def test_lossless_serialization():
    bar = candle(close=Decimal("102.0001"))
    assert Bar.from_dict(bar.to_dict()) == bar


@pytest.mark.parametrize("changes", [
    {"symbol": "../FPT"}, {"volume": -1}, {"volume": True}, {"volume": 2**63},
    {"high": Decimal("NaN")}, {"low": Decimal("103")},
    {"received_at": datetime(2026, 10, 6)}, {"status": "closed"},
    {"open": None}, {"exchange": "OTHER"},
])
def test_invalid_candle_is_rejected(changes):
    with pytest.raises(ValueError):
        candle(**changes)
