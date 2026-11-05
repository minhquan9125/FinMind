"""Enrichment is a new pending proposal, never an approval or source rewrite."""
from copy import deepcopy
import asyncio

import pytest

from backend.tests.test_wbs03_ownership_tables import run, REGISTRY
from backend.scripts.prepare_rejected_proposals import enrich_proposal, diagnose


def original():
    return run({3: ['(i) Công ty con trực tiếp\nTại ngày 31/12/2025\nTỷ lệ sở hữu\n'
                    'Công ty TNHH Phần mềm Alpha Cung cấp phần mềm 100%']})[2]


def proof(payload, text='Các công ty con do Tập đoàn kiểm soát.'):
    chunk = deepcopy(payload['chunks'][0])
    chunk.update(chunk_id='policy', text=text)
    chunk['locator'].update(block_id='policy', page=4)
    return chunk


def test_enrichment_preserves_original_claim_and_stays_pending():
    payload = original()
    before = deepcopy(payload)
    proposal = enrich_proposal(payload, [proof(payload)], 'consolidation_basis', 'kiểm soát')
    assert payload == before
    old, new = payload['relations'][0], proposal['relations'][0]
    assert new['relation_id'] != old['relation_id']
    assert new['review'] == {'status': 'PENDING', 'reviewer': None, 'reviewed_at': None}
    for key in ('subject_id', 'object_id', 'relation_type', 'temporal'):
        assert new[key] == old[key]
    assert new['attributes']['ownership_percent'] == old['attributes']['ownership_percent']
    assert new['attributes']['consolidation_basis'] == 'kiểm soát'
    assert new['evidence'][-1]['quote'] == proof(payload)['text']
    assert enrich_proposal(payload, [proof(payload)], 'consolidation_basis', 'kiểm soát') == proposal


@pytest.mark.parametrize('problem', ['other_document', 'other_version', 'same_id_conflict', 'no_basis'])
def test_unbound_or_missing_basis_is_refused(problem):
    payload = original()
    chunk = proof(payload)
    if problem == 'other_document':
        chunk['document_id'] = 'doc:' + 'c' * 64
    elif problem == 'other_version':
        chunk['document_version'] = 'c' * 64
    elif problem == 'same_id_conflict':
        chunk['chunk_id'] = payload['chunks'][0]['chunk_id']
    else:
        chunk['text'] = 'Không có thông tin.'
    with pytest.raises(ValueError):
        enrich_proposal(payload, [chunk], 'consolidation_basis', 'kiểm soát')


def test_wrong_relation_basis_and_approved_input_are_refused():
    payload = original()
    with pytest.raises(ValueError):
        enrich_proposal(payload, [proof(payload)], 'accounting_basis', 'kiểm soát')
    payload['relations'][0]['review']['status'] = 'APPROVED'
    with pytest.raises(ValueError):
        enrich_proposal(payload, [proof(payload)], 'consolidation_basis', 'kiểm soát')


def joint_venture():
    payload = run({3: ['Công ty liên doanh\nTại ngày 31/12/2025\nTỷ lệ sở hữu\n'
                       'Công ty TNHH Phần mềm Alpha Cung cấp phần mềm 50%']})[2]
    return enrich_proposal(payload, [proof(payload, 'Liên doanh dùng phương pháp vốn chủ sở hữu.')],
                           'accounting_basis', 'phương pháp vốn chủ sở hữu')


def test_grounded_joint_venture_label_is_checked_but_does_not_approve_table():
    result = asyncio.run(diagnose(joint_venture(), REGISTRY))
    assert result['status'] == 'PENDING'
    assert 'WARN_UNCHECKED_ATTRIBUTE' not in result['reasons']
    assert 'WARN_EVIDENCE_INSUFFICIENT' in result['reasons']
    assert result['verification_mode'] == 'FIXTURE'


@pytest.mark.parametrize('label', ['công ty liên kết', 'công ty con', 123, None])
def test_unsupported_or_wrong_label_is_rejected(label):
    payload = joint_venture()
    payload['relations'][0]['attributes']['relation_label'] = label
    result = asyncio.run(diagnose(payload, REGISTRY))
    assert result['status'] == 'REJECTED'
