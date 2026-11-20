import hashlib
import json
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch
from backend.src.vector_retrieval import backend as mod

INDEX='434ef5e0-6516-578d-8d18-721d21347e01'
IDS=['00000000-0000-0000-0000-00000000000'+str(i) for i in range(1,4)]
TEXTS=dict(zip(IDS,['tai san loi nhuan','tai san tai san','tai san']))

class SourceChanged(Exception):
    reason_code='SOURCE_CHANGED'

class Connection:
    def __init__(self):
        self.info=dict(embedding_model=mod.MODEL,status='ACTIVE')
        self.dimension='vector(1024)'
        self.fingerprint='a'*32
        self.transactions=[]
        self.queries=[]
        self.rows=[dict(chunk_id=cid,document_id=cid,chunk_index=0,page=None,
            content_hash=hashlib.sha256(TEXTS[cid].encode()).hexdigest(),locator_json={'id':cid},
            title='Report',doc_type='FINANCIAL_STATEMENT',company='FPT' if i<2 else 'BID',
            symbols=[],period='2026-Q2') for i,cid in enumerate(IDS)]

    @asynccontextmanager
    async def transaction(self,**options):
        self.transactions.append(options)
        yield

    async def fetchrow(self,sql,*args):
        self.queries.append((sql,args))
        return self.info

    async def fetchval(self,sql,*args):
        self.queries.append((sql,args))
        return self.dimension if 'pg_attribute' in sql else self.fingerprint

    async def fetch(self,sql,*args):
        self.queries.append((sql,args))
        if '1-(t.embedding' in sql:
            allowed={str(cid) for cid in args[2]}
            return [dict(chunk_id=cid,score=score) for cid,score in [(IDS[2],.99),(IDS[0],.9)] if cid in allowed][:args[3]]
        if 'ANY($2' in sql:
            wanted={str(cid) for cid in args[1]}
            return [dict(r) for r in self.rows if r['chunk_id'] in wanted]
        return [dict(r) for r in self.rows]

class Pool:
    def __init__(self,conn): self.conn=conn
    @asynccontextmanager
    async def acquire(self): yield self.conn

class Embedder:
    model_name='BAAI/bge-m3'
    revision='5617a9f61b028005a4858fdac845db406aefb181'
    def __init__(self): self.calls=0; self.vector=[1.0]+[0.0]*1023
    def embed_query(self,question): self.calls+=1; return self.vector

class BackendTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'cache.json'
        self.conn=Connection(); self.embedder=Embedder(); self.resolutions=[]
        self.fail_source=False; self.bad_text=False
        async def resolver(conn,rows):
            self.resolutions.append([r['chunk_id'] for r in rows])
            if self.fail_source: raise SourceChanged('secret DSN must never leak')
            return [dict(r,text='changed' if self.bad_text else TEXTS[r['chunk_id']]) for r in rows]
        self.retriever=mod.HybridRetriever(Pool(self.conn),self.embedder,resolver=resolver,clock=lambda:1000)

    async def asyncTearDown(self): self.temp.cleanup()

    async def build(self,**kwargs): return await self.retriever.build_cache(INDEX,self.path,**kwargs)
    async def search(self,**kwargs): return await self.retriever.search('tai san',INDEX,self.path,**kwargs)

    async def assert_code(self,code,call):
        with self.assertRaises(mod.RetrievalError) as raised: await call
        self.assertEqual(raised.exception.code,code)
        self.assertNotIn('secret',str(raised.exception))

    async def test_full_flow_finds_lexical_candidate_missing_from_dense(self):
        report=await self.build()
        self.assertEqual(report['chunks'],3)
        self.assertEqual(self.embedder.calls,0)
        envelope=json.loads(self.path.read_bytes())
        self.assertTrue(all('text' not in r and 'tokens' in r for r in envelope['payload']['rows']))
        self.assertNotIn('embedding',envelope['payload'])
        result=await self.search(company='fpt',period='2026-Q2',doc_type='financial_statement',top_k=2,candidates=2)
        self.assertEqual({r['chunk_id'] for r in result['results']},set(IDS[:2]))
        lexical=next(r for r in result['results'] if r['chunk_id']==IDS[1])
        self.assertIsNone(lexical['dense_rank'])
        self.assertEqual(lexical['bm25_rank'],1)
        self.assertTrue(all(r['text']==TEXTS[r['chunk_id']] for r in result['results']))
        sql,args=next((s,a) for s,a in self.conn.queries if '1-(t.embedding' in s)
        self.assertEqual({str(cid) for cid in args[2]},set(IDS[:2]))
        self.assertIn('ORDER BY t.embedding <=> $2::vector LIMIT $4',sql)
        self.assertTrue(all(t==dict(readonly=True,isolation='repeatable_read') for t in self.conn.transactions))
        self.assertEqual(result['scope_mode'],'INDEX')
        self.assertNotIn('corpus_id',result)

    async def test_cache_is_reused_without_source_rebuild(self):
        await self.build(); self.resolutions.clear()
        with patch.object(mod,'BM25Index',wraps=mod.BM25Index) as constructor:
            await self.search(); await self.search()
            self.assertEqual(constructor.call_count,1)
        self.assertEqual(len(self.resolutions),2)
        self.assertTrue(all('ORDER BY t.document_id' not in s for s,a in self.conn.queries[4:]))

    async def test_index_metadata_guards(self):
        for status in ('BUILDING','FAILED','ARCHIVED'):
            self.conn.info['status']=status
            await self.assert_code('INDEX_NOT_ACTIVE',self.build())
        self.conn.info['status']='BUILDING'
        report=await self.build(allow_building=True)
        self.assertEqual(report['index_status'],'BUILDING')
        self.assertEqual(self.conn.info['status'],'BUILDING')
        self.conn.info['embedding_model']='other'
        await self.assert_code('MODEL_MISMATCH',self.build(allow_building=True))
        self.conn.info=None
        await self.assert_code('INDEX_NOT_FOUND',self.build())

    async def test_dimension_guard(self):
        self.conn.dimension='vector(768)'
        await self.assert_code('DIMENSION_MISMATCH',self.build())

    async def test_failed_source_build_preserves_previous_file(self):
        await self.build(); old=self.path.read_bytes(); self.fail_source=True
        await self.assert_code('SOURCE_CHANGED',self.build())
        self.assertEqual(self.path.read_bytes(),old)

    async def test_source_and_hash_rechecked_on_search(self):
        await self.build(); self.fail_source=True
        await self.assert_code('SOURCE_CHANGED',self.search())
        self.fail_source=False; self.bad_text=True
        await self.assert_code('HASH_MISMATCH',self.search())

    async def test_cache_missing_corrupt_stale_expired(self):
        await self.assert_code('CACHE_BUILD_REQUIRED',self.search())
        self.path.write_text('bad JSON',encoding='utf-8')
        await self.assert_code('INVALID_CACHE',self.search())
        await self.build(); self.conn.fingerprint='b'*32
        await self.assert_code('CACHE_STALE',self.search())
        self.conn.fingerprint='a'*32; self.retriever.clock=lambda:5001
        await self.assert_code('CACHE_EXPIRED',self.search())

    async def test_checksum_and_index_rejected(self):
        await self.build()
        envelope=json.loads(self.path.read_bytes()); envelope['sha256']='0'*64
        self.path.write_text(json.dumps(envelope),encoding='utf-8')
        await self.assert_code('CACHE_CHECKSUM_MISMATCH',self.search())
        await self.build(); envelope=json.loads(self.path.read_bytes())
        envelope['payload']['index_id']=IDS[0]
        mod._write_cache(self.path,envelope['payload'])
        await self.assert_code('CACHE_INDEX_MISMATCH',self.search())

    async def test_selected_scope_not_trusted_from_local_cache(self):
        await self.build(); payload=json.loads(self.path.read_bytes())['payload']
        for row in payload['rows']: row['company']='FPT'
        mod._write_cache(self.path,payload)
        await self.assert_code('SOURCE_UNAVAILABLE',self.search(company='FPT'))

    async def test_no_scope_match_returns_empty_without_embedding(self):
        await self.build()
        result=await self.search(company='VCB')
        self.assertEqual(result['results'],[])
        self.assertEqual(self.embedder.calls,0)

    async def test_query_input_and_vector_bounds(self):
        for kwargs,code in [({'company':'FPT;DROP'},'INVALID_COMPANY'),({'period':'2026-02-30'},'INVALID_PERIOD'),({'period':'2026-13'},'INVALID_PERIOD'),({'doc_type':'BCTC%'},'INVALID_DOCUMENT_TYPE'),({'top_k':True},'INVALID_LIMITS'),({'top_k':5,'candidates':4},'INVALID_LIMITS')]:
            await self.assert_code(code,self.search(**kwargs))
        await self.assert_code('INVALID_QUESTION',self.retriever.search(' ',INDEX,self.path))
        await self.build()
        for vector in ([0.0]*1024,[float('nan')]*1024,[1.0]*3):
            self.embedder.vector=vector
            await self.assert_code('INVALID_QUERY_VECTOR',self.search())

    async def test_empty_index_no_file_created(self):
        self.conn.rows=[]
        await self.assert_code('INDEX_EMPTY',self.build())
        self.assertFalse(self.path.exists())

    async def test_atomic_replace_failure_preserves_cache(self):
        await self.build(); original=self.path.read_bytes()
        with patch.object(mod.os,'replace',side_effect=OSError('secret path')):
            await self.assert_code('CACHE_BUILD_FAILED',self.build())
        self.assertEqual(original,self.path.read_bytes())
        self.assertEqual(list(self.path.parent.glob('.cache-*')),[])

    def test_period_boundaries_and_cache_age_validation(self):
        row=dict(company='FPT',symbols=['BID'],period='2026-10-22T08:00:00+07:00',doc_type='NEWS')
        self.assertTrue(mod._matches(row,'BID','2026-10','NEWS'))
        self.assertFalse(mod._matches(row,None,'2026-1',None))
        for value in (True,0,float('nan')):
            with self.assertRaises(mod.RetrievalError): mod.HybridRetriever(None,None,resolver=lambda:None,max_cache_age=value)
