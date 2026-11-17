"""S5-WBS09.2: explicit contextual actions in the real service/planner."""
import asyncio
import copy
from datetime import date

import pytest

from tests.test_s5_wbs091_context import live_engine
from src.retrieval_orchestration.live_research import analyze_live

TODAY = date(2026, 11, 17)


@pytest.mark.parametrize('question', [
    'Liệt kê ra giúp tôi', 'Cho tôi xem danh sách', 'liet ke lai giup minh',
    'Liệt kê những nội dung vừa nói', 'Có thể liệt kê ra không?',
])
def test_list_followup_keeps_graph_subject_company_and_period(question):
    async def run():
        engine, content, graph = live_engine()
        first = await engine.answer('Các công ty con của FPT năm 2025 là những công ty nào?', 'list', today=TODAY)
        before = copy.deepcopy(first['scope'])
        result = await engine.answer(question, 'list', first['scope'], today=TODAY)
        assert result['hybrid_router']['route'] == 'GRAPH'
        assert result['scope']['companies'] == ['FPT']
        assert result['scope']['periods'] == ['2025']
        assert result['scope']['relation_types'] == ['HAS_SUBSIDIARY']
        assert len(graph.calls) == 2
        assert not content.calls
        assert first['scope'] == before
    asyncio.run(run())


@pytest.mark.parametrize('question', ['Giới thiệu tổng quan công ty này', 'Tổng quan doanh nghiệp đang nói', 'Giới thiệu tổng quan'])
def test_overview_followup_clears_financial_slots_and_keeps_current_company(question):
    async def run():
        engine, content, graph = live_engine()
        prior = analyze_live('Lợi nhuận sau thuế VCB năm 2025')['scope']
        result = await engine.answer(question, 'overview', prior, today=TODAY)
        assert result['scope']['companies'] == ['VCB']
        assert result['scope']['source_type'] == 'COMPANY_PROFILE'
        assert not result['scope'].get('metric_code')
        assert not result['scope'].get('periods')
        assert content.calls[-1][1]['companies'] == ['VCB']
        assert not graph.calls
    asyncio.run(run())


@pytest.mark.parametrize('context', [{}, {'companies': ['VCB', 'BID']}])
def test_overview_with_missing_or_ambiguous_company_asks_before_retrieval(context):
    async def run():
        engine, content, graph = live_engine()
        result = await engine.answer('Giới thiệu tổng quan công ty này', 'overview', context, today=TODAY)
        assert result['status'] == 'ASK_CLARIFICATION'
        assert not content.calls and not graph.calls
    asyncio.run(run())


def test_explicit_new_company_wins_over_current_company():
    async def run():
        engine, content, _ = live_engine()
        result = await engine.answer('Giới thiệu tổng quan BID', 'overview', {'companies': ['VCB']}, today=TODAY)
        assert result['scope']['companies'] == ['BID']
        assert content.calls[-1][1]['companies'] == ['BID']
    asyncio.run(run())


def test_list_without_subject_does_not_invent_one_or_search():
    async def run():
        engine, content, graph = live_engine()
        result = await engine.answer('Liệt kê ra giúp tôi', 'new', {}, today=TODAY)
        assert result['status'] == 'ASK_CLARIFICATION'
        assert not content.calls and not graph.calls
    asyncio.run(run())


def test_list_news_uses_news_list_not_old_article_detail():
    prior = dict(companies=['VCB'], source_type='NEWS', periods=['2026-11-17'],
                 _market_request={'kind': 'NEWS', 'action': 'DETAIL', 'day': '2026-11-17'},
                 _article_urls=['https://fireant.vn/bai-viet/old'])
    result = analyze_live('Liệt kê ra giúp tôi', prior, today=TODAY)
    assert result['decision'] == 'MARKET_LOOKUP'
    assert result['scope']['_market_request']['action'] == 'LIST'
    assert '_article_urls' not in result['scope']


def test_explicit_list_subject_does_not_reuse_previous_graph_filter():
    async def run():
        engine, _, graph = live_engine()
        first = await engine.answer('Ai là chủ tịch FPT năm 2025?', 'list')
        result = await engine.answer('Liệt kê công ty con của VCB năm 2024', 'list', first['scope'])
        assert result['scope']['companies'] == ['VCB']
        assert result['scope']['periods'] == ['2024']
        assert result['scope']['relation_types'] == ['HAS_SUBSIDIARY']
        assert graph.calls[-1]['position_code'] is None
    asyncio.run(run())


def test_message_api_lists_then_overviews_current_company(tmp_path):
    from uuid import uuid4
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from src.api.routers import research_chat as api
    from src.retrieval_orchestration.web_sessions import SessionStore

    engine, content, graph = live_engine()
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[api.get_owner] = lambda: str(owner)
    owner = uuid4()
    app.dependency_overrides[api.get_store] = lambda: SessionStore(tmp_path, engine=engine)
    with TestClient(app) as client:
        snap = client.post('/api/research/chat/sessions').json()
        path = '/api/research/chat/sessions/' + snap['session_id']
        for question in ('Các công ty con của FPT năm 2025?', 'Liệt kê ra giúp tôi', 'Giới thiệu tổng quan công ty này'):
            response = client.post(path+'/messages', json={'text': question, 'revision': snap['revision']})
            assert response.status_code == 200, response.text
            snap = response.json()
        assert len(graph.calls) == 2
        assert content.calls[-1][1]['source_type'] == 'COMPANY_PROFILE'
        assert content.calls[-1][1]['companies'] == ['FPT']
        assert client.get(path).json() == snap


def test_list_annual_content_keeps_the_prior_subject_in_retrieval():
    async def run():
        engine, content, _ = live_engine()
        first = await engine.answer('BCTN FPT năm 2025 nói gì về chiến lược?', 'annual-list')
        result = await engine.answer('Liệt kê những nội dung vừa nói', 'annual-list', first['scope'])
        assert result['scope']['source_type'] == 'BCTN'
        assert result['scope']['companies'] == ['FPT']
        assert result['scope']['periods'] == ['2025']
        assert 'chiến lược' in content.calls[-1][0]
    asyncio.run(run())


def test_news_listing_leaves_the_previous_article_query_but_keeps_date_and_publisher():
    prior = dict(companies=['FPT'], source_type='NEWS', publisher='fireant',
                 _market_request={'kind': 'NEWS', 'action': 'DETAIL', 'day': TODAY.isoformat(),
                                  'query': 'bài FPT ký hợp đồng về AI'},
                 _article_urls=['https://fireant.vn/bai-viet/old'])
    before = copy.deepcopy(prior)
    result = analyze_live('Cho tôi xem danh sách', prior, today=TODAY)
    request = result['scope']['_market_request']
    assert request == {'kind': 'NEWS', 'action': 'LIST', 'day': TODAY.isoformat()}
    assert result['scope']['publisher'] == 'fireant'
    assert result['scope']['companies'] == ['FPT']
    assert '_article_urls' not in result['scope']
    assert prior == before
    # Exercise the actual feed adapter: clearing only action/URLs would still
    # let the old title query narrow the list to one article.
    from src.retrieval_orchestration.market_research import MarketResearch
    from tests.test_market_research import News, Repository, article
    articles = [dict(article(ident='123'), title='FPT ký hợp đồng về AI',
                     published_at=TODAY.isoformat()),
                dict(article(ident='456'), title='FPT công bố cổ tức',
                     published_at=TODAY.isoformat())]
    market = MarketResearch(Repository(), services=lambda: (None, News(articles)))
    listed = asyncio.run(market.lookup(result['scope']))
    assert listed['status'] == 'EVIDENCE_READY'
    assert len(listed['evidence_pack']['items']) == 2
