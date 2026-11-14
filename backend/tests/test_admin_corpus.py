"""Read-only corpus views for the admin page. A fake connection stands in for PostgreSQL."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routers import admin_ingestion as api
from src.auth.authorization import Principal
from src.core import db
from src.documents.admin_corpus import list_documents, list_versions

A, B = '11111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222'
NOW = datetime(2026, 11, 6, tzinfo=timezone.utc)


class Conn:
    def __init__(self):
        self.sql = []

    async def fetch(self, sql, *args):
        self.sql.append(sql)
        if 'FROM public.corpus_versions cv' in sql:
            base = dict(version_label='v', description=None, frozen_at=NOW, manifest_sha256='x' * 64,
                        index_status='ACTIVE', embedding_model='bge-m3', built_at=NOW, documents=3)
            return [{**base, 'corpus_version_id': A, 'status': 'FROZEN', 'index_version_id': 'i1'},
                    {**base, 'corpus_version_id': B, 'status': 'FROZEN', 'index_version_id': 'i2', 'documents': 1}]
        if 'GROUP BY 1, 2' in sql:
            return [{'corpus_version_id': A, 'doc_type': 'NEWS', 'n': 2}, {'corpus_version_id': A, 'doc_type': 'BCTN', 'n': 1}]
        if 'SELECT DISTINCT d.doc_type' in sql:
            return [{'doc_type': 'BCTN'}, {'doc_type': 'NEWS'}]
        if 'cd.document_hash' in sql:
            return [{'document_id': 'd1', 'title': 'Tin FPT', 'doc_type': 'NEWS', 'symbol': 'FPT',
                     'document_hash': 'h', 'hash_matches': True}]
        raise AssertionError(sql)

    async def fetchval(self, sql, *args):
        self.sql.append(sql)
        if 'FROM public.corpus_versions WHERE' in sql:
            return 1 if str(args[0]) == A else None
        if sql.lstrip().startswith('SELECT count(*)'):
            return 7
        raise AssertionError(sql)


def run(coro):
    return asyncio.run(coro)


def test_versions_mark_the_serving_corpus_and_count_documents_by_type():
    out = run(list_versions(Conn(), B))
    assert out['serving_corpus_id'] == B
    first, second = out['items']
    assert (first['serving'], second['serving']) == (False, True)
    assert first['by_type'] == {'NEWS': 2, 'BCTN': 1} and second['by_type'] == {}
    assert first['documents'] == 3 and first['embedding_model'] == 'bge-m3'


def test_no_serving_corpus_marks_nothing():
    out = run(list_versions(Conn(), None))
    assert out['serving_corpus_id'] is None and not any(i['serving'] for i in out['items'])


def test_documents_are_paged_and_report_hash_agreement():
    out = run(list_documents(Conn(), A, offset=10, limit=5))
    assert out['total'] == 7 and out['offset'] == 10 and out['limit'] == 5
    assert out['items'][0]['hash_matches'] is True and out['doc_types'] == ['BCTN', 'NEWS']


def test_unknown_corpus_returns_none():
    assert run(list_documents(Conn(), B)) is None


def test_doc_type_filter_is_a_bound_parameter_not_interpolated_text():
    conn = Conn()
    run(list_documents(conn, A, doc_type="NEWS'; DROP TABLE documents;--"))
    assert not any('DROP TABLE' in sql for sql in conn.sql)
    assert any('d.doc_type = $2' in sql for sql in conn.sql)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, 'get_settings', lambda: SimpleNamespace(
        admin_ingestion_directory=tmp_path, admin_ingest_database_url=None, research_corpus_version_id=A))
    conn = Conn()

    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield conn

    monkeypatch.setattr(db, 'get_pool', lambda: Pool())
    app = FastAPI(); app.include_router(api.router)
    with TestClient(app) as c:
        yield c, app


def grant(app):
    app.dependency_overrides[api.access] = lambda: Principal(UUID(int=1), frozenset({'ADMINISTRATOR'}))


def test_endpoints_require_admin(client):
    c, _ = client
    assert c.get('/api/v1/admin/ingestion/corpus').status_code == 401
    assert c.get(f'/api/v1/admin/ingestion/corpus/{A}/documents').status_code == 401


def test_endpoints_return_data_and_map_errors(client):
    c, app = client; grant(app)
    versions = c.get('/api/v1/admin/ingestion/corpus').json()
    assert versions['serving_corpus_id'] == A and versions['items'][0]['serving'] is True
    docs = c.get(f'/api/v1/admin/ingestion/corpus/{A}/documents?limit=5').json()
    assert docs['total'] == 7 and docs['items'][0]['symbol'] == 'FPT'
    assert c.get(f'/api/v1/admin/ingestion/corpus/{B}/documents').status_code == 404
    assert c.get('/api/v1/admin/ingestion/corpus/not-a-uuid/documents').status_code == 422
    assert c.get(f'/api/v1/admin/ingestion/corpus/{A}/documents?limit=101').status_code == 422
    assert c.get(f'/api/v1/admin/ingestion/corpus/{A}/documents?doc_type=news;drop').status_code == 422
