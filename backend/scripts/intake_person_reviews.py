"""Legacy source records -> live WBS06 candidates -> restricted review store.

Default is a transaction rollback. --apply stores evaluations/quarantine, never
converts source_scoped identities into resolved ones or creates human approvals.
"""
import argparse,asyncio,copy,json,uuid
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
import asyncpg
from person_role_db import ROOT,dsn
from src.graph_review.adapters import source_ref
from src.graph_review.engine import IdentityRegistry,ReviewEngine
from src.graph_review.models import digest
from src.graph_review.repository import PostgresReviewStore
from src.graph_review.sources import PostgresSourceReader
from src.person_role.evidence_spans import person_spans

ACTOR=uuid.UUID('e0679567-7344-5f81-bf20-4a4ed0c24c28')
MIGRATION=ROOT/'docker/postgres/migrations/20261103_graph_review_store.sql'
REGISTRY=ROOT/'backend/src/sprint4_runtime/company.registry.20261030.r1.json'
CORPUS='b2550a0b-c423-5c50-9b15-6fb6af12e2c6'
INDEX='ecfbf20f-b3e0-5077-bd3e-03f0efb95e6d'

def obj(value):return json.loads(value) if isinstance(value,str) else value

def endpoint(row,which,loc,registry):
    kind='Company' if (which=='subject')==(row['relation_type'] in ('APPOINTS','DISMISSES')) else 'Person'
    # Historical person->company predicates have the same direction as HOLDS_ROLE.
    name=row[which];local_id=row.get(which+'_id')
    if kind=='Company':
        matches=[e for e in registry.rows.values() if e['entity_type']=='Company'
                 and loc.get('symbol') in e.get('ticker_aliases',[])]
        if len(matches)==1:
            known=matches[0]
            return dict(entity_id=known['entity_id'],entity_type=kind,canonical_name=known['canonical_name'],
                aliases=known.get('aliases',[]),identity_key=known['identity_key'],resolution_status='resolved')
    if not local_id:
        local_id=str(uuid.uuid5(uuid.NAMESPACE_URL,kind+':'+row['document_id']+':'+name))
    known=registry.rows.get(str(local_id))
    if known is None:
        mappings=[e for e in registry.rows.values() if str(local_id) in e.get('source_entity_ids',[])]
        if len(mappings)==1:known=mappings[0]
    if known and known['entity_type']==kind and name in {known['canonical_name'],*known.get('aliases',[])}:
        return dict(entity_id=known['entity_id'],entity_type=kind,canonical_name=known['canonical_name'],aliases=known.get('aliases',[]),
            identity_key=known.get('identity_key'),resolution_status='resolved')
    return dict(entity_id=str(local_id),entity_type=kind,canonical_name=name,aliases=[name],
                identity_key=None,resolution_status='unresolved')

async def convert(c,reviewed,row,reader,registry,known_names=None):
    loc=obj(row['locator_json']);payload=obj(row['payload']) or {}
    binding=loc.get('corpus_binding',{})
    ids=[b['chunk_id'] for b in binding.get('chunk_bindings',[])]
    if not ids:
        ids=[str(r['chunk_id']) for r in await c.fetch('''SELECT t.chunk_id FROM text_chunks t
            JOIN corpus_documents cd ON cd.document_id=t.document_id AND cd.corpus_version_id=$2::uuid
            WHERE t.document_id=$1::uuid AND t.index_version_id=$3::uuid AND t.superseded_at IS NULL
            AND ($4::integer IS NULL OR t.page_number=$4) ORDER BY t.chunk_index''',
            row['document_id'],CORPUS,INDEX,reviewed['pdf_page'])]
    evidence=[];errors=[];snapshots=set()
    for cid in dict.fromkeys(ids):
        actual=await reader.read_current(cid,CORPUS)
        if actual.document_id!=row['document_id'] or actual.index_version_id!=INDEX:
            raise ValueError('Source/document membership mismatch')
        # Full bound chunks preserve cross-chunk/page context without manufacturing
        # a synthetic chunk, a PDF page, or a quote that never existed in one chunk.
        person=row['object'] if row['relation_type'] in ('APPOINTS','DISMISSES') else row['subject']
        spans=person_spans(actual.text,person,known_names or [person])
        for span in spans:
            if span['start']<0 or actual.text[span['start']:span['end']]!=span['quote']:
                raise ValueError('Evidence span offsets do not match original source')
            evidence.append(source_ref(actual,span['quote']))
        import re
        match=re.search(r'\bSnapshot (\d{4}-\d{2}-\d{2})\b',actual.text.splitlines()[0])
        if match:
            snapshots.add(match[1])
            evidence.append(source_ref(actual,actual.text.splitlines()[0]))
    if reviewed['report_decision']=='REJECTED':errors.append('ERR_REPORT_REJECTED')
    if row.get('legacy_rejected'):errors.append('ERR_LEGACY_TERMINAL_REJECTED')
    if (row['subject'],row['object'],row['relation_type'],row['document_id'])!=(reviewed['subject'],reviewed['object'],reviewed['relation_type'],reviewed['document_id']):
        raise ValueError('Review report does not match stored extraction')
    if payload and digest(payload)!=row['content_sha256'].strip():raise ValueError('Stored metadata hash changed')
    valid_from=payload.get('effective_date') or loc.get('effective_date')
    temporal=dict(as_of=next(iter(snapshots)) if len(snapshots)==1 else None,valid_from=valid_from,valid_to=None)
    raw=dict(group='person',relation_type=row['relation_type'],subject=endpoint(row,'subject',loc,registry),
        object=endpoint(row,'object',loc,registry),evidence=evidence,attributes=dict(position=loc.get('position') or payload.get('position')),
        temporal=temporal,conflicts=['SOURCE_CONFLICT'] if row['validation_status']=='SOURCE_CONFLICT' else [],
        extractor_metadata=dict(format='legacy-person-live-intake-v2',origin_extraction_id=row['extraction_id'],
          report_decision=reviewed['report_decision'],report_review_body_sha256=reviewed['review_body_sha256'],
          original_validation_status=row['validation_status'],original_report_year=payload.get('report_year') or loc.get('year'),
          identity_scope='SOURCE_DOCUMENT_UNLESS_TRUSTED_REGISTRY',temporal_basis='SOURCE_SNAPSHOT_AS_OF_NOT_EVENT_DATE',input_errors=errors))
    raw['candidate_id']='person-intake:'+row['extraction_id']+':'+digest(raw)[:16]
    return raw

async def main(args):
    output=args.output;output.mkdir(parents=True,exist_ok=True)
    manifest=json.loads(args.manifest.read_text('utf-8'))
    registry_rows=json.loads(REGISTRY.read_text('utf-8'))
    if args.registry.resolve()!=REGISTRY.resolve():registry_rows+=json.loads(args.registry.read_text('utf-8'))
    registry=IdentityRegistry(registry_rows)
    graph_id=uuid.uuid5(uuid.NAMESPACE_URL,'finmind:person-live-intake-v2:'+manifest['report_sha256']+':'+registry.sha256)
    c=await asyncpg.connect(dsn(),timeout=15,command_timeout=120)
    tx=c.transaction(isolation='repeatable_read');await tx.start()
    try:
        # DDL replay and all intake writes share this transaction.
        await c.execute(MIGRATION.read_text('utf-8'));await c.execute(MIGRATION.read_text('utf-8'))
        await c.execute((MIGRATION.parent/'20261103_legacy_review_terminal.sql').read_text('utf-8'))
        rows=await c.fetch('''SELECT g.extraction_id::text,g.document_id::text,g.subject,g.object,g.relation_type,g.validation_status,
          e.locator_json,a.payload,a.content_sha256,a.subject_id::text,a.object_id::text,
          COALESCE((SELECT bool_or(decision='REJECTED') FROM graph_metadata.reviews lr WHERE lr.extraction_id=g.extraction_id),false) AS legacy_rejected
          FROM graph_extractions g JOIN evidence e USING(extraction_id)
          LEFT JOIN graph_metadata.assertions a USING(extraction_id) WHERE g.extraction_id=ANY($1::uuid[])''',
          [uuid.UUID(r['extraction_id']) for r in manifest['records']])
        byid={r['extraction_id']:dict(r) for r in rows}
        if len(byid)!=len(manifest['records']):raise ValueError('Some reviewed records are absent')
        reader=PostgresSourceReader(c);candidates=[]
        known_names=[r['object'] if r['relation_type'] in ('APPOINTS','DISMISSES') else r['subject'] for r in rows]
        for index,reviewed in enumerate(manifest['records'],1):
            candidates.append(await convert(c,reviewed,byid[reviewed['extraction_id']],reader,registry,known_names))
            if index%25==0:print(f'Source conversion {index}/{len(rows)}',flush=True)
        results=await ReviewEngine(reader,registry).evaluate_batch(candidates)
        # This command is intake, never an automatic/human approval endpoint.
        if any(r.status=='APPROVED' for r in results):raise ValueError('Use reviewed publication workflow for eligible candidates')
        if any('ERR_SOURCE_UNAVAILABLE' in r.reasons for r in results):raise ValueError('Transient source failure; intake rolled back')
        # A legacy adapter cannot represent every whole-page/table assertion as
        # a precise WBS06 claim yet. Do not turn those adapter failures into a
        # terminal rejection of facts the supplied human report accepted.
        scheduled=[];deferred=[]
        for raw,result,reviewed in zip(candidates,results,manifest['records']):
            if result.status=='REJECTED' and reviewed['report_decision']!='REJECTED':
                deferred.append(dict(origin_extraction_id=reviewed['extraction_id'],candidate_id=raw['candidate_id'],
                    status='CONVERSION_BLOCKED_NOT_A_HUMAN_REJECTION',reasons=result.reasons))
            else:scheduled.append((raw,result,reviewed))
        if not scheduled:raise ValueError('No correctly representable intake candidates')
        await c.execute('''INSERT INTO graph_versions(graph_version_id,built_at,node_count,edge_count,status)
            VALUES($1,now(),$2,$3,'EXTRACTED_PENDING') ON CONFLICT DO NOTHING''',graph_id,
            len({e['entity_id'] for raw,_,_ in scheduled for e in (raw['subject'],raw['object'])}),len(scheduled))
        await c.execute("SELECT set_config('app.graph_review_actor',$1,true)",str(ACTOR))
        await c.execute('SET LOCAL ROLE finmind_graph_intake')
        store=PostgresReviewStore(c);actor=SimpleNamespace(user_id=ACTOR,roles={'DATA_ENGINEER'})
        for raw,result,reviewed in scheduled:
            await store.save(raw,result,graph_id,actor,extraction_id=reviewed['extraction_id'])
        first_raw,first_result,first_reviewed=scheduled[0]
        first=await store.save(first_raw,first_result,graph_id,actor,extraction_id=first_reviewed['extraction_id'])
        if first['candidate']!=first_raw:raise ValueError('Intake readback differs')
        counts=[dict(r) for r in await c.fetch('SELECT status,count(*) AS count FROM graph_review_results WHERE graph_version_id=$1 GROUP BY status',graph_id)]
        if sum(r['count'] for r in counts)!=len(scheduled):raise ValueError('Intake count differs')
        denied={}
        for key,sql in [('intake_cannot_approve',"UPDATE graph_review_results SET status='APPROVED' WHERE graph_version_id=$1"),
                        ('intake_cannot_delete','DELETE FROM graph_review_results WHERE graph_version_id=$1')]:
            try:
                async with c.transaction():await c.execute(sql,graph_id)
            except asyncpg.InsufficientPrivilegeError:denied[key]=True
            else:raise ValueError('Intake role exceeds intended permissions')
        # Roll back every probe row, audit and terminal tombstone together.
        probe=c.transaction();await probe.start()
        try:
            raw=copy.deepcopy(first_raw);raw['candidate_id']='rollback-probe:'+str(graph_id)
            rejected=first_result.model_copy(update=dict(candidate_id=raw['candidate_id'],candidate_sha256=digest(raw),status='REJECTED',reasons=['ERR_ROLLBACK_PROBE']))
            record=await store.save(raw,rejected,graph_id,actor,extraction_id=first_reviewed['extraction_id'])
            async def must_reject(name,sql,*params):
                try:
                    async with c.transaction():await c.execute(sql,*params)
                except asyncpg.PostgresError as exc:
                    if exc.sqlstate!='P0001':raise
                    denied[name]=True
                else:raise ValueError('Guard failed: '+name)
            await must_reject('terminal_state_cannot_be_reset',
                'UPDATE graph_review_candidate_state SET ever_rejected=false WHERE candidate_id=$1',raw['candidate_id'])
            await c.execute('RESET ROLE');await c.execute('SET LOCAL ROLE finmind_graph_reviewer')
            await must_reject('rejected_cannot_be_approved',
                "UPDATE graph_review_results SET status='APPROVED',revision=revision+1,reviewed_by=$2 WHERE review_id=$1",uuid.UUID(record['review_id']),ACTOR)
            await must_reject('candidate_is_immutable',
                "UPDATE graph_review_results SET candidate='{}'::jsonb,revision=revision+1,reviewed_by=$2 WHERE review_id=$1",uuid.UUID(record['review_id']),ACTOR)
        finally:await probe.rollback()
        report=dict(status='COMMITTED_INTAKE_ONLY' if args.apply else 'DRY_RUN_ROLLED_BACK',graph_version_id=str(graph_id),
            report_sha256=manifest['report_sha256'],registry_sha256=registry.sha256,counts=counts,
            input_records=len(candidates),conversion_blocked=len(deferred),
            reason_counts=dict(Counter(reason for r in results for reason in r.reasons)),checks=dict(idempotent_save=True,readback=True,**denied),
            human_approvals_created=0,neo4j_writes=0,publication_status='BLOCKED_NO_APPROVED_RELATIONS',
            audit_principal=dict(user_id=str(ACTOR),type='INACTIVE_AUTOMATION_NO_LOGIN_NOT_HUMAN_REVIEWER'))
        if args.apply:await tx.commit()
        else:await tx.rollback()
        (output/('receipt.json' if args.apply else 'dry-run.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
        (output/'candidates.json').write_text(json.dumps(candidates,ensure_ascii=False,indent=2),'utf-8')
        (output/'evaluations.json').write_text(json.dumps([r.model_dump(mode='json') for r in results],ensure_ascii=False,indent=2),'utf-8')
        (output/'conversion-blocked.json').write_text(json.dumps(deferred,ensure_ascii=False,indent=2),'utf-8')
        people={}
        for raw,reviewed in zip(candidates,manifest['records']):
            if reviewed['report_decision']=='REJECTED':continue
            for entity in (raw['subject'],raw['object']):
                if entity['entity_type']!='Person' or entity['resolution_status']=='resolved':continue
                entry=people.setdefault(entity['entity_id'],dict(entity_id=entity['entity_id'],entity_type='Person',
                    canonical_name=entity['canonical_name'],aliases=entity['aliases'],identity_key=None,verified=False,
                    source_entity_ids=[entity['entity_id']],source_document_ids=[],source_urls=[]))
                for ev in raw['evidence']:
                    if ev['document_id'] not in entry['source_document_ids']:entry['source_document_ids'].append(ev['document_id'])
                if reviewed['source_url'] not in entry['source_urls']:entry['source_urls'].append(reviewed['source_url'])
        (output/'person-registry-TO_VERIFY.json').write_text(json.dumps(list(people.values()),ensure_ascii=False,indent=2),'utf-8')
        (output/'registry-used.json').write_text(json.dumps(list(registry.rows.values()),ensure_ascii=False,indent=2),'utf-8')
        print(json.dumps(report,ensure_ascii=False),flush=True)
    except BaseException:
        await tx.rollback();raise
    finally:await c.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');p.add_argument('--registry',type=Path,default=REGISTRY)
    p.add_argument('--manifest',type=Path,default=ROOT/'outputs/person-neo4j-publish-20261103/review-manifest.json')
    p.add_argument('--output',type=Path,default=ROOT/'outputs/person-neo4j-publish-20261103/intake')
    asyncio.run(main(p.parse_args()))
