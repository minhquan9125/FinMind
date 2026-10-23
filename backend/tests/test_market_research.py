"""Current market questions use shared feeds, not the frozen report corpus."""
import asyncio
import copy
from datetime import datetime, timedelta, timezone
import json

import pytest

from src.retrieval_orchestration.live_research import analyze_live, LiveResearchService
from src.retrieval_orchestration.market_research import MarketResearch
from src.b1_answering.evidence.citations import CitationError, prepare_evidence
from src.market_data.live import BusyError

VN = timezone(timedelta(hours=7))
NOW = datetime(2026, 10, 23, 10, 15, tzinfo=VN)


def quote(day='2026-10-23', close='82.5'):
    return {'symbol': 'FPT', 'source': 'vnstock_kbs', 'fetched_at': NOW.isoformat(),
            'live': {'last_success_at': NOW.isoformat(), 'stale': False},
            'bars': [{'date': day, 'close': close, 'source': 'vnstock_kbs', 'status': 'pending_reconciliation'}]}


def article(day='2026-10-23T02:00:00+00:00', ident='12345'):
    return {'id': ident, 'title': 'FPT công bố kết quả kinh doanh',
            'description': 'FPT công bố kết quả kinh doanh mới.', 'published_at': day,
            'url': 'https://fireant.vn/bai-viet/tin-fpt/'+ident, 'source': 'fireant'}


class Repository:
    def get_ohlcv(self, symbol, limit): return quote()
    def get_news(self, symbol, limit): return {'symbol': symbol, 'articles': []}


class Live:
    def __init__(self, payload=None): self.calls = []; self.payload = payload or quote()
    def refresh(self, symbol): self.calls.append(symbol); return copy.deepcopy(self.payload)
    def read(self, symbol, limit): return copy.deepcopy(self.payload)


class News:
    def __init__(self, articles=None, stale=False):
        self.articles = [article()] if articles is None else articles
        self.stale = stale
        self.calls = []
    def refresh(self, symbol):
        self.calls.append(symbol)
        return {'symbol': symbol, 'articles': copy.deepcopy(self.articles), 'fetched_at': NOW.isoformat(),
                'refresh': {'stale': self.stale, 'error': 'source unavailable' if self.stale else None}}
    def article(self, url):
        item = next(item for item in self.articles if item['url'] == url)
        return {'url': url, 'content': item['description']}


def scope(question):
    return analyze_live(question, today=NOW.date())['scope']


@pytest.mark.parametrize('question', [
    'giá cổ phiếu fpt hôm nay là bao nhiêu', 'FPT giá hiện tại bao nhiêu',
    'tóm tắt tin tức mới hôm nay của fpt', 'tin tức mới nhất FPT',
])
def test_current_questions_route_to_market(question):
    result = analyze_live(question, today=NOW.date())
    assert result['decision'] == 'MARKET_LOOKUP'
    assert result['scope']['companies'] == ['FPT']


def test_current_question_missing_symbol_accepts_company_followup():
    first = analyze_live('giá cổ phiếu hôm nay bao nhiêu', today=NOW.date())
    assert first['decision'] == 'ASK_CLARIFICATION'
    assert analyze_live('FPT', first['scope'], today=NOW.date())['decision'] == 'MARKET_LOOKUP'


@pytest.mark.parametrize('question', ['giá xyz hôm nay', 'xyz giá hiện tại', 'tin tức xyz mới nhất'])
def test_current_explicit_lowercase_symbol_is_not_limited_to_corpus_tickers(question):
    result = analyze_live(question, today=NOW.date())
    assert result['decision'] == 'MARKET_LOOKUP'
    assert result['scope']['companies'] == ['XYZ']


def test_live_news_does_not_silently_choose_between_publishers():
    first = analyze_live('tin tức CafeF và FireAnt mới nhất FPT', today=NOW.date())
    assert first['reason_code'] == 'AMBIGUOUS_PUBLISHER'
    second = analyze_live('FireAnt', first['scope'], today=NOW.date())
    assert second['decision'] == 'MARKET_LOOKUP'
    assert second['scope']['publisher'] == 'fireant'


def test_historical_news_stays_in_corpus_and_financial_questions_leave_market_context():
    assert analyze_live('tin tức FPT tháng 9/2026', today=NOW.date())['decision'] == 'SEARCH'
    current = scope('giá cổ phiếu FPT hôm nay')
    result = analyze_live('tổng tài sản FPT quý 2/2026', current, today=NOW.date())
    assert result['decision'] == 'SEARCH'
    assert result['scope']['source_type'] == 'BCTC'


def test_quote_uses_shared_service_and_known_kbs_scale():
    live = Live()
    bridge = MarketResearch(Repository(), services=lambda: (live, News()), now=lambda: NOW)
    result = asyncio.run(bridge.lookup(scope('giá cổ phiếu FPT hôm nay')))
    assert result['status'] == 'PRICE_READY'
    assert '82,500 VND' in result['draft']
    assert '23/10/2026' in result['draft']
    assert live.calls == ['FPT']
    assert prepare_evidence(result['evidence_pack'])


def test_old_trading_day_is_not_called_todays_price():
    bridge = MarketResearch(Repository(), services=lambda: (Live(quote('2026-10-22')), News()), now=lambda: NOW)
    result = asyncio.run(bridge.lookup(scope('giá cổ phiếu FPT hôm nay')))
    assert result['status'] == 'PRICE_READY'
    assert result['reason_code'] == 'STALE_PRICE'
    assert '22/10/2026' in result['draft']
    assert 'chưa có giá' in result['draft'].lower()


def test_unknown_historical_price_unit_is_not_guessed():
    class UnknownRepository(Repository):
        def get_ohlcv(self, *args):
            data = quote()
            data.pop('live')
            data['source'] = 'unknown'
            return data
    bridge = MarketResearch(UnknownRepository(), services=lambda: (None, None), now=lambda: NOW)
    result = asyncio.run(bridge.lookup(scope('giá cổ phiếu FPT hôm nay')))
    assert result['status'] != 'PRICE_READY'
    assert result['reason_code'] == 'PRICE_UNIT_UNVERIFIED'


def test_news_filters_by_vietnam_publication_day():
    news = News([article('2026-10-22T18:30:00+00:00', '1'), article('2026-10-22T10:00:00+00:00', '2')])
    bridge = MarketResearch(Repository(), services=lambda: (None, news), now=lambda: NOW)
    result = asyncio.run(bridge.lookup(scope('tóm tắt tin tức mới hôm nay của FPT')))
    assert result['status'] == 'EVIDENCE_READY'
    items = result['evidence_pack']['items']
    assert len(items) == 1
    assert items[0]['locator']['url'].endswith('/1')
    assert news.calls == ['FPT']
    assert prepare_evidence(result['evidence_pack'])


def test_no_news_today_does_not_substitute_older_news():
    news = News([article('2026-10-22T10:00:00+00:00')])
    bridge = MarketResearch(Repository(), services=lambda: (None, news), now=lambda: NOW)
    result = asyncio.run(bridge.lookup(scope('tin tức mới hôm nay của FPT')))
    assert result['status'] == 'NO_DATA'
    assert '2026-10-23' in result['message']
    assert 'corpus' not in result['message']
    latest = asyncio.run(bridge.lookup(scope('tin tức mới nhất FPT')))
    assert latest['status'] == 'EVIDENCE_READY'


def test_news_failure_without_cache_is_temporary_error_not_no_data():
    bridge = MarketResearch(Repository(), services=lambda: (None, News([], stale=True)), now=lambda: NOW)
    result = asyncio.run(bridge.lookup(scope('tin tức mới hôm nay của FPT')))
    assert result['status'] == 'SYSTEM_UNAVAILABLE'


def test_feed_hash_or_locator_tampering_is_rejected():
    bridge = MarketResearch(Repository(), services=lambda: (None, News()), now=lambda: NOW)
    result = asyncio.run(bridge.lookup(scope('tin mới hôm nay FPT')))
    pack = result['evidence_pack']
    pack['items'][0]['passage'] += 'CHANGED'
    with pytest.raises(CitationError): prepare_evidence(pack)


def test_busy_feed_preserves_shared_quota_and_retry_delay():
    class BusyLive(Live):
        def refresh(self, symbol): raise BusyError(17)
    result = asyncio.run(MarketResearch(Repository(), services=lambda: (BusyLive(), None), now=lambda: NOW)
                         .lookup(scope('giá FPT hôm nay')))
    assert result['reason_code'] == 'MARKET_BUSY'
    assert result['retry_after'] == 17


@pytest.mark.parametrize('timestamp', ['2026-10-24T00:00:00+07:00', '2026-10-23T01:00:00', 'invalid'])
def test_future_or_unzoned_news_is_not_todays_evidence(timestamp):
    result = asyncio.run(MarketResearch(Repository(), services=lambda: (None, News([article(timestamp)])), now=lambda: NOW)
                         .lookup(scope('tin mới hôm nay FPT')))
    assert result['status'] == 'NO_DATA'


def test_publisher_is_not_silently_replaced_and_missing_company_is_not_hom():
    assert analyze_live('giá cổ phiếu hôm nay', today=NOW.date())['reason_code'] == 'MISSING_COMPANY'
    news = News()
    result = asyncio.run(MarketResearch(Repository(), services=lambda: (None, news), now=lambda: NOW)
                         .lookup(scope('tin tức CafeF mới hôm nay của FPT')))
    assert result['reason_code'] == 'LIVE_PUBLISHER_UNAVAILABLE'
    assert news.calls == []


def test_market_period_does_not_leak_into_new_financial_question():
    context = scope('giá FPT hôm nay')
    result = analyze_live('tổng tài sản FPT', context, today=NOW.date())
    assert result['reason_code'] == 'MISSING_PERIOD'
    assert not result['scope'].get('periods')
    switched = analyze_live('còn SSI', context, today=NOW.date())
    assert switched['decision'] == 'MARKET_LOOKUP'
    assert switched['scope']['companies'] == ['SSI']
    assert analyze_live('xin chào mọi người', context, today=NOW.date())['decision'] != 'MARKET_LOOKUP'
    assert analyze_live('mới nhất', context, today=NOW.date())['scope']['_market_request']['day'] is None


@pytest.mark.parametrize('field', ['locator', 'source_sha256', 'snapshot'])
def test_snapshot_binding_rejects_partial_edits(field):
    bridge = MarketResearch(Repository(), services=lambda: (None, News()), now=lambda: NOW)
    pack = asyncio.run(bridge.lookup(scope('tin mới hôm nay FPT')))['evidence_pack']
    if field == 'locator': pack['items'][0][field]['url'] = 'https://evil.test/'
    elif field == 'snapshot': pack['items'][0][field]['title'] = 'changed'
    else: pack['items'][0][field] = '0' * 64
    with pytest.raises(CitationError): prepare_evidence(pack)


def test_quote_failure_uses_cache_with_explicit_freshness_warning():
    class FailedLive(Live):
        def refresh(self, symbol): raise RuntimeError('private details must not escape')
    result = asyncio.run(MarketResearch(Repository(), services=lambda: (FailedLive(), None), now=lambda: NOW)
                         .lookup(scope('giá FPT hôm nay')))
    assert result['status'] == 'PRICE_READY'
    assert result['freshness']['stale'] is True
    assert result['draft'] == 'Giá FPT ngày 23/10/2026: 82,500 VND.'
    assert 'private' not in str(result)


def test_router_factory_uses_configured_market_service_objects(monkeypatch):
    from src.api.routers import research_chat as api
    from src.core.config import Settings
    from src.core import db
    from src.documents import embeddings
    settings = Settings(_env_file=None, research_chat_live=True, gemini_api_key='')
    monkeypatch.setattr(api, 'get_settings', lambda: settings)
    monkeypatch.setattr(db, 'get_pool', lambda: object())
    monkeypatch.setattr(embeddings, 'get_embedding_service', lambda: object())
    live, news = Live(), News()
    api.configure_market_services(live, news)
    try:
        assert api.get_store().engine.market.services() == (live, news)
    finally:
        api.configure_market_services()


def test_news_company_can_be_supported_by_source_title_without_inventing_other_facts():
    from src.b1_answering.evidence.grounded import validate_grounded
    news_item = article()
    news_item.update(title='FPT cập nhật đăng ký doanh nghiệp', description='Doanh nghiệp cập nhật đăng ký.')
    pack = asyncio.run(MarketResearch(Repository(), services=lambda: (None, News([news_item])), now=lambda: NOW)
                       .lookup(scope('tin mới hôm nay FPT')))['evidence_pack']
    evidence = prepare_evidence(pack)
    eid = next(iter(evidence))
    payload = {'claims': [{'text': 'FPT cập nhật đăng ký doanh nghiệp.', 'evidence_ids': [eid],
                           'support_quotes': [{'evidence_id': eid, 'quote': news_item['description']}]}]}
    answer = validate_grounded(payload, evidence, {'source_type': 'NEWS'})
    assert answer['status'] == 'DRAFT_READY'
    payload['claims'][0]['text'] = 'Ngày 2026-10-23, FPT cập nhật đăng ký doanh nghiệp.'
    assert validate_grounded(payload, evidence, {'source_type': 'NEWS'})['status'] == 'DRAFT_READY'
    payload['claims'][0]['text'] = 'Ngày 2026-10-24, FPT cập nhật đăng ký doanh nghiệp.'
    with pytest.raises(CitationError): validate_grounded(payload, evidence, {'source_type': 'NEWS'})
    payload['claims'][0]['text'] = 'FPT cập nhật đăng ký doanh nghiệp 999 lần.'
    with pytest.raises(CitationError): validate_grounded(payload, evidence, {'source_type': 'NEWS'})


def test_current_news_pipeline_calls_gemini_without_corpus_search():
    class ForbiddenRetriever:
        async def retrieve(self, *args): raise AssertionError('must not query frozen corpus')
    class Provider:
        calls = 0
        async def count_tokens(self, request): return 100
        async def generate(self, request):
            self.calls += 1
            item = json.loads(request['contents'][0]['parts'][0]['text'])['evidence'][0]
            text = 'FPT công bố kết quả kinh doanh mới.'
            return {'model_version': 'fake', 'usage': {'input_tokens': 100, 'output_tokens': 40, 'total_tokens': 140},
                    'payload': {'claims': [{'text': text, 'evidence_ids': [item['evidence_id']],
                                           'support_quotes': [{'evidence_id': item['evidence_id'], 'quote': text}]}]}}
    async def run():
        provider = Provider()
        bridge = MarketResearch(Repository(), services=lambda: (Live(), News()), now=lambda: NOW)
        engine = LiveResearchService(ForbiddenRetriever(), provider=provider, market=bridge)
        # Use an explicit clock argument on the service, not the machine's timezone.
        result = await engine.answer('tóm tắt tin tức mới hôm nay của FPT', 'session', today=NOW.date())
        assert result['answering']['status'] == 'DRAFT_READY'
        assert result['evidence_pack']['schema_version'] == '1.2'
        assert provider.calls == 1
        price = await engine.answer('giá cổ phiếu FPT hôm nay', 'session', today=NOW.date())
        assert price['answering']['status'] == 'DRAFT_READY'
        assert provider.calls == 1
    asyncio.run(run())


def test_market_chat_saved_and_reopened_with_sources(tmp_path):
    from uuid import uuid4
    from src.retrieval_orchestration.web_sessions import SessionStore
    async def run():
        live = Live()
        engine = LiveResearchService(object(), market=MarketResearch(
            Repository(), services=lambda: (live, None), now=lambda: NOW))
        owner = str(uuid4())
        store = SessionStore(tmp_path, engine=engine)
        snapshot = await store.create(owner)
        sid = snapshot['session_id']
        snapshot = await store.send(owner, sid, 'giá cổ phiếu FPT hiện tại bao nhiêu', 0)
        assert '82,500 VND' in snapshot['messages'][-1]['content']
        assert live.calls == ['FPT']
        reopened = SessionStore(tmp_path, engine=engine)
        assert (await reopened.get(owner, sid))['messages'] == snapshot['messages']
        reference = await reopened.send(owner, sid, 'nguồn đâu', 1)
        assert live.calls == ['FPT']
        last = reference['messages'][-1]
        assert last['result']['answering']['manifest']['response_mode'] == 'SAVED_SOURCE_REFERENCE'
        assert 'Giá cổ phiếu FPT' in last['content']
    asyncio.run(run())
