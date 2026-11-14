from datetime import datetime
import json

import pytest

from ohlcv.history.vnstock import StockService, normalize_symbol, VN
from ohlcv.realtime.quote import normalize_quote, LiveService
from ohlcv.realtime.session import RateBudget, SessionGate
from ohlcv.storage.store import ProjectPaths

NOW = datetime(2026, 10, 6, 10, tzinfo=VN)
ROW = {'time':'2026-10-06', 'open':'1700', 'high':'1710.25', 'low':'1690', 'close':'1705.5', 'volume':123456789}

@pytest.mark.parametrize('input_code,canonical,exchange', [('vnindex','VNINDEX','HOSE'),('VN30','VN30','HOSE'),('HNX','HNXINDEX','HNX'),('UPCOM','UPCOMINDEX','UPCOM')])
def test_indices_load_on_demand_without_equity_catalog(local_tmp,input_code,canonical,exchange):
    calls=[]
    def fetch(action,symbol=None):
        calls.append((action,symbol))
        assert action=='history'
        return {'symbol':symbol,'instrument_type':'index','rows':[ROW],'fetched_at':NOW.isoformat()}
    service=StockService(ProjectPaths(local_tmp),fetch=fetch,clock=lambda:100)
    assert calls==[]
    data=service.load(input_code)
    assert normalize_symbol(input_code)==canonical
    assert calls==[('history',canonical)]
    assert data['bars'][0]['exchange']==exchange
    assert data['bars'][0]['close']=='1705.5'
    assert data['provenance']['instrument_type']=='index'
    assert data['provenance']['price_units']=='points'
    assert (local_tmp/f'data/stocks/{canonical}/data.json').is_file()
    assert service.load(input_code)['cached'] is True
    assert len(calls)==1

def result(symbol='VNINDEX',row=None):
    return {'symbol':symbol,'instrument_type':'index','rows':[row or ROW],'fetched_at':NOW.isoformat()}

def test_index_quote_points_identity_and_strict_volume():
    bar=normalize_quote(result(),'VNINDEX','HOSE')
    assert bar['close']=='1705.5' and bar['status']=='open' and bar['reconciled_at'] is None
    for invalid in [result('VN30'),result(row={**ROW,'volume':1.5}),result(row={**ROW,'volume':True}),result(row={**ROW,'close':float('nan')})]:
        with pytest.raises(ValueError):normalize_quote(invalid,'VNINDEX','HOSE')

def test_index_live_gate_weighted_budget_and_receipt(local_tmp):
    paths=ProjectPaths(local_tmp)
    calls=[]
    def fetch(action,symbol=None):calls.append((action,symbol));return result(symbol)
    StockService(paths,fetch=fetch,clock=lambda:100).load('VNINDEX')
    paths.atomic_json('config/calendar.live.json',{'version':1,'coverage_start':'2026-10-01','coverage_end':'2026-10-31',
        'working_dates':['2026-10-06'],'source':'fixture','overrides':{}})
    now=[NOW.replace(hour=12)]
    budget=RateBudget(clock=lambda:100)
    live=LiveService(paths,fetch=fetch,budget=budget,gate=SessionGate(paths,now=lambda:now[0]))
    assert live.quote('VNINDEX')['quote'] is None
    assert len(calls)==1 and len(budget.calls)==0
    now[0]=NOW
    quote=live.quote('VNINDEX')
    assert quote['quote']['close']=='1705.5' and len(budget.calls)==3
    assert quote['data']['provenance']['quote_price_divisor']==1
    assert 'index.ohlcv' in quote['data']['provenance']['live_method']
    assert json.loads(paths.output('data/stocks/VNINDEX/live.json').read_text())['symbol']=='VNINDEX'
