"""Coordinator acceptance matrix for context-dependent clarification."""
import asyncio
from datetime import date
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


class DialogueAcceptance(unittest.IsolatedAsyncioTestCase):
    def session(self):
        from src.b1_answering.dialogue import DialogueSession
        return DialogueSession(today=date(2026, 10, 20))

    async def test_short_answers_cross_company_and_year_matrix(self):
        for company in ('CMG', 'BID', 'FPT'):
            for year in ('2024', '2025'):
                for alias, code in [('sau', 'PROFIT_AFTER_TAX'), ('SAU NHÉ', 'PROFIT_AFTER_TAX'), ('chọn sau', 'PROFIT_AFTER_TAX'), ('truoc', 'PROFIT_BEFORE_TAX'), ('trc', 'PROFIT_BEFORE_TAX')]:
                    with self.subTest(company=company, year=year, alias=alias):
                        session = self.session()
                        await session.ask('lợi nhuận là bao nhiêu')
                        await session.ask(company)
                        result = await session.ask(alias)
                        self.assertEqual(result['scope']['companies'], [company])
                        self.assertEqual(result['scope']['metric_code'], code)
                        result = await session.ask(year)
                        self.assertEqual(result['scope']['companies'], [company])
                        self.assertEqual(result['scope']['metric_code'], code)
                        self.assertEqual(result['scope']['periods'], [year + '-12-31'])

    async def test_unknown_ticker_then_correction_keeps_question(self):
        session = self.session()
        await session.ask('lợi nhuận là bao nhiêu')
        result = await session.ask('ssi')
        self.assertEqual(result['reason_code'], 'UNKNOWN_TICKER')
        await session.ask('cmg')
        result = await session.ask('sau')
        self.assertEqual(result['scope']['metric_code'], 'PROFIT_AFTER_TAX')
        self.assertEqual(result['scope']['companies'], ['CMG'])

    async def test_multiple_indicator_families_ask_then_resolve(self):
        for text in ('nợ của fpt 2025 sau thuế', 'doanh thu và lợi nhuận sau thuế FPT năm2025', 'tổng tài sản và lợi nhuận sau thuế FPT năm2025'):
            with self.subTest(text=text):
                session = self.session()
                result = await session.ask(text)
                self.assertEqual(result['status'], 'ASK_CLARIFICATION')
                self.assertEqual(result['reason_code'], 'AMBIGUOUS_METRIC')
                self.assertIsNone(result['evidence_pack'])
                result = await session.ask('lợi nhuận sau thuế')
                self.assertEqual(result['scope']['companies'], ['FPT'])
                self.assertEqual(result['scope']['periods'], ['2025-12-31'])
                self.assertEqual(result['scope']['metric_code'], 'PROFIT_AFTER_TAX')

    async def test_unsupported_categories_are_explicit(self):
        for metric in ('nợ phải trả', 'doanh thu', 'vốn chủ sở hữu', 'ROE', 'EPS', 'P/E', 'P/B'):
            with self.subTest(metric=metric):
                result = await self.session().ask(f'{metric} của FPT năm 2025?')
                self.assertEqual(result['status'], 'UNSUPPORTED')
                self.assertEqual(result['reason_code'], 'UNSUPPORTED_METRIC')
                self.assertEqual(result['scope']['companies'], ['FPT'])
                self.assertEqual(result['scope']['periods'], ['2025-12-31'])
                self.assertIsNone(result['evidence_pack'])

    async def test_no_context_never_guesses_or_leaks_between_sessions(self):
        one, two = self.session(), self.session()
        await one.ask('lợi nhuận CMG năm2025')
        result = await two.ask('sau')
        self.assertEqual(result['status'], 'ASK_CLARIFICATION')
        self.assertNotEqual(result['reason_code'], 'UNKNOWN_TICKER')
        self.assertFalse(result['scope'].get('metric_code'))
        one.reset()
        result = await one.ask('sau')
        self.assertFalse(result['scope'].get('companies'))

    async def test_aliases_and_new_question_replace_old_scope(self):
        session = self.session()
        await session.ask('lợi nhuận CMG năm2025')
        result = await session.ask('TTS BID ngày30/06/2026?')
        self.assertEqual(result['scope']['companies'], ['BID'])
        self.assertEqual(result['scope']['metric_code'], 'TOTAL_ASSETS')
        self.assertEqual(result['status'], 'EVIDENCE_READY')
        self.assertEqual(result['evidence_pack']['items'][0]['evidence_id'], 'fixture-ev-bid-ta-2026q2')


if __name__ == '__main__':
    unittest.main()
