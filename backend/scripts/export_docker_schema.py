"""Read application catalogs only; export empty portable PostgreSQL schema.

Supports the observed regular-table schema, with defaults, constraints,
indexes and RLS. Refuses unsupported object kinds rather than omit them.
No SELECT from application tables, COPY data, INSERT or sequence values.
"""
import asyncio
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
SCHEMAS=['public','research_chat']


def quote(value):return '"'+value.replace('"','""')+'"'
def name(schema,table):return quote(schema)+'.'+quote(table)


async def main():
    import asyncpg
    from src.core.config import get_settings
    c=await asyncpg.connect(get_settings().database_url,ssl='require',timeout=25,statement_cache_size=0)
    try:
        async with c.transaction(readonly=True,isolation='repeatable_read'):
            await c.execute("SET LOCAL search_path = pg_catalog")
            version=await c.fetchval("SELECT current_setting('server_version')")
            tables=await c.fetch("SELECT c.oid,n.nspname AS schema,c.relname,c.relkind::text AS kind,c.relispartition,c.relrowsecurity,c.relforcerowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=ANY($1::text[]) AND c.relkind IN ('r','p','v','m','f','S') ORDER BY 2,3",SCHEMAS)
            if any(t['kind']!='r' or t['relispartition'] for t in tables):raise ValueError('Use pg_dump: unsupported relation kind')
            functions=await c.fetchval("SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=ANY($1::text[]) AND NOT EXISTS(SELECT 1 FROM pg_depend d WHERE d.classid='pg_proc'::regclass AND d.objid=p.oid AND d.deptype='e')",SCHEMAS)
            types=await c.fetchval("SELECT count(*) FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace WHERE n.nspname=ANY($1::text[]) AND t.typtype IN ('e','d') AND NOT EXISTS(SELECT 1 FROM pg_depend d WHERE d.classid='pg_type'::regclass AND d.objid=t.oid AND d.deptype='e')",SCHEMAS)
            triggers=await c.fetchval("SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=ANY($1::text[]) AND NOT t.tgisinternal",SCHEMAS)
            if functions or types or triggers:raise ValueError('Use pg_dump: application routines/types/triggers detected')
            lines=['-- Schema-only snapshot of live Supabase application catalogs. No table data.',
                '-- Source PostgreSQL '+version,'BEGIN;','CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;',
                'CREATE SCHEMA IF NOT EXISTS research_chat;',
                "DO $roles$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='finmind_chat_runtime') THEN CREATE ROLE finmind_chat_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS; END IF; END $roles$;",
                'GRANT finmind_chat_runtime TO CURRENT_USER;',
                'GRANT USAGE ON SCHEMA research_chat TO finmind_chat_runtime;']
            inventory=[];foreign=[];indexes=[];optional=[];count_constraints=0
            for t in tables:
                full=name(t['schema'],t['relname'])
                cols=await c.fetch('''SELECT a.attname,format_type(a.atttypid,a.atttypmod) AS type,a.attnotnull,
                    a.attidentity::text AS identity,a.attgenerated::text AS generated,pg_get_expr(d.adbin,d.adrelid) AS default_expr
                    FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
                    WHERE a.attrelid=$1 AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum''',t['oid'])
                if any(x['identity'] for x in cols):raise ValueError('Identity sequence requires pg_dump')
                column_sql=[]
                for col in cols:
                    sql=quote(col['attname'])+' '+col['type']
                    if col['generated']:
                        sql+=' GENERATED ALWAYS AS ('+col['default_expr']+') STORED'
                    elif col['default_expr']:sql+=' DEFAULT '+col['default_expr']
                    if col['attnotnull']:sql+=' NOT NULL'
                    column_sql.append(sql)
                lines.append('CREATE TABLE '+full+' (\n    '+',\n    '.join(column_sql)+'\n);')
                cons=await c.fetch('SELECT conname,contype::text AS kind,pg_get_constraintdef(oid,true) AS definition FROM pg_constraint WHERE conrelid=$1 ORDER BY conname',t['oid'])
                for con in cons:
                    stmt='ALTER TABLE '+full+' ADD CONSTRAINT '+quote(con['conname'])+' '+con['definition']+';'
                    (foreign if con['kind']=='f' else lines).append(stmt)
                    count_constraints+=1
                idx=await c.fetch("SELECT i.indexrelid,pg_get_indexdef(i.indexrelid) AS definition,am.amname FROM pg_index i JOIN pg_class ic ON ic.oid=i.indexrelid JOIN pg_am am ON am.oid=ic.relam WHERE i.indrelid=$1 AND NOT EXISTS(SELECT 1 FROM pg_constraint co WHERE co.conindid=i.indexrelid AND co.contype IN ('p','u','x')) ORDER BY ic.relname",t['oid'])
                for ix in idx:(optional if ix['amname']=='hnsw' else indexes).append(ix['definition']+';')
                inventory.append(dict(schema=t['schema'],table=t['relname'],columns=[dict(x) for x in cols],constraints=len(cons),rls=t['relrowsecurity'],force_rls=t['relforcerowsecurity']))
            lines.extend(foreign);lines.extend(indexes)
            for t in tables:
                full=name(t['schema'],t['relname'])
                if t['relrowsecurity']:lines.append('ALTER TABLE '+full+' ENABLE ROW LEVEL SECURITY;')
                if t['relforcerowsecurity']:lines.append('ALTER TABLE '+full+' FORCE ROW LEVEL SECURITY;')
            policies=await c.fetch('SELECT * FROM pg_policies WHERE schemaname=ANY($1::text[]) ORDER BY schemaname,tablename,policyname',SCHEMAS)
            for p in policies:
                if any(r not in ('public','finmind_chat_runtime') for r in p['roles']):raise ValueError('Unexpected platform policy role')
                roles=', '.join('PUBLIC' if r=='public' else quote(r) for r in p['roles'])
                stmt='CREATE POLICY '+quote(p['policyname'])+' ON '+name(p['schemaname'],p['tablename'])+' AS '+p['permissive']+' FOR '+p['cmd']+' TO '+roles
                if p['qual']:stmt+=' USING ('+p['qual']+')'
                if p['with_check']:stmt+=' WITH CHECK ('+p['with_check']+')'
                lines.append(stmt+';')
            grants=await c.fetch("SELECT table_schema,table_name,privilege_type FROM information_schema.role_table_grants WHERE grantee='finmind_chat_runtime' AND table_schema=ANY($1::text[]) ORDER BY 1,2,3",SCHEMAS)
            for g in grants:lines.append('GRANT '+g['privilege_type']+' ON TABLE '+name(g['table_schema'],g['table_name'])+' TO finmind_chat_runtime;')
            lines.append('COMMIT;')
    finally:await c.close()
    folder=ROOT/'docker/postgres';(folder/'init').mkdir(parents=True,exist_ok=True);(folder/'optional').mkdir(exist_ok=True)
    schema='\n\n'.join(lines)+'\n'
    if any(token in schema.upper() for token in ('INSERT INTO ','COPY PUBLIC.','SELECT PG_CATALOG.SETVAL')):raise ValueError('Unexpected data statement')
    (folder/'init/010_schema.sql').write_text(schema,encoding='utf-8')
    (folder/'optional/enable_hnsw.sql').write_text('-- Optional after bulk loading; vectors work without this index.\n'+'\n'.join(optional)+'\n',encoding='utf-8')
    receipt=dict(source_postgres_version=version,schemas=SCHEMAS,table_count=len(tables),constraint_count=count_constraints,
        regular_index_count=len(indexes),optional_hnsw_count=len(optional),policy_count=len(policies),
        database_writes=False,table_data_exported=False,source_sha256=hashlib.sha256(schema.encode()).hexdigest(),tables=inventory,
        excluded='Supabase-managed auth/storage/vault/realtime; platform grants/owners/passwords; extension internal objects; data/seeds/sequence values')
    (folder/'schema_inventory.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in receipt.items() if k!='tables'}),flush=True)


if __name__=='__main__':asyncio.run(main())
