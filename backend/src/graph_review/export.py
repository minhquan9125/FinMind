"""Revalidate attributed review records and export PDF/NEWS without locator rewriting."""
import json,uuid
from .models import Evidence
from .sources import compare_source
from ..documents.shared_source import read_release_root
from ..sprint4_runtime.contracts import validate_envelope
from ..sprint4_runtime.news_contract import is_news_locator

async def make_envelope(c,records,reader):
    documents={};chunks={};entities={};relations=[];root_cache={};scope=None
    for record in records:
        raw=record['candidate']
        attribution=await c.fetchrow('SELECT reviewed_by,reviewed_at FROM graph_review_results WHERE review_id=$1',uuid.UUID(record['review_id']))
        if not attribution or not attribution['reviewed_by'] or not attribution['reviewed_at']:
            raise ValueError('APPROVAL_ATTRIBUTION_MISSING')
        for endpoint in (raw['subject'],raw['object']):
            value={**endpoint,'attributes':{}}
            old=entities.setdefault(value['entity_id'],value)
            if old!=value:raise ValueError('APPROVED_ENTITY_IDENTITY_CONFLICT')
        evidence=[]
        for ref in raw['evidence']:
            current=await reader.read_current(ref['chunk_id'],ref['corpus_id'])
            if not is_news_locator(current.locator) and (current.locator.get('kind')!='db_text_span' or type(current.locator.get('page')) is not int):
                raise ValueError('SOURCE_PROFILE_NOT_SUPPORTED_BY_ENVELOPE_2_1_NO_FAKE_PDF_PAGE')
            compare_source(Evidence.model_validate(ref),current)
            pair=(current.corpus_id,current.index_version_id)
            if scope is None:scope=pair
            if scope!=pair:raise ValueError('APPROVED_RECORDS_MIX_CORPUS_INDEX')
            original=await c.fetchval('SELECT locator_json FROM text_chunks WHERE chunk_id=$1',uuid.UUID(current.chunk_id))
            original=json.loads(original) if isinstance(original,str) else original
            root=await read_release_root(c,current.index_version_id,root_cache)
            member=next(m for m in root['sources'] if m['source_table']==original['source_table'] and m['source_id']==original['source_id'])
            doc=dict(source_kind='db',document_id=current.document_id,document_version=current.document_version,
                source_uri=member['source_uri'],source_sha256=current.source_sha256,index_version_id=current.index_version_id)
            if documents.setdefault(current.document_id,doc)!=doc:raise ValueError('DOCUMENT_VERSION_CONFLICT')
            chunk=dict(document_id=current.document_id,document_version=current.document_version,chunk_id=current.chunk_id,
                text=current.text,locator=current.locator)
            key=(current.document_id,current.chunk_id)
            if chunks.setdefault(key,chunk)!=chunk:raise ValueError('CHUNK_VERSION_CONFLICT')
            evidence.append(dict(document_id=ref['document_id'],chunk_id=ref['chunk_id'],quote=ref['quote']))
        relations.append(dict(relation_id=raw['candidate_id'],subject_id=raw['subject']['entity_id'],object_id=raw['object']['entity_id'],
            relation_type=raw['relation_type'],attributes=raw['attributes'],temporal=raw['temporal'],evidence=evidence,
            review=dict(status='APPROVED',reviewer=str(attribution['reviewed_by']),reviewed_at=attribution['reviewed_at'].isoformat())))
    if not scope:raise ValueError('NO_APPROVED_SOURCE_SCOPE')
    version=('2.3.0' if any(is_news_locator(ch['locator']) for ch in chunks.values()) else
             '2.2.0' if any(k.endswith('_precision') for r in relations for k in r['temporal']) else '2.1.0')
    return validate_envelope(dict(schema_version=version,corpus_id=scope[0],dataset_version=scope[1],
        documents=list(documents.values()),chunks=list(chunks.values()),entities=list(entities.values()),mentions=[],relations=relations))
