"""Live WBS06 approval gate -> WBS09 -> Neo4j. Empty approval sets write nothing."""
import argparse,asyncio,json,os,uuid
from pathlib import Path
import asyncpg
from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError,ServiceUnavailable
from person_role_db import ROOT,dsn
from src.graph_review.engine import IdentityRegistry,ReviewEngine
from src.graph_review.repository import PostgresReviewStore,approved_records
from src.graph_review.sources import PostgresSourceReader
from src.graph_review.gate import build_gate
from src.graph_review.models import digest
from src.graph.sprint4_store import Sprint4GraphStore,prepare_batch
from src.graph.wbs09_pipeline import build_graph_version
from src.sprint4_runtime.contracts import validate_envelope
from src.sprint4_runtime.news_contract import is_news_locator
from src.graph_review.models import Evidence
from src.graph_review.sources import compare_source
from src.documents.shared_source import read_release_root

from src.graph_review.export import make_envelope

async def main(args):
    intake=json.loads((args.intake/'receipt.json').read_text('utf-8'))
    gid=intake['graph_version_id'];registry=IdentityRegistry(json.loads((args.intake/'registry-used.json').read_text('utf-8')))
    c=await asyncpg.connect(dsn(),timeout=15,command_timeout=120)
    report=dict(graph_version_id=gid,database_writes=0,neo4j_writes=0,status='BLOCKED',checks={})
    try:
        async with c.transaction(readonly=True,isolation='repeatable_read'):
            role=getattr(args,'source_role','finmind_graph_reader')
            if role not in {'finmind_graph_reader','finmind_graph_writer'}:raise ValueError('Unsupported read-only source role')
            await c.execute('SET LOCAL ROLE '+role)
            report['source_role']=role
            report['postgres_transaction_read_only']=True
            reader=PostgresSourceReader(c);engine=ReviewEngine(reader,registry);store=PostgresReviewStore(c)
            counts=[dict(row) for row in await c.fetch('SELECT status,count(*) AS count FROM graph_review_results WHERE graph_version_id=$1 GROUP BY status',uuid.UUID(gid))]
            has_approved=any(row['status']=='APPROVED' and row['count'] for row in counts)
            records=[]
            if has_approved:
                async with c.transaction():records=await approved_records(store,engine,gid)
            report.update(review_counts=counts,eligible_after_live_revalidation=len(records))
            if not records:
                report['blocked_reason']='NO_APPROVED_RELATIONS_AFTER_WBS06_GATE'
                if has_approved:
                    active=await store.active(gid)
                    fresh=await engine.evaluate_batch([r['candidate'] for r in active])
                    report['revalidation']=[dict(candidate_id=r.candidate_id,status=r.status,reasons=r.reasons,
                        source_verified=r.source_verified,verification_mode=r.verification_mode) for r in fresh]
            else:
                envelope=await make_envelope(c,records,reader)
                gate=await build_gate(store,engine,gid,envelope)
                prepared=prepare_batch(envelope,gid,'preflight')
                gate.authorize(prepared)
                (args.intake/'approved-envelope.json').write_text(json.dumps(envelope,ensure_ascii=False,indent=2),'utf-8')
                report['checks']['live_source_gate']=True
                if not args.apply:
                    report.update(status='DRY_RUN_READY',blocked_reason=None)
                else:
                    password=os.environ.get('NEO4J_PASSWORD')
                    if not password:raise ValueError('NEO4J_PASSWORD_REQUIRED_IN_PROCESS_ENVIRONMENT')
                    def approve(actual):
                        if digest(actual)!=gate.input_hash:raise PermissionError('Envelope differs from approval')
                        return gate
                    with GraphDatabase.driver(os.environ.get('NEO4J_URI','bolt://127.0.0.1:17687'),
                            auth=(os.environ.get('NEO4J_USER','neo4j'),password),connection_timeout=10) as driver:
                        driver.verify_connectivity()
                        report['neo4j_write_attempted']=True
                        receipt=build_graph_version(Sprint4GraphStore(driver,database=os.environ.get('NEO4J_DATABASE','neo4j')),
                            [envelope],graph_version_id=gid,approve=approve)
                    report.update(status=receipt['status'],neo4j_writes=receipt['counts']['loaded'],build_receipt=receipt)
    except (ValueError,PermissionError) as exc:
        report['blocked_reason']=str(exc)
    except asyncpg.PostgresError as exc:
        report['blocked_reason']='POSTGRES_SOURCE_REVALIDATION_FAILED:'+str(exc.sqlstate)
    except (Neo4jError,ServiceUnavailable) as exc:
        report['blocked_reason']='NEO4J_CONNECTION_OR_PUBLICATION_FAILED:'+type(exc).__name__
        report['neo4j_writes']=None if report.get('neo4j_write_attempted') else 0
    finally:await c.close()
    (args.intake/'publish-receipt.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),'utf-8')
    print(json.dumps(report,ensure_ascii=False,default=str))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true')
    p.add_argument('--intake',type=Path,default=ROOT/'outputs/person-neo4j-publish-20261103/intake')
    p.add_argument('--source-role',choices=['finmind_graph_reader','finmind_graph_writer'],default='finmind_graph_reader',
        help='Existing DB role for source reads; transaction stays read-only even for WBS03 writer')
    asyncio.run(main(p.parse_args()))
