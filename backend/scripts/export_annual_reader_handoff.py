"""Read-only mapping export and live source-reader smoke for 20 annual reports."""
import argparse,asyncio,hashlib,json,uuid
from pathlib import Path
import asyncpg
from person_role_db import ROOT,dsn
from src.documents.release_identity import validate_document_binding
from src.documents.annual_source_reader import read_annual_chunk,resolve_annual_member_row
CORPUS='9f2a7f99-a034-52bc-aff1-9d267ffe6019'
OUT=ROOT/'outputs/annual-reader-alias-handoff-20261030'
async def main():
 OUT.mkdir(exist_ok=True);c=await asyncpg.connect(dsn(),timeout=15,command_timeout=120)
 mapping={};sample=[];count=0
 try:
  async with c.transaction(readonly=True,isolation='repeatable_read'):
   rows=await c.fetch('''SELECT t.chunk_id::text,t.document_id::text,t.index_version_id::text,
    t.locator_json,t.content_hash,t.page_number,d.title,d.source_url,co.symbol FROM text_chunks t JOIN documents d USING(document_id)
    JOIN companies co USING(company_id) JOIN corpus_versions cv USING(index_version_id)
    JOIN index_versions i ON i.index_version_id=t.index_version_id
    JOIN corpus_documents cd ON cd.document_id=d.document_id AND cd.corpus_version_id=cv.corpus_version_id AND cd.document_hash=d.sha256
    WHERE cv.corpus_version_id=$1 AND cv.status='FROZEN' AND i.status='ACTIVE' AND d.doc_type='ANNUAL_REPORT' AND t.superseded_at IS NULL ORDER BY co.symbol,d.title,t.chunk_index''',uuid.UUID(CORPUS))
   cache={}
   for r in rows:
    loc=json.loads(r['locator_json']) if isinstance(r['locator_json'],str) else r['locator_json']
    binding=validate_document_binding(r['document_id'],r['index_version_id'],loc);count+=1
    verified=await resolve_annual_member_row(c,r,CORPUS,cache)
    assert hashlib.sha256(verified['chunk_text'].encode()).hexdigest()==r['content_hash'].strip()
    if count%4000==0:print('Annual reader chunks replayed: '+str(count),flush=True)
    if r['document_id'] not in mapping:
     mapping[r['document_id']]=dict(**binding,symbol=r['symbol'],title=r['title'],reporting_year=loc.get('reporting_year'),
       source_table=loc['source_table'],source_id=loc['source_id'],chunk_count=0)
     data=await read_annual_chunk(c,r['chunk_id'],CORPUS,cache)
     assert hashlib.sha256(data['chunk_text'].encode()).hexdigest()==r['content_hash'].strip()
     sample.append(data)
    mapping[r['document_id']]['chunk_count']+=1
   assert count==17664 and len(mapping)==20
  package=dict(corpus_version_id=CORPUS,index_version_id=rows[0]['index_version_id'],rule='UUIDv5(NAMESPACE_URL, finmind:release-document:{index_version_id}:{source_document_id})',
    validated_chunks=count,documents=list(mapping.values()))
  for name,payload in [('document_mapping.json',package),('reader_samples.json',sample),
    ('verification.json',dict(status='PASS',database_writes=0,mapping_chunks_checked=count,document_pairs=len(mapping),live_reader_replays=len(sample),full_text_replays=count,source_and_text_hash_validation=True))]:
   (OUT/name).write_text(json.dumps(payload,ensure_ascii=False,indent=2),'utf-8')
  print(json.dumps(dict(status='PASS',chunks=count,document_pairs=len(mapping),live_reader_replays=len(sample),database_writes=0)))
 finally:await c.close()
if __name__=='__main__':
 parser=argparse.ArgumentParser()
 parser.add_argument('--corpus',default=CORPUS)
 parser.add_argument('--output-dir',default=str(OUT))
 args=parser.parse_args();CORPUS=str(uuid.UUID(args.corpus));OUT=Path(args.output_dir)
 asyncio.run(main())
