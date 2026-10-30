"""PostgreSQL metadata sidecar for source-bound person-role assertions.

Metadata schema 1.0.0 is independent of extraction contract and graph UUID.
Does not promote AI source verification to human APPROVED or publish Neo4j.
"""
import hashlib,json,uuid
from datetime import datetime,timezone

def digest(value):
 return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

class MetadataConflict(ValueError): pass

class GraphMetadataRepository:
 def __init__(self,connection): self.c=connection

 async def _immutable_insert(self,table,key,payload):
  # Tables and identifiers are internal constants; values are always bound.
  columns=list(payload)
  values=[json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for v in payload.values()]
  placeholders=[f'${i+1}::jsonb' if isinstance(v,(dict,list)) else f'${i+1}' for i,v in enumerate(payload.values())]
  await self.c.execute(f"INSERT INTO graph_metadata.{table} ({','.join(columns)}) VALUES({','.join(placeholders)}) ON CONFLICT DO NOTHING",*values)
  clause=' AND '.join(f'{col}=${i+1}' for i,col in enumerate(key))
  row=await self.c.fetchrow(f'SELECT * FROM graph_metadata.{table} WHERE {clause}',*[payload[k] for k in key])
  if row is None: raise MetadataConflict('Identity not found after insert')
  for col,value in payload.items():
   actual=row[col]
   if isinstance(value,(dict,list)): actual=json.loads(actual) if isinstance(actual,str) else actual
   if actual!=value: raise MetadataConflict(f'Immutable {table} identity conflict: {col}')

 async def register_version(self,graph_id,corpus_id,index_id,manifest_hash,provenance,extraction_contract_version):
  await self._immutable_insert('versions',['graph_version_id'],dict(graph_version_id=uuid.UUID(str(graph_id)),corpus_version_id=uuid.UUID(str(corpus_id)),
   index_version_id=uuid.UUID(str(index_id)),metadata_schema_version='1.0.0',extraction_contract_version=extraction_contract_version,
   manifest_sha256=manifest_hash,provenance=provenance))

 async def put_assertion(self,graph_id,extraction_id,subject,object_,payload,bindings):
  """Caller uses a transaction: no partial entities/assertion/source rows on failure."""
  gid=uuid.UUID(str(graph_id));xid=uuid.UUID(str(extraction_id))
  relation=payload['relation_type']
  expected=('Company','Person') if relation in ('APPOINTS','DISMISSES') else ('Person','Company')
  if relation not in ('HOLDS_ROLE','FORMER_ROLE','RESIGNS','REQUESTS_RESIGNATION','APPOINTS','DISMISSES') or (subject['entity_type'],object_['entity_type'])!=expected:
   raise ValueError(f'Unsupported relation/direction: {relation}/{subject["entity_type"]}/{object_["entity_type"]}')
  if not bindings: raise ValueError('Source chunks required')
  if not payload.get('position') or not payload.get('original_source_document_id'): raise ValueError('Missing position/source identity')
  if payload.get('validation_status') not in ('SOURCE_VERIFIED','FUTURE_EFFECTIVE','SOURCE_CONFLICT'): raise ValueError('Unknown source validation status')
  if payload.get('review_status','PENDING')!='PENDING': raise ValueError('Review must be recorded separately')
  async with self.c.transaction():
   for entity in (subject,object_):
    await self._immutable_insert('entities',['graph_version_id','entity_id'],dict(graph_version_id=gid,entity_id=uuid.UUID(str(entity['entity_id'])),
     entity_type=entity['entity_type'],canonical_name=entity['canonical_name'],resolution_status=entity['resolution_status'],attributes=entity['attributes']))
   await self._immutable_insert('assertions',['extraction_id'],dict(extraction_id=xid,graph_version_id=gid,subject_id=uuid.UUID(str(subject['entity_id'])),
    object_id=uuid.UUID(str(object_['entity_id'])),relation_type=relation,content_sha256=digest(payload),payload=payload))
   expected={uuid.UUID(b['chunk_id']):b['content_hash'] for b in bindings}
   await self.c.executemany('INSERT INTO graph_metadata.source_chunks(graph_version_id,extraction_id,chunk_id,content_hash) VALUES($1,$2,$3,$4) ON CONFLICT DO NOTHING',
    [(gid,xid,k,v) for k,v in expected.items()])
   actual={r['chunk_id']:r['content_hash'] for r in await self.c.fetch('SELECT chunk_id,content_hash FROM graph_metadata.source_chunks WHERE extraction_id=$1',xid)}
   if actual!=expected:raise MetadataConflict('Immutable source bindings conflict')

 async def read_assertion(self,extraction_id):
  row=await self.c.fetchrow('SELECT * FROM graph_metadata.assertions WHERE extraction_id=$1',uuid.UUID(str(extraction_id)))
  if row is None:return None
  result=dict(row);payload=json.loads(row['payload']);
  if digest(payload)!=row['content_sha256']:raise MetadataConflict('Stored payload hash mismatch')
  result['payload']=payload
  sources=await self.c.fetch('''SELECT s.chunk_id,s.content_hash,t.content_hash AS actual_hash,
    (t.index_version_id=v.index_version_id AND t.document_id=g.document_id AND t.superseded_at IS NULL
     AND EXISTS(SELECT FROM public.corpus_documents cd WHERE cd.corpus_version_id=v.corpus_version_id AND cd.document_id=t.document_id)) AS valid
    FROM graph_metadata.source_chunks s JOIN graph_metadata.versions v USING(graph_version_id)
    JOIN public.graph_extractions g USING(extraction_id)
    LEFT JOIN public.text_chunks t ON t.chunk_id=s.chunk_id
    WHERE s.extraction_id=$1 ORDER BY s.chunk_id''',row['extraction_id'])
  if not sources or any(not s['valid'] or s['actual_hash'].strip()!=s['content_hash'] for s in sources):raise MetadataConflict('Source membership/hash changed')
  result['sources']=[dict(chunk_id=s['chunk_id'],content_hash=s['content_hash']) for s in sources]
  result['reviews']=[dict(r) for r in await self.c.fetch('SELECT * FROM graph_metadata.reviews WHERE extraction_id=$1 ORDER BY created_at,review_id',row['extraction_id'])]
  result['review_status']=result['reviews'][-1]['decision'] if result['reviews'] else 'PENDING'
  return result

 async def record_review(self,extraction_id,decision,reason_code,note,review_id=None):
  if decision not in ('PENDING','APPROVED','REJECTED','QUARANTINED') or not reason_code.strip() or not note.strip():raise ValueError('Explicit review decision/reason/note required')
  record=await self.read_assertion(extraction_id)
  if record is None:raise ValueError('Unknown assertion')
  p=record['payload']
  if decision=='APPROVED' and (p['relation_type'] not in ('HOLDS_ROLE','APPOINTS','DISMISSES') or p['validation_status']!='SOURCE_VERIFIED' or not p.get('effective_date') and not p.get('report_year')):
   raise ValueError('Approval requires verified source and temporal basis')
  rid=review_id or uuid.uuid4()
  await self.c.execute('INSERT INTO graph_metadata.reviews(review_id,extraction_id,decision,reason_code,note) VALUES($1,$2,$3,$4,$5)',rid,uuid.UUID(str(extraction_id)),decision,reason_code,note)
  return str(rid)
