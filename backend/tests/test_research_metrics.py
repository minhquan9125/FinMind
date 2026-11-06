import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest

from src.b1_answering.core.policy import Limits
from src.b1_answering.providers.gemini import GeminiProvider, GeminiError
from src.core.usage_tracking import begin_generation, capture_usage, generation_calls
from src.documents.research_metrics import ResearchMetrics, ObservedResearch


def call(model='model-a', total=15):
    return {'model':model, 'usage':{'input_tokens':10,'output_tokens':3,'total_tokens':total}}


def test_usage_persists_across_restart_and_unknown_is_separate(tmp_path):
    store=ResearchMetrics(tmp_path)
    at='2026-11-05T17:30:00+00:00'  # November 6 in Vietnam
    store.record('one',at,1200,{'answering':{'status':'DRAFT_READY'}},[call(),{'model':'model-a','usage':None}])
    store.record('two',at,500,{'status':'NO_DATA'},[])
    store.record('old','2026-11-05T16:59:00+00:00',100,{},[call(total=100)],failed=True)
    store.record('one',at,1200,{},[call(total=100)])  # same request cannot be counted twice
    result=ResearchMetrics(tmp_path).summary(datetime(2026,11,5,18,tzinfo=timezone.utc))
    assert result['total']==2 and result['outcomes']=={'SUCCESS':1,'INSUFFICIENT_EVIDENCE':1}
    assert result['total_tokens']==15 and result['unknown_calls']==1
    assert result['models']==[{'model':'model-a','calls':2,'unknown_calls':1,'input_tokens':10,'output_tokens':3,'total_tokens':15}]
    assert ResearchMetrics(tmp_path).list()['total']==3


def test_observed_requests_isolate_concurrent_usage_and_ignore_cumulative_budget(tmp_path):
    class Engine:
        limits=SimpleNamespace(model='model-a')
        retrieval_timeout=10
        async def answer(self, total):
            entry=begin_generation('model-a')
            await asyncio.sleep(0)
            capture_usage(entry, {'promptTokenCount':2,'candidatesTokenCount':1,'totalTokenCount':total})
            return {'answering':{'status':'DRAFT_READY','budget':{'tokens_reserved':99999}}}
    async def run():
        observed=ObservedResearch(Engine(),ResearchMetrics(tmp_path))
        await asyncio.gather(observed.answer(10),observed.answer(20))
        assert generation_calls.get() is None
    asyncio.run(run())
    items=ResearchMetrics(tmp_path).list()['items']
    assert sorted(i['known_total'] for i in items)==[10,20]


def test_provider_captures_usage_even_when_model_answer_is_blocked():
    async def run():
        calls=[]; token=generation_calls.set(calls)
        try:
            provider=GeminiProvider(Limits(),api_key='fixture-key',free_tier_confirmed=True,
                transport=httpx.MockTransport(lambda req:httpx.Response(200,json={
                    'promptFeedback':{'blockReason':'SAFETY'},
                    'usageMetadata':{'promptTokenCount':10,'candidatesTokenCount':0,'totalTokenCount':12}})))
            with pytest.raises(GeminiError,match='GEMINI_BLOCKED'):
                await provider.generate({})
            assert calls[0]['usage']=={'input_tokens':10,'output_tokens':0,'total_tokens':12}
        finally: generation_calls.reset(token)
    asyncio.run(run())


def test_provider_outage_and_cancellation_keep_unknown_usage(tmp_path):
    class Engine:
        async def answer(self):
            begin_generation('model-a')
            raise asyncio.CancelledError()
    async def run():
        with pytest.raises(asyncio.CancelledError):
            await ObservedResearch(Engine(),ResearchMetrics(tmp_path)).answer()
        assert generation_calls.get() is None
    asyncio.run(run())
    row=ResearchMetrics(tmp_path).list()['items'][0]
    assert row['outcome']=='ERROR' and row['unknown_calls']==1 and row['known_total']==0


def test_malformed_usage_is_not_reported_as_actual_tokens():
    calls=[]; token=generation_calls.set(calls)
    try:
        entry=begin_generation('model-a')
        capture_usage(entry,{'promptTokenCount':True,'candidatesTokenCount':2,'totalTokenCount':3})
        assert entry['usage'] is None
        capture_usage(entry,{'promptTokenCount':10,'candidatesTokenCount':5,'totalTokenCount':3})
        assert entry['usage'] is None
    finally: generation_calls.reset(token)


def test_metrics_failure_does_not_discard_answer():
    class Engine:
        async def answer(self): return {'status':'NO_DATA'}
    class Broken:
        def record(self,*args,**kwargs): raise RuntimeError('private-connection-string')
    assert asyncio.run(ObservedResearch(Engine(),Broken()).answer())=={'status':'NO_DATA'}
