import asyncio
from unittest.mock import AsyncMock
import pytest
from src.retrieval_orchestration.live_research import LiveResearchService, analyze_live
from src.retrieval_orchestration.hybrid_router.decision_engine import ScopeResolver

SYMBOLS = ('BID','CMG','CTG','ELC','FPT','ICT','ITD','MBB','TCB','VCB')

@pytest.mark.parametrize('symbol', SYMBOLS)
@pytest.mark.parametrize('template', ['Thông tin công ty {}', 'Giới thiệu tổng quan về {}', 'Thông tin {}'])
def test_company_profile_is_not_personnel(symbol, template):
    question = template.format(symbol)
    resolved = ScopeResolver().resolve(question)
    assert resolved.route_hint == 'VECTOR'
    decision = analyze_live(question)
    assert decision['decision'] == 'SEARCH'
    assert decision['scope']['source_type'] == 'COMPANY_PROFILE'
    assert decision['scope']['companies'] == [symbol]

@pytest.mark.parametrize('symbol', SYMBOLS)
def test_bare_company_defaults_to_profile(symbol):
    assert ScopeResolver().resolve(symbol).route_hint == 'VECTOR'
    class StopRetriever:
        async def retrieve(self, query, scope):
            assert scope['source_type'] == 'COMPANY_PROFILE'
            assert scope['companies'] == [symbol]
            assert '_hybrid_context' not in scope
            assert 'tin tức' not in query
            return dict(items=[])
    router = type('Router', (), {'answer': AsyncMock(return_value=None)})()
    old = dict(companies=['FPT'], _hybrid_context=dict(companies=['FPT'], position_code='BOARD_CHAIR'))
    result = asyncio.run(LiveResearchService(StopRetriever(), hybrid_router=router).answer(symbol, 'test', old))
    assert result['status'] == 'NO_DATA'

def test_greeting_never_calls_retrieval_or_router():
    router = type('Router', (), {'answer': AsyncMock()})()
    result = asyncio.run(LiveResearchService(object(), hybrid_router=router).answer('chào bạn', 'test'))
    assert result['reason_code'] == 'GREETING'
    router.answer.assert_not_called()

def test_explicit_profile_and_personnel_uses_both():
    result = ScopeResolver().resolve('Giới thiệu công ty FPT và ban lãnh đạo')
    assert result.route_hint == 'BOTH'
    assert result.scope.topic == 'COMPANY_PROFILE_WITH_RELATIONSHIPS'

def test_explicit_personnel_still_uses_graph():
    assert ScopeResolver().resolve('Ai là Chủ tịch VCB?').route_hint == 'GRAPH'

@pytest.mark.parametrize('symbol', SYMBOLS)
def test_members_without_group_clarifies_before_classifier(symbol):
    from src.retrieval_orchestration.hybrid_router.decision_engine import DecisionEngine
    class NeverClassify:
        def predict(self, question):
            raise AssertionError('Ambiguous membership must not reach classifier')
    question = f'cho tôi xem thành viên của {symbol}'
    result = DecisionEngine(NeverClassify()).decide(question)
    assert result.reason_code == 'AMBIGUOUS_COMPANY_MEMBERS'
    assert result.tasks == []
    decision = analyze_live(question)
    assert decision['reason_code'] == 'AMBIGUOUS_COMPANY_MEMBERS'
    assert decision['scope']['companies'] == [symbol]
