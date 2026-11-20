"""Delete approved articles one by one or in bulk, without ever touching indexed data."""
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routers import admin_ingestion as api
from src.auth.authorization import Principal
from src.documents.admin_ingestion import Queue, crawl_job


def article(n):
    return {'source': 'fireant', 'url': f'https://fireant.vn/bai-viet/fixture/{n}',
            'title': f'Nguồn kiểm thử {n}', 'content': f'FPT đã hoàn thiện hai AI Factory tại Việt Nam {n}.',
            'published_at': '2026-11-05T07:00:00+07:00', 'symbols': ['FPT'], 'raw': {'n': n}}


def populated(tmp_path, count=3, approve=True):
    q = Queue(tmp_path)
    j, _ = q.create_job('CRAWL', 'operator')
    crawl_job(q, j, lambda limit: ([article(n) for n in range(count)], []))
    ids = [row['id'] for row in q.articles()]
    if approve:
        for aid in ids: q.review(aid, 'APPROVED', 'Đã kiểm tra nội dung nguồn.', 'reviewer')
    return q, ids


def test_deleting_an_approved_article_hides_it_and_erases_its_content(tmp_path):
    q, ids = populated(tmp_path)
    result = q.delete_articles('admin', [ids[0]])
    assert result == {'deleted': [ids[0]], 'skipped': []}
    assert ids[0] not in [row['id'] for row in q.articles()]
    assert q.article_count() == 2 and q.article_count('APPROVED') == 2
    assert ids[0] not in q.selection()['approved_ids'] and 'DELETED' not in q.selection()['counts']
    with pytest.raises(ValueError, match='ARTICLE_NOT_FOUND'):
        q.article(ids[0])
    with q.connect() as c:
        assert c.execute('SELECT payload FROM articles WHERE id=?', (ids[0],)).fetchone()[0] == '{"deleted":true}'
    assert any(r.get('action') == 'DELETE_ARTICLE' and r.get('resource') == ids[0]
               for r in q.audit_page(category='operation')['items'])


def test_a_deleted_article_is_not_imported_again_by_the_next_crawl(tmp_path):
    q, ids = populated(tmp_path, count=2)
    q.delete_articles('admin', [ids[0]])
    j, _ = q.create_job('CRAWL', 'operator')
    crawl_job(q, j, lambda limit: ([article(n) for n in range(2)], []))
    assert q.article_count('PENDING') == 0
    assert ids[0] not in [row['id'] for row in q.articles()]
    assert q.article_count() == 1


def test_bulk_delete_reports_what_it_skipped_and_why(tmp_path):
    q, ids = populated(tmp_path, count=3, approve=False)
    q.review(ids[0], 'APPROVED', 'Đã kiểm tra nội dung nguồn.', 'reviewer')
    q.review(ids[1], 'APPROVED', 'Đã kiểm tra nội dung nguồn.', 'reviewer')
    unknown = '00000000-0000-0000-0000-000000000000'
    result = q.delete_articles('admin', [ids[0], ids[1], ids[1], ids[2], unknown])
    assert sorted(result['deleted']) == sorted([ids[0], ids[1]])
    assert {s['id']: s['reason'] for s in result['skipped']} == {ids[2]: 'NOT_APPROVED', unknown: 'NOT_FOUND'}
    assert q.article(ids[2])['status'] == 'PENDING'


def test_only_approved_articles_can_be_deleted(tmp_path):
    q, ids = populated(tmp_path, count=1, approve=False)
    assert q.delete_articles('admin', ids)['skipped'] == [{'id': ids[0], 'reason': 'NOT_APPROVED'}]
    q.review(ids[0], 'REJECTED', 'Không phù hợp phạm vi nguồn.', 'reviewer')
    assert q.delete_articles('admin', ids)['skipped'][0]['reason'] == 'NOT_APPROVED'


def test_articles_inside_a_stored_index_job_are_protected(tmp_path):
    q, ids = populated(tmp_path, count=2)
    job, _ = q.create_job('INDEX', 'operator', article_ids=[ids[0]])
    q.update_job(job, 'INDEXED', manifest_sha256='x')
    result = q.delete_articles('admin', ids)
    assert result['deleted'] == [ids[1]]
    assert result['skipped'] == [{'id': ids[0], 'reason': 'IN_INDEX_JOB'}]
    assert q.article(ids[0])['status'] == 'APPROVED'


def test_delete_is_refused_while_another_job_runs(tmp_path):
    q, ids = populated(tmp_path, count=1)
    q.create_job('CRAWL', 'operator')
    with pytest.raises(ValueError, match='ANOTHER_JOB_IS_RUNNING'):
        q.delete_articles('admin', ids)
    assert q.article(ids[0])['status'] == 'APPROVED'


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, 'get_settings', lambda: SimpleNamespace(admin_ingestion_directory=tmp_path, admin_ingest_database_url=None))
    app = FastAPI(); app.include_router(api.router)
    with TestClient(app) as c:
        yield c, app


def grant(app):
    app.dependency_overrides[api.access] = lambda: Principal(UUID(int=1), frozenset({'ADMINISTRATOR'}))


def test_api_requires_admin_and_validates_input(client):
    c, app = client
    base = '/api/v1/admin/ingestion/articles'
    assert c.post(base + '/delete', json={'article_ids': ['00000000-0000-0000-0000-000000000001']}).status_code == 401
    assert c.delete(base + '/00000000-0000-0000-0000-000000000001').status_code == 401
    grant(app)
    assert c.post(base + '/delete', json={'article_ids': []}).status_code == 422
    assert c.post(base + '/delete', json={'article_ids': ['not-a-uuid']}).status_code == 422
    assert c.post(base + '/delete', json={'article_ids': ['00000000-0000-0000-0000-000000000001'] * 501}).status_code == 422
    assert c.post(base + '/delete', json={'article_ids': ['00000000-0000-0000-0000-000000000001'], 'x': 1}).status_code == 422


def test_api_bulk_and_single_delete(client):
    c, app = client; grant(app)
    q = api.queue(); j, _ = q.create_job('CRAWL', 'operator')
    crawl_job(q, j, lambda limit: ([article(n) for n in range(3)], []))
    ids = [row['id'] for row in q.articles()]
    for aid in ids: q.review(aid, 'APPROVED', 'Đã kiểm tra nội dung nguồn.', 'reviewer')
    base = '/api/v1/admin/ingestion/articles'
    bulk = c.post(base + '/delete', json={'article_ids': ids[:2]})
    assert bulk.status_code == 200 and sorted(bulk.json()['deleted']) == sorted(ids[:2])
    assert c.get(base + '/selection').json()['counts'] == {'APPROVED': 1}
    assert c.get(base + '/' + ids[0]).status_code == 409  # ARTICLE_NOT_FOUND via operation()
    single = c.delete(base + '/' + ids[2])
    assert single.status_code == 200 and single.json()['deleted'] == [ids[2]]
    assert c.delete(base + '/' + ids[2]).status_code == 404
    assert c.get(base).json()['total'] == 0
