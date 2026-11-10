import asyncio,copy,hashlib,importlib.util,sys
from pathlib import Path
import pytest
from src.graph_review.engine import IdentityRegistry
from src.graph_review.models import VerifiedSource

scripts=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(scripts))
spec=importlib.util.spec_from_file_location('person_live_intake',scripts/'intake_person_reviews.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

DOC='11111111-1111-1111-1111-111111111111'
CID='22222222-2222-2222-2222-222222222222'
registry=IdentityRegistry([dict(entity_id='company:fpt',entity_type='Company',canonical_name='FPT',
    aliases=['FPT'],ticker_aliases=['FPT'],identity_key='ticker:FPT',verified=True)])

def row():
    return dict(extraction_id='33333333-3333-3333-3333-333333333333',document_id=DOC,
        subject='Nguyễn Văn An',object='FPT',relation_type='HOLDS_ROLE',validation_status='SOURCE_VERIFIED',
        payload=None,content_sha256=None,subject_id='person:source-scoped',object_id='company:source-scoped',
        locator_json=dict(symbol='FPT',position='Giám đốc',year=2024,corpus_binding=dict(chunk_bindings=[dict(chunk_id=CID)])))

def reviewed():
    return dict(subject='Nguyễn Văn An',object='FPT',relation_type='HOLDS_ROLE',document_id=DOC,
        report_decision='APPROVED',review_body_sha256='a'*64,pdf_page=1)

class Reader:
    def __init__(self,header,document_id=DOC):self.header,self.document_id=header,document_id
    async def read_current(self,*args):
        text=self.header+'\nNguyễn Văn An là Giám đốc FPT.'
        return VerifiedSource(self.document_id,'a'*64,CID,module.CORPUS,module.INDEX,'b'*64,
            hashlib.sha256(text.encode()).hexdigest(),{},text)

def test_document_scoped_person_never_promoted_to_canonical():
    value=module.endpoint(row(),'subject',row()['locator_json'],registry)
    assert value['resolution_status']=='unresolved' and value['identity_key'] is None
    assert module.endpoint(row(),'object',row()['locator_json'],registry)['resolution_status']=='resolved'

def test_only_explicit_verified_source_mapping_resolves_person():
    person=dict(entity_id='person:verified-canonical-id',entity_type='Person',canonical_name='Nguyễn Văn An',
        aliases=['Nguyễn Văn An'],identity_key='verified:person:123',verified=True,
        source_entity_ids=['person:source-scoped'])
    resolved=module.endpoint(row(),'subject',row()['locator_json'],IdentityRegistry([person]))
    assert resolved['entity_id']==person['entity_id'] and resolved['resolution_status']=='resolved'
    person['verified']=False
    assert module.endpoint(row(),'subject',row()['locator_json'],IdentityRegistry([person]))['resolution_status']=='unresolved'

def test_report_year_is_not_fabricated_as_calendar_day():
    async def run():
        raw=await module.convert(None,reviewed(),row(),Reader('FPT | Báo cáo thường niên 2024'),registry)
        assert raw['temporal']==dict(as_of=None,valid_from=None,valid_to=None)
        assert raw['extractor_metadata']['original_report_year']==2024
    asyncio.run(run())

def test_snapshot_observation_does_not_become_effective_date():
    async def run():
        raw=await module.convert(None,reviewed(),row(),Reader('FPT | Snapshot 2026-10-29'),registry)
        assert raw['temporal']['as_of']=='2026-10-29' and raw['temporal']['valid_from'] is None
    asyncio.run(run())

def test_rejected_report_cannot_be_treated_as_approved():
    async def run():
        review=reviewed();review['report_decision']='REJECTED'
        raw=await module.convert(None,review,row(),Reader('FPT | Snapshot 2026-10-29'),registry)
        assert 'ERR_REPORT_REJECTED' in raw['extractor_metadata']['input_errors']
    asyncio.run(run())

def test_wrong_source_document_fails_before_persistence():
    async def run():
        with pytest.raises(ValueError,match='membership'):
            await module.convert(None,reviewed(),row(),Reader('FPT','wrong-document'),registry)
    asyncio.run(run())

def test_legacy_rejection_is_terminal_before_any_insert():
    from src.person_role.metadata_repository import GraphMetadataRepository,MetadataConflict
    class Repository(GraphMetadataRepository):
        async def read_assertion(self,*args):
            return dict(review_status='REJECTED',payload={})
    async def run():
        for decision in ('APPROVED','PENDING','QUARANTINED'):
            with pytest.raises(MetadataConflict,match='terminal'):
                await Repository(None).record_review('not-used',decision,'TEST','No insert allowed')
    asyncio.run(run())
