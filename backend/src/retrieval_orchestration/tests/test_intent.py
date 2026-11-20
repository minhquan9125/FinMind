import unittest
import re
from retrieval_flow import intent

class TestIntentAnalyze(unittest.TestCase):
    def setUp(self):
        self.session = "sess-1"

    def _analyze(self, q, ctx=None):
        return intent.analyze(q, self.session, ctx)

    def test_valid_total_assets_point_in_time(self):
        # metric TOTAL_ASSETS with a specific day should succeed
        q = "Tổng tài sản của VCB vào 31/12/2022"
        res = self._analyze(q)
        self.assertEqual(res["decision"], "SEARCH")
        self.assertEqual(res["reason_code"], "SCOPE_COMPLETE")
        self.assertEqual(res["slots"]["metric"]["code"], "TOTAL_ASSETS")
        self.assertEqual(res["slots"]["companies"][0]["ticker"], "VCB")
        self.assertIsNotNone(res["slots"]["period"])
        self.assertEqual(res["slots"]["period"]["granularity"], "DAY")

    def test_unknown_ticker_out_of_scope(self):
        q = "Lợi nhuận của XYZ trong Q1/2023"
        res = self._analyze(q)
        self.assertEqual(res["decision"], "OUT_OF_SCOPE")
        self.assertEqual(res["reason_code"], "UNKNOWN_TICKER")

    def test_multi_company_without_compare_requires_clarification(self):
        q = "Tổng tài sản của VCB và BID trong 2022"
        res = self._analyze(q)
        self.assertEqual(res["decision"], "ASK_CLARIFICATION")
        self.assertEqual(res["reason_code"], "MULTI_INTENT_SPLIT_REQUIRED")
        self.assertTrue(res["clarification_question"])

    def test_news_source_conflict_asks_clarification(self):
        q = "Tin tức về lợi nhuận trước thuế của VCB theo tin"
        res = self._analyze(q)
        self.assertEqual(res["decision"], "ASK_CLARIFICATION")
        self.assertEqual(res["reason_code"], "SOURCE_CONFLICT")
        self.assertIn("Bạn có muốn dùng BCTC", res["clarification_question"])

    def test_missing_period_requests_clarification(self):
        q = "Lợi nhuận sau thuế của VCB"
        res = self._analyze(q)
        self.assertEqual(res["decision"], "ASK_CLARIFICATION")
        self.assertEqual(res["reason_code"], "MISSING_PERIOD")
        self.assertTrue(any("kỳ" in msg for msg in res["clarification_question"].split("?")))

    def test_invalid_date_returns_invalid_date_error(self):
        q = "Tổng tài sản của VCB vào 31/13/2022"  # month 13 invalid
        res = self._analyze(q)
        self.assertEqual(res["decision"], "ASK_CLARIFICATION")
        self.assertEqual(res["reason_code"], "INVALID_DATE")

    def test_advice_is_unsupported(self):
        q = "Bạn nên mua VCB?"
        res = self._analyze(q)
        self.assertEqual(res["decision"], "UNSUPPORTED")
        self.assertEqual(res["reason_code"], "UNSUPPORTED_ADVICE")

    def test_clarification_fills_missing_period(self):
        # First ask without period -> ASK_CLARIFICATION
        q1 = "Lợi nhuận sau thuế của VCB"
        first = self._analyze(q1)
        self.assertEqual(first["decision"], "ASK_CLARIFICATION")
        self.assertIn("period", first["missing_fields"])
        # Provide clarification with a quarter
        reply = "Quý 2/2023"
        second = intent.clarify(first, reply, self.session)
        self.assertEqual(second["decision"], "SEARCH")
        self.assertEqual(second["reason_code"], "SCOPE_COMPLETE")
        self.assertIsNotNone(second["slots"]["period"])
        self.assertEqual(second["slots"]["period"]["quarter"], 2)
        self.assertEqual(second["slots"]["period"]["year"], 2023)
        # Metric should stay the same
        self.assertEqual(second["slots"]["metric"]["code"], "PROFIT_AFTER_TAX")

    def test_clarify_unknown_ticker_adds_to_question_and_falls_back_to_ask(self):
        q = "Lợi nhuận của VCB"
        first = self._analyze(q)
        self.assertEqual(first["decision"], "ASK_CLARIFICATION")
        reply = "và XYZ"
        second = intent.clarify(first, reply, self.session)
        # XYZ is unknown, so result should be OUT_OF_SCOPE for unknown ticker
        self.assertEqual(second["decision"], "OUT_OF_SCOPE")
        self.assertEqual(second["reason_code"], "UNKNOWN_TICKER")

    def test_context_inheritance_company_and_period(self):
        # Simulate prior resolved query in context
        prior = {"session_id": self.session, "confirmed": True, "expired": False,
                 "last_resolved_query": intent.analyze("Tổng tài sản VCB năm 2022", self.session)}
        res = self._analyze("Tổng tài sản công ty này cùng kỳ", ctx=prior)
        self.assertEqual(res["decision"], "SEARCH")
        self.assertEqual(res["slots"]["companies"][0]["origin"], "SESSION_CONTEXT")
        self.assertEqual(res["slots"]["metric"]["code"], "TOTAL_ASSETS")
        self.assertEqual(res["slots"]["period"]["origin"], "SESSION_CONTEXT")



class AcceptanceTests(unittest.TestCase):
    def test_missing_slots_ambiguous_metric_and_followup(self):
        import copy
        a = intent.analyze("Tổng tài sản năm 2025?", "A")
        self.assertEqual((a["decision"], a["reason_code"]), ("ASK_CLARIFICATION", "MISSING_COMPANY"))
        a = intent.analyze("Lợi nhuận BID quý 2/2026?", "A")
        before = copy.deepcopy(a)
        self.assertEqual(a["reason_code"], "AMBIGUOUS_METRIC")
        b = intent.clarify(a, "sau thuế", "A")
        self.assertEqual((b["decision"], b["scope"]["companies"], b["scope"]["metric_code"]), ("SEARCH", ["BID"], "PROFIT_AFTER_TAX"))
        self.assertEqual(b["scope"]["periods"], ["2026-06-30"])
        self.assertEqual(b["slots"]["metric"]["origin"], "CLARIFICATION")
        self.assertEqual(a, before)
        self.assertNotEqual(intent.clarify(a, "sau thuế", "B")["decision"], "SEARCH")
        self.assertNotEqual(intent.clarify({**a, "expired": True}, "sau thuế", "A")["decision"], "SEARCH")

    def test_period_basis_table(self):
        cases = [("Tổng tài sản BID quý 2/2026", "POINT_IN_TIME", "2026-06-30"),
                 ("Tổng tài sản BID năm 2025", "POINT_IN_TIME", "2025-12-31"),
                 ("Lợi nhuận sau thuế BID năm 2025", "FULL_YEAR", "2025-12-31"),
                 ("Lợi nhuận sau thuế BID quý 2/2026", "STANDALONE_QUARTER", "2026-06-30"),
                 ("Lợi nhuận sau thuế BID 6 tháng đầu 2026", "YTD", "2026-06-30")]
        for text, basis, end in cases:
            result = intent.analyze(text, "A")
            self.assertEqual((result["decision"], result["scope"]["measure_basis"], result["scope"]["periods"]), ("SEARCH", basis, [end]))
        self.assertEqual(intent.analyze("Lợi nhuận sau thuế BID tại 30/06/2026", "A")["reason_code"], "AMBIGUOUS_BASIS")

    def test_compare_trend_annual_and_multiple_requests(self):
        cases = [("So sánh tổng tài sản BID và VCB tại 31/12/2025 hợp nhất", "COMPANY_COMPARE"),
                 ("Xu hướng lợi nhuận sau thuế FPT 2023–2025", "FINANCIAL_TREND"),
                 ("BCTN FPT 2025 nói gì về quản trị rủi ro", "ANNUAL_REPORT_TOPIC")]
        for question, kind in cases:
            result = intent.analyze(question, "A")
            self.assertEqual((result["decision"], result["intent"]), ("SEARCH", kind))
        for text in ("Tổng tài sản và doanh thu BID năm 2025", "Lợi nhuận sau thuế và doanh thu BID 2025"):
            self.assertEqual(intent.analyze(text, "A")["reason_code"], "MULTI_INTENT_SPLIT_REQUIRED")
        self.assertEqual(intent.analyze("So sánh tổng tài sản BID 2025 với VCB 2024", "A")["reason_code"], "CONFLICTING_PERIODS")

    def test_news_reference_dependency_and_unclear(self):
        self.assertEqual(intent.analyze("Tin VCB tháng 9/2026", "A")["reason_code"], "SOURCE_NOT_APPROVED")
        self.assertEqual(intent.analyze("Tổng tài sản BID 2025 theo tin tức", "A")["reason_code"], "SOURCE_CONFLICT")
        context = {"session_id": "A", "expired": False, "reference": {"answer_id": "fixture-answer", "evidence_id": "fixture-evidence"}}
        self.assertEqual(intent.analyze("Nguồn số vừa trả lời ở đâu?", "A", context)["decision"], "RESOLVE_REFERENCE")
        self.assertEqual(intent.analyze("Nguồn số vừa trả lời ở đâu?", "B", context)["reason_code"], "NO_REFERENCED_EVIDENCE")
        self.assertEqual(intent.analyze("Tổng tài sản BID 2025", "A", {"registry_unavailable": True})["decision"], "SYSTEM_UNAVAILABLE")
        for question in ("", "ABC", "Tổng tài sản BID mới nhất"):
            self.assertEqual(intent.analyze(question, "A")["decision"], "ASK_CLARIFICATION")

    def test_context_never_silently_fills_unreferenced_expired_or_other_session(self):
        prior = intent.analyze("Tổng tài sản BID 2025", "A")
        context = {"session_id": "A", "confirmed": True, "expired": False, "last_resolved_query": prior}
        self.assertNotEqual(intent.analyze("Tổng tài sản", "A", context)["decision"], "SEARCH")
        result = intent.analyze("còn VCB?", "A", context)
        self.assertEqual((result["decision"], result["scope"]["companies"], result["scope"]["periods"]), ("SEARCH", ["VCB"], ["2025-12-31"]))
        for context in ({**context, "expired": True}, {**context, "session_id": "B"}):
            self.assertNotEqual(intent.analyze("còn VCB?", "A", context)["decision"], "SEARCH")
