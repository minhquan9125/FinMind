import pytest

from src.retrieval_orchestration.trend_question import trend_request, render_trend

SYMBOLS = {'FPT', 'VCB', 'BID', 'CTG'}


def trend(label='DOWN', ret='-9.7700', vs='-6.4400', sma='54.3000', as_of='2026-11-19'):
    def horizon(h):
        return {'label': label, 'sessions': h, 'return_percent': ret, 'close_vs_sma_percent': vs, 'sma': sma}
    return {'as_of': as_of, 'source': {'price_scale': 1000},
            'horizons': {str(h): horizon(h) for h in (20, 60, 200)}}


@pytest.mark.parametrize('text, symbols, horizons', [
    ('Xu hướng ngắn hạn của VCB thế nào?', ['VCB'], [20]),
    ('Xu hướng trung hạn của BIDV ra sao?', ['BID'], [60]),
    ('Vietcombank xu hướng dài hạn thế nào?', ['VCB'], [200]),
    ('Cổ phiếu BID dạo này tăng hay giảm?', ['BID'], [20, 60, 200]),
    ('Hỗm rồi BID đi lên hay đi xuống?', ['BID'], [20, 60, 200]),
    ('Giá VCB đang nằm trên hay dưới đường trung bình 20 phiên?', ['VCB'], [20]),
    ('So sánh xu hướng ngắn hạn của VCB và BID', ['VCB', 'BID'], [20]),
    ('VCB đang trong xu hướng tăng trung hạn đúng không?', ['VCB'], [60]),
])
def test_trend_questions_are_read(text, symbols, horizons):
    request = trend_request(text, {}, SYMBOLS)
    assert request['symbols'] == symbols and request['horizons'] == horizons


@pytest.mark.parametrize('text', [
    'Giá VCB tháng 10/2026 tăng hay giảm bao nhiêu %?',   # a named period: exact arithmetic on bars
    'Phân tích xu hướng VCB',                              # a full analysis keeps its own path
    'Tin tức VCB tăng hay giảm',
    'Lợi nhuận VCB tăng hay giảm',
    'Mã nào đang xu hướng tăng',                           # screening, not one company
    'Xu hướng thị trường thế nào',                         # no company
])
def test_other_questions_are_not_trend_questions(text):
    assert trend_request(text, {}, SYMBOLS) is None


def test_followup_reuses_horizon_for_a_new_company():
    context = {'companies': ['VCB'], '_trend_request': {'horizons': [20]}}
    assert trend_request('Còn BID?', context, SYMBOLS) == {'symbols': ['BID'], 'horizons': [20], 'claim': None}
    assert trend_request('còn trung hạn thì sao', context, SYMBOLS)['symbols'] == ['VCB']
    assert trend_request('Còn BID?', {'companies': ['VCB']}, SYMBOLS) is None


def test_answer_states_label_return_and_moving_average():
    text = render_trend({'VCB': trend()}, [20], None)
    assert 'VCB tính đến phiên 19/11/2026' in text
    assert 'Ngắn hạn (20 phiên): Giảm' in text
    assert 'giá giảm 9,77% so với 20 phiên trước' in text
    assert 'nằm dưới đường trung bình 20 phiên (54.300 đồng), thấp hơn 6,44%' in text
    assert 'Trung hạn' not in text


def test_false_premise_is_corrected():
    text = render_trend({'VCB': trend()}, [60], 'UP')
    assert text.startswith('Không đúng.')
    assert render_trend({'VCB': trend()}, [60], 'DOWN').startswith('Đúng.')


def test_comparison_lists_each_company():
    text = render_trend({'VCB': trend(), 'BID': trend(ret='-9.6200', vs='-5.5900', sma='32.3600')}, [20], None)
    assert 'giá giảm 9,77%' in text and 'giá giảm 9,62%' in text


def test_missing_return_is_explained_not_invented():
    data = trend(label='UNCLEAR', ret=None)
    text = render_trend({'VCB': data}, [20], None)
    assert 'Chưa rõ xu hướng' in text and 'chưa tính mức tăng/giảm' in text


# ---- wired into the chat ----
import asyncio

from src.retrieval_orchestration.live_research import LiveResearchService
from src.retrieval_orchestration.price_analytics import PriceAnalytics


class PriceStore:
    async def symbols(self): return {'VCB', 'BID'}


class Market:
    def __init__(self, broken=()):
        self.broken = broken

    async def trend_reader(self, symbol):
        if symbol in self.broken: raise RuntimeError('db down')
        return trend() if symbol == 'VCB' else trend(ret='-9.6200', vs='-5.5900', sma='32.3600')


def ask(text, context=None, broken=()):
    service = LiveResearchService(object(), market=Market(broken), prices=PriceAnalytics(PriceStore()))
    return asyncio.run(service.answer(text, 'session', context or {}))


def test_chat_answers_trend_from_stored_prices_and_follow_up_switches_company():
    first = ask('Xu hướng ngắn hạn của VCB thế nào?')
    assert first['reason_code'] == 'PRICE_TREND_READY'
    assert 'giá giảm 9,77% so với 20 phiên trước' in first['answering']['draft']
    second = ask('Còn BID?', first['scope'])
    assert second['reason_code'] == 'PRICE_TREND_READY'
    assert 'Xu hướng giá BID' in second['answering']['draft'] and 'giá giảm 9,62%' in second['answering']['draft']


def test_unreadable_prices_are_reported_not_invented():
    result = ask('Xu hướng ngắn hạn của VCB thế nào?', broken=('VCB',))
    assert result['status'] == 'SYSTEM_UNAVAILABLE' and result['reason_code'] == 'PRICE_TREND_UNAVAILABLE'
