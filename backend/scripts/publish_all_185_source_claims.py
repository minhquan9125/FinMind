"""Replay all 185 repaired source claims, persist a ledger and publish source scope.

This does not turn unresolved global people into resolved identities, fabricate
calendar dates, or change the existing WBS06 global-graph approval policy.
"""
import argparse,asyncio,json,os,uuid,hashlib
from pathlib import Path
import asyncpg
from neo4j import GraphDatabase
from person_role_db import ROOT,dsn
from prepare_person_review_manifest import parse_report
from src.graph.source_person_claims import prepare_claim_batch,verify_live_claim_sources,SourcePersonClaimStore,packed
from src.graph_review.sources import PostgresSourceReader
from src.graph_review.models import digest

OUT=ROOT/'outputs/person-all-185-20261104'
MANIFEST=ROOT/'outputs/person-neo4j-publish-20261103/review-manifest.json'

async def main(args):
    audit=json.loads((OUT/'live-source-audit.json').read_text('utf-8'))
    repairs=json.loads((OUT/'repairs.json').read_text('utf-8'))
    manifest=json.loads(MANIFEST.read_text('utf-8'))
    report_path=Path(args.source_review)
    raw_report=report_path.read_bytes()
    if hashlib.sha256(raw_report).hexdigest()!=manifest['report_sha256']:raise ValueError('Human source review report hash changed')
    parsed=parse_report(raw_report.decode('utf-8-sig'))
    actual={r['extraction_id']:r for r in parsed['records']}
    for row in manifest['records']:
        r=actual[row['extraction_id']]
        if r['review_body_sha256']!=row['review_body_sha256'] or r['report_decision']!=row['report_decision']:raise ValueError('Human review assertion changed')
    batch=prepare_claim_batch(repairs,audit,manifest)
    print('All 185 deterministic source repairs validated',flush=True)
    c=await asyncpg.connect(dsn(),timeout=15,command_timeout=120)
    try:
        async with c.transaction(readonly=True,isolation='repeatable_read'):
            await c.execute('SET LOCAL ROLE finmind_graph_writer')
            live=await verify_live_claim_sources(batch,PostgresSourceReader(c))
        output=dict(status='DRY_RUN_READY_SOURCE_SCOPE',graph_version_id=batch['graph_version_id'],claims=185,
            excluded=0,live_checks=live,payload_sha256=batch['payload_sha256'],postgres_writes=0,neo4j_writes=0,
            serving_scope='SOURCE_DOCUMENT_ASSERTIONS_NOT_GLOBAL_IDENTITY_FACTS')
        if args.apply:
            password=os.environ.get('NEO4J_PASSWORD')
            if not password:raise ValueError('NEO4J_PASSWORD required in process environment')
            # Record immutable export provenance in an existing source payload table.
            # No existing extraction or terminal review decision is overwritten.
            pid=uuid.uuid5(uuid.NAMESPACE_URL,'finmind:source-person-claim-ledger:'+batch['graph_version_id'])
            uri='finmind:source-person-claim-ledger:'+batch['graph_version_id']
            async with c.transaction():
                await c.execute('''INSERT INTO raw_payloads(payload_id,source_uri,sha256,payload,stored_at)
                    VALUES($1,$2,$3,$4::jsonb,now()) ON CONFLICT(payload_id) DO NOTHING''',pid,uri,batch['payload_sha256'],packed(batch['manifest']))
                saved=await c.fetchrow('SELECT sha256,payload FROM raw_payloads WHERE payload_id=$1',pid)
                payload=json.loads(saved['payload']) if isinstance(saved['payload'],str) else saved['payload']
                if saved['sha256'].strip()!=batch['payload_sha256'] or digest(payload)!=batch['payload_sha256']:raise ValueError('Immutable source claim ledger conflict')
            with GraphDatabase.driver(os.environ.get('NEO4J_URI','bolt://127.0.0.1:17687'),auth=(os.environ.get('NEO4J_USER','neo4j'),password),connection_timeout=10) as driver:
                driver.verify_connectivity()
                receipt=SourcePersonClaimStore(driver,os.environ.get('NEO4J_DATABASE','neo4j')).publish(batch)
            output.update(status=receipt['status'],build_receipt=receipt,ledger_payload_id=str(pid),postgres_writes=1,neo4j_writes=185)
        (OUT/('publish-receipt.json' if args.apply else 'publish-dry-run.json')).write_text(json.dumps(output,ensure_ascii=False,indent=2),'utf-8')
        print(json.dumps(output,ensure_ascii=False))
    finally:await c.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true')
    parser.add_argument('--source-review',default=r'C:\Users\ADMIN\Downloads\WBS06_HANDOFF_VU (1).md')
    asyncio.run(main(parser.parse_args()))
