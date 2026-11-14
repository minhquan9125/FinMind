from datetime import datetime, timezone
from decimal import Decimal
import json
import pytest

from ohlcv.history.vnstock import StockService, normalize_history, normalize_symbol, indicators
from ohlcv.storage.store import ProjectPaths

NOW = datetime(2026, 10, 6, 10, tzinfo=timezone.utc)
ROWS = [{'time':'2026-10-06T07:00:00.000', 'open':Decimal('62'), 'high':Decimal('62.2'), 'low':Decimal('60'), 'close':Decimal('60.4'), 'volume':8214700}]
CATALOG = [{'symbol':'FPT','exchange':'HOSE','type':'stock','organ_name':'FPT'}, {'symbol':'VCB','exchange':'HOSE','type':'stock','organ_name':'VCB'}]

@pytest.mark.parametrize('value', ['../FPT','FPT:ads','CON','NUL','COM1','<script>','A'*11, '', None])
def test_bad_symbols(value):
    with pytest.raises(ValueError): normalize_symbol(value)

def test_normalization_exact_and_provisional():
    assert normalize_symbol(' fpt ') == 'FPT'
    payload = normalize_history(ROWS, 'FPT', 'HOSE', NOW)
    bar = payload['bars'][0]
    assert bar['close'] == '60.4' and bar['volume'] == 8214700
    assert bar['source'] == 'vnstock_kbs' and bar['status'] == 'pending_reconciliation'
    assert bar['source_updated_at'] is None
    assert payload['provenance']['fetched_at'] == NOW.isoformat()

@pytest.mark.parametrize('rows', [[], ROWS*2, [dict(ROWS[0], volume=1.5)], [dict(ROWS[0], high=50)], [dict(ROWS[0], close=float('nan'))], [dict(ROWS[0], time='2027-01-01')], [dict(ROWS[0], volume=True)]])
def test_invalid_batches(rows):
    with pytest.raises(ValueError): normalize_history(rows, 'FPT', 'HOSE', NOW)

def test_indicators_warmup_and_constant():
    bars = [{'trade_date':f'2026-01-{i+1:02}', 'close':'10'} for i in range(20)]
    values = indicators(bars)
    assert values[0]['sma20'] is None and values[18]['sma20'] is None
    assert values[-1]['sma20'] == '10' and values[-1]['sma50'] is None
    assert values[13]['rsi14'] is None and values[14]['rsi14'] == '50'

def test_sdk_float_prices_use_shortest_decimal_spelling():
    import pandas as pd
    from ohlcv.sdk.worker import serialize_dataframe
    frame=pd.DataFrame([dict(ROWS[0],high=62.2,close=60.4)])
    result=json.loads(serialize_dataframe(frame,'history'))
    assert result[0]['high']=='62.2' and result[0]['close']=='60.4'
    assert isinstance(result[0]['volume'],int)

def test_folders_cache_and_failure_preserves_data(local_tmp):
    calls=[]
    def fetch(action, symbol=None):
        calls.append((action,symbol))
        return {'rows':CATALOG if action=='catalog' else ROWS, 'fetched_at':NOW.isoformat()}
    service=StockService(ProjectPaths(local_tmp), fetch=fetch, clock=lambda:100)
    payload=service.load('fpt')
    target=local_tmp/'data/stocks/FPT/data.json'
    assert target.is_file() and json.loads(target.read_text())['count']==1
    assert service.load('FPT')['cached'] is True
    assert calls==[('catalog',None),('history','FPT')]
    before=target.read_bytes()
    service.fetch=lambda *a: {'rows':[], 'fetched_at':NOW.isoformat()}
    service.clock=lambda:1000
    with pytest.raises(ValueError):service.load('FPT', refresh=True)
    assert target.read_bytes()==before
    assert not (local_tmp/'data/stocks/ZZZ').exists()
    with pytest.raises(ValueError):service.load('ZZZ')

def test_new_symbol_has_own_folder_and_throttle(local_tmp):
    service=StockService(ProjectPaths(local_tmp), fetch=lambda action,symbol=None:{'rows':CATALOG if action=='catalog' else ROWS, 'fetched_at':NOW.isoformat()}, clock=lambda:100)
    service.load('FPT')
    with pytest.raises(RuntimeError,match='10'):service.load('VCB')
    service.clock=lambda:120
    service.load('VCB')
    assert (local_tmp/'data/stocks/FPT/data.json').is_file()
    assert (local_tmp/'data/stocks/VCB/data.json').is_file()

def test_failed_catalog_is_throttled(local_tmp):
    calls=[]
    def fetch(*args):
        calls.append(args)
        raise RuntimeError('source failure')
    service=StockService(ProjectPaths(local_tmp),fetch=fetch,clock=lambda:100)
    with pytest.raises(RuntimeError,match='source failure'):service.load('FPT')
    with pytest.raises(RuntimeError,match='10'):service.load('FPT')
    assert len(calls)==1

def test_revision_unchanged_then_correction(local_tmp):
    rows=ROWS
    service=StockService(ProjectPaths(local_tmp),fetch=lambda action,symbol=None:{'rows':CATALOG if action=='catalog' else rows,'fetched_at':NOW.isoformat()},clock=lambda:100)
    assert service.load('FPT')['bars'][0]['revision']==1
    service.clock=lambda:200
    assert service.load('FPT',refresh=True)['bars'][0]['revision']==1
    rows=[dict(ROWS[0],volume=12345)]
    service.clock=lambda:300
    assert service.load('FPT',refresh=True)['bars'][0]['revision']==2
