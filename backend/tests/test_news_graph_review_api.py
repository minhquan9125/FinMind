import uuid
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from src.api.routers import news_graph_review as api
from src.auth.authorization import Principal,current_principal
from src.graph_review.adapters import from_envelope
from tests.test_news_graph_contract import payload

def app():
    value=FastAPI();value.include_router(api.router);return value

def body():
    return dict(graph_version_id=str(uuid.uuid4()),candidate=from_envelope(payload())[0],note='Đã đối chiếu nguồn và ngày trong nội dung.')

@pytest.mark.parametrize('path',['approve','evaluate','publish','state'])
def test_news_mutations_and_source_reads_require_authentication(monkeypatch,path):
    async def forbidden(*args):raise AssertionError('must not open writer before auth')
    monkeypatch.setattr(api,'connect_writer',forbidden)
    result=TestClient(app()).post('/api/v1/admin/news-graph/'+path,json=body())
    assert result.status_code==401

@pytest.mark.parametrize('path',['approve','evaluate','publish','state'])
def test_non_admin_cannot_review_or_publish(monkeypatch,path):
    value=app();value.dependency_overrides[current_principal]=lambda:Principal(uuid.uuid4(),frozenset({'RESEARCHER'}))
    assert TestClient(value).post('/api/v1/admin/news-graph/'+path,json=body()).status_code==403

def test_approval_uses_server_principal_not_actor_fields_from_browser(monkeypatch):
    principal=Principal(uuid.uuid4(),frozenset({'ADMINISTRATOR'}));value=app()
    value.dependency_overrides[current_principal]=lambda:principal
    calls=[]
    class Connection:
        async def close(self):calls.append('closed')
    async def connect(*args):return Connection()
    async def approve(conn,actor,gid,candidate,note):
        assert actor is principal
        calls.append(candidate)
        return dict(review_id=str(uuid.uuid4()),result={'status':'APPROVED'},revision=2)
    monkeypatch.setattr(api,'connect_writer',connect);monkeypatch.setattr(api,'approve_news',approve)
    data=body();result=TestClient(value).post('/api/v1/admin/news-graph/approve',json=data)
    assert result.status_code==200 and result.json()['published'] is False
    assert calls[-1]=='closed'
    data['actor_id']=str(uuid.uuid4())
    assert TestClient(value).post('/api/v1/admin/news-graph/approve',json=data).status_code==422

def test_publish_cannot_accept_an_unreviewed_candidate_in_request(monkeypatch):
    value=app();value.dependency_overrides[current_principal]=lambda:Principal(uuid.uuid4(),frozenset({'ADMINISTRATOR'}))
    assert TestClient(value).post('/api/v1/admin/news-graph/publish',json=body()).status_code==422

def test_persistence_conflict_returns_a_safe_specific_reason(monkeypatch):
    value=app();value.dependency_overrides[current_principal]=lambda:Principal(uuid.uuid4(),frozenset({'ADMINISTRATOR'}))
    class Connection:
        async def close(self):pass
    async def connect(*args):return Connection()
    async def fail(*args):raise api.ReviewConflict('Expected one existing quarantine review record')
    monkeypatch.setattr(api,'connect_writer',connect);monkeypatch.setattr(api,'approve_news',fail)
    result=TestClient(value).post('/api/v1/admin/news-graph/approve',json=body())
    assert result.status_code==409
    assert result.json()['detail']=={'code':'QUARANTINE_HISTORY_MISSING'}
