"""Prepare corpus-v2 release evidence. SELECT-only; no apply/activation mode exists."""
import argparse
import asyncio
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'backend/scripts')]
from ingest_corpus_v2 import identities,validate_snapshot
from src.core.config import get_settings
from src.documents import db_source
from src.documents.db_chunking import company_documents,financial_documents,price_documents,chunk_document
from src.documents.corpus_manifest import NAMESPACE,sha256
from src.documents.renderer_context import read_renderer_context
from src.documents.corpus_scope import fact_value_hash,price_value_hash
from src.financial import exact_json


def membership_ids(snapshot):
    facts=set();prices=set();owners={}
    for doc in snapshot['manifest']['documents']:
        keys={key for c in doc['chunks'] for key in c['locator']['row_keys']}
        if doc['source_table']=='financial_reports':
            for key in keys:
                uuid.UUID(key)
                if key in owners and owners[key]!=doc['source_id']:raise ValueError('Observation in multiple reports')
                owners[key]=doc['source_id'];facts.add(key)
        if doc['source_table']=='price_bars':
            for key in keys:
                try:uuid.UUID(key)
                except ValueError:
                    if not key.endswith(':summary'):raise ValueError('Unexpected synthetic price row key')
                else:prices.add(key)
    return facts,prices,owners


async def load_recovered_sources(conn, recovery_path):
    """Load immutable source documents from the read-only recovery evidence."""
    if not recovery_path.exists():
        return {}
    recovery=json.loads(recovery_path.read_text(encoding='utf-8'))
    if recovery.get('database_writes') is not False:
        raise ValueError('Recovery evidence must be SELECT-only')
    bindings=recovery.get('bindings', [])
    if not bindings:
        return {}
    payload_ids={
        uuid.UUID(item['price_payload']['payload_id'])
        for item in bindings
        if item.get('price_payload')
    }
    payload_ids.update(
        uuid.UUID(item['metadata_payload']['payload_id'])
        for item in bindings
        if item.get('metadata_payload')
    )
    rows=await conn.fetch(
        'SELECT payload_id::text,sha256,payload FROM public.raw_payloads WHERE payload_id=ANY($1::uuid[])',
        list(payload_ids))
    payloads={row['payload_id']: row for row in rows}
    sources={}
    for binding in bindings:
        price_ref=binding.get('price_payload', {})
        metadata_ref=binding.get('metadata_payload', {})
        price_row=payloads.get(price_ref.get('payload_id'))
        metadata_row=payloads.get(metadata_ref.get('payload_id'))
        if price_row is None or metadata_row is None:
            raise ValueError('Recovered source payload is missing')
        if price_row['sha256'].strip()!=price_ref.get('sha256') or metadata_row['sha256'].strip()!=metadata_ref.get('sha256'):
            raise ValueError('Recovered source payload checksum changed')
        bars=exact_json.loads(price_row['payload'])
        metadata=exact_json.loads(metadata_row['payload'])
        symbol=binding['symbol']
        company_name=metadata.get('tên_doanh_nghiệp')
        if not company_name and metadata.get('sections'):
            company_name=metadata['sections'][0]['header'].split(' (FPT) | ',1)[0]
        indicators={}
        if bars:
            ids=[uuid.uuid5(uuid.UUID('b77dbd7f-5d89-479d-90a3-421e5f0981ea'),
                            f'price:{symbol}:{bar["trade_date"][:10]}:False') for bar in bars]
            indicator_rows=await conn.fetch(
                'SELECT price_id::text,sma20,sma50,rsi14 FROM public.price_indicators WHERE price_id=ANY($1::uuid[])',
                ids)
            indicators={row['price_id']: dict(row) for row in indicator_rows}
        rows=[]
        for bar in bars:
            price_id=uuid.uuid5(uuid.UUID('b77dbd7f-5d89-479d-90a3-421e5f0981ea'),
                                f'price:{symbol}:{bar["trade_date"][:10]}:False')
            indicator=indicators.get(str(price_id), {})
            rows.append(dict(
                symbol=symbol,
                company_name=company_name,
                price_id=str(price_id),
                trade_date=bar['trade_date'][:10],
                price_scale=binding['price_scale'],
                **{key: bar[key] for key in ('open','high','low','close','volume')},
                **{key: indicator.get(key) for key in ('sma20','sma50','rsi14')}))
        sources[('price_bars', binding['source_id'])]=price_documents(rows)[0]
        if binding['source_table']=='companies':
            company_id=binding['source_id']
            company_row=await conn.fetchrow(
                'SELECT company_id,symbol,company_name,industry_type,sector,exchange,is_active '
                'FROM public.companies WHERE company_id=$1', uuid.UUID(company_id))
            if company_row is None:
                raise ValueError('Recovered company source is missing')
            company_data=dict(company_row)
            company_data['company_name']=company_name
            sources[('companies', company_id)]=company_documents([company_data])[0]
    return sources


async def main(args):
    import asyncpg
    settings=get_settings();path=Path(args.manifest);original=path.read_bytes()
    snapshot=json.loads(original);validate_snapshot(snapshot)
    digest=snapshot['manifest_sha256'];index,_,_=identities(digest,settings.embedding_model_ref)
    corpus_id=uuid.uuid5(NAMESPACE,digest)
    facts,price_ids,owners=membership_ids(snapshot)
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    report=dict(database_writes=False,index_version_id=str(index),corpus_version_id=str(corpus_id),
                manifest_sha256=digest,embedding_calls=0,documents=[],snapshot_manifest_unchanged=True,
                full_answer_generation_citation_test_executed=False,semantic_relevance_benchmark_executed=False)
    conn=await asyncpg.connect(settings.database_url,ssl='require',statement_cache_size=0,timeout=25,command_timeout=60)
    try:
        async with conn.transaction(readonly=True,isolation='repeatable_read'):
            print('CONNECTED_READ_ONLY',flush=True)
            report['database_snapshot']=str(await conn.fetchval('SELECT transaction_timestamp()'))
            report['existing_corpora']=[dict(r) for r in await conn.fetch('SELECT corpus_version_id::text,version_label,index_version_id::text,manifest_sha256,status FROM public.corpus_versions')]
            report['index']=dict(await conn.fetchrow('SELECT index_version_id::text,embedding_model,status,chunker_version FROM public.index_versions WHERE index_version_id=$1',index) or {})
            stored={};last=None
            while True:
                page=await conn.fetch('''SELECT chunk_id::text,document_id::text,
                    chunk_index,content_hash,locator_json,superseded_at,vector_dims(embedding) AS dimensions,
                    -(embedding <#> embedding) AS norm_squared FROM public.text_chunks
                    WHERE index_version_id=$1 AND ($2::uuid IS NULL OR chunk_id>$2)
                    ORDER BY chunk_id LIMIT 500''',index,last)
                if not page:break
                stored.update({r['chunk_id']:dict(r) for r in page});last=uuid.UUID(page[-1]['chunk_id'])
                print('VECTOR_ROWS',len(stored),flush=True)
            stored_docs={r['document_id']:dict(r) for r in await conn.fetch('''SELECT document_id::text,sha256,external_id,file_type,doc_type
                FROM public.documents WHERE document_id IN (SELECT document_id FROM public.text_chunks WHERE index_version_id=$1)''',index)}
            financial_ids=[d['source_id'] for d in snapshot['manifest']['documents'] if d['source_table']=='financial_reports']
            sql=db_source.FINANCIAL_SQL.replace('o.observation_id, o.value, o.unit',
                'o.observation_id,o.metric_id,o.value,o.unit,o.scale,o.currency')
            sql=sql.replace('($1::text[] IS NULL OR c.symbol = ANY($1::text[]))','fr.report_id::text=ANY($1::text[])')
            finance_rows=[]
            for offset in range(0,len(financial_ids),20):
                finance_rows.extend(dict(r) for r in await conn.fetch(sql,financial_ids[offset:offset+20]))
                print('FINANCIAL_ROWS',len(finance_rows),flush=True)
            fact_lookup={str(r['observation_id']):r for r in finance_rows}
            sources={(d.source_table,str(d.source_id)):d for d in financial_documents(finance_rows,renderer_version='db-financial-v3')}
            print('SOURCES financial',len(sources),flush=True)
            for fetch in (db_source.fetch_company_documents,db_source.fetch_price_documents,
                          db_source.fetch_index_documents,db_source.fetch_news_documents):
                for doc in await fetch(conn):sources[(doc.source_table,str(doc.source_id))]=doc
            sources.update(await load_recovered_sources(
                conn, Path(args.recovery)))
            context_rows=[]
            uris=[f'finmind:renderer-context:{index}:{d["document_id"]}' for d in snapshot['manifest']['documents'] if d['source_table']=='financial_reports']
            for offset in range(0,len(uris),25):
                context_rows.extend(await conn.fetch('SELECT source_uri,payload_id,sha256,payload FROM public.raw_payloads WHERE source_uri=ANY($1::text[])',uris[offset:offset+25]))
            contexts={}
            for r in context_rows:contexts.setdefault(r['source_uri'],[]).append(r)
            class ContextReader:
                async def fetch(self,sql,uri):return contexts.get(uri,[])
            price_rows=await conn.fetch('''SELECT p.price_id::text,p.company_id::text,p.trade_date,p.is_adjusted,
                p.open,p.high,p.low,p.close,p.volume,p.price_scale,i.sma20,i.sma50,i.rsi14
                FROM public.price_bars p LEFT JOIN public.price_indicators i ON i.price_id=p.price_id
                WHERE p.price_id=ANY($1::uuid[])''',[uuid.UUID(k) for k in sorted(price_ids)])
            price_lookup={r['price_id']:dict(r) for r in price_rows}
            expected=set();documents=[];chunk_checks=Counter()
            for n,doc in enumerate(snapshot['manifest']['documents'],1):
                _,did,_=identities(digest,settings.embedding_model_ref,doc['document_id'])
                document_hash=hashlib.sha256(f'{index}:{doc["snapshot_sha256"]}'.encode()).hexdigest()
                documents.append(dict(document_id=str(did),document_hash=document_hash,
                    source_id=doc['source_id'],source_table=doc['source_table'],doc_type=doc['doc_type']))
                saved_doc=stored_docs.get(str(did))
                doc_ok=bool(saved_doc and saved_doc['sha256'].strip()==document_hash
                    and saved_doc['external_id']==str(doc['source_id']) and saved_doc['file_type']=='DB'
                    and saved_doc['doc_type']==doc['doc_type'])
                source=sources.get((doc['source_table'],doc['source_id']));error=None
                try:
                    if source is None:raise ValueError('SOURCE_MISSING')
                    if doc['source_table']=='financial_reports':
                        source=await read_renderer_context(ContextReader(),str(index),source)
                        uri=f'finmind:renderer-context:{index}:{source.document_id}'
                        payload=contexts[uri][0]['payload'];payload=json.loads(payload) if isinstance(payload,str) else payload
                        if payload['corpus_manifest_sha256']!=digest:raise ValueError('CONTEXT_CORPUS_MISMATCH')
                    rebuilt=chunk_document(source,130)
                    actual={c.chunk_index:c for c in rebuilt}
                except Exception as exc:
                    error=getattr(exc,'code',str(exc));actual={}
                stats=Counter()
                for chunk in doc['chunks']:
                    _,_,cid=identities(digest,settings.embedding_model_ref,doc['document_id'],chunk['source_chunk_id'])
                    expected.add(str(cid));row=stored.get(str(cid))
                    loc=row.get('locator_json') if row else None
                    loc=json.loads(loc) if isinstance(loc,str) else loc
                    vector_ok=bool(row and row['document_id']==str(did) and row['chunk_index']==chunk['chunk_index']
                        and row['content_hash'].strip()==chunk['content_hash'] and loc==chunk['locator']
                        and row['dimensions']==1024 and row['superseded_at'] is None
                        and row['norm_squared'] is not None and abs(row['norm_squared']-1)<0.001)
                    stats['vector_pass' if vector_ok else 'vector_fail']+=1
                    restored=actual.get(chunk['chunk_index'])
                    source_ok=bool(restored and restored.chunk_id==chunk['source_chunk_id']
                        and restored.content_hash==chunk['content_hash'] and restored.locator==chunk['locator'])
                    stats['source_pass' if source_ok else 'source_fail']+=1
                chunk_checks.update(stats)
                report['documents'].append(dict(document_id=str(did),source_id=doc['source_id'],source_table=doc['source_table'],
                    title=doc['title'],symbol=doc['symbol'],stored_document_matches=doc_ok,
                    source_error=error,**dict(stats)))
                if n%100==0:print('VERIFIED',n,dict(chunk_checks),flush=True)
            missing_facts=sorted(facts-fact_lookup.keys());missing_prices=sorted(price_ids-price_lookup.keys())
            bad_owners=[key for key in facts & fact_lookup.keys() if str(fact_lookup[key]['report_id'])!=owners[key]]
            plan=dict(schema_version='corpus-v2-registration-review-v1',status='DRAFT_NOT_APPROVED',database_writes=False,
                corpus_version_id=str(corpus_id),version_label='corpus-v2',manifest_sha256=digest,
                index_version_id=str(index),embedding_model=settings.embedding_model_ref,
                corpus_documents=documents,
                corpus_facts=[dict(observation_id=key,value_hash=fact_value_hash(fact_lookup[key])) for key in sorted(facts & fact_lookup.keys())],
                corpus_prices=[dict(price_id=key,value_hash=price_value_hash(price_lookup[key])) for key in sorted(price_ids & price_lookup.keys())],
                value_hash_basis='Exact current source values captured in this read-only snapshot; not a claim of original unrounded values at initial corpus freeze.',
                missing_facts=missing_facts,missing_prices=missing_prices,observation_owner_mismatches=bad_owners,
                future_index_status='ACTIVE',future_corpus_status='FROZEN',
                rollback='Restore prior application default; keep corpus-v1 and its index/members unchanged. No deletes.',
                required_order=['Resolve every preflight blocker','Re-run read-only preflight against same manifest',
                    'Obtain user approval','Register exact memberships and verify within one transaction',
                    'Mark index ACTIVE only after checks pass','Switch application default and smoke-test; revert default on failure'])
            blockers=[]
            if chunk_checks['vector_fail'] or expected!=stored.keys():blockers.append('VECTOR_INVENTORY_MISMATCH')
            if chunk_checks['source_fail']:blockers.append('SOURCE_RECONSTRUCTION_FAILED')
            if any(not d['stored_document_matches'] for d in report['documents']):blockers.append('DOCUMENT_IDENTITY_MISMATCH')
            if missing_facts or missing_prices or bad_owners:blockers.append('NUMERIC_MEMBERSHIP_MISMATCH')
            if report['index'].get('embedding_model')!=settings.embedding_model_ref:blockers.append('INDEX_MODEL_MISMATCH')
            if any(r['version_label']=='corpus-v2' and (r['corpus_version_id']!=str(corpus_id)
                   or r['manifest_sha256'].strip()!=digest or r['index_version_id']!=str(index)) for r in report['existing_corpora']):
                blockers.append('EXISTING_REGISTRATION_CONFLICT')
            report.update(chunks=dict(chunk_checks),expected_chunks=len(expected),stored_chunks=len(stored),
                fact_members=len(facts),price_members=len(price_ids),blockers=blockers,
                activation_ready=not blockers,default_changed=False)
            plan.update(preflight_blockers=blockers,activation_ready=not blockers)
    finally:
        if not conn.is_closed():await conn.close()
    if path.read_bytes()!=original:raise ValueError('Frozen manifest changed during audit')
    (out/'registration-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    (out/'preflight.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    (out/'default-corpus.env.proposed').write_text(f'# PROPOSAL ONLY. Do not apply before approval and a passing preflight.\nDEFAULT_CORPUS_VERSION_ID={corpus_id}\nDEFAULT_CORPUS_MANIFEST_SHA256={digest}\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='documents'},ensure_ascii=False,default=str),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',default=str(ROOT/'backend/.tmp/corpus-v2.content.manifest.json'))
    p.add_argument('--output',default=str(ROOT/'outputs/corpus-v2-release-20261022'))
    p.add_argument('--recovery',default=str(ROOT/'outputs/corpus-v2-source-recovery-20261022/recovery-experiment.json'))
    asyncio.run(main(p.parse_args()))
