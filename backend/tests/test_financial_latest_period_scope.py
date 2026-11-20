import asyncio
from src.retrieval_orchestration.live_research import DenseEvidenceRetriever
from tests.test_live_research import pack, CORPUS, INDEX


def test_latest_period_is_resolved_before_scoped_search():
    sample=pack()['items'][0]
    class Adapter(DenseEvidenceRetriever):
        async def _corpus(self):return {'index_version_id':INDEX}
        async def _financial_latest_period(self,company,corpus):
            assert company=='FPT'
            return '2026-Q2'
        async def _hybrid_rows(self,q,scope,corpus,company,period,doc_type=None):
            assert period=='2026-Q2'
            assert doc_type=='FINANCIAL_STATEMENT'
            return [dict(chunk_id=sample['chunk_id'],document_id=sample['source_id'],text=sample['passage'],
                content_hash=sample['content_sha256'],source_sha256=sample['source_sha256'],
                locator_json=sample['locator'],title='FPT',score=1)]
    adapter=Adapter(None,None,corpus_version_id=CORPUS,backend='hybrid')
    result=asyncio.run(adapter.retrieve('FPT',dict(companies=['FPT'],source_type='BCTC',
        periods=['LATEST_AVAILABLE_PERIOD'],metric_code='CASH_AND_CASH_EQUIVALENTS')))
    assert len(result['items'])==1
