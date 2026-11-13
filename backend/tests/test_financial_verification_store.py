"""Append-only BCTC write layer against a throwaway database on the isolated test cluster."""
from datetime import date
from decimal import Decimal
import asyncio
import json
import unittest
from datetime import datetime, timezone
from uuid import uuid4

from backend.src.financial import verification_store as store
from backend.tests.financial_db_fixture import create_financial_db, drop_financial_db

LOCATOR = dict(dataset_version='v1', ratio_type=None, source_field='isa3', source_section='income_statement',
               unit_status='UNVERIFIED', period_basis='UNVERIFIED', statement_scope='UNKNOWN',
               comparison_basis='UNKNOWN')
ENTRY = dict(symbol='FPT', period_code='2025-Q1', scope='CONSOLIDATED', audit_status='UNKNOWN',
             title='BCTC Q1 2025', url='https://finance.vietstock.vn/x.pdf', external_id='123', last_update=None)


def record(code, value, period='2025-Q1', section='INCOME_STATEMENT'):
    return dict(symbol='FPT', industry_type='TECH', period_code=period, fiscal_year=int(period[:4]),
                quarter=None if period.endswith('YEAR') else int(period[-1]),
                period_type='YEAR' if period.endswith('YEAR') else 'QUARTER', section=section, code=code,
                value=Decimal(value), unit='VND', scale=1, currency='VND', locator_json=dict(LOCATOR),
                published_at=date(2025, 4, 20))


def conclusion(status='VERIFIED', **kw):
    base = dict(document_id=None, statement_scope='CONSOLIDATED', audit_status='UNKNOWN', unit='VND',
                unit_status='VERIFIED', period_basis='STANDALONE_QUARTER', period_start=date(2025, 1, 1),
                period_end=date(2025, 3, 31), fiscal_year_end='12-31', fiscal_label_convention='CALENDAR',
                comparison_basis='AS_REPORTED', checks={'NET_REVENUE': {'result': 'FOUND'}}, evidence=[],
                status=status, reason_codes=['X'])
    base.update(kw)
    return base


class StoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.admin, self.c, self.db = await create_financial_db()
        c = self.c
        self.company = uuid4()
        await c.execute("INSERT INTO companies(company_id,symbol) VALUES($1,'FPT')", self.company)
        for code in ('NET_REVENUE', 'PROFIT_AFTER_TAX'):
            await c.execute("INSERT INTO metrics(metric_id,code,section,industry_scope) "
                            "VALUES($1,$2,'INCOME_STATEMENT','TECH')", uuid4(), code)
        self.period = uuid4()
        await c.execute("INSERT INTO reporting_periods(period_id,period_code,fiscal_year,quarter,period_type,"
                        "start_date,end_date) VALUES($1,'2025-Q1',2025,1,'QUARTER','2025-01-01','2025-03-31')",
                        self.period)
        self.source = await store.ensure_source(c, 'VIETSTOCK_BCTC', source_type='DOCUMENT', base_url='https://v')
        self.job = await store.start_job(c, self.source)
        self.payload = await store.store_payload(c, self.job, source_uri='u', payload_text='{"a": 1}')

    async def asyncTearDown(self):
        await drop_financial_db(self.admin, self.c, self.db)

    async def report(self):
        return await self.c.fetchval('SELECT report_id FROM financial_reports LIMIT 1')

    async def append(self, records):
        return await store.append_reports(self.c, records, job_id=self.job, payload_id=self.payload)

    async def test_ensure_source_does_not_change_approval(self):
        await self.c.execute("UPDATE sources SET approval_status='APPROVED' WHERE source_id=$1", self.source)
        again = await store.ensure_source(self.c, 'VIETSTOCK_BCTC', source_type='X', base_url='y')
        self.assertEqual(again, self.source)
        self.assertEqual(await self.c.fetchval('SELECT count(*) FROM sources WHERE name=$1', 'VIETSTOCK_BCTC'), 1)
        self.assertEqual(await self.c.fetchval('SELECT approval_status FROM sources WHERE source_id=$1',
                                               self.source), 'APPROVED')

    async def test_job_and_payload(self):
        await store.finish_job(self.c, self.job, ok=3, quarantined=1, status='PARTIAL')
        row = await self.c.fetchrow('SELECT * FROM ingestion_jobs WHERE job_id=$1', self.job)
        self.assertEqual(row['trigger_type'], 'BATCH')
        self.assertEqual((row['records_ok'], row['records_quarantined'], row['status']), (3, 1, 'PARTIAL'))
        self.assertIsNotNone(row['finished_at'])
        again = await store.store_payload(self.c, self.job, source_uri='u', payload_text='{"a": 1}')
        self.assertEqual(again, self.payload)

    async def test_ensure_document_same_sha_reuses_row(self):
        kw = dict(company_id=self.company, period_id=self.period, job_id=self.job, sha256='a' * 64,
                  page_count=5, file_size=10)
        first = await store.ensure_document(self.c, ENTRY, **kw)
        second = await store.ensure_document(self.c, ENTRY, **kw)
        self.assertEqual(first, second)
        row = await self.c.fetchrow('SELECT * FROM documents WHERE document_id=$1', first)
        self.assertEqual((row['doc_type'], row['file_type'], row['external_id']),
                         ('FINANCIAL_STATEMENT', 'PDF', '123'))
        self.assertEqual(await self.c.fetchval('SELECT count(*) FROM documents'), 1)
        self.assertEqual((row['parse_status'], row['language']), ('PARSED', 'vi'))

    async def test_document_published_at_must_be_aware(self):
        kw = dict(company_id=self.company, period_id=self.period, job_id=self.job, page_count=1, file_size=1)
        aware = datetime(2026, 8, 22, tzinfo=timezone.utc)
        doc = await store.ensure_document(self.c, {**ENTRY, 'last_update': aware}, sha256='b' * 64, **kw)
        self.assertEqual(await self.c.fetchval('SELECT published_at FROM documents WHERE document_id=$1', doc), aware)
        for bad in (datetime(2026, 8, 22), '2026-08-22'):
            with self.assertRaises(ValueError):
                await store.ensure_document(self.c, {**ENTRY, 'last_update': bad}, sha256='c' * 64, **kw)

    async def test_published_at_iso_string_coerced(self):
        rec = record('NET_REVENUE', '1')
        rec['published_at'] = '2026-08-22T00:00:00'
        await self.append([rec])
        self.assertEqual(await self.c.fetchval('SELECT published_at FROM financial_reports'), date(2026, 8, 22))

    async def test_duplicate_metric_in_group_raises(self):
        with self.assertRaises(ValueError):
            await self.append([record('NET_REVENUE', '1'), record('NET_REVENUE', '2')])

    async def test_concurrent_append_creates_single_version(self):
        import asyncpg
        c2 = await asyncpg.connect(host='127.0.0.1', port=15434, user='finmind_test', database=self.db)
        try:
            async def first():
                async with self.c.transaction():
                    res = await self.append([record('NET_REVENUE', '7')])
                    await asyncio.sleep(0.5)
                    return res

            async def second():
                await asyncio.sleep(0.1)
                async with c2.transaction():
                    return await store.append_reports(c2, [record('NET_REVENUE', '7')], job_id=self.job,
                                                      payload_id=self.payload)
            a, b = await asyncio.gather(first(), second())
        finally:
            await c2.close()
        self.assertEqual((a['new_reports'], b['new_reports'], b['unchanged']), (1, 0, 1))
        self.assertEqual(await self.c.fetchval('SELECT count(*) FROM financial_reports'), 1)

    async def test_concurrent_new_period_reuses_one_row_and_keeps_transactions_healthy(self):
        import asyncpg
        c2 = await asyncpg.connect(host='127.0.0.1', port=15434, user='finmind_test', database=self.db)
        both_read = asyncio.Event()
        reads = 0

        class SynchronizedConnection:
            def __init__(self, conn):
                self.conn = conn
                self.first_read = True

            def __getattr__(self, name):
                return getattr(self.conn, name)

            async def fetchval(self, query, *args):
                nonlocal reads
                result = await self.conn.fetchval(query, *args)
                if self.first_read and query.startswith('SELECT period_id FROM reporting_periods'):
                    self.first_read = False
                    reads += 1
                    if reads == 2:
                        both_read.set()
                    await asyncio.wait_for(both_read.wait(), timeout=3)
                return result

        async def writer(conn):
            async with conn.transaction():
                await conn.execute("SET LOCAL statement_timeout = '5s'")
                period_id = await store._period_id(SynchronizedConnection(conn),
                                                    record('NET_REVENUE', '7', period='2026-Q4'))
                self.assertEqual(await conn.fetchval('SELECT 1'), 1)
                return period_id

        tasks = [asyncio.create_task(writer(conn)) for conn in (self.c, c2)]
        try:
            results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=8)
            self.assertFalse([result for result in results if isinstance(result, BaseException)], results)
            self.assertEqual(results[0], results[1])
            self.assertEqual(await self.c.fetchval(
                "SELECT count(*) FROM reporting_periods WHERE period_code='2026-Q4'"), 1)
            for conn in (self.c, c2):
                self.assertEqual(await conn.fetchval('SELECT 1'), 1)
                self.assertFalse(conn.is_in_transaction())
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await c2.close()

    async def test_append_verification_idempotent(self):
        await self.append([record('NET_REVENUE', '100')])
        rid = await self.report()
        first = await store.append_verification(self.c, rid, self.job, conclusion())
        self.assertIsNotNone(first)
        self.assertIsNone(await store.append_verification(self.c, rid, self.job, conclusion()))
        self.assertEqual(await self.c.fetchval('SELECT count(*) FROM financial_report_verifications'), 1)
        self.assertEqual((await store.current_verification(self.c, rid))['verification_id'], first)

    async def test_append_verification_supersedes(self):
        await self.append([record('NET_REVENUE', '100')])
        rid = await self.report()
        first = await store.append_verification(self.c, rid, self.job, conclusion())
        second = await store.append_verification(self.c, rid, self.job, conclusion('PARTIAL'))
        self.assertNotEqual(first, second)
        rows = {r['verification_id']: r for r in await self.c.fetch('SELECT * FROM financial_report_verifications')}
        self.assertEqual(rows[second]['supersedes_id'], first)
        self.assertEqual(rows[first]['status'], 'VERIFIED')
        self.assertEqual(json.loads(rows[second]['checks'])['reason_codes'], ['X'])
        cur = await store.current_verification(self.c, rid)
        self.assertEqual((cur['status'], cur['reason_codes']), ('PARTIAL', ['X']))

    async def test_append_reports_new_period_and_restatement(self):
        recs = [record('NET_REVENUE', '100'), record('PROFIT_AFTER_TAX', '10')]
        self.assertEqual(await self.append(recs), dict(new_reports=1, new_versions=0, unchanged=0))
        self.assertEqual(await self.c.fetchval('SELECT count(*) FROM observations'), 2)
        r1 = await self.c.fetchrow('SELECT * FROM financial_reports')
        self.assertEqual((r1['report_version'], r1['statement_scope'], r1['audit_status'], r1['period_id'],
                          r1['payload_id'], r1['job_id'], r1['document_id']),
                         (1, 'INCOME_STATEMENT', 'UNKNOWN', self.period, self.payload, self.job, None))
        o = await self.c.fetchrow('SELECT * FROM observations LIMIT 1')
        self.assertEqual((o['unit'], o['scale'], o['currency']), ('VND', 1, 'VND'))
        self.assertEqual(set(json.loads(o['locator_json'])),
                         {'dataset_version', 'ratio_type', 'source_field', 'source_section'})
        self.assertEqual(await self.append(recs), dict(new_reports=0, new_versions=0, unchanged=1))
        recs2 = [record('NET_REVENUE', '101'), record('PROFIT_AFTER_TAX', '10')]
        self.assertEqual(await self.append(recs2), dict(new_reports=0, new_versions=1, unchanged=0))
        v2 = await self.c.fetchrow('SELECT * FROM financial_reports WHERE report_version=2')
        self.assertEqual(v2['restated_from_id'], r1['report_id'])
        self.assertEqual(await self.c.fetchval('SELECT count(*) FROM observations WHERE report_id=$1',
                                               r1['report_id']), 2)
        self.assertEqual(await self.append(recs2), dict(new_reports=0, new_versions=0, unchanged=1))
        # a metric missing from the new records does not by itself make a version
        self.assertEqual(await self.append([record('NET_REVENUE', '101')]),
                         dict(new_reports=0, new_versions=0, unchanged=1))

    async def test_extra_metric_alone_is_unchanged(self):
        await self.c.execute("INSERT INTO metrics(metric_id,code,section,industry_scope) "
                             "VALUES($1,'TOTAL_ASSETS','INCOME_STATEMENT','TECH')", uuid4())
        await self.append([record('NET_REVENUE', '100')])
        self.assertEqual(await self.append([record('NET_REVENUE', '100.0'), record('TOTAL_ASSETS', '5')]),
                         dict(new_reports=0, new_versions=0, unchanged=1))
        self.assertEqual(await self.c.fetchval('SELECT count(*) FROM financial_reports'), 1)
        # a shared metric with a new value still makes a version
        self.assertEqual((await self.append([record('NET_REVENUE', '99'), record('TOTAL_ASSETS', '5')]))
                         ['new_versions'], 1)

    async def test_old_importer_float_noise_is_unchanged(self):
        noisy = {('ROE', 'RATIO'): Decimal('0.419432899299999994990884033541078679263591766357421875'),
                 ('EPS', 'INCOME_STATEMENT'): Decimal('3456.789000000000214322819374501705169677734375')}
        for (code, section), value in noisy.items():
            metric, rid = uuid4(), uuid4()
            await self.c.execute('INSERT INTO metrics(metric_id,code,section,industry_scope) VALUES($1,$2,$3,$4)',
                                 metric, code, section, 'TECH')
            # old-importer shape: statement_scope holds the section name, version 1
            await self.c.execute("INSERT INTO financial_reports(report_id,company_id,period_id,payload_id,job_id,"
                                 "statement_scope,audit_status,report_version) VALUES($1,$2,$3,$4,$5,$6,'UNKNOWN',1)",
                                 rid, self.company, self.period, self.payload, self.job, section)
            await self.c.execute('INSERT INTO observations(observation_id,report_id,metric_id,value) '
                                 'VALUES($1,$2,$3,$4)', uuid4(), rid, metric, value)
        exact = [{**record('ROE', '0.4194328993'), 'section': 'RATIO'}, record('EPS', '3456.789')]
        self.assertEqual(await self.append(exact), dict(new_reports=0, new_versions=0, unchanged=2))
        changed = [{**record('ROE', '0.4194328994'), 'section': 'RATIO'}, record('EPS', '3456.789')]
        self.assertEqual(await self.append(changed), dict(new_reports=0, new_versions=1, unchanged=1))
        self.assertFalse(store.values_differ({'x': Decimal('0.4194328992999999')}, {'x': Decimal('0.4194328993')}))
        self.assertTrue(store.values_differ({'x': Decimal('0.41943289')}, {'x': Decimal('0.4194328993')}))

    async def test_metric_resolved_by_section_and_industry(self):
        bank = uuid4()
        await self.c.execute("INSERT INTO metrics(metric_id,code,section,industry_scope) "
                             "VALUES($1,'PROFIT_AFTER_TAX','INCOME_STATEMENT','BANK')", bank)
        tech = await self.c.fetchval("SELECT metric_id FROM metrics WHERE code='PROFIT_AFTER_TAX' "
                                     "AND industry_scope='TECH'")
        await self.append([record('PROFIT_AFTER_TAX', '10')])
        self.assertEqual(await self.c.fetchval('SELECT metric_id FROM observations'), tech)
        with self.assertRaises(ValueError):  # no BALANCE_SHEET row for this code
            await self.append([record('PROFIT_AFTER_TAX', '10', section='BALANCE_SHEET')])
        with self.assertRaises(ValueError):  # no BANK row for NET_REVENUE
            await self.append([{**record('NET_REVENUE', '10'), 'industry_type': 'BANK'}])

    async def test_market_ratio_only_changes_do_not_create_versions(self):
        for code in ('PE', 'PB'):
            await self.c.execute("INSERT INTO metrics(metric_id,code,section,industry_scope) VALUES($1,$2,'RATIO','TECH')",
                                 uuid4(), code)
        old = [record('PE', '10', section='RATIO'), record('PB', '2', section='RATIO')]
        self.assertEqual(await self.append(old), dict(new_reports=1, new_versions=0, unchanged=0))
        for pe, pb in (('11', '2'), ('10', '3')):
            with self.subTest(pe=pe, pb=pb):
                result = await self.append([record('PE', pe, section='RATIO'), record('PB', pb, section='RATIO')])
                self.assertEqual(result, dict(new_reports=0, new_versions=0, unchanged=1))
        self.assertEqual(await self.c.fetchval('SELECT count(*) FROM financial_reports'), 1)
        self.assertEqual({r['code']: r['value'] for r in await self.c.fetch(
            'SELECT m.code,o.value FROM observations o JOIN metrics m USING(metric_id)')},
                         {'PE': Decimal('10'), 'PB': Decimal('2')})

    async def test_pe_and_revenue_change_still_versions_income(self):
        await self.c.execute("INSERT INTO metrics(metric_id,code,section,industry_scope) VALUES($1,'PE','RATIO','TECH')",
                             uuid4())
        await self.append([record('PE', '10', section='RATIO'), record('NET_REVENUE', '100')])
        result = await self.append([record('PE', '11', section='RATIO'), record('NET_REVENUE', '101')])
        self.assertEqual(result, dict(new_reports=0, new_versions=1, unchanged=1))
        row = await self.c.fetchrow('SELECT statement_scope FROM financial_reports WHERE report_version=2')
        self.assertEqual(row['statement_scope'], 'INCOME_STATEMENT')

    async def test_eps_5571_to_3727_is_an_accounting_restatement(self):
        await self.c.execute('INSERT INTO metrics(metric_id,code,section,industry_scope) '
                             "VALUES($1,'BASIC_EARNINGS_PER_SHARE','INCOME_STATEMENT','TECH')", uuid4())
        await self.append([record('BASIC_EARNINGS_PER_SHARE', '5571', period='2024-YEAR')])
        result = await self.append([record('BASIC_EARNINGS_PER_SHARE', '3727', period='2024-YEAR')])
        self.assertEqual(result, dict(new_reports=0, new_versions=1, unchanged=0))
        self.assertEqual(await self.c.fetchval(
            'SELECT o.value FROM observations o JOIN financial_reports r USING(report_id) WHERE r.report_version=2'),
                         Decimal('3727'))

    async def test_accounting_ratio_restatement_keeps_current_market_values(self):
        for code in ('PE', 'ROE'):
            await self.c.execute("INSERT INTO metrics(metric_id,code,section,industry_scope) VALUES($1,$2,'RATIO','TECH')",
                                 uuid4(), code)
        await self.append([record('PE', '10', section='RATIO'), record('ROE', '0.2', section='RATIO')])
        result = await self.append([record('PE', '11', section='RATIO'), record('ROE', '0.21', section='RATIO')])
        self.assertEqual(result, dict(new_reports=0, new_versions=1, unchanged=0))
        self.assertEqual({r['code']: r['value'] for r in await self.c.fetch(
            'SELECT m.code,o.value FROM observations o JOIN metrics m USING(metric_id) '
            'JOIN financial_reports r USING(report_id) WHERE r.report_version=2')},
                         {'PE': Decimal('11'), 'ROE': Decimal('0.21')})

    async def test_new_period_row_created(self):
        res = await self.append([record('NET_REVENUE', '5', period='2025-YEAR'),
                                 record('NET_REVENUE', '6', period='2026-Q3')])
        self.assertEqual(res['new_reports'], 2)
        rows = {r['period_code']: r for r in await self.c.fetch('SELECT * FROM reporting_periods')}
        y, q = rows['2025-YEAR'], rows['2026-Q3']
        self.assertEqual((y['quarter'], y['period_type'], y['start_date'], y['end_date']),
                         (None, 'YEAR', date(2025, 1, 1), date(2025, 12, 31)))
        self.assertEqual((q['quarter'], q['period_type'], q['start_date'], q['end_date']),
                         (3, 'QUARTER', date(2026, 7, 1), date(2026, 9, 30)))

    async def test_unknown_metric_or_symbol_raises(self):
        with self.assertRaises(ValueError):
            await self.append([record('NOPE', '1')])
        bad = record('NET_REVENUE', '1')
        bad['symbol'] = 'ZZZ'
        with self.assertRaises(ValueError):
            await self.append([bad])

    async def test_quarantine(self):
        await store.quarantine(self.c, self.job, payload_id=self.payload, reason_code='MISMATCH',
                               reasons={'a': 1})
        row = await self.c.fetchrow('SELECT * FROM quarantine_records')
        self.assertEqual((row['reason_code'], row['job_id'], row['payload_id']),
                         ('MISMATCH', self.job, self.payload))


class MarketRatioComparisonTests(unittest.TestCase):
    MARKET_CODES = {'NUMBER_OF_SHARES_MKT_CAP', 'MARKET_CAP', 'DIVIDEND_YIELD', 'PE', 'PB', 'PS',
                    'PRICE_TO_CASH_FLOW', 'EV_TO_EBITDA'}

    def test_only_the_eight_observed_market_codes_are_ignored(self):
        for code in sorted(self.MARKET_CODES):
            with self.subTest(code=code):
                self.assertFalse(store.values_differ({code: Decimal('1')}, {code: Decimal('2')}))

    def test_accounting_metrics_remain_version_triggers(self):
        from backend.src.financial import mapping

        catalogs = [mapping.SECTION_MAPS, *mapping.INDUSTRY_SECTION_MAPS.values()]
        codes = {code for sections in catalogs for fields in sections.values() for code in fields.values()}
        for code in sorted(codes - self.MARKET_CODES):
            with self.subTest(code=code):
                self.assertTrue(store.values_differ({code: Decimal('1')}, {code: Decimal('2')}))
        self.assertTrue(store.values_differ({'BASIC_EARNINGS_PER_SHARE': Decimal('5571')},
                                           {'BASIC_EARNINGS_PER_SHARE': Decimal('3727')}))
        self.assertTrue(store.values_differ({'PE': Decimal('10'), 'NET_REVENUE': Decimal('100')},
                                           {'PE': Decimal('11'), 'NET_REVENUE': Decimal('101')}))


class PayloadResponsivenessTests(unittest.IsolatedAsyncioTestCase):
    async def test_payload_sha_allows_another_coroutine_to_tick(self):
        import threading
        from unittest.mock import patch

        started, released, finished = threading.Event(), threading.Event(), threading.Event()
        original_sha256 = store.hashlib.sha256
        payload_id = uuid4()

        def held_sha256(data):
            started.set()
            try:
                released.wait(timeout=2)
                return original_sha256(data)
            finally:
                finished.set()

        class ExistingPayloadConnection:
            async def fetchval(self, query, *args):
                return payload_id

        async def heartbeat():
            did_start = await asyncio.to_thread(started.wait, 1)
            ticked_during_sha = did_start and not finished.is_set()
            released.set()
            return ticked_during_sha

        try:
            with patch.object(store.hashlib, 'sha256', held_sha256):
                stored, ticked = await asyncio.wait_for(asyncio.gather(
                    store.store_payload(ExistingPayloadConnection(), uuid4(), source_uri='u', payload_text='{"a": 1}'),
                    heartbeat()), timeout=4)
            self.assertEqual(stored, payload_id)
            self.assertTrue(ticked, 'event loop did not tick while payload SHA was held')
        finally:
            released.set()


if __name__ == '__main__':
    unittest.main()
