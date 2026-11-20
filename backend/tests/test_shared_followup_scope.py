import copy
from datetime import date
import pytest
from src.retrieval_orchestration.context_policy import question_context
from src.retrieval_orchestration.live_research import analyze_live
from src.retrieval_orchestration.hybrid_router.decision_engine import DecisionEngine,SessionScope
from tests.test_web_chat_router import Predictor

TODAY=date(2026,11,20)
SYMBOLS=['VCB','BID','CTG','MBB','TCB','FPT','CMG','ELC','ITD','ICT']


@pytest.mark.parametrize('symbol',SYMBOLS)
@pytest.mark.parametrize('first,expected',[
    ('Giá FPT hôm nay','PRICE'),
    ('Tin tức FPT mới nhất','NEWS'),
    ('Tổng tài sản FPT quý 2/2026','BCTC'),
    ('Theo BCTN FPT năm 2025, chiến lược kinh doanh là gì?','BCTN'),
    ('Phân tích FPT','MARKET_ANALYSIS'),
])
def test_company_only_followup_keeps_the_last_subject_across_sources(symbol,first,expected):
    previous=analyze_live(first,today=TODAY)['scope']
    before=copy.deepcopy(previous)
    text=f'thế còn {symbol} sao'
    context=question_context(text,previous,TODAY)
    result=analyze_live(text,context,today=TODAY)
    assert result['scope']['companies']==[symbol]
    assert result['scope']['source_type']==expected
    assert result['decision'] in ('SEARCH','MARKET_LOOKUP')
    assert previous==before


@pytest.mark.parametrize('symbol',SYMBOLS)
def test_chairman_followup_keeps_role_not_price(symbol):
    engine=DecisionEngine(Predictor())
    first=engine.decide('Ai là Chủ tịch FPT năm 2025?')
    values={k:getattr(first.scope,k) for k in SessionScope.__dataclass_fields__ if hasattr(first.scope,k)}
    values.update(confirmed=True,route_hint=first.route)
    second=engine.decide(f'thế còn {symbol} sao',context=SessionScope(**values))
    assert second.scope.companies==[symbol]
    assert second.scope.position_code==first.scope.position_code
    assert second.scope.periods==first.scope.periods
    assert second.route=='GRAPH'


@pytest.mark.parametrize('first,text,expected',[
    ('Giá FPT hôm nay','thế còn VCB mà chủ tịch thì sao','NEWS'),
    ('Theo BCTN FPT năm 2025, ai là chủ tịch?','còn VCB tổng tài sản quý 2/2026','BCTC'),
    ('Tổng tài sản FPT quý 2/2026','còn VCB tin tức mới nhất','NEWS'),
    ('Tin tức FPT mới nhất','còn VCB giá cổ phiếu hôm nay','PRICE'),
])
def test_explicit_new_subject_overrides_old_subject(first,text,expected):
    old=analyze_live(first,today=TODAY)['scope']
    context=question_context(text,old,TODAY)
    result=analyze_live(text,context,today=TODAY)
    assert result['scope']['companies']==['VCB']
    assert result['scope']['source_type']==expected
    if expected!='PRICE':assert result['scope'].get('metric_code')!='LAST_PRICE'


def test_switching_news_company_does_not_keep_the_previous_article_url():
    previous={'companies':['FPT'],'source_type':'NEWS','_article_urls':['https://example.org/fpt'],
        '_article_anchor':{'secret':'old'},'_market_request':{'kind':'NEWS','day':None,'action':'DETAIL'}}
    result=question_context('thế còn VCB sao',previous,TODAY)
    assert '_article_urls' not in result
    assert '_article_anchor' not in result
    assert previous['_article_urls']


@pytest.mark.parametrize('text',[
    'thế còn Ngân hàng Vietcombank sao',
    'còn Vietcombank thì sao',
    'đổi sang VCB',
])
def test_company_switch_rewrites_only_the_company_in_the_last_user_question(text):
    from src.retrieval_orchestration.conversation_actions import company_switch_question
    previous={'companies':['FPT'],'_last_question':'Ai là Chủ tịch FPT năm 2025?'}
    rewritten=company_switch_question(text,previous)
    assert rewritten=='Ai là Chủ tịch VCB năm 2025?'


def test_explicit_chairman_after_price_reaches_the_graph_with_the_new_company():
    import asyncio
    from tests.test_web_chat_router import service
    engine,graph,_=service()
    previous=analyze_live('Giá FPT hôm nay',today=TODAY)['scope']
    previous['_last_question']='Giá FPT hôm nay'
    out=asyncio.run(engine.answer('thế còn VCB mà chủ tịch thì sao','test',previous,today=TODAY))
    assert graph.calls
    assert graph.calls[0]['companies']==['VCB']
    assert graph.calls[0]['position_code']
    assert not any('2026-11-20'==p for p in graph.calls[0]['periods'])
    assert out['hybrid_router']['route']=='GRAPH'


def test_company_followup_after_two_companies_asks_which_comparison_to_continue():
    import asyncio
    from src.retrieval_orchestration.live_research import LiveResearchService
    previous={'companies':['FPT','VCB'],'source_type':'BCTC','metric_code':'TOTAL_ASSETS','periods':['2025']}
    result=asyncio.run(LiveResearchService(object()).answer('thế còn BID sao','test',previous,today=TODAY))
    assert result['reason_code']=='AMBIGUOUS_CONTEXT'
    assert previous['companies']==['FPT','VCB']


def test_company_only_followup_after_multiple_companies_asks_instead_of_guessing():
    import asyncio
    from src.retrieval_orchestration.live_research import LiveResearchService
    previous={'companies':['FPT','MBB'],'source_type':'BCTC','metric_code':'TOTAL_ASSETS',
        'periods':['2025'],'_last_question':'So sánh tổng tài sản FPT và MBB năm 2025'}
    out=asyncio.run(LiveResearchService(object()).answer('thế còn VCB sao','test',previous,today=TODAY))
    assert out['reason_code']=='AMBIGUOUS_CONTEXT'
    assert out['status']=='ASK_CLARIFICATION'
