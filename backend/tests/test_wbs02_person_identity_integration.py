import copy,hashlib,json,sqlite3
from pathlib import Path
import pytest
from src.person_role.person_identity import resolve_person_identity
from src.person_role.extractor import normalize_and_extract

ROOT=Path(__file__).resolve().parents[1]/'resources/person_role/wbs02-r2'


def fixture():return json.loads((ROOT/'examples/tcb.resolve.input.json').read_text('utf-8'))


def test_real_handoff_resolves_exact_decisions_without_changing_store_or_source():
    store=ROOT/'person.registry.sqlite';before=hashlib.sha256(store.read_bytes()).hexdigest()
    payload=fixture();original=copy.deepcopy(payload)
    companies=json.loads((ROOT/'company.registry.json').read_text('utf-8'))
    resolved,audit=resolve_person_identity(payload,store,companies)
    assert payload==original and resolved['documents']==original['documents'] and resolved['chunks']==original['chunks']
    ids={e['entity_id'] for e in resolved['entities'] if e['entity_type']=='Person' and e['resolution_status']=='resolved'}
    assert {'PER-326d1f708ee4d2ec61fb','PER-b2d19b702b1f626a6ace'}<=ids
    assert audit['registry_counts']==dict(mentions=959,approved=21,pending=938,rejected=0,persons=10)
    assert audit['relation_approvals_created']==0 and audit['registry_writes']==0
    assert hashlib.sha256(store.read_bytes()).hexdigest()==before


def test_changed_pinned_locator_cannot_reuse_identity_decision():
    payload=fixture();payload['chunks'][0]['locator']['page']+=1
    with pytest.raises(ValueError,match='snapshot'):
        resolve_person_identity(payload,ROOT/'person.registry.sqlite')


def test_new_document_with_same_name_does_not_resolve_by_name():
    import uuid
    payload=fixture();mapping={d['document_id']:str(uuid.uuid4()) for d in payload['documents']}
    for doc in payload['documents']:doc['document_id']=mapping[doc['document_id']]
    for chunk in payload['chunks']:
        chunk['document_id']=mapping[chunk['document_id']]
    # Fixture is an empty envelope before normalization.
    result,_=resolve_person_identity(payload,ROOT/'person.registry.sqlite')
    assert not [e for e in result['entities'] if e['entity_type']=='Person' and e['resolution_status']=='resolved']


def test_pipeline_preserves_resolved_ids_but_never_approves_relations():
    companies=json.loads((ROOT/'company.registry.json').read_text('utf-8'))
    result,audit=normalize_and_extract(fixture(),companies,person_store=ROOT/'person.registry.sqlite')
    assert audit['person_identity']['resolved_person_entities']>0
    assert result['relations'] and all(r['review']['status']=='PENDING' for r in result['relations'])


def test_missing_or_foreign_sqlite_is_rejected(tmp_path):
    with pytest.raises(FileNotFoundError):resolve_person_identity(fixture(),tmp_path/'missing.sqlite')
    path=tmp_path/'foreign.sqlite'
    with sqlite3.connect(path) as conn:conn.execute('CREATE TABLE unrelated(id integer)')
    with pytest.raises(ValueError,match='Unsupported'):resolve_person_identity(fixture(),path)
