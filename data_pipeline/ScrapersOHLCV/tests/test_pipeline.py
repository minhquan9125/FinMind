from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
import json
import pytest
from ohlcv.core.calendar import TradingCalendar
from ohlcv.core.pipeline import DailyPipeline
from ohlcv.storage.store import CandleStore, ProjectPaths
from ohlcv.providers.dnse import DNSEProvider
from test_core import candle, NOW

DAY = date(2026, 10, 6)
YESTERDAY = date(2026, 10, 5)
ENDED = NOW + timedelta(hours=6)


class FakeProvider:
    def __init__(self):
        self.bars = []
        self.calls = []

    def history(self, symbol, exchange, start, end, now):
        self.calls.append(symbol)
        return [b for b in self.bars if b.symbol == symbol]

    def decode_stream(self, payload, universe, now):
        return payload['bar']


@pytest.fixture
def setup(local_tmp):
    paths = ProjectPaths(local_tmp)
    cal = TradingCalendar([YESTERDAY, DAY, date(2026, 10, 7)], YESTERDAY, date(2026, 10, 11), 'fixture')
    provider = FakeProvider()
    with CandleStore(paths) as store:
        yield DailyPipeline(store, cal, provider, {'FPT':'HOSE'}, paths), store, provider, paths


def test_persist_replace_rollover_restore(setup):
    pipe, store, provider, paths = setup
    assert pipe.ingest_stream({'T':'b', 'bar':candle()}, NOW).accepted
    second = candle(volume=1300, source_updated_at=NOW+timedelta(seconds=2))
    assert pipe.ingest_stream({'T':'b', 'bar':second}, NOW+timedelta(seconds=2)).accepted
    tomorrow = replace(candle(), trade_date=DAY+timedelta(days=1), volume=100, source_updated_at=NOW+timedelta(days=1))
    assert pipe.ingest_stream({'T':'b','bar':tomorrow}, NOW+timedelta(days=1)).accepted
    assert [b.volume for b in store.history('FPT')] == [1300, 100]
    restored = DailyPipeline(store, pipe._calendar, provider, {'FPT':'HOSE'}, paths)
    assert restored.status(NOW)['active_symbols'] == 1
    assert restored.book.current['FPT'].trade_date == tomorrow.trade_date


def test_write_failure_does_not_change_state(setup, monkeypatch):
    pipe, store, _, _ = setup
    pipe.ingest_stream({'T':'b','bar':candle()}, NOW)
    initial = pipe.book.current['FPT']
    def failure(bars):
        raise OSError('disk full')
    monkeypatch.setattr(store, 'upsert_batch', failure)
    with pytest.raises(OSError):
        pipe.ingest_stream({'T':'b','bar':candle(volume=1400, source_updated_at=NOW+timedelta(seconds=2))}, NOW+timedelta(seconds=2))
    assert pipe.book.current['FPT'] == initial


def test_recovery_historical_close_today_open_then_pending(setup):
    pipe, store, provider, _ = setup
    provider.bars = [candle(trade_date=YESTERDAY, source_updated_at=None), candle(source_updated_at=None)]
    pipe.recover(YESTERDAY, DAY, NOW)
    assert store.get('FPT', YESTERDAY).status == 'closed'
    assert store.get('FPT', DAY).status == 'open'
    pipe.recover(YESTERDAY, DAY, ENDED)
    assert store.get('FPT', DAY).status == 'pending_reconciliation'
    assert store.get('FPT', YESTERDAY).revision == 1


def test_authoritative_recovery_corrects_volume_and_watermark(setup):
    pipe, store, provider, _ = setup
    pipe.ingest_stream({'T':'b','bar':candle()}, NOW)
    provider.bars = [candle(volume=900, high=Decimal('104'), source_updated_at=None)]
    pipe.recover(DAY, DAY, NOW+timedelta(seconds=5))
    corrected = store.get('FPT', DAY)
    assert corrected.volume == 900
    assert corrected.high == Decimal('104')
    assert corrected.source_updated_at == NOW
    assert corrected.status == 'open'


def test_clock_alone_never_closes_but_final_event_does(setup):
    pipe, store, provider, _ = setup
    provider.bars = [candle(source_updated_at=None)]
    pipe.recover(DAY, DAY, ENDED)
    assert store.get('FPT', DAY).status == 'pending_reconciliation'
    final = candle(volume=950, source_updated_at=ENDED)
    assert pipe.ingest_stream({'T':'bc','bar':final}, ENDED).accepted
    assert store.get('FPT', DAY).status == 'closed'
    provider.bars = [candle(volume=1200, source_updated_at=None)]
    pipe.recover(DAY, DAY, ENDED)
    assert store.get('FPT', DAY).volume == 950


def test_stale_final_event_does_not_finalize(setup):
    pipe, store, _, _ = setup
    result = pipe.ingest_stream({'T':'bc','bar':candle()}, ENDED)
    assert not result.accepted
    assert store.get('FPT', DAY) is None


def test_early_final_and_unknown_basis_remain_provisional(setup):
    pipe, store, _, _ = setup
    assert pipe.ingest_stream({'T':'bc','bar':candle()}, NOW).accepted
    assert store.get('FPT', DAY).status == 'open'


def test_unknown_basis_final_event_remains_pending(setup):
    pipe, store, _, _ = setup
    bar = candle(price_basis='unknown', volume_basis='unknown', source_updated_at=ENDED)
    assert pipe.ingest_stream({'T':'bc','bar':bar}, ENDED).accepted
    assert store.get('FPT', DAY).status == 'pending_reconciliation'


def test_missing_dates_reported_without_invention(setup):
    pipe, store, _, _ = setup
    result = pipe.recover(YESTERDAY, DAY, NOW)
    assert result['missing_expected'] == [{'symbol':'FPT','trade_date':YESTERDAY.isoformat()}, {'symbol':'FPT','trade_date':DAY.isoformat()}]
    assert store.history('FPT') == []


@pytest.mark.parametrize('changes', [{'symbol':'VNM'}, {'trade_date':DAY+timedelta(days=1)}, {'status':'closed','reconciled_at':NOW}])
def test_foreign_recovery_rejected_without_writes(setup, changes):
    pipe, store, provider, _ = setup
    bar = candle(**changes)
    provider.history = lambda *args: [bar]
    with pytest.raises(ValueError):
        pipe.recover(DAY, DAY, NOW)
    assert store.history('FPT') == []


def test_duplicate_recovery_days_rejected(setup):
    pipe, store, provider, _ = setup
    provider.bars = [candle(), candle(volume=1200)]
    with pytest.raises(ValueError):
        pipe.recover(DAY, DAY, NOW)
    assert store.history('FPT') == []


def test_future_recovery_rejected_before_network(setup):
    pipe, _, provider, _ = setup
    with pytest.raises(ValueError):
        pipe.recover(DAY, DAY+timedelta(days=1), NOW)
    assert provider.calls == []


def test_history_correction_does_not_replace_active_today(setup):
    pipe, store, provider, _ = setup
    pipe.ingest_stream({'T':'b','bar':candle()}, NOW)
    provider.bars = [candle(trade_date=YESTERDAY, source_updated_at=None)]
    pipe.recover(YESTERDAY, YESTERDAY, NOW)
    provider.bars = [candle(trade_date=YESTERDAY, volume=850, source_updated_at=None)]
    pipe.recover(YESTERDAY, YESTERDAY, NOW+timedelta(minutes=1))
    assert store.get('FPT', YESTERDAY).volume == 850
    assert pipe.book.current['FPT'].trade_date == DAY


def test_partial_symbol_commit_book_kept_consistent(setup):
    pipe, store, provider, paths = setup
    pipe = DailyPipeline(store, pipe._calendar, provider, {'FPT':'HOSE','VNM':'HOSE'}, paths)
    def history(symbol, *args):
        if symbol == 'VNM':
            raise RuntimeError('secret-key')
        return [candle(trade_date=YESTERDAY, source_updated_at=None)]
    provider.history = history
    with pytest.raises(RuntimeError) as exc:
        pipe.recover(YESTERDAY, YESTERDAY, NOW)
    assert 'secret-key' not in str(exc.value)
    assert pipe.book.current['FPT'] == store.get('FPT', YESTERDAY)


def test_closed_export_and_path_confinement(setup):
    pipe, store, provider, paths = setup
    provider.bars = [candle(trade_date=YESTERDAY, source_updated_at=None), candle(source_updated_at=None)]
    pipe.recover(YESTERDAY, DAY, NOW)
    assert pipe.export('out.json') == 1
    assert json.loads(paths.output('out.json').read_text())['bars'][0]['status'] == 'closed'
    with pytest.raises(ValueError):
        pipe.export('../outside.json')


def test_all_halted_session_not_finalizable(local_tmp):
    paths = ProjectPaths(local_tmp)
    cal = TradingCalendar([YESTERDAY], YESTERDAY, DAY, 'fixture', {YESTERDAY.isoformat(): {'HOSE':[{'start':'09:00','end':'10:00','phase':'halted'}]}})
    provider = FakeProvider()
    provider.bars = [candle(trade_date=YESTERDAY)]
    with CandleStore(paths) as store:
        pipe = DailyPipeline(store, cal, provider, {'FPT':'HOSE'}, paths)
        pipe.recover(YESTERDAY, YESTERDAY, NOW)
        assert store.get('FPT', YESTERDAY).status != 'closed'


def test_live_after_rest_initialization_can_advance_with_real_source_timestamp(setup):
    pipe, store, provider, _ = setup
    provider.bars = [candle(source_updated_at=None)]
    pipe.recover(DAY, DAY, NOW)
    update = candle(volume=1300, source_updated_at=NOW+timedelta(seconds=2))
    result = pipe.ingest_stream({'T':'b','bar':update}, NOW+timedelta(seconds=3))
    assert result.accepted
    assert store.get('FPT', DAY).volume == 1300
    assert store.get('FPT', DAY).source_updated_at == update.source_updated_at


def test_buffered_snapshot_before_rest_observation_cannot_overwrite_correction(setup):
    pipe, store, provider, _ = setup
    pipe.ingest_stream({'T':'b','bar':candle()}, NOW)
    provider.bars = [candle(close=Decimal('104'),source_updated_at=None)]
    pipe.recover(DAY, DAY, NOW+timedelta(seconds=5))
    stale = candle(close=Decimal('103'),source_updated_at=NOW+timedelta(seconds=2))
    assert not pipe.ingest_stream({'T':'b','bar':stale},NOW+timedelta(seconds=6)).accepted
    assert store.get('FPT', DAY).close == Decimal('104')
    again = pipe.recover(DAY,DAY,NOW+timedelta(seconds=7))
    assert again['applied_bars'] == 0


def test_recovery_observation_barrier_survives_database_reopen(setup):
    pipe, store, provider, paths = setup
    provider.bars = [candle(source_updated_at=None)]
    pipe.recover(DAY, DAY, NOW)
    store.close()
    with CandleStore(paths) as reopened:
        restored = DailyPipeline(reopened, pipe.calendar, provider, {'FPT':'HOSE'}, paths)
        assert restored.book.current['FPT'].reconciled_at == NOW
        stale = candle(volume=1300, source_updated_at=NOW)
        assert not restored.ingest_stream({'T':'b','bar':stale}, NOW+timedelta(seconds=1)).accepted
        fresh = replace(stale, source_updated_at=NOW+timedelta(seconds=2))
        assert restored.ingest_stream({'T':'b','bar':fresh}, NOW+timedelta(seconds=3)).accepted
        assert reopened.get('FPT', DAY).reconciled_at == NOW
