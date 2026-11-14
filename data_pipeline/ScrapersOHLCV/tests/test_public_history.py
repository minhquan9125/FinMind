"""Public history keeps provenance provisional and never invents missing dates."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
import pytest
from ohlcv.history.public import ingest_response, parse_response, request_url
import ohlcv.history.public as public
from ohlcv.storage.store import CandleStore, ProjectPaths

NOW = datetime(2026, 10, 6, 16, 0, tzinfo=timezone(timedelta(hours=7)))
DAY = date(2026, 10, 5)
STAMP = int(datetime(2026, 10, 5, 9, 0, tzinfo=NOW.tzinfo).timestamp())


def payload(**changes):
    return {'t':[STAMP], 'o':[Decimal('62.10')], 'h':[Decimal('63.2')],
            'l':[Decimal('61.9')], 'c':[Decimal('62.5')], 'v':[1300], **changes}


def ingest(paths, data=None, now=NOW, **changes):
    return ingest_response(payload() if data is None else data, symbol='FPT', exchange='HOSE',
                           start=DAY, end=NOW.date(), fetched_at=now, paths=paths, **changes)


def test_persist_actual_shape_with_unknown_provenance(local_tmp):
    paths = ProjectPaths(local_tmp)
    report = ingest(paths)
    assert report['received_bars'] == report['changed_bars'] == 1
    with CandleStore(paths, 'data/runtime/public-candles.sqlite3') as store:
        bar = store.get('FPT', DAY)
        assert bar.close == Decimal('62.5')
        assert bar.open == Decimal('62.10')
        assert (bar.source,bar.price_basis,bar.volume_basis) == ('dnse_public','unknown','unknown')
        assert bar.status == 'pending_reconciliation'
        assert bar.source_updated_at is None
    exported = json.loads(paths.output('data/runtime/public-ohlcv.json').read_text(encoding='utf-8'))
    assert exported['count'] == 1
    assert exported['bars'][0]['open'] == '62.10'
    assert exported['provenance']['authenticated'] is False
    assert not paths.output('config/calendar.json').exists()


def test_idempotent_reload_and_newer_public_correction(local_tmp):
    paths = ProjectPaths(local_tmp)
    ingest(paths)
    assert ingest(paths, now=NOW+timedelta(minutes=1))['changed_bars'] == 0
    changed = payload(c=[Decimal('62.8')],v=[1400])
    assert ingest(paths, changed, NOW+timedelta(minutes=2))['changed_bars'] == 1
    with CandleStore(paths,'data/runtime/public-candles.sqlite3') as store:
        assert store.get('FPT', DAY).revision == 2
        assert store.get('FPT', DAY).volume == 1400
    with pytest.raises(ValueError):
        ingest(paths, payload(), NOW)


@pytest.mark.parametrize('changes', [{'v':[]},{'o':[None]},{'v':[-1]}, {'t':[STAMP,STAMP], 'o':[62,62], 'h':[63,63], 'l':[61,61], 'c':[62,62], 'v':[1,1]}])
def test_invalid_source_does_not_create_database(local_tmp, changes):
    paths = ProjectPaths(local_tmp)
    with pytest.raises(ValueError):
        ingest(paths,payload(**changes))
    assert not paths.output('data/runtime/public-candles.sqlite3').exists()


def test_out_of_range_date_rejected_not_silently_saved(local_tmp):
    paths=ProjectPaths(local_tmp)
    with pytest.raises(ValueError):
        ingest(paths,payload(t=[STAMP-86400]))
    assert not paths.output('data/runtime/public-candles.sqlite3').exists()


def test_missing_dates_not_invented_and_no_trade_stays_null(local_tmp):
    paths=ProjectPaths(local_tmp)
    ingest(paths,payload(o=[0],h=[0],l=[0],c=[0],v=[0]))
    result=json.loads(paths.output('data/runtime/public-ohlcv.json').read_text())
    assert len(result['bars']) == 1
    assert result['bars'][0]['quality'] == 'no_trade'
    assert result['bars'][0]['close'] is None


def test_fixed_url_validation_and_inclusive_range():
    url=request_url('FPT','HOSE',DAY,NOW.date(),NOW)
    assert url.startswith('https://api.dnse.com.vn/chart-api/v2/ohlcs/stock?')
    assert 'resolution=1D' in url
    for args in [('fpt','HOSE',DAY,NOW.date()),('FPT','BAD',DAY,NOW.date()),('FPT','HOSE',DAY,NOW.date()+timedelta(days=1)),('FPT','HOSE',DAY-timedelta(days=367),NOW.date())]:
        with pytest.raises(ValueError):request_url(*args,NOW)


@pytest.mark.parametrize('raw',[b'{"c":[NaN]}',b'{broken',b'\xff',b' '* (5*1024*1024+1)],ids=['nonfinite','broken','utf8','oversized'])
def test_invalid_or_oversized_response_rejected(raw):
    with pytest.raises(ValueError):parse_response(raw)


def test_response_exact_prices_and_bigint_volume():
    result=parse_response(b'{"c":[62.1234567890123456789],"v":[9223372036854775807]}')
    assert result['c'][0] == Decimal('62.1234567890123456789')
    assert result['v'][0] == 9223372036854775807


def test_escape_output_rejected_before_writes(local_tmp):
    paths=ProjectPaths(local_tmp)
    with pytest.raises(ValueError):ingest(paths,output='../outside.json')
    assert not paths.output('data/runtime/public-candles.sqlite3').exists()


@pytest.mark.parametrize('suffix',['','-wal','-shm','-journal'])
def test_database_sidecar_cannot_be_json_output(local_tmp,suffix):
    paths=ProjectPaths(local_tmp)
    with pytest.raises(ValueError):ingest(paths,output='data/runtime/public-candles.sqlite3'+suffix)
    assert not paths.output('data/runtime/public-candles.sqlite3').exists()


def test_mixed_historical_provenance_rejected_before_updates(local_tmp):
    from dataclasses import replace
    from ohlcv.providers.dnse import decode_daily
    paths=ProjectPaths(local_tmp)
    bar=decode_daily(payload(),'FPT','HOSE',NOW,Decimal('1'),'raw','matched')[0]
    with CandleStore(paths,'data/runtime/public-candles.sqlite3') as store:
        store.upsert_batch([bar,replace(bar,trade_date=NOW.date(),source='dnse_public',price_basis='unknown',volume_basis='unknown')])
    with pytest.raises(ValueError):ingest(paths)
    with CandleStore(paths,'data/runtime/public-candles.sqlite3') as store:
        assert store.get('FPT',DAY)==bar


def test_multi_symbol_export_stable_without_duplicates(local_tmp):
    paths=ProjectPaths(local_tmp)
    ingest(paths)
    ingest_response(payload(),symbol='VNM',exchange='HOSE',start=DAY,end=NOW.date(),fetched_at=NOW,paths=paths)
    exported=json.loads(paths.output('data/runtime/public-ohlcv.json').read_text())
    assert [bar['symbol'] for bar in exported['bars']]==['FPT','VNM']
    assert exported['count']==2


def test_transport_one_attempt_tls_and_no_redirect(monkeypatch):
    calls=[]
    class Response:
        headers={'Date':'Tue, 06 Oct 2026 09:00:00 GMT'}
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,limit):assert limit==public.MAX_RESPONSE+1;return b'{}'
    class Opener:
        def open(self,request,timeout):
            calls.append((request,timeout));return Response()
    handlers=[]
    monkeypatch.setattr(public,'build_opener',lambda *args:(handlers.extend(args) or Opener()))
    assert public.fetch_response(request_url('FPT','HOSE',DAY,NOW.date(),NOW))[0]==b'{}'
    assert len(calls)==1 and calls[0][1]==20
    assert calls[0][0].get_header('Authorization') is None
    assert handlers[0].redirect_request(None,None,None,None,None,None) is None
    assert handlers[1]._context.check_hostname


def test_http_429_stops_without_retry_and_closes_body(monkeypatch):
    from io import BytesIO
    from urllib.error import HTTPError
    body=BytesIO(b'private body must not be echoed')
    calls=[]
    class Opener:
        def open(self,*args,**kwargs):
            calls.append(1);raise HTTPError(public.ENDPOINT,429,'limit',{},body)
    monkeypatch.setattr(public,'build_opener',lambda *args:Opener())
    with pytest.raises(RuntimeError,match='HTTP 429') as error:
        public.fetch_response(request_url('FPT','HOSE',DAY,NOW.date(),NOW))
    assert len(calls)==1 and body.closed
    assert 'private body' not in str(error.value)


def test_cli_fetch_once_and_future_range_before_network(local_tmp,monkeypatch,capsys):
    paths=ProjectPaths(local_tmp)
    monkeypatch.setattr(public,'ProjectPaths',lambda:paths)
    raw=json.dumps(payload(),default=str).encode()
    calls=[]
    monkeypatch.setattr(public,'fetch_response',lambda url:(calls.append(url) or (raw,None)))
    assert public.main(['--start','2026-10-05','--end','2026-10-06'])==0
    assert len(calls)==1
    assert json.loads(capsys.readouterr().out)['requests']==1
    future=(datetime.now(public.VN).date()+timedelta(days=1)).isoformat()
    assert public.main(['--start',future])==2
    assert len(calls)==1
