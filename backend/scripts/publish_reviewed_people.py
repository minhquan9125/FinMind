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
from src.documents.shared_source import read_release_root

async def make_envelope(c,records,reader):
    documents={};chunks={};entities={};relations=[];root_cache={};scope=None
    for record in records:
        raw=record['candidate']
        attribution=await c.fetchrow('SELECT reviewed_by,reviewed_at FROM graph_review_results WHERE review_id=$1',uuid.UUID(record['review_id']))
        if not attribution or not attribution['reviewed_by'] or not attribution['reviewed_at']:
            raise ValueError('APPROVAL_ATTRIBUTION_MISSING')
        for endpoint in (raw['subject'],raw['object']):
            value={**endpoint,'attributes':{}}
            old=entities.setdefault(value['entity_id'],value)
            if old!=value:raise ValueError('APPROVED_ENTITY_IDENTITY_CONFLICT')
        evidence=[]
        for ref in raw['evidence']:
            current=await reader.read_current(ref['chunk_id'],ref['corpus_id'])
            if current.locator.get('kind')!='db_text_span' or type(current.locator.get('page')) is not int:
                raise ValueError('SOURCE_PROFILE_NOT_SUPPORTED_BY_ENVELOPE_2_1_NO_FAKE_PDF_PAGE')
            pair=(current.corpus_id,current.index_version_id)
            if scope is None:scope=pair
            if scope!=pair:raise ValueError('APPROVED_RECORDS_MIX_CORPUS_INDEX')
            original=await c.fetchval('SELECT locator_json FROM text_chunks WHERE chunk_id=$1',uuid.UUID(current.chunk_id))
            original=json.loads(original) if isinstance(original,str) else original
            root=await read_release_root(c,current.index_version_id,root_cache)
            member=next(m for m in root['sources'] if m['source_table']==original['source_table'] and m['source_id']==original['source_id'])
            doc=dict(source_kind='db',document_id=current.document_id,document_version=current.document_version,
                source_uri=member['source_uri'],source_sha256=current.source_sha256,index_version_id=current.index_version_id)
            if documents.setdefault(current.document_id,doc)!=doc:raise ValueError('DOCUMENT_VERSION_CONFLICT')
            chunk=dict(document_id=current.document_id,document_version=current.document_version,chunk_id=current.chunk_id,
                text=current.text,locator=current.locator)
            key=(current.document_id,current.chunk_id)
            if chunks.setdefault(key,chunk)!=chunk:raise ValueError('CHUNK_VERSION_CONFLICT')
            evidence.append(dict(document_id=ref['document_id'],chunk_id=ref['chunk_id'],quote=ref['quote']))
        relations.append(dict(relation_id=raw['candidate_id'],subject_id=raw['subject']['entity_id'],object_id=raw['object']['entity_id'],
            relation_type=raw['relation_type'],attributes=raw['attributes'],temporal=raw['temporal'],evidence=evidence,
            review=dict(status='APPROVED',reviewer=str(attribution['reviewed_by']),reviewed_at=attribution['reviewed_at'].isoformat())))
    if not scope:raise ValueError('NO_APPROVED_SOURCE_SCOPE')
    version='2.2.0' if any(k.endswith('_precision') for r in relations for k in r['temporal']) else '2.1.0'
    return validate_envelope(dict(schema_version=version,corpus_id=scope[0],dataset_version=scope[1],
        documents=list(documents.values()),chunks=list(chunks.values()),entities=list(entities.values()),mentions=[],relations=relations))

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
