"""Historical price questions: read into a request, computed from bars, answered by fixed sentences."""
import asyncio
from datetime import date
from decimal import Decimal

import pytest

from src.retrieval_orchestration.price_analytics import PriceAnalytics, PriceQuestionError, parse

TODAY = date(2026, 11, 13)
SYMBOLS = {'VCB', 'FPT', 'MBB', 'MSN'}


def bar(day, o, h, l, c, v):
    return {'date': day, 'open': Decimal(o), 'high': Decimal(h), 'low': Decimal(l), 'close': Decimal(c), 'volume': v}


DATA = {
    'VCB': [bar(date(2026, 5, 20), '63.17', '64.17', '61.29', '64.07', 14381600),
            bar(date(2026, 10, 1), '57.0', '58.0', '56.5', '57.5', 3000000),
            bar(date(2026, 10, 2), '57.5', '59.9', '57.0', '59.0', 5000000),
            bar(date(2026, 10, 5), '59.0', '59.5', '55.2', '56.0', 7000000),
            bar(date(2026, 10, 6), '56.9', '57.4', '56.0', '57.3', 4496200),
            bar(date(2026, 11, 12), '60.0', '61.0', '59.0', '60.5', 2000000)],
    'MBB': [bar(date(2026, 9, 30), '19.65', '19.8', '19.55', '19.65', 6955000),
            bar(date(2026, 10, 6), '19.15', '19.2', '18.85', '19.2', 17320700)],
    'FPT': [], 'MSN': [bar(date(2026, 7, 27), '65.0', '65.1', '63.5', '63.9', 4605200)],
}


class FakeStore:
    async def symbols(self):
        return SYMBOLS

    async def bars(self, symbol, start, end):
        return [b for b in DATA[symbol] if start <= b['date'] < end]


def ask(question):
    return asyncio.run(PriceAnalytics(FakeStore()).answer(question, TODAY))


def text(result):
    return result['answering']['draft'] if result.get('answering') else result['message']


def test_one_day_gives_all_fields_in_nghin_dong():
    out = text(ask('Ngày 20/05/2026, giá mở cửa, cao nhất, thấp nhất và đóng cửa của VCB lần lượt là bao nhiêu?'))
    for fact in ('63,17', '64,17', '61,29', '64,07'):
        assert fact in out
    assert 'khối lượng' not in out          # not asked for


def test_one_day_without_named_fields_gives_the_whole_bar_with_volume():
    out = text(ask('VCB ngày 20/05/2026 giá thế nào'))
    assert '14.381.600 cổ phiếu' in out and '63,17' in out


def test_highest_and_lowest_close_in_a_period_with_their_dates():
    out = text(ask('Giá đóng cửa cao nhất và thấp nhất của VCB trong tháng 10/2026 là bao nhiêu, vào ngày nào?'))
    assert 'Giá đóng cửa cao nhất' in out and '59 nghìn đồng' in out and '02/10/2026' in out
    assert 'Giá đóng cửa thấp nhất' in out and '56 nghìn đồng' in out and '05/10/2026' in out
    assert '4 phiên' in out


def test_highest_price_means_the_highest_high_not_the_highest_close():
    out = text(ask('Giá cao nhất của VCB trong tháng 10 là bao nhiêu'))
    assert '59,9 nghìn đồng' in out and '02/10/2026' in out


def test_average_and_total_volume():
    assert '4.874.050 cổ phiếu/phiên' in text(ask('Khối lượng giao dịch trung bình của VCB trong tháng 10/2026'))
    assert 'Tổng khối lượng giao dịch của VCB' in text(ask('Tổng khối lượng giao dịch của VCB tháng 10/2026 là bao nhiêu'))


def test_two_days_compare_gives_direction_and_percent():
    out = text(ask('So sánh giá đóng cửa của MBB giữa phiên 30/09/2026 và phiên 06/10/2026: tăng hay giảm bao nhiêu?'))
    assert '19,65' in out and '19,2' in out and 'giảm 0,45 nghìn đồng (−2,29%)' in out


def test_change_over_a_period_uses_first_and_last_session():
    out = text(ask('VCB tăng hay giảm bao nhiêu % từ 01/10/2026 đến 06/10/2026?'))
    assert '57,5' in out and '57,3' in out and 'giảm 0,2 nghìn đồng' in out


def test_range_and_volume_of_a_day():
    out = text(ask('Ngày 27/07/2026 giá đóng cửa của MSN là bao nhiêu và biên độ dao động trong ngày (high − low)?'))
    assert '63,9' in out and '1,6 nghìn đồng' in out


def test_weekend_is_explained_with_the_nearest_earlier_session():
    result = ask('Giá đóng cửa của VCB ngày 03/10/2026 là bao nhiêu?')
    assert result['status'] == 'NO_DATA' and 'cuối tuần' in result['message'] and '02/10/2026' in result['message']


def test_a_date_beyond_the_data_is_said_to_be_missing_not_guessed():
    result = ask('Giá đóng cửa của VCB ngày 21/12/2026')
    assert result['status'] == 'NO_DATA' and 'ngoài khoảng dữ liệu' in result['message']


def test_symbol_without_bars_in_the_period_says_so():
    result = ask('Giá cao nhất của FPT trong tháng 10/2026')
    assert result['status'] == 'NO_DATA' and 'chưa phủ' in result['message']


def test_impossible_date_is_reported():
    result = ask('Giá đóng cửa VCB ngày 31/02/2026')
    assert result['status'] == 'NO_DATA' and 'không tồn tại' in result['message']


def test_period_without_an_operation_tells_how_to_ask():
    result = ask('Giá VCB tháng 10/2026')
    assert result['status'] == 'NO_DATA' and 'Giá cao nhất của VCB' in result['message']


@pytest.mark.parametrize('question', [
    'giá cao nhất của VCB trong tháng 10/2026',
    'VCB đạt giá cao nhất bao nhiêu trong tháng 10 năm 2026?',
    'Trong tháng 10/2026, đỉnh giá của Vietcombank là bao nhiêu',
    'cho mình hỏi giá cao nhất cổ phiếu VCB tháng 10/2026 với',
])
def test_different_phrasings_give_the_same_answer(question):
    assert '59,9 nghìn đồng' in text(ask(question))


@pytest.mark.parametrize('question', [
    'Giá cổ phiếu VCB hôm nay',                 # live quote: the established flow
    'Nên mua VCB không, giá cao nhất tháng 10',  # advice is refused by the established flow
    'Vì sao giá VCB giảm tháng 10/2026',
    'Doanh thu của FPT năm 2025',
    'Giá vốn hàng bán của FPT năm 2025',
    'VCB là công ty gì',
])
def test_questions_that_are_not_price_analytics_are_left_to_the_chat(question):
    assert ask(question) is None


def test_parse_reads_periods_and_operations():
    spec = parse('Khối lượng lớn nhất của VCB quý 3/2026', SYMBOLS, TODAY)
    assert spec['symbols'] == ['VCB'] and spec['ops'] == ['max'] and spec['fields'] == ['volume']
    assert spec['period'][:2] == (date(2026, 7, 1), date(2026, 10, 1))
    spec = parse('VCB giá cao nhất 30 ngày qua', SYMBOLS, TODAY)
    assert spec['period'][0] == date(2026, 10, 14)
    spec = parse('Giá thấp nhất của VCB trong năm 2026', SYMBOLS, TODAY)
    assert spec['period'][:2] == (date(2026, 1, 1), date(2027, 1, 1))


def test_month_without_year_means_the_latest_such_month():
    assert parse('giá cao nhất VCB tháng 10', SYMBOLS, TODAY)['period'][0] == date(2026, 10, 1)
    assert parse('giá cao nhất VCB tháng 12', SYMBOLS, TODAY)['period'][0] == date(2025, 12, 1)


def test_more_than_five_symbols_is_refused():
    big = {'AAA', 'BBB', 'CCC', 'DDD', 'EEE', 'FFF'}
    with pytest.raises(PriceQuestionError):
        parse('Giá cao nhất của AAA BBB CCC DDD EEE FFF tháng 10/2026', big, TODAY)


def test_several_symbols_are_answered_one_by_one():
    out = text(ask('Giá cao nhất của VCB và MBB trong tháng 10/2026'))
    assert 'VCB' in out and 'MBB' in out and '59,9' in out and '19,2' in out


def test_company_without_prices_is_named_not_replaced():
    result = ask('Giá cao nhất của HPG trong tháng 10/2026')
    assert result['status'] == 'NO_DATA' and 'Chưa có dữ liệu giá của HPG' in result['message']
    assert 'VCB' in result['message']              # lists what is available


def test_known_and_unknown_company_together():
    out = text(ask('Giá cao nhất của VCB và HPG trong tháng 10/2026'))
    assert '59,9' in out and 'Chưa có dữ liệu giá của HPG' in out


def test_two_dates_are_compared_in_time_order_whatever_the_order_in_the_question():
    out = text(ask('Giá đóng cửa của VCB ngày 06/10/2026 so với ngày 05/10/2026 thì biến động bao nhiêu %?'))
    assert 'ngày 05/10/2026 là 56' in out and 'tăng 1,3 nghìn đồng' in out


def test_short_field_names_cao_and_thap_mean_the_days_high_and_low():
    out = text(ask('VCB ngày 20/05/2026 mở cửa, cao, thấp, đóng cửa bao nhiêu'))
    assert all(fact in out for fact in ('63,17', '64,17', '61,29', '64,07'))
    assert 'khối lượng' not in out
