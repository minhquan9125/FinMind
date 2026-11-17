"""User oracle judging must not silently bless dropped objectives or unexecuted injections."""
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('user_acceptance',ROOT/'backend/scripts/run_s5_user_acceptance.py')
runner=importlib.util.module_from_spec(spec)
# Deliberately feature-detect so missing runner is an assertion failure before implementation.

def load():
    assert spec.origin and Path(spec.origin).is_file(), 'User-acceptance runner not implemented'
    spec.loader.exec_module(runner)
    return runner


def case(**changes):
    return dict(id='USER-001',question='user question',expected_behavior='SERVE',expected_objectives=['PRICE','NEWS'],
        required_company='FPT',required_period=None,fallback_expectation='UNCONSTRAINED',provider_scenario='NORMAL')|changes


def observed(**changes):
    return dict(status='NO_DATA',classification_objectives=['PRICE','NEWS'],dispatch_objectives=['PRICE'],
        companies=['FPT'],periods=[],fallback_calls=0,dispatch_calls=1,clarification=None,exception=None,
        injected_scenario_reached=False)|changes


def test_a_correct_classifier_cannot_hide_a_dropped_second_user_objective():
    result=load().judge(case(),observed())
    assert result['status']=='FAIL' and any('objective' in error for error in result['mismatches'])


def test_a_failure_injection_not_reached_is_not_counted_as_tested():
    c=case(expected_behavior='ASK',expected_objectives=['ASK'],provider_scenario='TIMEOUT')
    o=observed(status='ASK_CLARIFICATION',dispatch_calls=0,clarification='Please clarify',dispatch_objectives=[])
    result=load().judge(c,o)
    assert result['injection_status']=='NOT_EXERCISED' and result['manual_review_required']


def test_unused_classifier_cannot_fail_a_correct_user_dispatch():
    c=case(expected_objectives=['PRICE'])
    result=load().judge(c,observed(classification_objectives=[],dispatch_objectives=['PRICE']))
    assert result['status']=='PASS' and not result['classifier_matches_gold']


def test_unreached_injection_does_not_hide_wrong_baseline_behavior():
    c=case(expected_behavior='ASK',expected_objectives=['ASK'],provider_scenario='TIMEOUT')
    result=load().judge(c,observed())
    assert result['status']=='FAIL' and result['injection_status']=='NOT_EXERCISED'


def test_company_and_period_cannot_silently_change():
    c=case(expected_objectives=['PRICE'],required_period='2025')
    result=load().judge(c,observed(companies=['MBB'],periods=['2026'],dispatch_objectives=['PRICE']))
    assert result['status']=='FAIL' and len(result['mismatches'])>=2


def test_clear_question_cannot_pass_if_classification_fallback_was_called():
    c=case(expected_objectives=['PRICE'],fallback_expectation='NEVER')
    result=load().judge(c,observed(fallback_calls=1,dispatch_objectives=['PRICE']))
    assert result['status']=='FAIL'


def test_clarification_requires_a_message_and_no_retrieval():
    c=case(expected_behavior='ASK',expected_objectives=['ASK'])
    assert load().judge(c,observed(status='ASK_CLARIFICATION',clarification=None))['status']=='FAIL'
