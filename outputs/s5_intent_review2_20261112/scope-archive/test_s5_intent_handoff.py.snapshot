"""Evidence is not an accepted route or calibrated confidence."""
import copy
import json
from pathlib import Path

import pytest

from src.retrieval_orchestration.intent_handoff import prepare_intent_review


def payload(policy='intent-linear-v1', kind='CLASSIFIER_PROBABILITY_UNCALIBRATED', raw_label='NUMERIC', label='NUMERIC'):
    ranking = dict(ranking_policy=policy, score_type=kind,
                   groups=[dict(intent_label=raw_label, score=.71), dict(intent_label='NEWS', score=.3)])
    resolution = dict(ranking_policy='intent-request-objectives-v5', score_type='DECISION_EVIDENCE_NO_CONFIDENCE',
                      intent_label=label, confidence=None, runtime_enabled=False,
                      unresolved_requests=[], component_labels=[])
    return ranking, resolution


def test_uncalibrated_probability_is_not_promoted_to_accepted_intent():
    result = prepare_intent_review(*payload())
    assert result['status'] == 'NEED_VALIDATION' and result['accepted_intent'] is None
    assert result['reason'] == 'UNCALIBRATED_CLASSIFIER'
    assert result['route'] is None and result['confidence'] is None


def test_different_labels_do_not_borrow_the_original_score():
    result = prepare_intent_review(*payload(label='PERSON_ROLE'))
    assert result['reason'] == 'LABEL_DISAGREEMENT'
    assert result['proposed_intent'] == 'PERSON_ROLE' and result['raw_top_intent'] == 'NUMERIC'
    assert 'score' not in result and result['accepted_intent'] is None


def test_real_homograph_case_is_not_reported_as_successful_numeric_classification():
    path = Path(__file__).resolve().parents[2] / 'outputs/s5_intent_review2_20261112/run02/results.json'
    row = next(r for r in json.loads(path.read_text(encoding='utf-8'))['review2_probes'] if r['id'] == 'R2-01')
    result = prepare_intent_review(row['base_ranking'], row['resolution'])
    assert result['status'] == 'NEED_VALIDATION'
    assert result['reason'] == 'UNRESOLVED_REQUEST_TARGET'
    assert result['accepted_intent'] is None and result['route'] is None


@pytest.mark.parametrize('key', ['ranking_policy', 'score_type'])
def test_missing_ranking_contract_is_rejected(key):
    ranking, resolution = payload()
    del ranking[key]
    result = prepare_intent_review(ranking, resolution)
    assert result['status'] == 'REJECT_CLASSIFICATION'


def test_mixed_without_component_evidence_is_not_automatically_both():
    result = prepare_intent_review(*payload(raw_label='MIXED', label='MIXED'))
    assert result['reason'] == 'MIXED_COMPONENTS_UNVERIFIED' and result['route'] is None


def test_matching_valid_cosine_can_only_proceed_to_original_threshold_policy():
    result = prepare_intent_review(*payload('cosine-max-per-label-v1', 'COSINE_SIMILARITY_NOT_PROBABILITY'))
    assert result['status'] == 'CHECK_COSINE_POLICY'
    assert result['accepted_intent'] is None and result['route'] is None


def test_resolution_cannot_claim_fabricated_confidence_or_live_execution():
    ranking, resolution = payload()
    resolution['confidence'] = 1.0
    assert prepare_intent_review(ranking, resolution)['status'] == 'REJECT_CLASSIFICATION'
    resolution['confidence'] = None
    resolution['runtime_enabled'] = True
    assert prepare_intent_review(ranking, resolution)['status'] == 'REJECT_CLASSIFICATION'


def test_handoff_does_not_mutate_inputs():
    values = payload()
    before = copy.deepcopy(values)
    prepare_intent_review(*values)
    assert values == before
