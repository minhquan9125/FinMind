import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_backend import Connection,Pool,Embedder,TEXTS,INDEX
from backend.src.vector_retrieval import backend as mod


class PagedConnection(Connection):
    def __init__(self):
        super().__init__()
        self.pages=[];self.fail_at=None;self.repeat=False;self.backward=False

    async def fetch(self,sql,*args):
        if 'ORDER BY t.chunk_id' not in sql:
            return await super().fetch(sql,*args)
        self.pages.append((sql,args))
        if len(self.pages)==self.fail_at:
            raise OSError('injected connection drop')
        rows=sorted(self.rows,key=lambda r:r['chunk_id'])
        if self.repeat:return rows[:1]
        if self.backward:return rows[1:2] if len(self.pages)==1 else rows[:1]
        if len(args)==3:rows=[r for r in rows if r['chunk_id']>args[1]]
        return [dict(r) for r in rows[:args[-1]]]


class CachePagingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'cache.json'
        self.conn=PagedConnection();self.resolved=[]
        async def resolver(conn,rows):
            self.resolved.extend(r['chunk_id'] for r in rows)
            return [dict(r,text=TEXTS[r['chunk_id']]) for r in rows]
        self.service=mod.HybridRetriever(Pool(self.conn),Embedder(),resolver=resolver)

    async def build(self,size):
        with patch.object(mod,'CACHE_BATCH_SIZE',size):
            return await self.service.build_cache(INDEX,self.path)

    async def test_multiple_full_pages_bound_cursor_and_single_readonly_snapshot(self):
        result=await self.build(1)
        ids=sorted(r['chunk_id'] for r in self.conn.rows)
        self.assertEqual(result['chunks'],3)
        self.assertCountEqual(self.resolved,ids);self.assertEqual(len(set(self.resolved)),3)
        self.assertEqual(len(self.conn.pages),4)
        self.assertEqual(self.conn.pages[0][1],(INDEX,1))
        for (_,args),last in zip(self.conn.pages[1:],ids):self.assertEqual(args,(INDEX,last,1))
        self.assertTrue(all('OFFSET' not in sql and 'ORDER BY t.chunk_id' in sql for sql,_ in self.conn.pages))
        self.assertEqual(self.conn.transactions,[dict(readonly=True,isolation='repeatable_read')])
        payload,index=self.service._cache(self.path,INDEX,mod.MODEL)
        self.assertCountEqual([r['chunk_id'] for r in payload['rows']],ids)

    async def test_short_final_page_and_oversized_batch_terminates(self):
        self.assertEqual((await self.build(2))['chunks'],3)
        self.assertEqual(len(self.conn.pages),2)
        self.conn.pages.clear();self.resolved.clear()
        self.assertEqual((await self.build(500))['chunks'],3)
        self.assertEqual(len(self.conn.pages),1)

    async def test_empty_index_keeps_previous_cache(self):
        self.path.write_bytes(b'old-cache');self.conn.rows=[]
        with self.assertRaises(mod.RetrievalError) as error:await self.build(1)
        self.assertEqual(error.exception.code,'INDEX_EMPTY')
        self.assertEqual(self.path.read_bytes(),b'old-cache')
        self.assertEqual(self.resolved,[])

    async def test_failed_second_fetch_keeps_previous_cache_without_partial_resolution(self):
        self.path.write_bytes(b'old-cache');self.conn.fail_at=2
        with self.assertRaises(mod.RetrievalError) as error:await self.build(1)
        self.assertEqual(error.exception.code,'CACHE_BUILD_FAILED')
        self.assertEqual(self.path.read_bytes(),b'old-cache')
        self.assertEqual(self.resolved,[]);self.assertEqual(len(self.conn.pages),2)

    async def test_repeated_page_and_backward_cursor_fail_instead_of_loop(self):
        for flag in ('repeat','backward'):
            self.conn.pages.clear();self.conn.repeat=False;self.conn.backward=False
            setattr(self.conn,flag,True)
            with self.subTest(flag=flag),self.assertRaises(mod.RetrievalError):await self.build(1)
            self.assertEqual(len(self.conn.pages),2)
