"""Apply terminal-review guard; permission probes always roll back."""
import asyncio,json,uuid
import asyncpg
from person_role_db import ROOT,dsn

async def main():
 c=await asyncpg.connect(dsn(),timeout=15);tx=c.transaction();await tx.start()
 try:
  before=await c.fetchval('SELECT count(*) FROM graph_metadata.reviews')
  sql=(ROOT/'docker/postgres/migrations/20261103_legacy_review_terminal.sql').read_text('utf-8')
  await c.execute(sql);await c.execute(sql)
  xid=await c.fetchval('SELECT extraction_id FROM graph_metadata.assertions ORDER BY extraction_id LIMIT 1')
  probe=c.transaction();await probe.start()
  try:
   await c.execute('SET LOCAL ROLE finmind_graph_reviewer')
   await c.execute("INSERT INTO graph_metadata.reviews(review_id,extraction_id,decision,reason_code,note) VALUES($1,$2,'REJECTED','ROLLBACK_PROBE','Temporary probe, never committed')",uuid.uuid4(),xid)
   blocked=False
   try:
    async with c.transaction():
     await c.execute("INSERT INTO graph_metadata.reviews(review_id,extraction_id,decision,reason_code,note) VALUES($1,$2,'PENDING','ROLLBACK_PROBE','Must be rejected')",uuid.uuid4(),xid)
   except asyncpg.CheckViolationError:blocked=True
   if not blocked:raise ValueError('Legacy rejection was reopened')
  finally:await probe.rollback()
  after=await c.fetchval('SELECT count(*) FROM graph_metadata.reviews')
  assert before==after
  await tx.commit()
  report=dict(status='MIGRATION_COMMITTED',legacy_rejected_cannot_reopen=True,probes_rolled_back=True,legacy_review_count_unchanged=after)
  out=ROOT/'outputs/person-neo4j-publish-20261103/intake/legacy-terminal.json'
  out.write_text(json.dumps(report,indent=2),'utf-8');print(json.dumps(report))
 except BaseException:await tx.rollback();raise
 finally:await c.close()
if __name__=='__main__':asyncio.run(main())
