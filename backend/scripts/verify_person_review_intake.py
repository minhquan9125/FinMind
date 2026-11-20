"""Independent readback after commit; no migration or data writes."""
import asyncio,json,uuid
import asyncpg
from person_role_db import ROOT,dsn
from src.graph_review.engine import IdentityRegistry

async def main():
 output=ROOT/'outputs/person-neo4j-publish-20261103/intake'
 receipt=json.loads((output/'receipt.json').read_text('utf-8'));gid=uuid.UUID(receipt['graph_version_id'])
 candidates=json.loads((output/'candidates.json').read_text('utf-8'))
 original={raw['candidate_id']:raw for raw in candidates}
 c=await asyncpg.connect(dsn(),timeout=15)
 try:
  async with c.transaction(readonly=True):
   actor=await c.fetchrow("SELECT is_active,password_hash FROM users WHERE user_id='e0679567-7344-5f81-bf20-4a4ed0c24c28'")
   assert actor and actor['is_active'] is False and actor['password_hash'] is None
   await c.execute('SET LOCAL ROLE finmind_graph_reader')
   rows=await c.fetch('SELECT candidate_id,candidate,status FROM graph_review_results WHERE graph_version_id=$1',gid)
   assert len(rows)==128 and sum(row['status']=='PENDING' for row in rows)==126 and sum(row['status']=='REJECTED' for row in rows)==2
   for row in rows:
    raw=json.loads(row['candidate']) if isinstance(row['candidate'],str) else row['candidate']
    assert raw==original[row['candidate_id']]
   audit_count=await c.fetchval('SELECT count(*) FROM graph_review_audit a JOIN graph_review_results r USING(review_id) WHERE r.graph_version_id=$1',gid)
   assert audit_count==128
  # Quarantine has an existing independent RLS policy; inspect as operator, not
  # by granting the chat reader access to all legacy ingestion quarantine rows.
  qcount=await c.fetchval('SELECT count(*) FROM quarantine_records q JOIN graph_review_results r ON r.review_id=q.review_id WHERE r.graph_version_id=$1',gid)
  assert qcount==128
  probes=await c.fetchval("SELECT count(*) FROM graph_review_results WHERE candidate_id LIKE 'rollback-probe:%'")
  assert probes==0
  report=dict(status='COMMITTED_READBACK_PASS',graph_version_id=str(gid),pending=126,rejected=2,audit_rows=audit_count,
    quarantine_rows=qcount,reader_roundtrip=True,no_probe_rows=True,inactive_audit_principal=True,database_writes=0)
  (output/'readback.json').write_text(json.dumps(report,indent=2),'utf-8')
  print(json.dumps(report))
 finally:await c.close()
 # Reconstruct the exact registry snapshot for older runs of the intake CLI.
 registry=IdentityRegistry(json.loads((ROOT/'backend/src/sprint4_runtime/company.registry.20261030.r1.json').read_text('utf-8')))
 if not (output/'registry-used.json').exists():
  assert registry.sha256==receipt['registry_sha256']
  (output/'registry-used.json').write_text(json.dumps(list(registry.rows.values()),ensure_ascii=False,indent=2),'utf-8')

if __name__=='__main__':asyncio.run(main())
