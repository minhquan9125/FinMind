import pytest
from src.retrieval_orchestration.news_presentation import has_recommendation_headline, render_news_list


@pytest.mark.parametrize('symbol', ['BID','CMG','CTG','ELC','FPT','ICT','ITD','MBB','TCB','VCB'])
def test_recommendation_is_attributed_without_changing_headline(symbol):
    title = f'Khuyến nghị mua {symbol} với kỳ vọng tăng giá'
    item = dict(title=title, snapshot=dict(provider='fireant', published_at='2026-11-16T18:30:00+00:00'))
    text = render_news_list([item])
    assert f'“{title}”' in text
    assert 'Nguồn lấy tin: FireAnt' in text
    assert 'Ngày đăng: 17/11/2026 [1]' in text
    assert 'không phải lời khuyên mua bán của FinMind' in text
    assert 'Bài có tiêu đề về nhận định/khuyến nghị đầu tư' in text


@pytest.mark.parametrize('title', ['VIC dẫn đầu chiều mua của khối ngoại, FPT chịu bán ròng',
    'FPT mua lại công ty công nghệ', 'FPT công bố kết quả kinh doanh'])
def test_ordinary_buy_or_sell_news_is_not_labeled_as_advice(title):
    assert not has_recommendation_headline(title)


def test_order_numbering_and_stale_status_are_preserved():
    items = [dict(title=title, snapshot=dict(provider='fireant', published_at='2026-11-17T09:00:00+07:00'))
             for title in ['Khuyến nghị mua FPT', 'FPT công bố kết quả kinh doanh']]
    text = render_news_list(items, stale=True)
    assert text.index(items[0]['title']) < text.index(items[1]['title'])
    assert '[1]' in text and '[2]' in text
    assert 'lần lấy tin mới vừa thất bại' in text
