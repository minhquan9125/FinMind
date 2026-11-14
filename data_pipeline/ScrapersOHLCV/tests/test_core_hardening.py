from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest

from ohlcv.core.models import Bar
from ohlcv.core.state import CandleBook

NOW = datetime(2026, 10, 6, 3, 0, tzinfo=timezone.utc)


def candle(**changes):
    values = dict(
        symbol="FPT",
        exchange="HOSE",
        trade_date=date(2026, 10, 6),
        open=Decimal("100"),
        high=Decimal("105"),
        low=Decimal("99"),
        close=Decimal("102"),
        volume=1000,
        source_updated_at=NOW,
        received_at=NOW,
    )
    values.update(changes)
    return Bar(**values)


def test_symbol_regex_fullmatch():
    with pytest.raises(ValueError):
        candle(symbol="FPT\n")
    with pytest.raises(ValueError):
        candle(symbol="FPT ")
    with pytest.raises(ValueError):
        candle(symbol="TOOLONGSYMBOL")


def test_enum_validation():
    with pytest.raises(ValueError):
        candle(price_basis="invented")
    with pytest.raises(ValueError):
        candle(volume_basis="invented")
    with pytest.raises(ValueError):
        candle(quality="interpolated")
    with pytest.raises(ValueError):
        candle(quality=123)
    with pytest.raises(ValueError):
        candle(exchange=123)

    # Valid explicit unknown basis
    b = candle(price_basis="unknown", volume_basis="unknown", quality="unknown")
    assert b.price_basis == "unknown"
    assert b.volume_basis == "unknown"
    assert b.quality == "unknown"


def test_no_trade_iff_all_ohlc_none_and_zero_volume():
    # Valid no trade
    nt = candle(open=None, high=None, low=None, close=None, volume=0, quality="no_trade")
    assert nt.quality == "no_trade"

    # Invalid: no_trade with positive volume
    with pytest.raises(ValueError):
        candle(open=None, high=None, low=None, close=None, volume=10, quality="no_trade")

    # Invalid: no_trade with ohlc
    with pytest.raises(ValueError):
        candle(quality="no_trade")

    # Invalid: all None OHLC with complete quality
    with pytest.raises(ValueError):
        candle(open=None, high=None, low=None, close=None, volume=0, quality="complete")


def test_from_dict_strictness():
    d = candle().to_dict()

    # Boolean volume rejected
    d_bad_vol = dict(d, volume=True)
    with pytest.raises(ValueError):
        Bar.from_dict(d_bad_vol)

    # Fractional/string volume rejected
    d_str_vol = dict(d, volume="1000")
    with pytest.raises(ValueError):
        Bar.from_dict(d_str_vol)

    # Float price rejected (lossy)
    d_flt = dict(d, open=100.5)
    with pytest.raises(ValueError):
        Bar.from_dict(d_flt)

    # Boolean price rejected
    d_bool_price = dict(d, open=False)
    with pytest.raises(ValueError):
        Bar.from_dict(d_bool_price)

    # Empty string datetime rejected
    d_empty_dt = dict(d, source_updated_at="   ")
    with pytest.raises(ValueError):
        Bar.from_dict(d_empty_dt)

    # Empty string price rejected
    d_empty_p = dict(d, open="")
    with pytest.raises(ValueError):
        Bar.from_dict(d_empty_p)

    # String decimal exact roundtrip preserved
    d_exact = dict(d, close="102.000500")
    b_exact = Bar.from_dict(d_exact)
    assert b_exact.close == Decimal("102.000500")


def test_candlebook_restore_ordering_and_conflict():
    b1 = candle(trade_date=date(2026, 10, 5))
    b2 = candle(trade_date=date(2026, 10, 6))

    # Independent of input ordering, newest trade_date is restored
    book = CandleBook([b1, b2])
    assert book.current["FPT"].trade_date == date(2026, 10, 6)

    book2 = CandleBook([b2, b1])
    assert book2.current["FPT"].trade_date == date(2026, 10, 6)

    # Same key conflicting restore records rejected
    b2_conflicting = candle(trade_date=date(2026, 10, 6), volume=9999)
    with pytest.raises(ValueError, match="Conflicting restore records"):
        CandleBook([b2, b2_conflicting])


def test_apply_ignores_incoming_revision():
    book = CandleBook([candle(revision=1)])
    incoming = candle(revision=99, volume=1500, source_updated_at=NOW + timedelta(seconds=5))
    res = book.apply(incoming)
    assert res.accepted
    assert res.bar.revision == 2


def test_authoritative_cannot_reopen_closed():
    closed_bar = candle(status="closed", reconciled_at=NOW)
    book = CandleBook([closed_bar])

    open_incoming = candle(status="open", volume=2000, source_updated_at=NOW + timedelta(minutes=1))
    res = book.apply(open_incoming, authoritative=True)
    assert not res.accepted
    assert res.reason == "authoritative_cannot_reopen_closed"
    assert book.current["FPT"].status == "closed"


def test_closed_duplicate_no_revision():
    closed_bar = candle(status="closed", reconciled_at=NOW)
    book = CandleBook([closed_bar])
    replay = candle(status="closed", reconciled_at=NOW, received_at=NOW + timedelta(seconds=10))
    res = book.apply(replay, authoritative=True)
    assert not res.accepted
    assert res.reason == "duplicate"
    assert book.current["FPT"].revision == 1


def test_pending_reconciliation_receives_ordered_updates_retaining_pending():
    pending_bar = candle(status="pending_reconciliation")
    book = CandleBook([pending_bar])

    incoming = candle(status="open", volume=1200, source_updated_at=NOW + timedelta(seconds=1))
    res = book.apply(incoming)
    assert res.accepted
    assert res.bar.status == "pending_reconciliation"
    assert res.bar.volume == 1200
    assert res.bar.revision == 2


def test_payload_tuple_includes_reconciliation_and_source_order():
    b1 = candle(status="closed", reconciled_at=NOW)
    b2 = candle(status="closed", reconciled_at=NOW + timedelta(seconds=1))
    assert b1.payload_tuple() != b2.payload_tuple()


def test_rejected_updates_do_not_mutate_state():
    initial = candle()
    book = CandleBook([initial])

    # Rejected regression
    res = book.apply(candle(volume=500, source_updated_at=NOW + timedelta(seconds=1)))
    assert not res.accepted
    assert book.current["FPT"] == initial
    assert len(book.dirty) == 0
