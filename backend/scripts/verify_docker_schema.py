"""Compare empty local Docker DB against exported schema metadata."""
import asyncio
import json
from pathlib import Path
import sys
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[2]


async def main():
    import asyncpg
    expected=json.loads((ROOT/'docker/postgres/schema_inventory.json').read_text(encoding='utf-8'))
    config=dict(line.split('=',1) for line in (ROOT/'docker/postgres/.env').read_text().splitlines() if '=' in line and not line.startswith('#'))
    dsn='postgresql://'+quote(config['POSTGRES_USER'],safe='')+':'+quote(config['POSTGRES_PASSWORD'],safe='')+'@127.0.0.1:'+config['POSTGRES_PORT']+'/'+config['POSTGRES_DB']
    conn=await asyncpg.connect(dsn,timeout=15)
    report=dict(passed=False,table_count=0,empty_tables=0,column_mismatches=[],constraint_mismatches=[],rls_mismatches=[])
    try:
        async with conn.transaction(readonly=True):
            await conn.execute('SET LOCAL search_path=pg_catalog')
            tables=await conn.fetch("SELECT c.oid,n.nspname AS schema,c.relname,c.relrowsecurity,c.relforcerowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=ANY($1::text[]) AND c.relkind='r' ORDER BY 2,3",expected['schemas'])
            report['table_count']=len(tables)
            assert {(t['schema'],t['relname']) for t in tables}=={(t['schema'],t['table']) for t in expected['tables']}
            for table,original in zip(tables,expected['tables']):
                cols=[dict(x) for x in await conn.fetch('''SELECT a.attname,format_type(a.atttypid,a.atttypmod) AS type,a.attnotnull,
                    a.attidentity::text AS identity,a.attgenerated::text AS generated,pg_get_expr(d.adbin,d.adrelid) AS default_expr
                    FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
                    WHERE a.attrelid=$1 AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum''',table['oid'])]
                if cols!=original['columns']:report['column_mismatches'].append(table['relname'])
                if await conn.fetchval('SELECT count(*) FROM pg_constraint WHERE conrelid=$1',table['oid'])!=original['constraints']:report['constraint_mismatches'].append(table['relname'])
                if (table['relrowsecurity'],table['relforcerowsecurity'])!=(original['rls'],original['force_rls']):report['rls_mismatches'].append(table['relname'])
                full='"'+table['schema']+'"."'+table['relname']+'"'
                if await conn.fetchval('SELECT count(*) FROM '+full)==0:report['empty_tables']+=1
            report['policies']=await conn.fetchval('SELECT count(*) FROM pg_policies WHERE schemaname=ANY($1::text[])',expected['schemas'])
            report['vector_version']=await conn.fetchval("SELECT extversion FROM pg_extension WHERE extname='vector'")
            report['hnsw_created']=bool(await conn.fetchval("SELECT to_regclass('public.idx_text_chunks_embedding_hnsw') IS NOT NULL"))
            report['cosine_distance']=await conn.fetchval("SELECT '[1,0,0]'::public.vector OPERATOR(public.<=>) '[1,0,0]'::public.vector")
            report['passed']=bool(report['empty_tables']==expected['table_count'] and not any(report[k] for k in ('column_mismatches','constraint_mismatches','rls_mismatches')) and report['policies']==expected['policy_count'] and report['cosine_distance']==0 and not report['hnsw_created'])
    finally:await conn.close()
    out=ROOT/'outputs/docker-schema-20261027';out.mkdir(parents=True,exist_ok=True)
    (out/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':asyncio.run(main())
