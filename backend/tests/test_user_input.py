"""Mixed Vietnamese abbreviations, raw Telex and calendar price followups."""
from datetime import date
import asyncio
import json
from uuid import uuid4

import pytest

from src.retrieval_orchestration.input_normalization import normalize_user_text, _rules
from src.retrieval_orchestration.live_research import analyze_live, LiveResearchService
from src.retrieval_orchestration.retrieval_flow.intent import _fold

TODAY = date(2026, 10, 24)


@pytest.mark.parametrize('text', [
    'giá fpt hôm qua là bn', 'gia fpt hom qua la bn',
    'giaf fpt hoom qua laf bn', 'giá FPT hoom qua laf bao nhieeu',
    'hoom qua fpt cos giaf bao nhieeu', 'giaf coor phieeus FPT hoom qua laf bn',
])
def test_mixed_price_questions_share_same_intent(text):
    result = analyze_live(text, today=TODAY)
    assert result['decision'] == 'MARKET_LOOKUP'
    assert result['scope']['companies'] == ['FPT']
    assert result['scope']['_market_request']['day'] == '2026-10-23'


@pytest.mark.parametrize(('text', 'expected'), [
    ('laf bn', 'la bao nhieu'), ('ngafy 15', 'ngay 15'), ('ko dc', 'khong duoc'),
    ('tooms tawts tin tuwcs', 'tom tat tin tuc'),
    ('loij nhuaanj sau thuees', 'loi nhuan sau thue'),
])
def test_normalization_is_idempotent(text, expected):
    result = normalize_user_text(text)
    assert _fold(result) == expected
    assert normalize_user_text(result) == result


def test_identifiers_links_numbers_and_ticker_positions_are_not_rewritten():
    text = 'FPT SSI LAF DDC PROFIT_AFTER_TAX 57,400 15/10/2026 50k https://example.com/laf?bn=ko HTTPS://example.com/laf mail@laf.com'
    assert normalize_user_text(text) == text
    assert 'laf' in normalize_user_text('giá laf hôm nay')
    assert normalize_user_text('LAF') == 'LAF'


def test_financial_and_news_questions_use_same_normalization():
    result = analyze_live('loij nhuaanj sau thuees FPT quy4/2025 laf bn', today=TODAY)
    assert result['decision'] == 'SEARCH'
    assert result['scope']['metric_code'] == 'PROFIT_AFTER_TAX'
    news = analyze_live('tooms tawts tin tuwcs FPT hoom nay', today=TODAY)
    assert news['decision'] == 'MARKET_LOOKUP'
    assert news['scope']['_market_request']['action'] == 'SUMMARY'


@pytest.mark.parametrize(('question', 'day'), [
    ('còn ngày 15', '2026-10-15'), ('con ngay 15', '2026-10-15'),
    ('conf ngafy 15', '2026-10-15'), ('còn ngày 15/10/2026', '2026-10-15'),
    ('conf ngafy 15/10/2026', '2026-10-15'), ('ngày 15/9', '2026-09-15'),
])
def test_partial_dates_inherit_existing_month_year_and_keep_price(question, day):
    first = analyze_live('hôm qua fpt có giá bao nhiêu', today=TODAY)
    result = analyze_live(question, first['scope'], today=TODAY)
    assert result['decision'] == 'MARKET_LOOKUP'
    assert result['scope']['source_type'] == 'PRICE'
    assert result['scope']['companies'] == ['FPT']
    assert result['scope']['_market_request']['day'] == day


def test_partial_day_without_anchor_asks_month_year_and_keeps_pending_day():
    first = analyze_live('giá FPT ngày 15', today=TODAY)
    assert first['decision'] == 'ASK_CLARIFICATION'
    assert first['reason_code'] == 'MISSING_MARKET_DATE'
    assert first['scope']['source_type'] == 'PRICE'
    assert all('quý' not in option['label'] and 'tài sản' not in option['label'] for option in first['clarification_options'])
    second = analyze_live('tháng 10 năm 2026', first['scope'], today=TODAY)
    assert second['decision'] == 'MARKET_LOOKUP'
    assert second['scope']['_market_request']['day'] == '2026-10-15'


def test_year_only_remains_price_and_asks_for_day_instead_of_financial_metric():
    first = analyze_live('giá FPT hôm qua', today=TODAY)
    result = analyze_live('năm 2025', first['scope'], today=TODAY)
    assert result['decision'] == 'ASK_CLARIFICATION'
    assert result['reason_code'] == 'MISSING_MARKET_DATE'
    assert result['scope']['source_type'] == 'PRICE'
    corrected = analyze_live('ngày 15/10', result['scope'], today=TODAY)
    assert corrected['scope']['_market_request']['day'] == '2025-10-15'


def test_short_day_uses_previous_month_and_rejects_invalid_day_without_rolling():
    first = analyze_live('giá FPT ngày 28/02/2026', today=TODAY)
    result = analyze_live('còn ngày 31', first['scope'], today=TODAY)
    assert result['decision'] == 'ASK_CLARIFICATION'
    assert result['reason_code'] == 'INVALID_DATE'
    assert result['scope']['source_type'] == 'PRICE'


@pytest.mark.parametrize('stem', ['gia', 'co', 'phieu', 'hom', 'ngay', 'thang', 'nam', 'quy',
    'loi', 'nhuan', 'tong', 'tai', 'san', 'tien', 'khoan', 'no', 'vay', 'ngan', 'dai',
    'han', 'von', 'chu', 'huu', 'doanh', 'thu', 'thuan', 'dong', 'dau', 'tu', 'kinh',
    'chi', 'phi', 'ban', 'hang', 'tin', 'tuc', 'tom', 'tat', 'tiet', 'bai', 'viet',
    'noi', 'dung', 'du', 'an', 'cong', 'vien', 'nghe', 'xem', 'giup', 'bao', 'nhieu'])
@pytest.mark.parametrize('tone', ['s', 'f', 'r', 'x', 'j'])
def test_generated_telex_tone_variants(stem, tone):
    assert normalize_user_text(stem+tone) == stem


@pytest.mark.parametrize(('key', 'value'), list(_rules()[0]['aliases'].items()))
def test_configured_common_aliases_are_supported(key, value):
    assert _fold(normalize_user_text(key)) == value


def test_ambiguous_short_forms_use_context_and_quantities_stay_unchanged():
    assert _fold(normalize_user_text('giá cp FPT hn bn')) == 'gia co phieu fpt hom nay bao nhieu'
    assert _fold(normalize_user_text('tin dự án FPT ở hn')) == 'tin du an fpt o ha noi'
    assert _fold(normalize_user_text('cp bán hàng')) == 'chi phi ban hang'
    assert _fold(normalize_user_text('dk doanh nghiệp')) == 'dang ky doanh nghiep'
    assert _fold(normalize_user_text('ko đk')) == 'khong duoc'
    assert normalize_user_text('57 tr 50 k 2 b') == '57 tr 50 k 2 b'
    assert normalize_user_text('bar PROFIT_AFTER_TAX FPT') == 'bar PROFIT_AFTER_TAX FPT'
    assert normalize_user_text('laf giá bn').startswith('laf ')


def test_compact_calendar_labels_work_in_context():
    first = analyze_live('giá FPT hôm qua', today=TODAY)
    result = analyze_live('conf ngafy15', first['scope'], today=TODAY)
    assert result['scope']['_market_request']['day'] == '2026-10-15'
    result = analyze_live('ngay15 thg9 nam2025', first['scope'], today=TODAY)
    assert result['scope']['_market_request']['day'] == '2025-09-15'


def test_numbered_company_choice_is_not_mistaken_for_day_of_month():
    first = analyze_live('giá cổ phiếu hôm nay bn', today=TODAY)
    assert first['reason_code'] == 'MISSING_COMPANY'
    result = analyze_live('1', first['scope'], today=TODAY)
    assert result['decision'] == 'MARKET_LOOKUP'
    assert result['scope']['companies'] == ['FPT']
    assert result['scope']['_market_request']['day'] == '2026-10-24'


def test_alias_expansion_is_bounded_without_truncating_the_original_input():
    text = ('bn '*1300).strip()
    assert normalize_user_text(text) == text
    assert normalize_user_text('.'*4000) == '.'*4000


def test_mixed_typing_and_short_date_return_prices_from_the_requested_bars():
    from datetime import datetime, timezone, timedelta
    from src.retrieval_orchestration.market_research import MarketResearch
    class Live:
        def stock_history(self, symbol):
            return {'source': 'vnstock_kbs', 'fetched_at': '2026-10-24T10:00:00+07:00',
                    'bars': [{'date': day, 'close': close, 'source': 'vnstock_kbs', 'price_unit': 'thousand_vnd'}
                             for day, close in [('2026-10-15', '60.2'), ('2026-10-23', '57.4')]]}
    async def run():
        bridge = MarketResearch(object(), services=lambda: (Live(), None),
            now=lambda: datetime(2026, 10, 24, 10, tzinfo=timezone(timedelta(hours=7))))
        service = LiveResearchService(object(), market=bridge)
        first = await service.answer('giaf FPT hoom qua laf bn', 't', today=TODAY)
        assert '23/10/2026: 57,400 VND' in first['answering']['draft']
        second = await service.answer('conf ngafy 15', 't', first['scope'], today=TODAY)
        assert second['answering']['draft'] == 'Giá đóng cửa FPT ngày 15/10/2026: 60,200 VND.'
        assert second['answering']['budget']['calls_used'] == 0
    asyncio.run(run())


def test_legacy_topicless_clarification_can_recover_previous_price_but_not_active_financial():
    class Market:
        async def lookup(self, scope):
            return {'status': 'NO_DATA', 'reason_code': 'NO_TRADING_DAY', 'message': 'Chưa có dữ liệu phiên.'}
    async def run():
        previous = {'scope': analyze_live('giá FPT hôm qua', today=TODAY)['scope']}
        legacy = {'companies': ['FPT'], 'periods': ['2025'], 'metric_code': None}
        service = LiveResearchService(object(), market=Market())
        result = await service.answer('còn ngày 15/10/2026', 't', legacy, previous_result=previous, today=TODAY)
        assert result['scope']['source_type'] == 'PRICE'
        assert result['scope']['_market_request']['day'] == '2026-10-15'
        financial = analyze_live('tổng tài sản FPT', today=TODAY)['scope']
        result = await service.answer('ngày 15/10/2026', 't', financial, previous_result=previous, today=TODAY)
        assert result['scope']['source_type'] == 'BCTC'
        assert result['scope']['metric_code'] == 'TOTAL_ASSETS'
    asyncio.run(run())


def test_saved_chat_keeps_original_typing_and_resumes_price_context(tmp_path):
    from src.retrieval_orchestration.web_sessions import SessionStore
    class Market:
        calls = []
        async def lookup(self, scope):
            self.calls.append(scope['_market_request']['day'])
            return {'status': 'NO_DATA', 'reason_code': 'NO_TRADING_DAY', 'message': 'Chưa có dữ liệu phiên.'}
    async def run():
        market = Market()
        service = LiveResearchService(object(), market=market)
        store = SessionStore(tmp_path, engine=service)
        owner = str(uuid4())
        session = await store.create(owner)
        sid = session['session_id']
        raw = 'giaf FPT hoom qua laf bn'
        sent = await store.send(owner, sid, raw, 0)
        assert sent['messages'][-2]['content'] == raw
        reopened = SessionStore(tmp_path, engine=service)
        await reopened.send(owner, sid, 'conf ngafy 15', 1)
        result = await reopened.send(owner, sid, 'còn ngày 15/10/2026', 2)
        assert result['messages'][-1]['result']['scope']['source_type'] == 'PRICE'
        asked = await reopened.send(owner, sid, 'năm 2025', 3)
        assert asked['messages'][-1]['result']['reason_code'] == 'MISSING_MARKET_DATE'
        assert len(market.calls) == 3
        doc = json.loads((tmp_path/owner/(sid+'.json')).read_text('utf8'))
        assert doc['metadata']['live_context']['source_type'] == 'PRICE'
    asyncio.run(run())
