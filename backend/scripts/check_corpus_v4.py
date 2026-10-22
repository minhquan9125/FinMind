"""Member preflight and SELECT-only audit. Never registers or activates a release."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'backend/scripts')]
from src.documents.source_snapshot import load_source_snapshot
from src.documents.corpus_manifest import build_manifest,sha256
from ingest_corpus_v2 import validate_snapshot,identities

RELEASE=ROOT/'outputs/corpus-v4-clean-mapped-20261022'


def offline(folder,model):
    data=json.loads((folder/'ingest-manifest.json').read_text(encoding='utf-8'))
    validate_snapshot(data)
    source=json.loads((folder/'source-snapshot.json').read_text(encoding='utf-8'))
    release=json.loads((folder/'release-manifest.json').read_text(encoding='utf-8'))
    release_hash=release.pop('release_manifest_sha256')
    if sha256(release)!=release_hash or source['release_manifest_sha256']!=release_hash:
        raise ValueError('RELEASE_HASH_MISMATCH')
    if data['source_snapshot_id']!=source['source_snapshot_id'] or data['source_snapshot_sha256']!=release_hash:
        raise ValueError('SNAPSHOT_RELEASE_MISMATCH')
    snapshot=load_source_snapshot(folder/'source-snapshot.json')
    index,_,_=identities(data['manifest_sha256'],model)
    rows=[];expected={};kinds={};financial_rows=set()
    for doc in data['manifest']['documents']:
        _,did,_=identities(data['manifest_sha256'],model,doc['document_id'])
        doc_hash=hashlib.sha256(f'{index}:{doc["snapshot_sha256"]}'.encode()).hexdigest()
        for chunk in doc['chunks']:
            text=snapshot.resolve(chunk['locator'],chunk['content_hash'])
            if chunk['locator']['source_table']=='financial_reports':
                if 'đơn vị chưa xác minh' in text:raise ValueError('FINANCIAL_WARNING_REMAINS')
                financial_rows.update(chunk['locator']['row_keys'])
            _,_,cid=identities(data['manifest_sha256'],model,doc['document_id'],chunk['source_chunk_id'])
            expected[str(cid)]=dict(document_id=str(did),chunk=chunk)
            rows.append(dict(document_id=str(did),document_hash=doc_hash,doc_type=doc['doc_type'],
                title=doc['title'],external_id=doc['source_id'],source_url=None,chunk_id=str(cid),
                chunk_index=chunk['chunk_index'],chunk_text=text,content_hash=chunk['content_hash'],
                locator_json=chunk['locator'],dimensions=1024))
            kinds[doc['doc_type']]=kinds.get(doc['doc_type'],0)+1
    registered=build_manifest(dict(index_version_id=str(index),chunker_version='db-corpus-v2',
        chunk_size=130,chunk_overlap=0,embedding_model=model),rows)
    if len(financial_rows)!=72096:raise ValueError('CLEAN_ROW_COUNT_MISMATCH')
    return data,snapshot,expected,registered,kinds


async def run(args):
    from src.core.config import get_settings
    settings=get_settings();folder=Path(args.release).resolve()
    data,snapshot,expected,registered,kinds=offline(folder,settings.embedding_model_ref)
    index=registered['manifest']['index']['index_version_id']
    report=dict(database_writes=False,offline='PASS',index_version_id=index,
        proposed_corpus_version_id=registered['corpus_version_id'],registered_manifest_hash=registered['manifest_sha256'],
        documents=registered['manifest']['document_count'],expected=len(expected),types=kinds,
        database_checked=False,activation_ready=False,blockers=[])
    if args.database:
        import asyncpg
        conn=await asyncpg.connect(settings.database_url,ssl='require',statement_cache_size=0,timeout=25,command_timeout=45)
        try:
            async with conn.transaction(readonly=True,isolation='repeatable_read'):
                report['index_status']=await conn.fetchval('SELECT status FROM public.index_versions WHERE index_version_id=$1',uuid.UUID(index))
                last=None;seen=set();failures=[]
                while True:
                    rows=await conn.fetch('''SELECT chunk_id::text,document_id::text,chunk_index,content_hash,locator_json,
                        vector_dims(embedding) AS dimensions,-(embedding <#> embedding) AS norm_squared,superseded_at
                        FROM public.text_chunks WHERE index_version_id=$1 AND ($2::uuid IS NULL OR chunk_id>$2)
                        ORDER BY chunk_id LIMIT 250''',uuid.UUID(index),last)
                    if not rows:break
                    for row in rows:
                        key=row['chunk_id'];seen.add(key);item=expected.get(key)
                        try:
                            if item is None:raise ValueError('UNEXPECTED_CHUNK')
                            old=item['chunk'];loc=json.loads(row['locator_json']) if isinstance(row['locator_json'],str) else row['locator_json']
                            if (row['document_id']!=item['document_id'] or row['chunk_index']!=old['chunk_index']
                                or row['content_hash'].strip()!=old['content_hash'] or loc!=old['locator']
                                or row['dimensions']!=1024 or row['superseded_at'] is not None
                                or row['norm_squared'] is None or abs(row['norm_squared']-1)>=.001):
                                raise ValueError('STORED_CHUNK_MISMATCH')
                            snapshot.resolve(loc,row['content_hash'])
                        except Exception as exc:failures.append(dict(chunk_id=key,reason=getattr(exc,'code',str(exc))))
                    last=uuid.UUID(rows[-1]['chunk_id'])
                report.update(database_checked=True,stored=len(seen),missing=len(expected.keys()-seen),failures=failures)
                if seen!=expected.keys():report['blockers'].append('INCOMPLETE_INGEST')
                if failures:report['blockers'].append('VECTOR_OR_SOURCE_FAILURE')
                docs=await conn.fetch('''SELECT document_id::text,sha256 FROM public.documents WHERE document_id=ANY($1::uuid[])''',
                    [uuid.UUID(d['document_id']) for d in registered['manifest']['documents']])
                expected_docs={d['document_id']:d['document_hash'] for d in registered['manifest']['documents']}
                actual_docs={r['document_id']:r['sha256'].strip() for r in docs}
                report['missing_documents']=len(expected_docs.keys()-actual_docs.keys())
                if report['missing_documents']:report['blockers'].append('DOCUMENTS_NOT_YET_INGESTED')
                if any(actual_docs[k]!=expected_docs[k] for k in actual_docs):report['blockers'].append('DOCUMENT_HASH_MISMATCH')
                existing=await conn.fetch('''SELECT corpus_version_id::text,version_label,manifest_sha256,status,index_version_id::text
                    FROM public.corpus_versions WHERE version_label=$1 OR corpus_version_id=$2''',
                    'corpus-v4-clean-mapped',uuid.UUID(registered['corpus_version_id']))
                report['registrations']=[dict(r) for r in existing]
                if args.runtime:
                    if len(existing)!=1 or existing[0]['corpus_version_id']!=registered['corpus_version_id'] or existing[0]['manifest_sha256'].strip()!=registered['manifest_sha256'] or existing[0]['status']!='FROZEN' or existing[0]['index_version_id']!=index:
                        report['blockers'].append('REGISTRATION_NOT_READY')
                    if report['index_status']!='ACTIVE':report['blockers'].append('INDEX_NOT_ACTIVE')
        finally:
            if not conn.is_closed():await conn.close()
    else:report['blockers'].append('DATABASE_NOT_CHECKED')
    if args.runtime:
        path=Path(settings.source_snapshot_path or '')
        if not path.is_absolute():path=Path.cwd()/path
        if settings.default_corpus_version_id!=registered['corpus_version_id'] or settings.default_corpus_manifest_sha256!=registered['manifest_sha256']:
            report['blockers'].append('DEFAULT_CONFIG_MISMATCH')
        if settings.source_read_backend == 'supabase':
            report['runtime_source_backend']='supabase'
        elif not path.is_file() or hashlib.sha256(path.read_bytes()).digest()!=hashlib.sha256((folder/'source-snapshot.json').read_bytes()).digest():
            report['blockers'].append('RUNTIME_SNAPSHOT_MISMATCH')
    report['activation_ready']=report['database_checked'] and not report['blockers']
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    (out/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    (out/'registration-manifest.proposed.json').write_text(json.dumps(registered,ensure_ascii=False,indent=2),encoding='utf-8')
    checks={name:hashlib.sha256((folder/name).read_bytes()).hexdigest() for name in ('source-snapshot.json','ingest-manifest.json','release-manifest.json')}
    (out/'checksums.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    (out/'runtime.env.proposed').write_text(f'# Apply only after registration, source audit and API checks pass.\nDEFAULT_CORPUS_VERSION_ID={registered["corpus_version_id"]}\nDEFAULT_CORPUS_MANIFEST_SHA256={registered["manifest_sha256"]}\nSOURCE_READ_BACKEND=supabase\nSOURCE_SNAPSHOT_PATH=\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True,default=str),flush=True)
    return 0 if report['activation_ready'] else 2


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--release',default=str(RELEASE));p.add_argument('--database',action='store_true')
    p.add_argument('--runtime',action='store_true',help='Also require registered ACTIVE release and matching runtime configuration')
    p.add_argument('--output',default=str(ROOT/'outputs/corpus-v4-member-handoff-20261022'))
    try:raise SystemExit(asyncio.run(run(p.parse_args())))
    except Exception as exc:
        print('V4_CHECK_FAILED',getattr(exc,'code',type(exc).__name__),file=sys.stderr)
        raise SystemExit(1)
