"""Admin authorization and real report projection; no DB/model/network."""
import json
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routers import admin_jobs
from src.auth import authorization
from src.documents.news_batch_runner import digest, run


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(admin_jobs, 'get_settings', lambda: SimpleNamespace(admin_jobs_directory=tmp_path))
    monkeypatch.setattr(authorization, 'read_access_token', lambda token, settings: UUID(int=1))
    monkeypatch.setattr(authorization, 'get_pool', lambda: object())
    async def user(pool, user_id): return {'is_active': True}
    async def roles(pool, user_id): return ['ADMINISTRATOR']
    monkeypatch.setattr(authorization.repository, 'find_user_by_id', user)
    monkeypatch.setattr(authorization.repository, 'get_user_roles', roles)
    app = FastAPI(); app.include_router(admin_jobs.router)
    with TestClient(app) as test_client:
        yield test_client


HEADERS = {'Authorization': 'Bearer fixture-token'}


def create_job(root, name='fixture-job'):
    payload = {'documents': [{'document_id': 'fixture-document', 'doc_type': 'NEWS',
                             'chunks': [{'locator': {'source_table': 'news_articles', 'source_id': 'a1'}}]}]}
    manifest = {'corpus_version_id': 'fixture-corpus', 'manifest_sha256': digest(payload), 'manifest': payload}
    run(manifest, [{'article_id': 'a1', 'content': 'FPT đã hoàn thiện hai AI Factory.'}], root / name)


def test_requires_actual_server_grant_before_reading_reports(client, monkeypatch):
    assert client.get('/api/v1/admin/jobs').status_code == 401
    async def roles(pool, user_id): return ['RESEARCHER']
    monkeypatch.setattr(authorization.repository, 'get_user_roles', roles)
    assert client.get('/api/v1/admin/jobs', headers=HEADERS).status_code == 403
    assert client.get('/api/v1/admin/jobs/fixture-job', headers=HEADERS).status_code == 403


def test_empty_list_and_unknown_detail(client):
    assert client.get('/api/v1/admin/jobs', headers=HEADERS).json()['items'] == []
    assert client.get('/api/v1/admin/jobs/missing', headers=HEADERS).status_code == 404


def test_runner_report_survives_api_projection_without_approval_claim(client, tmp_path):
    create_job(tmp_path)
    data = client.get('/api/v1/admin/jobs', headers=HEADERS).json()
    assert data['total'] == 1
    item = data['items'][0]
    assert item['mode'] == 'fixture' and item['counts']['PENDING_REVIEW'] == 1
    assert item['acceptance_status'] == 'NOT_EVALUATED'
    assert item['database_reconciliation'] == 'NOT_READY'
    detail = client.get('/api/v1/admin/jobs/fixture-job', headers=HEADERS).json()
    assert detail['items'] == [{'article_id': 'a1', 'status': 'PENDING_REVIEW', 'reason': None}]
    assert str(tmp_path) not in json.dumps(detail)
    assert 'AI Factory' not in json.dumps(detail)
    # Same response after a fresh read: no in-memory mock state.
    assert client.get('/api/v1/admin/jobs/fixture-job', headers=HEADERS).json() == detail


def test_pagination_validation_and_no_mutations(client, tmp_path):
    create_job(tmp_path, 'job-a'); create_job(tmp_path, 'job-b')
    data = client.get('/api/v1/admin/jobs?offset=1&limit=1', headers=HEADERS).json()
    assert data['total'] == 2 and data['items'][0]['job_id'] == 'job-b'
    assert client.get('/api/v1/admin/jobs?limit=1000', headers=HEADERS).status_code == 422
    assert client.get('/api/v1/admin/jobs/job-a?offset=-1', headers=HEADERS).status_code == 422
    assert client.post('/api/v1/admin/jobs', headers=HEADERS).status_code == 405


def test_corrupt_report_is_visible_without_leaking_contents(client, tmp_path):
    create_job(tmp_path)
    path = tmp_path / 'fixture-job/report.json'
    report = json.loads(path.read_text('utf-8'))
    report['counts']['ERROR'] = 99
    report['connection'] = 'postgres://secret@private'
    path.write_text(json.dumps(report), encoding='utf-8')
    data = client.get('/api/v1/admin/jobs', headers=HEADERS).json()
    assert data['items'] == [{'job_id': 'fixture-job', 'status': 'INVALID_REPORT'}]
    response = client.get('/api/v1/admin/jobs/fixture-job', headers=HEADERS)
    assert response.status_code == 409 and 'secret' not in response.text


def test_malformed_job_id_and_outside_path_are_not_read(client, tmp_path):
    create_job(tmp_path)
    assert client.get('/api/v1/admin/jobs/bad.name', headers=HEADERS).status_code == 404
    # Check confinement directly, independent of HTTP URL normalization.
    with pytest.raises(Exception) as error:
        admin_jobs.load_report(tmp_path.resolve(), '../elsewhere')
    assert error.value.status_code == 404


def test_inactive_admin_is_denied(client, monkeypatch):
    async def inactive(pool, user_id): return {'is_active': False}
    monkeypatch.setattr(authorization.repository, 'find_user_by_id', inactive)
    assert client.get('/api/v1/admin/jobs', headers=HEADERS).status_code == 401
