import asyncio,copy,json,hashlib
from pathlib import Path
import pytest
from src.graph_temporal import bounds,validate_temporal,month_supported
from src.sprint4_runtime.contracts import validate_envelope
from src.graph.sprint4_store import prepare_batch
from src.graph_review.engine import ReviewEngine,IdentityRegistry
from src.graph_review.models import VerifiedSource
from src.graph_review.sources import FixtureSourceReader
from src.graph_review.repository import PostgresReviewStore


def payload():
    value=json.loads((Path(__file__).parent/'fixtures/wbs08_graph_contract.json').read_text('utf-8'))
    value['schema_version']='2.2.0'
    for r in value['relations']:
        r['temporal']=dict(as_of=None,valid_from='2024-04',valid_to=None,valid_from_precision='month')
    return value


def test_month_contract_and_projection_preserve_claim_without_fake_day():
    value=payload();validate_envelope(value)
    prepared=prepare_batch(value,'month-fixture','fixture')
    assert prepared['relations']
    for r in prepared['relations']:
        assert r['properties']['valid_from']=='2024-04'
        assert r['properties']['valid_from_precision']=='month'
        assert r['properties']['valid_from_lower']=='2024-04-01'
        assert r['properties']['valid_from_upper']=='2024-04-30'


@pytest.mark.parametrize('change',[
    {'valid_from':'2024-13'}, {'valid_from':'2024-04-01'},
    {'valid_from_precision':'year'}, {'valid_from':None},
    {'valid_to':'2024-03','valid_to_precision':'month'},
])
def test_invalid_month_precision_or_interval_rejected(change):
    value=payload();value['relations'][0]['temporal'].update(change)
    with pytest.raises(ValueError):validate_envelope(value)


def test_old_contract_cannot_silently_accept_months():
    for version in ('2.0.0','2.1.0'):
        value=payload();value['schema_version']=version
        with pytest.raises(ValueError):validate_envelope(value)
    value=payload();del value['relations'][0]['temporal']['valid_from_precision']
    with pytest.raises(ValueError):validate_envelope(value)


def test_source_month_match_does_not_turn_day_or_year_into_month():
    assert month_supported('2024-04','từ tháng 4/2024')
    assert month_supported('2024-04','từ tháng 4 năm 2024')
    assert not month_supported('2024-04','ngày 15/04/2024')
    assert not month_supported('2024-04','năm 2024')
    assert bounds('2024-02','month')==('2024-02-01','2024-02-29')


def test_wbs06_requires_matching_month_evidence():
    text='Ông Nguyễn Văn An là Giám đốc FPT từ tháng 4/2024.'
    h=hashlib.sha256(text.encode()).hexdigest()
    source=VerifiedSource('d','v','c','corpus','index','a'*64,h,{},text,verification_mode='FIXTURE')
    person=dict(entity_id='p',entity_type='Person',canonical_name='Nguyễn Văn An',aliases=[],identity_key='p',verified=True)
    company=dict(entity_id='fpt',entity_type='Company',canonical_name='FPT',aliases=[],identity_key='fpt',verified=True)
    def endpoint(e):return {k:v for k,v in e.items() if k!='verified'}|dict(resolution_status='resolved')
    raw=dict(candidate_id='fixture-month',group='person',relation_type='HOLDS_ROLE',subject=endpoint(person),object=endpoint(company),
        attributes=dict(position='Giám đốc'),temporal=dict(as_of=None,valid_from='2024-04',valid_to=None,valid_from_precision='month'),
        extractor_metadata=dict(envelope_schema_version='2.2.0'),
        evidence=[dict(document_id='d',document_version='v',chunk_id='c',corpus_id='corpus',index_version_id='index',
                       source_sha256='a'*64,content_hash=h,locator={},quote=text)])
    engine=ReviewEngine(FixtureSourceReader([source]),IdentityRegistry([person,company]))
    result=asyncio.run(engine.evaluate(raw));assert result.status=='APPROVED' and not result.load_allowed
    raw['temporal']['valid_from']='2024-05'
    assert 'ERR_FACT_UNSUPPORTED' in asyncio.run(engine.evaluate(raw)).reasons


def test_reviewer_updates_existing_quarantine_without_insert_privilege():
    class Connection:
        async def execute(self,sql,*args):
            assert sql.lstrip().startswith('UPDATE public.quarantine_records')
            return 'UPDATE 1'
    from types import SimpleNamespace
    import uuid
    asyncio.run(PostgresReviewStore(Connection())._quarantine(
        dict(review_id=str(uuid.uuid4()),result=dict(status='APPROVED',reasons=[])),
        SimpleNamespace(user_id=uuid.uuid4()),update=True))
