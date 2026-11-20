"""Immutable document-scoped person assertions, distinct from global identity facts.

No GraphEntity/GRAPH_RELATION labels are used: this projection must not silently
enter the global-person READY graph or assert a current office/end date.
"""
import hashlib,json,uuid
from datetime import datetime,timezone
from ..graph_review.models import digest,Evidence
from ..graph_review.sources import compare_source
from ..person_role.source_claim_repairs import repair_claim

CONTRACT='person-source-claims-v1'
NS=uuid.UUID('159386cc-35e4-4b0e-8b9c-7777452541b4')

def packed(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))

def prepare_claim_batch(repairs,audit,manifest):
    accepted={r['extraction_id']:r for r in manifest['records'] if r['report_decision']=='APPROVED'}
    rows=repairs['records'];sources={c['chunk_id']:c for r in audit['records'] for c in r['live_verified_chunks']}
    originals={r['extraction_id']:r for r in audit['records']}
    names=list({r['object'] if r['relation_type'] in ('APPOINTS','DISMISSES') else r['subject'] for r in audit['records']})
    if len(rows)!=185 or {r['origin_extraction_id'] for r in rows}!=set(accepted):raise ValueError('Lossless 185-record scope required')
    for row in rows:
        xid=row['origin_extraction_id'];original=originals[xid]
        if row.get('excluded') or row['repair_status']!='SOURCE_FIELDS_REPAIRED':raise ValueError('Unrepaired claim cannot publish')
        if not all(original['checks'][k] for k in ('has_live_source','all_source_reads_passed','exact_person_name_present')):raise ValueError('Unverified source')
        if row['report_review_body_sha256']!=accepted[xid]['review_body_sha256']:raise ValueError('Source review changed')
        if digest(repair_claim(original,names))!=digest(row):raise ValueError('Repair differs from deterministic source derivation')
        if not row.get('evidence'):raise ValueError('Missing exact evidence')
        for ref in row['evidence']:
            source=sources[ref['chunk_id']]
            if source['text'][ref['quote_start']:ref['quote_end']]!=ref['quote']:raise ValueError('Quote/offset mismatch')
            if hashlib.sha256(source['text'].encode()).hexdigest()!=ref['content_hash']:raise ValueError('Source hash changed')
    body=dict(contract=CONTRACT,source_review_report_sha256=manifest['report_sha256'],claims=rows)
    checksum=digest(body);gid=str(uuid.uuid5(NS,checksum))
    companies={};people=[];relations=[]
    for row in rows:
        xid=row['origin_extraction_id'];person_key=gid+':person-occurrence:'+xid;company_key=gid+':company:'+row['company']
        companies[company_key]=dict(key=company_key,graph_version_id=gid,symbol=row['company'],name=row['company'])
        people.append(dict(key=person_key,graph_version_id=gid,name=row['person_name'],
            origin_extraction_id=xid,identity_scope='SOURCE_OCCURRENCE',global_identity_resolved=False))
        props=dict(key=gid+':claim:'+xid,graph_version_id=gid,origin_extraction_id=xid,
            relation_type=row['relation_type'],original_relation_type=row['original_relation_type'],
            position=row['position'],original_position=row['original_position'],
            source_url=row['source_url'],source_report_year=str(row['source_report_year']) if row['source_report_year'] else None,
            evidence_json=packed(row['evidence']),repair_notes_json=packed(row['repair_notes']),evidence_basis=row['evidence_basis'],
            source_review_status='APPROVED_IN_SOURCE_REPORT',identity_scope='SOURCE_OCCURRENCE',
            time_scope='SOURCE_DOCUMENT_NOT_CURRENT_OFFICE',calendar_date_asserted=False,
            report_review_body_sha256=row['report_review_body_sha256'],
            claim_sha256=digest(row))
        # Appointment/dismissal arrows preserve Company->Person semantics.
        props['semantic_subject']='Company' if row['relation_type'] in ('APPOINTS','DISMISSES') else 'Person'
        relations.append(dict(person_key=person_key,company_key=company_key,properties=props))
    return dict(graph_version_id=gid,payload_sha256=checksum,manifest=body,companies=list(companies.values()),people=people,relations=relations)

async def verify_live_claim_sources(batch,reader):
    refs=[ref for row in batch['manifest']['claims'] for ref in row['evidence']]
    grouped={}
    for ref in refs:grouped.setdefault(ref['corpus_id'],[]).append(ref['chunk_id'])
    for corpus,ids in grouped.items():await reader.prefetch(ids,corpus)
    for ref in refs:
        current=await reader.read_current(ref['chunk_id'],ref['corpus_id'])
        if current.verification_mode!='LIVE' or not current.active:raise ValueError('Live current sources required')
        values={k:ref[k] for k in Evidence.model_fields}
        compare_source(Evidence.model_validate(values),current)
        if current.text[ref['quote_start']:ref['quote_end']]!=ref['quote']:raise ValueError('Live quote offsets changed')
    return dict(unique_chunks=len({r['chunk_id'] for r in refs}),exact_evidence_spans=len(refs),source_replay='LIVE')

class SourcePersonClaimStore:
    def __init__(self,driver,database='neo4j'):self.driver,self.database=driver,database

    def publish(self,batch):
        with self.driver.session(database=self.database) as session:
            for name,label in [('source_person_claim_version','SourcePersonGraphVersion'),('source_person_occurrence','SourcePersonOccurrence'),('source_person_company','SourcePersonCompany')]:
                session.run(f'CREATE CONSTRAINT {name} IF NOT EXISTS FOR (n:{label}) REQUIRE n.key IS UNIQUE').consume()
            return session.execute_write(self._write,batch)

    @staticmethod
    def _write(tx,batch):
        gid=batch['graph_version_id']
        row=tx.run('''MERGE (v:SourcePersonGraphVersion {key:$gid})
            ON CREATE SET v.payload_sha256=$sha,v.status='BUILDING',v.contract=$contract,v.created_at=$now,
                          v.serving_scope='SOURCE_DOCUMENT_ASSERTIONS',v.global_identity_resolved=false
            SET v.lock=coalesce(v.lock,0)+1 RETURN v.payload_sha256 AS sha,v.status AS status''',
            gid=gid,sha=batch['payload_sha256'],contract=CONTRACT,now=datetime.now(timezone.utc).isoformat()).single(strict=True)
        if row['sha']!=batch['payload_sha256']:raise ValueError('Immutable source graph conflict')
        was_ready=row['status']=='READY'
        tx.run('''UNWIND $rows AS row MERGE (p:SourcePersonOccurrence {key:row.key}) ON CREATE SET p+=row''',rows=batch['people']).consume()
        tx.run('''UNWIND $rows AS row MERGE (c:SourcePersonCompany {key:row.key}) ON CREATE SET c+=row''',rows=batch['companies']).consume()
        for subject,pattern in [('Person','(p)-[r:SOURCE_PERSON_CLAIM {key:row.properties.key}]->(c)'),
                                ('Company','(c)-[r:SOURCE_PERSON_CLAIM {key:row.properties.key}]->(p)')]:
            rows=[r for r in batch['relations'] if r['properties']['semantic_subject']==subject]
            tx.run('''UNWIND $rows AS row MATCH(p:SourcePersonOccurrence {key:row.person_key})
                MATCH(c:SourcePersonCompany {key:row.company_key}) MERGE '''+pattern+' ON CREATE SET r+=row.properties',rows=rows).consume()
        actual=list(tx.run('''MATCH(p:SourcePersonOccurrence)-[r:SOURCE_PERSON_CLAIM {graph_version_id:$gid}]-(c:SourcePersonCompany)
            RETURN r.origin_extraction_id AS id,properties(r) AS data,p.key AS person_key,c.key AS company_key,
                   startNode(r).key AS subject_key,p.name AS person_name,c.symbol AS company_symbol ORDER BY id''',gid=gid))
        expected={r['properties']['origin_extraction_id']:r for r in batch['relations']}
        names={p['key']:p['name'] for p in batch['people']};symbols={c['key']:c['symbol'] for c in batch['companies']}
        found={r['id']:r for r in actual}
        if len(actual)!=len(expected) or set(found)!=set(expected):raise ValueError('Source claim reconciliation failed')
        for ident,row in found.items():
            wanted=expected[ident]
            if (row['person_key'],row['company_key'])!=(wanted['person_key'],wanted['company_key']):raise ValueError('Source occurrence endpoints changed')
            if row['subject_key']!=wanted['company_key' if wanted['properties']['semantic_subject']=='Company' else 'person_key']:raise ValueError('Source relation direction changed')
            if row['person_name']!=names[wanted['person_key']] or row['company_symbol']!=symbols[wanted['company_key']]:raise ValueError('Source person/company name changed')
            if any(row['data'].get(k)!=v for k,v in wanted['properties'].items()):raise ValueError('Immutable source claim properties changed')
        tx.run("MATCH(v:SourcePersonGraphVersion {key:$gid}) SET v.status='READY',v.claim_count=$count,v.company_count=$companies",gid=gid,count=len(found),companies=len(batch['companies'])).consume()
        return dict(status='READY_SOURCE_DOCUMENT_ASSERTIONS',graph_version_id=gid,claims=len(found),
            source_person_occurrences=len(batch['people']),companies=len(batch['companies']),
            changed_existing_global_graph=False,global_person_identities_inferred=0,
            idempotent_replay=was_ready)
