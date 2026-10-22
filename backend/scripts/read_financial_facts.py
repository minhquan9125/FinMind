"""Read financial facts in READ ONLY REPEATABLE READ; never write Supabase."""
import argparse
import asyncio
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from src.core.config import get_settings
from src.financial.reader import read_financial_facts


async def main(args):
    import asyncpg
    conn=await asyncpg.connect(get_settings().database_url,ssl='require',statement_cache_size=0,timeout=25,command_timeout=30)
    try:
        tx=conn.transaction(readonly=True,isolation='repeatable_read')
        await tx.start()
        try:
            facts=await read_financial_facts(conn,args.symbol,args.period,
                config_version_id=args.config_version,report_id=args.report_id,
                source_family_name=getattr(args,'source_family',None),payload_id=getattr(args,'payload_id',None),
                corpus_version_id=getattr(args,'corpus_version',None) or getattr(get_settings(),'default_corpus_version_id',None),
                expected_corpus_hash=(getattr(get_settings(),'default_corpus_manifest_sha256',None)
                    if not getattr(args,'corpus_version',None) else None))
        except BaseException as original:
            # A failed rollback/closed connection must not hide the reader/query error.
            if not conn.is_closed():
                try:await tx.rollback()
                except Exception as cleanup:original.add_note(f'Rollback failed: {type(cleanup).__name__}')
            raise
        else:await tx.rollback()
        result=dict(database_writes=False,selected_config=args.config_version,
            selected_corpus=getattr(args,'corpus_version',None) or getattr(get_settings(),'default_corpus_version_id',None),
            selected_report=args.report_id,source_family=getattr(args,'source_family',None),
            selected_payload=getattr(args,'payload_id',None),count=len(facts),facts=facts)
        rendered=json.dumps(result,ensure_ascii=False,indent=2)
        if args.output:
            target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(rendered,encoding='utf-8')
            print(json.dumps({k:v for k,v in result.items() if k!='facts'}))
        else:print(rendered)
    finally:
        if not conn.is_closed():await conn.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--symbol',required=True);p.add_argument('--period',required=True)
    p.add_argument('--config-version',help='Explicit frozen configuration UUID; omitted means legacy only')
    p.add_argument('--report-id',help='Choose one exact report when several source/report versions exist')
    p.add_argument('--source-family',choices=['clean','normalized'],help='Explicit ingestion family; normalized groups sections from one payload/job')
    p.add_argument('--payload-id',help='Choose one exact source payload; never falls back to a different batch')
    p.add_argument('--corpus-version',help='Explicit registered/frozen corpus UUID; otherwise uses configured default if set')
    p.add_argument('--output',help='Optional UTF-8 JSON evidence file')
    try:asyncio.run(main(p.parse_args()))
    except Exception as exc:
        print('FINANCIAL_READ_FAILED',type(exc).__name__,str(exc),file=sys.stderr);raise SystemExit(1)
