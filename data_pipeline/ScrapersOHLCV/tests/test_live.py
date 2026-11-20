from datetime import datetime
from decimal import Decimal
import json

import pytest

from ohlcv.storage.store import ProjectPaths
from ohlcv.history.vnstock import normalize_history, VN
from ohlcv.realtime.session import SessionGate, RateBudget
from ohlcv.realtime.quote import LiveService, normalize_quote


def moment(value):
    return datetime.fromisoformat(value).replace(tzinfo=VN)


def calendar(paths):
    paths.atomic_json('config/calendar.live.json', {'version':1,
        'coverage_start':'2026-10-01', 'coverage_end':'2026-10-31',
        'working_dates':['2026-10-06','2026-10-07'], 'source':'test fixture', 'overrides':{}})


QUOTE = {'symbol':'FPT','exchange':'HOSE','TD':'06/10/2026', 'open_price':'62000',
         'high_price':'62200','low_price':'60000','close_price':'60400','volume_accumulated':8214700}


def test_session_boundaries_and_missing_calendar(local_tmp):
    paths=ProjectPaths(local_tmp)
    now=[moment('2026-10-06T10:00:00')]
    gate=SessionGate(paths, now=lambda:now[0])
    assert not gate.status('HOSE')['active']
    calendar(paths)
    gate=SessionGate(paths, now=lambda:now[0])
    for time, hose, hnx in [('08:59:59',False,False),('09:00:00',True,True),
                          ('11:29:59',True,True),('11:30:00',False,False),
                          ('12:59:59',False,False),('13:00:00',True,True),
                          ('14:44:59',True,True),('14:45:00',False,True),('15:00:00',False,False)]:
        now[0]=moment('2026-10-06T'+time)
        assert gate.status('HOSE')['active'] is hose
        assert gate.status('HNX')['active'] is hnx
    now[0]=moment('2026-10-10T10:00:00')
    assert gate.status('UPCOM')['phase']=='holiday'
    now[0]=moment('2027-01-04T10:00:00')
    assert gate.status('HOSE')['phase']=='unknown_calendar'
    now[0]=datetime(2026,10,6,10)
    with pytest.raises(ValueError):gate.status('HOSE')
    with pytest.raises(ValueError):gate.status('FAKE')


def test_weighted_rate_budget_spacing_and_sliding_window():
    now=[0.0]
    budget=RateBudget(clock=lambda:now[0])
    assert budget.reserve(3)==0
    assert budget.reserve()==5
    now[0]=5
    assert budget.reserve(3)==0
    now[0]=10
    assert budget.reserve(3)==0
    now[0]=15
    assert budget.reserve(3)==0
    now[0]=20
    assert budget.reserve(3)==0
    now[0]=25
    assert budget.reserve()==0
    now[0]=30
    assert budget.reserve()==30
    now[0]=60
    assert budget.reserve(3)==0
    with pytest.raises(ValueError):budget.reserve(True)
    with pytest.raises(ValueError):budget.reserve(17)


def test_quote_units_date_and_cumulative_volume():
    quote=normalize_quote({'rows':[QUOTE], 'fetched_at':'2026-10-06T10:00:01+07:00'},'FPT','HOSE')
    assert quote['close']=='60.4' and quote['volume']==8214700
    assert quote['trade_date']=='2026-10-06'
    for update in ({'symbol':'VCB'},{'exchange':'HNX'},{'TD':None},{'volume_accumulated':True},
                   {'high_price':'60000'},{'close_price':'NaN'},{'volume_accumulated':1.5}):
        with pytest.raises(ValueError):normalize_quote({'rows':[{**QUOTE,**update}],
            'fetched_at':'2026-10-06T10:00:01+07:00'},'FPT','HOSE')


def setup_service(local_tmp, fetch):
    paths=ProjectPaths(local_tmp);calendar(paths)
    now=[moment('2026-10-06T10:00:00')]
    rows=[{'time':'2026-10-06T07:00:00','open':'62','high':'62.2','low':'60','close':'60.4','volume':8214700}]
    paths.atomic_json('data/stocks/FPT/data.json',normalize_history(rows,'FPT','HOSE',now[0]))
    service=LiveService(paths, fetch=fetch, gate=SessionGate(paths,now=lambda:now[0]),
                        budget=RateBudget(clock=lambda:100))
    return paths,now,service


def test_outside_session_no_sdk_and_close_in_flight_discards(local_tmp):
    calls=[]
    def fetch(action,symbol):
        calls.append((action,symbol));now[0]=moment('2026-10-06T11:30:00')
        return {'rows':[QUOTE],'fetched_at':now[0].isoformat()}
    paths,now,service=setup_service(local_tmp,fetch)
    original=paths.output('data/stocks/FPT/data.json').read_bytes()
    now[0]=moment('2026-10-06T12:00:00')
    assert service.quote('FPT')['quote'] is None and not calls
    now[0]=moment('2026-10-06T11:29:59')
    assert service.quote('FPT')['session']['active'] is False
    assert len(calls)==1
    assert paths.output('data/stocks/FPT/data.json').read_bytes()==original


def test_live_update_and_stale_quote_preserves_data(local_tmp):
    def fetch(action,symbol):return {'rows':[{**QUOTE,'close_price':'61000'}], 'fetched_at':now[0].isoformat()}
    paths,now,service=setup_service(local_tmp,fetch)
    result=service.quote('FPT')
    assert result['data']['bars'][-1]['close']=='61'
    assert result['data']['bars'][-1]['status']=='open'
    assert paths.output('data/stocks/FPT/live.json').is_file()
    before=paths.output('data/stocks/FPT/data.json').read_bytes()
    service.budget=RateBudget(clock=lambda:100)
    service.fetch=lambda *args:{'rows':[{**QUOTE,'TD':'05/10/2026'}],'fetched_at':now[0].isoformat()}
    assert service.quote('FPT')['quote'] is None
    assert paths.output('data/stocks/FPT/data.json').read_bytes()==before


def test_volume_regression_is_not_applied(local_tmp):
    paths,now,service=setup_service(local_tmp,lambda *args:{'rows':[{**QUOTE,'volume_accumulated':1}],
        'fetched_at':'2026-10-06T10:00:00+07:00'})
    original=paths.output('data/stocks/FPT/data.json').read_bytes()
    result=service.quote('FPT')
    assert result['quote'] is None and 'reason' in result
    assert paths.output('data/stocks/FPT/data.json').read_bytes()==original


def test_budget_wait_does_not_fetch(local_tmp):
    calls=[]
    paths,now,service=setup_service(local_tmp,lambda *args:calls.append(args))
    service.budget.reserve()
    assert service.quote('FPT')['wait_seconds']==5 and not calls


def test_receipt_extra_decimal_fields_are_lossless_text(local_tmp):
    paths,now,service=setup_service(local_tmp,lambda *args:{'rows':[{**QUOTE,'percent_change':Decimal('-2.42326333')}],
        'fetched_at':'2026-10-06T10:00:00+07:00'})
    result=service.quote('FPT')
    assert result['quote'] is not None
    receipt=json.loads(paths.output('data/stocks/FPT/live.json').read_text())
    assert receipt['rows'][0]['percent_change']=='-2.42326333'


def test_backfill_once_before_quote_and_closed_before_history_returns(local_tmp):
    calls=[]
    paths,now,service=setup_service(local_tmp,None)
    previous=json.loads(paths.output('data/stocks/FPT/data.json').read_text())
    previous['bars'][0]['trade_date']='2026-10-01'
    paths.atomic_json('data/stocks/FPT/data.json',previous)
    now[0]=moment('2026-10-07T10:00:00')
    def fetch(action,symbol):
        calls.append(action)
        return {'rows':[{'time':'2026-10-06T07:00:00','open':'62','high':'62.2','low':'60','close':'60.4','volume':8214700}],
                'fetched_at':now[0].isoformat()}
    service.fetch=fetch
    assert service.quote('FPT')['wait_seconds']==5
    assert calls==['history']
    assert service.quote('FPT')['wait_seconds']==5 and calls==['history']
    assert json.loads(paths.output('data/stocks/FPT/data.json').read_text())['bars'][-1]['trade_date']=='2026-10-06'


def test_invalid_calendar_rate_and_saved_data_fail_closed(local_tmp):
    paths=ProjectPaths(local_tmp)
    paths.atomic_json('config/calendar.live.json',{'version':99})
    assert not SessionGate(paths).status('HOSE')['active']
    for kwargs in ({'max_calls':True},{'period':float('nan')},{'spacing':0}):
        with pytest.raises(ValueError):RateBudget(**kwargs)
    service=LiveService(paths,fetch=lambda *args:pytest.fail('unexpected source call'))
    with pytest.raises(ValueError):service.status('FPT')
    paths.atomic_json('data/stocks/FPT/data.json',{'bars':[{'symbol':'VCB','source':'vnstock_kbs'}]})
    with pytest.raises(ValueError):service.quote('FPT')


def test_backfill_closed_mid_request_and_unavailable_history(local_tmp):
    paths,now,service=setup_service(local_tmp,None)
    previous=json.loads(paths.output('data/stocks/FPT/data.json').read_text())
    previous['bars'][0]['trade_date']='2026-10-01'
    paths.atomic_json('data/stocks/FPT/data.json',previous)
    original=paths.output('data/stocks/FPT/data.json').read_bytes()
    now[0]=moment('2026-10-07T11:29:59')
    def close(*args):now[0]=moment('2026-10-07T11:30:00');return {}
    service.fetch=close
    assert service.quote('FPT')['session']['active'] is False
    assert paths.output('data/stocks/FPT/data.json').read_bytes()==original
    now[0]=moment('2026-10-07T10:00:00');service.budget=RateBudget(clock=lambda:200)
    service.fetch=lambda *args:{'rows':[{'time':'2026-10-01','open':'62','high':'62.2','low':'60','close':'60.4','volume':10}],
        'fetched_at':now[0].isoformat()}
    assert service.quote('FPT')['wait_seconds']==60
    assert paths.output('data/stocks/FPT/data.json').read_bytes()==original


def test_fresh_day_append_revision_and_basis_guards(local_tmp):
    paths,now,service=setup_service(local_tmp,None)
    now[0]=moment('2026-10-07T10:00:00')
    service.fetch=lambda *args:{'rows':[{**QUOTE,'TD':'07/10/2026'}],'fetched_at':now[0].isoformat()}
    result=service.quote('FPT')
    assert len(result['data']['bars'])==2 and result['quote']['revision']==1
    service.budget=RateBudget(clock=lambda:200)
    assert service.quote('FPT')['quote']['revision']==1
    data=result['data'];data['bars'][0]['price_basis']='adjusted';paths.atomic_json('data/stocks/FPT/data.json',data)
    with pytest.raises(ValueError):service.status('FPT')


def test_sdk_gate_closed_after_slow_import_never_applies_quote(local_tmp):
    paths,now,service=setup_service(local_tmp,lambda *args:{'session_closed':True})
    before=paths.output('data/stocks/FPT/data.json').read_bytes()
    assert service.quote('FPT')['session']['active'] is False
    assert paths.output('data/stocks/FPT/data.json').read_bytes()==before
