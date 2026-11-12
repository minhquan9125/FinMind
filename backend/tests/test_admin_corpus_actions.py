"""Switch serving corpus, archive and restore. Fake DB connections, real SQLite queue."""
import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routers import admin_ingestion as api
from src.auth.authorization import Principal
from src.core import db
from src.documents import admin_news_index
from src.documents.admin_corpus import CorpusActionError, servable, set_archived, switch_serving
from src.documents.admin_ingestion import Queue

OLD, NEW, DEFAULT = ('aaaaaaaa-0000-0000-0000-00000000000%d' % n for n in (1, 2, 3))
IDX_OLD, IDX_NEW = 'bbbbbbbb-0000-0000-0000-000000000001', 'bbbbbbbb-0000-0000-0000-000000000002'


def row(corpus, index, status='FROZEN', index_status='ACTIVE', manifest='m' * 64):
    return {'corpus_version_id': corpus, 'status': status, 'manifest_sha256': manifest,
            'index_version_id': index, 'index_status': index_status}


class Conn:
    def __init__(self, rows, update='UPDATE 1'):
        self.rows, self.update, self.executed = rows, update, []

    async def fetchrow(self, sql, cid):
        return self.rows.get(str(cid))

    async def execute(self, sql, *args):
        self.executed.append((sql, args))
        return self.update

    async def close(self): pass


def run(coro):
    return asyncio.run(coro)


def conn(**kwargs):
    return Conn({OLD: row(OLD, IDX_OLD), NEW: row(NEW, IDX_NEW), DEFAULT: row(DEFAULT, 'b3')}, **kwargs)


def test_servable_needs_frozen_active_index_and_manifest():
    assert servable(row(OLD, IDX_OLD))
    assert not servable(row(OLD, IDX_OLD, status='ARCHIVED'))
    assert not servable(row(OLD, IDX_OLD, index_status='BUILDING'))
    assert not servable(row(OLD, IDX_OLD, manifest=None))


def test_switch_moves_the_serving_pointer_and_audits(tmp_path):
    q = Queue(tmp_path); q.publish_corpus(NEW, IDX_NEW)
    result = run(switch_serving(conn(), q, OLD, DEFAULT, 'admin'))
    assert q.serving_corpus(DEFAULT) == OLD
    assert result['corpus_version_id'] == OLD and result['previous_corpus_id'] == NEW
    assert any(r['action'] == 'SWITCH_CORPUS' for r in q.audit_page(category='operation')['items'])


def test_switch_refusals_leave_the_pointer_alone(tmp_path):
    q = Queue(tmp_path); q.publish_corpus(NEW, IDX_NEW)
    for rows, target, code in (
        (conn(), '00000000-0000-0000-0000-000000000009', 'CORPUS_NOT_FOUND'),
        (Conn({OLD: row(OLD, IDX_OLD, status='ARCHIVED')}), OLD, 'CORPUS_NOT_SERVABLE'),
        (Conn({OLD: row(OLD, IDX_OLD, index_status='BUILDING')}), OLD, 'CORPUS_NOT_SERVABLE'),
        (conn(), NEW, 'ALREADY_SERVING'),
    ):
        with pytest.raises(CorpusActionError, match=code):
            run(switch_serving(rows, q, target, DEFAULT, 'admin'))
    assert q.serving_corpus(DEFAULT) == NEW


def test_archive_and_restore_update_only_the_expected_state(tmp_path):
    q = Queue(tmp_path); q.publish_corpus(NEW, IDX_NEW)
    c = conn()
    assert run(set_archived(c, q, OLD, True, DEFAULT, 'admin')) == {'corpus_version_id': OLD, 'status': 'ARCHIVED'}
    assert c.executed[0][1][1:] == ('ARCHIVED', 'FROZEN')
    archived = Conn({OLD: row(OLD, IDX_OLD, status='ARCHIVED')})
    assert run(set_archived(archived, q, OLD, False, DEFAULT, 'admin'))['status'] == 'FROZEN'
    assert archived.executed[0][1][1:] == ('FROZEN', 'ARCHIVED')
    actions = [r['action'] for r in q.audit_page(category='operation')['items']]
    assert 'ARCHIVE_CORPUS' in actions and 'RESTORE_CORPUS' in actions


def test_the_serving_and_the_default_corpus_cannot_be_archived(tmp_path):
    q = Queue(tmp_path); q.publish_corpus(NEW, IDX_NEW)
    c = conn()
    for target in (NEW, DEFAULT):
        with pytest.raises(CorpusActionError, match='CORPUS_IN_USE'):
            run(set_archived(c, q, target, True, DEFAULT, 'admin'))
    assert not c.executed


def test_archive_detects_a_concurrent_change(tmp_path):
    q = Queue(tmp_path); q.publish_corpus(NEW, IDX_NEW)
    with pytest.raises(CorpusActionError, match='CORPUS_STATE_CHANGED'):
        run(set_archived(conn(update='UPDATE 0'), q, OLD, True, DEFAULT, 'admin'))
    with pytest.raises(CorpusActionError, match='CORPUS_STATE_CHANGED'):  # restoring something not archived
        run(set_archived(conn(), q, OLD, False, DEFAULT, 'admin'))


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, 'get_settings', lambda: SimpleNamespace(
        admin_ingestion_directory=tmp_path, research_corpus_version_id=DEFAULT,
        admin_ingest_database_url=SimpleNamespace(get_secret_value=lambda: 'postgresql://writer')))
    fake = conn()

    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield fake

    async def writer(settings): return fake

    monkeypatch.setattr(db, 'get_pool', lambda: Pool())
    monkeypatch.setattr(admin_news_index, 'connect_writer', writer)
    Queue(tmp_path).publish_corpus(NEW, IDX_NEW)
    app = FastAPI(); app.include_router(api.router)
    with TestClient(app) as c:
        yield c, app, fake


def grant(app):
    app.dependency_overrides[api.access] = lambda: Principal(UUID(int=1), frozenset({'ADMINISTRATOR'}))


def test_api_requires_admin(client):
    c, _, _ = client
    for action in ('serve', 'archive', 'restore'):
        assert c.post(f'/api/v1/admin/ingestion/corpus/{OLD}/{action}').status_code == 401


def test_api_switch_archive_restore_and_error_codes(client):
    c, app, fake = client; grant(app)
    base = '/api/v1/admin/ingestion/corpus/'
    assert c.post(base + f'{OLD}/serve').json()['corpus_version_id'] == OLD
    assert c.post(base + f'{OLD}/serve').json()['detail'] == 'ALREADY_SERVING'
    assert c.post(base + '00000000-0000-0000-0000-000000000009/serve').status_code == 404
    assert c.post(base + f'{NEW}/archive').status_code == 200  # no longer serving after the switch
    assert c.post(base + f'{OLD}/archive').json()['detail'] == 'CORPUS_IN_USE'
    assert c.post(base + f'{DEFAULT}/archive').json()['detail'] == 'CORPUS_IN_USE'
    fake.rows[NEW] = row(NEW, IDX_NEW, status='ARCHIVED')
    assert c.post(base + f'{NEW}/restore').json() == {'corpus_version_id': NEW, 'status': 'FROZEN'}
    assert c.post(base + 'not-a-uuid/serve').status_code == 422


def test_archive_needs_the_writer_connection(client, monkeypatch, tmp_path):
    c, app, _ = client; grant(app)
    monkeypatch.setattr(api, 'get_settings', lambda: SimpleNamespace(
        admin_ingestion_directory=tmp_path, research_corpus_version_id=DEFAULT, admin_ingest_database_url=None))
    assert c.post(f'/api/v1/admin/ingestion/corpus/{OLD}/archive').json()['detail'] == 'ADMIN_INGEST_DATABASE_URL_REQUIRED'
