import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from backend.scripts import replay_market_activity as replay


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.root=Path('.agent-state/replay-test')/uuid4().hex
        self.root.mkdir(parents=True)
        self.envelope=json.loads(Path('backend/tests/fixtures/market_activity.json').read_text(encoding='utf-8'))
        self.path=self.root/'live.json'
        self.path.write_text(json.dumps(self.envelope),encoding='utf-8')

    def test_dry_run_validates_real_quote_without_database(self):
        with patch.object(replay,'apply_plans',side_effect=AssertionError('DB called')):
            summary=asyncio.run(replay.replay(self.path))
        self.assertEqual(summary['observed'],1)
        self.assertEqual(summary['rejected'],0)
        self.assertEqual(summary['dates'],['2026-10-07'])
        self.assertEqual(summary['observations'][0]['quality_status'],'pending_reconciliation')
        self.assertEqual(summary['observations'][0]['observation_status'],'intraday')

    def test_background_basket_symbol_is_accepted_without_expanding_financial_project_scope(self):
        env=deepcopy(self.envelope);env['rows'][0]['symbol']='ACB'
        self.path.write_text(json.dumps(env),encoding='utf-8')
        out=asyncio.run(replay.replay(self.path))
        self.assertEqual((out['observed'],out['rejected']),(1,0))
        self.assertEqual(len(replay.ingest.PROJECT_SYMBOLS),10)

    def test_receipts_are_skipped_invalid_quotes_rejected(self):
        (self.root/'receipt.json').write_text('{"success":true}',encoding='utf-8')
        bad=deepcopy(self.envelope);bad['rows'][0]['close_price']='NaN'
        (self.root/'bad.json').write_text(json.dumps(bad),encoding='utf-8')
        out=asyncio.run(replay.replay(self.root))
        self.assertEqual((out['observed'],out['rejected'],out['skipped']),(1,1,1))

    def test_unknown_stock_and_preopen_zero_rejected(self):
        for field,value in [('symbol','ZZZ'),('open_price','0'),('TD','11/11/9999')]:
            env=deepcopy(self.envelope);env['rows'][0][field]=value
            self.path.write_text(json.dumps(env),encoding='utf-8')
            self.assertEqual(asyncio.run(replay.replay(self.path))['rejected'],1)

    def test_apply_calls_shared_store_and_counts_failures(self):
        fake=AsyncMock(return_value=['inserted'])
        with patch.object(replay,'apply_plans',fake):
            out=asyncio.run(replay.replay(self.path,apply=True))
        self.assertEqual(out['inserted'],1);self.assertEqual(out['failed'],0)
        fake=AsyncMock(return_value=['needs_reconciliation'])
        with patch.object(replay,'apply_plans',fake):
            out=asyncio.run(replay.replay(self.path,apply=True))
        self.assertEqual(out['rejected'],1)

    def test_unsafe_or_oversized_input_rejected(self):
        with self.assertRaises(ValueError):asyncio.run(replay.replay(Path('..')))
        self.path.write_text(' '*1_048_577,encoding='utf-8')
        self.assertEqual(asyncio.run(replay.replay(self.path))['rejected'],1)

    def test_index_envelope_without_row_symbol_is_skipped(self):
        for marker in ({'instrument_type':'index'}, {'symbol':'VNINDEX'}):
            env={**self.envelope,**marker,'rows':[{'index_code':'VNINDEX','TD':'07/10/2026'}]}
            self.path.write_text(json.dumps(env),encoding='utf-8')
            out=asyncio.run(replay.replay(self.path))
            self.assertEqual((out['observed'],out['rejected'],out['skipped']),(0,0,1))
            self.assertEqual(out['issues'][0]['reason'],'benchmark_is_not_stock_activity')

    def test_cli_rejected_quote_has_nonzero_exit(self):
        self.path.write_text(json.dumps({**self.envelope,'rows':[]}),encoding='utf-8')
        with patch('sys.stdout'):
            self.assertEqual(replay.main(['--input',str(self.path)]),1)


@unittest.skipUnless(os.getenv('FINMIND_TEST_POSTGRES')=='1','Explicit isolated PostgreSQL check')
class ReplayPostgresTests(unittest.IsolatedAsyncioTestCase):
    async def test_mixed_offsets_keep_earlier_field_and_its_payload(self):
        import asyncpg
        from backend.scripts import ingest_market_news_to_supabase as ingest
        folder=ingest.PROJECT_ROOT/'.agent-state/replay-test'/uuid4().hex;folder.mkdir(parents=True)
        env=json.loads(Path('backend/tests/fixtures/market_activity.json').read_text(encoding='utf-8'))
        earlier=deepcopy(env);earlier['fetched_at']='2026-10-07T10:00:00+07:00'
        earlier['rows'][0].update(symbol='CMG',TD='07/10/2026',volume_accumulated=100,total_value=1000)
        later=deepcopy(earlier);later['fetched_at']='2026-10-07T04:00:00+00:00'
        later['rows'][0].update(volume_accumulated=150,total_value=None)
        (folder/'earlier.json').write_text(json.dumps(earlier),encoding='utf-8')
        (folder/'later.json').write_text(json.dumps(later),encoding='utf-8')
        conn=await asyncpg.connect(host='127.0.0.1',port=15434,user='finmind_test',database='postgres')
        outer=conn.transaction();await outer.start()
        try:
            await ingest.ensure_source(conn,'vnstock_kbs','MARKET_DATA','fixture')
            await conn.execute("INSERT INTO companies(company_id,symbol,exchange) VALUES($1,'CMG','HOSE') ON CONFLICT DO NOTHING",uuid4())
            company=await conn.fetchval("SELECT company_id FROM companies WHERE symbol='CMG'")
            await conn.execute('DELETE FROM daily_market_activity WHERE company_id=$1',company)
            async def apply(plans):return [(await ingest.apply_live(conn,p))['activity_status'] for p in plans]
            with patch.object(replay,'apply_plans',apply):out=await replay.replay(folder,apply=True)
            self.assertEqual((out['inserted'],out['updated'],out['rejected']),(1,1,0))
            row=await conn.fetchrow('SELECT * FROM daily_market_activity WHERE company_id=$1',company)
            self.assertEqual((row['volume'],row['total_value_vnd']),(150,1000))
            origins=json.loads(row['field_payload_ids'])
            self.assertNotEqual(origins['total_value_vnd'],str(row['payload_id']))
            original=await conn.fetchval('SELECT payload FROM raw_payloads WHERE payload_id=$1',__import__('uuid').UUID(origins['total_value_vnd']))
            self.assertEqual(json.loads(original)['fetched_at'],earlier['fetched_at'])
        finally:await outer.rollback();await conn.close()

    async def test_actual_snapshot_replay_is_idempotent_and_atomic(self):
        import asyncpg
        from backend.scripts import ingest_market_news_to_supabase as ingest
        pool=await asyncpg.create_pool(host='127.0.0.1',port=15434,user='finmind_test',database='postgres',min_size=1,max_size=2)
        env=json.loads(Path('backend/tests/fixtures/market_activity.json').read_text(encoding='utf-8'))
        plan={'symbol':'FPT','source':'vnstock_kbs','is_index':False,'live':env,
              'live_path':ingest.PROJECT_ROOT/'outputs/replay-fixture.json','activity_session_status':'intraday'}
        try:
            async with pool.acquire() as conn:
                await conn.execute(Path('supabase/migrations/20261111000100_daily_market_activity.sql').read_text(encoding='utf-8'))
                one=await ingest.apply_live(conn,plan);two=await ingest.apply_live(conn,plan)
                self.assertIn(one['activity_status'],('inserted','unchanged'))
                self.assertEqual(two['activity_status'],'unchanged')
                rows=await conn.fetch('''SELECT a.*,r.payload,r.sha256 FROM daily_market_activity a
                    JOIN companies c USING(company_id) JOIN raw_payloads r USING(payload_id)
                    WHERE c.symbol='FPT' AND trade_date='2026-10-07' ''')
                self.assertEqual(len(rows),1)
                self.assertEqual(rows[0]['foreign_buy_volume'],368405)
                self.assertEqual(rows[0]['quality_status'],'pending_reconciliation')
                self.assertEqual(json.loads(rows[0]['payload']),env)
        finally:await pool.close()
