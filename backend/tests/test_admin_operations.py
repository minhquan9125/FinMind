from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routers import admin_ingestion as api
from src.auth.authorization import Principal, current_principal
from src.core import db
from src.documents.admin_ingestion import Queue, crawl_job


@pytest.fixture
def client(tmp_path, monkeypatch):
    settings = SimpleNamespace(admin_ingestion_directory=tmp_path, research_corpus_version_id=str(UUID(int=2)))
    monkeypatch.setattr(api, 'get_settings', lambda: settings)
    app = FastAPI(); app.include_router(api.router)
    with TestClient(app) as client:
        yield client, app, Queue(tmp_path)


def allow(app, roles=frozenset({'ADMINISTRATOR'})):
    app.dependency_overrides[api.access] = lambda: Principal(UUID(int=1), roles)


def test_operations_require_authentication(client):
    c, app, q = client
    assert c.get('/api/v1/admin/ingestion/overview').status_code == 401
    assert c.get('/api/v1/admin/ingestion/audit').status_code == 401
    app.dependency_overrides[current_principal] = lambda: Principal(UUID(int=1), frozenset({'RESEARCHER'}))
    assert c.get('/api/v1/admin/ingestion/overview').status_code == 403
    assert c.get('/api/v1/admin/ingestion/audit').status_code == 403


def test_overview_reports_all_jobs_and_survives_database_failure(client, monkeypatch):
    c, app, q = client; allow(app)
    for i in range(103):
        job, _ = q.create_job('CRAWL', 'operator')
        q.update_job(job, 'FAILED', error='private connection string')
    monkeypatch.setattr(db, 'get_pool', lambda: (_ for _ in ()).throw(RuntimeError('postgres://secret')))
    response = c.get('/api/v1/admin/ingestion/overview')
    assert response.status_code == 200
    data = response.json()
    assert data['job_counts']['FAILED'] == 103
    assert len(data['recent_jobs']) == 8
    assert data['storage'] == {'status': 'unavailable'}
    assert 'secret' not in response.text and 'private' not in response.text


def test_overview_reads_current_serving_corpus(client, monkeypatch):
    c, app, q = client; allow(app)
    corpus = str(UUID(int=33)); q.publish_corpus(corpus, str(UUID(int=34)))
    class Conn:
        async def fetchrow(self, sql, ident):
            assert ident == UUID(corpus)
            return {'corpus_status':'FROZEN','index_status':'ACTIVE','index_id':str(UUID(int=34)),
                    'documents':12,'chunks':100}
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
    monkeypatch.setattr(db, 'get_pool', lambda: SimpleNamespace(acquire=lambda: Conn()))
    data = c.get('/api/v1/admin/ingestion/overview').json()
    assert data['corpus_id'] == corpus
    assert data['storage']['chunks'] == 100 and data['storage']['status'] == 'available'


def test_audit_combines_historical_reviews_and_operations_and_paginates(client):
    c, app, q = client; allow(app)
    job, _ = q.create_job('CRAWL', 'operator')
    crawl_job(q, job, lambda limit: ([{'title':'Bài kiểm thử', 'url':'https://fireant.vn/bai-viet/test/123',
        'content':'Nội dung bài kiểm thử đầy đủ. ' * 20}], []))
    aid = q.articles()[0]['id']
    q.review(aid, 'APPROVED', 'Đã kiểm tra văn bản gốc.', 'human-reviewer')
    q.audit('operator', 'SOURCE_CONFIG', 'fireant')
    first = c.get('/api/v1/admin/ingestion/audit?limit=1').json()
    second = c.get('/api/v1/admin/ingestion/audit?limit=1&offset=1').json()
    assert first['total'] == 2 and first['items'][0]['id'] != second['items'][0]['id']
    reviews = c.get('/api/v1/admin/ingestion/audit?category=review').json()
    assert reviews['total'] == 1 and reviews['items'][0]['resource'] == aid
    assert reviews['items'][0]['note'] == 'Đã kiểm tra văn bản gốc.'
    assert c.get('/api/v1/admin/ingestion/audit?category=operation').json()['total'] == 1
    assert c.get('/api/v1/admin/ingestion/audit?category=invalid').status_code == 422
    assert c.get('/api/v1/admin/ingestion/audit?offset=-1').status_code == 422
    assert c.get('/api/v1/admin/ingestion/audit?limit=101').status_code == 422
