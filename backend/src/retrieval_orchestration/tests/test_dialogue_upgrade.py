from datetime import date
import unittest
from retrieval_flow.conversation import ChatSession


class DialogueUpgradeTests(unittest.IsolatedAsyncioTestCase):
    async def test_combined_company_and_tax_reply(self):
        s=ChatSession(today=date(2026,10,19))
        await s.ask('Lợi nhuận năm 2025?')
        r=await s.ask('BID, sau thuế')
        self.assertEqual((r['scope']['companies'],r['scope']['periods'],r['scope']['metric_code']),
                         (['BID'],['2025-12-31'],'PROFIT_AFTER_TAX'))

    async def test_multiple_updates_leave_unspecified_metric(self):
        s=ChatSession()
        await s.ask('Lợi nhuận sau thuế BID năm 2025')
        r=await s.ask('VCB năm 2024')
        self.assertEqual(r['scope']['companies'],['VCB'])
        self.assertEqual(r['scope']['periods'],['2024-12-31'])
        self.assertEqual(r['scope']['metric_code'],'PROFIT_AFTER_TAX')
        r=await s.ask('trước thuế quý 2/2026')
        self.assertEqual((r['scope']['periods'],r['scope']['metric_code'],r['scope']['measure_basis']),
                         (['2026-06-30'],'PROFIT_BEFORE_TAX','STANDALONE_QUARTER'))

    async def test_natural_correction_company_period_and_reference(self):
        s=ChatSession()
        await s.ask('Lợi nhuận trước thuế BID năm 2025')
        for text,company in [('không, là VCB','VCB'),('còn FPT thì sao','FPT'),('khong, la BID','BID')]:
            r=await s.ask(text)
            self.assertEqual(r['scope']['companies'],[company])
            self.assertEqual(r['scope']['periods'],['2025-12-31'])
        r=await s.ask('ý tôi là năm 2024')
        self.assertEqual(r['scope']['periods'],['2024-12-31'])

    async def test_previous_year_and_quarter_rollover(self):
        for clock,phrase,expected in [(date(2026,10,19),'năm ngoái','2025-12-31'),
                                     (date(2026,1,15),'quý trước','2025-12-31'),
                                     (date(2026,10,19),'quý trước','2026-09-30'),
                                     (date(2026,10,19),'quý này','2026-12-31')]:
            s=ChatSession(today=clock)
            r=await s.ask('Lợi nhuận sau thuế BID '+phrase)
            self.assertEqual(r['scope']['periods'],[expected])

    async def test_choices_preserve_active_scope(self):
        s=ChatSession()
        await s.ask('Lợi nhuận sau thuế BID năm 2025')
        before=s.context_summary()
        for text in ['BID hoặc VCB','trước thuế hay sau thuế','năm 2024 hoặc năm 2025','hợp nhất hay riêng']:
            r=await s.ask(text)
            self.assertEqual(r['status'],'ASK_CLARIFICATION')
            self.assertIsNone(r['evidence_pack'])
            self.assertEqual(s.context_summary(),before)
        r=await s.ask('VCB')
        self.assertEqual((r['scope']['companies'],r['scope']['periods']),(['VCB'],['2025-12-31']))

    async def test_initial_choice_then_explicit_selection(self):
        s=ChatSession()
        r=await s.ask('BID hoặc VCB lợi nhuận sau thuế năm 2025')
        self.assertEqual(r['status'],'ASK_CLARIFICATION')
        self.assertIn('BID',r['message'])
        self.assertIn('VCB',r['message'])
        r=await s.ask('BID')
        self.assertEqual((r['scope']['companies'],r['scope']['periods']),(['BID'],['2025-12-31']))

    async def test_fresh_query_does_not_inherit_period_or_company(self):
        s=ChatSession()
        await s.ask('Tổng tài sản BID năm 2025')
        r=await s.ask('Tổng tài sản FPT?')
        self.assertEqual(r['scope']['periods'],[])
        self.assertEqual(r['reason_code'],'MISSING_PERIOD')
        r=await s.ask('Lợi nhuận sau thuế năm 2024?')
        self.assertEqual(r['scope']['companies'],[])

    async def test_metric_change_recomputes_basis(self):
        s=ChatSession()
        await s.ask('Lợi nhuận sau thuế BID năm 2025')
        r=await s.ask('đổi chỉ tiêu sang tổng tài sản')
        self.assertEqual(r['scope']['metric_code'],'TOTAL_ASSETS')
        self.assertEqual(r['scope']['measure_basis'],'POINT_IN_TIME')

    async def test_unknown_natural_correction_does_not_keep_bid(self):
        s=ChatSession()
        await s.ask('Lợi nhuận sau thuế BID năm 2025')
        for text in ['không, là ssi','còn ssi thì sao','ssi, sau thuế']:
            r=await s.ask(text)
            self.assertEqual(r['reason_code'],'UNKNOWN_TICKER')
            self.assertIsNone(r['evidence_pack'])
        r=await s.ask('VCB')
        self.assertEqual(r['scope']['companies'],['VCB'])

    async def test_context_summary_pure_chatter_and_reset(self):
        s=ChatSession()
        await s.ask('Lợi nhuận BID năm 2025')
        before=s.last_decision
        summary=s.context_summary()
        self.assertIn('BID',summary)
        self.assertIn('2025',summary)
        self.assertIn('Chờ',summary)
        self.assertEqual(s.last_decision,before)
        await s.ask('cảm ơn')
        self.assertEqual(s.context_summary(),summary)
        s.reset()
        self.assertIn('Không có',s.context_summary())

    async def test_multi_slot_does_not_bypass_news_advice_or_isolation(self):
        s=ChatSession()
        await s.ask('Lợi nhuận BID năm 2025')
        self.assertEqual((await s.ask('Có nên mua VCB?'))['status'],'UNSUPPORTED')
        self.assertEqual((await s.ask('Tin tức VCB'))['status'],'OUT_OF_SCOPE')
        other=ChatSession()
        self.assertEqual((await other.ask('sau thuế'))['status'],'ASK_CLARIFICATION')

    async def test_quarter_and_ytd_entity_are_not_lost(self):
        s=ChatSession()
        await s.ask('Lợi nhuận sau thuế BID lũy kế quý 2/2026 hợp nhất')
        r=await s.ask('VCB')
        self.assertEqual(r['scope']['measure_basis'],'YTD')
        self.assertEqual(r['scope']['reporting_entity'],'CONSOLIDATED')
