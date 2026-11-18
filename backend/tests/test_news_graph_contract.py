"""NEWS is source-bound without a PDF page; old PDF contracts remain strict."""
import asyncio,copy,hashlib,uuid
from datetime import datetime,timezone
from types import SimpleNamespace
import pytest
from src.sprint4_runtime.contracts import validate_envelope
from src.graph.sprint4_store import prepare_batch
from src.graph_review.adapters import from_envelope
from src.graph_review.models import Evidence,VerifiedSource
from src.graph_review.sources import compare_source,SourceProblem

def payload():
    doc,chunk,corpus,index,article=[str(uuid.uuid4()) for _ in range(5)]
    text='Tin nguồn | 2026-10-24\nAlpha và Beta đồng tài trợ dự án ngày 23/10/2026.'
    hashed=hashlib.sha256(text.encode()).hexdigest()
    locator=dict(source_table='news_articles',source_id=article,doc_type='NEWS',url='https://example.org/news',
        reconstruction=dict(schema_version='source-locator-v2',chunker_version='db-v1',
            document_id=str(uuid.uuid4()),source_chunk_id=str(uuid.uuid4()),section_index=0,
            row_start=0,row_end=1,char_start=0,char_end=50,chunk_index=0,
            content_hash=hashed,source_view_sha256='b'*64))
    return dict(schema_version='2.3.0',corpus_id=corpus,dataset_version=index,
        documents=[dict(source_kind='db',document_id=doc,document_version='a'*64,source_uri='finmind:news:'+article,
                        source_sha256='a'*64,index_version_id=index)],
        chunks=[dict(document_id=doc,document_version='a'*64,chunk_id=chunk,text=text,locator=locator)],
        entities=[dict(entity_id=n,entity_type='Company',canonical_name=n.title(),identity_key=n,
                       resolution_status='resolved',aliases=[],attributes={}) for n in ('alpha','beta')],mentions=[],
        relations=[dict(relation_id='news-proof',subject_id='alpha',object_id='beta',relation_type='COOPERATES_WITH',
            attributes={'cooperation_scope':'đồng tài trợ'},temporal=dict(as_of='2026-10-23',valid_from=None,valid_to=None),
            evidence=[dict(document_id=doc,chunk_id=chunk,quote='Alpha và Beta đồng tài trợ dự án ngày 23/10/2026.')],
            review=dict(status='APPROVED',reviewer=str(uuid.uuid4()),reviewed_at=datetime.now(timezone.utc).isoformat()))])

def test_news_roundtrip_preserves_original_locator_quote_hash_and_release_alias():
    value=payload();before=copy.deepcopy(value)
    validate_envelope(value)
    prepared=prepare_batch(value,str(uuid.uuid4()),'news-batch')
    assert prepared and value==before
    candidate=from_envelope(value)[0]
    ref=Evidence.model_validate(candidate['evidence'][0])
    source=VerifiedSource(**{k:v for k,v in ref.model_dump().items() if k!='quote'},text=value['chunks'][0]['text'])
    compare_source(ref,source)
    assert ref.locator==before['chunks'][0]['locator']
    assert 'page' not in ref.locator
    assert ref.document_id!=ref.locator['reconstruction']['document_id']
    assert not candidate['extractor_metadata']['input_errors']

@pytest.mark.parametrize('version',['2.0.0','2.1.0','2.2.0'])
def test_news_cannot_silently_enter_an_old_pdf_contract(version):
    value=payload();value['schema_version']=version
    with pytest.raises(ValueError):validate_envelope(value)

@pytest.mark.parametrize('change',[
    lambda v:v['chunks'][0]['locator'].update(page=1),
    lambda v:v['chunks'][0]['locator'].update(source_table='annual_reports'),
    lambda v:v['chunks'][0]['locator'].update(url='file:///private'),
    lambda v:v['chunks'][0]['locator'].update(url='https://user:secret@example.org'),
    lambda v:v['chunks'][0]['locator']['reconstruction'].update(content_hash='c'*64),
    lambda v:v['chunks'][0]['locator']['reconstruction'].update(char_end=0),
    lambda v:v['chunks'][0].update(text='Changed source'),
    lambda v:v['relations'][0]['evidence'][0].update(quote='Invented cooperation'),
])
def test_invalid_news_evidence_cannot_be_exported(change):
    value=payload();change(value)
    with pytest.raises(ValueError):validate_envelope(value)

def test_valid_shape_does_not_replace_live_locator_verification():
    value=payload();candidate=from_envelope(value)[0]
    ref=Evidence.model_validate(candidate['evidence'][0])
    source=VerifiedSource(**{k:v for k,v in ref.model_dump().items() if k!='quote'},text=value['chunks'][0]['text'])
    changed=ref.model_copy(deep=True);changed.locator['url']='https://example.org/another'
    with pytest.raises(SourceProblem):compare_source(changed,source)
