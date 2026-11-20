"""Acceptance regressions for Nhân's S5-WBS09.1 conversation scope."""
import copy
import asyncio
import os
from datetime import date

import pytest

from src.retrieval_orchestration.live_research import analyze_live

TODAY = date(2026, 11, 16)


def financial():
    return analyze_live('Lợi nhuận sau thuế BID năm 2025 hợp nhất', today=TODAY)['scope']


@pytest.mark.parametrize('question', [
    'Cho mình quay lại mã ACB, giữ chỉ tiêu và kỳ vừa hỏi nhé.',
    'Đổi sang ACB, giữ nguyên chỉ tiêu và kỳ trước.',
])
def test_keep_metric_reference_is_not_a_request_to_choose_another_metric(question):
    result = analyze_live(question, financial(), today=TODAY)
    assert result['decision'] == 'SEARCH'
    assert result['scope']['companies'] == ['ACB']
    assert result['scope']['metric_code'] == 'PROFIT_AFTER_TAX'
    assert result['scope']['periods'] == ['2025']
    assert result['scope']['reporting_entity'] == 'CONSOLIDATED'


@pytest.mark.parametrize('question', ['Còn quý 2 thì sao?', 'Thế còn quý hai cùng năm thì sao nhỉ?'])
def test_quarter_followup_uses_unique_conversation_year(question):
    result = analyze_live(question, financial(), today=TODAY)
    assert result['decision'] == 'SEARCH'
    assert result['scope']['periods'] == ['2025-Q2']
    assert result['scope']['measure_basis'] == 'STANDALONE_QUARTER'


def test_annual_company_followup_keeps_question_and_year_with_new_company():
    prior = analyze_live('BCTN FPT năm 2024 nói gì về chiến lược?', today=TODAY)['scope']
    result = analyze_live('Còn VCB thì sao?', prior, today=TODAY)
    assert result['scope']['companies'] == ['VCB']
    assert result['scope']['periods'] == ['2024']
    assert 'chiến lược' in result['scope']['_annual_question']
    assert 'FPT' not in result['scope']['_annual_question'].upper()


@pytest.mark.parametrize('question, source, metric', [
    ('Lợi nhuận sau thuế FPT năm 2025', 'BCTC', 'PROFIT_AFTER_TAX'),
    ('Tin FPT mới nhất', 'NEWS', None),
])
def test_explicit_new_topic_leaves_annual_report(question, source, metric):
    prior = analyze_live('BCTN FPT năm 2024 nói gì về chiến lược?', today=TODAY)['scope']
    result = analyze_live(question, prior, today=TODAY)
    assert result['scope']['source_type'] == source
    assert result['scope'].get('metric_code') == metric
    assert '_annual_question' not in result['scope']
    assert result['scope'].get('topic') != 'ANNUAL_REPORT_TOPIC'


def test_switch_from_news_to_financial_does_not_keep_news_topic_or_publisher():
    prior = dict(companies=['FPT'], periods=['2026-09'], source_type='NEWS',
                 topic='RELATIONSHIP_LOOKUP', publisher='cafef', metric_code=None,
                 _hybrid_context={'companies': ['FPT'], 'position_code': 'CEO', 'route_hint': 'GRAPH'})
    result = analyze_live('Doanh thu thuần VCB năm 2024', prior, today=TODAY)
    assert result['scope']['source_type'] == 'BCTC'
    assert result['scope']['metric_code'] == 'NET_REVENUE'
    assert result['scope']['periods'] == ['2024']
    assert not result['scope'].get('topic')
    assert 'publisher' not in result['scope']
    assert '_hybrid_context' not in result['scope']


def test_input_context_remains_unchanged():
    prior = financial()
    before = copy.deepcopy(prior)
    analyze_live('Còn VCB quý 2/2024 thì sao?', prior, today=TODAY)
    assert prior == before


def test_explicit_company_period_metric_override_old_slots():
    result = analyze_live('Doanh thu thuần VCB quý 2/2024 riêng lẻ', financial(), today=TODAY)
    assert result['scope']['companies'] == ['VCB']
    assert result['scope']['periods'] == ['2024-Q2']
    assert result['scope']['metric_code'] == 'NET_REVENUE'
    assert result['scope']['reporting_entity'] == 'PARENT'


def test_new_conversation_requires_its_own_metric():
    reset = analyze_live('/new', financial(), today=TODAY)
    assert reset['scope'] == {}
    result = analyze_live('Còn VCB thì sao?', reset['scope'], today=TODAY)
    assert result['decision'] == 'ASK_CLARIFICATION'
    assert not result['scope'].get('metric_code')


def test_quarter_without_prior_year_asks_instead_of_guessing():
    result = analyze_live('Lợi nhuận sau thuế BID quý 2', today=TODAY)
    assert result['reason_code'] == 'MISSING_YEAR'


def test_multiple_prior_years_do_not_choose_arbitrarily():
    prior = {**financial(), 'periods': ['2024', '2025']}
    result = analyze_live('Còn quý 2 thì sao?', prior, today=TODAY)
    assert result['decision'] == 'ASK_CLARIFICATION'
    assert result['reason_code'] == 'MISSING_YEAR'


@pytest.mark.parametrize('question', [
    'Tóm tắt kế hoạch doanh thu', 'Đánh giá chiến lược mở rộng',
])
def test_annual_content_followup_keeps_report_even_when_it_mentions_a_metric(question):
    prior = analyze_live('BCTN FPT năm 2024 nói gì về chiến lược?', today=TODAY)['scope']
    result = analyze_live(question, prior, today=TODAY)
    assert result['scope']['source_type'] == 'BCTN'
    assert result['scope']['periods'] == ['2024']


def test_news_month_is_not_a_financial_reporting_period():
    prior = analyze_live('Tin tức FPT tháng 9/2026', today=TODAY)['scope']
    result = analyze_live('Doanh thu thuần', prior, today=TODAY)
    assert result['scope']['source_type'] == 'BCTC'
    assert result['scope']['periods'] == ['LATEST_AVAILABLE_PERIOD']


def test_annual_company_name_alias_is_replaced_in_retrieval_question():
    prior = analyze_live('BCTN của Hòa Phát năm 2024 nói gì về chiến lược?', today=TODAY)['scope']
    result = analyze_live('Còn VCB thì sao?', prior, today=TODAY)
    assert 'Hòa Phát' not in result['scope']['_annual_question']
    assert 'VCB' in result['scope']['_annual_question']


@pytest.mark.parametrize('question, company, year', [
    ('Còn VCB năm 2023 thì sao?', 'VCB', '2023'),
    ('Còn Vinamilk thì sao?', 'VNM', '2024'),
    ('Còn năm 2023 thì sao?', 'FPT', '2023'),
])
def test_annual_followup_replaces_only_explicit_slots(question, company, year):
    prior = analyze_live('BCTN FPT năm 2024 nói gì về chiến lược?', today=TODAY)['scope']
    result = analyze_live(question, prior, today=TODAY)
    assert result['scope']['companies'] == [company]
    assert result['scope']['periods'] == [year]
    assert 'chiến lược' in result['scope']['_annual_question']
    assert year in result['scope']['_annual_question']
    if company != 'FPT':
        assert 'FPT' not in result['scope']['_annual_question'].upper()


def test_annual_correction_after_comparison_asks_which_company_to_replace():
    prior = analyze_live('So sánh chiến lược FPT và VCB theo BCTN năm 2024', today=TODAY)['scope']
    result = analyze_live('Còn BID thì sao?', prior, today=TODAY)
    assert result['decision'] == 'ASK_CLARIFICATION'
    assert result['reason_code'] == 'AMBIGUOUS_CONTEXT'


def test_explicit_new_metric_is_not_hidden_by_keep_wording():
    result = analyze_live('Giữ chỉ tiêu ROE của VCB năm 2024', financial(), today=TODAY)
    assert result['decision'] == 'SEARCH'
    assert result['scope']['metric_code'] == 'ROE'
    assert result['scope']['companies'] == ['VCB']
    assert result['scope']['periods'] == ['2024']


def test_ambiguous_new_profit_topic_does_not_stay_in_annual_report():
    prior = analyze_live('BCTN FPT năm 2024 nói gì về chiến lược?', today=TODAY)['scope']
    result = analyze_live('Lợi nhuận FPT năm 2025 là bao nhiêu?', prior, today=TODAY)
    assert result['decision'] == 'ASK_CLARIFICATION'
    assert result['scope']['source_type'] == 'BCTC'
    assert result['scope']['_pending_metric'] == 'PROFIT'


def test_negative_keep_request_does_not_silently_reuse_old_metric():
    result = analyze_live('Không giữ chỉ tiêu cũ, còn VCB thì sao?', financial(), today=TODAY)
    assert result['decision'] == 'ASK_CLARIFICATION'
    assert not result['scope'].get('metric_code')


class EmptyContent:
    """Record the query/scope; deliberately provide no financial evidence."""
    def __init__(self):
        self.calls = []

    async def retrieve(self, query, scope):
        self.calls.append((query, copy.deepcopy(scope)))
        return {'items': []}


class UnavailableGraph:
    def __init__(self):
        self.calls = []

    async def retrieve(self, scope):
        from src.retrieval_orchestration.web_chat_router import GraphChatError
        self.calls.append(scope.model_dump())
        raise GraphChatError('GRAPH_NOT_READY')


def live_engine():
    from src.retrieval_orchestration.hybrid_router.decision_engine import DecisionEngine
    from src.retrieval_orchestration.live_research import LiveResearchService
    from src.retrieval_orchestration.web_chat_router import WebChatRouter

    class Predictor:
        model_version = 'isolated-context-test'

        def predict(self, text):
            return (0.01, 0.99)

    content, graph = EmptyContent(), UnavailableGraph()
    engine = LiveResearchService(content, hybrid_router=WebChatRouter(
        lambda: DecisionEngine(Predictor()), graph, content))
    return engine, content, graph


def test_live_service_graph_then_financial_then_followup_clears_graph_filters():
    async def run():
        engine, content, graph = live_engine()
        first = await engine.answer('Chủ tịch HĐQT FPT năm 2024 là ai?', 'scope-test', today=TODAY)
        assert first['hybrid_router']['route'] == 'GRAPH'
        second = await engine.answer('Doanh thu thuần VCB năm 2025', 'scope-test', first['scope'], today=TODAY)
        assert second['scope']['source_type'] == 'BCTC'
        assert '_hybrid_context' not in second['scope']
        assert not second['scope'].get('position_code')
        assert not second['scope'].get('relation_types')
        third = await engine.answer('Còn BID thì sao?', 'scope-test', second['scope'], today=TODAY)
        assert third['scope']['companies'] == ['BID']
        assert third['scope']['metric_code'] == 'NET_REVENUE'
        assert third['scope']['periods'] == ['2025']
        assert len(graph.calls) == 1
        assert len(content.calls) == 2
    asyncio.run(run())


def test_live_service_annual_followup_retrieval_contains_new_company_and_old_subject():
    async def run():
        engine, content, _ = live_engine()
        first = await engine.answer('BCTN FPT năm 2024 nói gì về chiến lược?', 'scope-test', today=TODAY)
        second = await engine.answer('Còn VCB thì sao?', 'scope-test', first['scope'], today=TODAY)
        assert second['scope']['periods'] == ['2024']
        query, scope = content.calls[-1]
        assert scope['companies'] == ['VCB']
        assert 'FPT' not in query.upper()
        assert 'chiến lược' in query
    asyncio.run(run())


@pytest.mark.parametrize('storage', ['file', 'postgres_contract'])
def test_message_api_restart_resume_reset_and_owner_isolation(tmp_path, storage):
    from uuid import uuid4
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from src.api.routers import research_chat as api
    from src.retrieval_orchestration.web_sessions import SessionStore

    engine, content, _ = live_engine()
    owner = str(uuid4())
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[api.get_owner] = lambda: owner
    if storage == 'file':
        app.dependency_overrides[api.get_store] = lambda: SessionStore(tmp_path, engine=engine)
    else:
        from tests.test_postgres_chat_store import Repository
        from src.retrieval_orchestration.postgres_sessions import PostgresSessionStore
        repository = Repository()  # Storage boundary only; no real database claims.
        app.dependency_overrides[api.get_store] = lambda: PostgresSessionStore(repository=repository, engine=engine)
    with TestClient(app) as client:
        original = client.post('/api/research/chat/sessions').json()
        path = '/api/research/chat/sessions/' + original['session_id']

        def send(path, snap, text):
            response = client.post(path + '/messages', json={'text': text, 'revision': snap['revision']})
            assert response.status_code == 200, response.text
            return response.json()

        original = send(path, original, 'Lợi nhuận sau thuế BID năm 2025')
        original = send(path, original, 'Còn VCB thì sao?')
        assert original['messages'][-1]['result']['scope']['metric_code'] == 'PROFIT_AFTER_TAX'
        # Every API request creates a fresh store instance: scope must be persisted.
        assert client.get(path).json() == original
        resumed = client.post(path + '/resume').json()
        child_path = '/api/research/chat/sessions/' + resumed['session_id']
        resumed = send(child_path, resumed, 'Thế còn quý hai cùng năm thì sao nhỉ?')
        assert resumed['messages'][-1]['result']['scope']['periods'] == ['2025-Q2']
        assert client.get(path).json() == original
        resumed = send(child_path, resumed, 'Doanh thu thuần ACB năm 2024')
        assert resumed['messages'][-1]['result']['scope']['metric_code'] == 'NET_REVENUE'
        fresh = client.post('/api/research/chat/sessions').json()
        fresh = send('/api/research/chat/sessions/' + fresh['session_id'], fresh, 'Còn VCB thì sao?')
        scope = fresh['messages'][-1]['result']['scope']
        assert not scope.get('metric_code')
        assert scope.get('periods') != ['2024']
        resumed = send(child_path, resumed, '/new')
        assert resumed['messages'][-1]['result']['scope'] == {}
        resumed = send(child_path, resumed, 'Còn BID thì sao?')
        assert not resumed['messages'][-1]['result']['scope'].get('metric_code')
        app.dependency_overrides[api.get_owner] = lambda: str(uuid4())
        assert client.get(path).status_code == 404
        assert content.calls


@pytest.mark.skipif(os.getenv('RUN_S5_WBS091_DB_SMOKE') != '1', reason='opt-in rollback-only PostgreSQL scope check')
def test_real_postgres_scope_persistence_and_cleanup():
    """Actual SQL/RLS/store; savepoints inside a rollback-only outer transaction.

    Isolation-level/concurrency behavior is not measured by this scope check.
    """
    from contextlib import asynccontextmanager
    from uuid import UUID, uuid4
    import asyncpg
    from src.auth import repository as auth_repository
    from src.core.config import get_settings
    from src.retrieval_orchestration.chat_types import ChatError
    from src.retrieval_orchestration.postgres_sessions import PostgresSessionStore

    class SavepointConnection:
        def __init__(self, connection):
            self.connection = connection

        def __getattr__(self, name):
            return getattr(self.connection, name)

        def transaction(self, **options):
            # Repository requests both read-committed and repeatable-read.
            # asyncpg forbids mixing isolation levels inside one outer test
            # transaction; use savepoints to retain guaranteed rollback.
            return self.connection.transaction()

    class TransactionPool:
        def __init__(self, connection):
            self.connection = connection

        @asynccontextmanager
        async def acquire(self):
            yield SavepointConnection(self.connection)

    async def run():
        connection = await asyncpg.connect(get_settings().database_url, timeout=10, command_timeout=15)
        transaction = connection.transaction()
        await transaction.start()
        owner, sids = None, []
        try:
            await connection.execute("SET LOCAL statement_timeout = '15s'")
            pool = TransactionPool(connection)
            account = await auth_repository.create_user(pool, f's5wbs091-{uuid4().hex}@example.com',
                                                       'Rollback-only context test', 'disabled-synthetic-login')
            owner = str(account['user_id'])
            engine, _, _ = live_engine()
            store = PostgresSessionStore(pool, engine=engine)
            first = await store.create(owner)
            sid = first['session_id']
            sids.append(sid)
            await store.send(owner, sid, 'Lợi nhuận sau thuế BID năm 2025', 0)
            saved = await store.send(owner, sid, 'Còn VCB thì sao?', 1)
            reopened = PostgresSessionStore(pool, engine=engine)
            assert await reopened.get(owner, sid) == saved
            child = await reopened.resume(owner, sid)
            sids.append(child['session_id'])
            child = await reopened.send(owner, child['session_id'], 'Còn quý 2 thì sao?', 0)
            assert child['messages'][-1]['result']['scope']['periods'] == ['2025-Q2']
            assert await store.get(owner, sid) == saved
            fresh = await store.create(owner)
            sids.append(fresh['session_id'])
            fresh = await store.send(owner, fresh['session_id'], 'Còn BID thì sao?', 0)
            assert not fresh['messages'][-1]['result']['scope'].get('metric_code')
            with pytest.raises(ChatError) as error:
                await store.get(str(uuid4()), sid)
            assert error.value.status == 404
        finally:
            try:
                await transaction.rollback()
                if owner is not None:
                    assert await connection.fetchval('SELECT count(*) FROM public.users WHERE user_id=$1',
                                                     account['user_id']) == 0
                # Read under the same role/identity after rollback: none of the test chats remain.
                if sids:
                    async with connection.transaction():
                        await connection.execute('SET LOCAL ROLE finmind_chat_runtime')
                        await connection.fetchval("SELECT set_config('app.chat_user_id', $1, true)", owner)
                        assert await connection.fetchval(
                            'SELECT count(*) FROM research_chat.conversations WHERE conversation_id=ANY($1::uuid[])',
                            [UUID(sid) for sid in sids]) == 0
            finally:
                await connection.close()
    asyncio.run(run())
