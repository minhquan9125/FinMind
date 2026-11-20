import asyncio

import pytest

from src.retrieval_orchestration.screening import is_screening_question, render_screen

SYMBOLS = {'FPT', 'VCB', 'BID', 'CTG'}


def trend(label20='UP', ret20='6.24', vs20='3.10', label60='DOWN', label200='DOWN'):
    def horizon(label, ret='1.00', vs='1.00'):
        return {'label': label, 'return_percent': ret, 'close_vs_sma_percent': vs}
    return {'as_of': '2026-11-18', 'horizons': {'20': horizon(label20, ret20, vs20), '60': horizon(label60),
                                                 '200': horizon(label200)}}


def health(profit=None, revenue=None, period='2026-Q3'):
    def signal(value):
        return {'value': value, 'status': 'complete' if value is not None else 'insufficient_data'}
    return {'period': period, 'signals': {'profit_yoy_percent': signal(profit), 'revenue_yoy_percent': signal(revenue)}}


@pytest.mark.parametrize('text', ['h mã nào đang xu hướng', 'mã nào đang phát triển tốt',
                                  'hiện tại mã nào đang ngon để đầu tư', 'doanh nghiệp nào đang tăng trưởng',
                                  'công ty nào tốt', 'ma nao dang tang'])
def test_screening_questions_are_recognized(text):
    assert is_screening_question(text, SYMBOLS)


@pytest.mark.parametrize('text', ['FPT đang phát triển tốt không', 'nên mua VCB không', 'giá VCB hôm nay',
                                  'mã nào là của Vietcombank', 'công ty nào phát triển tốt hơn Hòa Phát?'])
def test_other_questions_are_not_screening(text):
    assert not is_screening_question(text, SYMBOLS)


def test_rising_codes_listed_by_return_with_reasons():
    text = render_screen({'FPT': trend(ret20='6.24', vs20='3.10'), 'VCB': trend(ret20='9.50', vs20='4.00'),
                          'BID': trend(label20='DOWN')}, {}, '2026-11-18', None)
    assert text.startswith('Lọc theo dữ kiện đến ngày 18/11/2026:')
    assert 'VCB (+9,5% trong 20 phiên, giá trên SMA20 4,0%), FPT (+6,2% trong 20 phiên, giá trên SMA20 3,1%)' in text
    assert 'BID' not in text
    assert 'Chưa có mã nào có xu hướng tăng dài hạn (200 phiên) theo dữ liệu.' in text
    assert 'Chưa đủ số liệu BCTC đã đối chiếu để so sánh tăng trưởng cùng kỳ.' in text
    assert 'không chịu trách nhiệm' not in text


def test_verified_growth_listed_and_long_term_style_puts_it_first():
    text = render_screen({'FPT': trend()}, {'VCB': health(profit='22.10', period='2026-Q3'), 'FPT': health()},
                         '2026-11-18', 'FINANCIAL')
    assert 'VCB (lợi nhuận +22,1% so với cùng kỳ, quý 3/2026)' in text
    assert text.index('Tăng trưởng so với cùng kỳ') < text.index('Xu hướng tăng ngắn hạn')


def test_skipped_codes_are_reported():
    assert '(Bỏ qua 1 mã do chưa đọc được dữ liệu.)' in render_screen({}, {}, '2026-11-18', None, skipped=1)


# ---- wired into the chat ----
from src.retrieval_orchestration.live_research import LiveResearchService
from src.retrieval_orchestration.price_analytics import PriceAnalytics


class PriceStoreFixture:
    async def symbols(self): return {'FPT', 'VCB', 'HPG'}


class Market:
    def __init__(self, broken=()):
        self.broken = broken

    async def trend_reader(self, symbol):
        if symbol in self.broken: raise RuntimeError('db down')
        return {'FPT': trend(ret20='5.0'), 'HPG': trend(ret20='30.0')}.get(symbol) or trend(label20='DOWN')

    async def screening_health_reader(self, symbols):
        # Only codes with BCTC come back: HPG has prices but no financial statements.
        return {'FPT': health(), 'VCB': health(profit='12.0')}


def run_screen(text, context=None, broken=()):
    service = LiveResearchService(object(), market=Market(broken), prices=PriceAnalytics(PriceStoreFixture()))
    return asyncio.run(service.answer(text, 'session', context or {}))


def test_chat_answers_screening_from_the_database():
    result = run_screen('mã nào đang tăng')
    assert result['reason_code'] == 'SCREENING_READY' and result['answering']['status'] == 'DRAFT_READY'
    assert 'FPT (+5,0% trong 20 phiên' in result['answering']['draft']
    assert 'VCB (lợi nhuận +12,0% so với cùng kỳ' in result['answering']['draft']


def test_non_screening_question_does_not_enter_the_price_store():
    service = LiveResearchService(object(), market=Market(), prices=PriceAnalytics(object()))
    assert asyncio.run(service._answer_screening('giá VCB hôm nay', {})) is None


def test_one_unreadable_code_does_not_break_the_list():
    draft = run_screen('mã nào đang tăng', broken=('VCB',))['answering']['draft']
    assert 'FPT (+5,0%' in draft and '(Bỏ qua 1 mã do chưa đọc được dữ liệu.)' in draft


def test_long_term_style_puts_growth_first():
    draft = run_screen('mã nào đang phát triển', {'_investor_focus': {'focus': 'FINANCIAL', 'source': 'STATED'}})[
        'answering']['draft']
    assert draft.index('Tăng trưởng so với cùng kỳ') < draft.index('Xu hướng tăng ngắn hạn')


def test_screening_only_lists_codes_with_full_data():
    draft = run_screen('dạo này mã gì ngon')['answering']['draft']
    assert 'FPT (+5,0%' in draft and 'HPG' not in draft


@pytest.mark.parametrize('text', ['dạo này mã gì ngon', 'mã nào đang tăng', 'mã mô đang tốt', 'dạo ni mã j ngon',
                                  'cổ phiếu j đang tăng trưởng', 'công ty mô đang phát triển'])
def test_question_words_gi_nao_mo_j_are_equivalent(text):
    assert is_screening_question(text, SYMBOLS)
