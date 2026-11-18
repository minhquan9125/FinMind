import asyncio
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import pytest
from src.retrieval_orchestration.context_policy import question_context
from src.retrieval_orchestration.live_research import analyze_live, LiveResearchService
from src.retrieval_orchestration.market_dialogue import matching_articles

TODAY = date(2026,11,18)
OLD = dict(companies=['FPT'],source_type='BCTN',periods=['2025'],
    _annual_question='FPT chiến lược 2025', _hybrid_context={'person_name':'old'},
    _article_urls=['https://example.org/old'], _pending_metric='PROFIT')


@pytest.mark.parametrize('symbol', ['VCB','BID','CTG','MBB','TCB','FPT','CMG','ELC','ITD','ICT'])
def test_article_question_drops_old_report_filters_for_all_companies(symbol):
    question=f'{symbol} có thông báo thay đổi nhân sự gì trong bài đăng ngày 04/11/2026?'
    value=analyze_live(question,OLD,today=TODAY)
    assert value['decision']=='MARKET_LOOKUP'
    scope=value['scope']
    assert scope['source_type']=='NEWS' and scope['companies']==[symbol]
    assert scope['_market_request']['action']=='DETAIL'
    assert scope['_market_request']['day']=='2026-11-04'
    assert '_annual_question' not in scope and '_hybrid_context' not in scope
    assert scope['periods']==['2026-11-04']
    assert OLD['companies']==['FPT']


@pytest.mark.parametrize('question',[
    'MBB có thông báo thay đổi nhân sự gì trong bài đăng ngày 04/11/2026?',
    'ITD bổ nhiệm ai làm Giám đốc Tài chính theo thông báo ngày 24/08/2026?',
    'Chi nhánh Phú Quốc của MBB thay đổi địa điểm như thế nào?'])
def test_article_content_uses_stored_news_without_neo4j(question):
    router=SimpleNamespace(answer=AsyncMock(side_effect=AssertionError('Must not query graph')))
    service=LiveResearchService(object(),hybrid_router=router)
    stored=AsyncMock(return_value={'items':[]})
    with patch('src.retrieval_orchestration.stored_news.latest_news',stored):
        result=asyncio.run(service.answer(question,'test',OLD,today=TODAY))
    assert result['reason_code']=='NO_STORED_NEWS'
    assert stored.call_args.args[1]['source_type']=='NEWS'
    router.answer.assert_not_called()


def test_headline_search_ignores_question_filler_and_publication_date():
    items=[{'title':'MBB: Thông báo thay đổi nhân sự'}]
    result=analyze_live('MBB có thông báo thay đổi nhân sự gì trong bài đăng ngày 04/11/2026?',OLD,today=TODAY)
    assert matching_articles(result['scope']['_market_request']['query'],items)==items
    relocation=[{'title':'Ngân hàng MBB thông báo thay đổi địa điểm Chi nhánh Phú Quốc'}]
    assert matching_articles('Chi nhánh Phú Quốc của MBB thay đổi địa điểm như thế nào?',relocation)==relocation
    appointment=[{'title':'ITD: Nghị quyết HĐQT về việc bổ nhiệm Giám đốc Tài chính'}]
    value=analyze_live('ITD bổ nhiệm ai làm Giám đốc Tài chính theo thông báo ngày 24/08/2026?',OLD,today=TODAY)
    assert value['scope']['source_type']=='NEWS'
    assert value['scope']['_market_request']['day']=='2026-08-24'
    assert matching_articles(value['scope']['_market_request']['query'],appointment)==appointment


@pytest.mark.parametrize('question',[
    'Người được ITD bổ nhiệm theo thông báo ngày 24/08/2026',
    'Chức vụ được nhắc trong nghị quyết ITD ngày 24/08/2026',
    'Thời điểm hiệu lực theo quyết định ITD ngày 24/08/2026'])
def test_explicit_announcement_source_does_not_depend_on_question_word_list(question):
    value=analyze_live(question,OLD,today=TODAY)
    assert value['scope']['source_type']=='NEWS'
    assert value['scope']['_market_request']['action']=='DETAIL'


@pytest.mark.parametrize('text', ['còn VCB','năm 2024','chi tiết hơn đi','ai là phó chủ tịch'])
def test_short_followups_keep_context(text):
    assert question_context(text,OLD,TODAY)==OLD


@pytest.mark.parametrize(('question','source'),[
    ('Tin tức MBB mới nhất','NEWS'),('Doanh thu VCB năm 2024','BCTC'),
    ('Theo BCTN BID năm 2025, chiến lược là gì?','BCTN')])
def test_explicit_new_questions_replace_prior_topic(question,source):
    decision=analyze_live(question,OLD,today=TODAY)
    assert decision['scope']['source_type']==source
    assert '_article_urls' not in decision['scope']
    assert '_hybrid_context' not in decision['scope']
