import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from src.b1_answering.dialogue import DialogueSession


class DialogueBehavior(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_negation_and_ambiguous_choices(self):
        for reply in ('không phải sau, trước', 'khong phai sau, truoc'):
            s = DialogueSession()
            await s.ask('lợi nhuận FPT năm 2025')
            result = await s.ask(reply)
            self.assertEqual(result['scope']['metric_code'], 'PROFIT_BEFORE_TAX')
            self.assertEqual(result['scope']['companies'], ['FPT'])
        s = DialogueSession()
        await s.ask('lợi nhuận CMG năm 2025')
        result = await s.ask('sau hay trước')
        self.assertEqual(result['status'], 'ASK_CLARIFICATION')
        result = await s.ask('trc')
        self.assertEqual(result['scope']['metric_code'], 'PROFIT_BEFORE_TAX')
        self.assertEqual(result['scope']['companies'], ['CMG'])

    async def test_choose_unsupported_never_fabricates(self):
        s = DialogueSession()
        await s.ask('nợ FPT 2025 sau thuế')
        result = await s.ask('nợ')
        self.assertEqual(result['status'], 'UNSUPPORTED')
        self.assertEqual(result['scope']['periods'], ['2025-12-31'])
        self.assertIsNone(result['evidence_pack'])

    async def test_multi_company_and_period_resolution(self):
        for initial, selection in [('nợ hoặc lợi nhuận sau thuế FPT BID 2025', 'FPT'),
                                   ('nợ hoặc lợi nhuận sau thuế FPT 2024 2025', '2025')]:
            s = DialogueSession()
            await s.ask(initial)
            result = await s.ask('lợi nhuận sau thuế')
            self.assertEqual(result['reason_code'], 'AMBIGUOUS_SCOPE')
            result = await s.ask(selection)
            self.assertEqual(result['scope']['companies'], ['FPT'])
            self.assertEqual(result['scope']['periods'], ['2025-12-31'])
            self.assertEqual(result['scope']['metric_code'], 'PROFIT_AFTER_TAX')

    async def test_new_complete_question_replaces_pending_scope(self):
        s = DialogueSession()
        await s.ask('nợ FPT 2025 sau thuế')
        result = await s.ask('TTS BID ngày30/06/2026')
        self.assertEqual(result['status'], 'EVIDENCE_READY')
        self.assertEqual(result['scope']['companies'], ['BID'])
        self.assertEqual(result['scope']['periods'], ['2026-06-30'])

    async def test_case_insensitive_unambiguous_abbreviations(self):
        for alias, code in [('lnst', 'PROFIT_AFTER_TAX'), ('LNTT', 'PROFIT_BEFORE_TAX'), ('tts', 'TOTAL_ASSETS')]:
            with self.subTest(alias=alias):
                result = await DialogueSession().ask(f'{alias} FPT 2025')
                self.assertEqual(result['scope']['metric_code'], code)

    async def test_copy_and_session_id(self):
        s = DialogueSession('session-one')
        result = await s.ask('nợ FPT 2025')
        result['scope']['companies'].clear()
        self.assertEqual(s.last_result['scope']['companies'], ['FPT'])
        self.assertEqual(s.session_id, 'session-one')

    async def test_short_answer_for_different_field_does_not_guess_profit(self):
        s = DialogueSession()
        await s.ask('tổng tài sản BID')
        result = await s.ask('sau')
        self.assertEqual(result['status'], 'ASK_CLARIFICATION')
        self.assertNotEqual(result['reason_code'], 'UNKNOWN_TICKER')
        result = await s.ask('2025')
        self.assertEqual(result['scope']['metric_code'], 'TOTAL_ASSETS')

    async def test_quarter_scope_not_downgraded_to_year(self):
        s = DialogueSession()
        result = await s.ask('nợ FPT quý 2/2025')
        self.assertEqual(result['scope']['periods'], ['2025-06-30'])
        s.reset()
        await s.ask('lợi nhuận FPT quý 2/2025')
        result = await s.ask('sau')
        self.assertEqual(result['scope']['periods'], ['2025-06-30'])

    async def test_vague_and_empty_reply_keep_pending_scope(self):
        s = DialogueSession()
        await s.ask('nợ FPT 2025 sau thuế')
        for reply in ('gì cũng được', ''):
            result = await s.ask(reply)
            self.assertEqual(result['status'], 'ASK_CLARIFICATION')
            self.assertEqual(result['scope']['companies'], ['FPT'])
            self.assertIsNone(result['evidence_pack'])

    async def test_named_new_question_without_period_does_not_inherit_old_period(self):
        s = DialogueSession()
        await s.ask('LNST FPT 2025')
        result = await s.ask('tổng tài sản BID')
        self.assertEqual(result['status'], 'ASK_CLARIFICATION')
        self.assertFalse(result['scope']['periods'])


if __name__ == '__main__':
    unittest.main()
