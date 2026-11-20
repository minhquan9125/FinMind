from pathlib import Path
import hashlib
PINS = {'intent.py': '8d1f077bb22b5adcbdf09f2534a45fb979b760dc963cfd0b1de260dcde3d014e', 'contracts.py': '10b580d1dbc6657d38540fc1f9f1506e975757d468c7db81708a71a5451b6910', 'orchestrator.py': '3a727093b88b913d84ca44f9b05fba1bd39586c63d6cde4277601427f53b7a85', 'fixtures.json': 'f4cc6896fe141834a9e002beb306362af624ed6fe4df9b0b98ab8ee1a3a1096d'}
for name, digest in PINS.items():
    data = (Path(__file__).resolve().parents[1] / 'retrieval_flow' / name).read_bytes().replace(b'\r\n', b'\n')
    if hashlib.sha256(data).hexdigest() != digest:
        raise RuntimeError('Runtime dependency changed: ' + name)
import asyncio
from datetime import date
import io
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
from retrieval_flow.conversation import ChatSession, render_response
import hoi

class ConversationTests(unittest.IsolatedAsyncioTestCase):

    async def test_missing_company_then_metric_keeps_relative_year(self):
        session = ChatSession(today=date(2026, 10, 16))
        first = await session.ask('lợi nhuân năm nay là bao nhiêu')
        self.assertEqual(first['clarification'], 'Bạn muốn xem công ty nào?')
        second = await session.ask('BID')
        self.assertEqual(second['scope']['periods'], ['2026-12-31'])
        self.assertIn('trước thuế hay sau thuế', second['clarification'])
        final = await session.ask('sau thuế')
        self.assertEqual(final['status'], 'NO_DATA')
        self.assertEqual(final['scope']['companies'], ['BID'])
        self.assertEqual(final['scope']['metric_code'], 'PROFIT_AFTER_TAX')

    async def test_full_metric_reply_is_not_a_new_question(self):
        session = ChatSession()
        await session.ask('Lợi nhuận BID năm 2025?')
        result = await session.ask('lợi nhuận sau thuế')
        self.assertEqual(result['scope']['companies'], ['BID'])
        self.assertEqual(result['scope']['periods'], ['2025-12-31'])

    async def test_corrections_replace_company_period_and_metric(self):
        session = ChatSession()
        await session.ask('Lợi nhuận sau thuế BID năm 2025')
        await session.ask('đổi sang VCB')
        await session.ask('quý 2/2026')
        result = await session.ask('trước thuế')
        self.assertEqual(result['scope']['companies'], ['VCB'])
        self.assertEqual(result['scope']['periods'], ['2026-06-30'])
        self.assertEqual(result['scope']['measure_basis'], 'STANDALONE_QUARTER')
        self.assertEqual(result['scope']['metric_code'], 'PROFIT_BEFORE_TAX')

    async def test_fresh_question_does_not_inherit_missing_period(self):
        session = ChatSession()
        await session.ask('Tổng tài sản BID năm 2025')
        result = await session.ask('Tổng tài sản FPT là bao nhiêu?')
        self.assertEqual(result['reason_code'], 'MISSING_PERIOD')
        self.assertEqual(result['scope']['companies'], ['FPT'])
        self.assertEqual(result['scope']['periods'], [])

    async def test_unknown_casing_keeps_pending_slots_and_allows_correction(self):
        for ticker in ('SSI', 'SSi', 'ssi'):
            session = ChatSession()
            await session.ask('Lợi nhuận năm 2025')
            result = await session.ask(ticker)
            self.assertEqual(result['reason_code'], 'UNKNOWN_TICKER')
            self.assertIn('SSI', render_response(result))
            result = await session.ask('chủ đề trước')
            self.assertEqual(result['reason_code'], 'UNKNOWN_TICKER')
            await session.ask('BID')
            result = await session.ask('sau thuế')
            self.assertEqual(result['scope']['companies'], ['BID'])
            self.assertEqual(result['scope']['periods'], ['2025-12-31'])

    async def test_new_unknown_company_never_uses_previous_bid(self):
        session = ChatSession()
        await session.ask('Tổng tài sản BID năm 2025')
        result = await session.ask('cho t xem lợi nhuận ssi năm 2024')
        self.assertEqual(result['status'], 'OUT_OF_SCOPE')
        self.assertIsNone(result['evidence_pack'])
        await session.ask('VCB')
        result = await session.ask('sau thuế')
        self.assertEqual(result['scope']['companies'], ['VCB'])
        self.assertEqual(result['scope']['periods'], ['2024-12-31'])

    async def test_chatter_keeps_pending_context(self):
        session = ChatSession()
        await session.ask('Lợi nhuận BID năm 2025')
        await session.ask('hôm nay trời đẹp')
        result = await session.ask('sau thuế')
        self.assertEqual(result['scope']['companies'], ['BID'])
        self.assertEqual(result['scope']['periods'], ['2025-12-31'])

    async def test_reference_reset_and_isolation(self):
        session = ChatSession('A')
        await session.ask('Tổng tài sản BID tại 30/06/2026')
        self.assertEqual((await session.ask('chủ đề trước'))['status'], 'EVIDENCE_READY')
        self.assertEqual((await ChatSession('B').ask('chủ đề trước'))['status'], 'ASK_CLARIFICATION')
        session.reset()
        self.assertIsNone(session.last_result)
        self.assertIsNone(session.last_decision)
        self.assertEqual((await session.ask('chủ đề trước'))['status'], 'ASK_CLARIFICATION')

    async def test_new_full_year_is_not_conflicting_with_previous_year(self):
        session = ChatSession()
        await session.ask('Tổng tài sản BID năm 2025')
        result = await session.ask('năm 2024')
        self.assertEqual(result['scope']['periods'], ['2024-12-31'])

    async def test_actual_compare_annual_and_news_advice_gates(self):
        session = ChatSession()
        for question, expected in [('So sánh tổng tài sản BID và VCB tại 31/12/2025 hợp nhất', 'EVIDENCE_READY'), ('BCTN FPT 2025 nói gì về quản trị rủi ro?', 'EVIDENCE_READY'), ('Có nên mua VCB?', 'UNSUPPORTED'), ('Tin tức VCB', 'OUT_OF_SCOPE')]:
            result = await session.ask(question)
            self.assertEqual(result['status'], expected)

    async def test_blank_and_returned_copies_cannot_mutate_memory(self):
        session = ChatSession()
        result = await session.ask('Tổng tài sản BID năm 2025')
        before = session.last_decision
        await session.ask('')
        self.assertEqual(session.last_decision, before)
        result['scope']['companies'].clear()
        before['scope']['companies'].clear()
        self.assertEqual((await session.ask('chủ đề trước'))['scope']['companies'], ['BID'])

class TerminalTests(unittest.TestCase):

    def test_debug_and_reset_commands(self):
        output = io.StringIO()
        with patch('builtins.input', side_effect=['Tổng tài sản BID năm 2025', '/json', '/moi', '/json', 'exit']), redirect_stdout(output):
            asyncio.run(hoi.main())
        value = output.getvalue()
        self.assertIn('"request_id":', value)
        self.assertIn('Đã xóa ngữ cảnh', value)
        self.assertIn('Chưa có kết quả', value)

    def test_eof_is_graceful(self):
        with patch('builtins.input', side_effect=EOFError), redirect_stdout(io.StringIO()):
            asyncio.run(hoi.main())
import asyncio
import unittest
from datetime import date
from retrieval_flow.conversation import ChatSession, render_response

class IndependentBehaviorTests(unittest.IsolatedAsyncioTestCase):
    """Integration style tests exercising the public ChatSession API.

    The tests focus on the acceptance criteria described in the task:
    * multi‑turn slot retention (year, company, metric)
    * out‑of‑scope handling for unknown tickers (case‑insensitive)
    * explicit reset of context
    * human‑readable response (no raw JSON) and JSON debug path
    """

    async def async_ask(self, session: ChatSession, *questions: str):
        """Convenience helper that sends a series of questions to the same
        ChatSession and returns the envelope of the *last* ask.
        """
        result = None
        for q in questions:
            result = await session.ask(q)
        return result

    async def test_multi_turn_slot_retention(self):
        today = date(2025, 1, 1)
        session = ChatSession(today=today)
        result1 = await session.ask('lợi nhuận năm nay là bao nhiêu')
        result2 = await session.ask('BID')
        result3 = await session.ask('sau thuế')
        scope = result3.get('scope', {})
        self.assertIn('companies', scope)
        self.assertIn('BID', scope['companies'])
        self.assertIn('periods', scope)
        self.assertTrue(any(('2025' in p for p in scope['periods'])))
        self.assertIn('metric_code', scope)
        self.assertEqual(scope['metric_code'], 'PROFIT_AFTER_TAX')
        self.assertIn(result3.get('status'), ('NO_DATA', 'EVIDENCE_READY'))
        human = render_response(result3)
        self.assertNotIn('request_id', human)
        self.assertIn('BID', human)
        self.assertIn('2025', human)

    async def test_unknown_ticker_is_out_of_scope(self):
        session = ChatSession()
        result = await session.ask('cho t xem lợi nhuận ssi')
        self.assertEqual(result.get('status'), 'OUT_OF_SCOPE')
        self.assertEqual(result.get('reason_code'), 'UNKNOWN_TICKER')
        msg = result.get('clarification') or result.get('message') or ''
        self.assertIn('SSI', msg)
        self.assertIn('ngoài', msg.lower())
        self.assertNotIn('SSI', session.last_result.get('scope', {}).get('companies', []))
        self.assertNotIn('"request_id"', render_response(result))

    async def test_reset_clears_previous_context(self):
        session = ChatSession()
        await session.ask('lợi nhuận năm 2024 của BID')
        self.assertIsNotNone(session.last_decision)
        self.assertIn('BID', session.last_decision.get('scope', {}).get('companies', []))
        session.reset()
        result = await session.ask('tổng tài sản')
        scope = result.get('scope', {})
        self.assertEqual(scope.get('companies', []), [])
        self.assertIsNotNone(session.last_decision)
        self.assertNotIn('BID', str(session.last_decision))

    async def test_json_debug_path_exposes_raw_envelope(self):
        session = ChatSession()
        await session.ask('tổng tài sản BID tại 30/06/2026?')
        raw = session.last_result
        self.assertIsInstance(raw, dict)
        for key in ('request_id', 'status', 'scope'):
            self.assertIn(key, raw)
        human = render_response(raw)
        self.assertNotIn('request_id', human)
        self.assertNotIn('status', human)
if __name__ == '__main__':
    unittest.main()
