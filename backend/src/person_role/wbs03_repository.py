"""Contract 2.1.0 DB-source intake with live pinned-source verification.

Supports registered annual DB chunks. Offline PDF/bbox or pageless inputs must
use a separate source adapter; never synthesize a PDF page for those inputs.
"""
import json,uuid
from .contract.contracts import validate_envelope
from .metadata_repository import digest,MetadataConflict
from src.documents.annual_source_reader import read_annual_chunk
from src.documents.shared_source import read_release_root

NS=uuid.UUID('21870190-e3a3-48c9-ac23-b0d51c6fa94f')
def entity_label(entity):
 """A display label only; never mark an unresolved entity as canonical."""
 return entity.get('canonical_name') or next(iter(entity.get('aliases',[])),entity['entity_id'])

async def build_db_envelope(connection,corpus_id,chunk_ids,cache=None):
 corpus_id=str(uuid.UUID(str(corpus_id)));cache={} if cache is None else cache;documents={};chunks=[]
 for chunk_id in dict.fromkeys(chunk_ids):
  r=await read_annual_chunk(connection,chunk_id,corpus_id,cache)
  loc=r['locator'];meta=loc['reconstruction'];iid=r['index_version_id']
  root=await read_release_root(connection,iid,cache)
  member=next(m for m in root['sources'] if m['source_table']==loc['source_table'] and m['source_id']==loc['source_id'])
  doc=dict(source_kind='db',document_id=r['document_id'],document_version=meta['source_view_sha256'],source_uri=member['source_uri'],
   source_sha256=member['sha256'],index_version_id=iid,title=r['title'],doc_type='ANNUAL_REPORT')
  if r['document_id'] in documents and documents[r['document_id']]!=doc:raise ValueError('Document has inconsistent source versions; split envelopes by source view')
  documents[r['document_id']]=doc
  text=r['chunk_text'];header,sep,_=text.partition('\n')
  chunks.append(dict(document_id=r['document_id'],document_version=doc['document_version'],chunk_id=r['chunk_id'],text=text,
   locator=dict(kind='db_text_span',page=r['pdf_page'],section_index=meta['section_index'],char_start=meta['char_start'],char_end=meta['char_end'],
    text_start=len(header)+len(sep),offset_basis='normalized_section_body',offset_unit='unicode_codepoint',content_hash=r['content_hash'])))
 if not chunks:raise ValueError('At least one registered chunk required')
 result=dict(schema_version='2.1.0',corpus_id=corpus_id,dataset_version=iid,documents=list(documents.values()),chunks=chunks,entities=[],mentions=[],relations=[])
 return validate_envelope(result)

class WBS03Repository:
 def __init__(self,connection):self.c=connection;self.cache={}

 async def verify_sources(self,payload):
  validate_envelope(payload)
  if payload['schema_version']!='2.1.0' or any(d.get('source_kind')!='db' for d in payload['documents']):raise ValueError('Only contract 2.1.0 registered DB annual sources supported')
  # Do not silently accept unused documents or unverifiable empty source batches.
  actual=await build_db_envelope(self.c,payload['corpus_id'],[ch['chunk_id'] for ch in payload['chunks']],self.cache)
  if actual['dataset_version']!=payload['dataset_version']:raise ValueError('Index version mismatch')
  docs={d['document_id']:d for d in actual['documents']}
  if set(docs)!={d['document_id'] for d in payload['documents']}:raise ValueError('Document membership mismatch')
  for d in payload['documents']:
   for field in ('source_kind','document_id','document_version','source_uri','source_sha256','index_version_id'):
    if d.get(field)!=docs[d['document_id']][field]:raise ValueError('Document source mismatch: '+field)
  chunks={(ch['document_id'],ch['chunk_id']):ch for ch in actual['chunks']}
  for ch in payload['chunks']:
   if chunks.get((ch['document_id'],ch['chunk_id']))!=ch:raise ValueError('Pinned chunk text/locator mismatch')
  return actual

 async def save(self,payload):
  """Atomic immutable draft; reruns return identical IDs, never APPROVED."""
  validate_envelope(payload)
  if any(r['review']['status']!='PENDING' for r in payload['relations']):raise ValueError('Intake accepts PENDING only; review is a separate authorized step')
  checksum=digest(payload);gid=uuid.uuid5(NS,checksum)
  async with self.c.transaction(isolation=None if self.c.is_in_transaction() else 'repeatable_read'):
   await self.verify_sources(payload)
   await self.c.execute("INSERT INTO graph_versions(graph_version_id,built_at,node_count,edge_count,status) VALUES($1,now(),$2,$3,'EXTRACTED_PENDING') ON CONFLICT DO NOTHING",gid,len(payload['entities']),len(payload['relations']))
   await self.c.execute('''INSERT INTO graph_metadata.wbs03_envelopes(graph_version_id,corpus_version_id,index_version_id,schema_version,content_sha256,payload)
    VALUES($1,$2,$3,'2.1.0',$4,$5::jsonb) ON CONFLICT DO NOTHING''',gid,uuid.UUID(payload['corpus_id']),uuid.UUID(payload['dataset_version']),checksum,json.dumps(payload,ensure_ascii=False))
   stored=await self.read(gid)
   if stored!=payload:raise MetadataConflict('Envelope identity conflict')
   entities={e['entity_id']:e for e in payload['entities']};chunks={(ch['document_id'],ch['chunk_id']):ch for ch in payload['chunks']}
   for r in payload['relations']:
    xid=uuid.uuid5(gid,'relation:'+r['relation_id']);first=r['evidence'][0]
    subject=entity_label(entities[r['subject_id']]);object_=entity_label(entities[r['object_id']])
    span='\n'.join(e['quote'] for e in r['evidence'])
    await self.c.execute('''INSERT INTO graph_extractions(extraction_id,graph_version_id,document_id,method,subject,relation_type,object,source_span,validation_status,manual_check)
     VALUES($1,$2,$3,'WBS03',$4,$5,$6,$7,'CONTRACT_VALIDATED','PENDING') ON CONFLICT DO NOTHING''',xid,gid,uuid.UUID(first['document_id']),subject,r['relation_type'],object_,span)
    row=await self.c.fetchrow('SELECT graph_version_id,document_id,subject,relation_type,object,source_span,validation_status,manual_check FROM graph_extractions WHERE extraction_id=$1',xid)
    assert tuple(row)==(gid,uuid.UUID(first['document_id']),subject,r['relation_type'],object_,span,'CONTRACT_VALIDATED','PENDING')
    for i,ev in enumerate(r['evidence']):
     eid=uuid.uuid5(xid,'evidence:'+str(i));ch=chunks[(ev['document_id'],ev['chunk_id'])]
     d=next(d for d in payload['documents'] if d['document_id']==ev['document_id'])
     origin=await self.c.fetchrow('SELECT company_id,period_id,source_url FROM documents WHERE document_id=$1',uuid.UUID(ev['document_id']))
     locator=dict(kind='wbs03_db_contract',envelope_schema_version='2.1.0',relation_id=r['relation_id'],subject_id=r['subject_id'],object_id=r['object_id'],
      evidence=ev,locator=ch['locator'],attributes=r['attributes'],temporal=r['temporal'],review=r['review'],
      source_url=origin['source_url'],page=ch['locator']['page'],
      corpus_binding=dict(graph_version_id=str(gid),corpus_version_id=payload['corpus_id'],index_version_id=payload['dataset_version'],document_id=ev['document_id'],chunk_id=ev['chunk_id'],content_hash=ch['locator']['content_hash']))
     await self.c.execute('''INSERT INTO evidence(evidence_id,evidence_type,chunk_id,extraction_id,source_sha256,locator_json,company_id,period_id,created_at)
      VALUES($1,'GRAPH',$2,$3,$4,$5::jsonb,$6,$7,now()) ON CONFLICT DO NOTHING''',eid,uuid.UUID(ev['chunk_id']),xid,d['source_sha256'],json.dumps(locator,ensure_ascii=False),origin['company_id'],origin['period_id'])
     actual=await self.c.fetchrow('SELECT extraction_id,chunk_id,source_sha256,locator_json FROM evidence WHERE evidence_id=$1',eid)
     if actual['extraction_id']!=xid or str(actual['chunk_id'])!=ev['chunk_id'] or actual['source_sha256'].strip()!=d['source_sha256'] or json.loads(actual['locator_json'])!=locator:raise MetadataConflict('Evidence identity conflict')
   n=await self.c.fetchval('SELECT count(*) FROM graph_extractions WHERE graph_version_id=$1',gid)
   if n!=len(payload['relations']):raise MetadataConflict('Extraction count mismatch')
  return dict(graph_version_id=str(gid),envelope_sha256=checksum,relations=len(payload['relations']),chunks=len(payload['chunks']),status='EXTRACTED_PENDING')

 async def read(self,graph_version_id):
  row=await self.c.fetchrow('SELECT content_sha256,payload FROM graph_metadata.wbs03_envelopes WHERE graph_version_id=$1',uuid.UUID(str(graph_version_id)))
  if row is None:return None
  payload=json.loads(row['payload']);validate_envelope(payload)
  if digest(payload)!=row['content_sha256']:raise MetadataConflict('Envelope hash mismatch')
  return payload
