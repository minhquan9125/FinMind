"""db-financial-v5: verified scope/unit header and BCTC PDF link in the chunk locator."""
import unittest
from datetime import date
from decimal import Decimal
from uuid import uuid4

from backend.src.documents import db_source
from backend.src.documents.db_chunking import chunk_documents, financial_documents
from backend.src.financial import verification_store as store
from backend.tests.financial_db_fixture import create_financial_db, drop_financial_db

V5 = 'db-financial-v5'
VID = '11111111-1111-1111-1111-111111111111'
EVIDENCE = [{'metric': 'TOTAL_ASSETS', 'page': 9}, {'metric': 'PROFIT_AFTER_TAX', 'page': 4}]


def rows(unit='VND', **extra):
    base = dict(report_id='r1', symbol='FPT', company_name='FPT', period_code='2025-Q1',
                statement_scope='CONSOLIDATED', section='INCOME_STATEMENT', code='PROFIT_AFTER_TAX',
                canonical_name='LNST', observation_id='o1', value=1_000_000, unit=unit)
    return [{**base, **extra}]


VERIFIED = dict(verification_id=VID, v_status='VERIFIED', v_scope='CONSOLIDATED', v_unit='VND',
                v_unit_status='VERIFIED', v_evidence=EVIDENCE, doc_title='BCTC Q1', doc_url='http://x/a.pdf')


class PureTests(unittest.TestCase):
    def header(self, version, rs):
        return financial_documents(rs, renderer_version=version)[0].sections[0].header

    def test_v5_header_verified(self):
        self.assertEqual(self.header(V5, rows(**VERIFIED)),
                         'FPT (FPT) | Báo cáo Kết quả hoạt động kinh doanh | quý 1/2025 (riêng quý) | '
                         'Phạm vi: Hợp nhất (đã xác minh) | Đơn vị: VND (đã xác minh) | Nguồn: BCTC Q1')
        self.assertIn('Phạm vi: Riêng (đã xác minh)', self.header(V5, rows(**{**VERIFIED, 'v_scope': 'SEPARATE'})))

    def test_v5_unverified_matches_v3_wording(self):
        for extra in ({}, {**VERIFIED, 'v_status': 'PARTIAL'}):
            v5 = financial_documents(rows('SOURCE_NATIVE', **extra), renderer_version=V5)[0].sections[0]
            v3 = financial_documents(rows('SOURCE_NATIVE'), renderer_version='db-financial-v3')[0].sections[0]
            self.assertEqual((v5.header, [r.text for r in v5.rows]), (v3.header, [r.text for r in v3.rows]))
            self.assertIn('đơn vị nguồn chưa xác minh', v5.header)
            self.assertIn('(đơn vị chưa xác minh)', v5.rows[0].text)

    def test_v5_verified_report_keeps_per_row_suffix_for_non_vnd_rows(self):
        # final review #15: report-level VND verification says nothing about EPS or native-unit rows.
        section = financial_documents(
            rows('VND', **VERIFIED) + [dict(rows('VND_PER_SHARE', **VERIFIED)[0], code='EPS', canonical_name='EPS',
                                            observation_id='o2'),
                                       dict(rows('SOURCE_NATIVE', **VERIFIED)[0], code='X', canonical_name='X',
                                            observation_id='o3')],
            renderer_version=V5)[0].sections[0]
        text = {r.key: r.text for r in section.rows}
        self.assertNotIn('chưa xác minh', text['o1'])
        self.assertIn('(đơn vị chưa xác minh)', text['o2'])
        self.assertIn('(đơn vị chưa xác minh)', text['o3'])

    def test_v5_locator_has_link(self):
        loc = chunk_documents(financial_documents(rows(**VERIFIED), renderer_version=V5))[0].locator
        self.assertEqual((loc['url'], loc['source_title'], loc['verification_id'], loc['source_page']),
                         ('http://x/a.pdf', 'BCTC Q1', VID, 4))  # PROFIT_AFTER_TAX beats TOTAL_ASSETS
        none = chunk_documents(financial_documents(rows(), renderer_version=V5))[0].locator
        self.assertEqual((none['verification_id'], none['url'], none['source_page']), (None, None, None))

    def test_v3_output_unchanged(self):
        # chunk ids recorded from the pre-v5 code (git HEAD) for the same two rows
        base = [dict(rows()[0], code=c, canonical_name=c, value=1_000_000 * i, observation_id=f'o{i}', unit=u)
                for i, (c, u) in enumerate((('A', 'VND'), ('B', 'SOURCE_NATIVE')), 1)]
        want = {'db-financial-v2': '5a6cbf79-2cc9-53fd-aab6-8de2243a04d7',
                'db-financial-v3': '25a9dec5-71d4-5d28-a087-cdecfe461f5c',
                'db-financial-v4': 'fcd3ae87-1ddc-5a76-a3e0-a87f190111c0'}
        for version, chunk_id in want.items():
            got = [c.chunk_id for c in chunk_documents(financial_documents(base, renderer_version=version))]
            self.assertEqual(got, [chunk_id], version)


class PinTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.admin, self.c, self.db = await create_financial_db()

    async def asyncTearDown(self):
        await drop_financial_db(self.admin, self.c, self.db)

    async def test_locator_document_pins_verification(self):
        c, company, metric, period = self.c, uuid4(), uuid4(), uuid4()
        await c.execute("INSERT INTO companies(company_id,symbol,industry_type) VALUES($1,'FPT','TECH')", company)
        await c.execute("INSERT INTO metrics(metric_id,code,section) VALUES($1,'PROFIT_AFTER_TAX','INCOME_STATEMENT')", metric)
        await c.execute("INSERT INTO reporting_periods(period_id,period_code,fiscal_year,quarter,period_type,"
                        "start_date,end_date) VALUES($1,'2025-Q1',2025,1,'QUARTER','2025-01-01','2025-03-31')", period)
        job = await store.start_job(c, await store.ensure_source(c, 'SRC', source_type='X', base_url='b'))
        payload = await store.store_payload(c, job, source_uri='u', payload_text='{}')
        rid, oid = uuid4(), uuid4()
        await c.execute("INSERT INTO financial_reports(report_id,company_id,period_id,payload_id,job_id,"
                        "statement_scope,audit_status,report_version) VALUES($1,$2,$3,$4,$5,'CONSOLIDATED','UNKNOWN',1)",
                        rid, company, period, payload, job)
        await c.execute("INSERT INTO observations(observation_id,report_id,metric_id,value,unit,scale,currency,"
                        "locator_json) VALUES($1,$2,$3,$4,'VND',1,'VND','{}'::jsonb)", oid, rid, metric, Decimal(5_000_000))
        docs = [await store.ensure_document(c, {'title': t, 'url': f'http://x/{t}.pdf'}, company_id=company,
                                            period_id=period, job_id=job, sha256=t * 64, page_count=9, file_size=1)
                for t in 'ab']

        def conclusion(doc, status, page):
            return dict(document_id=doc, statement_scope='CONSOLIDATED', audit_status='UNKNOWN', unit='VND',
                        unit_status='VERIFIED', period_basis='STANDALONE_QUARTER', period_start=date(2025, 1, 1),
                        period_end=date(2025, 3, 31), fiscal_year_end='12-31', fiscal_label_convention='CALENDAR',
                        comparison_basis='AS_REPORTED', checks={}, status=status, reason_codes=[],
                        evidence=[{'metric': 'PROFIT_AFTER_TAX', 'page': page}])

        first = await store.append_verification(c, rid, job, conclusion(docs[0], 'VERIFIED', 3))
        [old] = chunk_documents(await db_source.fetch_financial_documents(c, ['FPT'], renderer_version=V5))
        self.assertEqual((old.locator['verification_id'], old.locator['source_title'], old.locator['source_page']),
                         (str(first), 'a', 3))
        second = await store.append_verification(c, rid, job, conclusion(docs[1], 'PARTIAL', 7))

        async def rebuild(vid):
            doc = await db_source.fetch_locator_document(c, 'financial_reports', str(rid), 130,
                                                         financial_renderer_version=V5, verification_id=str(vid))
            return chunk_documents([doc])[0].content_hash

        self.assertEqual(await rebuild(first), old.content_hash)
        self.assertNotEqual(await rebuild(second), old.content_hash)
        from backend.src.documents.chunk_reconstruction import reconstruct_chunk
        got = await reconstruct_chunk(c, old.locator, old.content_hash)  # pinned: survives the newer verification
        self.assertEqual(got.content_hash, old.content_hash)
        [now] = chunk_documents(await db_source.fetch_financial_documents(c, ['FPT'], renderer_version=V5))
        self.assertEqual(now.locator['verification_id'], str(second))  # current = latest


if __name__ == '__main__':
    unittest.main()
