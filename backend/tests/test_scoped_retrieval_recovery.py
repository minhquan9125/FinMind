"""The recovery contract applies to every project company and source branch."""
import asyncio
import copy
import hashlib
from unittest.mock import AsyncMock
import pytest
from src.retrieval_orchestration.live_research import DenseEvidenceRetriever
from src.documents.chunk_reconstruction import ReconstructionError
from tests.test_live_research import CORPUS, INDEX

SYMBOLS=['VCB','BID','CTG','MBB','TCB','FPT','CMG','ELC','ITD','ICT']


def source_row(symbol,body='Tổng tài sản (TOTAL_ASSETS): 100 triệu VND',entity='Hợp nhất'):
    text=f'{symbol} | tại cuối quý 2/2026 | Phạm vi: {entity}\n'+body
    return dict(chunk_id='chunk',document_id='document',text=text,
        content_hash=hashlib.sha256(text.encode()).hexdigest(),source_sha256='a'*64,
        locator_json={},title=f'{symbol} source',score=1)


class Adapter(DenseEvidenceRetriever):
    async def _corpus(self):return {'index_version_id':INDEX}
    async def _hybrid_rows(self,*args):return []
    async def _annual_rows(self,rows,*args):return rows


@pytest.mark.parametrize('symbol',SYMBOLS)
@pytest.mark.parametrize('source,method',[
    ('BCTC','_scoped_lexical_rows'),('COMPANY_PROFILE','_scoped_lexical_rows'),
    ('BCTN','_annual_lexical_rows'),('NEWS','_news_lexical_rows'),
])
def test_primary_empty_tries_alternate_retrieval_with_same_company_and_period(symbol,source,method):
    adapter=Adapter(None,None,corpus_version_id=CORPUS,backend='hybrid')
    alternate=AsyncMock(return_value=[source_row(symbol)])
    setattr(adapter,method,alternate)
    period='2025' if source=='BCTN' else '2026-Q2' if source=='BCTC' else '2026-11-04' if source=='NEWS' else None
    scope=dict(companies=[symbol],source_type=source,periods=[period] if period else [],
        reporting_entity='CONSOLIDATED',metric_code='TOTAL_ASSETS' if source=='BCTC' else None)
    before=copy.deepcopy(scope)
    out=asyncio.run(adapter.retrieve('Tổng tài sản' if source=='BCTC' else 'Nội dung',scope))
    assert out['items']
    assert all(i['score']['type'] in ('RRF','COSINE_SIMILARITY') for i in out['items'])
    assert alternate.await_count==1
    assert alternate.call_args.args[2:4]==(symbol,period)
    assert scope==before
    assert out['retrieval_trace']


def test_financial_recovery_never_substitutes_a_different_metric():
    adapter=Adapter(None,None,corpus_version_id=CORPUS,backend='hybrid')
    adapter._scoped_lexical_rows=AsyncMock(return_value=[source_row('FPT','Doanh thu (NET_REVENUE): 100 triệu VND')])
    out=asyncio.run(adapter.retrieve('Tổng tài sản FPT',dict(companies=['FPT'],periods=['2026-Q2'],
        source_type='BCTC',metric_code='TOTAL_ASSETS',reporting_entity='CONSOLIDATED')))
    assert out['items']==[]


def test_financial_recovery_never_substitutes_parent_for_consolidated():
    adapter=Adapter(None,None,corpus_version_id=CORPUS,backend='hybrid')
    adapter._scoped_lexical_rows=AsyncMock(return_value=[source_row('FPT',entity='Riêng lẻ')])
    out=asyncio.run(adapter.retrieve('Tổng tài sản hợp nhất',dict(companies=['FPT'],periods=['2026-Q2'],
        source_type='BCTC',metric_code='TOTAL_ASSETS',reporting_entity='CONSOLIDATED')))
    assert out['items']==[]


def test_recovered_hash_error_is_not_converted_to_missing_data():
    adapter=Adapter(None,None,corpus_version_id=CORPUS,backend='hybrid')
    row=source_row('FPT');row['content_hash']='b'*64
    adapter._scoped_lexical_rows=AsyncMock(return_value=[row])
    with pytest.raises(ReconstructionError):
        asyncio.run(adapter.retrieve('Tổng tài sản',dict(companies=['FPT'],periods=['2026-Q2'],
            source_type='BCTC',metric_code='TOTAL_ASSETS',reporting_entity='CONSOLIDATED')))
