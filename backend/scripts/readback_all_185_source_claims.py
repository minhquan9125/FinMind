"""Read-only reconciliation of every repaired source assertion after publication."""
import asyncio,json,os,uuid
from collections import Counter
import asyncpg
from neo4j import GraphDatabase
from person_role_db import ROOT,dsn
from src.graph_review.models import digest

OUT=ROOT/'outputs/person-all-185-20261104'

async def ledger_check(payload_id,checksum):
    c=await asyncpg.connect(dsn(),timeout=15)
    try:
        async with c.transaction(readonly=True):
            row=await c.fetchrow('SELECT sha256,payload FROM raw_payloads WHERE payload_id=$1',uuid.UUID(payload_id))
            data=json.loads(row['payload']) if isinstance(row['payload'],str) else row['payload']
            if row['sha256'].strip()!=checksum or digest(data)!=checksum:raise ValueError('Postgres ledger mismatch')
            old=await c.fetch("SELECT status,count(*) AS n FROM graph_review_results WHERE graph_version_id='89631a45-d8fe-532b-b190-dd74fff75811' GROUP BY status")
            counts={r['status']:r['n'] for r in old}
            if counts!={'PENDING':126,'REJECTED':2}:raise ValueError('Original review history changed')
            return dict(ledger_sha256_verified=True,original_review_counts=counts)
    finally:await c.close()

def main():
    receipt=json.loads((OUT/'publish-receipt.json').read_text('utf-8'));gid=receipt['graph_version_id']
    repairs=json.loads((OUT/'repairs.json').read_text('utf-8'))
    expected={r['origin_extraction_id']:r for r in repairs['records']}
    with GraphDatabase.driver(os.environ.get('NEO4J_URI','bolt://127.0.0.1:17687'),auth=(os.environ.get('NEO4J_USER','neo4j'),os.environ['NEO4J_PASSWORD']),connection_timeout=10) as driver:
        with driver.session(database=os.environ.get('NEO4J_DATABASE','neo4j')) as session:
            version=session.run('MATCH(v:SourcePersonGraphVersion {key:$gid}) RETURN v.status AS status,v.payload_sha256 AS sha',gid=gid).single()
            rows=[dict(r) for r in session.run('''MATCH(p:SourcePersonOccurrence)-[r:SOURCE_PERSON_CLAIM {graph_version_id:$gid}]-(c:SourcePersonCompany)
                RETURN p.name AS person,c.symbol AS company,r.origin_extraction_id AS id,properties(r) AS data,
                       startNode(r).key=c.key AS company_is_subject ORDER BY id''',gid=gid)]
            original=session.run("MATCH(v:GraphVersion {id:'93567c73-7bc7-5076-b609-0515980d37d7'}) OPTIONAL MATCH()-[r:GRAPH_RELATION {graph_version_id:v.id}]->() RETURN v.status AS status,count(r) AS edges").single()
        if not version or version['status']!='READY' or version['sha']!=receipt['payload_sha256']:raise ValueError('Source version not READY or hash differs')
        if len(rows)!=185 or {r['id'] for r in rows}!=set(expected):raise ValueError('Not all 185 claims were loaded exactly once')
        for row in rows:
            wanted=expected[row['id']];actual=row['data']
            if row['person']!=wanted['person_name'] or row['company']!=wanted['company']:raise ValueError('Person/company differs')
            if actual['claim_sha256']!=digest(wanted) or actual['position']!=wanted['position'] or actual['relation_type']!=wanted['relation_type']:raise ValueError('Corrected statement differs')
            if row['company_is_subject']!=(wanted['relation_type'] in ('APPOINTS','DISMISSES')):raise ValueError('Predicate direction differs')
            if json.loads(actual['evidence_json'])!=wanted['evidence']:raise ValueError('Evidence/locator differs')
            if actual['calendar_date_asserted'] is not False or actual['identity_scope']!='SOURCE_OCCURRENCE':raise ValueError('Unstated global identity/date')
        if not original or original['status']!='READY' or original['edges']!=2:raise ValueError('Original approved global version changed')
    pg=asyncio.run(ledger_check(receipt['ledger_payload_id'],receipt['payload_sha256']))
    result=dict(status='ALL_185_SOURCE_CLAIMS_READBACK_VERIFIED',graph_version_id=gid,total=185,excluded=0,
        by_company=dict(Counter(r['company'] for r in rows)),directions_verified=True,source_quotes_and_hashes_verified=True,
        scope='DOCUMENT_SCOPED_ASSERTIONS_NOT_185_GLOBAL_IDENTITIES',existing_global_approved_edges=2,postgres=pg,
        claims=[dict(extraction_id=r['id'],person=r['person'],company=r['company'],position=r['data']['position'],relation_type=r['data']['relation_type']) for r in rows])
    (OUT/'readback.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='claims'},ensure_ascii=False))

if __name__=='__main__':main()
