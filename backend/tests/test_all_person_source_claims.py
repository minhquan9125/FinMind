"""Synthetic fixtures only; no real source review or publication is fabricated."""
import asyncio,copy,hashlib,uuid
import pytest
from src.person_role.source_claim_repairs import repair_claim
from src.graph.source_person_claims import prepare_claim_batch,verify_live_claim_sources,SourcePersonClaimStore
from src.graph_review.models import VerifiedSource
from src.graph_review.sources import PostgresSourceReader


def case():
    records=[];manifest=[]
    for i in range(185):
        xid=str(uuid.uuid5(uuid.NAMESPACE_URL,'SYNTHETIC-CLAIM-'+str(i)))
        body=f'Ông Person{i} Giám đốc FPT.';text='SYNTHETIC FIXTURE ONLY\n'+body
        h=hashlib.sha256(text.encode()).hexdigest()
        source=dict(document_id='d',document_version='a'*64,chunk_id='chunk'+str(i),corpus_id='fixture',index_version_id='index',
            content_hash=h,source_sha256='a'*64,locator={},text=text)
        records.append(dict(extraction_id=xid,subject='Person'+str(i),object='FPT',symbol='FPT',relation_type='HOLDS_ROLE',position='Giám đốc',
            report_year=None,source_url='fixture://synthetic',review_body_sha256='b'*64,live_verified_chunks=[source],
            checks=dict(has_live_source=True,all_source_reads_passed=True,exact_person_name_present=True)))
        manifest.append(dict(extraction_id=xid,report_decision='APPROVED',review_body_sha256='b'*64))
    names=[r['subject'] for r in records]
    repairs=dict(records=[repair_claim(r,names) for r in records])
    return repairs,dict(records=records),dict(records=manifest,report_sha256='c'*64)


def test_all_185_are_retained_as_scoped_claims_without_invented_dates_or_global_ids():
    batch=prepare_claim_batch(*case())
    assert len(batch['relations'])==185 and len(batch['people'])==185
    assert all(not p['global_identity_resolved'] for p in batch['people'])
    assert all(not r['properties']['calendar_date_asserted'] for r in batch['relations'])
    assert all(r['properties']['time_scope']=='SOURCE_DOCUMENT_NOT_CURRENT_OFFICE' for r in batch['relations'])
    assert len({p['key'] for p in batch['people']})==185


def test_missing_or_unrepaired_record_prevents_whole_batch_publication():
    repairs,audit,manifest=case();repairs['records'].pop()
    with pytest.raises(ValueError,match='185-record'):prepare_claim_batch(repairs,audit,manifest)
    repairs,audit,manifest=case();repairs['records'][0]['repair_status']='UNRESOLVED'
    with pytest.raises(ValueError,match='Unrepaired'):prepare_claim_batch(repairs,audit,manifest)


def test_changed_role_and_unapproved_report_cannot_publish():
    repairs,audit,manifest=case();repairs['records'][0]['position']='Chủ tịch'
    with pytest.raises(ValueError,match='derivation'):prepare_claim_batch(repairs,audit,manifest)
    repairs,audit,manifest=case();manifest['records'][0]['report_decision']='REJECTED'
    with pytest.raises(ValueError,match='185-record'):prepare_claim_batch(repairs,audit,manifest)


def test_fixture_sources_cannot_authorize_production_source_graph():
    repairs,audit,manifest=case();batch=prepare_claim_batch(repairs,audit,manifest)
    sources={s['chunk_id']:s for r in audit['records'] for s in r['live_verified_chunks']}
    class Reader:
        async def prefetch(self,*args):pass
        async def read_current(self,chunk_id,corpus_id):
            row=sources[chunk_id]
            return VerifiedSource(**{k:v for k,v in row.items() if k!='text'},text=row['text'],verification_mode='FIXTURE')
    with pytest.raises(ValueError,match='Live current'):asyncio.run(verify_live_claim_sources(batch,Reader()))


def test_prefetch_is_membership_only_and_does_not_bless_inactive_source():
    cid=str(uuid.uuid4());corpus=str(uuid.uuid4())
    class Connection:
        async def fetch(self,sql,*args):
            assert 't.*' not in sql and 'embedding' not in sql
            return [dict(chunk_id=cid,superseded_at=None,index_status='INACTIVE',corpus_status='FROZEN')]
    async def run():
        reader=PostgresSourceReader(Connection());await reader.prefetch([cid],corpus)
        from src.graph_review.models import SourceProblem
        with pytest.raises(SourceProblem,match='INACTIVE'):await reader.read_current(cid,corpus)
    asyncio.run(run())


def test_writer_reconciles_every_property_and_returns_version_status():
    batch=prepare_claim_batch(*case())
    class Result(list):
        def single(self,strict=False):return self[0]
        def consume(self):pass
    class Transaction:
        def run(self,sql,**params):
            if 'RETURN v.payload_sha256' in sql:return Result([dict(sha=batch['payload_sha256'],status='BUILDING')])
            if 'RETURN r.origin_extraction_id' in sql:
                return Result([dict(id=r['properties']['origin_extraction_id'],data=r['properties'],person_key=r['person_key'],
                    company_key=r['company_key'],subject_key=r['person_key'],
                    person_name=next(p['name'] for p in batch['people'] if p['key']==r['person_key']),company_symbol='FPT') for r in batch['relations']])
            if 'MERGE (p)-[r:SOURCE_PERSON_CLAIM' in sql:
                assert len(params['rows'])==185
            return Result()
    receipt=SourcePersonClaimStore._write(Transaction(),batch)
    assert receipt['claims']==185 and not receipt['idempotent_replay']
