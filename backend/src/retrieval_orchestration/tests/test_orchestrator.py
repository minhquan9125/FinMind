from pathlib import Path
import hashlib
RUNTIME_PINS = {'retrieval_flow/contracts.py': '10b580d1dbc6657d38540fc1f9f1506e975757d468c7db81708a71a5451b6910', 'retrieval_flow/fixtures.json': 'f4cc6896fe141834a9e002beb306362af624ed6fe4df9b0b98ab8ee1a3a1096d', 'retrieval_flow/intent.py': '8d1f077bb22b5adcbdf09f2534a45fb979b760dc963cfd0b1de260dcde3d014e'}
for name, expected in RUNTIME_PINS.items():
    data = (Path(__file__).resolve().parents[1] / name).read_bytes().replace(b'\r\n', b'\n')
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise RuntimeError("Approved runtime dependency changed: " + name)

import unittest
import asyncio
from retrieval_flow.orchestrator import orchestrate, FixtureRetriever, FixtureReferenceResolver

class TestOrchestrator(unittest.TestCase):
    def setUp(self):
        self.valid_question = "Tổng tài sản BID tại 30/06/2026?"
        self.invalid_question = ""
        self.timeout_question = "Timeout question"
        self.session_id = "test-session"

    async def orchestrate_helper(self, question, session_id, **kwargs):
        return await orchestrate(question, session_id, **kwargs)

    def test_orchestrate_search_success(self):
        async def test():
            result = await self.orchestrate_helper(self.valid_question, self.session_id)
            self.assertEqual(result['status'], "EVIDENCE_READY")
            self.assertIn("evidence_pack", result)
        asyncio.run(test())

    def test_orchestrate_no_data(self):
        async def test():
            result = await self.orchestrate_helper("Tổng tài sản BID năm 2024?", self.session_id)
            self.assertEqual(result['status'], "NO_DATA")
        asyncio.run(test())

    def test_orchestrate_invalid_decision(self):
        async def test():
            result = await self.orchestrate_helper(self.invalid_question, self.session_id)
            self.assertEqual(result['status'], "ASK_CLARIFICATION")
        asyncio.run(test())

    def test_orchestrate_timeout(self):
        class SlowRetriever:
            async def retrieve(self, scope, query_id, index_version):
                await asyncio.sleep(1)

        async def test():
            result = await self.orchestrate_helper(
                self.valid_question,
                self.session_id,
                retriever=SlowRetriever(),
                timeout_seconds=0.01
            )
            self.assertEqual(result['status'], "SYSTEM_UNAVAILABLE")
            self.assertEqual(result['reason_code'], "RETRIEVAL_TIMEOUT")

        asyncio.run(test())

    def test_orchestrate_invalid_reference(self):
        async def test():
            resolver = FixtureReferenceResolver()
            result = await self.orchestrate_helper(
                "Nguồn số vừa trả lời ở đâu?",
                self.session_id,
                reference_resolver=resolver
            )
            self.assertEqual(result['status'], "OUT_OF_SCOPE")
            self.assertEqual(result['reason_code'], "NO_REFERENCED_EVIDENCE")

        asyncio.run(test())



class JourneyTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_retrieval_before_b1_search(self):
        adapter = FixtureRetriever()
        for question, status in [("Tổng tài sản năm 2025?", "ASK_CLARIFICATION"),
                                 ("Lợi nhuận BID quý 2/2026?", "ASK_CLARIFICATION"),
                                 ("Tin VCB tháng 9/2026", "OUT_OF_SCOPE"),
                                 ("Có nên mua VCB?", "UNSUPPORTED")]:
            result = await orchestrate(question, "A", retriever=adapter)
            self.assertEqual(result['status'], status)
            self.assertIsNone(result['evidence_pack'])
        self.assertEqual(adapter.calls, [])

    async def test_actual_metric_compare_and_annual_journeys(self):
        for question in ("Tổng tài sản BID tại 30/06/2026?",
                         "So sánh tổng tài sản BID và VCB tại 31/12/2025 hợp nhất",
                         "BCTN FPT 2025 nói gì về quản trị rủi ro?"):
            adapter = FixtureRetriever()
            result = await orchestrate(question, "A", retriever=adapter)
            self.assertEqual(result['status'], 'EVIDENCE_READY')
            self.assertEqual(len(adapter.calls), 1)
            self.assertEqual(result['query_id'], result['evidence_pack']['query_id'])
            self.assertEqual(result['execution_mode'], 'FIXTURE')
            self.assertNotIn('answer', result)
        result = await orchestrate("Tổng tài sản VCB tại 30/06/2026?", 'A')
        self.assertEqual(result['status'], 'NO_DATA')

    async def test_invalid_pack_query_version_and_wrong_scope(self):
        from retrieval_flow.contracts import load_fixtures
        class Altered:
            def __init__(self, mode): self.mode = mode
            async def retrieve(self, scope, query_id, index_version):
                pack = await FixtureRetriever().retrieve(scope, query_id, index_version)
                if self.mode == 'raw': return 'not a pack'
                if self.mode == 'query': pack['query_id'] = 'wrong'
                if self.mode == 'index': pack['data_version']['id'] = 'fixture-wrong'
                if self.mode == 'locator': del pack['items'][0]['locator']
                if self.mode == 'scope':
                    pack['items'] = load_fixtures()['packs']['valid_compare']['items']
                return pack
        for mode in ('raw','query','index','locator','scope'):
            result = await orchestrate('Tổng tài sản BID tại 30/06/2026?', 'A', retriever=Altered(mode))
            self.assertEqual(result['status'], 'INSUFFICIENT_EVIDENCE' if mode == 'scope' else 'INVALID_EVIDENCE_PACK')
            self.assertIsNone(result['evidence_pack'])
            self.assertTrue(result['errors'])

    async def test_pinned_version_missing_never_searches(self):
        from retrieval_flow.intent import analyze
        def missing(question, session, context):
            result = analyze(question, session, context)
            result['corpus_version_id'] = 'missing'
            return result
        adapter = FixtureRetriever()
        result = await orchestrate('Tổng tài sản BID tại 30/06/2026?', 'A', analyzer=missing, retriever=adapter)
        self.assertEqual((result['status'],result['reason_code']), ('SYSTEM_UNAVAILABLE','VERSION_UNAVAILABLE'))
        self.assertEqual(adapter.calls, [])

    async def test_errors_are_sanitized(self):
        class Broken:
            async def retrieve(self, *args): raise RuntimeError('secret-upstream-trace')
        result = await orchestrate('Tổng tài sản BID tại 30/06/2026?', 'A', retriever=Broken())
        self.assertEqual(result['status'], 'SYSTEM_UNAVAILABLE')
        self.assertNotIn('secret-upstream-trace', str(result))
        self.assertIsNone(result['evidence_pack'])

    async def test_reference_resolution_and_session_isolation(self):
        ref = {'answer_id':'fixture-answer','evidence_id':'fixture-evidence'}
        record = {**ref,'source_id':'doc:fixture-source','locator':{'page_number':1}}
        resolver = FixtureReferenceResolver({('A',ref['answer_id'],ref['evidence_id']):record})
        context = {'session_id':'A','expired':False,'reference':ref}
        adapter = FixtureRetriever()
        result = await orchestrate('Nguồn số vừa trả lời ở đâu?', 'A', context=context,
                                   retriever=adapter, reference_resolver=resolver)
        self.assertEqual(result['status'], 'REFERENCE_READY')
        self.assertEqual(result['scope']['reference'], record)
        self.assertEqual((len(adapter.calls),len(resolver.calls)), (0,1))
        result = await orchestrate('Nguồn số vừa trả lời ở đâu?', 'B', context=context,
                                   retriever=adapter, reference_resolver=resolver)
        self.assertEqual(result['reason_code'], 'NO_REFERENCED_EVIDENCE')
        self.assertEqual(len(resolver.calls), 1)

    async def test_reference_timeout_and_bad_identity(self):
        class Slow:
            async def resolve(self, *args): await asyncio.sleep(1)
        context = {'session_id':'A','expired':False,'reference':{'answer_id':'a','evidence_id':'e'}}
        result = await orchestrate('Nguồn số vừa trả lời ở đâu?', 'A', context=context,
                                   reference_resolver=Slow(), timeout_seconds=.001)
        self.assertEqual(result['reason_code'],'REFERENCE_TIMEOUT')
        bad = FixtureReferenceResolver({('A','a','e'):{'answer_id':'other','evidence_id':'e'}})
        result = await orchestrate('Nguồn số vừa trả lời ở đâu?', 'A', context=context, reference_resolver=bad)
        self.assertEqual(result['reason_code'],'NO_REFERENCED_EVIDENCE')

    async def test_caller_cancellation_and_late_response(self):
        started, stopped = asyncio.Event(), asyncio.Event()
        class Pending:
            async def retrieve(self, *args):
                started.set()
                try: await asyncio.sleep(10)
                finally: stopped.set()
        task = asyncio.create_task(orchestrate('Tổng tài sản BID tại 30/06/2026?', 'A', retriever=Pending()))
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError): await task
        self.assertTrue(stopped.is_set())
        class Late:
            async def retrieve(self, scope, query, index):
                try: await asyncio.sleep(1)
                except asyncio.CancelledError: return await FixtureRetriever().retrieve(scope,query,index)
        result = await orchestrate('Tổng tài sản BID tại 30/06/2026?', 'A', retriever=Late(), timeout_seconds=.001)
        self.assertEqual(result['reason_code'],'RETRIEVAL_TIMEOUT')
        self.assertIsNone(result['evidence_pack'])

    async def test_envelope_and_invalid_timeout(self):
        keys = {'request_id','query_id','execution_mode','b1_decision','status','reason_code','message',
                'scope','clarification','evidence_pack','errors'}
        for timeout in (True,0,float('nan'),float('inf')):
            result = await orchestrate('Tổng tài sản BID tại 30/06/2026?', 'A', timeout_seconds=timeout)
            self.assertEqual(set(result),keys)
            self.assertEqual(result['reason_code'],'INVALID_TIMEOUT')

class DeadlineBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_exact_deadline_still_accepts_a_complete_valid_pack(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from retrieval_flow import orchestrator as module
        ticks = iter([10.0,11.0])
        with patch.object(module, "time", SimpleNamespace(monotonic=lambda:next(ticks))):
            result = await module.orchestrate("Tổng tài sản BID tại 30/06/2026?", "boundary", timeout_seconds=1.0)
        self.assertEqual(result["status"], "EVIDENCE_READY")
