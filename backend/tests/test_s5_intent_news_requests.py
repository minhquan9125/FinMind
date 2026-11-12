"""News objectives, independent requests and source-only counterexamples."""
import numpy as np
import pytest

from src.retrieval_orchestration.intent_news_requests import explicit_intent, requests, resolve_objectives

LABELS = ['ENTITY_RELATION', 'MIXED', 'NEWS', 'NUMERIC', 'PERSON_ROLE', 'REPORT_CONTENT', 'TREND']


@pytest.mark.parametrize('question', [
    'Tìm bài tin cho biết doanh thu của VJC trong năm 2024.',
    'Hãy tìm bài báo về lợi nhuận của HPG.',
    'Liệt kê bản tin về việc bổ nhiệm CEO của DGC.',
    'Tóm tắt bài tin về doanh thu của PNJ.',
    'Đối chiếu hai bài tin về kế hoạch lợi nhuận của VNM.',
])
def test_article_is_the_requested_output(question):
    assert explicit_intent(question) == 'NEWS'


@pytest.mark.parametrize('question', [
    'Theo bài tin đã chỉ định, doanh thu VJC là bao nhiêu?',
    'Lấy số liệu doanh thu trong bài tin về PNJ.',
    'CEO xuất hiện trong bài tin là ai?',
    'Đánh giá xu hướng doanh thu theo các bài tin.',
    'Có bao nhiêu bài tin về VJC?',
    'Tìm giá trị doanh thu trong bài tin đã chỉ định.',
])
def test_article_as_source_does_not_force_news(question):
    assert explicit_intent(question) != 'NEWS'


def test_news_numeric_case_reproduces_wrong_whole_question_head():
    texts = requests('Cho biết LNST VJC 2024 rồi tìm bài tin VJC mở đường bay mới.')
    base = [.07, .225, .23, .15, .1, .1, .125]
    components = [[.08, .15, .1, .27, .1, .13, .17], [.1, .1, .45, .1, .08, .08, .09]]
    before = np.asarray(base).copy()
    decision = resolve_objectives(base, components, LABELS, texts)
    assert decision['intent_label'] == 'MIXED'
    assert set(decision['component_labels']) == {'NUMERIC', 'NEWS'}
    assert np.array_equal(base, before)
    assert decision['confidence'] is None and decision['runtime_enabled'] is False


def test_read_value_and_identify_ceo_are_separate_requests():
    text = 'Đọc tổng tài sản PNJ cuối năm 2024 và xác định ai là CEO của PNJ.'
    assert requests(text) == ['Đọc tổng tài sản PNJ cuối năm 2024', 'xác định ai là CEO của PNJ']


@pytest.mark.parametrize('question', [
    'Đọc doanh thu và lợi nhuận của PNJ năm 2024.',
    'Đọc doanh thu AI và cloud của FPT năm 2025 là bao nhiêu?',
    'Đọc doanh thu PNJ năm 2024 và năm 2023.',
])
def test_read_metric_lists_do_not_create_independent_requests(question):
    assert requests(question) == [question]


def test_two_news_requests_do_not_become_mixed():
    texts = ['Tìm bài tin bổ nhiệm CEO PNJ', 'tóm tắt bài tin mở rộng nhà máy']
    decision = resolve_objectives([.1, .4, .1, .1, .1, .1, .1], [], LABELS, texts)
    assert decision['intent_label'] == 'NEWS'


def test_single_news_request_overrides_wrong_mixed_head():
    decision = resolve_objectives([.1, .4, .1, .1, .1, .1, .1], [], LABELS,
                                  ['Tìm bài tin cho biết doanh thu của VJC trong năm 2024.'])
    assert decision['intent_label'] == 'NEWS'
