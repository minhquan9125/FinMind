"""Read back committed metadata using the application's restricted role."""
import asyncio,json,uuid
import asyncpg
from person_role_db import ROOT,dsn
from src.person_role.metadata_repository import GraphMetadataRepository
async def main():
 c=await asyncpg.connect(dsn(),timeout=15,command_timeout=90)
 try:
  async with c.transaction(readonly=True):
   await c.execute('SET LOCAL ROLE finmind_chat_runtime')
   identity=dict(await c.fetchrow('SELECT current_user,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user'))
   assert not identity['rolsuper'] and not identity['rolbypassrls']
   gid=uuid.UUID('6f1504e8-3eef-59e7-9d20-8c5957cb4427')
   rows=await c.fetch('SELECT extraction_id FROM graph_metadata.assertions WHERE graph_version_id=$1',gid)
   repo=GraphMetadataRepository(c);sources=0
   for row in rows:
    record=await repo.read_assertion(row['extraction_id']);assert record['review_status']=='PENDING'
    sources+=len(record['sources'])
   assert len(rows)==184
  out=dict(status='PASS',application_role=identity,assertions_read_and_hash_verified=len(rows),source_bindings_checked=sources,human_approvals=0,database_writes=0)
  output=ROOT/'outputs/graph-metadata-20261030';output.mkdir(parents=True,exist_ok=True)
  (output/'verification.json').write_text(json.dumps(out,indent=2),'utf-8');print(json.dumps(out))
 finally:await c.close()
asyncio.run(main())
