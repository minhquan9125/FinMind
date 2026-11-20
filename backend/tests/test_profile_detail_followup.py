from datetime import date
import pytest
from src.retrieval_orchestration.conversation_actions import profile_detail_question
from src.retrieval_orchestration.live_research import analyze_live


@pytest.mark.parametrize('symbol', ['VCB','BID','CTG','MBB','TCB','FPT','CMG','ELC','ITD','ICT'])
@pytest.mark.parametrize('text', ['chi tiết hơn đi', 'cụ thể hơn', 'nói chi tiết hơn về công ty đó nhé'])
def test_profile_detail_searches_report_instead_of_repeating_profile(symbol, text):
    question = profile_detail_question(text, {'companies':[symbol], 'source_type':'COMPANY_PROFILE'})
    assert question and symbol in question
    decision = analyze_live(question, {'companies':[symbol]}, today=date(2026,11,18))
    assert decision['decision'] == 'SEARCH'
    assert decision['scope']['source_type'] == 'BCTN'
    assert decision['scope']['companies'] == [symbol]
    assert decision['scope']['periods'] == ['LATEST_AVAILABLE_PERIOD']


@pytest.mark.parametrize('context', [None, {'companies':['FPT','VCB'],'source_type':'COMPANY_PROFILE'},
    {'companies':['FPT'],'source_type':'NEWS'}, {'companies':['VCB'],'source_type':'BCTN'}])
def test_unrelated_or_ambiguous_topics_are_not_rewritten(context):
    assert profile_detail_question('chi tiết hơn đi',context) is None


def test_explicit_new_subject_is_not_replaced_with_previous_company():
    assert profile_detail_question('chi tiết doanh thu VCB năm 2025',
        {'companies':['FPT'],'source_type':'COMPANY_PROFILE'}) is None


def test_live_turn_passes_report_question_and_clean_context_to_router():
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from src.retrieval_orchestration.live_research import LiveResearchService
    router = SimpleNamespace(answer=AsyncMock(return_value={'status':'NO_DATA'}))
    service = LiveResearchService(object(), hybrid_router=router)
    context = {'companies':['VCB'], 'source_type':'COMPANY_PROFILE', 'periods':['2024'],
               '_person_graph_name':'old person'}
    result = asyncio.run(service.answer('chi tiết hơn đi', 'session', context))
    assert result['status'] == 'NO_DATA'
    question, scope = router.answer.call_args.args
    assert 'BCTN' in question and 'VCB' in question
    assert scope == {'companies':['VCB']}
    assert context['source_type'] == 'COMPANY_PROFILE'  # no mutation of saved context
