"""Acceptance reports must distinguish v2 regression from independent accuracy."""
import importlib.util
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('evaluate_s5_router',ROOT/'backend/scripts/evaluate_s5_router.py')
evaluation=importlib.util.module_from_spec(spec); spec.loader.exec_module(evaluation)


def test_development_is_never_independent_acceptance_even_at_one_hundred_percent():
    assert evaluation.verdict_v2([dict(passed=True)],independent=False)['status']=='NOT_INDEPENDENT_ACCEPTANCE'

@pytest.mark.parametrize('rows', [[],[dict(passed=False)],[dict(passed=True)]*8+[dict(passed=False)]*2])
def test_missing_or_failing_predictions_fail_acceptance(rows):
    assert evaluation.verdict_v2(rows,independent=True)['status']=='FAIL'


def test_ninety_percent_boundary_and_all_failures_are_counted():
    assert evaluation.verdict_v2([dict(passed=True)]*9+[dict(passed=False)],independent=True)['status']=='PASS'


def test_corpus_has_no_legacy_v7_dependencies():
    cases=evaluation.load_corpus(evaluation.DEFAULT_CORPUS)
    assert len(cases)==110 and len({r['intent_label'] for r in cases})==11


def test_wrong_components_fail_even_if_route_matches():
    case=dict(intent_label='MIXED',component_intents=['NUMERIC','NEWS'])
    assert not evaluation.prediction_matches(case,dict(intent_label='MIXED',component_labels=['PRICE','NEWS']))

@pytest.mark.parametrize('text',['=1+1','+SUM(A1)','-1+2','@SUM(A1)'])
def test_excel_cannot_execute_user_text(text):
    assert evaluation.safe_cell(text).startswith("'")


def test_export_preserves_scores_errors_and_six_sheets(tmp_path):
    from openpyxl import load_workbook
    rows=[dict(id='one',question='=1+1',expected_label='PRICE',actual_label='NEWS',
        expected_components=[],actual_components=[],decision='NEED_FALLBACK',route=None,
        source='CLASSIFIER',reason_code='UNVERIFIED_V2_CLASSIFICATION',model_top_1_score=.73,
        model_score_gap=.03,passed=False,error='wrong label')]
    path=tmp_path/'report.xlsx'
    evaluation.write_workbook(path,dict(status='FAIL'),rows,dict(corpus_sha256='abc'))
    book=load_workbook(path)
    assert len(book.sheetnames)==6 and book['Ca_sai'].max_row==2
    assert all(c.data_type!='f' for ws in book for row in ws for c in row)
    assert any(c.value==.73 and c.data_type=='n' for row in book['Cau_hoi'] for c in row)
    book.close()
