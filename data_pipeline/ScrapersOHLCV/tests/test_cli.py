from datetime import date
import json
import pytest
from ohlcv.app.cli import main
from ohlcv.core.calendar import TradingCalendar
from ohlcv.storage.store import CandleStore, ProjectPaths
from test_core import NOW


@pytest.fixture
def cli_root(local_tmp):
    paths = ProjectPaths(local_tmp)
    cal = TradingCalendar([date(2026,10,6)], date(2026,10,5), date(2026,10,11), 'fixture')
    paths.atomic_json('config/calendar.json', cal.to_dict())
    paths.atomic_json('config/universe.json', {'FPT':'HOSE'})
    return local_tmp


def args(root):
    return ['--root',str(root),'--now',NOW.isoformat()]


def test_help_and_validation_without_db(cli_root, capsys):
    assert main(['--help']) == 0
    capsys.readouterr()
    assert main(args(cli_root)+['validate-calendar']) == 0
    assert json.loads(capsys.readouterr().out)['valid']
    assert not (cli_root/'runtime').exists()


def test_status_no_credentials(cli_root, monkeypatch, capsys):
    monkeypatch.delenv('DNSE_API_KEY', raising=False)
    monkeypatch.delenv('DNSE_API_SECRET', raising=False)
    assert main(args(cli_root)+['status']) == 0
    assert json.loads(capsys.readouterr().out)['active_symbols'] == 0


def test_missing_credentials_fail_before_database(cli_root, monkeypatch, capsys):
    monkeypatch.setenv('DNSE_API_KEY','do-not-print-me')
    monkeypatch.delenv('DNSE_API_SECRET',raising=False)
    assert main(args(cli_root)+['--price-multiplier','1','recover','--start','2026-10-05','--end','2026-10-06']) == 2
    assert 'do-not-print-me' not in capsys.readouterr().err
    assert not (cli_root/'runtime').exists()


def test_replay_rejected_results_counted_and_export(cli_root, capsys):
    payload = dict(T='b',type='STOCK',resolution='1D',symbol='FPT',time=1791219600,lastUpdated=NOW.timestamp(),open=100,high=105,low=99,close=102,volume=1000)
    path = cli_root/'stream.jsonl'
    path.write_text(json.dumps(payload)+'\n'+json.dumps(payload)+'\n',encoding='utf-8')
    assert main(args(cli_root)+['--price-multiplier','1','replay','--input','stream.jsonl']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['accepted'] == 1 and result['rejected'] == 1
    assert main(args(cli_root)+['export','--include-open','--output','bars.json']) == 0
    capsys.readouterr()
    assert json.loads((cli_root/'bars.json').read_text())['count'] == 1


def test_replay_storage_failure_fails_command(cli_root, monkeypatch, capsys):
    payload = dict(T='b',type='STOCK',resolution='1D',symbol='FPT',time=1791219600,lastUpdated=NOW.timestamp(),open=100,high=105,low=99,close=102,volume=1000)
    (cli_root/'stream.jsonl').write_text(json.dumps(payload),encoding='utf-8')
    def failure(*args):
        raise OSError('do-not-print-me')
    monkeypatch.setattr(CandleStore,'upsert_batch',failure)
    assert main(args(cli_root)+['--price-multiplier','1','replay','--input','stream.jsonl']) == 2
    assert 'do-not-print-me' not in capsys.readouterr().err


def test_invalid_universe_and_nan_fail_without_db(cli_root, capsys):
    (cli_root/'config/universe.json').write_text('{"fpt":"HOSE"}',encoding='utf-8')
    assert main(args(cli_root)+['status']) == 2
    assert not (cli_root/'runtime').exists()
    (cli_root/'config/universe.json').write_text('{"FPT":"HOSE"}',encoding='utf-8')
    assert main(args(cli_root)+['--price-multiplier','NaN','replay']) == 2
    assert not (cli_root/'runtime').exists()


def test_live_frozen_clock_rejected_before_connection(cli_root):
    assert main(args(cli_root)+['--price-multiplier','1','live','--start','2026-10-05']) == 2
