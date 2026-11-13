"""The web chat answer must use and persist the selected route evidence."""

import asyncio
from uuid import uuid4

from src.retrieval_orchestration.chat_logic import append_turn, new_document
from src.retrieval_orchestration.live_research import LiveResearchService
from tests.test_routed_answer import execution, replay
from src.retrieval_orchestration.routed_answer import compose_routed_answer


def test_both_chat_turn_and_saved_source_followup_use_same_citations():
    calls = []

    async def runner(question):
        calls.append(question)
        return compose_routed_answer(execution('BOTH'), replay, corpus_version_id='corpus-frozen')

    class Retriever:
        async def retrieve(self, *_):
            raise AssertionError('B1 retrieval must not replace BOTH evidence')

    async def check():
        engine = LiveResearchService(Retriever(), route_runner=runner)
        doc = new_document(str(uuid4()), str(uuid4()))
        doc['metadata']['execution_mode'] = 'LIVE'
        first = await append_turn(doc, 'Công ty con FPT năm 2025?', engine)
        answer = first['messages'][-1]['result']
        assert answer['route'] == 'BOTH'
        assert '[1]' in first['messages'][-1]['content']
        assert len(answer['answering']['citations']) == 2
        second = await append_turn(first, 'nguồn của câu trả lời trước', engine)
        followup = second['messages'][-1]['result']
        assert followup['answering']['manifest']['response_mode'] == 'SAVED_SOURCE_REFERENCE'
        assert followup['answering']['citations'] == answer['answering']['citations']
        assert len(calls) == 1

    asyncio.run(check())


def test_both_runner_precedes_existing_graph_chat_and_graph_still_uses_it():
    calls = []

    async def runner(question):
        calls.append('both-runner')
        if 'pe' in question.lower():
            return compose_routed_answer(execution('BOTH'), replay, corpus_version_id='corpus-frozen')
        return None

    class ExistingGraphChat:
        async def answer(self, *_args, **_kwargs):
            calls.append('graph-chat')
            return {'route': 'GRAPH', 'status': 'EVIDENCE_READY', 'scope': {}, 'message': 'Graph source'}

    async def check():
        service = LiveResearchService(object(), route_runner=runner, hybrid_router=ExistingGraphChat())
        both = await service.answer('TCB thuộc ngành nào và PE năm 2025?', str(uuid4()))
        assert both['route'] == 'BOTH'
        assert calls == ['both-runner']
        calls.clear()
        graph = await service.answer('TCB có công ty con nào năm 2025?', str(uuid4()))
        assert graph['route'] == 'GRAPH'
        assert calls == ['both-runner', 'graph-chat']

    asyncio.run(check())


def test_live_router_result_reaches_persistable_answer(monkeypatch):
    from src.api.routers import hybrid_router as api
    from src.core import db
    from src.retrieval_orchestration import routed_answer
    from types import SimpleNamespace

    class Decision:
        def decide(self, _):
            return SimpleNamespace(decision='SEARCH', route='BOTH')

    class Engine:
        def run(self, _):
            return execution('BOTH')

    async def source(_, item, corpus_id):
        assert corpus_id == 'corpus-frozen'
        return replay(item)

    monkeypatch.setattr(api, 'get_settings', lambda: SimpleNamespace(
        hybrid_router_mode='live', research_corpus_version_id='corpus-frozen'))
    monkeypatch.setattr(api, 'get_router_engine', lambda: Decision())
    monkeypatch.setattr(api, '_get_live_engine', lambda loop: Engine())
    monkeypatch.setattr(db, 'get_pool', lambda: object())
    monkeypatch.setattr(routed_answer, 'replay_pinned_source', source)
    answer = asyncio.run(api.run_routed_chat_answer('Công ty con FPT năm 2025?'))
    assert answer['route'] == 'BOTH'
    assert answer['answering']['status'] == 'DRAFT_READY'
    assert len(answer['evidence_pack']['items']) == 2


def test_vector_route_keeps_existing_b1_chat(monkeypatch):
    from src.api.routers import hybrid_router as api
    from types import SimpleNamespace

    class Decision:
        def decide(self, _):
            return SimpleNamespace(decision='SEARCH', route='VECTOR')

    monkeypatch.setattr(api, 'get_settings', lambda: SimpleNamespace(hybrid_router_mode='live'))
    monkeypatch.setattr(api, 'get_router_engine', lambda: Decision())
    monkeypatch.setattr(api, '_get_live_engine', lambda loop: (_ for _ in ()).throw(
        AssertionError('VECTOR must not load GRAPH adapter')))
    assert asyncio.run(api.run_routed_chat_answer('Doanh thu FPT năm 2025?')) is None


def test_route_change_never_presents_a_different_branch_as_the_answer(monkeypatch):
    from src.api.routers import hybrid_router as api
    from types import SimpleNamespace

    class Decision:
        def decide(self, _):
            return SimpleNamespace(decision='SEARCH', route='BOTH')

    class Engine:
        def run(self, _):
            return execution('VECTOR')

    monkeypatch.setattr(api, 'get_settings', lambda: SimpleNamespace(
        hybrid_router_mode='live', research_corpus_version_id='corpus-frozen'))
    monkeypatch.setattr(api, 'get_router_engine', lambda: Decision())
    monkeypatch.setattr(api, '_get_live_engine', lambda loop: Engine())
    answer = asyncio.run(api.run_routed_chat_answer('TCB với FPT năm 2025?'))
    assert answer['status'] == 'INSUFFICIENT_EVIDENCE'
    assert answer['reason_code'] == 'ROUTE_CHANGED'


def test_natural_source_followup_without_cua_is_recognized():
    from src.retrieval_orchestration.live_research import analyze_live
    assert analyze_live('nguồn câu trả lời trước')['decision'] == 'RESOLVE_REFERENCE'


def test_graph_route_takes_priority_over_generic_news_intent():
    calls = []

    async def runner(_):
        calls.append('router')
        return compose_routed_answer(execution('GRAPH'), replay, corpus_version_id='corpus-frozen')

    class News:
        async def answer(self, *_args, **_kwargs):
            calls.append('news')
            return {'status': 'NO_DATA', 'scope': {}, 'message': 'News route'}

    async def check():
        engine = LiveResearchService(object(), route_runner=runner, admin_news=News())
        answer = await engine.answer('Tin bổ nhiệm Chủ tịch FPT năm 2025?', str(uuid4()))
        assert answer['route'] == 'GRAPH'
        assert calls == ['router']

    asyncio.run(check())
