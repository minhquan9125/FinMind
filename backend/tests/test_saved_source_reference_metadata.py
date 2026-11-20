import copy
from src.retrieval_orchestration.saved_source_reference import source_reference_metadata


def test_source_link_and_date_come_from_saved_evidence_not_a_guessed_address():
    item={'locator':{'url':'https://example.org/fpt','published_at':'2026-11-20T08:00:00+07:00'}}
    before=copy.deepcopy(item);citation={'source_url':'https://wrong.example.org/other'}
    lines=source_reference_metadata(citation,item)
    assert citation['source_url']=='https://example.org/fpt'
    assert 'Ngày đăng: 20/11/2026' in lines
    assert item==before


def test_pdf_reference_keeps_the_document_url_and_page():
    citation={}
    lines=source_reference_metadata(citation,{'locator':{'pdf_page':33},'source_url':'https://example.org/report.pdf'})
    assert 'Trang PDF: 33' in lines
    assert citation['source_url'].endswith('report.pdf')


def test_no_public_link_is_explicit_and_never_invented():
    citation={'source_url':'javascript:alert(1)'}
    lines=source_reference_metadata(citation,{'locator':{},'source_url':'javascript:alert(1)'})
    assert 'source_url' not in citation
    assert any('chưa có liên kết công khai' in line for line in lines)
