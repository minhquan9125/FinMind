from datetime import datetime,timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4,UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.routers import admin_ingestion as api
from src.auth.authorization import Principal,current_principal
from src.documents.api_budget import ApiBudget
from src.documents.research_metrics import ResearchMetrics


def cfg():return {'mode':'paid','period':'month','limit_usd':'0.000020','warn_at':80,
    'rates':[{'model':'test-model','input_per_million':'1','output_per_million':'2'}]}


def seed(root):
    metrics=ResearchMetrics(root);ident=str(uuid4())
    metrics.record(ident,'2026-11-05T17:05:00+00:00',1200,
        {'scope':{'companies':['ICT']},'answering':{'status':'DRAFT_READY','reason_code':'SUCCESS',
            'citations':[{'chunk_id':'chunk-1','locator':{'url':'https://fireant.vn/source'}}]}},
        [{'model':'test-model','usage':{'input_tokens':10,'output_tokens':3,'total_tokens':15}}],question='Câu hỏi kiểm thử')
    return metrics,ident


def test_budget_uses_exact_decimal_and_bills_reasoning_as_output(tmp_path):
    seed(tmp_path);store=ApiBudget(tmp_path);version=store.save(cfg(),'admin','test setup',None)
    snap=store.snapshot(datetime(2026,11,6,tzinfo=timezone.utc))
    # 10 input + (3 visible output + 2 reasoning)*2 = 20 microdollars
    assert Decimal(snap['usage']['used_usd'])==Decimal('0.000020')
    assert snap['usage']['warning'] and snap['usage']['exceeded']
    assert snap['usage']['percent']==100 and snap['usage']['complete']
    with pytest.raises(ValueError,match='BUDGET_CONFIG_CHANGED'):store.save(cfg(),'admin','stale',None)
    store.save({**cfg(),'mode':'free'},'admin','switch free',version)
    assert Decimal(ApiBudget(tmp_path).snapshot(datetime(2026,11,6,tzinfo=timezone.utc))['usage']['used_usd'])==0


def test_missing_rates_unknown_usage_and_vietnam_day_boundaries(tmp_path):
    metrics,ident=seed(tmp_path)
    metrics.record(str(uuid4()),'2026-11-05T17:10:00+00:00',5,{},[{'model':'test-model','usage':None}])
    metrics.record(str(uuid4()),'2026-11-05T16:59:00+00:00',5,{},[{'model':'unpriced','usage':None}])
    store=ApiBudget(tmp_path);config={**cfg(),'period':'day','rates':[{'model':'different','input_per_million':'1','output_per_million':'2'}]}
    store.save(config,'admin','setup',None)
    u=store.snapshot(datetime(2026,11,6,tzinfo=timezone.utc))['usage']
    assert u['unknown_calls']==1 and u['unpriced_calls']==1 and not u['complete']
    assert len(metrics.list(day='2026-11-06')['items'])==2
    assert metrics.list(company='BID')['total']==0
    assert metrics.list(company='ICT',outcome_filter='SUCCESS')['total']==1
    assert metrics.detail(ident)['details']['question']=='Câu hỏi kiểm thử'


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(api,'get_settings',lambda:SimpleNamespace(admin_ingestion_directory=tmp_path))
    app=FastAPI();app.include_router(api.router)
    with TestClient(app) as c:yield c,app,tmp_path


def test_new_endpoints_require_admin_and_validate_updates(client):
    c,app,root=client
    for path in ['/budget','/traces']:
        assert c.get('/api/v1/admin/ingestion'+path).status_code==401
    app.dependency_overrides[current_principal]=lambda:Principal(UUID(int=1),frozenset({'RESEARCHER'}))
    assert c.get('/api/v1/admin/ingestion/traces').status_code==403
    assert c.put('/api/v1/admin/ingestion/budget',json={}).status_code==403
    app.dependency_overrides[current_principal]=lambda:Principal(UUID(int=1),frozenset({'ADMINISTRATOR'}))
    assert c.get('/api/v1/admin/ingestion/budget').json()['version'] is None
    body={**cfg(),'reason':'test reason','expected_version':None}
    saved=c.put('/api/v1/admin/ingestion/budget',json=body)
    assert saved.status_code==200 and len(saved.json()['history'])==1
    assert c.put('/api/v1/admin/ingestion/budget',json=body).status_code==409
    for invalid in [{'limit_usd':'0'},{'warn_at':101},{'rates':[]},{'limit_usd':'NaN'},{'mode':'paid','rates':cfg()['rates']*2}]:
        assert c.put('/api/v1/admin/ingestion/budget',json={**body,**invalid}).status_code==422
    metrics,ident=seed(root)
    assert c.get('/api/v1/admin/ingestion/traces?company=ICT&day=2026-11-06').json()['total']==1
    assert c.get('/api/v1/admin/ingestion/traces?day=2026-99-99').status_code==422
    assert c.get('/api/v1/admin/ingestion/traces/'+ident).json()['id']==ident
    assert c.get('/api/v1/admin/ingestion/traces/'+str(uuid4())).status_code==404
