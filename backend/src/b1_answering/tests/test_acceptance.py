"""Coordinator integration checks, independent of worker-authored tests."""
import asyncio
import copy
import sys
import unittest
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def fixture_result():
    return {
        'status': 'EVIDENCE_READY', 'execution_mode': 'FIXTURE',
        'evidence_pack': {
            'schema_version': '1.0', 'query_id': 'synthetic-query',
            'data_version': {'kind': 'INDEX', 'id': 'synthetic-index-v1'},
            'items': [{'evidence_id': 'e1', 'chunk_id': 'fixture-c1',
                       'source_id': 'fixture-document', 'source_sha256': 'a' * 64,
                       'passage': '[DỮ LIỆU MẪU] Chỉ tiêu minh họa có giá trị 123 đơn vị mẫu.',
                       'locator': {'page_number': 7, 'table_id': 'fixture-table'}}],
        },
    }


class Provider:
    def __init__(self, *, claim=None, usage=True):
        self.calls = []
        self.claim = claim
        self.usage = usage

    async def count_tokens(self, request):
        self.calls.append('count')
        return 100

    async def generate(self, request):
        self.calls.append('generate')
        return {'payload': {'claims': [{
            'text': self.claim or fixture_result()['evidence_pack']['items'][0]['passage'],
            'evidence_ids': ['e1'],
        }]}, 'usage': {'input_tokens': 100, 'output_tokens': 20, 'total_tokens': 120} if self.usage else None,
            'model_version': 'fixture-only'}


class EndToEnd(unittest.IsolatedAsyncioTestCase):
    async def test_existing_retrieval_is_wired_to_answering(self):
        from src.b1_answering.service import answer_question
        from src.b1_answering.hoi import FixtureProvider
        from src.b1_answering.policy import Limits
        result = await answer_question('Tổng tài sản BID tại 30/06/2026?', 'coordinator-session', provider=FixtureProvider(Limits()))
        self.assertEqual(result['scope']['companies'], ['BID'])
        self.assertEqual(result['answering']['status'], 'DRAFT_READY')
        self.assertEqual(result['answering']['citations'][0]['evidence_id'], 'fixture-ev-bid-ta-2026q2')

    async def test_cli_uses_existing_multiturn_session(self):
        from src.b1_answering.hoi import run_cli
        args = SimpleNamespace(live=False, example=False, json=False, question=None)
        output = StringIO()
        with redirect_stdout(output), patch('builtins.input', side_effect=[
            'lợi nhuận năm 2025', 'BID', 'sau thuế', '/moi', 'Tổng tài sản BID tại 30/06/2026?', 'exit'
        ]):
            await run_cli(args)
        self.assertIn('Công ty: BID', output.getvalue())
        self.assertIn('fixture-ev-bid-ta-2026q2', output.getvalue())
        self.assertIn('ngân sách của tiến trình vẫn được giữ', output.getvalue())

    async def test_cli_json_is_parseable(self):
        import json
        from src.b1_answering.hoi import run_cli
        output, error = StringIO(), StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            await run_cli(SimpleNamespace(live=False, example=True, json=True, question=None))
        result = json.loads(output.getvalue())
        self.assertEqual(result['answering']['status'], 'DRAFT_READY')
        self.assertIn('OFFLINE', error.getvalue())

    async def test_cli_single_reset_command_exits(self):
        from src.b1_answering.hoi import run_cli
        with redirect_stdout(StringIO()):
            await asyncio.wait_for(run_cli(SimpleNamespace(live=False, example=False, json=False, question='/moi')), 1)

    async def test_cli_live_missing_key_fails_safely(self):
        import os
        from src.b1_answering.hoi import run_cli
        from src.b1_answering.gemini import GeminiError
        with patch.dict(os.environ, {}, clear=True), patch('sys.stdin.isatty', return_value=False):
            with self.assertRaises(GeminiError) as error:
                await run_cli(SimpleNamespace(live=True, example=True, json=False, question=None))
        self.assertEqual(error.exception.code, 'MISSING_API_KEY')

    async def test_draft_has_exact_source_locator_and_disabled_b3(self):
        from src.b1_answering.service import complete_retrieval
        original = fixture_result()
        before = copy.deepcopy(original)
        provider = Provider()
        result = await complete_retrieval('Chỉ tiêu minh họa?', original, provider=provider)
        answer = result['answering']
        self.assertEqual(answer['status'], 'DRAFT_READY')
        self.assertEqual(provider.calls, ['count', 'generate'])
        self.assertIn('123', answer['draft'])
        self.assertEqual(answer['citations'][0]['locator'], before['evidence_pack']['items'][0]['locator'])
        self.assertEqual(original, before)
        components = answer['manifest']['components']
        self.assertFalse(components['b3_evidence_gate'])
        self.assertFalse(components['b3_answer_verification'])
        self.assertFalse(components['tools'])

    async def test_nonsearch_states_never_contact_provider(self):
        from src.b1_answering.service import complete_retrieval
        for status in ('ASK_CLARIFICATION', 'NO_DATA', 'OUT_OF_SCOPE', 'SYSTEM_UNAVAILABLE'):
            provider = Provider()
            result = await complete_retrieval('hỏi', {'status': status}, provider=provider)
            self.assertEqual(result['answering']['status'], 'SKIPPED')
            self.assertEqual(provider.calls, [])

    async def test_unsupported_number_is_not_rendered(self):
        from src.b1_answering.service import complete_retrieval
        result = await complete_retrieval('hỏi', fixture_result(), provider=Provider(claim='Giá trị là 999 tỷ đồng.'))
        self.assertNotEqual(result['answering']['status'], 'DRAFT_READY')
        self.assertIsNone(result['answering']['draft'])

    async def test_budget_does_not_reset_between_requests(self):
        from src.b1_answering.policy import Budget, Limits
        from src.b1_answering.service import complete_retrieval
        limits = Limits(max_generation_calls=1)
        budget = Budget(limits)
        provider = Provider()
        first = await complete_retrieval('hỏi', fixture_result(), provider=provider, limits=limits, budget=budget)
        second = await complete_retrieval('hỏi', fixture_result(), provider=provider, limits=limits, budget=budget)
        self.assertEqual(first['answering']['status'], 'DRAFT_READY')
        self.assertEqual(second['answering']['status'], 'BUDGET_EXCEEDED')
        self.assertEqual(provider.calls.count('generate'), 1)

    async def test_unknown_usage_keeps_worst_case_reservation(self):
        from src.b1_answering.policy import Budget, Limits
        from src.b1_answering.service import complete_retrieval
        limits = Limits()
        budget = Budget(limits)
        result = await complete_retrieval('hỏi', fixture_result(), provider=Provider(usage=False), limits=limits, budget=budget)
        self.assertNotEqual(result['answering']['status'], 'DRAFT_READY')
        self.assertEqual(budget.snapshot()['tokens_reserved'], 100 + limits.max_output_tokens)
        self.assertEqual(budget.snapshot()['unknown_usage'], 1)

    async def test_cancel_propagates_and_reservation_survives(self):
        from src.b1_answering.policy import Budget, Limits
        from src.b1_answering.service import complete_retrieval
        started = asyncio.Event()

        class Waiting(Provider):
            async def generate(self, request):
                started.set()
                await asyncio.Event().wait()

        limits = Limits()
        budget = Budget(limits)
        task = asyncio.create_task(complete_retrieval('hỏi', fixture_result(), provider=Waiting(), limits=limits, budget=budget))
        await asyncio.wait_for(started.wait(), 2)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(budget.snapshot()['unknown_usage'], 1)
        self.assertGreater(budget.snapshot()['tokens_reserved'], 0)


if __name__ == '__main__':
    unittest.main()
