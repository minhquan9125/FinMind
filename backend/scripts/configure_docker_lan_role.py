"""Provision a non-admin development login on LOCAL Docker only; no seed data."""
import argparse
import asyncio
import json
from pathlib import Path
import re
import secrets
import sys
from urllib.parse import quote
import uuid

ROOT=Path(__file__).resolve().parents[2]


async def main(args):
    import asyncpg
    if not re.fullmatch(r'[a-z][a-z0-9_]{2,40}',args.user):raise ValueError('Invalid role name')
    folder=ROOT/'docker/postgres'
    admin=dict(l.split('=',1) for l in (folder/'.env').read_text().splitlines() if '=' in l and not l.startswith('#'))
    credential=folder/(args.user+'.env.local')
    if credential.exists():
        values=dict(l.split('=',1) for l in credential.read_text().splitlines() if '=' in l)
        password=values['DB_PASSWORD']
    else:password=secrets.token_hex(24)
    def dsn(user,pwd,host):return 'postgresql://'+quote(user,safe='')+':'+quote(pwd,safe='')+'@'+host+':'+admin['POSTGRES_PORT']+'/'+admin['POSTGRES_DB']
    conn=await asyncpg.connect(dsn(admin['POSTGRES_USER'],admin['POSTGRES_PASSWORD'],'127.0.0.1'),timeout=15)
    try:
        async with conn.transaction():
            await conn.execute("DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='finmind_developer') THEN CREATE ROLE finmind_developer NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS; END IF; END $$")
            role='"'+args.user+'"'
            if not await conn.fetchval('SELECT 1 FROM pg_roles WHERE rolname=$1',args.user):
                await conn.execute(f'CREATE ROLE {role} LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS CONNECTION LIMIT 20')
            password_literal="'"+password.replace("'","''")+"'"
            await conn.execute(f'ALTER ROLE {role} WITH LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD {password_literal}')
            await conn.execute(f'GRANT finmind_developer TO {role}')
            await conn.execute('GRANT CONNECT ON DATABASE "'+admin['POSTGRES_DB'].replace('"','""')+'" TO finmind_developer')
            await conn.execute('GRANT USAGE ON SCHEMA public TO finmind_developer')
            await conn.execute('GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO finmind_developer')
            await conn.execute('GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO finmind_developer')
            tables=await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
            for t in tables:
                table='public."'+t['tablename'].replace('"','""')+'"'
                exists=await conn.fetchval("SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename=$1 AND policyname='finmind_lan_development'",t['tablename'])
                if not exists:await conn.execute('CREATE POLICY finmind_lan_development ON '+table+' FOR ALL TO finmind_developer USING (true) WITH CHECK (true)')
            # Chat history remains owner-scoped via the existing SET LOCAL ROLE path.
            await conn.execute(f'GRANT finmind_chat_runtime TO {role} WITH INHERIT FALSE')
            await conn.execute('GRANT USAGE ON SCHEMA research_chat TO finmind_developer')
            await conn.execute('GRANT SELECT ON research_chat.schema_migrations TO finmind_developer')
    finally:await conn.close()
    lan_dsn=dsn(args.user,password,args.host)
    credential.write_text('DATABASE_URL='+lan_dsn+'\nDB_HOST='+args.host+'\nDB_PORT='+admin['POSTGRES_PORT']+'\nDB_NAME='+admin['POSTGRES_DB']+'\nDB_USER='+args.user+'\nDB_PASSWORD='+password+'\nRESEARCH_WARMUP_ENABLED=false\n',encoding='utf-8')
    # Exercise RLS and DML inside a transaction that is always rolled back.
    test=await asyncpg.connect(dsn(args.user,password,'127.0.0.1'),timeout=15)
    try:
        flags=await test.fetchrow('SELECT rolsuper,rolcreatedb,rolcreaterole,rolbypassrls FROM pg_roles WHERE rolname=current_user')
        if any(flags.values()):raise ValueError('Development account has elevated rights')
        tx=test.transaction();await tx.start()
        try:
            rid=uuid.uuid4()
            await test.execute('INSERT INTO public.roles(role_id,role_code,description) VALUES($1,$2,$3)',rid,'LAN_PROBE','rolled back connectivity test')
            assert await test.fetchval('SELECT count(*) FROM public.roles WHERE role_id=$1',rid)==1
            await test.execute('UPDATE public.roles SET description=$2 WHERE role_id=$1',rid,'updated')
            await test.execute('DELETE FROM public.roles WHERE role_id=$1',rid)
            await test.execute('SET LOCAL ROLE finmind_chat_runtime')
            await test.fetchval("SELECT set_config('app.chat_user_id',$1,true)",str(uuid.uuid4()))
            await test.fetchval('SELECT count(*) FROM research_chat.conversations')
        finally:await tx.rollback()
    finally:await test.close()
    print(json.dumps(dict(user=args.user,host=args.host,port=int(admin['POSTGRES_PORT']),database=admin['POSTGRES_DB'],admin=False,crud_and_chat_role_test_passed=True,data_rows_added=0,credentials_file=str(credential.relative_to(ROOT)))),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--user',default='finmind_team');p.add_argument('--host',required=True)
    try:asyncio.run(main(p.parse_args()))
    except Exception as e:print('LAN account setup failed:',type(e).__name__,flush=True);sys.exit(1)
