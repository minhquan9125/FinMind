"""Reproduce Nhan's original extractor at a pinned commit, using SELECT-only sources.

Never mistakes a compact handoff for a full envelope. No DB or Neo4j writes.
"""
import argparse
import asyncio
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
import asyncpg
from src.core.config import get_settings
from src.sprint4_runtime.bctn_source import read_verified_bctn_chunks
from src.graph_review.models import digest


def git_bytes(commit,path):
    return subprocess.check_output(['git','show',f'{commit}:{path}'],cwd=ROOT)


async def main(args):
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    package=out/'runtime'/'nhan_original_runtime';package.mkdir(parents=True,exist_ok=True)
    prefix='backend/src/sprint4_runtime/'
    paths=subprocess.check_output(['git','ls-tree','-r','--name-only',args.commit,'--',prefix],cwd=ROOT,text=True).splitlines()
    code_hashes={}
    for name in paths:
        relative=name[len(prefix):]
        if '/' in relative or Path(relative).suffix not in ('.py','.json'):continue
        data=git_bytes(args.commit,name);(package/relative).write_bytes(data)
        code_hashes[name]=hashlib.sha256(data).hexdigest()
    sys.path.insert(0,str(package.parent))
    extractor=importlib.import_module('nhan_original_runtime.relation_extractor').extract_candidates
    adapter=importlib.import_module('nhan_original_runtime.db_adapter').document_envelope
    registry=json.loads((package/'company.registry.20261030.r1.json').read_text('utf-8'))
    handoff=json.loads(git_bytes(args.commit,'docs/sprint4/WBS03-23-candidate-review.json'))
    documents=sorted({x['document']['document_id'] for x in handoff['candidates']})
    report=dict(commit=args.commit,corpus_id=handoff['corpus_id'],index_version_id=handoff['index_version_id'],
        database_writes=0,neo4j_writes=0,original_runtime_sha256=code_hashes,
        registry_sha256=hashlib.sha256((package/'company.registry.20261030.r1.json').read_bytes()).hexdigest(),
        reproduction_is_not_historical_output_file=True,documents=[],items=[])
    connection=await asyncpg.connect(get_settings().database_url,timeout=15,statement_cache_size=0)
    contexts={};all_rows={}
    try:
        async with connection.transaction(readonly=True,isolation='repeatable_read'):
            table=await connection.fetchval("SELECT to_regclass('graph_metadata.wbs03_envelopes')::text")
            report['original_envelope_table']=table
            if table and await connection.fetchval("SELECT has_table_privilege(current_user,'graph_metadata.wbs03_envelopes','SELECT')"):
                stored=await connection.fetch("""SELECT graph_version_id::text,content_sha256,payload
                    FROM graph_metadata.wbs03_envelopes WHERE corpus_version_id=$1
                    AND EXISTS(SELECT FROM jsonb_array_elements(payload->'relations') r
                     WHERE r->>'relation_type' IN ('HAS_SUBSIDIARY','HAS_ASSOCIATE','OWNS_SHARES','COOPERATES_WITH'))""",
                    __import__('uuid').UUID(handoff['corpus_id']))
                report['stored_company_envelope_count']=len(stored)
                for row in stored:
                    payload=json.loads(row['payload']) if isinstance(row['payload'],str) else row['payload']
                    (out/f"stored-{row['graph_version_id']}.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),'utf-8')
            for ordinal,doc_id in enumerate(documents,1):
                rows=await read_verified_bctn_chunks(connection,handoff['corpus_id'],document_id=doc_id)
                all_rows[doc_id]=rows
                original=extractor(adapter(rows,handoff['corpus_id']),registry)
                (out/f'{doc_id}.original-envelope.json').write_text(json.dumps(original,ensure_ascii=False,indent=2),'utf-8')
                by_id={r['relation_id']:r for r in original['relations']}
                entities={e['entity_id']:e for e in original['entities']}
                chunks={c['chunk_id']:c for c in original['chunks']}
                report['documents'].append(dict(document_id=doc_id,title=rows[0]['title'],chunks=len(rows),relations=len(by_id)))
                for compact in [c for c in handoff['candidates'] if c['document']['document_id']==doc_id]:
                    raw=by_id.get(compact['relation_id'])
                    if raw is None:
                        report['items'].append(dict(candidate_id=compact['relation_id'],reproduced=False));continue
                    evidence_key=lambda e:(e['document_id'],e['chunk_id'],e['quote'])
                    differences=[]
                    for key in ('relation_type','attributes','temporal'):
                        if raw[key]!=compact[key]:differences.append(key)
                    if {evidence_key(e) for e in raw['evidence']}!={evidence_key(e) for e in compact['evidence']}:differences.append('evidence')
                    item=dict(candidate_id=compact['relation_id'],document_id=doc_id,reproduced=True,
                        compact_differences=differences,relation=raw,subject=entities[raw['subject_id']],object=entities[raw['object_id']],
                        document=original['documents'][0])
                    report['items'].append(item)
                    contexts[compact['relation_id']]=[chunks[e['chunk_id']] for e in raw['evidence']]
                # Keep verified full source near legal/consolidation/date cues
                # for reviewer inspection; these are NOT automatically approved.
                import re
                interesting=[r for r in rows if re.search(r'công ty con|công ty liên kết|31/12/2024|31/12/2025|kiểm soát|hợp tác',r['text'],re.I)]
                (out/f'{doc_id}.review-context.json').write_text(json.dumps(interesting,ensure_ascii=False,indent=2,default=str),'utf-8')
                print(f"SOURCE_AND_ORIGINAL_EXTRACTOR {ordinal}/{len(documents)} chunks={len(rows)} relations={len(by_id)}",flush=True)
    finally:await connection.close()
    report['reproduced_count']=sum(x['reproduced'] for x in report['items'])
    report['identical_compact_relation_count']=sum(x['reproduced'] and not x['compact_differences'] for x in report['items'])
    (out/'original_reproduction.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    (out/'candidate_contexts.json').write_text(json.dumps(contexts,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('items','documents','original_runtime_sha256')},ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit',default='1f72ccdadc195bdd7539b91c7df7fe587f84bc09')
    parser.add_argument('--output',type=Path,required=True)
    asyncio.run(main(parser.parse_args()))
