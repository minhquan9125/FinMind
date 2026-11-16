"""The measurement must keep failed/absent cases and distinguish labels/routes."""
import copy
import importlib
from pathlib import Path

import pytest


@pytest.fixture
def evaluation(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    return importlib.import_module('evaluate_s5_wbs132')


def case(ident='x', label='NUMERIC', branch='VECTOR', **extra):
    return dict(id=ident, text='Một câu hỏi mới', label=label, branch=branch, family=ident, note='rationale', **extra)


def observed(ident='x', label='NUMERIC', branch='VECTOR', **extra):
    return dict(id=ident, label=label, branch=branch,
                **{'components': [], 'elapsed_ms': 10, 'fallback_calls': 0, 'error': None, **extra})


def test_label_correct_cannot_hide_wrong_route(evaluation):
    result = evaluation.summarize([case()], [observed(branch='NEWS')])
    assert result['label_correct'] == 1
    assert result['branch_correct'] == result['joint_correct'] == 0


def test_missing_result_and_timeout_stay_in_denominator(evaluation):
    result = evaluation.summarize([case('a'), case('b'), case('c')],
                                  [observed('a'), observed('b', elapsed_ms=100, error='TIMEOUT')])
    assert result['total'] == 3 and result['joint_correct'] == 1
    assert result['missing_ids'] == ['c'] and result['error_ids'] == ['b']
    assert result['joint_accuracy'] == pytest.approx(1 / 3)


def test_mixed_requires_component_set_even_if_label_and_branch_match(evaluation):
    result = evaluation.summarize([case(label='MIXED', branch='BOTH', components=['PERSON_ROLE','NUMERIC'])],
                                  [observed(label='MIXED', branch='BOTH', components=['NUMERIC'])])
    assert result['label_correct'] == result['branch_correct'] == 1
    assert result['joint_correct'] == 0


def test_fallback_rate_uses_actual_calls_not_gate_or_source(evaluation):
    result = evaluation.summarize([case('a'), case('b')],
                                  [observed('a', gate='FALLBACK'), observed('b', fallback_calls=1)])
    assert result['fallback_cases'] == 1 and result['fallback_rate'] == 0.5


def test_duplicate_or_unknown_results_are_not_silently_dropped(evaluation):
    for rows in ([observed(), observed()], [observed('unknown')]):
        with pytest.raises(ValueError):
            evaluation.summarize([case()], rows)


@pytest.mark.parametrize('change', [
    {'label':'TYPO'}, {'branch':'TYPO'}, {'label':'MIXED','components':['NUMERIC']},
    {'label':'MIXED','components':['NUMERIC','NUMERIC']}, {'components':['PRICE']}, {'context':'invalid'},
])
def test_validator_rejects_invalid_gold(evaluation, change):
    with pytest.raises(ValueError):
        evaluation.validate_cases([case(**change)])


def test_validator_rejects_duplicate_normalized_questions(evaluation):
    rows = [case('a'), case('b')]
    rows[1]['text'] = 'mot cau hoi moi!!!'
    with pytest.raises(ValueError):
        evaluation.validate_cases(rows)


def test_complete_dataset_has_all_eleven_labels(evaluation):
    import json
    path = Path(__file__).parent / 'fixtures/s5_wbs132_cases.json'
    rows = json.loads(path.read_text(encoding='utf-8'))['cases']
    before = copy.deepcopy(rows)
    evaluation.validate_cases(rows)
    assert len(rows) == 60 and {row['label'] for row in rows} == evaluation.LABELS
    assert rows == before


@pytest.mark.parametrize('result,branch', [
    ({'b1_decision':'PRICE_ANALYTICS','status':'NO_DATA'}, 'PRICE'),
    ({'b1_decision':'MARKET_LOOKUP','scope':{'source_type':'NEWS'}}, 'NEWS'),
    ({'b1_decision':'SEARCH','scope':{'source_type':'BCTN'}}, 'VECTOR'),
    ({'b1_decision':'SEARCH','hybrid_router':{'route':'BOTH'},'status':'NO_DATA'}, 'BOTH'),
    ({'b1_decision':'ASK_CLARIFICATION','scope':{'source_type':'PRICE'}}, 'ASK_CLARIFICATION'),
    ({'b1_decision':'UNSUPPORTED'}, 'REFUSE'),
])
def test_branch_mapping_preserves_specialized_paths(evaluation, result, branch):
    assert evaluation.branch_of(result) == branch


def test_planner_score_is_separate_from_final_chat_path(evaluation):
    row = observed(branch='VECTOR', planner_outputs=[{'route':'BOTH'}])
    metrics = evaluation.planner_summary([case(branch='BOTH')], [row])
    assert metrics['correct'] == metrics['observed_eligible'] == 1
    assert evaluation.summarize([case(branch='BOTH')], [row])['branch_correct'] == 0


def test_planner_not_called_is_not_counted_as_a_success(evaluation):
    metrics = evaluation.planner_summary([case(branch='PRICE')], [observed(planner_outputs=[])])
    assert metrics['observed_eligible'] == 0 and metrics['accuracy'] is None
    assert metrics['not_observed_ids'] == ['x']


def test_rule_resolved_label_does_not_inflate_raw_model_accuracy(evaluation):
    row = observed(classification={'base_ranking':{'groups':[{'intent_label':'NEWS'}]}})
    metrics = evaluation.summarize([case()], [row])
    assert metrics['label_correct'] == 1 and metrics['raw_model_label_correct'] == 0
