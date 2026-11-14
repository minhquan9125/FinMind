"""Apply additive migration and backfill current graph; --apply commits."""
import argparse,asyncio,json,uuid
import asyncpg
from person_role_db import ROOT,dsn
from src.person_role.metadata_repository import GraphMetadataRepository,MetadataConflict
OUT=ROOT/'outputs/graph-metadata-20261030'
MIG=ROOT/'docker/postgres/migrations/20261030_graph_metadata.sql'
GID=uuid.UUID('6f1504e8-3eef-59e7-9d20-8c5957cb4427')

async def main(apply):
 OUT.mkdir(exist_ok=True)
 c=await asyncpg.connect(dsn(),timeout=15,command_timeout=120)
 tx=c.transaction();await tx.start()
 try:
  await c.execute(MIG.read_text('utf-8'))
  await c.execute(MIG.read_text('utf-8')) # Migration replay must be harmless.
  binding=ROOT/'outputs/person-graph-new-corpus-20261030/result.json'
  if not binding.exists():binding=ROOT/'docs/graph/acceptance/graph-source-binding.json'
  result=json.loads(binding.read_text('utf-8'))
  await c.execute('SET LOCAL ROLE finmind_graph_writer')
  repo=GraphMetadataRepository(c)
  await repo.register_version(GID,result['corpus_version_id'],result['index_version_id'],result['manifest_sha256'],
   dict(manifest_uri='finmind:person-role-graph-manifest:'+str(GID),semantic_review='AI_SOURCE_VERIFIED_NOT_HUMAN_APPROVED'),
   'source-bound-person-role-v2;target-WBS03-2.1.0-not-envelope-converted')
  await c.execute('RESET ROLE')
  rows=await c.fetch('''SELECT g.extraction_id,g.subject,g.object,g.relation_type,g.validation_status,e.locator_json
   FROM graph_extractions g JOIN evidence e USING(extraction_id) WHERE g.graph_version_id=$1 ORDER BY g.extraction_id''',GID)
  assert len(rows)==184
  first=None
  await c.execute('SET LOCAL ROLE finmind_graph_writer')
  for i,r in enumerate(rows):
   loc=json.loads(r['locator_json']);binding=loc['corpus_binding']
   def entity(name,kind):
    scope=('company:'+loc['symbol']) if kind=='Company' else ('person:'+binding['original_source_document_id']+':'+name)
    return dict(entity_id=str(uuid.uuid5(GID,scope)),entity_type=kind,canonical_name=name,resolution_status='source_scoped',
     attributes=dict(identity_scope='DOCUMENT_ONLY' if kind=='Person' else 'COMPANY_SYMBOL',symbol=loc['symbol']))
   kinds=('Company','Person') if r['relation_type'] in ('APPOINTS','DISMISSES') else ('Person','Company')
   s=entity(r['subject'],kinds[0]);o=entity(r['object'],kinds[1])
   p=dict(relation_type=r['relation_type'],position=loc['position'],validation_status=r['validation_status'],
    original_source_document_id=binding['original_source_document_id'],review_status='PENDING',
    source_url=loc.get('source_url'),report_year=loc.get('year'),effective_date=loc.get('effective_date'),
    stage=loc.get('stage'),corpus_binding=binding,semantic_review_method=loc.get('review_method'))
   args=(GID,r['extraction_id'],s,o,p,binding['chunk_bindings'])
   await repo.put_assertion(*args)
   if first is None:first=args
   if (i+1)%40==0:print(f'Metadata {i+1}/184',flush=True)
  await repo.put_assertion(*first)
  checks={'migration_replay':True,'repository_idempotent_replay':True}
  async def denied(name,call,expected=(asyncpg.InsufficientPrivilegeError,asyncpg.CheckViolationError,MetadataConflict)):
   try:
    async with c.transaction(): await call()
   except expected:checks[name]=True
   else:raise AssertionError('Expected rejection: '+name)
  bad=dict(first[4],position='TAMPERED')
  await denied('immutable_identity_conflict',lambda:repo.put_assertion(*first[:4],bad,first[5]))
  await c.execute('SET LOCAL ROLE finmind_graph_reader')
  read=await repo.read_assertion(first[1]);assert read['payload']==first[4] and read['sources']
  checks['reader_roundtrip_and_hash']=True
  await denied('reader_cannot_write',lambda:repo.put_assertion(*first))
  await denied('reader_cannot_delete',lambda:c.execute('DELETE FROM graph_metadata.assertions WHERE extraction_id=$1',first[1]))
  await c.execute('SET LOCAL ROLE finmind_graph_writer')
  await denied('writer_cannot_review',lambda:repo.record_review(first[1],'REJECTED','TEST','Permission test'))
  await denied('writer_cannot_mutate',lambda:c.execute("UPDATE graph_metadata.assertions SET payload='{}' WHERE extraction_id=$1",first[1]))
  await denied('wrong_chunk_hash_rejected',lambda:repo._immutable_insert('source_chunks',['extraction_id','chunk_id'],dict(graph_version_id=GID,extraction_id=first[1],chunk_id=uuid.UUID(first[5][0]['chunk_id']),content_hash='0'*64)))
  await denied('wrong_corpus_index_rejected',lambda:repo.register_version(GID,'9f2a7f99-a034-52bc-aff1-9d267ffe6019',result['index_version_id'],result['manifest_sha256'],{},'test'))
  await c.execute('SET LOCAL ROLE finmind_chat_runtime')
  assert (await repo.read_assertion(first[1]))['payload']==first[4]
  checks['application_runtime_read']=True
  await denied('application_runtime_cannot_write_metadata',lambda:repo.put_assertion(*first))
  # Exercise RLS directly after granting a test-only table privilege, then rollback it.
  await c.execute('RESET ROLE')
  async with c.transaction() as test_tx:
   await c.execute('GRANT INSERT ON graph_metadata.reviews TO finmind_graph_reader')
   await c.execute('SET LOCAL ROLE finmind_graph_reader')
   await denied('rls_blocks_reader_review_even_with_insert_grant',lambda:c.execute("INSERT INTO graph_metadata.reviews(review_id,extraction_id,decision,reason_code,note) VALUES($1,$2,'REJECTED','TEST','RLS probe')",uuid.uuid4(),first[1]))
   await c.execute('RESET ROLE')
   await c.execute('REVOKE INSERT ON graph_metadata.reviews FROM finmind_graph_reader')
  await c.execute('SET LOCAL ROLE finmind_graph_reviewer')
  # All review test rows are rolled back, never mistaken for real decisions.
  probe=c.transaction();await probe.start()
  for decision in ('PENDING','REJECTED','QUARANTINED'):
   await repo.record_review(first[1],decision,'INTEGRATION_TEST','Temporary permission/roundtrip test')
   assert (await repo.read_assertion(first[1]))['review_status']==decision
  await denied('unresolved_endpoints_cannot_be_approved',lambda:c.execute("INSERT INTO graph_metadata.reviews(review_id,extraction_id,decision,reason_code,note) VALUES($1,$2,'APPROVED','TEST','Must fail for unresolved endpoints')",uuid.uuid4(),first[1]))
  await probe.rollback();checks['review_and_quarantine_roundtrip_rolled_back']=True
  await c.execute('RESET ROLE')
  counts={t:await c.fetchval('SELECT count(*) FROM graph_metadata.'+t) for t in ('versions','entities','assertions','source_chunks','reviews')}
  assert counts['assertions']==184 and counts['reviews']==0
  roles=[dict(r) for r in await c.fetch("SELECT rolname,rolsuper,rolbypassrls FROM pg_roles WHERE rolname IN ('finmind_graph_reader','finmind_graph_writer','finmind_graph_reviewer')")]
  assert all(not r['rolsuper'] and not r['rolbypassrls'] for r in roles)
  rls=[dict(r) for r in await c.fetch("SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class JOIN pg_namespace n ON n.oid=relnamespace WHERE n.nspname='graph_metadata' AND relkind='r' AND relname IN ('versions','entities','assertions','source_chunks','reviews')")]
  assert len(rls)==5 and all(r['relrowsecurity'] and r['relforcerowsecurity'] for r in rls)
  if apply:await tx.commit()
  else:await tx.rollback()
  report=dict(status='COMMITTED' if apply else 'MIGRATION_AND_REPOSITORY_ROLLBACK_TEST_PASS',environment='VPS PostgreSQL',checks=checks,counts=counts,roles=roles,rls=rls,
   graph_version_id=str(GID),schema_version='1.0.0',contract_envelope_conversion=False,human_approvals_created=0,existing_graph_modified=False)
  (OUT/('result.json' if apply else 'preview.json')).write_text(json.dumps(report,indent=2),'utf-8')
  print(json.dumps(report),flush=True)
 except BaseException:
  await tx.rollback();raise
 finally:await c.close()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');asyncio.run(main(p.parse_args().apply))
