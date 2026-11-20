"""Offline price-basis gates; no test uses configured PostgreSQL."""
import asyncio
import copy
import importlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

MODULE = 'backend.scripts.reconcile_market_prices'
spec = importlib.util.find_spec(MODULE)
reconcile = importlib.import_module(MODULE) if spec else None


def row(day='2026-10-28', **changes):
    value = dict(symbol='FPT', trade_date=day, open='100', high='102', low='99',
                 close='101', volume=1000, price_scale=1000, is_adjusted=False,
                 source_name='vnstock_kbs')
    value.update(changes)
    return value


class PriceComparisonTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(reconcile, 'PF05 comparison module is not implemented')

    def test_identical_overlap_allows_only_missing_candidate_days(self):
        result = reconcile.compare_price_series([row()], [row(), row('2026-10-29')])
        self.assertEqual(result['status'], 'compatible')
        self.assertEqual(result['counts'], dict(existing=1, candidate=2, matched=1,
                                              different=0, missing=1, existing_only=0))
        self.assertEqual(result['missing'], [{'symbol': 'FPT', 'trade_date': '2026-10-29'}])
        self.assertEqual(result['differences'], [])

    def test_declared_scale_adjustment_and_source_are_required_even_when_prices_match(self):
        for change in ({'price_scale': 1}, {'is_adjusted': True}, {'is_adjusted': None},
                       {'source_name': 'another_vendor'}, {'source_name': None},
                       {'price_scale': None}, {'source_id': 'bad-identity'}):
            with self.subTest(change=change):
                result = reconcile.compare_price_series([row()], [row(**change)])
                self.assertEqual(result['status'], 'unresolved')
                self.assertTrue(result['differences'])

    def test_factor_1000_is_reported_as_exact_ohlc_differences(self):
        result = reconcile.compare_price_series([row()], [row(open='100000', high='102000',
                                                              low='99000', close='101000')])
        self.assertEqual(result['status'], 'unresolved')
        close = next(item for item in result['differences'] if item.get('field') == 'close')
        self.assertEqual((close['existing'], close['candidate']), ('101', '101000'))

    def test_volume_and_price_corrections_are_never_compatible(self):
        for change in ({'volume': 1001}, {'close': '101.0001'}):
            result = reconcile.compare_price_series([row()], [row(**change)])
            self.assertEqual(result['status'], 'unresolved')
            self.assertEqual(result['counts']['different'], 1)

    def test_no_overlap_or_unanchored_symbol_blocks_append(self):
        for rows in ([row('2026-10-29')], [row(), row('2026-10-29', symbol='VCB')]):
            result = reconcile.compare_price_series([row()], rows)
            self.assertEqual(result['status'], 'unresolved')

    def test_duplicates_bad_dates_ohlcv_nan_and_bools_are_rejected(self):
        cases = [[row(), row()]]
        cases += [[row(**change)] for change in (
            {'symbol': '../FPT'}, {'symbol': 'FPT '}, {'trade_date': '2026-1-01'},
            {'trade_date': '2026-10-28T00:00:00'}, {'open': 'NaN'}, {'high': float('inf')},
            {'close': True}, {'low': 0}, {'high': 99}, {'volume': True}, {'volume': -1},
            {'volume': 1.1}, {'volume': 2**63}, {'price_scale': True}, {'is_adjusted': 0},
            {'price_scale': -1}, {'source_name': ''})]
        for rows in cases:
            with self.subTest(rows=rows):
                result = reconcile.compare_price_series([row()], rows)
                self.assertEqual(result['status'], 'unresolved')
                self.assertTrue(result['differences'])

    def test_basis_changes_on_new_nonoverlap_day_are_rejected(self):
        for change in ({'price_scale': 1}, {'is_adjusted': True}, {'source_name': 'other'}):
            result = reconcile.compare_price_series([row()], [row(), row('2026-10-29', **change)])
            self.assertEqual(result['status'], 'unresolved')

    def test_envelope_metadata_is_explicit_and_conflicts_are_rejected(self):
        bar = {key: value for key, value in row().items()
               if key not in ('symbol', 'source_name', 'price_scale', 'is_adjusted')}
        envelope = dict(symbol='FPT', source_name='vnstock_kbs', price_scale=1000,
                        is_adjusted=False, bars=[bar])
        before = copy.deepcopy(envelope)
        self.assertEqual(reconcile.compare_price_series(envelope, envelope)['status'], 'compatible')
        self.assertEqual(envelope, before)
        envelope['bars'][0]['price_scale'] = 1
        self.assertEqual(reconcile.compare_price_series(before, envelope)['status'], 'unresolved')

    def test_date_alias_only_accepted_when_unambiguous(self):
        self.assertEqual(reconcile.compare_price_series([row()], [row(date='2026-10-28')])['status'],
                         'compatible')
        self.assertEqual(reconcile.compare_price_series([row()], [row(date='2026-10-27')])['status'],
                         'unresolved')

    def test_empty_and_wrong_shapes_return_unresolved(self):
        for bad in ([], {}, None, 'rows', [None]):
            self.assertEqual(reconcile.compare_price_series([row()], bad)['status'], 'unresolved')


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(reconcile, 'PF05 receipt module is not implemented')
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.existing = Path(self.directory.name) / 'existing.json'
        self.candidate = Path(self.directory.name) / 'candidate.json'
        self.existing.write_text(json.dumps([row()]), encoding='utf-8')
        self.candidate.write_text(json.dumps([row(), row('2026-10-29')]), encoding='utf-8')

    def test_cli_dryrun_never_imports_database_or_reads_runtime_config(self):
        code = """import builtins, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name == 'asyncpg' or name.startswith('backend.src.core.config') or name == 'dotenv':
        raise AssertionError('dryrun reached DB/config')
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from backend.scripts.reconcile_market_prices import main
raise SystemExit(main(sys.argv[1:]))
"""
        done = subprocess.run([sys.executable, '-B', '-c', code, '--existing', str(self.existing),
                               '--candidate', str(self.candidate)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        receipt = json.loads(done.stdout)
        self.assertEqual(receipt['comparison']['status'], 'compatible')
        self.assertEqual(len(receipt['existing_sha256']), 64)
        self.assertEqual(sorted(p.name for p in self.existing.parent.iterdir()),
                         ['candidate.json', 'existing.json'])

    def test_changed_files_and_forged_comparison_invalidate_saved_receipt(self):
        receipt = reconcile.build_receipt(self.existing, self.candidate)
        reconcile.verify_receipt(receipt, self.existing, self.candidate)
        forged = copy.deepcopy(receipt)
        forged['comparison']['counts']['matched'] = 99
        with self.assertRaises(ValueError):
            reconcile.verify_receipt(forged, self.existing, self.candidate)
        self.candidate.write_text(self.candidate.read_text() + '\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            reconcile.verify_receipt(receipt, self.existing, self.candidate)

    def test_append_checks_receipt_and_basis_before_touching_database(self):
        class NoDatabase:
            def transaction(self):
                raise AssertionError('Unsafe candidate reached database')
        receipt = reconcile.build_receipt(self.existing, self.candidate)
        self.candidate.write_text(json.dumps([row(), row('2026-10-29', close='101.5')]), encoding='utf-8')
        with self.assertRaises(ValueError):
            asyncio.run(reconcile.append_missing(NoDatabase(), self.existing, self.candidate, receipt))
        self.candidate.write_text(json.dumps([row(source_name='other')]), encoding='utf-8')
        unresolved = reconcile.build_receipt(self.existing, self.candidate)
        with self.assertRaises(ValueError):
            asyncio.run(reconcile.append_missing(NoDatabase(), self.existing, self.candidate, unresolved))

    def test_unresolved_apply_and_missing_receipt_fail_before_runtime_config(self):
        with patch.object(reconcile, '_apply_runtime', side_effect=AssertionError('DB reached')):
            with patch('sys.stdout', new_callable=io.StringIO), patch('sys.stderr', new_callable=io.StringIO):
                self.assertNotEqual(reconcile.main(['--existing', str(self.existing), '--candidate',
                                                   str(self.candidate), '--apply']), 0)
                self.candidate.write_text(json.dumps([row(source_name='other')]), encoding='utf-8')
                saved = self.existing.parent / 'receipt.json'
                saved.write_text(json.dumps(reconcile.build_receipt(self.existing, self.candidate)))
                self.assertNotEqual(reconcile.main(['--existing', str(self.existing), '--candidate',
                                                   str(self.candidate), '--apply', '--receipt', str(saved)]), 0)


@unittest.skipUnless(os.getenv('FINMIND_TEST_POSTGRES') == '1', 'Explicit isolated PostgreSQL check')
class AppendPostgresTests(unittest.IsolatedAsyncioTestCase):
    async def test_append_only_after_database_still_equals_reviewed_export(self):
        import asyncpg
        from backend.scripts import ingest_market_news_to_supabase as ingest
        folder = ingest.PROJECT_ROOT / '.agent-state/replay-test' / uuid4().hex
        folder.mkdir(parents=True)
        existing, candidate = folder / 'existing.json', folder / 'candidate.json'
        existing.write_text(json.dumps([row()]), encoding='utf-8')
        candidate.write_text(json.dumps([row(), row('2026-10-29', close='101.5')]), encoding='utf-8')
        receipt = reconcile.build_receipt(existing, candidate)
        conn = await asyncpg.connect(host='127.0.0.1', port=15434, user='finmind_test', database='postgres')
        other = await asyncpg.connect(host='127.0.0.1', port=15434, user='finmind_test', database='postgres')
        outer = conn.transaction()
        await outer.start()
        try:
            company = await conn.fetchval("SELECT company_id FROM companies WHERE symbol='FPT'")
            await conn.execute('DELETE FROM price_bars WHERE company_id=$1', company)
            payload = await ingest.store_payload(conn, existing, 'vnstock_kbs', 'MARKET_DATA', 'test', [row()], 1)
            await conn.execute('''INSERT INTO price_bars VALUES ($1,$2,$3,'2026-10-28',false,1000,100,102,99,101,1000)''',
                               uuid4(), company, payload)
            count = lambda: conn.fetchval('SELECT count(*) FROM price_bars WHERE company_id=$1', company)
            test=self
            class CheckedConnection:
                def __getattr__(self,name):return getattr(conn,name)
                async def fetch(self,sql,*args):
                    rows=await conn.fetch(sql,*args)
                    if 'FROM public.price_bars b' in sql:
                        async with other.transaction():
                            await other.execute("SET LOCAL lock_timeout='100ms'")
                            with test.assertRaises(asyncpg.LockNotAvailableError):
                                await other.execute('UPDATE public.price_bars SET price_scale=1 WHERE false')
                    return rows
            self.assertEqual((await reconcile.append_missing(CheckedConnection(), existing, candidate, receipt))['inserted'], 1)
            added = await conn.fetchrow("SELECT close,payload_id FROM price_bars WHERE company_id=$1 AND trade_date='2026-10-29'", company)
            self.assertEqual(str(added['close']), '101.5000')
            self.assertNotEqual(added['payload_id'], payload)
            # A rerun finds a newer stored day than the reviewed export and writes nothing.
            with self.assertRaises(ValueError):
                await reconcile.append_missing(conn, existing, candidate, receipt)
            self.assertEqual(await count(), 2)
            await conn.execute("DELETE FROM price_bars WHERE company_id=$1 AND trade_date='2026-10-29'", company)
            await conn.execute('UPDATE price_bars SET close=101.1 WHERE company_id=$1', company)
            with self.assertRaises(ValueError):
                await reconcile.append_missing(conn, existing, candidate, receipt)
            self.assertEqual(await count(), 1)
        finally:
            await outer.rollback()
            await conn.close()
            await other.close()


if __name__ == '__main__':
    unittest.main()
