"""Coordinator regression: realistic Gemini metadata through the actual adapter."""
import json
from pathlib import Path
import sys
import unittest
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from src.b1_answering.gemini import GeminiProvider, GeminiError
from src.b1_answering.policy import Limits


class GeminiMetadataAcceptance(unittest.IsolatedAsyncioTestCase):
    async def generate(self, parts):
        data = {'candidates': [{'finishReason': 'STOP', 'content': {'parts': parts}}],
                'modelVersion': 'fixture-model',
                'usageMetadata': {'promptTokenCount': 10, 'candidatesTokenCount': 5, 'totalTokenCount': 15}}
        provider = GeminiProvider(Limits(), api_key='fake-regression-key', free_tier_confirmed=True,
                                  transport=httpx.MockTransport(lambda _: httpx.Response(200, json=data)))
        return await provider.generate({})

    async def test_signed_answer_and_thought_exclusion(self):
        answer = {'claims': [{'text': 'Nguồn mẫu', 'evidence_ids': ['e1']}]}
        for prefix in ([], [{'thought': True, 'text': 'private reasoning marker', 'thoughtSignature': 'signature'}]):
            with self.subTest(thought=bool(prefix)):
                result = await self.generate(prefix + [{'text': json.dumps(answer), 'thoughtSignature': 'signature'}])
                self.assertEqual(result['payload'], answer)
                self.assertEqual(result['usage']['total_tokens'], 15)
                self.assertEqual(result['model_version'], 'fixture-model')
                self.assertNotIn('private reasoning marker', str(result))

    async def test_only_thought_is_not_an_answer(self):
        with self.assertRaises(GeminiError) as error:
            await self.generate([{'text': '{"claims": []}', 'thought': True}])
        self.assertEqual(error.exception.code, 'GEMINI_EMPTY_RESPONSE')

    async def test_signature_is_not_answer_content(self):
        result = await self.generate([{'thoughtSignature': 'private-signature'}, {'text': '{"claims": []}'}])
        self.assertEqual(result['payload'], {'claims': []})
        self.assertNotIn('private-signature', str(result))

    async def test_invalid_thought_text_is_rejected_before_skipping(self):
        with self.assertRaises(GeminiError) as error:
            await self.generate([{'thought': True, 'text': 123}, {'text': '{"claims": []}'}])
        self.assertEqual(error.exception.code, 'INVALID_GEMINI_RESPONSE')

    async def test_malformed_finish_reason_does_not_escape_as_type_error(self):
        for finish in (None, [], {}, True):
            with self.subTest(finish=finish):
                data = {'candidates': [{'finishReason': finish, 'content': {'parts': [{'text': '{}'}]}}]}
                provider = GeminiProvider(Limits(), api_key='fake-key', free_tier_confirmed=True,
                                          transport=httpx.MockTransport(lambda _: httpx.Response(200, json=data)))
                with self.assertRaises(GeminiError) as error:
                    await provider.generate({})
                self.assertEqual(error.exception.code, 'INVALID_GEMINI_RESPONSE')

    async def test_pipeline_accepts_signed_json_and_retains_budget_on_parse_error(self):
        from src.b1_answering.hoi import DEMO_PACK, DEMO_PASSAGE
        from src.b1_answering.policy import Budget
        from src.b1_answering.service import complete_retrieval
        for malformed in (False, True):
            with self.subTest(malformed=malformed):
                calls = []
                def handler(request):
                    calls.append(request.url.path)
                    if request.url.path.endswith(':countTokens'):
                        return httpx.Response(200, json={'totalTokens': 100})
                    payload = 'not-json' if malformed else json.dumps({'claims': [{'text': DEMO_PASSAGE, 'evidence_ids': ['demo-e1']}]})
                    return httpx.Response(200, json={
                        'candidates': [{'finishReason': 'STOP', 'content': {'parts': [
                            {'thought': True, 'text': 'private-reasoning'},
                            {'text': payload, 'thoughtSignature': 'private-signature'}]}}],
                        'modelVersion': 'fixture-model',
                        'usageMetadata': {'promptTokenCount': 100, 'candidatesTokenCount': 20, 'totalTokenCount': 120}})
                provider = GeminiProvider(Limits(), api_key='fake-key', free_tier_confirmed=True,
                                          transport=httpx.MockTransport(handler))
                budget = Budget(Limits())
                out = await complete_retrieval('Ví dụ?', {'status': 'EVIDENCE_READY', 'execution_mode': 'FIXTURE', 'evidence_pack': DEMO_PACK}, provider=provider, budget=budget)
                self.assertEqual(len(calls), 2)
                self.assertEqual(out['answering']['reason_code'], 'INVALID_GEMINI_JSON' if malformed else 'SUCCESS')
                self.assertEqual(budget.snapshot()['unknown_usage'], int(malformed))
                self.assertNotIn('private-reasoning', str(out))
                self.assertNotIn('private-signature', str(out))


if __name__ == '__main__':
    unittest.main()
