"""Second review: lexical evidence must respect Vietnamese spelling and goals."""
import unicodedata

import pytest

from src.retrieval_orchestration.intent_semantic_requests import explicit_intent, requests, resolve_objectives

LABELS = ['ENTITY_RELATION', 'MIXED', 'NEWS', 'NUMERIC', 'PERSON_ROLE', 'REPORT_CONTENT', 'TREND']


@pytest.mark.parametrize('question', [
    'Lợi nhuận FPT có độc lập với mảng viễn thông không?',
    'Loi nhuan FPT co doc lap voi mang vien thong khong?',
    'Đọc báo cáo chất lượng dịch vụ của FPT.',
    'Đọc nội dung về sản lượng điện của GEG.',
])
def test_homographs_do_not_create_numeric_evidence(question):
    assert explicit_intent(question) != 'NUMERIC'


@pytest.mark.parametrize('question', [
    'Đọc doanh thu FPT năm 2024.',
    'Doc doanh thu FPT nam 2024.',
    'Lương CEO FPT năm 2024 là bao nhiêu?',
    'Luong CEO FPT nam 2024 la bao nhieu?',
    'Giá cổ phiếu FPT hôm nay bao nhiêu?',
    'Doanh thu AI và cloud của FPT là bao nhiêu?',
])
def test_legitimate_value_requests_remain_numeric(question):
    assert explicit_intent(question) == 'NUMERIC'


@pytest.mark.parametrize('form', ['NFC', 'NFD'])
def test_homograph_protection_is_unicode_normalization_independent(form):
    assert explicit_intent(unicodedata.normalize(form, 'Lợi nhuận có độc lập không?')) != 'NUMERIC'
    assert explicit_intent(unicodedata.normalize(form, 'Đọc doanh thu FPT.')) == 'NUMERIC'


@pytest.mark.parametrize('question', [
    'Ai đang làm CEO của FPT?',
    'Ai hiện đang đảm nhiệm chức Tổng giám đốc của VNM?',
    'Người đứng đầu FPT là ai?',
    'Nguoi dung dau DGC la ai?',
])
def test_role_paraphrases_have_explicit_role_evidence(question):
    assert explicit_intent(question) == 'PERSON_ROLE'


@pytest.mark.parametrize('question', ['FPT có tin gì mới?', 'VNM co tin tuc gi moi?'])
def test_indirect_news_questions_have_news_evidence(question):
    assert explicit_intent(question) == 'NEWS'


@pytest.mark.parametrize('question', [
    'Lương CEO FPT bao nhiêu?',
    'Tìm bài tin về người đứng đầu FPT.',
    'Doanh thu AI của FPT bao nhiêu?',
])
def test_role_paraphrases_do_not_override_other_goals(question):
    assert explicit_intent(question) != 'PERSON_ROLE'


def test_financial_change_explanation_is_not_every_why_question():
    assert explicit_intent('Giải thích vì sao doanh thu FPT giảm qua ba năm.') == 'TREND'
    assert explicit_intent('Giải thích vì sao ông An được bổ nhiệm.') is None
    assert explicit_intent('Giải thích vì sao doanh thu giảm theo bài tin đã chỉ định.') is None


def test_numeric_and_independent_causal_analysis_are_mixed():
    texts = requests('Cho biết doanh thu FPT năm 2024 rồi giải thích vì sao doanh thu giảm qua ba năm.')
    decision = resolve_objectives([.1, .1, .1, .4, .1, .1, .1], [], LABELS, texts)
    assert decision['intent_label'] == 'MIXED'
    assert set(decision['component_labels']) == {'NUMERIC', 'TREND'}


def test_rejected_numeric_evidence_does_not_override_classifier_head():
    base = [.1, .1, .1, .1, .1, .1, .4]
    result = resolve_objectives(base, [], LABELS, ['Lợi nhuận FPT có độc lập với mảng viễn thông không?'])
    assert result['intent_label'] == 'TREND'
    assert result['confidence'] is None and result['runtime_enabled'] is False
    assert base == [.1, .1, .1, .1, .1, .1, .4]


def test_read_report_content_is_report_instead_of_a_salary_metric():
    assert explicit_intent('Đọc báo cáo chất lượng dịch vụ của FPT.') == 'REPORT_CONTENT'


def test_indirect_news_can_be_an_independent_clause():
    text = 'FPT có tin gì mới rồi cho biết EPS FPT năm 2024.'
    assert len(requests(text)) == 2


@pytest.mark.parametrize('question', [
    'Doc lap cua loi nhuan FPT voi mang vien thong la the nao?',
    'Doc luong khach cua VJC nam 2024.',
])
def test_ambiguous_ascii_read_and_salary_need_context(question):
    assert explicit_intent(question) != 'NUMERIC'


@pytest.mark.parametrize('question', [
    'Giải thích vì sao chất lượng dịch vụ giảm qua ba năm.',
    'Giai thich vi sao chat luong dich vu giam qua ba nam.',
])
def test_quantity_homograph_is_not_financial_trend_evidence(question):
    assert explicit_intent(question) != 'TREND'
