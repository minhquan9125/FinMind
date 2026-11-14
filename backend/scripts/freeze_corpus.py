"""Create WBS16 manifest from ingested chunks. Default: read only; --apply registers corpus."""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from src.documents.corpus_manifest import read_manifest, register_manifest


async def run(args):
    import asyncpg
    from dotenv import load_dotenv
    load_dotenv(ROOT / 'backend/.env')
    load_dotenv(ROOT / '.env')
    if not args.label or len(args.label) > 30:
        raise ValueError('Version label must contain 1 to 30 characters')
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = await asyncpg.connect(os.environ['DATABASE_URL'], ssl='require', statement_cache_size=0, timeout=25)
    try:
        async with conn.transaction(isolation='repeatable_read', readonly=not args.apply):
            if args.apply:
                # Keep the source snapshot stable until the registration commits.
                await conn.execute('LOCK TABLE public.documents, public.text_chunks IN SHARE MODE')
            result = await read_manifest(conn, args.index)
            if target.exists():
                if json.loads(target.read_text(encoding='utf-8')) != result:
                    raise ValueError('Output exists with different content; choose another path')
            else:
                # Persist the snapshot before registering its hash in the database.
                with target.open('x', encoding='utf-8') as stream:
                    json.dump(result, stream, ensure_ascii=False, indent=2)
                    stream.write('\n')
            registered = await register_manifest(conn, result, args.label) if args.apply else False
        print(json.dumps({'corpus_version_id': result['corpus_version_id'],
                          'manifest_sha256': result['manifest_sha256'],
                          'documents': result['manifest']['document_count'],
                          'chunks': result['manifest']['chunk_count'],
                          'mode': 'registered' if registered else ('already_registered' if args.apply else 'read_only'),
                          'file': str(target)}, ensure_ascii=False, indent=2))
    finally:
        await conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', default='1e029e66-0adf-53ac-8f28-431ed7312745')
    parser.add_argument('--label', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--apply', action='store_true')
    try:
        asyncio.run(run(parser.parse_args()))
    except Exception as exc:
        print(f'Freeze failed ({type(exc).__name__}): {exc}', file=sys.stderr)
        sys.exit(1)
