"""Financial-value requests and boundaries that must not become NUMERIC."""
import pytest

from src.retrieval_orchestration.intent_numeric_requests import explicit_intent, resolve_objectives


@pytest.mark.parametrize('question', [
    'Doanh thu AI và cloud của doanh nghiệp ABC là bao nhiêu?',
    'Lợi nhuận sau thuế của doanh nghiệp XYZ năm 2024 là bao nhiêu?',
    'Gia tri ROE cua doanh nghiep QRS nam 2023 la bao nhieu?',
    'EPS của doanh nghiệp ABC năm 2024 bằng bao nhiêu?',
    'Cho biết tổng tài sản của doanh nghiệp XYZ cuối năm 2024.',
    'Đọc dòng tiền hoạt động kinh doanh của doanh nghiệp QRS năm 2023.',
    'Theo bài tin đã chỉ định, doanh thu của doanh nghiệp ABC là bao nhiêu?',
    'Theo BCTN XYZ, lợi nhuận mục tiêu năm 2025 là bao nhiêu?',
])
def test_explicit_financial_value_is_numeric(question):
    assert explicit_intent(question) == 'NUMERIC'


@pytest.mark.parametrize('question', [
    'Có bao nhiêu công ty con công bố doanh thu năm 2024?',
    'Tỷ lệ sở hữu cổ phần của ông An là bao nhiêu?',
    'Chủ tịch của doanh nghiệp có doanh thu lớn nhất là ai?',
    'Ngày nào CEO được bổ nhiệm, mức lương đã công bố bao nhiêu?',
    'Tìm bài tin cho biết doanh thu ABC năm 2024 là bao nhiêu.',
    'Tóm tắt kế hoạch lợi nhuận trong BCTN ABC.',
    'Trích nguyên văn hàng ghi giá trị doanh thu trong BCTC.',
    'Đánh giá xu hướng doanh thu của ABC qua ba năm.',
    'Giải thích vì sao doanh thu ABC giảm, số liệu là bao nhiêu?',
    'Lợi nhuận mục tiêu của ABC có khả thi không?',
    'Doanh thu của ABC là gì?',
    'Có bao nhiêu bài tin về lợi nhuận của ABC?',
    'Cho biết nội dung bài tin cổ tức của ABC.',
    'Cho biết chính sách ghi nhận doanh thu trong BCTN ABC.',
    'Cho biết kế hoạch lợi nhuận trong BCTN ABC.',
])
def test_other_objectives_are_not_forced_to_numeric(question):
    assert explicit_intent(question) != 'NUMERIC'


def test_numeric_resolution_preserves_scores_and_has_no_confidence():
    labels = ['ENTITY_RELATION', 'MIXED', 'NEWS', 'NUMERIC', 'PERSON_ROLE', 'REPORT_CONTENT', 'TREND']
    base = [.267, .107, .059, .254, .081, .082, .150]
    unchanged = base.copy()
    decision = resolve_objectives(base, [], labels, ['Doanh thu AI và cloud của doanh nghiệp ABC là bao nhiêu?'])
    assert decision['intent_label'] == 'NUMERIC'
    assert decision['confidence'] is None and decision['runtime_enabled'] is False
    assert base == unchanged


def test_two_distinct_objectives_stay_mixed():
    labels = ['ENTITY_RELATION', 'MIXED', 'NEWS', 'NUMERIC', 'PERSON_ROLE', 'REPORT_CONTENT', 'TREND']
    texts = ['Cho biết doanh thu ABC năm 2024.', 'CEO của ABC là ai?']
    decision = resolve_objectives([.1, .1, .1, .4, .1, .1, .1], [[.1, .1, .1, .4, .1, .1, .1]] * 2, labels, texts)
    assert decision['intent_label'] == 'MIXED'
    assert set(decision['component_labels']) == {'NUMERIC', 'PERSON_ROLE'}
