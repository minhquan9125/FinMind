"""Read prices belonging to one approved corpus; no live-table fallback or writes."""
import argparse
import asyncio
from datetime import date
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from src.core.config import get_settings
from src.documents.corpus_scope import load_scope,read_prices


async def main(args):
    import asyncpg
    settings=get_settings()
    corpus=args.corpus_version or settings.default_corpus_version_id
    if not corpus:raise ValueError('Choose --corpus-version; no default corpus is active')
    conn=await asyncpg.connect(settings.database_url,ssl='require',statement_cache_size=0,timeout=25,command_timeout=45)
    try:
        async with conn.transaction(readonly=True,isolation='repeatable_read'):
            scope=await load_scope(conn,corpus,expected_hash=settings.default_corpus_manifest_sha256 if not args.corpus_version else None)
            rows=await read_prices(conn,scope,args.symbol,args.start,args.end)
            # Prices remain scaled source values; callers must use price_scale explicitly.
            print(json.dumps(dict(database_writes=False,corpus_version_id=scope.corpus_version_id,
                count=len(rows),rows=rows),ensure_ascii=False,default=str))
    finally:
        if not conn.is_closed():await conn.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--symbol',required=True);p.add_argument('--corpus-version')
    p.add_argument('--start',type=date.fromisoformat);p.add_argument('--end',type=date.fromisoformat)
    asyncio.run(main(p.parse_args()))
