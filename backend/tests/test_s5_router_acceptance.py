"""Verify the 04.3 evaluator independently of runtime policy success counts."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('router_acceptance', ROOT / 'backend/scripts/evaluate_s5_router.py')
evaluation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluation)


def metrics():
    return dict(line_coverage=.95, branch_coverage=.94, behavior_coverage=1,
                policy_success=1, new_question_success=.95, regression_success=.95,
                new_label_accuracy=.95, new_candidate_route_accuracy=.95)


def test_all_declared_gates_must_pass():
    assert evaluation.acceptance_verdict(metrics())['status'] == 'PASS'


@pytest.mark.parametrize('field', list(metrics()))
@pytest.mark.parametrize('value', [.899999, None])
def test_coverage_or_model_failure_cannot_be_hidden_by_all_fallbacks_passing(field, value):
    result = evaluation.acceptance_verdict(metrics() | {field: value})
    assert result['status'] == 'FAIL' and field in result['failed_gates']


def test_exact_ninety_percent_boundary_is_accepted():
    assert evaluation.acceptance_verdict({k: .9 for k in metrics()})['status'] == 'PASS'


def test_reason_and_scope_must_match_in_addition_to_the_route():
    actual = dict(decision='ASK_CLARIFICATION', route=None, reason_code='INVALID_PERIOD', scope={'company_ticker': 'FPT'})
    assert evaluation.check_expected(actual, {'decision': 'ASK_CLARIFICATION', 'reason_code': 'MISSING_COMPANY'})
    assert not evaluation.check_expected(actual, {'decision': 'ASK_CLARIFICATION', 'scope.company_ticker': 'FPT'})


@pytest.mark.parametrize('value', ['=1+1', '+SUM(A1)', '-1+2', '@SUM(A1)'])
def test_user_and_provider_text_cannot_become_an_excel_formula(value):
    assert evaluation.safe_cell(value).startswith("'")


def test_real_numeric_scores_stay_numeric_in_excel():
    assert evaluation.safe_cell(.734) == .734


def test_wrong_mixed_components_fail_even_when_the_route_is_the_same():
    case = dict(expected_decision='NEED_FALLBACK', expected_label='MIXED',
                expected_components=['PERSON_ROLE', 'REPORT_CONTENT'], expected_business_route='BOTH')
    assessed = evaluation.assess_prediction(case, 'MIXED', ['ENTITY_RELATION', 'NUMERIC'], 'BOTH')
    assert assessed['label_pass'] and assessed['candidate_route_pass']
    assert assessed['component_pass'] is False and assessed['mismatches']


def test_component_order_does_not_change_the_semantic_objectives():
    case = dict(expected_decision='NEED_FALLBACK', expected_label='MIXED',
                expected_components=['NUMERIC', 'NEWS'], expected_business_route='VECTOR')
    assert not evaluation.assess_prediction(case, 'MIXED', ['NEWS', 'NUMERIC'], 'VECTOR')['mismatches']


def test_a_missing_prediction_cannot_pass_a_labeled_question():
    case = dict(expected_decision='NEED_FALLBACK', expected_label='NEWS',
                expected_components=[], expected_business_route='VECTOR')
    assert evaluation.assess_prediction(case, None, [], None)['label_pass'] is False


def test_scope_blocked_questions_do_not_need_model_inference():
    case = dict(expected_decision='ASK_CLARIFICATION', expected_label='NEWS',
                expected_components=[], expected_business_route=None)
    result = evaluation.assess_prediction(case, None, [], None)
    assert result['label_pass'] is None and not result['mismatches']


def test_failure_index_keeps_failed_scope_cases_with_no_label():
    row = dict(expected_label=None, passed=False, policy_pass=False)
    assert evaluation.include_failure(row)
    assert not evaluation.include_failure(row | dict(passed=True))


def test_business_questions_are_balanced_independent_and_complete():
    rows = evaluation.load_business()
    assert len(rows) == 80 and len(evaluation.regression_cases()) == 56
    assert sum(r['expected_decision'] == 'ASK_CLARIFICATION' for r in rows) == 10


def test_excel_keeps_expectations_real_scores_and_every_failed_test_id(tmp_path):
    from openpyxl import load_workbook
    cases = [('NEW', evaluation.load_business()), ('REGRESSION_032', evaluation.regression_cases())]
    questions = []
    for dataset, rows in cases:
        for case in rows:
            questions.append(dict(case, dataset=dataset, actual_label=None, actual_components=[],
                candidate_route=None, actual_decision='NOT_RUN', actual_route=None,
                reason_code='INFERENCE_ERROR', v7_reason_code=None, cosine_ranking=None,
                classifier_ranking=None, passed=False, policy_pass=False,
                mismatches=['Controlled export test: model unavailable']))
    path = tmp_path/'controlled-export.xlsx'
    summary = dict(verdict={'status': 'FAIL'}, metrics={k: None for k in evaluation.GATES},
                   model={'name': 'TEST_ONLY', 'revision': 'NO_MODEL'}, business_sha256='TEST_ONLY')
    summary['metrics'].update(line_coverage=.95, branch_coverage=.94, behavior_coverage=1)
    evaluation.write_workbook(path, summary, questions, [],
                              {'missing_lines': [1], 'missing_branches': [[1, 2]]}, {'MISSING_COMPANY': []})
    book = load_workbook(path)
    assert len(book.sheetnames) == 6
    assert book['Cau_hoi_moi'].max_row == 81 and book['Hoi_quy_03_2'].max_row == 57
    headers = [c.value for c in book['Cau_hoi_moi'][1]]
    for expected in ['Decision kỳ vọng', 'Lý do kỳ vọng', 'Thành phần kỳ vọng', 'Thành phần V7']:
        assert expected in headers
    failures = [r[0].value for r in book['Ca_sai'].iter_rows(min_row=2)]
    assert len(failures) == 136 and 'S5-043-N077' in failures
    assert all(r[headers.index('Kết quả')].value == 'FAIL'
               for r in book['Cau_hoi_moi'].iter_rows(min_row=2))
    assert all(c.data_type != 'f' for ws in book for row in ws for c in row)
    book.close()


@pytest.mark.parametrize('case', evaluation.policy_cases(), ids=lambda c: c['test_id'])
def test_contract_policy_case(case):
    row = evaluation.run_policy_case(case)
    assert row['passed'], row
