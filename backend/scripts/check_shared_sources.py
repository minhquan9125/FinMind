"""Member doctor for shared DB sources. No local snapshot or embedding needed."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from src.core.config import get_settings
from src.documents.corpus_scope import load_scope
from src.documents.shared_source import resolve_shared_source


async def main(args):
    import asyncpg
    settings=get_settings();corpus=args.corpus or settings.default_corpus_version_id
    if not corpus:raise ValueError('Choose --corpus or configure DEFAULT_CORPUS_VERSION_ID')
    conn=await asyncpg.connect(settings.database_url,ssl='require',statement_cache_size=0,timeout=25,command_timeout=45)
    result=dict(database_writes=False,local_snapshot_required=False,checks=0)
    try:
        async with conn.transaction(readonly=True,isolation='repeatable_read'):
            scope=await load_scope(conn,corpus,model=settings.embedding_model_ref,
                expected_hash=settings.default_corpus_manifest_sha256 if not args.corpus else None)
            result.update(corpus_version_id=scope.corpus_version_id,index_version_id=scope.index_version_id)
            cache={};last=None
            while True:
                rows=await conn.fetch('''SELECT t.chunk_id::text,t.locator_json,t.content_hash
                    FROM public.text_chunks t JOIN public.corpus_documents cd USING(document_id)
                    WHERE cd.corpus_version_id=$1 AND t.index_version_id=$2 AND t.superseded_at IS NULL
                      AND ($3::uuid IS NULL OR t.chunk_id>$3) ORDER BY t.chunk_id LIMIT 250''',
                    uuid.UUID(scope.corpus_version_id),uuid.UUID(scope.index_version_id),last)
                if not rows:break
                for row in rows:
                    loc=json.loads(row['locator_json']) if isinstance(row['locator_json'],str) else row['locator_json']
                    await resolve_shared_source(conn,scope.index_version_id,loc,row['content_hash'],cache)
                    result['checks']+=1
                last=uuid.UUID(rows[-1]['chunk_id'])
            if not result['checks']:raise ValueError('EMPTY_CORPUS')
            result['status']='PASS'
    finally:
        if not conn.is_closed():await conn.close()
    rendered=json.dumps(result)
    if args.output:
        Path(args.output).write_text(rendered,encoding='utf-8')
    print(rendered,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--corpus');p.add_argument('--output')
    try:asyncio.run(main(p.parse_args()))
    except Exception as exc:
        print('SHARED_SOURCE_CHECK_FAILED',getattr(exc,'code',type(exc).__name__),file=sys.stderr)
        raise SystemExit(1)
