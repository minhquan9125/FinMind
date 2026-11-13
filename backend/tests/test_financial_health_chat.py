"""Financial health evidence for chat (MARKET_ANALYSIS): passage, feed contract, reader fallback."""
import asyncio
from datetime import datetime
import unittest

from backend.src.b1_answering.evidence.market_contract import CitationError, feed_item
from backend.src.financial.health_passage import compact_health, financial_health_passage

CITE = dict(title='BCTC Hợp nhất Kiểm toán năm 2025', url='https://static2.vietstock.vn/data/HOSE/2025/BCTC/x.pdf',
            page=12)


def analysis(**signals):
    base = {name: dict(value=None, status='insufficient_data', reasons=['unverified_money_unit'])
            for name in ('revenue_yoy_percent', 'profit_yoy_percent', 'net_margin_percent',
                         'liabilities_to_assets_percent', 'roe_percent')}
    base['nim_percent'] = dict(value=None, status='not_applicable', reasons=['industry_profile'])
    base.update(signals)
    return dict(symbol='FPT', industry='TECH', period='2025-YEAR', status='provisional', signals=base, evidence=[])


PEERS = dict(metrics={'revenue_yoy_percent': dict(peer_median='8.1', position='above', favorable=True,
                                                  status='complete', peer_symbols=['CMG', 'ELC', 'ITD'])})


class PassageTests(unittest.TestCase):
    def test_compact_keeps_values_and_drops_not_applicable(self):
        health = compact_health(analysis(revenue_yoy_percent=dict(value='12.3456', status='complete', reasons=[])),
                                PEERS, [CITE])
        self.assertEqual(health['period'], '2025-YEAR')
        self.assertNotIn('nim_percent', health['signals'])
        self.assertEqual(health['signals']['revenue_yoy_percent']['value'], '12.35')
        self.assertEqual(health['signals']['revenue_yoy_percent']['peer'], dict(median='8.10', position='above'))
        self.assertEqual(health['citations'], [CITE])

    def test_passage_states_values_unverified_metrics_and_sources(self):
        health = compact_health(analysis(revenue_yoy_percent=dict(value='12.3456', status='complete', reasons=[])),
                                PEERS, [CITE])
        text = financial_health_passage('FPT', health)
        self.assertIn('năm 2025', text)
        self.assertIn('Tăng trưởng doanh thu so với cùng kỳ: 12,35%', text)
        self.assertIn('cao hơn trung vị nhóm cùng ngành (8,10%)', text)
        self.assertIn('so với cùng kỳ năm trước', text.splitlines()[1])  # plain-language meaning
        # missing signals share one line right after the values, so one short quote covers both
        self.assertIn('12,35%', text.splitlines()[1])
        self.assertTrue(text.splitlines()[2].startswith('- Chưa đủ dữ liệu đã xác minh: '))
        self.assertIn('biên lợi nhuận ròng', text.splitlines()[2])
        self.assertIn('BCTC Hợp nhất Kiểm toán năm 2025 (trang 12)', text)
        self.assertIn('không phải khuyến nghị', text)

    def test_nothing_verified_says_so(self):
        text = financial_health_passage('FPT', compact_health(analysis(), {}, []))
        self.assertIn('Chưa có chỉ số tài chính nào đủ dữ liệu đã xác minh', text)


class FeedContractTests(unittest.TestCase):
    def snapshot(self, **health):
        base = compact_health(analysis(revenue_yoy_percent=dict(value='5', status='complete', reasons=[])), {}, [CITE])
        base.update(health)
        return dict(kind='FINANCIAL_HEALTH', provider='finmind_db', symbol='FPT',
                    observed_at='2026-11-13T11:00:00+07:00', health=base)

    def test_valid_snapshot_has_link_and_passage(self):
        item = feed_item(self.snapshot())
        self.assertEqual(item['source_type'], 'FINANCIAL_HEALTH')
        self.assertEqual((item['title'], item['locator']['url'], item['locator']['page']),
                         (CITE['title'], CITE['url'], 12))
        self.assertIn('Tăng trưởng doanh thu so với cùng kỳ: 5,00%', item['passage'])

    def test_without_citation_there_is_no_link(self):
        item = feed_item(self.snapshot(citations=[]))
        self.assertNotIn('url', item['locator'])
        self.assertEqual(item['title'], 'Tình hình tài chính FPT · dữ liệu FinMind')

    def test_rejects_foreign_link_and_bad_period(self):
        for bad in (dict(citations=[dict(CITE, url='https://evil.example/x.pdf')]), dict(period='2025'),
                    dict(signals={}), dict(citations=[dict(CITE, page='12')])):
            with self.subTest(bad=bad), self.assertRaises(CitationError):
                feed_item(self.snapshot(**bad))


class ReaderFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_health_reader_keeps_the_analysis(self):
        from backend.src.retrieval_orchestration.market_research import MarketResearch

        async def broken(symbol):
            raise RuntimeError('db down')
        research = MarketResearch(None, services=lambda: (None, None), health_reader=broken)
        seen = {}

        def fake_lookup(scope, previous_pack, trend=None, health=None):
            seen.update(trend=trend, health=health)
            return dict(status='EVIDENCE_READY')
        research._lookup = fake_lookup
        result = await research.lookup(dict(source_type='MARKET_ANALYSIS', companies=['FPT']))
        self.assertEqual(result['status'], 'EVIDENCE_READY')
        self.assertIsNone(seen['health'])


    def test_analysis_pack_contains_financial_health(self):
        from backend.src.retrieval_orchestration.market_research import MarketResearch
        research = MarketResearch(None, services=lambda: (None, None))
        research._quote = lambda *a: dict(status='NO_DATA')
        research._news = lambda *a: dict(status='NO_DATA')
        health = compact_health(analysis(revenue_yoy_percent=dict(value='5', status='complete', reasons=[])), {},
                                [CITE])
        result = research._analysis('FPT', dict(source_type='MARKET_ANALYSIS', companies=['FPT']), None, None,
                                    None, health)
        kinds = [item['source_type'] for item in result['evidence_pack']['items']]
        self.assertEqual(kinds, ['FINANCIAL_HEALTH'])
        self.assertEqual(result['evidence_pack']['items'][0]['locator']['url'], CITE['url'])


if __name__ == '__main__':
    unittest.main()
