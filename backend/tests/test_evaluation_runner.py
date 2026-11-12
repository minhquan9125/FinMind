"""Evaluation runs: sequential, resilient, one at a time. A fake chat engine replaces Gemini."""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routers import admin_ingestion as api
from src.auth.authorization import Principal
from src.documents import evaluation_runner
from src.documents.evaluation_runner import EvaluationStore, run_evaluation, summarize

ITEMS = [
    {'id': 'Q01', 'question': 'Doanh thu?', 'expected': '3.984 tỷ đồng', 'category': 'a', 'verified': True},
    {'id': 'Q02', 'question': 'Ngày?', 'expected': 'Ngày 22/09/2026', 'category': 'b', 'verified': True},
    {'id': 'Q03', 'question': 'Giá mục tiêu?', 'expected': 'Không có thông tin / Hệ thống phải từ chối trả lời (Safe Refusal).', 'verified': False},
]


class Engine:
    def __init__(self, behave): self.behave, self.asked = behave, []

    async def answer(self, question, session_id, *args, **kwargs):
        self.asked.append((question, session_id))
        return await self.behave(question)


def draft(text, status='DRAFT_READY', route='VECTOR'):
    return {'status': 'EVIDENCE_READY', 'hybrid_router': {'route': route},
            'answering': {'status': status, 'draft': text, 'citations': [{'evidence_id': 'e'}]}}


def run(store, engine, items=ITEMS, **kw):
    ident = store.create('admin', len(items))
    asyncio.run(run_evaluation(store, engine, ident, items, **kw))
    return ident


def test_a_full_run_scores_each_question_and_summarises(tmp_path):
    async def behave(question):
        if question == 'Doanh thu?': return draft('Doanh thu đạt 3.984 tỷ đồng.')
        if question == 'Ngày?': return draft('Sự kiện diễn ra ngày 1/1/2026.')           # wrong date
        return {'status': 'NO_DATA', 'message': 'Chưa đủ bằng chứng.', 'answering': {'status': 'SKIPPED'}}
    store = EvaluationStore(tmp_path)
    ident = run(store, Engine(behave))
    run_ = store.get(ident)
    assert run_['status'] == 'COMPLETED' and run_['done'] == 3
    levels = {r['qid']: r['level'] for r in run_['results']}
    assert levels == {'Q01': 'PASS', 'Q02': 'FAIL', 'Q03': 'PASS'}        # Q03: refusing is the right answer
    first = run_['results'][0]
    assert first['route'] == 'VECTOR' and first['citations'] == 1 and first['answer'].startswith('Doanh thu')
    assert run_['summary']['levels'] == {'PASS': 2, 'FAIL': 1} and run_['summary']['verified_questions'] == 2


def test_each_question_gets_its_own_chat_session(tmp_path):
    async def behave(question): return draft('x')
    engine = Engine(behave)
    run(EvaluationStore(tmp_path), engine)
    sessions = [s for _, s in engine.asked]
    assert len(set(sessions)) == 3 and all(s.startswith('eval-') for s in sessions)


def test_a_failing_or_slow_question_is_recorded_and_the_run_goes_on(tmp_path):
    async def behave(question):
        if question == 'Doanh thu?': raise RuntimeError('boom with secret details')
        if question == 'Ngày?': await asyncio.sleep(5)
        return draft('x')
    store = EvaluationStore(tmp_path)
    ident = run(store, Engine(behave), timeout=0.05)
    results = {r['qid']: r for r in store.get(ident)['results']}
    assert results['Q01']['error'] == 'RuntimeError' and results['Q01']['level'] == 'ERROR'
    assert 'secret' not in str(results['Q01'])                                # only the exception type is kept
    assert results['Q02']['status'] == 'TIMEOUT' and results['Q03']['error'] is None
    assert store.get(ident)['status'] == 'COMPLETED'


def test_only_one_run_at_a_time_and_stale_runs_do_not_block(tmp_path):
    store = EvaluationStore(tmp_path)
    first = store.create('admin', 2)
    with pytest.raises(ValueError, match='EVALUATION_ALREADY_RUNNING'):
        store.create('admin', 2)
    old = (datetime.now(timezone.utc) - timedelta(seconds=evaluation_runner.STALE_SECONDS + 5)).isoformat()
    with store.metrics.connect() as conn:
        conn.execute('UPDATE eval_runs SET updated_at=? WHERE id=?', (old, first))
    assert store.status(first) == 'INTERRUPTED' and store.active() is None
    assert store.create('admin', 1)


def test_an_interrupt_stops_the_run_between_questions(tmp_path):
    store = EvaluationStore(tmp_path)
    holder = {}

    async def behave(question):
        store.interrupt(holder['id'])                                          # the admin presses stop during Q01
        return draft('3.984 tỷ đồng')
    ident = store.create('admin', 3); holder['id'] = ident
    asyncio.run(run_evaluation(store, Engine(behave), ident, ITEMS))
    run_ = store.get(ident)
    assert run_['status'] == 'INTERRUPTED' and len(run_['results']) == 1 and run_['done'] == 1
    with pytest.raises(ValueError, match='EVALUATION_NOT_RUNNING'):
        store.interrupt(ident)
    with pytest.raises(ValueError, match='EVALUATION_NOT_FOUND'):
        store.interrupt('missing')


def test_summary_handles_empty_and_unscored_runs():
    assert summarize([])['mean_score'] is None and summarize([])['total'] == 0
    out = summarize([{'level': 'MANUAL', 'score': None, 'latency_ms': 100, 'citations': 0},
                     {'level': 'PASS', 'score': 1.0, 'latency_ms': 300, 'citations': 2, 'verified': True}])
    assert out['mean_score'] == 1.0 and out['mean_latency_ms'] == 200 and out['with_sources'] == 1


# ---- API -------------------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, 'get_settings', lambda: SimpleNamespace(admin_ingestion_directory=tmp_path))
    from src.api.routers import research_chat

    async def behave(question): return draft('3.984 tỷ đồng', status='DRAFT_READY')
    monkeypatch.setattr(research_chat, 'get_store', lambda: SimpleNamespace(engine=Engine(behave)))
    from src.documents import evaluation_set
    monkeypatch.setattr(evaluation_set, 'load_golden', lambda root=None: [dict(i) for i in ITEMS])
    app = FastAPI(); app.include_router(api.router)
    with TestClient(app) as c:
        yield c, app


def grant(app):
    app.dependency_overrides[api.access] = lambda: Principal(UUID(int=1), frozenset({'ADMINISTRATOR'}))


def test_api_requires_admin(client):
    c, _ = client
    base = '/api/v1/admin/ingestion/evaluation'
    assert c.get(base + '/questions').status_code == 401 and c.get(base + '/runs').status_code == 401
    assert c.post(base + '/runs', json={'question_ids': ['Q01']}).status_code == 401


def test_api_runs_the_chosen_questions_and_reports_them(client):
    c, app = client; grant(app)
    base = '/api/v1/admin/ingestion/evaluation'
    assert [q['id'] for q in c.get(base + '/questions').json()['items']] == ['Q01', 'Q02', 'Q03']
    assert c.post(base + '/runs', json={'question_ids': []}).status_code == 422
    assert c.post(base + '/runs', json={'question_ids': ['Q99']}).json()['detail'] == 'EVALUATION_UNKNOWN_QUESTION'
    assert c.post(base + '/runs', json={'question_ids': ['Q01'] * 41}).status_code == 422
    started = c.post(base + '/runs', json={'question_ids': ['Q01', 'Q01']})        # duplicates collapse
    assert started.status_code == 202 and started.json()['total'] == 1
    run_id = started.json()['run_id']
    detail = c.get(f'{base}/runs/{run_id}').json()                                  # the background task already ran
    assert detail['status'] == 'COMPLETED' and detail['results'][0]['level'] == 'PASS'
    assert c.get(base + '/runs').json()['items'][0]['id'] == run_id
    assert c.get(f'{base}/runs/{UUID(int=5)}').status_code == 404
    assert c.post(f'{base}/runs/{run_id}/interrupt').json()['detail'] == 'EVALUATION_NOT_RUNNING'
    assert c.post(f'{base}/runs/{UUID(int=5)}/interrupt').status_code == 404
