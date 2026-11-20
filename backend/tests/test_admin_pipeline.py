"""Optional crawl -> DB index -> corpus switch automation. No DB, embedding or network."""
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.api.routers import admin_ingestion as api
from src.auth.authorization import Principal
from src.documents import admin_pipeline
from src.documents.admin_ingestion import Queue, crawl_job
from src.documents.admin_pipeline import follow_up, run_full

WRITER = SimpleNamespace(admin_ingest_database_url='postgresql://writer')
NO_WRITER = SimpleNamespace(admin_ingest_database_url=None)


def article(n=1):
    return {'source': 'fireant', 'url': f'https://fireant.vn/bai-viet/fixture/{n}',
            'title': f'Nguồn kiểm thử {n}', 'content': 'FPT đã hoàn thiện hai AI Factory tại Việt Nam.',
            'published_at': '2026-11-05T07:00:00+07:00', 'symbols': ['FPT'], 'raw': {'original': 'source'}}


class Calls:
    def __init__(self): self.index, self.build = [], []

    def index_fn(self, queue, ident, settings):
        self.index.append(ident); queue.update_job(ident, 'ACTIVE')

    def build_fn(self, queue, ident, settings):
        self.build.append(ident); queue.update_job(ident, 'INDEXED')


def finished_crawl(tmp_path, *, approve=True, **config):
    q = Queue(tmp_path)
    j, _ = q.create_job('CRAWL', 'operator')
    crawl_job(q, j, lambda limit: ([article()], []))
    aid = q.articles()[0]['id']
    if approve:
        q.review(aid, 'APPROVED', 'Đã kiểm tra nội dung nguồn.', 'reviewer')
    q.config({**q.config(), **config})
    j2, _ = q.create_job('CRAWL', 'scheduler')
    crawl_job(q, j2, lambda limit: ([], []))
    return q, j2, aid


def test_everything_is_off_by_default(tmp_path):
    q, crawl, _ = finished_crawl(tmp_path)
    calls = Calls()
    result = follow_up(q, crawl, WRITER, index_fn=calls.index_fn, build_fn=calls.build_fn)
    assert result['skipped'] == 'AUTO_INDEX_OFF'
    assert not calls.index and not calls.build
    assert not [j for j in q.jobs() if j['kind'] == 'INDEX']


def test_auto_index_stores_in_the_db_but_does_not_switch_the_corpus(tmp_path):
    q, crawl, aid = finished_crawl(tmp_path, auto_index=True)
    calls = Calls()
    result = follow_up(q, crawl, WRITER, index_fn=calls.index_fn, build_fn=calls.build_fn)
    assert len(calls.build) == 1 and not calls.index
    job = q.get_job(calls.build[0])
    assert job['kind'] == 'INDEX' and job['details']['article_ids'] == [aid]
    assert result['index_status'] == 'INDEXED' and result['auto_activate'] is False


def test_auto_activate_runs_the_full_index_and_switch(tmp_path):
    q, crawl, _ = finished_crawl(tmp_path, auto_index=True, auto_activate=True)
    calls = Calls()
    result = follow_up(q, crawl, WRITER, index_fn=calls.index_fn, build_fn=calls.build_fn)
    assert len(calls.index) == 1 and not calls.build
    assert result['index_status'] == 'ACTIVE' and result['auto_activate'] is True


def test_missing_writer_connection_is_reported_not_attempted(tmp_path):
    q, crawl, _ = finished_crawl(tmp_path, auto_index=True, auto_activate=True)
    calls = Calls()
    result = follow_up(q, crawl, NO_WRITER, index_fn=calls.index_fn, build_fn=calls.build_fn)
    assert result['skipped'] == 'ADMIN_INGEST_DATABASE_URL_REQUIRED'
    assert not calls.index and not calls.build


def test_nothing_approved_means_nothing_indexed(tmp_path):
    q, crawl, _ = finished_crawl(tmp_path, approve=False, auto_index=True, auto_activate=True)
    calls = Calls()
    result = follow_up(q, crawl, WRITER, index_fn=calls.index_fn, build_fn=calls.build_fn)
    assert result['skipped'] == 'NO_APPROVED_ARTICLES'
    assert not calls.index and not calls.build


def test_articles_still_needing_ocr_are_never_indexed(tmp_path, monkeypatch):
    q, crawl, _ = finished_crawl(tmp_path, auto_index=True, auto_activate=True)
    monkeypatch.setattr(admin_pipeline, 'auto_review_reasons', lambda payload: {'OCR_REQUIRED'})
    calls = Calls()
    result = follow_up(q, crawl, WRITER, index_fn=calls.index_fn, build_fn=calls.build_fn)
    assert result['skipped'] == 'NO_APPROVED_ARTICLES'
    assert not calls.index and not calls.build


def test_failed_crawl_is_never_followed_by_indexing(tmp_path):
    q, crawl, _ = finished_crawl(tmp_path, auto_index=True, auto_activate=True)
    q.update_job(crawl, 'FAILED')
    calls = Calls()
    assert follow_up(q, crawl, WRITER, index_fn=calls.index_fn, build_fn=calls.build_fn)['skipped'] == 'CRAWL_NOT_COMPLETED'
    assert not calls.index and not calls.build


def test_a_failing_stage_is_recorded_and_never_raises(tmp_path):
    q, crawl, _ = finished_crawl(tmp_path, auto_index=True)

    def boom(queue, ident, settings): raise RuntimeError('db down')
    result = follow_up(q, crawl, WRITER, build_fn=boom)
    assert result['error'] == 'RuntimeError'
    assert q.get_job(crawl)['details']['pipeline']['error'] == 'RuntimeError'


def test_result_is_stored_on_the_crawl_job_and_audited(tmp_path):
    q, crawl, _ = finished_crawl(tmp_path, auto_index=True)
    calls = Calls()
    follow_up(q, crawl, WRITER, index_fn=calls.index_fn, build_fn=calls.build_fn)
    assert q.get_job(crawl)['details']['pipeline']['stage'] == 'INDEX'
    assert any(row.get('action') == 'AUTO_PIPELINE' for row in q.audit_page(category='operation')['items'])


def test_run_full_crawls_then_follows_up(tmp_path):
    q = Queue(tmp_path)
    j, _ = q.create_job('CRAWL', 'operator')
    crawl_job(q, j, lambda limit: ([article()], []))
    q.review(q.articles()[0]['id'], 'APPROVED', 'Đã kiểm tra nội dung nguồn.', 'reviewer')
    q.config({**q.config(), 'auto_index': True})
    j2, _ = q.create_job('CRAWL', 'scheduler')
    calls = Calls()
    result = run_full(q, j2, WRITER, collector=lambda limit: ([article(2)], []),
                      index_fn=calls.index_fn, build_fn=calls.build_fn)
    assert result['stage'] == 'INDEX' and len(calls.build) == 1
    assert q.get_job(j2)['status'] in ('COMPLETED', 'PARTIAL')


def test_auto_activate_requires_auto_index():
    with pytest.raises(ValidationError):
        api.SourceConfig(auto_activate=True, auto_index=False)
    assert api.SourceConfig(auto_activate=True, auto_index=True).auto_activate is True
    assert api.SourceConfig().auto_index is False and api.SourceConfig().auto_activate is False


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, 'get_settings', lambda: SimpleNamespace(admin_ingestion_directory=tmp_path, admin_ingest_database_url=None))
    app = FastAPI(); app.include_router(api.router)
    with TestClient(app) as c:
        yield c, app


def test_pipeline_endpoint_requires_admin_and_a_writer_when_indexing(client, monkeypatch):
    c, app = client
    assert c.post('/api/v1/admin/ingestion/pipeline').status_code == 401
    app.dependency_overrides[api.access] = lambda: Principal(UUID(int=1), frozenset({'ADMINISTRATOR'}))
    api.queue().config({**api.queue().config(), 'auto_index': True})
    assert c.post('/api/v1/admin/ingestion/pipeline').status_code == 503
    assert c.get('/api/v1/admin/ingestion/source').json()['auto_index'] is True
    assert c.put('/api/v1/admin/ingestion/source', json={'auto_activate': True, 'auto_index': False}).status_code == 422
