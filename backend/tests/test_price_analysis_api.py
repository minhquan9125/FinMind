"""PF07: the analysis endpoint keeps auth, maps errors and runs the real calculator."""
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.src.api.routers.market_data import get_price_analysis_pool
from backend.src.auth.authorization import Principal, current_principal
from backend.src.market_data.analysis_queries import get_price_analysis, get_stored_bars
from backend.src.market_data.app import app

URL = '/api/market-data/stocks/{}/analysis'


def price_rows(start=date(2026, 9, 1), count=21):
    return [dict(price_id=f'price-{i}', trade_date=start + timedelta(days=i), open=Decimal(100 + i),
                 high=Decimal(102 + i), low=Decimal(99 + i), close=Decimal(100 + i),
                 volume=200 if i == 20 else 100, price_scale=1000, is_adjusted=False,
                 payload_id=f'raw-{i}', source_id='s1', source_name='historical',
                 approval_status='PENDING') for i in range(count)]


class FakePool:
    """Answers each read by table name; records statements, arguments and transaction options."""
    def __init__(self, prices=(), company=True, fail=None, trend_fail=None):
        self.prices, self.company, self.fail, self.calls, self.options = list(prices), company, fail, [], None
        self.trend_fail = trend_fail

    @asynccontextmanager
    async def acquire(self):
        if self.fail:
            raise self.fail
        yield self

    @asynccontextmanager
    async def _transaction(self):
        yield

    def transaction(self, **options):
        self.options = options
        return self._transaction()

    async def fetch(self, sql, *args):
        self.calls.append((sql, args))
        if self.trend_fail and 'LIMIT $3' not in sql and 'exchange' in sql:
            raise self.trend_fail
        if 'public.companies' in sql:
            return [{'company_id': 'company-1', 'exchange': 'HOSE'}] if self.company else []
        if 'daily_market_activity' in sql or 'market_index_bars' in sql:
            return []
        return self.prices

    async def fetchval(self, sql, *args):
        if 'price_indicators' in sql:
            return Decimal('55.5')
        return 'daily_market_activity'


class PriceAnalysisApiTests(unittest.TestCase):
    def setUp(self):
        for patcher in (patch.dict('os.environ', {'FINMIND_LIVE_ENABLED': '0'}),
                        patch('backend.src.market_data.app.get_pool', lambda: object())):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(app.dependency_overrides.clear)
        self.pool = FakePool(price_rows())
        app.dependency_overrides[get_price_analysis_pool] = lambda: self.pool
        self.sign_in('RESEARCHER')

    def sign_in(self, *roles):
        app.dependency_overrides[current_principal] = lambda: Principal(uuid4(), frozenset(roles))

    def get(self, symbol='FPT', query='?as_of=2026-09-21'):
        with TestClient(app) as client:
            return client.get(URL.format(symbol) + query)

    def test_authentication_and_read_role_are_required(self):
        del app.dependency_overrides[current_principal]
        self.assertEqual(self.get().status_code, 401)
        self.sign_in('GUEST')
        self.assertEqual(self.get().status_code, 403)
        self.assertEqual(self.pool.calls, [])

    def test_real_calculator_result_with_provenance_and_bound_parameters(self):
        response = self.get('fpt')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual((body['symbol'], body['as_of'], body['session_count']), ('FPT', '2026-09-21', 21))
        self.assertEqual(body['metrics']['return_20_percent'], '20.0000')
        self.assertEqual(body['metrics']['volume_vs_prior20'], '2.0000')
        self.assertEqual(body['status'], 'partial')
        self.assertIsNone(body['activity']['windows']['20']['foreign_net_volume'])
        self.assertEqual(body['sources']['prices'][-1]['price_id'], 'price-20')
        self.assertIn('unadjusted_prices', body['warnings'])
        self.assertEqual(self.pool.options, {'readonly': True, 'isolation': 'repeatable_read'})
        for sql, args in self.pool.calls:
            self.assertNotIn('FPT', sql)
            self.assertNotIn('2026-09-21', sql)
        self.assertEqual(self.pool.calls[0][1], ('FPT',))
        self.assertEqual(self.pool.calls[1][1], ('company-1', date(2026, 9, 21), 21))

    def test_analysis_includes_trend(self):
        self.pool = FakePool(price_rows(count=30))
        body = self.get(query='?as_of=2026-09-30').json()
        trend = body['trend']
        self.assertEqual(trend['horizons']['20']['label'], 'UP')
        self.assertEqual(trend['horizons']['200']['label'], 'INSUFFICIENT_DATA')
        self.assertEqual((trend['benchmark'], trend['context']['rsi14']), ('VNINDEX', '55.5000'))
        for sql, args in self.pool.calls:
            self.assertNotIn('FPT', sql)
            self.assertNotIn('2026-09-30', sql)

    def test_trend_failure_keeps_analysis(self):
        self.pool = FakePool(price_rows(), trend_fail=TimeoutError())
        response = self.get()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIsNone(body['trend'])
        self.assertIn('trend_unavailable', body['warnings'])
        self.assertEqual(body['metrics']['return_20_percent'], '20.0000')

    def test_bad_requests_never_reach_the_database(self):
        tomorrow = (datetime.now(timezone(timedelta(hours=7))).date() + timedelta(days=1)).isoformat()
        for symbol, query, status in (('FPT', '?as_of=' + tomorrow, 400), ('FP1', '', 400),
                                      ('FPTX', '', 400), ('FPT', '?as_of=21-09-2026', 422)):
            with self.subTest(symbol=symbol, query=query):
                self.assertEqual(self.get(symbol, query).status_code, status)
        self.assertEqual(self.pool.calls, [])

    def test_missing_data_is_404_and_storage_failures_are_sanitized_503(self):
        for pool in (FakePool(company=False), FakePool()):
            self.pool = pool
            self.assertEqual(self.get().status_code, 404)
        mixed = price_rows()
        mixed[-1]['source_name'] = 'another_vendor'
        for pool in (FakePool(fail=OSError('postgresql://user:secret@host')), FakePool(mixed)):
            self.pool = pool
            response = self.get()
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('secret', response.text)
        del app.dependency_overrides[get_price_analysis_pool]
        self.assertEqual(self.get().status_code, 503)


class StoredChartTests(unittest.IsolatedAsyncioTestCase):
    """The price chart plots the same stored bars the analysis reads."""
    def setUp(self):
        for patcher in (patch.dict('os.environ', {'FINMIND_LIVE_ENABLED': '0'}),
                        patch('backend.src.market_data.app.get_pool', lambda: object())):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(app.dependency_overrides.clear)
        app.dependency_overrides[current_principal] = lambda: Principal(uuid4(), frozenset({'RESEARCHER'}))

    async def test_stored_bars_become_one_ordered_series_or_nothing(self):
        data = await get_stored_bars(FakePool(reversed(price_rows())), 'FPT')
        self.assertEqual((data['source'], data['price_unit'], len(data['bars'])), ('historical', 'thousand_vnd', 21))
        self.assertEqual(data['bars'][-1], {
            'date': '2026-09-21', 'open': '120', 'high': '122', 'low': '119', 'close': '120', 'volume': 200,
            'status': 'closed', 'quality': 'complete', 'price_basis': 'unadjusted', 'volume_basis': 'unknown',
            'source': 'historical'})
        other_scale, same_day = price_rows(), price_rows()
        other_scale[3]['price_scale'] = 1
        same_day[4]['trade_date'] = same_day[5]['trade_date']
        for pool in (FakePool(), FakePool(company=False), FakePool(other_scale), FakePool(same_day)):
            self.assertIsNone(await get_stored_bars(pool, 'FPT'))
        self.assertIsNone(await get_stored_bars(FakePool(price_rows()), 'VNINDEX'))

    async def test_chart_and_analysis_show_the_same_latest_close(self):
        pool = FakePool(price_rows())
        app.dependency_overrides[get_price_analysis_pool] = lambda: pool
        with patch('backend.src.api.routers.market_data.get_pool', lambda: pool), TestClient(app) as client:
            chart = client.get('/api/market-data/stocks/fpt/ohlcv?limit=2').json()
            analysis = client.get(URL.format('FPT') + '?as_of=2026-09-21').json()
        self.assertEqual([bar['date'] for bar in chart['bars']], ['2026-09-20', '2026-09-21'])
        self.assertEqual(chart['bars'][-1]['date'], analysis['as_of'])
        self.assertEqual(Decimal(chart['bars'][-1]['close']), Decimal(analysis['metrics']['close']))

    async def test_chart_keeps_the_saved_file_when_storage_is_unavailable(self):
        for pool in (FakePool(fail=OSError('postgresql://user:secret@host')), FakePool()):
            with patch('backend.src.api.routers.market_data.get_pool', lambda: pool), TestClient(app) as client:
                response = client.get('/api/market-data/stocks/AAA/ohlcv')
            self.assertEqual((response.status_code, response.json()['bars']), (200, []))


@unittest.skipUnless(os.getenv('FINMIND_TEST_POSTGRES') == '1', 'Explicit isolated PostgreSQL check')
class PriceAnalysisPostgresTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_queries_join_exact_dates_and_provenance(self):
        import asyncpg
        from backend.scripts import ingest_market_news_to_supabase as ingest
        symbol = 'Q' + ''.join(chr(65 + int(c, 16)) for c in uuid4().hex[:2])
        company, start = uuid4(), date(2001, 1, 1)
        days = [start + timedelta(days=i) for i in range(21)]
        pool = await asyncpg.create_pool(host='127.0.0.1', port=15434, user='finmind_test',
                                         database='postgres', min_size=1, max_size=2)
        try:
            async with pool.acquire() as conn:
                await conn.execute((ingest.PROJECT_ROOT / 'supabase/migrations/20261111000100_daily_market_activity.sql')
                                   .read_text(encoding='utf-8'))
                await conn.execute('DELETE FROM companies WHERE symbol=$1', symbol)
                await conn.execute('INSERT INTO companies(company_id,symbol) VALUES($1,$2)', company, symbol)
                payload = await ingest.store_payload(conn, ingest.PROJECT_ROOT / f'outputs/analysis-{symbol}.json',
                                                     'vnstock_kbs', 'MARKET_DATA', 'test', {'symbol': symbol}, 1)
                source = await conn.fetchval("SELECT source_id FROM sources WHERE name='vnstock_kbs'")
                await conn.executemany(
                    'INSERT INTO price_bars VALUES ($1,$2,$3,$4,false,1000,$5,$6,$7,$5,$8)',
                    [(uuid4(), company, payload, day, Decimal(100 + i), Decimal(102 + i), Decimal(99 + i),
                      200 if i == 20 else 100) for i, day in enumerate(days)])
                await conn.executemany(
                    '''INSERT INTO market_index_bars(index_symbol,trade_date,close,payload_id)
                       VALUES ('VNINDEX',$1,$2,$3) ON CONFLICT (index_symbol,trade_date) DO UPDATE
                       SET close=EXCLUDED.close, payload_id=EXCLUDED.payload_id''',
                    [(day, Decimal(1000 + i), payload) for i, day in enumerate(days)])
                await conn.execute(
                    '''INSERT INTO daily_market_activity(company_id,trade_date,source_id,volume,foreign_buy_volume,
                         foreign_sell_volume,observation_status,fetched_at,payload_id,field_payload_ids)
                       VALUES ($1,$2,$3,200,30,50,'intraday',$4,$5,$6::jsonb)''',
                    company, days[-1], source, datetime(2001, 1, 21, 4, tzinfo=timezone.utc), payload,
                    '{"volume":"%s"}' % payload)
            try:
                out = await get_price_analysis(pool, symbol, days[-1])
                self.assertEqual((out['session_count'], out['first_date'], out['as_of']), (21, '2001-01-01', '2001-01-21'))
                self.assertEqual(out['metrics']['return_20_percent'], '20.0000')
                self.assertEqual(out['benchmark']['windows']['20']['return_percent'], '2.0000')
                self.assertEqual(out['benchmark']['windows']['20']['difference_percentage_points'], '18.0000')
                latest = out['activity']['latest_observation']
                self.assertEqual((latest['foreign_net_volume'], latest['quality_status']), (-20, 'pending_reconciliation'))
                self.assertEqual(latest['field_payload_ids'], {'volume': str(payload)})
                self.assertIsNone(out['activity']['windows']['1']['foreign_net_volume'])
                self.assertEqual(out['sources']['prices'][0]['source_name'], 'vnstock_kbs')
                self.assertEqual(out['sources']['prices'][0]['payload_id'], str(payload))
                self.assertNotIn('activity_storage_unavailable', out['warnings'])
                self.assertFalse(any('benchmark_missing_provenance' in w for w in out['warnings']))
                self.assertEqual((await get_price_analysis(pool, symbol, days[4]))['session_count'], 5)
                with self.assertRaises(LookupError):
                    await get_price_analysis(pool, symbol, date(2000, 12, 31))
            finally:
                async with pool.acquire() as conn:
                    await conn.execute('DELETE FROM daily_market_activity WHERE company_id=$1', company)
                    await conn.execute('DELETE FROM price_bars WHERE company_id=$1', company)
                    await conn.execute("DELETE FROM market_index_bars WHERE index_symbol='VNINDEX' AND trade_date=ANY($1::date[])", days)
                    await conn.execute('DELETE FROM companies WHERE company_id=$1', company)
        finally:
            await pool.close()


if __name__ == '__main__':
    unittest.main()
