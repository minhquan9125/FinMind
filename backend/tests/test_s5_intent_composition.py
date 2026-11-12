import numpy as np
import pytest
from src.retrieval_orchestration.intent_composition import requests,combine_scores
from src.retrieval_orchestration.intent_scoring import baseline_policy


def test_two_questions_are_two_requests_without_needing_and():
    parts=requests('Ai giữ chức Chủ tịch của doanh nghiệp? Báo cáo mô tả chính sách kiểm soát ra sao?')
    assert len(parts)==2


def test_company_and_metrics_lists_do_not_create_independent_requests():
    assert len(requests('So sánh doanh thu VCB và TCB năm 2024.'))==1
    assert len(requests('Doanh thu và lợi nhuận doanh nghiệp năm 2024 là bao nhiêu?'))==1


def test_citation_and_glossary_are_support_not_an_extra_request():
    parts=requests('Ai được bổ nhiệm làm KTT? Trích câu làm bằng chứng cho câu trả lời; KTT = kế toán trưởng.')
    assert parts==['Ai được bổ nhiệm làm KTT']


def test_standalone_quote_of_report_is_still_a_request():
    assert len(requests('Trích nguyên văn chính sách quản trị rủi ro trong báo cáo.'))==1


def test_compound_imperatives_can_be_separated():
    assert len(requests('Tìm công ty con rồi cho biết doanh thu của từng công ty.'))==2


def test_and_alone_does_not_make_mixed_and_same_label_parts_do_not_boost():
    labels=['MIXED','NUMERIC','PERSON_ROLE','REPORT_CONTENT']
    base=np.array([.1,.7,.1,.1])
    result=combine_scores(base,[[.1,.7,.1,.1],[.1,.6,.2,.1]],labels)
    assert np.array_equal(result['scores'],base)
    assert result['support']==0


def test_distinct_requests_add_only_computed_mixed_support_and_keep_raw_scores():
    labels=['MIXED','PERSON_ROLE','REPORT_CONTENT']
    base=np.array([.15,.45,.4])
    result=combine_scores(base,[[.1,.8,.1],[.1,.2,.7]],labels)
    assert np.allclose(result['scores'],[.7,.45,.4])
    assert np.array_equal(base,[.15,.45,.4])
    assert result['component_labels']==['PERSON_ROLE','REPORT_CONTENT']


def test_single_or_unclear_mixed_part_cannot_force_promotion():
    labels=['MIXED','PERSON_ROLE','REPORT_CONTENT']
    base=np.array([.1,.6,.3])
    assert np.array_equal(combine_scores(base,[[.1,.8,.1]],labels)['scores'],base)
    assert np.array_equal(combine_scores(base,[[.8,.1,.1],[.1,.2,.7]],labels)['scores'],base)


def test_new_composition_score_is_rejected_by_legacy_policy():
    with pytest.raises(ValueError,match='UNSUPPORTED_SCORE_CONTRACT'):
        baseline_policy(dict(ranking_policy='intent-composition-support-v1',score_type='COMPOSITION_SUPPORT_UNCALIBRATED',groups=[]))
