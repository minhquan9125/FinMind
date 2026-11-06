"""Shared workbook definitions must survive conversion without invented approval."""
from xml.sax.saxutils import escape
from zipfile import ZipFile

import pytest

from backend.scripts.wbs17_workbook import load_workbook_suite


def workbook(path, *, readiness='READY_RETRIEVAL', runtime='Graph READY: v1', question='Original question?'):
    cells = {'A6': 'Test_ID', 'B6': 'Question', 'A7': 'TC_GRAPH_01', 'B7': question,
             'C7': 'Company-Company', 'D7': 'GRAPH', 'H7': readiness, 'I7': 'Needs setup',
             'L7': 'FPT; document 2024', 'M7': runtime, 'N7': 'SEARCH',
             'Q8': 'corpus', 'Q9': 'index', 'Q10': 'v1', 'Q13': '5'}
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    sheet = '<worksheet xmlns="'+ns+'"><sheetData><row>'+''.join(
        f'<c r="{k}" t="inlineStr"><is><t>{escape(v)}</t></is></c>' for k, v in cells.items()
    )+'</row></sheetData></worksheet>'
    with ZipFile(path, 'w') as z:
        z.writestr('xl/workbook.xml', '<workbook xmlns="'+ns+'" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Test_Cases_Master" sheetId="1" r:id="r1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml', sheet)
        z.writestr('xl/worksheets/_rels/sheet1.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="c1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments" Target="../comments/comment1.xml"/></Relationships>')
        z.writestr('xl/comments/comment1.xml', '<comments xmlns="'+ns+'"><commentList><comment ref="E7"><text><t>{"subject_id":"parent","object_id":"child","relation_type":"HAS_SUBSIDIARY","temporal":{"as_of":"2024-12-31"}}</t></text></comment></commentList></comments>')
    return path


def test_import_keeps_question_and_requires_human_gold_review(tmp_path):
    suite = load_workbook_suite(workbook(tmp_path/'a.xlsx'))
    c = suite['cases'][0]
    assert c['case_id'] == 'TC_GRAPH_01' and c['question'] == 'Original question?'
    assert c['gold']['status'] == 'DRAFT' and c['gold']['reviewer'] is None
    assert suite['minimum_repeats'] == 5
    assert c['context'] == {}  # Question interpretation belongs to the router.
    assert c['b1_context'] == {'companies': ['FPT'], 'periods': ['2024']}
    assert len(suite['workbook_sha256']) == 64


def test_unready_cases_cannot_run_and_unknown_selection_is_rejected(tmp_path):
    p = workbook(tmp_path/'a.xlsx', readiness='SETUP_REQUIRED')
    assert load_workbook_suite(p)['cases'][0]['readiness'] == 'NOT_READY'
    with pytest.raises(ValueError, match='Unknown case'):
        load_workbook_suite(p, case_ids=['missing'])


def test_ready_graph_without_pinned_version_is_rejected(tmp_path):
    with pytest.raises(ValueError, match='graph version'):
        load_workbook_suite(workbook(tmp_path/'a.xlsx', runtime='Graph READY: unknown'))
