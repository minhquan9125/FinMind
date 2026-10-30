"""Test LAN-address login without printing credentials or retaining test data."""
import asyncio
import json
from pathlib import Path
import uuid

ROOT=Path(__file__).resolve().parents[2]


async def main():
    import asyncpg
    cfg=dict(l.split('=',1) for l in (ROOT/'docker/postgres/finmind_team.env.local').read_text().splitlines() if '=' in l)
    conn=await asyncpg.connect(cfg['DATABASE_URL'],timeout=15)
    report={'host':cfg['DB_HOST'],'port':int(cfg['DB_PORT']),'user':cfg['DB_USER'],
        'tested_from':'database host via its LAN IPv4; second-device test still required','passed':False}
    try:
        report['server_address']=str(await conn.fetchval('SELECT inet_server_addr()'))
        flags=dict(await conn.fetchrow('SELECT rolsuper,rolcreatedb,rolcreaterole,rolbypassrls FROM pg_roles WHERE rolname=current_user'))
        assert not any(flags.values())
        report['admin_flags']=flags
        assert await conn.fetchval("SELECT has_table_privilege(current_user,'public.text_chunks','SELECT,INSERT,UPDATE,DELETE')")
        assert not await conn.fetchval("SELECT has_table_privilege(current_user,'public.text_chunks','TRUNCATE')")
        assert not await conn.fetchval("SELECT has_schema_privilege(current_user,'public','CREATE')")
        report['public_dml_allowed']=True;report['truncate_and_schema_create_allowed']=False
        tx=conn.transaction();await tx.start()
        try:
            key=uuid.uuid4()
            await conn.execute('INSERT INTO public.roles(role_id,role_code) VALUES($1,$2)',key,'LAN_VERIFY')
            assert await conn.fetchval('SELECT count(*) FROM public.roles WHERE role_id=$1',key)==1
            await conn.execute('UPDATE public.roles SET description=$2 WHERE role_id=$1',key,'test rollback')
            await conn.execute('DELETE FROM public.roles WHERE role_id=$1',key)
        finally:await tx.rollback()
        public=await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname='public'")
        counts=[]
        for row in public:
            counts.append(await conn.fetchval('SELECT count(*) FROM public."'+row['tablename'].replace('"','""')+'"'))
        report['public_tables']=len(public);report['public_rows']=sum(counts)
        report['passed']=True
    finally:await conn.close()
    folder=ROOT/'outputs/docker-lan-20261027';folder.mkdir(parents=True,exist_ok=True)
    (folder/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report),flush=True)


if __name__=='__main__':asyncio.run(main())
