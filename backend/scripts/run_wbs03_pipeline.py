"""Registered DB chunks -> WBS02/03 rules -> immutable PostgreSQL drafts."""
import argparse,asyncio,json,uuid
from pathlib import Path
import asyncpg
from person_role_db import ROOT,dsn
from src.person_role.wbs03_repository import build_db_envelope,WBS03Repository
from src.person_role.extractor import normalize_and_extract
from src.person_role.review import review_source,build_review_envelope

REGISTRY=ROOT/'backend/resources/person_role/company.registry.json'
async def extract_registered(c,corpus,chunk_ids,review_candidates=False):
 envelope=await build_db_envelope(c,corpus,chunk_ids)
 registry=json.loads(REGISTRY.read_text('utf-8'))
 if not review_candidates:return normalize_and_extract(envelope,registry)
 items=[]
 for ch in envelope['chunks']:
  raw=await c.fetchval('SELECT locator_json FROM text_chunks WHERE chunk_id=$1',uuid.UUID(ch['chunk_id']))
  source=dict(content_hash=ch['locator']['content_hash'],corpus_version_id=corpus,index_version_id=envelope['dataset_version'],document_id=ch['document_id'],chunk_id=ch['chunk_id'],page_number=ch['locator']['page'],locator_json=json.loads(raw))
  items.extend(review_source(ch['text'],source))
 return build_review_envelope(envelope,items,registry)

async def main(args):
 c=await asyncpg.connect(dsn(),timeout=15,command_timeout=90)
 try:
  async with c.transaction(isolation='repeatable_read'):
   await c.execute('SET LOCAL ROLE finmind_graph_writer')
   if args.input:payload=json.loads(args.input.read_text('utf-8'));audit={'mode':'existing-WBS03-envelope'}
   else:payload,audit=await extract_registered(c,args.corpus,args.chunk,args.review_candidates)
   repo=WBS03Repository(c)
   if args.apply:result=await repo.save(payload)
   else:
    await repo.verify_sources(payload);result=dict(status='SOURCE_VERIFIED_DRY_RUN',relations=len(payload['relations']),chunks=len(payload['chunks']),database_writes=0)
  args.output.mkdir(parents=True,exist_ok=True)
  for name,obj in [('envelope.json',payload),('audit.json',audit),('result.json',result)]:
   (args.output/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),'utf-8')
  print(json.dumps(result))
 finally:await c.close()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path);p.add_argument('--corpus',default='b2550a0b-c423-5c50-9b15-6fb6af12e2c6');p.add_argument('--chunk',action='append',default=[])
 p.add_argument('--review-candidates',action='store_true');p.add_argument('--apply',action='store_true');p.add_argument('--output',type=Path,required=True)
 args=p.parse_args()
 if bool(args.input)==bool(args.chunk):p.error('Supply --input or one/more --chunk, exclusively')
 asyncio.run(main(args))
