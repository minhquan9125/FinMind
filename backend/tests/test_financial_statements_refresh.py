"""BCTC refresh job, fully offline: fake Vietcap capture, fake Vietstock catalog and downloads,
throwaway database on the test cluster 127.0.0.1:15434 (never production 15433)."""
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from io import BytesIO
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock
from uuid import uuid4
import zipfile

import asyncpg
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from backend.scripts import refresh_financial_statements as job
from backend.src.financial import exact_json, mapping
from backend.src.financial import verification_store as store
from backend.tests.financial_db_fixture import create_financial_db, drop_financial_db
from data_pipeline.annual_reports import vietstock_download_annual as annual
from data_pipeline.financial_data import financial_capture as capture

NOW = datetime(2026, 11, 12, 11, 0, tzinfo=timezone.utc)
BANKS = ('VCB', 'BID', 'CTG', 'MBB', 'TCB')
SECTION_FIELDS = {'INCOME_STATEMENT': ('isa1', 'isa3', 'isb38', 'isa20'), 'BALANCE_SHEET': ('bsa53', 'bsa78'),
                  'CASH_FLOW': ('cfa18',), 'RATIO': ('roe',)}
TABLES = ('sources', 'ingestion_jobs', 'raw_payloads', 'reporting_periods', 'financial_reports', 'observations',
          'documents', 'financial_report_verifications', 'quarantine_records')
CONS_2025, SEP_2025, CONS_2024 = (f'https://static2.vietstock.vn/data/FPT/{n}.pdf' for n in (501, 502, 401))


def fields(symbol, year, bump=0):
    n = 10 ** 12 * (job.SYMBOLS.index(symbol) + 1) + year * 10 ** 6 + bump
    income = {'isb38': n} if symbol in BANKS else {'isa3': n, 'isa1': None}  # None: mapped field without value
    return {**income, 'isa20': n // 5, 'bsa53': n * 7, 'bsa78': n * 2, 'cfa18': n // 3, 'roe': Decimal('0.1875')}


def provider_payload(symbol, section, data):
    rows = []
    for period, values in data.items():
        year, q = int(period[:4]), 5 if period.endswith('YEAR') else int(period[-1])
        own = {k: v for k, v in values.items() if k in SECTION_FIELDS[section]}
        if section == 'RATIO':
            rows.append(dict(ticker=symbol, yearReport=year, quarter=q, **own))
        else:
            rows.append(dict(ticker=symbol, organCode=symbol, yearReport=year, lengthReport=q,
                             publicDate='2026-03-01T00:00:00', **own))
    if section == 'RATIO':
        return {'successful': True, 'data': rows}
    return {'successful': True, 'data': {'quarters': [r for r in rows if r['lengthReport'] != 5],
                                         'years': [r for r in rows if r['lengthReport'] == 5]}}


def text_pdf(lines):
    writer = PdfWriter()
    page = writer.add_blank_page(612, 792)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'),
                             NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject(
        {NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(('BT /F1 9 Tf 11 TL 30 770 Td ' + ' '.join(f'({line}) Tj T*' for line in lines)
                     + ' ET').encode('latin-1'))
    page[NameObject('/Contents')] = writer._add_object(stream)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def blank_pdf():
    writer = PdfWriter()
    writer.add_blank_page(612, 792)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def zip_bytes(members):
    out = BytesIO()
    with zipfile.ZipFile(out, 'w') as archive:
        for name, data in members:
            archive.writestr(name, data)
    return out.getvalue()


def dotted(n):
    return f'{n:,}'.replace(',', '.')


def statement_pdf(current, prior):
    return text_pdf(['BAO CAO TAI CHINH HOP NHAT cho nam tai chinh ket thuc ngay 31 thang 12 nam 2025',
                     'Don vi tinh: VND',
                     f"Doanh thu thuan {dotted(current['isa3'])} {dotted(prior['isa3'])}",
                     f"Loi nhuan sau thue {dotted(current['isa20'])} {dotted(prior['isa20'])}",
                     f"Tong cong tai san {dotted(current['bsa53'])} {dotted(prior['bsa53'])}",
                     'Thuyet minh kem theo la mot bo phan hop thanh cua bao cao tai chinh nay. ' * 2])


def wrong_pdf():
    return text_pdf(['BAO CAO TAI CHINH nam tai chinh ket thuc ngay 31 thang 12 nam 2024', 'Don vi tinh: VND',
                     'Doanh thu thuan 5.555.555.555.555', 'Loi nhuan sau thue 4.444.444.444.444',
                     'Tong cong tai san 3.333.333.333.333',
                     'Thuyet minh kem theo la mot bo phan hop thanh cua bao cao tai chinh nay. ' * 2])


def catalog_row(title, url, fid, ms=1_767_000_000_000):
    return {'Title': title, 'Url': url, 'LastUpdate': f'/Date({ms})/', 'FileInfoID': fid}


class FakeVietstock:
    delay = 1.0

    def __init__(self, rows, fail=()):
        self.rows, self.fail = rows, set(fail)

    def document_type(self, *names, exact=False):
        return 7

    def reports_for(self, symbol, year, *, document_type_id, term_id):
        if symbol in self.fail:
            raise ConnectionError('vietstock down')
        return self.rows.get((symbol, year, term_id), [])


class RefreshLoopTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        patch = mock.patch.object(job, 'ROOT', self.root)
        patch.start()
        self.addCleanup(patch.stop)
        patch = mock.patch.object(annual, 'ROOT', self.root)
        patch.start()
        self.addCleanup(patch.stop)

    async def assert_loop_responsive(self, operation, target, name):
        entered, release, responsive = threading.Event(), threading.Event(), threading.Event()
        original = getattr(target, name)

        def slow(*args, **kwargs):
            if not entered.is_set():
                entered.set()
                if release.wait(2):  # timeout only releases a regression that blocks the loop
                    responsive.set()
            return original(*args, **kwargs)

        async def tick():
            self.assertTrue(await asyncio.to_thread(entered.wait, 2), f'{name} was not reached')
            release.set()

        try:
            with mock.patch.object(target, name, slow):
                result, _ = await asyncio.gather(operation, tick())
        finally:
            release.set()
        self.assertTrue(responsive.is_set(), f'{name} blocked the event loop')
        return result

    async def test_pdf_read_pages_keeps_event_loop_responsive(self):
        entry = dict(symbol='FPT', period_code='2025-YEAR', external_id='501', url=CONS_2025)
        data = text_pdf(['Doanh thu va tai san cua cong ty. ' * 8])

        def download(url, target):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)

        result = await self.assert_loop_responsive(
            job.fetch_pdf(mock.AsyncMock(), entry, download), job.statement_pdf, 'read_pages')
        self.assertEqual(result['sha256'], hashlib.sha256(data).hexdigest())

    async def test_decide_keeps_event_loop_responsive(self):
        entry = dict(period_code='2025-YEAR', scope='CONSOLIDATED', audit_status='AUDITED',
                     title='BCTC 2025', url=CONS_2025)
        pdf = dict(entry=entry, pages=[])
        inputs = dict(period_code='2025-YEAR', industry='TECH', values={})
        with mock.patch.object(job, 'fetch_pdf', new=mock.AsyncMock(return_value=pdf)):
            fetched, best = await self.assert_loop_responsive(
                job.choose(mock.AsyncMock(), inputs, [entry], mock.Mock(), []), job, 'decide')
        self.assertEqual(fetched, [pdf])
        self.assertEqual(best[1]['status'], 'PARTIAL')

    async def test_run_setup_and_cleanup_keep_event_loop_responsive(self):
        client = mock.Mock()
        for target, name in ((Path, 'mkdir'), (job.json, 'dumps'), (Path, 'write_text'),
                             (client.session, 'close')):
            with self.subTest(operation=name), mock.patch.object(job, 'VietstockAnnualClient', return_value=client):
                result = await self.assert_loop_responsive(job.run(False, now=NOW, symbols=()), target, name)
                self.assertEqual(result, 0)


    async def test_single_zip_pdf_cached_and_reused(self):
        entry = dict(symbol='CTG', period_code='2025-YEAR', external_id='701', url=CONS_2025)
        data = text_pdf(['Doanh thu va tai san cua cong ty. ' * 8])
        archive = zip_bytes([('nested/report.PDF', data), ('readme.txt', b'notes')])
        downloads = []

        def download(url, target):
            downloads.append(url)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive)

        conn = mock.AsyncMock()
        conn.fetch.return_value = []
        result = await job.fetch_pdf(conn, entry, download)
        self.assertIsNotNone(result)
        cached = self.root / 'data/references/vietstock/financial_statements/files/CTG/2025-YEAR/701.pdf'
        self.assertEqual(cached.read_bytes(), data)
        self.assertEqual((result['sha256'], result['file_size'], result['page_count']),
                         (hashlib.sha256(data).hexdigest(), len(data), 1))
        self.assertIn('Doanh thu va tai san', result['pages'][0])
        self.assertEqual(await job.fetch_pdf(conn, entry, download), result)
        self.assertEqual(downloads, [entry['url']])

    async def test_zip_without_one_safe_pdf_skipped(self):
        data = text_pdf(['Doanh thu va tai san cua cong ty. ' * 8])
        unsafe = [f'escaped-{kind}-{uuid4().hex}.pdf' for kind in ('posix', 'windows', 'absolute')]
        cases = {'multiple': [('first.pdf', data), ('second.pdf', data)],
                 'zero': [('readme.txt', b'notes'), ('fake.pdf', b'not a PDF')],
                 'traversal': [(f'../{unsafe[0]}', data), (f'..\\{unsafe[1]}', data), (f'/{unsafe[2]}', data)],
                 'corrupt': None}
        inputs = dict(period_code='2025-YEAR', industry='BANK', values={})
        for name, members in cases.items():
            with self.subTest(archive=name):
                entry = dict(symbol='CTG', period_code='2025-YEAR', external_id=name, url=CONS_2025,
                             scope='CONSOLIDATED', audit_status='AUDITED', title='BCTC 2025')
                archive = zip_bytes(members) if members is not None else b'PK\x03\x04broken'

                def download(url, target):
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive)

                skipped = []
                self.assertEqual(await job.choose(mock.AsyncMock(), inputs, [entry], download, skipped), ([], None))
                self.assertEqual(skipped, [dict(period_code='2025-YEAR', external_id=name,
                                                reason='DOWNLOAD_NOT_PDF')])
                cached = self.root / 'data/references/vietstock/financial_statements/files/CTG/2025-YEAR' / f'{name}.pdf'
                self.assertFalse(cached.exists())
        for name in unsafe:
            self.assertEqual(list(self.root.rglob(name)), [])


class PlanReportsComparisonTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def records(values, period='2025-YEAR'):
        return [dict(code=code, section=section, value=Decimal(value), period_code=period, industry_type='TECH')
                for code, section, value in values]

    class Connection:
        def __init__(self, old):
            self.old = old

        async def fetch(self, query, *args):
            if query.startswith('SELECT m.code,o.value FROM observations'):
                return [dict(code=r['code'], value=r['value']) for r in self.old if r['section'] == args[0]]
            raise AssertionError(query)

        async def fetchval(self, query, company_id, period, section):
            if not query.startswith('SELECT r.report_id FROM financial_reports'):
                raise AssertionError(query)
            return section if any(r['period_code'] == period and r['section'] == section for r in self.old) else None

    async def test_plan_reports_market_ratio_only_changes_are_unchanged(self):
        old = self.records([('PE', 'RATIO', '10'), ('PB', 'RATIO', '2')])
        for changed in ([('PE', 'RATIO', '11'), ('PB', 'RATIO', '2')],
                        [('PE', 'RATIO', '10'), ('PB', 'RATIO', '3')]):
            with self.subTest(changed=changed):
                counts, fresh = await job.plan_reports(self.Connection(old), uuid4(), self.records(changed))
                self.assertEqual(counts, dict(new_reports=0, new_versions=0))
                self.assertEqual(fresh, set())

    async def test_plan_reports_pe_and_revenue_change_still_versions_income(self):
        old = self.records([('PE', 'RATIO', '10'), ('NET_REVENUE', 'INCOME_STATEMENT', '100')])
        records = self.records([('PE', 'RATIO', '11'), ('NET_REVENUE', 'INCOME_STATEMENT', '101')])
        counts, fresh = await job.plan_reports(self.Connection(old), uuid4(), records)
        self.assertEqual(counts, dict(new_reports=0, new_versions=1))
        self.assertEqual(fresh, {('2025-YEAR', 'INCOME_STATEMENT')})

    async def test_plan_reports_eps_restatement_still_versions_income(self):
        old = self.records([('BASIC_EARNINGS_PER_SHARE', 'INCOME_STATEMENT', '5571')], period='2024-YEAR')
        records = self.records([('BASIC_EARNINGS_PER_SHARE', 'INCOME_STATEMENT', '3727')], period='2024-YEAR')
        counts, fresh = await job.plan_reports(self.Connection(old), uuid4(), records)
        self.assertEqual(counts, dict(new_reports=0, new_versions=1))
        self.assertEqual(fresh, {('2024-YEAR', 'INCOME_STATEMENT')})


class RefreshTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.admin, self.c, self.db = await create_financial_db()
        for symbol in job.SYMBOLS:
            await self.c.execute('INSERT INTO companies(company_id,symbol,industry_type,sector) VALUES($1,$2,$3,$4)',
                                 uuid4(), symbol, 'BANK' if symbol in BANKS else 'TECH', 'x')
        # production shape: one metrics row per (code, section, industry_scope)
        keys = {(mapping.get_code(f, capture.SECTIONS[s], ind), s, ind) for s, fs in SECTION_FIELDS.items()
                for f in fs for ind in ('BANK', 'TECH')}
        for key in keys:
            await self.c.execute('INSERT INTO metrics(metric_id,code,section,industry_scope) VALUES($1,$2,$3,$4)',
                                 uuid4(), *key)
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.patch = mock.patch.object(job, 'ROOT', self.root)
        self.patch.start()
        self.data = {s: {f'{y}-YEAR': fields(s, y) for y in (2024, 2025)} for s in job.SYMBOLS}
        fpt = self.data['FPT']
        self.files = {CONS_2025: statement_pdf(fpt['2025-YEAR'], fpt['2024-YEAR']),
                      SEP_2025: statement_pdf(fpt['2025-YEAR'], fpt['2024-YEAR']), CONS_2024: blank_pdf()}
        self.catalog = {('FPT', 2025, 1): [catalog_row('BCTC Hop nhat Kiem toan nam 2025', CONS_2025, 501),
                                           catalog_row('BCTC Cong ty me Kiem toan nam 2025', SEP_2025, 502)],
                        ('FPT', 2024, 1): [catalog_row('BCTC Hop nhat Kiem toan nam 2024', CONS_2024, 401)]}
        self.downloads, self.reports = [], []

    async def asyncTearDown(self):
        self.patch.stop()
        self.tmp.cleanup()
        await drop_financial_db(self.admin, self.c, self.db)

    def fetch_vietcap(self, symbols, output_root, profiles):
        run = Path(output_root) / ('capture-' + uuid4().hex[:8])
        run.mkdir(parents=True)
        manifest = dict(dataset_version=run.name, run_dir=str(run), status='complete', companies={})
        for symbol in symbols:
            decoded, receipts = {}, {}
            for section in capture.SECTIONS:
                payload = provider_payload(symbol, section, self.data[symbol])
                payload['serverDateTime'] = getattr(self, 'stamp', '2026-11-12T11:00:00')  # Vietcap varies this per call
                raw = exact_json.dumps(payload).encode('utf-8')
                name = f'{symbol}-{section}-1.response'
                (run / name).write_bytes(raw)
                decoded[section] = capture.decode_section(raw, symbol=symbol, section=section)
                receipts[section] = dict(status='complete', path=name, sha256=hashlib.sha256(raw).hexdigest(),
                                         url=f'https://iq.vietcap.com.vn/x/{symbol}/{section}',
                                         received_at='2026-11-12T11:00:00+00:00')
            (run / f'{symbol}-normalized.json').write_text(exact_json.dumps(dict(
                symbol=symbol, profile=profiles[symbol],
                financial_data={capture.SECTIONS[k]: v for k, v in decoded.items()})), encoding='utf-8')
            manifest['companies'][symbol] = dict(status='complete', normalized_path=f'{symbol}-normalized.json',
                                                 sections=receipts)
        return manifest

    def download(self, url, target):
        self.downloads.append(url)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.files[url])
        return len(self.files[url])

    async def run_job(self, apply, symbols=('FPT',), fail=()):
        return await job.run(apply, now=NOW, symbols=symbols, fetch_vietcap=self.fetch_vietcap,
                             vietstock=FakeVietstock(self.catalog, fail), download=self.download,
                             connect=lambda: asyncpg.connect(host='127.0.0.1', port=15434, user='finmind_test',
                                                             database=self.db),
                             on_report=self.reports.append)

    async def counts(self):
        return {t: await self.c.fetchval(f'SELECT count(*) FROM {t}') for t in TABLES}

    async def current(self, period, section='INCOME_STATEMENT'):
        rid = await self.c.fetchval(
            'SELECT r.report_id FROM financial_reports r JOIN reporting_periods p USING (period_id) '
            'JOIN companies c USING (company_id) WHERE c.symbol=$1 AND p.period_code=$2 AND r.statement_scope=$3 '
            'ORDER BY r.report_version DESC LIMIT 1', 'FPT', period, section)
        return await store.current_verification(self.c, rid)

    async def test_dry_run_writes_nothing(self):
        before = await self.counts()
        self.assertEqual(await job.run(False, now=NOW, fetch_vietcap=self.fetch_vietcap,
                                       vietstock=FakeVietstock(self.catalog), download=self.download,
                                       connect=lambda: asyncpg.connect(host='127.0.0.1', port=15434,
                                                                       user='finmind_test', database=self.db),
                                       on_report=self.reports.append), 0)
        self.assertEqual(await self.counts(), before)
        written = list((self.root / 'outputs/financial-refresh').glob('*/report.json'))
        self.assertEqual(len(written), 1)
        report = exact_json.loads(written[0].read_text(encoding='utf-8'))
        self.assertEqual(set(report), {'started_at', 'apply', 'symbols', 'documents_added'})
        self.assertEqual(set(report['symbols']), set(job.SYMBOLS))
        self.assertFalse(report['apply'])
        fpt = report['symbols']['FPT']
        self.assertEqual(set(fpt), {'status', 'new_reports', 'new_versions', 'verifications_added', 'verified',
                                    'partial', 'mismatch', 'skipped', 'error', 'unknown_metrics'})
        # 2 periods x 4 sections would be new; IS + BS of both periods get a verification.
        self.assertEqual((fpt['status'], fpt['new_reports'], fpt['verifications_added'], fpt['verified'],
                          fpt['partial']), ('ok', 8, 4, 2, 2))
        self.assertEqual(report['documents_added'], 2)
        self.assertTrue(all(item['status'] == 'ok' for item in report['symbols'].values()))
        self.assertEqual(sorted(self.downloads), sorted([CONS_2025, CONS_2024]))  # PDFs still cached

    async def test_apply_then_rerun_adds_nothing(self):
        self.assertEqual(await self.run_job(True, symbols=('FPT', 'BID')), 0)
        first = self.reports[-1]
        self.assertTrue(first['apply'])
        self.assertEqual((first['symbols']['FPT']['new_reports'], first['symbols']['FPT']['verifications_added'],
                          first['symbols']['BID']['new_reports'], first['documents_added']), (8, 4, 8, 2))
        self.assertNotIn(SEP_2025, self.downloads)  # consolidated verified: separate file never fetched
        verified = await self.current('2025-YEAR', 'BALANCE_SHEET')
        self.assertEqual((verified['status'], verified['statement_scope'], verified['audit_status']),
                         ('VERIFIED', 'CONSOLIDATED', 'AUDITED'))
        doc = await self.c.fetchrow('SELECT * FROM documents WHERE document_id=$1', verified['document_id'])
        self.assertEqual((doc['external_id'], doc['source_url']), ('501', CONS_2025))
        self.assertEqual(await self.c.fetchval(
            "SELECT count(*) FROM observations o JOIN metrics m USING (metric_id) WHERE m.code='GROSS_REVENUE'"), 0)
        before = await self.counts()
        self.assertEqual(await self.run_job(True, symbols=('FPT', 'BID')), 0)
        second = self.reports[-1]
        for symbol in ('FPT', 'BID'):
            item = second['symbols'][symbol]
            self.assertEqual((item['new_reports'], item['new_versions'], item['verifications_added']), (0, 0, 0))
        self.assertEqual(second['documents_added'], 0)
        after = await self.counts()
        for table in ('financial_reports', 'observations', 'documents', 'financial_report_verifications',
                      'raw_payloads', 'quarantine_records'):
            self.assertEqual(after[table], before[table], table)

    async def test_network_error_isolated_per_symbol(self):
        self.assertEqual(await self.run_job(True, symbols=('BID', 'FPT'), fail=('BID',)), 1)
        report = self.reports[-1]
        self.assertEqual(report['symbols']['BID']['status'], 'failed')
        self.assertIn('vietstock down', report['symbols']['BID']['error'])
        self.assertEqual(report['symbols']['FPT']['status'], 'ok')
        count = 'SELECT count(*) FROM financial_reports JOIN companies USING (company_id) WHERE symbol=$1'
        self.assertEqual(await self.c.fetchval(count, 'BID'), 0)
        self.assertEqual(await self.c.fetchval(count, 'FPT'), 8)

    async def test_unscanned_pdf_partial(self):
        self.assertEqual(await self.run_job(True), 0)
        for section in ('INCOME_STATEMENT', 'BALANCE_SHEET'):
            cur = await self.current('2024-YEAR', section)
            self.assertEqual(cur['status'], 'PARTIAL')
            self.assertIn('NO_TEXT_LAYER', cur['reason_codes'])
        self.assertEqual(self.reports[-1]['symbols']['FPT']['partial'], 2)

    async def test_cache_sha_mismatch_redownloads(self):
        self.assertEqual(await self.run_job(True), 0)
        cached = self.root / 'data/references/vietstock/financial_statements/files/FPT/2025-YEAR/501.pdf'
        self.assertEqual(cached.read_bytes(), self.files[CONS_2025])
        cached.write_bytes(b'tampered')
        self.downloads.clear()
        self.assertEqual(await self.run_job(True), 0)
        self.assertEqual(self.downloads, [CONS_2025])  # the intact 2024 file is served from the cache
        self.assertEqual(cached.read_bytes(), self.files[CONS_2025])
        self.assertEqual(self.reports[-1]['documents_added'], 0)

    async def test_mismatch_tries_separate_then_quarantines(self):
        self.files[CONS_2025] = wrong_pdf()
        self.files[CONS_2024] = wrong_pdf()
        self.assertEqual(await self.run_job(True), 0)
        self.assertIn(SEP_2025, self.downloads)
        cur = await self.current('2025-YEAR')
        self.assertEqual((cur['status'], cur['statement_scope']), ('VERIFIED', 'SEPARATE'))
        old = await self.current('2024-YEAR')
        # final review #7: no required number was found in the file, so its title is not evidence of scope
        self.assertEqual((old['status'], old['statement_scope']), ('MISMATCH', 'UNKNOWN'))
        rows = await self.c.fetch('SELECT * FROM quarantine_records')
        self.assertEqual(len(rows), 2)  # IS + BS of 2024
        self.assertEqual({r['reason_code'] for r in rows}, {'VERIFICATION_MISMATCH'})
        self.assertEqual(self.reports[-1]['symbols']['FPT']['mismatch'], 2)
        self.assertEqual(await self.run_job(True), 0)
        self.assertEqual(await self.c.fetchval('SELECT count(*) FROM quarantine_records'), 2)  # not re-quarantined

    async def test_too_many_restatements_rolls_back(self):
        self.assertEqual(await self.run_job(True), 0)
        before = await self.counts()
        self.data['FPT'] = {f'{y}-YEAR': fields('FPT', y, bump=1) for y in (2024, 2025)}
        self.assertEqual(await self.run_job(True), 1)
        item = self.reports[-1]['symbols']['FPT']
        self.assertEqual((item['status'], item['error']), ('failed', 'TOO_MANY_RESTATEMENTS'))
        after = await self.counts()
        for table in ('financial_reports', 'observations', 'documents', 'financial_report_verifications'):
            self.assertEqual(after[table], before[table], table)

    async def test_replaced_file_same_id_redownloads(self):
        self.assertEqual(await self.run_job(True), 0)
        first = (await self.current('2025-YEAR'))['document_id']
        self.catalog[('FPT', 2025, 1)][0] = catalog_row('BCTC Hop nhat Kiem toan nam 2025', CONS_2025, 501,
                                                        ms=4_102_444_800_000)  # LastUpdate after the cached copy
        self.files[CONS_2025] += b'\n%replaced at source\n'
        self.downloads.clear()
        self.assertEqual(await self.run_job(True), 0)
        self.assertEqual(self.downloads, [CONS_2025])
        self.assertEqual(self.reports[-1]['documents_added'], 1)
        current = await self.current('2025-YEAR')
        self.assertNotEqual(current['document_id'], first)
        self.assertEqual(await self.c.fetchval('SELECT external_id FROM documents WHERE document_id=$1',
                                               current['document_id']), '501')
        self.downloads.clear()
        self.assertEqual(await self.run_job(True), 0)
        self.assertEqual(self.downloads, [])  # the stored document now carries that LastUpdate

    async def test_non_pdf_download_falls_back(self):
        self.files[CONS_2025] = b'<html>please log in</html>'
        self.assertEqual(await self.run_job(True), 0)
        self.assertIn(SEP_2025, self.downloads)
        self.assertEqual(self.reports[-1]['symbols']['FPT']['skipped'],
                         [{'period_code': '2025-YEAR', 'external_id': '501', 'reason': 'DOWNLOAD_NOT_PDF'}])
        self.assertEqual({r['external_id'] for r in await self.c.fetch('SELECT external_id FROM documents')},
                         {'502', '401'})
        self.assertFalse((self.root / 'data/references/vietstock/financial_statements/files/FPT/2025-YEAR/501.pdf')
                         .exists())
        current = await self.current('2025-YEAR')
        self.assertEqual((current['status'], current['statement_scope']), ('VERIFIED', 'SEPARATE'))

    async def test_reconnects_when_connection_closed(self):
        loop, conns = asyncio.get_running_loop(), []

        async def connect():
            conns.append(await asyncpg.connect(host='127.0.0.1', port=15434, user='finmind_test', database=self.db))
            return conns[-1]

        def closing_fetch(symbols, output_root, profiles):
            if symbols == ['BID']:  # the connection drops while BID is being captured
                asyncio.run_coroutine_threadsafe(conns[-1].close(), loop).result()
            return self.fetch_vietcap(symbols, output_root, profiles)

        self.assertEqual(await job.run(True, now=NOW, symbols=('BID', 'FPT'), fetch_vietcap=closing_fetch,
                                       vietstock=FakeVietstock(self.catalog), download=self.download,
                                       connect=connect, on_report=self.reports.append), 1)
        report = self.reports[-1]['symbols']
        self.assertEqual((report['BID']['status'], report['FPT']['status']), ('failed', 'ok'))
        self.assertEqual(len(conns), 2)

    async def test_closes_own_vietstock_session(self):
        made = []

        class OwnClient(FakeVietstock):
            def __init__(self, delay):
                super().__init__({})
                self.session = mock.Mock()
                made.append(self)

        with mock.patch.object(job, 'VietstockAnnualClient', OwnClient):
            self.assertEqual(await job.run(False, now=NOW, symbols=('FPT',), fetch_vietcap=self.fetch_vietcap,
                                           download=self.download,
                                           connect=lambda: asyncpg.connect(host='127.0.0.1', port=15434,
                                                                           user='finmind_test', database=self.db)), 0)
        made[0].session.close.assert_called_once_with()

    # --- final review fix wave (13/11) ---
    async def test_raw_payload_stored_only_when_numbers_change(self):
        # Vietcap's serverDateTime changes every call; unchanged numbers must not grow raw_payloads (#3).
        self.stamp = 'call-1'
        await self.run_job(True)
        before = await self.counts()
        self.stamp = 'call-2'
        await self.run_job(True)
        self.assertEqual((await self.counts())['raw_payloads'], before['raw_payloads'])
        self.stamp = 'call-3'
        self.data['FPT']['2025-YEAR'] = fields('FPT', 2025, bump=7)  # a real restatement
        await self.run_job(True)
        after = await self.counts()
        self.assertGreater(after['raw_payloads'], before['raw_payloads'])
        latest = await self.c.fetchrow(
            "SELECT r.payload_id, p.payload::text AS body FROM financial_reports r JOIN raw_payloads p USING (payload_id) "
            "JOIN reporting_periods rp USING (period_id) WHERE rp.period_code='2025-YEAR' "
            "AND r.statement_scope='INCOME_STATEMENT' ORDER BY r.report_version DESC LIMIT 1")
        self.assertIn('call-3', latest['body'])

    async def test_unknown_metric_is_skipped_and_reported(self):
        # A new Vietcap field must not fail the whole symbol (#13).
        code = mapping.get_code('bsa78', capture.SECTIONS['BALANCE_SHEET'], 'TECH')
        await self.c.execute("DELETE FROM metrics WHERE code=$1 AND section='BALANCE_SHEET' AND industry_scope='TECH'",
                             code)
        self.assertEqual(await self.run_job(False), 0)
        item = self.reports[-1]['symbols']['FPT']
        self.assertEqual(item['status'], 'ok')
        self.assertIn([code, 'BALANCE_SHEET', 'TECH'], [list(k) for k in item['unknown_metrics']])
        self.assertEqual(await self.run_job(True), 0)
        self.assertEqual(self.reports[-1]['symbols']['FPT']['status'], 'ok')
        self.assertGreater(await self.c.fetchval(
            "SELECT count(*) FROM quarantine_records WHERE reason_code='UNKNOWN_METRIC'"), 0)

    async def test_dry_run_session_is_read_only(self):
        # Even a code path that tried to write would fail in a dry run (#14).
        seen = []
        original = job.refresh_symbol

        async def spy(conn, *args, **kwargs):
            seen.append(await conn.fetchval('SHOW default_transaction_read_only'))
            return await original(conn, *args, **kwargs)
        with mock.patch.object(job, 'refresh_symbol', spy):
            await self.run_job(False)
            await self.run_job(True)
        self.assertEqual(seen, ['on', 'off'])


class FixWaveUnitTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'a.pdf'
        self.path.write_bytes(text_pdf(['Doanh thu va tai san cua cong ty. ' * 8]))

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def test_page_text_is_cached_by_sha256(self):
        # OCR is expensive: the same file is read once, a changed file again (#4).
        calls = []

        def reader(data):
            calls.append(len(data))
            return ['page text']
        with mock.patch.object(job.statement_pdf, 'read_pages', reader):
            first = job._load(self.path)
            second = job._load(self.path)
            self.path.write_bytes(text_pdf(['Mot noi dung khac hoan toan. ' * 8]))
            job._load(self.path)
        self.assertEqual(len(calls), 2)
        self.assertEqual(first['pages'], second['pages'])

    async def test_unreadable_result_is_cached_too(self):
        calls = []

        def reader(data):
            calls.append(1)
            raise job.statement_pdf.NoTextLayer('scan')
        with mock.patch.object(job.statement_pdf, 'read_pages', reader):
            job._load(self.path)
            again = job._load(self.path)
        self.assertEqual(len(calls), 1)
        self.assertIsInstance(again['pages'], job.statement_pdf.NoTextLayer)

    async def test_ocr_environment_failure_is_not_cached(self):
        # A run on a machine without OCR tools must not leave the scan stuck as NO_TEXT_LAYER (re-review).
        calls = []

        def reader(data):
            calls.append(1)
            raise job.statement_pdf.OcrUnavailable('OCR tools are not installed')
        with mock.patch.object(job.statement_pdf, 'read_pages', reader):
            job._load(self.path)
            again = job._load(self.path)
        self.assertEqual(len(calls), 2)
        self.assertIsInstance(again['pages'], job.statement_pdf.NoTextLayer)

    async def test_cache_write_failure_does_not_fail_the_file(self):
        with mock.patch.object(job.statement_pdf, 'read_pages', lambda data: ['p']),                 mock.patch.object(Path, 'replace', side_effect=PermissionError('locked')):
            self.assertEqual(job._load(self.path)['pages'], ['p'])

    async def test_cached_error_type_is_whitelisted(self):
        cache = self.path.with_name(self.path.stem + '.pages.json')
        cache.write_text(json.dumps({'sha256': hashlib.sha256(self.path.read_bytes()).hexdigest(),
                                     'error': {'type': 'Path', 'message': '/etc'}}), encoding='utf-8')
        with mock.patch.object(job.statement_pdf, 'read_pages', lambda data: ['fresh']):
            self.assertEqual(job._load(self.path)['pages'], ['fresh'])

    async def test_oversized_zip_is_skipped_not_fatal(self):
        # extract_zip_pdfs raises ValueError above its size cap; that file is skipped (#12).
        self.path.write_bytes(zip_bytes([('report.pdf', b'%PDF-1.4 x')]))
        with mock.patch.object(job, 'extract_zip_pdfs', side_effect=ValueError('ZIP expands beyond limit')):
            self.assertIsNone(job._load(self.path))

    async def test_choose_keeps_the_conclusion_with_most_metrics_found(self):
        # No file verifies: keep the one with more evidence, not just the first (#10).
        entries = [dict(scope='CONSOLIDATED', period_code='2025-Q3', external_id='1', url='u1', audit_status='X',
                        title='t'), dict(scope='SEPARATE', period_code='2025-Q3', external_id='2', url='u2',
                                         audit_status='X', title='t')]
        pdfs = {e['external_id']: dict(entry=e, sha256=e['external_id'], pages=['x']) for e in entries}
        conclusions = {'1': dict(status='PARTIAL', evidence=[{'metric': 'A'}]),
                       '2': dict(status='PARTIAL', evidence=[{'metric': 'A'}, {'metric': 'B'}, {'metric': 'C'}])}

        async def fake_fetch(conn, entry, download):
            return pdfs[entry['external_id']]
        with mock.patch.object(job, 'fetch_pdf', fake_fetch), \
                mock.patch.object(job, 'decide', lambda inputs, ev: conclusions[ev['document']['url'][1]]):
            _, best = await job.choose(None, {}, entries, None, [])
        self.assertEqual(best[0]['entry']['external_id'], '2')


if __name__ == '__main__':
    unittest.main()
