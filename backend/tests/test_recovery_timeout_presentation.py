import asyncio
from src.retrieval_orchestration.live_research import LiveResearchService
from tests.test_live_research import Retriever,pack


def test_recovery_timeout_is_not_reported_as_missing_financial_data():
    evidence=pack();evidence['items']=[]
    evidence['retrieval_trace']=[{'status':'TIMEOUT','source':'BCTC'}]
    engine=LiveResearchService(Retriever(evidence))
    out=asyncio.run(engine.answer('Tổng tài sản FPT quý 2/2026','test'))
    assert out['status']=='SYSTEM_UNAVAILABLE'
    assert out['reason_code']=='RECOVERY_TIMEOUT'
