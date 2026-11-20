"""Live integration; migration commits only with --apply; draft probes rollback."""
import argparse,asyncio,json,uuid
from copy import deepcopy
import asyncpg
from person_role_db import ROOT,dsn
from run_wbs03_pipeline import extract_registered
from src.person_role.wbs03_repository import WBS03Repository
from src.person_role.metadata_repository import digest

CID='b2550a0b-c423-5c50-9b15-6fb6af12e2c6'
OUT=ROOT/'outputs/wbs03-pipeline-20261030'
async def main(apply):
 OUT.mkdir(exist_ok=True);c=await asyncpg.connect(dsn(),timeout=15,command_timeout=90)
 tx=c.transaction(isolation='repeatable_read');await tx.start()
 try:
  migration=(ROOT/'docker/postgres/migrations/20261030_wbs03_envelopes.sql').read_text('utf-8')
  await c.execute(migration);await c.execute(migration);print('Migration replay passed',flush=True)
  # Real ELC page, selected by corpus membership, not by a fabricated fixture.
  ids=await c.fetch('''SELECT t.chunk_id::text FROM text_chunks t JOIN documents d USING(document_id)
   JOIN corpus_documents cd USING(document_id) JOIN companies co USING(company_id)
   WHERE cd.corpus_version_id=$1 AND co.symbol='ELC' AND t.page_number=68 AND t.index_version_id=$2
   AND t.superseded_at IS NULL ORDER BY t.chunk_index''',uuid.UUID(CID),uuid.UUID('ecfbf20f-b3e0-5077-bd3e-03f0efb95e6d'))
  assert ids
  await c.execute('SET LOCAL ROLE finmind_graph_writer')
  selected=None
  for row in ids:
   print('Reading real ELC chunk '+row['chunk_id'],flush=True)
   payload,audit=await extract_registered(c,CID,[row['chunk_id']],True)
   if payload['relations']:selected=(payload,audit);break
  assert selected,'No real review candidates: do not fabricate an extraction'
  payload,audit=selected;repo=WBS03Repository(c);checks={}
  probe=c.transaction();await probe.start()
  print('Real candidates: '+str(len(payload['relations'])),flush=True)
  saved=await repo.save(payload);again=await repo.save(payload);assert saved==again
  assert await repo.read(saved['graph_version_id'])==payload
  checks['real_source_extract_save_read']=True;checks['replay_without_duplicates']=True
  async def rejected(name,value):
   try:
    async with c.transaction():await repo.save(value)
   except (ValueError,asyncpg.InsufficientPrivilegeError):checks[name]=True
   else:raise AssertionError('Expected rejection: '+name)
  wrong=deepcopy(payload);wrong['documents'][0]['source_sha256']='0'*64
  await rejected('wrong_snapshot_hash_rejected',wrong)
  wrong=deepcopy(payload);wrong['chunks'][0]['locator']['char_start']+=1;wrong['chunks'][0]['locator']['char_end']+=1
  await rejected('internally_consistent_but_wrong_locator_rejected',wrong)
  wrong=deepcopy(payload);wrong['documents'][0]['source_uri']='finmind:shared-source:wrong'
  await rejected('wrong_source_uri_rejected',wrong)
  wrong=deepcopy(payload);wrong['relations'][0]['review']['status']='APPROVED'
  await rejected('no_auto_approval',wrong)
  await c.execute('SET LOCAL ROLE finmind_chat_runtime')
  assert await repo.read(saved['graph_version_id'])==payload
  checks['runtime_read_roundtrip']=True
  await rejected('runtime_cannot_save',payload)
  await c.execute('RESET ROLE')
  assert await c.fetchval('SELECT count(*) FROM graph_extractions WHERE graph_version_id=$1',uuid.UUID(saved['graph_version_id']))==len(payload['relations'])
  await probe.rollback()
  # Rollback data probes; keep only the additive schema when explicitly requested.
  await c.execute('RESET ROLE')
  if apply:await tx.commit()
  else:await tx.rollback()
  for name,obj in [('tested-envelope.json',payload),('extraction-audit.json',audit)]:
   (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),'utf-8')
  result=dict(status='MIGRATION_COMMITTED_TEST_DRAFTS_ROLLED_BACK' if apply else 'ALL_ROLLED_BACK_PASS',checks=checks,real_candidates=len(payload['relations']),corpus_version_id=CID,ai_calls=0,approved_relations_created=0,test_drafts_persisted=0)
  (OUT/'verification.json').write_text(json.dumps(result,indent=2),'utf-8');print(json.dumps(result))
 except BaseException:
  await tx.rollback();raise
 finally:await c.close()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');asyncio.run(main(p.parse_args().apply))
