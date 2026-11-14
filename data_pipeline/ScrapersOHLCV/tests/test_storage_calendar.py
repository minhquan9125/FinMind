from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from ohlcv.core.calendar import TradingCalendar
from ohlcv.storage.store import CandleStore, ProjectPaths
from test_core import candle


DAY = date(2026, 10, 6)
TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def calendar(**kwargs):
    return TradingCalendar([DAY], date(2026, 10, 5), date(2026, 10, 11), "test-fixture", **kwargs)


@pytest.mark.parametrize("exchange,clock,phase", [
    ("HOSE", "08:59", "pre_open"), ("HOSE", "09:00", "ato"),
    ("HOSE", "09:15", "continuous"), ("HOSE", "11:30", "lunch"),
    ("HOSE", "13:00", "continuous"), ("HOSE", "14:30", "atc"),
    ("HOSE", "14:45", "ended"), ("HNX", "09:00", "continuous"),
    ("HNX", "14:45", "after_hours"), ("HNX", "15:00", "ended"),
    ("UPCOM", "14:45", "continuous"), ("UPCOM", "15:00", "ended"),
])
def test_exchange_session_boundaries(exchange, clock, phase):
    now = datetime.fromisoformat(f"2026-10-06T{clock}:00").replace(tzinfo=TZ)
    assert calendar().phase(exchange, now) == phase


def test_holiday_and_unknown_calendar_do_not_collect():
    cal = calendar()
    assert not cal.is_collecting("HOSE", datetime(2026, 10, 5, 10, tzinfo=TZ))
    assert cal.phase("HOSE", datetime(2026, 10, 12, 10, tzinfo=TZ)) == "unknown_calendar"
    assert not cal.has_ended("HOSE", datetime(2026, 10, 12, 16, tzinfo=TZ))
    with pytest.raises(ValueError):
        cal.trading_dates(date(2026, 10, 1), DAY)


def test_override_handles_exceptional_short_session():
    cal = calendar(overrides={"2026-10-06": {"HOSE": [{"start": "09:00", "end": "10:00", "phase": "continuous"}]}})
    assert cal.has_ended("HOSE", datetime(2026, 10, 6, 10, tzinfo=TZ))
    assert not cal.is_collecting("HOSE", datetime(2026, 10, 6, 10, tzinfo=TZ))
    assert TradingCalendar.from_dict(cal.to_dict()).to_dict() == cal.to_dict()


def test_storage_replaces_same_day_and_restores(local_tmp):
    paths = ProjectPaths(local_tmp)
    store = CandleStore(paths)
    assert store.upsert_batch([candle()]) == 1
    assert store.upsert_batch([candle()]) == 0
    changed = candle(volume=1300, revision=2)
    assert store.upsert_batch([changed]) == 1
    store.close()
    restored = CandleStore(paths)
    assert restored.latest() == [changed]
    assert len(restored.history("FPT")) == 1
    restored.close()


def test_storage_prevents_revision_rollback(local_tmp):
    store = CandleStore(ProjectPaths(local_tmp))
    store.upsert_batch([candle(revision=5)])
    with pytest.raises(ValueError):
        store.upsert_batch([candle(volume=500, revision=1)])
    assert store.latest()[0].revision == 5
    store.close()


def test_storage_closed_history_sorted_without_provisional(local_tmp):
    from dataclasses import replace
    from test_core import NOW
    store = CandleStore(ProjectPaths(local_tmp))
    closed = candle(trade_date=date(2026, 10, 5), status="closed", reconciled_at=NOW)
    store.upsert_batch([candle(), closed])
    assert store.history("FPT", closed_only=True) == [closed]
    assert [b.trade_date for b in store.history("FPT")] == [date(2026, 10, 5), DAY]
    store.close()


def test_all_output_paths_confined_before_writing(local_tmp):
    paths = ProjectPaths(local_tmp)
    with pytest.raises(ValueError):
        paths.output("../escape.json")
    with pytest.raises(ValueError):
        ProjectPaths(Path(__file__).resolve().parents[2])
    paths.atomic_json("nested/checkpoint.json", {"volume": 1500})
    assert paths.output("nested/checkpoint.json").read_text(encoding="utf-8").strip()
