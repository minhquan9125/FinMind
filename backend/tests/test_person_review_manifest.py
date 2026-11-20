import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('person_review_manifest',Path(__file__).resolve().parents[1]/'scripts/prepare_person_review_manifest.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def record(ordinal=1,decision='APPROVED',ident='00000000-0000-0000-0000-000000000001'):
    return f'''### {decision} — {ordinal}. {ident}

**Bằng chứng nguồn:**
> Ông A là Giám đốc.

**Bản kiểm:** A → FPT · `HOLDS_ROLE` · Giám đốc.
**Nguồn:** https://example.com/source.pdf · document_id `11111111-1111-1111-1111-111111111111` · trang PDF `18`.
**Hash section/trang đã kiểm:** `{'a'*64}`.
'''

def test_keeps_report_decisions_without_granting_publish_status():
    parsed=module.parse_report(record()+record(2,'REJECTED','00000000-0000-0000-0000-000000000002'))
    assert parsed['counts']=={'APPROVED':1,'REJECTED':1}
    assert parsed['publication_status'].startswith('NOT_PUBLISHABLE')
    assert parsed['records'][1]['report_decision']=='REJECTED'
    assert parsed['records'][0]['pdf_page']==18

def test_duplicate_id_and_missing_source_rejected():
    with pytest.raises(ValueError,match='duplicate'):
        module.parse_report(record()+record(2))
    with pytest.raises(ValueError,match='source binding'):
        module.parse_report(record().replace('**Nguồn:**','Missing source:'))

def test_noncontiguous_ordinals_rejected():
    with pytest.raises(ValueError,match='contiguous'):
        module.parse_report(record(2))

def test_windows_line_endings_do_not_leave_a_period_in_position():
    parsed=module.parse_report(record().replace('\n','\r\n'))
    assert parsed['records'][0]['position']=='Giám đốc'
