"""Hưng's review cases: acronym segmentation and common role phrasings."""
import pytest

from src.retrieval_orchestration.intent_request_review import requests, explicit_intent, resolve_objectives


@pytest.mark.parametrize('question', [
    'Doanh thu mảng AI và dịch vụ cloud của FPT năm 2025 là bao nhiêu?',
    'Cho biết doanh thu cloud và AI của FPT năm 2025 là bao nhiêu?',
    'Doanh thu AI và cloud của doanh nghiệp ABC là bao nhiêu?',
    'Hãy cho biết doanh thu mảng AI và dịch vụ cloud của FPT năm 2025 là bao nhiêu?',
    'Cho biết doanh thu AI và cloud của ABC năm 2025 là bao nhiêu?',
])
def test_ai_acronym_does_not_create_two_requests(question):
    assert requests(question) == [question]


def test_ai_acronym_does_not_hide_a_real_second_request():
    question = 'Doanh thu mảng AI của FPT năm 2025 là bao nhiêu và tìm bài tin FPT ký hợp đồng cloud.'
    assert len(requests(question)) == 2


def test_uppercase_who_question_still_splits_real_requests():
    assert len(requests('AI giữ chức Chủ tịch? BCTN mô tả chính sách nhân sự ra sao?')) == 2


@pytest.mark.parametrize('question', [
    'Chủ tịch HĐQT của FPT là ai?',
    'Chu tich HDQT cua ABC la ai?',
    'Ông Nguyễn Văn A giữ chức gì tại FPT?',
    'CEO của FPT là ai?',
    'Ai là CEO của ABC?',
    'Who is the CEO of ABC?',
])
def test_common_role_phrasings(question):
    assert explicit_intent(question) == 'PERSON_ROLE'


@pytest.mark.parametrize('question', [
    'Tìm bài tin về việc bổ nhiệm CEO FPT.',
    'Trích nguyên văn hàng chức vụ CEO trong BCTN.',
    'Lương CEO của FPT năm 2025 là bao nhiêu?',
    'BCTN mô tả chiến lược phát triển AI và cloud ra sao?',
])
def test_role_words_do_not_override_other_objectives(question):
    assert explicit_intent(question) != 'PERSON_ROLE'


def test_role_fix_preserves_raw_scores_and_null_confidence():
    labels = ['MIXED', 'NUMERIC', 'PERSON_ROLE', 'REPORT_CONTENT', 'TREND']
    base = [.1, .6, .1, .1, .1]
    original = base.copy()
    result = resolve_objectives(base, [], labels, ['CEO của FPT là ai?'])
    assert result['intent_label'] == 'PERSON_ROLE'
    assert result['confidence'] is None and result['runtime_enabled'] is False
    assert base == original
