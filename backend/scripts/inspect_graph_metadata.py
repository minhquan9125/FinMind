import asyncio,json
import asyncpg
from person_role_db import dsn,ROOT
async def main():
 c=await asyncpg.connect(dsn(),timeout=15)
 try:
  out={}
  for key,q in {
   'identity':"SELECT current_user,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user",
   'columns':"SELECT table_schema,table_name,column_name,data_type FROM information_schema.columns WHERE table_schema='public' AND table_name IN ('graph_versions','graph_extractions','evidence','quarantine_records') ORDER BY table_name,ordinal_position",
   'rls':"SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class JOIN pg_namespace n ON n.oid=relnamespace WHERE n.nspname='public' AND relname IN ('graph_versions','graph_extractions','evidence','quarantine_records','text_chunks','documents')",
   'policies':"SELECT schemaname,tablename,policyname,roles,cmd FROM pg_policies WHERE tablename IN ('graph_versions','graph_extractions','evidence','quarantine_records')",
   'roles':"SELECT rolname,rolsuper,rolbypassrls FROM pg_roles WHERE rolname LIKE 'finmind%'",
   'constraints':"SELECT conname,pg_get_constraintdef(oid) AS definition FROM pg_constraint WHERE conrelid IN ('public.graph_extractions'::regclass,'public.evidence'::regclass)"}.items():out[key]=[dict(r) for r in await c.fetch(q)]
  p=ROOT/'outputs/graph-metadata-20261030';p.mkdir(exist_ok=True);(p/'schema-before.json').write_text(json.dumps(out,indent=2,default=str),'utf-8')
  print(json.dumps({k:v for k,v in out.items() if k not in ('columns','constraints')},default=str))
 finally:await c.close()
asyncio.run(main())
