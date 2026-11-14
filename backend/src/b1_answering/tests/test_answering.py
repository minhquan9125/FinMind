import asyncio
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from src.b1_answering.gemini import GeminiError, GeminiProvider
from src.b1_answering.policy import Budget, Limits, PolicyError
from src.b1_answering.service import complete_retrieval
from src.b1_answering.hoi import DEMO_PACK, DEMO_PASSAGE, FixtureProvider


def envelope():
    return {'status': 'EVIDENCE_READY', 'execution_mode': 'FIXTURE', 'evidence_pack': copy.deepcopy(DEMO_PACK)}


def response(text=DEMO_PASSAGE, *, finish='STOP', usage=True):
    data = {'candidates': [{'finishReason': finish, 'content': {'parts': [{'text': json.dumps(
        {'claims': [{'text': text, 'evidence_ids': ['demo-e1']}]}, ensure_ascii=False)}]}}],
            'modelVersion': 'gemini-3.5-flash-lite-test'}
    if usage:
        data['usageMetadata'] = {'promptTokenCount': 100, 'candidatesTokenCount': 50, 'totalTokenCount': 150}
    return data



async def _no_sleep(_seconds):
    return None

class TestGeminiProvider(unittest.IsolatedAsyncioTestCase):
    def provider(self, handler):
        return GeminiProvider(Limits(), api_key='dummy-test-key', free_tier_confirmed=True, transport=httpx.MockTransport(handler))

    async def test_configuration_blocks_calls_and_repr_redacts(self):
        with patch.dict(os.environ, {}, clear=True):
            for kwargs, code in [({}, 'MISSING_API_KEY'), ({'api_key': 'dummy'}, 'FREE_TIER_NOT_CONFIRMED')]:
                with self.subTest(code=code), self.assertRaises(GeminiError) as error:
                    GeminiProvider(Limits(), **kwargs)
                self.assertEqual(error.exception.code, code)
        self.assertNotIn('dummy-test-key', repr(self.provider(lambda _: httpx.Response(200))))

    async def test_actual_pipeline_request_headers_count_schema_and_locator(self):
        calls = []
        def handler(req):
            calls.append(req)
            self.assertEqual(req.headers['x-goog-api-key'], 'dummy-test-key')
            self.assertNotIn('dummy-test-key', str(req.url))
            self.assertEqual(req.url.host, 'generativelanguage.googleapis.com')
            self.assertEqual(req.extensions['timeout']['read'], 600)
            body = json.loads(req.content)
            if req.url.path.endswith(':countTokens'):
                actual = body['generateContentRequest']
                self.assertEqual(actual['model'], 'models/gemini-3.5-flash-lite')
                self.assertIn('systemInstruction', actual)
                self.assertIn('responseJsonSchema', actual['generationConfig'])
                return httpx.Response(200, json={'totalTokens': 100})
            self.assertNotIn('tools', body)
            self.assertEqual(body['generationConfig']['maxOutputTokens'], Limits.load().max_output_tokens)
            return httpx.Response(200, json=response())
        out = await complete_retrieval('Chỉ tiêu minh họa?', envelope(), provider=self.provider(handler))
        self.assertEqual(out['answering']['status'], 'DRAFT_READY')
        self.assertEqual(len(calls), 2)
        self.assertEqual(out['answering']['citations'][0]['locator'], DEMO_PACK['items'][0]['locator'])
        self.assertFalse(out['answering']['manifest']['components']['b3_answer_verification'])

    async def test_bad_status_and_single_retry_only_for_overload(self):
        # Overload (502/503/504) gets exactly one retry; quota (429), 500 and other statuses never retry.
        for status, code, tries in [(429, 'RATE_LIMITED', 1), (302, 'GEMINI_UNAVAILABLE', 1),
                                    (400, 'GEMINI_UNAVAILABLE', 1), (500, 'GEMINI_UNAVAILABLE', 1),
                                    (503, 'GEMINI_UNAVAILABLE', 2)]:
            calls = []
            def handler(req):
                calls.append(req)
                return httpx.Response(status, text='untrusted upstream error')
            with self.subTest(status=status), patch('asyncio.sleep', new=_no_sleep), \
                    self.assertRaises(GeminiError) as error:
                await self.provider(handler).generate({})
            self.assertEqual(error.exception.code, code)
            self.assertEqual(len(calls), tries)

    async def test_overload_then_success_returns_the_second_answer(self):
        calls = []
        def handler(req):
            calls.append(req)
            return httpx.Response(503, text='busy') if len(calls) == 1 else httpx.Response(200, json=response())
        with patch('asyncio.sleep', new=_no_sleep):
            out = await self.provider(handler).generate({})
        self.assertEqual(len(calls), 2)
        self.assertIn('payload', out)

    async def test_timeout_safe_error_and_body_limit(self):
        def timeout(req):
            raise httpx.ReadTimeout('dummy-test-key must never be echoed', request=req)
        with self.assertRaises(GeminiError) as error:
            await self.provider(timeout).count_tokens({})
        self.assertEqual(str(error.exception), 'GEMINI_TIMEOUT')
        self.assertTrue(error.exception.__suppress_context__)
        with self.assertRaises(GeminiError) as error:
            await self.provider(lambda _: httpx.Response(200, content=b'x' * (1024 * 1024 + 1))).generate({})
        self.assertEqual(error.exception.code, 'INVALID_GEMINI_RESPONSE')

    async def test_output_and_malformed_json_rejected(self):
        cases = [(json.dumps(response(finish='MAX_TOKENS')), 'OUTPUT_LIMIT_EXCEEDED'),
                 ('{}', 'INVALID_GEMINI_RESPONSE'), ('{"candidates":[],"candidates":[]}', 'INVALID_GEMINI_RESPONSE'),
                 ('NaN', 'INVALID_GEMINI_RESPONSE')]
        for body, code in cases:
            with self.subTest(body=body), self.assertRaises(GeminiError) as error:
                await self.provider(lambda _: httpx.Response(200, text=body)).generate({})
            self.assertEqual(error.exception.code, code)

    async def test_unknown_usage_is_not_zero(self):
        provider = self.provider(lambda req: httpx.Response(200, json={'totalTokens': 100} if req.url.path.endswith(':countTokens') else response(usage=False)))
        budget = Budget(Limits())
        out = await complete_retrieval('hỏi', envelope(), provider=provider, budget=budget)
        self.assertNotEqual(out['answering']['status'], 'DRAFT_READY')
        self.assertEqual(budget.snapshot()['tokens_reserved'], 100 + Limits().max_output_tokens)
        self.assertEqual(budget.snapshot()['unknown_usage'], 1)


class TestCompleteRetrieval(unittest.IsolatedAsyncioTestCase):
    async def test_nonready_conflicting_and_empty_never_call(self):
        class Never:
            async def count_tokens(self, _):
                raise AssertionError('must not call')
        bad = envelope()
        bad['evidence_pack']['conflicts'] = True
        empty = envelope()
        empty['evidence_pack']['items'] = []
        for incoming in [{'status': 'ASK_CLARIFICATION'}, {'status': 'NO_DATA'}, bad, empty]:
            result = await complete_retrieval('hỏi', incoming, provider=Never())
            self.assertIn(result['answering']['status'], ('SKIPPED', 'INSUFFICIENT_EVIDENCE'))

    async def test_exhaustion_blocks_count_and_generation_and_limits_mismatch(self):
        limits = Limits(max_generation_calls=1)
        budget = Budget(limits)
        provider = FixtureProvider(limits)
        first = await complete_retrieval('hỏi', envelope(), provider=provider, limits=limits, budget=budget)
        self.assertEqual(first['answering']['status'], 'DRAFT_READY')
        with patch.object(provider, 'count_tokens', side_effect=AssertionError('no calls outside budget')):
            second = await complete_retrieval('hỏi', envelope(), provider=provider, limits=limits, budget=budget)
        self.assertEqual(second['answering']['status'], 'BUDGET_EXCEEDED')
        with self.assertRaises(PolicyError):
            await complete_retrieval('hỏi', envelope(), provider=provider, limits=Limits(), budget=budget)

    async def test_input_limit_before_generation(self):
        provider = FixtureProvider(Limits())
        with patch.object(provider, 'count_tokens', return_value=16385), patch.object(provider, 'generate', side_effect=AssertionError('not allowed')):
            out = await complete_retrieval('hỏi', envelope(), provider=provider)
        self.assertEqual(out['answering']['reason_code'], 'INPUT_LIMIT_EXCEEDED')

    async def test_shared_deadline_and_timeout_reservation(self):
        limits = Limits(read_timeout_seconds=1)
        class Slow:
            async def count_tokens(self, _):
                await asyncio.sleep(.55)
                return 100
            async def generate(self, _):
                await asyncio.sleep(.55)
                raise AssertionError('should time out first')
        budget = Budget(limits)
        out = await complete_retrieval('hỏi', envelope(), provider=Slow(), limits=limits, budget=budget)
        self.assertEqual(out['answering']['reason_code'], 'GEMINI_TIMEOUT')
        self.assertEqual(budget.snapshot()['unknown_usage'], 1)


class TestCli(unittest.TestCase):
    def test_script_example_offline(self):
        script = Path(__file__).resolve().parents[1] / 'hoi.py'
        result = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(script), '--example'], capture_output=True, text=True, encoding='utf-8', timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('123', result.stdout)
        self.assertIn('demo-e1', result.stdout)
        self.assertIn('OFFLINE', result.stdout)


if __name__ == '__main__':
    unittest.main()
