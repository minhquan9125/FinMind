"""Live audit of every report-accepted assertion, retaining all 185 outcomes."""
import asyncio,json,re,uuid,hashlib
from collections import Counter
from urllib.parse import urlsplit,urlunsplit
import asyncpg
from person_role_db import ROOT,dsn
from src.graph_review.sources import PostgresSourceReader
from src.graph_review.positions import position_supported
from src.person_role.evidence_spans import person_spans

OUT=ROOT/'outputs/person-all-185-20261104'
CORPUS='b2550a0b-c423-5c50-9b15-6fb6af12e2c6'

def compact(value):return ' '.join(value.split())
def urlkey(value):
    u=urlsplit(value or '');return urlunsplit((u.scheme,u.netloc,u.path,'','')).rstrip('/')

async def main():
    manifest=json.loads((ROOT/'outputs/person-neo4j-publish-20261103/review-manifest.json').read_text('utf-8'))
    records=[r for r in manifest['records'] if r['report_decision']=='APPROVED']
    if len(records)!=185:raise ValueError('Expected all 185 accepted source records')
    c=await asyncpg.connect(dsn(),timeout=15,command_timeout=120)
    results=[];cache={}
    try:
        async with c.transaction(readonly=True,isolation='repeatable_read'):
            await c.execute('SET LOCAL ROLE finmind_graph_writer')
            rows=await c.fetch('''SELECT g.extraction_id::text,g.document_id::text,g.source_span,g.validation_status,
                e.locator_json,d.title,d.source_url FROM graph_extractions g JOIN evidence e USING(extraction_id)
                JOIN documents d USING(document_id) WHERE g.extraction_id=ANY($1::uuid[])''',[uuid.UUID(r['extraction_id']) for r in records])
            byid={r['extraction_id']:dict(r) for r in rows}
            reader=PostgresSourceReader(c)
            ids=[]
            for row in rows:
                loc=json.loads(row['locator_json']) if isinstance(row['locator_json'],str) else row['locator_json']
                ids.extend(b['chunk_id'] for b in loc.get('corpus_binding',{}).get('chunk_bindings',[]))
            await reader.prefetch(ids,CORPUS)
            print(f'Prefetched source membership for {len(set(ids))} chunks',flush=True)
            for number,reviewed in enumerate(records,1):
                reviewed=dict(reviewed)
                reviewed['position']=reviewed['position'].strip().rstrip('.')
                row=byid[reviewed['extraction_id']]
                loc=json.loads(row['locator_json']) if isinstance(row['locator_json'],str) else row['locator_json']
                name=reviewed['object'] if reviewed['relation_type'] in ('APPOINTS','DISMISSES') else reviewed['subject']
                page=reviewed['pdf_page'];binding=loc.get('corpus_binding',{})
                chunk_ids=[b['chunk_id'] for b in binding.get('chunk_bindings',[])]
                rebinding=None
                if not chunk_ids:
                    matches=await c.fetch('''SELECT d.document_id::text,d.source_url,d.title FROM documents d
                        JOIN corpus_documents cd USING(document_id) WHERE cd.corpus_version_id=$1
                        AND (d.document_id=$2 OR d.source_url=$3)''',uuid.UUID(CORPUS),uuid.UUID(row['document_id']),reviewed['source_url'])
                    if not matches:
                        matches=await c.fetch('''SELECT d.document_id::text,d.source_url,d.title FROM documents d
                            JOIN corpus_documents cd USING(document_id) WHERE cd.corpus_version_id=$1 AND split_part(d.source_url,'?',1)=$2''',
                            uuid.UUID(CORPUS),urlkey(reviewed['source_url']))
                    matches={m['document_id']:m for m in matches}
                    if len(matches)==1:
                        doc=next(iter(matches.values()))
                        chunk_ids=[r['chunk_id'] for r in await c.fetch('''SELECT chunk_id::text FROM text_chunks WHERE document_id=$1 AND superseded_at IS NULL
                            AND ($2::integer IS NULL OR page_number=$2) ORDER BY chunk_index''',uuid.UUID(doc['document_id']),page)]
                        rebinding=dict(old_document_id=row['document_id'],new_document_id=doc['document_id'],basis='UNIQUE_CORPUS_DOCUMENT_AND_SOURCE_URL')
                verified=[];errors=[]
                for chunk_id in dict.fromkeys(chunk_ids):
                    try:
                        # Restore a savepoint if a source permission/query fails;
                        # a single failure must not invalidate later audit rows.
                        if ('wbs06-row',str(chunk_id),CORPUS) in reader.cache:
                            actual=await reader.read_current(chunk_id,CORPUS)
                        else:
                            async with c.transaction():actual=await reader.read_current(chunk_id,CORPUS)
                        verified.append(dict(document_id=actual.document_id,document_version=actual.document_version,
                            chunk_id=actual.chunk_id,corpus_id=actual.corpus_id,index_version_id=actual.index_version_id,
                            content_hash=actual.content_hash,source_sha256=actual.source_sha256,locator=actual.locator,text=actual.text))
                    except Exception as exc:errors.append(dict(chunk_id=chunk_id,code=getattr(exc,'code',type(exc).__name__)))
                text='\n'.join(v['text'].partition('\n')[2] if v['locator'].get('kind')=='db_text_span' else v['text'] for v in verified)
                source_match=bool(text) and (compact(reviewed['quote']) in compact(text) or compact(row['source_span']) in compact(text))
                raw_body_match=bool(text) and compact(text)==compact(row['source_span'])
                spans=[]
                for v in verified:
                    for span in person_spans(v['text'],name,[name]):
                        spans.append(dict(chunk_id=v['chunk_id'],**span,position_supported=position_supported(reviewed['position'],span['quote'])))
                item=dict(**reviewed,symbol=loc.get('symbol'),report_year=loc.get('year'),original_source_status=row['validation_status'],
                    original_source_span=row['source_span'],original_page_sha256=hashlib.sha256(row['source_span'].encode()).hexdigest(),
                    source_rebinding=rebinding,live_verified_chunks=verified,source_errors=errors,
                    checks=dict(has_live_source=bool(verified),all_source_reads_passed=bool(verified) and not errors,
                        reviewed_quote_or_span_present=source_match,full_page_matches=raw_body_match,
                        exact_person_name_present=compact(name).casefold() in compact(text).casefold(),
                        position_literal_or_alias_present=position_supported(reviewed['position'],text)),
                    exact_person_spans=spans,excluded=False)
                results.append(item)
                if number%5==0:print(f'Live source audit {number}/185',flush=True)
    finally:await c.close()
    summary=dict(total=185,excluded=0,by_company=dict(Counter(r['symbol'] for r in results)),
        checks={key:sum(r['checks'][key] for r in results) for key in results[0]['checks']},
        source_errors=dict(Counter(e['code'] for r in results for e in r['source_errors'])),
        database_writes=0,neo4j_writes=0)
    OUT.mkdir(exist_ok=True)
    (OUT/'live-source-audit.json').write_text(json.dumps(dict(summary=summary,records=results),ensure_ascii=False,indent=2),'utf-8')
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':asyncio.run(main())
