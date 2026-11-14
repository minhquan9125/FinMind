"""BCTC health calculator reading from the DB (isolated test cluster)."""
from datetime import date
from decimal import Decimal
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from backend.scripts import report_financial_health as cli
from backend.src.financial import verification_store as store
from backend.src.financial.health_db import citation_for, fetch_health_records
from backend.src.financial.health_store import canonical_rows
from backend.tests.financial_db_fixture import create_financial_db, drop_financial_db

LOC = dict(source_section='income_statement', source_field='isa20', ratio_type=None, unit_status='UNVERIFIED')


def conclusion(**kw):
    base = dict(document_id=None, statement_scope='CONSOLIDATED', audit_status='UNKNOWN', unit='VND',
                unit_status='VERIFIED', period_basis='STANDALONE_QUARTER', period_start=date(2025, 1, 1),
                period_end=date(2025, 3, 31), fiscal_year_end='12-31', fiscal_label_convention='CALENDAR',
                comparison_basis='AS_REPORTED', checks={}, evidence=[], status='VERIFIED', reason_codes=[])
    base.update(kw)
    return base


class HealthDbTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.admin, self.c, self.db = await create_financial_db()
        self.company = uuid4()
        await self.c.execute("INSERT INTO companies(company_id,symbol,industry_type) VALUES($1,'FPT','TECH')",
                             self.company)
        self.metric = {}
        for code, section in (('PROFIT_AFTER_TAX', 'INCOME_STATEMENT'), ('TOTAL_ASSETS', 'BALANCE_SHEET'),
                              ('ROE', 'RATIO')):
            self.metric[code] = uuid4()
            await self.c.execute('INSERT INTO metrics(metric_id,code,section) VALUES($1,$2,$3)',
                                 self.metric[code], code, section)
        self.period = uuid4()
        await self.c.execute("INSERT INTO reporting_periods(period_id,period_code,fiscal_year,quarter,period_type,"
                             "start_date,end_date) VALUES($1,'2025-Q1',2025,1,'QUARTER','2025-01-01','2025-03-31')",
                             self.period)
        source = await store.ensure_source(self.c, 'SRC', source_type='X', base_url='b')
        self.job = await store.start_job(self.c, source)
        self.payload = await store.store_payload(
            self.c, self.job, source_uri='u',
            payload_text='{"income_statement": [{"period_label": "2025-Q1", "isa20": 0.4194328993}]}')

    async def asyncTearDown(self):
        await drop_financial_db(self.admin, self.c, self.db)

    async def add_report(self, section='INCOME_STATEMENT', code='PROFIT_AFTER_TAX', value='0.41943289930001',
                         version=1, locator=LOC, unit='UNKNOWN'):
        rid, oid = uuid4(), uuid4()
        await self.c.execute(
            "INSERT INTO financial_reports(report_id,company_id,period_id,payload_id,job_id,statement_scope,"
            "audit_status,report_version) VALUES($1,$2,$3,$4,$5,$6,'UNKNOWN',$7)",
            rid, self.company, self.period, self.payload, self.job, section, version)
        await self.c.execute(
            'INSERT INTO observations(observation_id,report_id,metric_id,value,unit,scale,currency,locator_json) '
            "VALUES($1,$2,$3,$4,$5,1,NULL,$6::jsonb)", oid, rid, self.metric[code], Decimal(value), unit,
            json.dumps(locator))
        return rid, oid

    async def verify(self, rid, **kw):
        await store.append_verification(self.c, rid, self.job, conclusion(**kw))

    async def test_records_merge_current_verification(self):
        rid, _ = await self.add_report()
        await self.verify(rid)
        row = canonical_rows(await fetch_health_records(self.c, ['FPT']))[0]
        self.assertEqual((row['unit'], row['basis'], row['scope']), ('VND', 'QUARTER', 'CONSOLIDATED'))
        self.assertEqual(row['source_locator']['unit_status'], 'VERIFIED')
        self.assertEqual((row['period_start'], row['fiscal_year_end']), ('2025-01-01', '12-31'))
        self.assertEqual(row['source_name'], 'SRC')

    async def test_balance_sheet_is_instant(self):
        rid, _ = await self.add_report('BALANCE_SHEET', 'TOTAL_ASSETS', locator=dict(LOC, source_section='x'))
        await self.verify(rid, period_basis='UNKNOWN')
        row = canonical_rows(await fetch_health_records(self.c, ['FPT']))[0]
        self.assertEqual(row['basis'], 'INSTANT')

    async def test_balance_sheet_instant_without_period_end(self):
        rid, _ = await self.add_report('BALANCE_SHEET', 'TOTAL_ASSETS')
        await self.verify(rid, period_basis='STANDALONE_QUARTER', period_start=None, period_end=None)
        row = canonical_rows(await fetch_health_records(self.c, ['FPT']))[0]
        self.assertEqual(row['basis'], 'INSTANT')

    async def test_ratio_unit_not_verified(self):
        rid, _ = await self.add_report('RATIO', 'ROE', unit='PERCENT')
        rid2, _ = await self.add_report()
        await self.verify(rid)
        await self.verify(rid2)
        rows = {r['metric']: r for r in canonical_rows(await fetch_health_records(self.c, ['FPT']))}
        self.assertEqual(rows['roe']['unit'], 'UNKNOWN')
        self.assertEqual(rows['profit']['unit'], 'VND')

    async def test_payload_fallback_to_observation_value(self):
        await self.add_report(locator=dict(LOC, source_field='missing'), value='12.5')
        rec = (await fetch_health_records(self.c, ['FPT']))[0]
        self.assertEqual(rec['value'], Decimal('12.5'))

    async def test_unverified_report_keeps_unknown(self):
        await self.add_report()
        row = canonical_rows(await fetch_health_records(self.c, ['FPT']))[0]
        self.assertEqual((row['unit'], row['basis'], row['scope']), ('UNKNOWN', 'UNKNOWN', 'UNKNOWN'))

    async def test_mismatch_merges_nothing(self):
        rid, _ = await self.add_report()
        await self.verify(rid, status='MISMATCH')
        row = canonical_rows(await fetch_health_records(self.c, ['FPT']))[0]
        self.assertEqual((row['unit'], row['basis']), ('UNKNOWN', 'UNKNOWN'))

    async def test_value_from_payload_not_float(self):
        await self.add_report()
        rec = (await fetch_health_records(self.c, ['FPT']))[0]
        self.assertEqual(rec['value'], Decimal('0.4194328993'))
        self.assertIsInstance(rec['value'], Decimal)

    async def test_latest_version_only(self):
        await self.add_report(version=1)
        _, oid2 = await self.add_report(version=2)
        recs = await fetch_health_records(self.c, ['FPT'])
        self.assertEqual([r['observation_id'] for r in recs], [str(oid2)])
        self.assertEqual(recs[0]['report_version'], 2)

    async def test_citation_for(self):
        doc = await store.ensure_document(
            self.c, dict(title='BCTC Q1 2025', url='https://x/y.pdf', external_id='1', last_update=None),
            company_id=self.company, period_id=self.period, job_id=self.job, sha256='a' * 64, page_count=9, file_size=1)
        rid, oid = await self.add_report()
        self.assertIsNone(await citation_for(self.c, oid))
        await self.verify(rid, document_id=doc, evidence=[dict(metric='ROE', page=1),
                                                          dict(metric='PROFIT_AFTER_TAX', page=7)])
        self.assertEqual(await citation_for(self.c, oid), dict(title='BCTC Q1 2025', url='https://x/y.pdf', page=7))
        rid2, oid2 = await self.add_report(section='RATIO', code='ROE', version=1)
        await self.verify(rid2, document_id=doc, status='MISMATCH')
        self.assertIsNone(await citation_for(self.c, oid2))

    async def test_report_from_db_cli_readonly(self):
        rid, _ = await self.add_report()
        await self.verify(rid)
        dsn = f'postgresql://finmind_test@127.0.0.1:15434/{self.db}'
        with tempfile.TemporaryDirectory() as out:
            code = await asyncio.to_thread(cli.main, ['--from-db', '--dsn', dsn, '--symbols', 'FPT', '--output', out])
            report = json.loads((Path(out) / 'report.json').read_text(encoding='utf-8'))
        self.assertEqual(code, 0)
        self.assertIn('FPT', report['analyses'])
        with self.assertRaises(SystemExit):
            cli.main(['--from-db', '--snapshot', 'x', '--output', 'o'])

    async def test_verified_money_row_gets_vnd_currency(self):
        # Old importer and capture both leave currency NULL; health._issues needs 'VND' (final review #6a).
        from backend.src.financial.health import _issues
        rid, _ = await self.add_report()
        await self.verify(rid)
        row = canonical_rows(await fetch_health_records(self.c, ['FPT']))[0]
        self.assertEqual((row['unit'], row['currency']), ('VND', 'VND'))
        self.assertNotIn('unverified_money_unit', _issues(row))

    async def test_balance_sheet_window_is_a_single_day(self):
        from backend.src.financial.health import _issues
        rid, _ = await self.add_report('BALANCE_SHEET', 'TOTAL_ASSETS')
        await self.verify(rid)
        row = canonical_rows(await fetch_health_records(self.c, ['FPT']))[0]
        self.assertEqual((row['basis'], row['period_start'], row['period_end']), ('INSTANT', '2025-03-31', '2025-03-31'))
        self.assertNotIn('unverified_or_invalid_period_window', _issues(row))

    async def test_restated_comparison_basis_is_not_merged(self):
        rid, _ = await self.add_report()
        await self.verify(rid, comparison_basis='RESTATED')
        row = canonical_rows(await fetch_health_records(self.c, ['FPT']))[0]
        self.assertEqual(row['comparison_basis'], 'UNKNOWN')

    async def test_citation_needs_a_page(self):
        rid, oid = await self.add_report()
        doc = await store.ensure_document(self.c, dict(title='BCTC', url='https://static2.vietstock.vn/x.pdf',
                                          external_id='1', last_update=None), company_id=self.company,
                                          period_id=self.period, job_id=self.job, sha256='a' * 64, page_count=3,
                                          file_size=10)
        await self.verify(rid, document_id=doc, evidence=[])
        self.assertIsNone(await citation_for(self.c, oid))


    async def test_eps_keeps_its_per_share_unit(self):
        # The verification proves the VND money unit only; EPS stays VND per share (re-review).
        rid, _ = await self.add_report(unit='VND_PER_SHARE')
        await self.verify(rid)
        rec = (await fetch_health_records(self.c, ['FPT']))[0]
        self.assertEqual(rec['unit'], 'VND_PER_SHARE')


    async def test_get_financial_health_for_chat(self):
        from contextlib import asynccontextmanager
        from backend.src.financial import health_db
        health_db._CACHE.update(at=None, rows=None)
        rid, _ = await self.add_report(value='5000000000')
        doc = await store.ensure_document(self.c, dict(title='BCTC Q1', url='https://static2.vietstock.vn/q1.pdf',
                                          external_id='9', last_update=None), company_id=self.company,
                                          period_id=self.period, job_id=self.job, sha256='b' * 64, page_count=3,
                                          file_size=10)
        await self.verify(rid, document_id=doc, evidence=[dict(metric='PROFIT_AFTER_TAX', page=7, unit='VND', snippet='x')])
        conn = self.c

        class Pool:
            @asynccontextmanager
            async def acquire(self):
                yield conn
        health = await health_db.get_financial_health(Pool(), 'FPT')
        self.assertEqual(health['period'], '2025-Q1')
        self.assertTrue(health['signals'])
        self.assertEqual(health['citations'], [dict(title='BCTC Q1', url='https://static2.vietstock.vn/q1.pdf', page=7)])
        self.assertIsNone(await health_db.get_financial_health(Pool(), 'XYZ'))


    async def test_records_carry_text_ids_for_the_calculator(self):
        # The chat path must not lose provenance: health._issues requires string ids (bug found in Task 10).
        from backend.src.financial.health import _issues
        rid, _ = await self.add_report('BALANCE_SHEET', 'TOTAL_ASSETS')
        await self.verify(rid)
        rec = (await fetch_health_records(self.c, ['FPT']))[0]
        self.assertTrue(all(isinstance(rec[k], str) for k in ('observation_id', 'payload_id', 'report_id')))
        row = canonical_rows([rec])[0]
        self.assertFalse({'missing_observation_id', 'missing_payload_id'} & set(_issues(row)))


if __name__ == '__main__':
    unittest.main()
