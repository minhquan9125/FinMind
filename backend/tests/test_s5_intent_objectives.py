from src.retrieval_orchestration.intent_request_objectives import explicit_intent,resolve_objectives

LABELS=['MIXED','NUMERIC','PERSON_ROLE','REPORT_CONTENT','TREND']


def test_explicit_report_policy_is_not_trend():
    assert explicit_intent('Báo cáo mô tả chính sách kiểm soát rủi ro ra sao?')=='REPORT_CONTENT'


def test_news_request_is_not_reclassified_as_report_or_role():
    assert explicit_intent('Tóm tắt bài tin về việc ai được bổ nhiệm trong BCTN.') is None


def test_numeric_in_report_does_not_trigger_report_rule():
    assert explicit_intent('Theo BCTC, ROE năm 2020 là bao nhiêu?') is None


def test_role_question_and_quote_request_have_different_objectives():
    assert explicit_intent('Ai giữ chức Chủ tịch HĐQT cuối năm?')=='PERSON_ROLE'
    assert explicit_intent('Trích nguyên văn hàng chức vụ trong BCTN.') is None


def test_mixed_requires_two_different_explicit_requests():
    parts=['Ai giữ chức Chủ tịch HĐQT cuối năm?', 'Báo cáo mô tả chính sách kiểm soát ra sao?']
    result=resolve_objectives([.1,.1,.4,.1,.3],[[.1,.1,.6,.1,.1],[.1,.1,.1,.2,.5]],LABELS,parts)
    assert result['intent_label']=='MIXED' and result['confidence'] is None


def test_two_people_questions_are_still_one_role_intent():
    parts=['Ai giữ chức Chủ tịch HĐQT?', 'Ai giữ chức Tổng giám đốc?']
    result=resolve_objectives([.5,.1,.2,.1,.1],[[.1,.1,.6,.1,.1]]*2,LABELS,parts)
    assert result['intent_label']=='PERSON_ROLE'


def test_single_explicit_report_can_correct_misclassified_head():
    result=resolve_objectives([.1,.1,.1,.2,.5],[],LABELS,['Báo cáo mô tả chính sách kiểm soát ra sao?'])
    assert result['intent_label']=='REPORT_CONTENT'


def test_unrelated_request_does_not_use_a_company_specific_rule():
    for company in ['VCB','UNKNOWN_COMPANY']:
        assert explicit_intent(f'Ai giữ chức Chủ tịch HĐQT {company}?')=='PERSON_ROLE'


def test_final_check_rejects_encoding_damage_before_embedding(monkeypatch):
    from pathlib import Path
    import importlib
    import pytest
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    checker=importlib.import_module('check_s5_intent_objectives_final')
    with pytest.raises(ValueError,match='CORRUPTED_QUESTION_ENCODING'):
        checker.validate_questions([dict(text='Ai gi? ch?c Gi?m ??c?')])
    checker.validate_questions([dict(text='Ai giữ chức Giám đốc?'),dict(text='Ai giu chuc Giam doc?')])
