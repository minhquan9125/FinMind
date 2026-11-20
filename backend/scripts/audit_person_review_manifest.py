"""Match review IDs to live PostgreSQL records and report publication blockers."""
import asyncio,hashlib,json,uuid
from collections import Counter
import asyncpg
from person_role_db import ROOT,dsn
from src.person_role.metadata_repository import digest

SUPPORTED={'HOLDS_ROLE','APPOINTS','DISMISSES'}

async def main():
 output=ROOT/'outputs/person-neo4j-publish-20261103'
 manifest=json.loads((output/'review-manifest.json').read_text('utf-8'))
 ids=[uuid.UUID(r['extraction_id']) for r in manifest['records']]
 c=await asyncpg.connect(dsn(),timeout=15)
 try:
  async with c.transaction(readonly=True,isolation='repeatable_read'):
   rows=await c.fetch('''SELECT g.extraction_id::text,g.document_id::text,g.subject,g.object,g.relation_type,
     g.validation_status,e.locator_json,a.payload,a.content_sha256,
     s.resolution_status AS subject_resolution,o.resolution_status AS object_resolution,
     (SELECT decision FROM graph_metadata.reviews r WHERE r.extraction_id=g.extraction_id ORDER BY created_at DESC,review_id DESC LIMIT 1) AS review_decision
     FROM graph_extractions g JOIN evidence e USING(extraction_id)
     LEFT JOIN graph_metadata.assertions a USING(extraction_id)
     LEFT JOIN graph_metadata.entities s ON s.graph_version_id=a.graph_version_id AND s.entity_id=a.subject_id
     LEFT JOIN graph_metadata.entities o ON o.graph_version_id=a.graph_version_id AND o.entity_id=a.object_id
     WHERE g.extraction_id=ANY($1::uuid[])''',ids)
   byid={r['extraction_id']:dict(r) for r in rows};results=[]
   for reviewed in manifest['records']:
    row=byid.get(reviewed['extraction_id']);blockers=[]
    item=dict(extraction_id=reviewed['extraction_id'],report_decision=reviewed['report_decision'],subject=reviewed['subject'],object=reviewed['object'],relation_type=reviewed['relation_type'])
    if reviewed['report_decision']=='REJECTED':blockers.append('REPORT_REJECTED')
    if row is None:
     blockers.append('EXTRACTION_NOT_FOUND')
    else:
     loc=json.loads(row['locator_json']) if isinstance(row['locator_json'],str) else row['locator_json']
     if (row['subject'],row['object'],row['relation_type'])!=(reviewed['subject'],reviewed['object'],reviewed['relation_type']):blockers.append('REPORT_FACT_MISMATCH')
     if row['document_id']!=reviewed['document_id']:blockers.append('REPORT_DOCUMENT_MISMATCH')
     p=row['payload'];p=json.loads(p) if isinstance(p,str) else p
     if p is None:blockers.append('NO_METADATA_ASSERTION')
     elif digest(p)!=row['content_sha256'].strip():blockers.append('METADATA_HASH_MISMATCH')
     if row['subject_resolution']!='resolved' or row['object_resolution']!='resolved':blockers.append('CANONICAL_IDENTITY_UNRESOLVED')
     if row['review_decision']!='APPROVED':blockers.append('APPLICATION_APPROVAL_MISSING')
     if reviewed['relation_type'] not in SUPPORTED:blockers.append('RELATION_OUTSIDE_CURRENT_PUBLISH_CONTRACT')
     if row['validation_status']!='SOURCE_VERIFIED':blockers.append('SOURCE_VALIDATION_NOT_SOURCE_VERIFIED')
     if not (p or {}).get('effective_date') and not (p or {}).get('report_year'):blockers.append('TEMPORAL_MAPPING_REQUIRED')
     item.update(subject_resolution=row['subject_resolution'],object_resolution=row['object_resolution'],database_review=row['review_decision'] or 'PENDING',source_status=row['validation_status'],source_url=loc.get('source_url'),report_year=(p or {}).get('report_year'),effective_date=(p or {}).get('effective_date'))
    item['blockers']=blockers;item['publishable']=not blockers;results.append(item)
   report=dict(database_writes=0,neo4j_writes=0,report_sha256=manifest['report_sha256'],records=results,
    summary=dict(total=len(results),report_approved=sum(r['report_decision']=='APPROVED' for r in results),report_rejected=sum(r['report_decision']=='REJECTED' for r in results),found_in_postgres=len(byid),publishable=sum(r['publishable'] for r in results),blockers=dict(Counter(b for r in results for b in r['blockers']))))
   (output/'publishability-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),'utf-8')
   print(json.dumps(report['summary'],ensure_ascii=False))
 finally:await c.close()
if __name__=='__main__':asyncio.run(main())
