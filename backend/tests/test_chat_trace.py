"""Each chat turn is recorded in queries / query_companies / answers (throwaway test DB 127.0.0.1:15434)."""
import asyncio
import logging
from uuid import uuid4

import pytest

from src.retrieval_orchestration.chat_trace import record_turn
from src.retrieval_orchestration.postgres_sessions import PostgresSessionStore
from tests.financial_db_fixture import create_financial_db, drop_financial_db
from tests.test_postgres_chat_store import Engine, Repository

RESULT = {
    'request_id': 'req-1', 'status': 'EVIDENCE_READY', 'scope': {'source_type': 'MARKET_ANALYSIS', 'companies': ['FPT', 'ZZZ']},
    'answering': {'status': 'INSUFFICIENT_EVIDENCE', 'reason_code': 'PARTIAL_CLAIMS', 'draft': 'FPT giảm. [1]',
                  'manifest': {'model_returned': 'gemini-3.5-flash-lite', 'prompt_version': 'b1-grounded-v1'}},
}


@pytest.fixture
def db():
    loop = asyncio.new_event_loop()
    admin, conn, name = loop.run_until_complete(create_financial_db())
    user = uuid4()
    loop.run_until_complete(conn.execute(
        "INSERT INTO users(user_id,email,username,password_hash,is_active) VALUES($1,'t@test.local','t','x',true)", user))
    loop.run_until_complete(conn.execute(
        "INSERT INTO companies(company_id,symbol,company_name,is_active) VALUES($1,'FPT','FPT',true)", uuid4()))
    yield (lambda coro: loop.run_until_complete(coro)), conn, str(user)
    loop.run_until_complete(drop_financial_db(admin, conn, name))
    loop.close()


def test_turn_writes_query_companies_and_answer(db):
    run, conn, user = db
    query_id = run(record_turn(conn, user_id=user, question='phân tích fpt', result=RESULT, latency_ms=1234))
    assert query_id
    query = run(conn.fetchrow('SELECT question_text, question_type, trace_id, language FROM queries WHERE query_id=$1', query_id))
    assert dict(query) == {'question_text': 'phân tích fpt', 'question_type': 'MARKET_ANALYSIS', 'trace_id': 'req-1', 'language': 'vi'}
    companies = run(conn.fetch('SELECT c.symbol FROM query_companies q JOIN companies c USING (company_id) WHERE q.query_id=$1', query_id))
    assert [r['symbol'] for r in companies] == ['FPT']                  # ZZZ is not a known company
    answer = run(conn.fetchrow('SELECT status, reason_code, answer_text, model_name, latency_ms FROM answers WHERE query_id=$1', query_id))
    assert dict(answer) == {'status': 'INSUFFICIENT_EVIDENCE', 'reason_code': 'PARTIAL_CLAIMS', 'answer_text': 'FPT giảm. [1]',
                            'model_name': 'gemini-3.5-flash-lite', 'latency_ms': 1234}


def test_unknown_reason_code_is_registered_once(db):
    run, conn, user = db
    run(record_turn(conn, user_id=user, question='a', result=RESULT, latency_ms=1))
    run(record_turn(conn, user_id=user, question='b', result=RESULT, latency_ms=1))
    assert run(conn.fetchval("SELECT count(*) FROM reason_codes WHERE code='PARTIAL_CLAIMS'")) == 1


def test_trace_failure_never_breaks_chat(caplog):
    class BrokenPool:
        def acquire(self): raise OSError('db down')

    async def run():
        store = PostgresSessionStore(BrokenPool(), repository=Repository(), engine=Engine())
        owner = str(uuid4())
        sid = (await store.create(owner))['session_id']
        return await store.send(owner, sid, 'giá fpt', 0)

    with caplog.at_level(logging.WARNING):
        snapshot = asyncio.run(run())
    assert snapshot['messages'][-1]['content'] == 'Bạn muốn xem ngày nào?'
    assert 'chat_trace_failed' in caplog.text
