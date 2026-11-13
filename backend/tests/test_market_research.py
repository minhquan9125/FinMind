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
    def get_news(self, symbol, limit):
        if symbol is None:
            return {'symbol': None, 'articles': [
                {**article(), 'marker': 'check', 'category': 'market'},
                article(ident='12346'),
            ]}
        return {'symbol': symbol, 'articles': []}


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


def test_company_profile_is_searchable_without_financial_metric_or_period():
    decision = analyze_live('Cong ty FPT hoat dong trong linh vuc gi?', today=NOW.date())
    assert decision['decision'] == 'SEARCH'
    assert decision['scope']['companies'] == ['FPT']
    assert decision['scope']['source_type'] == 'COMPANY_PROFILE'
    assert decision['scope']['topic'] == 'COMPANY_PROFILE'
    assert decision['scope'].get('periods') in (None, [])


def test_generic_comparison_defaults_to_company_overview():
    decision = analyze_live('So sanh tong quan FPT va CMG', today=NOW.date())
    assert decision['decision'] == 'SEARCH'
    assert decision['scope']['companies'] == ['FPT', 'CMG']
    assert decision['scope']['source_type'] == 'COMPANY_OVERVIEW'
    assert decision['scope']['topic'] == 'OVERALL_COMPARISON'
    assert decision['scope']['periods'] == ['2026']


def test_named_person_event_impact_searches_news_without_inventing_a_ticker():
    decision = analyze_live(
        'Pham Hoang Nam bi bat co anh huong den co phieu khong?', today=NOW.date()
    )
    assert decision['decision'] == 'SEARCH'
    assert decision['scope']['topic'] == 'EVENT_IMPACT'
    assert decision['scope']['companies'] == []
    assert decision['scope']['periods'] == ['LATEST_AVAILABLE_PERIOD']


def test_leadership_and_shareholder_without_period_use_latest_available_sources():
    for question in ('Ai la chu tich FPT?', 'Ai la co dong lon cua FPT?'):
        decision = analyze_live(question, today=NOW.date())
        assert decision['decision'] == 'SEARCH'
        assert decision['scope']['topic'] == 'RELATIONSHIP_LOOKUP'
        assert decision['scope']['periods'] == ['LATEST_AVAILABLE_PERIOD']


@pytest.mark.parametrize('question', [
    'cho tôi biết tất cả hội đồng của FPT', 'thành viên hội đồng quản trị FPT',
    'danh sách HĐQT FPT', 'danh sách HDQT FPT', 'ban điều hành FPT gồm những ai',
    'danh sách ban kiểm soát FPT',
])
def test_organizational_question_leaves_old_financial_clarification(question):
    old = analyze_live('FPT', today=NOW.date())['scope']
    old.update(periods=['2025'], _pending_quarter=2, _pending_reporting_entity=True)
    result = analyze_live(question, old, today=NOW.date())
    assert result['decision'] == 'SEARCH'
    assert result['scope']['companies'] == ['FPT']
    assert result['scope']['topic'] == 'RELATIONSHIP_LOOKUP'
    assert result['scope']['source_type'] == 'NEWS'
    assert result['scope']['metric_code'] is None
    assert result['scope']['periods'] == ['LATEST_AVAILABLE_PERIOD']
    assert not result['scope'].get('_pending_metric')
    assert not result.get('clarification_options')


def test_unspecified_members_asks_for_people_group_then_accepts_numeric_choice():
    old = analyze_live('FPT', today=NOW.date())['scope']
    first = analyze_live('cho tôi bik tất cả thành viên của FPT', old, today=NOW.date())
    assert first['reason_code'] == 'AMBIGUOUS_COMPANY_MEMBERS'
    assert [o['reply'] for o in first['clarification_options']] == ['Thành viên hội đồng quản trị', 'Ban điều hành']
    for choice in ('1', '2'):
        selected = analyze_live(choice, first['scope'], today=NOW.date())
        assert selected['decision'] == 'SEARCH'
        assert selected['scope']['topic'] == 'RELATIONSHIP_LOOKUP'
        assert selected['scope']['companies'] == ['FPT']


@pytest.mark.parametrize('question', [
    'giá cổ phiếu fpt hôm nay là bao nhiêu', 'FPT giá hiện tại bao nhiêu',
    'tóm tắt tin tức mới hôm nay của fpt', 'tin tức mới nhất FPT',
])
def test_current_questions_route_to_market(question):
    result = analyze_live(question, today=NOW.date())
    assert result['decision'] == 'MARKET_LOOKUP'
    assert result['scope']['companies'] == ['FPT']


@pytest.mark.parametrize('question', [
    'Hom nay thi truong co bien dong gi?',
    'TTCK hom nay co gi moi?',
    'Chung khoan hom nay co gi hot?',
    'Thi truong hom nay co do lua hay rung lac khong?',
    'tt hn co bien gi?',
    'ck nay co drama gi?',
])
def test_daily_market_digest_does_not_require_company(question):
    decision = analyze_live(question, today=NOW.date())
    assert decision['decision'] == 'MARKET_LOOKUP'
    assert decision['scope']['companies'] == []
    assert decision['scope']['topic'] == 'MARKET_DAILY_DIGEST'
    assert decision['scope']['_market_request']['market_wide'] is True
    result = asyncio.run(MarketResearch(
        Repository(), services=lambda: (Live(), News()), now=lambda: NOW
    ).lookup(decision['scope']))
    assert result['reason_code'] == 'MARKET_DAILY_DIGEST_READY'
    assert len(result['evidence_pack']['items']) == 2


def test_causal_price_question_collects_price_and_news_for_grounded_analysis():
    question = 'Vì sao hôm nay giá cổ phiếu FPT giảm?'
    decision = analyze_live(question, today=NOW.date())
    assert decision['decision'] == 'MARKET_LOOKUP'
    assert decision['scope']['source_type'] == 'MARKET_ANALYSIS'
    assert decision['scope']['_market_request']['action'] == 'ANALYSIS'
    bridge = MarketResearch(
        Repository(), services=lambda: (Live(), News()), now=lambda: NOW
    )
    result = asyncio.run(bridge.lookup(decision['scope']))
    assert result['status'] == 'EVIDENCE_READY'
    kinds = {item['snapshot']['kind'] for item in result['evidence_pack']['items']}
    assert kinds == {'PRICE', 'NEWS'}
    assert 'nhân quả' in result['message']


def test_person_statement_and_plan_question_searches_documents_not_financial_metric():
    question = (
        'Ai đang là chủ tịch của FPT vậy, trong năm 2025 ông ấy có chia sẻ gì '
        'về kế hoạch làm AI của công ty không?'
    )
    decision = analyze_live(question, today=NOW.date())
    assert decision['decision'] == 'SEARCH'
    assert decision['scope']['companies'] == ['FPT']
    assert decision['scope']['periods'] == ['2025']
    assert decision['scope']['source_type'] == 'NEWS'
    assert decision['scope']['metric_code'] is None


def test_short_msn_price_chat_routes_to_current_market_quote():
    decision = analyze_live('giá msn hn là bn', today=NOW.date())
    assert decision['decision'] == 'MARKET_LOOKUP'
    assert decision['scope']['companies'] == ['MSN']
    assert decision['scope']['source_type'] == 'PRICE'
    assert decision['scope']['metric_code'] == 'LAST_PRICE'


@pytest.mark.parametrize('question,start,end,quarter', [
    ('giá FPT tháng này', '2026-10-01', '2026-10-23', '2026-Q4'),
    ('giá FPT tháng trước', '2026-09-01', '2026-09-30', '2026-Q3'),
    ('giá FPT tuần này', '2026-10-19', '2026-10-23', '2026-Q4'),
    ('giá FPT tuần trước', '2026-10-12', '2026-10-18', '2026-Q4'),
])
def test_relative_market_ranges_are_fixed_to_vietnam_calendar(
    question, start, end, quarter
):
    decision = analyze_live(question, today=NOW.date())
    request = decision['scope']['_market_request']
    assert decision['decision'] == 'MARKET_LOOKUP'
    assert request['action'] == 'RANGE'
    assert request['start_day'] == start
    assert request['end_day'] == end
    assert request['quarter'] == quarter


def test_month_price_range_returns_verified_first_last_session_summary():
    class RangeLive(Live):
        def stock_history(self, symbol):
            return {
                'symbol': symbol, 'source': 'vnstock_kbs', 'fetched_at': NOW.isoformat(),
                'bars': [
                    {'date': '2026-10-01', 'close': '80', 'source': 'vnstock_kbs',
                     'price_unit': 'thousand_vnd'},
                    {'date': '2026-10-23', 'close': '84', 'source': 'vnstock_kbs',
                     'price_unit': 'thousand_vnd'},
                ],
            }
    decision = analyze_live('giá FPT tháng này', today=NOW.date())
    result = asyncio.run(MarketResearch(
        Repository(), services=lambda: (RangeLive(), None), now=lambda: NOW
    ).lookup(decision['scope']))
    assert result['reason_code'] == 'PRICE_RANGE_READY'
    assert '2026-Q4' in result['draft']
    assert '+5.00%' in result['draft']
    assert len(result['evidence_pack']['items']) == 2


@pytest.mark.parametrize('question,period', [
    ('tổng tài sản FPT tháng này', '2026-Q4'),
    ('tổng tài sản FPT tuần này', '2026-Q4'),
    ('tổng tài sản FPT tháng trước', '2026-Q3'),
    ('tổng tài sản FPT tuần trước', '2026-Q4'),
])
def test_relative_month_and_week_map_to_containing_reporting_quarter(question, period):
    decision = analyze_live(question, today=NOW.date())
    assert decision['decision'] == 'SEARCH'
    assert decision['scope']['periods'] == [period]


def test_shareholder_question_searches_documents_instead_of_asking_financial_metric():
    decision = analyze_live('Ai là cổ đông lớn của FPT năm 2025?', today=NOW.date())
    assert decision['decision'] == 'SEARCH'
    assert decision['scope']['source_type'] == 'NEWS'
    assert decision['scope']['companies'] == ['FPT']
    assert decision['scope']['periods'] == ['2025']


@pytest.mark.parametrize('question', [
    'Tình hình FPT dạo này có khởi sắc không?',
    'FPT gần đây có triển vọng thế nào?',
])
def test_recent_company_outlook_uses_multisource_market_analysis(question):
    decision = analyze_live(question, today=NOW.date())
    assert decision['decision'] == 'MARKET_LOOKUP'
    assert decision['scope']['source_type'] == 'MARKET_ANALYSIS'
    assert decision['scope']['companies'] == ['FPT']
    assert decision['scope']['_market_request']['action'] == 'ANALYSIS'


def test_current_question_missing_symbol_accepts_company_followup():
    first = analyze_live('giá cổ phiếu hôm nay bao nhiêu', today=NOW.date())
    assert first['decision'] == 'ASK_CLARIFICATION'
    assert analyze_live('FPT', first['scope'], today=NOW.date())['decision'] == 'MARKET_LOOKUP'


@pytest.mark.parametrize('question', [
    'hôm nay giá như nào', 'hom nay gia nhu nao', 'HOM NAY GIA NHU NAO',
    'giá như thế nào hôm nay', 'giá mới nhất hôm nay', 'cho tôi xem giá hôm nay',
    'hôm nay giá ra sao',
])
def test_price_followup_never_treats_conversational_words_as_tickers(question):
    previous = scope('giá FPT hôm nay')
    result = analyze_live(question, previous, today=NOW.date())
    assert result['decision'] == 'MARKET_LOOKUP'
    assert result['scope']['companies'] == ['FPT']
    assert result['scope']['periods'] == [NOW.date().isoformat()]
    assert result['scope']['source_type'] == 'PRICE'


@pytest.mark.parametrize('previous', [None, {'companies': ['NHU'], 'source_type': 'PRICE',
    '_market_request': {'kind': 'QUOTE', 'day': None, 'action': 'LIST'}}])
def test_no_confirmed_company_asks_instead_of_fetching_a_phantom_symbol(previous):
    first = analyze_live('hôm nay giá như nào', previous, today=NOW.date())
    assert first['reason_code'] == 'MISSING_COMPANY'
    assert first['scope'].get('companies') in (None, [])
    next_turn = analyze_live('FPT', first['scope'], today=NOW.date())
    assert next_turn['decision'] == 'MARKET_LOOKUP'
    assert next_turn['scope']['companies'] == ['FPT']


def test_real_catalog_ticker_is_kept_when_its_letters_overlap_language():
    from src.retrieval_orchestration.input_normalization import registered_symbols
    assert 'CEO' in registered_symbols()
    result = analyze_live('giá CEO hôm nay', today=NOW.date())
    assert result['decision'] == 'MARKET_LOOKUP'
    assert result['scope']['companies'] == ['CEO']


@pytest.mark.parametrize('question', ['giá xyz hôm nay', 'xyz giá hiện tại', 'tin tức xyz mới nhất'])
def test_current_explicit_lowercase_symbol_is_not_limited_to_corpus_tickers(question):
    result = analyze_live(question, today=NOW.date())
    assert result['decision'] == 'MARKET_LOOKUP'
    assert result['scope']['companies'] == ['XYZ']


@pytest.mark.parametrize('word', ['bik', 'bít', 'biết'])
def test_conversational_know_is_not_mistaken_for_an_extra_ticker(word):
    previous = analyze_live('FPT', today=NOW.date())['scope']
    result = analyze_live(f'cho tôi {word} giá hôm nay FPT là bao nhiêu', previous, today=NOW.date())
    assert result['decision'] == 'MARKET_LOOKUP'
    assert result['scope']['companies'] == ['FPT']
    assert result['scope']['source_type'] == 'PRICE'
    assert result['scope']['periods'] == [NOW.date().isoformat()]
    assert not result.get('clarification_options')


def test_multiple_market_tickers_offer_real_choices_and_keep_date_when_selected():
    first = analyze_live('giá FPT và CMG hôm nay', today=NOW.date())
    assert first['reason_code'] == 'SCOPE_TOO_LARGE'
    assert [o['reply'] for o in first['clarification_options']] == ['FPT', 'CMG']
    selected = analyze_live('2', first['scope'], today=NOW.date())
    assert selected['decision'] == 'MARKET_LOOKUP'
    assert selected['scope']['companies'] == ['CMG']
    assert selected['scope']['periods'] == [NOW.date().isoformat()]


@pytest.mark.parametrize('question', ['giá BIK hôm nay', 'giá bik hôm nay', 'cho tôi mã BIK giá hôm nay'])
def test_explicit_symbol_is_not_rewritten_as_conversational_verb(question):
    result = analyze_live(question, today=NOW.date())
    assert result['decision'] == 'MARKET_LOOKUP'
    assert result['scope']['companies'] == ['BIK']


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
    assert result['reason_code'] == 'LATEST_PERIOD_DEFAULTED'
    assert result['scope']['periods'] == ['LATEST_AVAILABLE_PERIOD']
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


def _saved_only_payload(unit):
    data = quote()
    data.pop('live')  # no valid live overlay: the source fetch failed, only the saved file remains
    if unit:
        data['bars'][0]['price_unit'] = unit
    return data


def test_failed_live_fetch_reports_saved_price_when_the_bar_declares_its_unit():
    class FailedLive(Live):
        def refresh(self, symbol): raise RuntimeError('source down')
    live = FailedLive(_saved_only_payload('thousand_vnd'))
    result = asyncio.run(MarketResearch(Repository(), services=lambda: (live, None), now=lambda: NOW)
                         .lookup(scope('giá FPT hôm nay')))
    assert result['status'] == 'PRICE_READY'
    assert result['freshness']['stale'] is True
    assert result['draft'] == 'Giá FPT ngày 23/10/2026: 82,500 VND.'


def test_failed_live_fetch_still_refuses_to_guess_an_undeclared_unit():
    class FailedLive(Live):
        def refresh(self, symbol): raise RuntimeError('source down')
    live = FailedLive(_saved_only_payload(None))
    result = asyncio.run(MarketResearch(Repository(), services=lambda: (live, None), now=lambda: NOW)
                         .lookup(scope('giá FPT hôm nay')))
    assert result['status'] != 'PRICE_READY'
    assert result['reason_code'] == 'PRICE_UNIT_UNVERIFIED'


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


def price_trend():
    from datetime import date
    from decimal import Decimal
    from src.market_data.trend import analyze_trend
    rows, day, value = [], date(2025, 1, 2), Decimal(100)
    while len(rows) < 260:
        if day.weekday() < 5:
            close = value.quantize(Decimal('.0001'))
            rows.append({'trade_date': day, 'open': close, 'high': close * Decimal('1.01'), 'low': close * Decimal('0.99'),
                         'close': close, 'volume': 1000, 'price_scale': 1000, 'is_adjusted': False,
                         'source_name': 'ENTRADE', 'source_id': 's1', 'approval_status': 'PENDING'})
            value *= Decimal('1.003')
        day += timedelta(days=1)
    return analyze_trend(rows, [], exchange='HOSE', rsi14=Decimal('61.5'))


def trend_snapshot(**changes):
    trend = price_trend()
    return {'kind': 'PRICE_TREND', 'provider': 'finmind_db', 'symbol': 'FPT', 'observed_at': NOW.isoformat(),
            'as_of': trend['as_of'], 'trend': trend, **changes}


def test_feed_item_accepts_price_trend():
    from src.b1_answering.evidence.market_contract import feed_item
    item = feed_item(trend_snapshot())
    assert item['source_type'] == 'PRICE_TREND'
    assert 'Ngắn hạn: Tăng' in item['passage'] and 'không phải khuyến nghị' in item['passage']
    assert item['locator']['trading_day'] == item['snapshot']['as_of']
    for broken in (trend_snapshot(as_of='11/11/2026'), {k: v for k, v in trend_snapshot().items() if k != 'as_of'},
                   trend_snapshot(trend={'horizons': {}})):
        with pytest.raises(CitationError):
            feed_item(broken)


def analysis_scope():
    decision = analyze_live('Xu hướng giá FPT dạo này thế nào?', today=NOW.date())
    assert decision['scope']['source_type'] == 'MARKET_ANALYSIS'
    return decision['scope']


def test_analysis_includes_trend_evidence_first():
    async def reader(symbol):
        assert symbol == 'FPT'
        return price_trend()
    bridge = MarketResearch(Repository(), services=lambda: (Live(), News()), now=lambda: NOW, trend_reader=reader)
    result = asyncio.run(bridge.lookup(analysis_scope()))
    assert result['status'] == 'EVIDENCE_READY'
    items = result['evidence_pack']['items']
    assert items[0]['source_type'] == 'PRICE_TREND'
    assert {item['snapshot']['kind'] for item in items} == {'PRICE_TREND', 'PRICE', 'NEWS'}


def test_analysis_staleness_is_about_news_not_price_age():
    # The chat appends 'lần lấy tin mới vừa thất bại' on stale; an old price snapshot is not that.
    later = NOW + timedelta(minutes=5)
    bridge = MarketResearch(Repository(), services=lambda: (Live(), News()), now=lambda: later)
    assert asyncio.run(bridge.lookup(analysis_scope()))['freshness']['stale'] is False
    bridge = MarketResearch(Repository(), services=lambda: (Live(), News([article()], stale=True)), now=lambda: later)
    assert asyncio.run(bridge.lookup(analysis_scope()))['freshness']['stale'] is True


def test_analysis_survives_trend_failure():
    async def reader(symbol):
        raise OSError('database down')
    bridge = MarketResearch(Repository(), services=lambda: (Live(), News()), now=lambda: NOW, trend_reader=reader)
    result = asyncio.run(bridge.lookup(analysis_scope()))
    assert result['status'] == 'EVIDENCE_READY'
    assert {item['snapshot']['kind'] for item in result['evidence_pack']['items']} == {'PRICE', 'NEWS'}


def test_prompt_mentions_trend_rule():
    from src.b1_answering.core.policy import Limits
    from src.b1_answering.evidence import grounded
    from src.b1_answering.evidence.market_contract import feed_pack
    evidence = prepare_evidence(feed_pack([trend_snapshot()]))
    request = grounded.build_grounded_request('Xu hướng FPT?', evidence, Limits.load(), {'source_type': 'MARKET_ANALYSIS'})
    assert 'không đổi, không nâng hay hạ nhãn' in request['systemInstruction']['parts'][0]['text']


def test_previous_answer_source_names_a_price_trend_citation_by_its_title():
    from src.retrieval_orchestration.live_research import citation_title
    scope = {'companies': ['FPT']}
    assert citation_title({'source_type': 'PRICE_TREND', 'title': 'Xu hướng giá FPT · dữ liệu FinMind'}, scope) \
        == 'Xu hướng giá FPT · dữ liệu FinMind'
    assert citation_title({'source_type': 'NEWS'}, scope) == 'Nguồn thị trường'
    assert citation_title({'source_type': 'BCTC', 'title': 'x'}, scope) == 'Báo cáo tài chính FPT'


@pytest.mark.parametrize('invalid_scope', [
    None, 42, 'private-scope-token', [],
    {'source_type': 'MARKET_ANALYSIS', 'companies': None},
    {'source_type': 'MARKET_ANALYSIS', 'companies': 42},
    {'source_type': 'MARKET_ANALYSIS', 'companies': [None]},
    {'source_type': 'MARKET_ANALYSIS', 'companies': {'FPT': 'private-scope-token'}},
])
def test_malformed_market_scope_returns_unavailable(invalid_scope):
    calls = []
    async def reader(symbol):
        calls.append(symbol)
        return price_trend()
    bridge = MarketResearch(Repository(), services=lambda: (Live(), News()),
                            now=lambda: NOW, trend_reader=reader)
    result = asyncio.run(bridge.lookup(invalid_scope))
    assert result['status'] == 'SYSTEM_UNAVAILABLE'
    assert result['reason_code'] == 'MARKET_UNAVAILABLE'
    assert calls == []
    assert 'private-scope-token' not in str(result)


@pytest.fixture
def historical_analysis_inputs():
    request = analysis_scope()
    request['_market_request']['day'] = '2026-10-22'
    class HistoricalLive(Live):
        def stock_history(self, symbol):
            assert symbol == 'FPT'
            payload = quote('2026-10-22')
            payload['bars'][0]['price_unit'] = 'thousand_vnd'
            return payload
    return request, HistoricalLive(), News([article('2026-10-22T02:00:00+00:00')])


@pytest.mark.parametrize('requested_day', ['2026-10-22', '2026-10-23'])
def test_analysis_passes_explicit_day_as_date_to_supported_trend_reader(
        historical_analysis_inputs, requested_day):
    from datetime import date
    request, live, news = historical_analysis_inputs
    request['_market_request']['day'] = requested_day
    calls = []
    async def reader(symbol, *, as_of=None):
        calls.append((symbol, as_of))
        trend = price_trend()
        trend['as_of'] = as_of.isoformat() if as_of is not None else NOW.date().isoformat()
        return trend
    bridge = MarketResearch(Repository(), services=lambda: (live, news), now=lambda: NOW,
                            trend_reader=reader)
    result = asyncio.run(bridge.lookup(request))
    assert calls == [('FPT', date.fromisoformat(requested_day))]
    assert type(calls[0][1]) is date
    assert result['status'] == 'EVIDENCE_READY'
    trend_item = result['evidence_pack']['items'][0]
    assert trend_item['source_type'] == 'PRICE_TREND'
    assert trend_item['snapshot']['as_of'] == requested_day
    assert prepare_evidence(result['evidence_pack'])


def assert_market_warning(caplog, message, *private_values):
    records = [record for record in caplog.records
               if record.name == 'src.retrieval_orchestration.market_research']
    assert len(records) == 1
    record = records[0]
    assert record.levelname == 'WARNING'
    assert record.getMessage() == message
    assert record.exc_info is None
    assert record.exc_text is None
    assert record.stack_info is None
    for value in private_values:
        assert value not in caplog.text
        assert value not in repr(record.__dict__)


def test_historical_analysis_skips_legacy_reader_without_latest_fallback(
        historical_analysis_inputs, caplog):
    request, live, news = historical_analysis_inputs
    request['_private_scope'] = 'private-scope-token'
    calls = []
    async def reader(symbol):
        calls.append(symbol)
        return price_trend()
    bridge = MarketResearch(Repository(), services=lambda: (live, news), now=lambda: NOW,
                            trend_reader=reader)
    caplog.set_level('WARNING', logger='src.retrieval_orchestration.market_research')
    result = asyncio.run(bridge.lookup(request))
    assert calls == []
    assert result['status'] == 'EVIDENCE_READY'
    assert {item['source_type'] for item in result['evidence_pack']['items']} == {'PRICE', 'NEWS'}
    assert prepare_evidence(result['evidence_pack'])
    assert_market_warning(caplog, 'Market trend lookup failed (TypeError)', 'private-scope-token')


def test_trend_reader_failure_logs_only_fixed_message_and_exception_class(caplog):
    request = analysis_scope()
    request['_private_scope'] = 'private-scope-token'
    async def reader(symbol):
        raise OSError('private-exception-token')
    bridge = MarketResearch(Repository(), services=lambda: (Live(), News()), now=lambda: NOW,
                            trend_reader=reader)
    caplog.set_level('WARNING', logger='src.retrieval_orchestration.market_research')
    result = asyncio.run(bridge.lookup(request))
    assert result['status'] == 'EVIDENCE_READY'
    assert {item['source_type'] for item in result['evidence_pack']['items']} == {'PRICE', 'NEWS'}
    assert prepare_evidence(result['evidence_pack'])
    assert_market_warning(caplog, 'Market trend lookup failed (OSError)',
                          'private-exception-token', 'private-scope-token')


def test_rejected_trend_evidence_preserves_price_news_and_logs_safely(caplog):
    from src.b1_answering.evidence.market_contract import feed_item
    request = analysis_scope()
    request['_private_scope'] = 'private-scope-token'
    invalid_trend = {'as_of': 'private-evidence-token', 'horizons': {}}
    with pytest.raises(CitationError):
        feed_item(trend_snapshot(as_of=invalid_trend['as_of'], trend=invalid_trend))
    async def reader(symbol):
        return invalid_trend
    bridge = MarketResearch(Repository(), services=lambda: (Live(), News()), now=lambda: NOW,
                            trend_reader=reader)
    caplog.set_level('WARNING', logger='src.retrieval_orchestration.market_research')
    result = asyncio.run(bridge.lookup(request))
    assert result['status'] == 'EVIDENCE_READY'
    assert {item['source_type'] for item in result['evidence_pack']['items']} == {'PRICE', 'NEWS'}
    assert prepare_evidence(result['evidence_pack'])
    assert_market_warning(caplog, 'Market trend evidence rejected (CitationError)',
                          'private-evidence-token', 'private-scope-token')


def test_outer_market_failure_logs_only_fixed_message_and_exception_class(caplog):
    request = analysis_scope()
    request['_private_scope'] = 'private-scope-token'
    def failed_services():
        raise RuntimeError('private-exception-token')
    bridge = MarketResearch(Repository(), services=failed_services, now=lambda: NOW)
    caplog.set_level('WARNING', logger='src.retrieval_orchestration.market_research')
    result = asyncio.run(bridge.lookup(request))
    assert result['status'] == 'SYSTEM_UNAVAILABLE'
    assert result['reason_code'] == 'MARKET_UNAVAILABLE'
    assert 'private-exception-token' not in str(result)
    assert 'private-scope-token' not in str(result)
    assert_market_warning(caplog, 'Market lookup failed (RuntimeError)',
                          'private-exception-token', 'private-scope-token')


@pytest.mark.parametrize('question', ['phân tích fpt', 'Phân tích MBB', 'đánh giá cổ phiếu FPT',
                                      'FPT mạnh hay yếu?'])
def test_plain_company_analysis_goes_to_market_analysis(question):
    # Chat test 13/11: "phân tích fpt" was routed to a BCTC metric clarification instead of analysis.
    decision = analyze_live(question, today=NOW.date())
    assert decision['decision'] == 'MARKET_LOOKUP'
    assert decision['scope']['source_type'] == 'MARKET_ANALYSIS'


@pytest.mark.parametrize('question', ['phân tích doanh thu FPT năm 2025', 'Phân tích lợi nhuận MBB quý 3/2025',
                                      'Phân tích chiến lược FPT trong báo cáo thường niên 2025'])
def test_metric_analysis_keeps_the_report_route(question):
    assert analyze_live(question, today=NOW.date())['scope'].get('source_type') != 'MARKET_ANALYSIS'


# ---- analysis focus: 'phân tích cổ phiếu' and 'phân tích tài chính' are different questions ----
@pytest.mark.parametrize('question,focus', [
    ('phân tích fpt', 'STOCK'), ('phân tích cổ phiếu fpt', 'STOCK'), ('fpt mạnh hay yếu', 'STOCK'),
    ('phân tích tài chính fpt', 'FINANCIAL'), ('tình hình tài chính fpt', 'FINANCIAL'),
    ('sức khỏe tài chính fpt', 'FINANCIAL'), ('phân tích báo cáo tài chính fpt', 'FINANCIAL'),
    ('phân tích bctc fpt', 'FINANCIAL'), ('đánh giá tài chính fpt', 'FINANCIAL'),
    ('phân tích kỹ thuật fpt', 'TECHNICAL'), ('xu hướng giá fpt', 'TECHNICAL'),
    ('xu hướng cổ phiếu fpt', 'TECHNICAL'),
])
def test_analysis_questions_carry_their_focus(question, focus):
    decision = analyze_live(question)
    assert decision['scope']['source_type'] == 'MARKET_ANALYSIS'
    assert decision['scope']['companies'] == ['FPT']
    assert decision['scope']['_market_request']['focus'] == focus


@pytest.mark.parametrize('question', [
    'doanh thu fpt 2025', 'xu hướng doanh thu fpt', 'thuyết minh bctc fpt',
    'phân tích tài chính fpt năm 2025',  # a dated period stays with reports: health shows the latest period only
])
def test_metric_report_and_dated_questions_are_not_analysis(question):
    assert analyze_live(question)['scope'].get('source_type') != 'MARKET_ANALYSIS'


@pytest.mark.parametrize('focus,first', [('STOCK', '(1) "Giá:'), ('FINANCIAL', '(1) "Tình hình tài chính:'),
                                         ('TECHNICAL', '(1) "Xu hướng giá:')])
def test_prompt_orders_groups_by_focus(focus, first):
    from src.b1_answering.core.policy import Limits
    from src.b1_answering.evidence import grounded
    scope = {'source_type': 'MARKET_ANALYSIS', 'companies': ['FPT'], '_market_request': {'focus': focus}}
    text = grounded.build_grounded_request('phân tích', _one_evidence(), Limits.load(), scope)['systemInstruction']['parts'][0]['text']
    assert first in text


def _one_evidence():
    return {'e1': dict(evidence_id='e1', source_id='s', chunk_id='c', source_sha256='a'*64, source_type='PRICE',
                       title='Giá', passage='Giá gần nhất của FPT: 50,500 VND.', locator={'trading_day': '2026-11-13'})}


def test_financial_focus_without_verified_bctc_says_so():
    class Provider:
        async def count_tokens(self, request): return 100
        async def generate(self, request):
            item = json.loads(request['contents'][0]['parts'][0]['text'])['evidence'][0]
            text = item['passage'].splitlines()[0]
            return {'model_version': 'fake', 'usage': {'input_tokens': 100, 'output_tokens': 40, 'total_tokens': 140},
                    'payload': {'claims': [{'text': text, 'evidence_ids': [item['evidence_id']],
                                           'support_quotes': [{'evidence_id': item['evidence_id'], 'quote': text}]}]}}
    async def run():
        bridge = MarketResearch(Repository(), services=lambda: (Live(), News()), now=lambda: NOW)
        engine = LiveResearchService(object(), provider=Provider(), market=bridge)
        result = await engine.answer('phân tích tài chính fpt', 'session', today=NOW.date())
        assert result['answering']['status'] == 'DRAFT_READY'
        assert 'Chưa có số liệu tài chính đã đối chiếu với BCTC gốc' in result['answering']['draft']
        stock = await engine.answer('phân tích cổ phiếu fpt', 'session', today=NOW.date())
        assert 'Chưa có số liệu tài chính' not in stock['answering']['draft']
    asyncio.run(run())
