"""User regressions: compact prices, temporal followups, listings and articles."""
import asyncio
import copy
import json
import pytest

from src.retrieval_orchestration.live_research import analyze_live, LiveResearchService
from src.retrieval_orchestration.market_research import MarketResearch
from tests.test_market_research import NOW, Repository, Live, News, article, scope


class DetailedNews(News):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.details = []
    def article(self, url):
        self.details.append(url)
        return {'url': url, 'content': 'FPT triển khai công viên công nghệ tại Hà Nội. Dự án có trung tâm nghiên cứu mới.'}


class Provider:
    calls = 0
    def __init__(self): self.requests = []
    async def count_tokens(self, request): return 200
    async def generate(self, request):
        self.calls += 1
        body = json.loads(request['contents'][0]['parts'][0]['text'])
        self.requests.append(body)
        item = body['evidence'][0]
        text = 'FPT triển khai công viên công nghệ tại Hà Nội.'
        return {'model_version': 'fake', 'usage': {'input_tokens': 200, 'output_tokens': 60, 'total_tokens': 260},
                'payload': {'claims': [{'text': text, 'evidence_ids': [item['evidence_id']],
                                       'support_quotes': [{'evidence_id': item['evidence_id'], 'quote': text}]}]}}


def engine(news=None, provider=None):
    bridge = MarketResearch(Repository(), services=lambda: (Live(), news or DetailedNews()), now=lambda: NOW)
    return LiveResearchService(object(), provider=provider, market=bridge)


def test_price_has_only_symbol_amount_and_calendar_date():
    result = asyncio.run(engine().answer('giá FPT hôm nay là bao nhiêu', 'test', today=NOW.date()))
    draft = result['answering']['draft']
    assert draft == 'Giá FPT ngày 23/10/2026: 82,500 VND.'
    assert '[1]' not in draft
    assert result['presentation']['sources'] == 'HIDDEN'


def test_yesterday_followup_keeps_price_and_company():
    first = analyze_live('giá FPT hôm nay', today=NOW.date())
    second = analyze_live('còn hôm qua', first['scope'], today=NOW.date())
    assert second['decision'] == 'MARKET_LOOKUP'
    assert second['scope']['companies'] == ['FPT']
    assert second['scope']['_market_request']['day'] == '2026-10-22'
    assert second['scope']['source_type'] == 'PRICE'


@pytest.mark.parametrize(('question', 'day'), [
    ('còn hôm kia', '2026-10-21'), ('hôm kia thì sao', '2026-10-21'),
    ('hôm 22/10/2026', '2026-10-22'), ('còn hôm 21/10/2026', '2026-10-21'),
    ('ngày 20/10/2026 thì sao', '2026-10-20'), ('còn 2026-10-19', '2026-10-19'),
    ('giá FPT hôm 1/10/2026', '2026-10-01'),
])
def test_calendar_price_questions_keep_symbol_and_exact_date(question, day):
    first = analyze_live('giá FPT hôm nay', today=NOW.date())
    result = analyze_live(question, first['scope'], today=NOW.date())
    assert result['decision'] == 'MARKET_LOOKUP'
    assert result['scope']['companies'] == ['FPT']
    assert result['scope']['_market_request']['day'] == day


def test_invalid_price_day_asks_for_valid_date_without_fetching_today():
    previous = scope('giá FPT hôm nay')
    result = analyze_live('còn hôm 31/02/2026', previous, today=NOW.date())
    assert result['decision'] == 'ASK_CLARIFICATION'
    assert result['reason_code'] == 'INVALID_DATE'
    corrected = analyze_live('22/10/2026', result['scope'], today=NOW.date())
    assert corrected['decision'] == 'MARKET_LOOKUP'
    assert corrected['scope']['_market_request']['day'] == '2026-10-22'


def test_historical_quote_selects_exact_day_and_declared_unit():
    class HistoryLive(Live):
        def stock_history(self, symbol):
            return {'source': 'vnstock_kbs', 'fetched_at': NOW.isoformat(), 'bars': [
                {'date': '2026-10-22', 'close': '81.3', 'source': 'vnstock_kbs', 'price_unit': 'thousand_vnd'}]}
        def refresh(self, symbol): raise AssertionError('historical question must not request current quote')
    bridge = MarketResearch(Repository(), services=lambda: (HistoryLive(), None), now=lambda: NOW)
    request = analyze_live('còn hôm qua', scope('giá FPT hôm nay'), today=NOW.date())['scope']
    result = asyncio.run(bridge.lookup(request))
    assert result['status'] == 'PRICE_READY'
    assert result['draft'] == 'Giá đóng cửa FPT ngày 22/10/2026: 81,300 VND.'


def test_news_question_lists_headlines_without_gemini():
    async def run():
        provider = Provider()
        news = DetailedNews()
        result = await engine(news, provider).answer('tin tức FPT hôm nay có gì mới', 'test', today=NOW.date())
        assert result['answering']['status'] == 'DRAFT_READY'
        assert result['answering']['manifest']['response_mode'] == 'NEWS_LIST'
        assert article()['title'] in result['answering']['draft']
        assert result['presentation']['sources'] == 'LINKS'
        assert provider.calls == 0
        assert news.details == []
    asyncio.run(run())


def test_explicit_summary_fetches_article_content_and_keeps_only_used_links():
    async def run():
        provider, news = Provider(), DetailedNews([article(ident='1'), article(ident='2')])
        result = await engine(news, provider).answer('tóm tắt tin tức FPT hôm nay', 'test', today=NOW.date())
        assert result['answering']['status'] == 'DRAFT_READY'
        assert 'trung tâm nghiên cứu mới' in provider.requests[0]['evidence'][0]['passage']
        assert len(news.details) == 2
        assert len(result['answering']['citations']) == 1
        assert result['presentation']['sources'] == 'USED_LINKS'
    asyncio.run(run())


def test_article_title_followup_resolves_list_and_fetches_only_that_article():
    async def run():
        news, provider = DetailedNews(), Provider()
        service = engine(news, provider)
        first = await service.answer('tin tức FPT hôm nay có gì mới', 'test', today=NOW.date())
        result = await service.answer('cho tôi biết chi tiết về: '+article()['title'], 'test', first['scope'],
                                      previous_result=first, today=NOW.date())
        assert result['answering']['status'] == 'DRAFT_READY'
        assert result['scope']['_market_request']['action'] == 'DETAIL'
        assert news.calls == ['FPT']  # no second feed scan
        assert news.details == [article()['url']]
        assert provider.calls == 1
    asyncio.run(run())


def test_title_followup_also_resolves_previously_failed_news_draft():
    async def run():
        service = engine(provider=Provider())
        first = await service.answer('tin tức FPT hôm nay', 'test', today=NOW.date())
        first['answering']['status'] = 'INSUFFICIENT_EVIDENCE'
        result = await service.answer('chi tiết bài: '+article()['title'], 'test', first['scope'],
                                      previous_result=first, today=NOW.date())
        assert result['answering']['status'] == 'DRAFT_READY'
    asyncio.run(run())
