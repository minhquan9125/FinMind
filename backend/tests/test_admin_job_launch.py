"""Fixture-only launch of WBS16 staging runs from the admin API. Real runner, no DB/model/network."""
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routers import admin_jobs
from src.auth import authorization
from src.documents.news_batch_runner import digest

HEADERS = {'Authorization': 'Bearer fixture-token'}


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


def inputs(article_id='a1'):
    payload = {'documents': [{'document_id': 'fixture-document', 'doc_type': 'NEWS',
                             'chunks': [{'locator': {'source_table': 'news_articles', 'source_id': article_id}}]}]}
    manifest = {'corpus_version_id': 'fixture-corpus', 'manifest_sha256': digest(payload), 'manifest': payload}
    return {'manifest': manifest, 'articles': [{'article_id': article_id, 'content': 'FPT đã hoàn thiện hai AI Factory.'}]}


def test_launch_requires_an_administrator(client, monkeypatch):
    assert client.post('/api/v1/admin/jobs/runs', json=inputs()).status_code == 401
    async def roles(pool, user_id): return ['RESEARCHER']
    monkeypatch.setattr(authorization.repository, 'get_user_roles', roles)
    assert client.post('/api/v1/admin/jobs/runs', json=inputs(), headers=HEADERS).status_code == 403


def test_a_launched_run_produces_a_report_in_a_server_chosen_directory(client, tmp_path):
    started = client.post('/api/v1/admin/jobs/runs', json=inputs(), headers=HEADERS)
    assert started.status_code == 202
    job_id = started.json()['job_id']
    assert job_id.startswith('web-fixture-') and started.json()['mode'] == 'fixture'
    assert (tmp_path / job_id / 'report.json').is_file()                       # background task already ran
    listing = client.get('/api/v1/admin/jobs', headers=HEADERS).json()
    item = next(i for i in listing['items'] if i['job_id'] == job_id)
    assert item['mode'] == 'fixture' and item['counts']['PENDING_REVIEW'] == 1
    assert json.loads((tmp_path / job_id / 'launch.json').read_text())['status'] == 'COMPLETED'
    assert client.get(f'/api/v1/admin/jobs/{job_id}', headers=HEADERS).json()['items'][0]['article_id'] == 'a1'


def test_the_request_cannot_choose_paths_modes_or_extra_fields(client, tmp_path):
    for extra in ({'output': '/tmp/x'}, {'mode': 'full'}, {'receipt': {}}, {'directory': '..'}):
        response = client.post('/api/v1/admin/jobs/runs', json={**inputs(), **extra}, headers=HEADERS)
        assert response.status_code == 422
    assert not any(tmp_path.iterdir())


def test_bad_inputs_are_reported_by_code_without_leaking_details(client, tmp_path):
    bad = inputs(); bad['manifest']['manifest_sha256'] = 'f' * 64               # payload hash no longer matches
    job_id = client.post('/api/v1/admin/jobs/runs', json=bad, headers=HEADERS).json()['job_id']
    state = json.loads((tmp_path / job_id / 'launch.json').read_text())
    # The runner's free-text message is not an error code, so only a generic code is stored.
    assert state['status'] == 'FAILED' and state['reason'] == 'INPUT_VALIDATION_OR_IO_FAILED'
    assert 'hash' not in json.dumps(state).lower()
    item = next(i for i in client.get('/api/v1/admin/jobs', headers=HEADERS).json()['items'] if i['job_id'] == job_id)
    assert item['status'] == 'LAUNCH_FAILED' and str(tmp_path) not in json.dumps(item)


def test_only_one_launch_runs_at_a_time(client, tmp_path):
    running = tmp_path / 'web-fixture-20261101-000000-abcd'
    running.mkdir()
    now = datetime.now(timezone.utc).isoformat()
    (running / 'launch.json').write_text(json.dumps({'status': 'RUNNING', 'mode': 'fixture', 'started_at': now, 'updated_at': now}))
    blocked = client.post('/api/v1/admin/jobs/runs', json=inputs(), headers=HEADERS)
    assert blocked.status_code == 409 and blocked.json()['detail'] == 'JOB_ALREADY_RUNNING'
    item = next(i for i in client.get('/api/v1/admin/jobs', headers=HEADERS).json()['items'] if i['job_id'] == running.name)
    assert item['status'] == 'RUNNING'


def test_a_silent_run_stops_blocking_and_shows_as_failed(client, tmp_path):
    stale = tmp_path / 'web-fixture-20261101-000000-dead'
    stale.mkdir()
    old = (datetime.now(timezone.utc) - timedelta(seconds=admin_jobs.LAUNCH_STALE_SECONDS + 10)).isoformat()
    (stale / 'launch.json').write_text(json.dumps({'status': 'RUNNING', 'mode': 'fixture', 'started_at': old, 'updated_at': old}))
    assert client.post('/api/v1/admin/jobs/runs', json=inputs(), headers=HEADERS).status_code == 202
    item = next(i for i in client.get('/api/v1/admin/jobs', headers=HEADERS).json()['items'] if i['job_id'] == stale.name)
    assert item['status'] == 'LAUNCH_FAILED' and item['reason'] == 'WORKER_STOPPED'


def test_oversized_inputs_are_refused(client, monkeypatch):
    monkeypatch.setattr(admin_jobs, 'MAX_INPUT_BYTES', 200)
    response = client.post('/api/v1/admin/jobs/runs', json=inputs(), headers=HEADERS)
    assert response.status_code == 413 and response.json()['detail'] == 'JOB_INPUT_TOO_LARGE'


def test_runner_made_directories_and_launch_files_do_not_confuse_each_other(client, tmp_path):
    (tmp_path / 'plain-dir').mkdir()
    (tmp_path / 'broken-launch').mkdir(); (tmp_path / 'broken-launch' / 'launch.json').write_text('{not json')
    assert client.get('/api/v1/admin/jobs', headers=HEADERS).json()['items'] == []
