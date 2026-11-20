import pytest
from src.retrieval_orchestration.live_research import analyze_live, content_fallback_scope


@pytest.mark.parametrize('symbol', ['VCB','BID','CTG','MBB','TCB','FPT','CMG','ELC','ITD','ICT'])
@pytest.mark.parametrize('topic', ['nhân sự hiện tại', 'ban lãnh đạo', 'ban điều hành'])
def test_relationship_question_reaches_router_before_generic_content(symbol, topic):
    question=f'cho tôi biết {topic} của {symbol}'
    assert content_fallback_scope(question, analyze_live(question)) is None


@pytest.mark.parametrize('symbol', ['VCB','BID','CTG','MBB','TCB','FPT','CMG','ELC','ITD','ICT'])
def test_named_report_keeps_its_year_and_source(symbol):
    question=f'Mới tìm hiểu {symbol}, công ty này kiếm tiền từ những mảng nào theo báo cáo 2025?'
    decision=analyze_live(question)
    assert decision['scope']['source_type']=='BCTN'
    assert decision['scope']['periods']==['2025']
    assert content_fallback_scope(question,decision) is None
