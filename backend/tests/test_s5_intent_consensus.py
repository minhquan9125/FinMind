import numpy as np
import pytest
from src.retrieval_orchestration.intent_request_consensus import resolve

LABELS=['MIXED','NUMERIC','PERSON_ROLE','REPORT_CONTENT']


def test_role_and_report_agree_with_whole_question_so_resolve_mixed():
    raw=np.array([.16,.01,.42,.41])
    result=resolve(raw,[[.1,.1,.7,.1],[.1,.1,.1,.7]],LABELS)
    assert result['intent_label']=='MIXED'
    assert result['confidence'] is None
    assert result['reason']=='TWO_REQUESTS_SUPPORTED_BY_WHOLE_QUESTION'
    assert np.array_equal(raw,[.16,.01,.42,.41])


def test_clause_mistake_without_whole_question_agreement_does_not_promote():
    result=resolve([.1,.6,.2,.1],[[.1,.7,.1,.1],[.1,.1,.1,.7]],LABELS)
    assert result['intent_label']=='NUMERIC'


def test_same_label_requests_do_not_create_mixed():
    result=resolve([.1,.6,.2,.1],[[.1,.7,.1,.1],[.1,.6,.2,.1]],LABELS)
    assert result['intent_label']=='NUMERIC'


def test_single_primary_request_after_citation_removal_is_not_combined():
    result=resolve([.6,.1,.2,.1],[[.1,.1,.7,.1]],LABELS)
    assert result['intent_label']=='PERSON_ROLE'
    assert result['reason']=='SINGLE_PRIMARY_REQUEST_AFTER_SUPPORT_REMOVAL'


def test_original_mixed_is_preserved():
    result=resolve([.6,.1,.2,.1],[[.1,.1,.7,.1],[.1,.6,.2,.1]],LABELS)
    assert result['intent_label']=='MIXED'


def test_no_parts_keeps_whole_question_label():
    assert resolve([.1,.6,.2,.1],[],LABELS)['intent_label']=='NUMERIC'


def test_resolution_cannot_enter_legacy_score_threshold():
    from src.retrieval_orchestration.intent_scoring import baseline_policy
    decision=resolve([.1,.6,.2,.1],[],LABELS)
    with pytest.raises(ValueError,match='UNSUPPORTED_SCORE_CONTRACT'):
        baseline_policy(decision)
