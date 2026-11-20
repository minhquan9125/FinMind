"""Explicit PostgreSQL integration checks against the isolated test cluster."""
import asyncio
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import unittest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from uuid import uuid4

from backend.src.market_data.activity_store import upsert_activity


class SourceMappingTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_noncanonical_source_is_reused(self):
        from backend.scripts import ingest_market_news_to_supabase as ingest
        existing=uuid4();conn=AsyncMock()
        conn.fetch.return_value=[{'source_id':existing}]
        self.assertEqual(await ingest.ensure_source(conn,'vnstock_kbs','MARKET_DATA','test'),existing)
        conn.execute.assert_not_awaited()

    async def test_ambiguous_source_name_is_rejected(self):
        from backend.scripts import ingest_market_news_to_supabase as ingest
        conn=AsyncMock();conn.fetch.return_value=[{'source_id':uuid4()},{'source_id':uuid4()}]
        with self.assertRaises(ValueError):await ingest.ensure_source(conn,'vnstock_kbs','MARKET_DATA','test')
        conn.execute.assert_not_awaited()

    async def test_activity_without_existing_source_cannot_create_raw_or_mapping(self):
        from backend.scripts import ingest_market_news_to_supabase as ingest
        class Connection:
            def __init__(self):self.writes=[]
            @asynccontextmanager
            async def transaction(self):yield
            async def fetch(self,sql,*args):return [{'company_id':uuid4()}] if 'companies' in sql else []
            async def fetchval(self,*args):return None
            async def execute(self,sql,*args):self.writes.append(sql)
        conn=Connection()
        env=json.loads(Path('backend/tests/fixtures/market_activity.json').read_text(encoding='utf-8'))
        result=await ingest.apply_live(conn,{'symbol':'FPT','source':'vnstock_kbs','is_index':False,
            'live':env,'live_path':ingest.PROJECT_ROOT/'outputs/unknown-mapping.json'})
        self.assertEqual(result['activity_status'],'rejected')
        self.assertEqual(conn.writes,[])


@unittest.skipUnless(os.getenv('FINMIND_TEST_POSTGRES') == '1', 'Set FINMIND_TEST_POSTGRES=1 for isolated PostgreSQL checks')
class ActivityStoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import asyncpg
        self.c = await asyncpg.connect(host='127.0.0.1',port=15434,user='finmind_test',database='postgres')
        self.assertEqual(await self.c.fetchval('SELECT current_user'), 'finmind_test')
        await self.c.execute((Path(__file__).resolve().parents[2]/'supabase/migrations/20261111000100_daily_market_activity.sql').read_text(encoding='utf-8'))
        self.company,self.source,self.job,self.payload = [uuid4() for _ in range(4)]
        await self.c.execute("INSERT INTO companies(company_id,symbol) VALUES($1,$2)",self.company,'T'+self.company.hex[:8])
        await self.c.execute("INSERT INTO sources(source_id,name) VALUES($1,$2)",self.source,'test-'+str(self.source))
        await self.c.execute('INSERT INTO ingestion_jobs(job_id,source_id) VALUES($1,$2)',self.job,self.source)
        await self.c.execute("INSERT INTO raw_payloads(payload_id,job_id,sha256,payload) VALUES($1,$2,$3,'{}')",self.payload,self.job,'0'*64)
        self.row = dict(symbol='FPT',trade_date=date(2026,10,7),volume=100,total_value_vnd=Decimal('1000'),
                        foreign_buy_volume=30,foreign_sell_volume=20,foreign_buy_value_vnd=None,foreign_sell_value_vnd=None,
                        volume_basis='unknown',value_basis='unknown',observation_status='intraday',
                        quality_status='pending_reconciliation',source_updated_at=None,
                        fetched_at=datetime(2026,10,7,4,tzinfo=timezone.utc))

    async def asyncTearDown(self):
        await self.c.close()

    async def save(self,row=None,payload=None,conn=None):
        return await upsert_activity(conn or self.c,row or self.row,company_id=self.company,
                                     source_id=self.source,payload_id=payload or self.payload)

    async def stored(self):
        return await self.c.fetchrow('SELECT * FROM daily_market_activity WHERE company_id=$1 AND trade_date=$2',self.company,self.row['trade_date'])

    async def test_idempotent_and_separate_days(self):
        self.assertEqual(await self.save(),'inserted')
        self.assertEqual(await self.save(),'unchanged')
        self.assertEqual((await self.stored())['revision'],1)
        self.assertEqual(await self.save({**self.row,'trade_date':date(2026,10,8)}),'inserted')
        self.assertEqual(await self.c.fetchval('SELECT count(*) FROM daily_market_activity WHERE company_id=$1',self.company),2)

    async def test_newer_cumulative_snapshot_replaces_not_adds(self):
        await self.save()
        new={**self.row,'volume':150,'foreign_buy_volume':40,'fetched_at':self.row['fetched_at']+timedelta(minutes=1)}
        self.assertEqual(await self.save(new),'updated')
        stored=await self.stored();self.assertEqual(stored['volume'],150);self.assertEqual(stored['revision'],2)
        self.assertEqual(stored['foreign_buy_volume'],40)

    async def test_old_decreasing_and_equal_timestamp_changes_are_rejected(self):
        await self.save()
        for row in [{**self.row,'fetched_at':self.row['fetched_at']-timedelta(seconds=1),'volume':200},
                    {**self.row,'fetched_at':self.row['fetched_at']+timedelta(seconds=1),'volume':99},
                    {**self.row,'volume':200}]:
            self.assertEqual(await self.save(row),'needs_reconciliation')
        self.assertEqual((await self.stored())['volume'],100)

    async def test_missing_new_fields_do_not_erase_known_values(self):
        await self.save()
        row={**self.row,'foreign_buy_volume':None,'total_value_vnd':None,'fetched_at':self.row['fetched_at']+timedelta(seconds=1)}
        await self.save(row)
        self.assertEqual((await self.stored())['foreign_buy_volume'],30)
        self.assertEqual((await self.stored())['total_value_vnd'],Decimal('1000'))

    async def test_atomic_rollback_and_foreign_keys(self):
        tx=self.c.transaction();await tx.start()
        await self.save();await tx.rollback()
        self.assertIsNone(await self.stored())
        import asyncpg
        with self.assertRaises(asyncpg.ForeignKeyViolationError):await self.save(payload=uuid4())
        self.assertIsNone(await self.stored())

    async def test_payload_from_another_source_is_rejected(self):
        other=uuid4()
        await self.c.execute('INSERT INTO sources(source_id,name) VALUES($1,$2)',other,'test-'+str(other))
        with self.assertRaises(ValueError):
            await upsert_activity(self.c,self.row,company_id=self.company,source_id=other,payload_id=self.payload)
        self.assertIsNone(await self.stored())

    async def test_concurrent_upserts_have_one_latest_row(self):
        import asyncpg
        other=await asyncpg.connect(host='127.0.0.1',port=15434,user='finmind_test',database='postgres')
        try:
            newer={**self.row,'volume':150,'fetched_at':self.row['fetched_at']+timedelta(seconds=1)}
            await asyncio.gather(self.save(),self.save(newer,conn=other))
            row=await self.stored();self.assertEqual(row['volume'],150)
            self.assertEqual(await self.c.fetchval('SELECT count(*) FROM daily_market_activity WHERE company_id=$1',self.company),1)
        finally:await other.close()

    async def test_immutable_payload_while_legacy_sink_uses_stable_ids(self):
        from backend.scripts import ingest_market_news_to_supabase as ingest
        path=ingest.PROJECT_ROOT/'outputs'/'activity-test.json'
        old=ingest.STABLE_PAYLOAD_IDS;ingest.STABLE_PAYLOAD_IDS=True
        try:
            a=await ingest.store_payload(self.c,path,'vnstock_kbs','MARKET_DATA','test',{'volume':1},1,immutable=True)
            b=await ingest.store_payload(self.c,path,'vnstock_kbs','MARKET_DATA','test',{'volume':2},1,immutable=True)
            self.assertNotEqual(a,b)
            raw=await self.c.fetchrow('SELECT payload,sha256 FROM raw_payloads WHERE payload_id=$1',a)
            self.assertEqual(json.loads(raw['payload']),{'volume':1})
            self.assertEqual(raw['sha256'].strip(),hashlib.sha256(ingest.canonical_json({'volume':1}).encode()).hexdigest())
            self.assertEqual(await ingest.store_payload(self.c,path,'vnstock_kbs','MARKET_DATA','test',{'volume':1},1,immutable=True),a)
        finally:ingest.STABLE_PAYLOAD_IDS=old


if __name__=='__main__':unittest.main()
