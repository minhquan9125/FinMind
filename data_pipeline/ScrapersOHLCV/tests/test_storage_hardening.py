from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
import pytest
from ohlcv.storage.store import CandleStore, ProjectPaths
from ohlcv.core.calendar import TradingCalendar
from test_core import candle, NOW


def test_batch_rolls_back_earlier_write(local_tmp):
    with CandleStore(ProjectPaths(local_tmp)) as store:
        initial = candle(revision=5)
        store.upsert_batch([initial])
        with pytest.raises(ValueError):
            store.upsert_batch([candle(symbol='AAA'), candle(volume=900, revision=2)])
        assert store.get('AAA', initial.trade_date) is None
        assert store.get('FPT', initial.trade_date) == initial


def test_revision_conflict_and_stale_identical_rejected(local_tmp):
    with CandleStore(ProjectPaths(local_tmp)) as store:
        initial = candle(revision=5)
        store.upsert_batch([initial])
        with pytest.raises(ValueError):
            store.upsert_batch([candle(volume=900, revision=5)])
        with pytest.raises(ValueError):
            store.upsert_batch([candle(revision=4)])
        assert store.upsert_batch([replace(initial, received_at=NOW+timedelta(seconds=4))]) == 0


@pytest.mark.parametrize('path', ['../out.json', 'file:stream', 'C:out.json', 'C:/out.json', '\\outside', '//server/share/file'])
def test_unsafe_paths_rejected(local_tmp, path):
    with pytest.raises(ValueError):
        ProjectPaths(local_tmp).output(path)


def test_nan_does_not_create_output_directory(local_tmp):
    with pytest.raises(ValueError):
        ProjectPaths(local_tmp).atomic_json('new/bad.json', {'x': float('nan')})
    assert not (local_tmp / 'new').exists()


@pytest.mark.parametrize('suffix', ['', '-wal', '-shm', '-journal'])
def test_sqlite_symlinks_rejected(local_tmp, suffix):
    target = local_tmp / 'runtime' / ('candles.sqlite3' + suffix)
    target.parent.mkdir()
    try:
        target.symlink_to(local_tmp / 'missing')
    except OSError:
        pytest.skip('Symlink privileges unavailable')
    with pytest.raises(ValueError):
        CandleStore(ProjectPaths(local_tmp))


def test_no_trade_and_offsets_preserved(local_tmp):
    b = candle(open=None, high=None, low=None, close=None, volume=0, quality='no_trade')
    with CandleStore(ProjectPaths(local_tmp)) as store:
        store.upsert_batch([b])
        assert store.get(b.symbol, b.trade_date) == b


def test_calendar_naive_time_and_unknown_coverage_rejected():
    day = date(2026, 10, 6)
    cal = TradingCalendar([day], day, day, 'fixture')
    with pytest.raises(ValueError):
        cal.phase('HOSE', datetime(2026, 10, 6, 10))
    with pytest.raises(ValueError):
        cal.has_ended('HOSE', datetime(2026, 10, 6, 16))
    with pytest.raises(ValueError):
        cal.is_working_day(date(2026, 10, 7))
    with pytest.raises(ValueError):
        TradingCalendar.from_dict(dict(cal.to_dict(), version=True))


def test_generator_calendar_whitelist_retained():
    day = date(2026, 10, 6)
    cal = TradingCalendar((d for d in [day]), day, day, 'fixture')
    assert cal.is_working_day(day)


def test_override_sorted_copied_and_closed_exchange():
    day = date(2026, 10, 6)
    overrides = {day.isoformat(): {'HOSE': [{'start':'13:00','end':'14:00','phase':'continuous'}, {'start':'09:00','end':'10:00','phase':'continuous'}], 'HNX': []}}
    cal = TradingCalendar([day], day, day, 'fixture', overrides)
    overrides[day.isoformat()]['HOSE'].clear()
    assert len(cal.sessions('HOSE', day)) == 2
    assert not cal.trading_day('HNX', day)
    assert cal.session_end('HNX', day) is None
