import asyncio
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
import pytest
from src.retrieval_orchestration.live_research import (
    LiveResearchService,DenseEvidenceRetriever,analyze_live,content_fallback_scope)

TODAY = date(2026, 11, 27)
UNSCOPED_SOURCE = '{} triển khai chính sách chuyển đổi số nào trong năm 2026?'

@pytest.mark.parametrize('company', ['BIDV','BID','VCB','CTG','MBB','TCB','FPT','CMG','ELC','ITD','ICT'])
def test_complete_non_metric_question_searches_content_for_every_company(company):
    text=UNSCOPED_SOURCE.format(company)
    decision=analyze_live(text, today=TODAY)
    scope=content_fallback_scope(text,decision)
    assert scope is not None
    assert scope['companies']==['BID' if company=='BIDV' else company]
    assert scope['source_type']=='CONTENT' and scope['metric_code'] is None
    assert scope['periods'] == ['2026']


@pytest.mark.parametrize('text', ['FPT','FPT năm 2025','Lợi nhuận FPT năm 2025',
    'Doanh thu FPT quý 2','Ai là chủ tịch FPT?', 'Theo BCTN FPT 2025 có kế hoạch gì?'])
def test_slots_metrics_and_explicit_sources_keep_their_existing_paths(text):
    assert content_fallback_scope(text,analyze_live(text)) is None


def test_no_content_is_truthfully_no_data_without_metric_options_or_graph():
    retriever=SimpleNamespace(retrieve=AsyncMock(return_value={'items':[]}))
    router=SimpleNamespace(answer=AsyncMock(side_effect=AssertionError('Do not require Neo4j')))
    service=LiveResearchService(retriever,hybrid_router=router)
    result=asyncio.run(service.answer(UNSCOPED_SOURCE.format('BIDV'), 'test', today=TODAY))
    assert result['status']=='NO_DATA' and result['reason_code']=='NO_CONTENT_EVIDENCE'
    assert result['clarification_options']==[]
    passed_scope = retriever.retrieve.call_args.args[1]
    assert passed_scope['companies'] == ['BID']
    assert passed_scope['periods'] == ['2026']


def test_multiple_companies_asks_for_subject_instead_of_four_financial_metrics():
    retriever=SimpleNamespace(retrieve=AsyncMock(side_effect=AssertionError('Ambiguous subject')))
    service=LiveResearchService(retriever)
    text=UNSCOPED_SOURCE.format('BID và MBB')
    result=asyncio.run(service.answer(text, 'test', today=TODAY))
    assert result['reason_code']=='AMBIGUOUS_CONTENT_COMPANY'
    assert 'BID' in result['message'] and 'MBB' in result['message']
    assert result['clarification_options']==[]


def test_verified_content_still_passes_through_existing_grounding_not_direct_render():
    retriever=SimpleNamespace(retrieve=AsyncMock(return_value={'items':[{'fake':'candidate'}],'query_id':'id'}))
    service=LiveResearchService(retriever)
    complete=AsyncMock(return_value={'status':'INSUFFICIENT_EVIDENCE'})
    with patch('src.retrieval_orchestration.live_research.prepare_evidence') as verify, patch(
            'src.retrieval_orchestration.live_research.complete_retrieval',complete):
        result=asyncio.run(service.answer(UNSCOPED_SOURCE.format('BIDV'), 'test', today=TODAY))
    verify.assert_called_once()
    complete.assert_awaited_once()
    assert result['status']=='INSUFFICIENT_EVIDENCE'


def test_invalid_source_is_not_sent_to_generation():
    retriever=SimpleNamespace(retrieve=AsyncMock(return_value={'items':[{'fake':'candidate'}]}))
    service=LiveResearchService(retriever)
    complete=AsyncMock()
    with patch('src.retrieval_orchestration.live_research.complete_retrieval',complete):
        result=asyncio.run(service.answer(UNSCOPED_SOURCE.format('BIDV'), 'test', today=TODAY))
    complete.assert_not_called()
    assert result['status']=='INSUFFICIENT_EVIDENCE'


@pytest.mark.parametrize('changed', [False,True])
def test_content_search_combines_sources_only_from_one_corpus_version(changed):
    from src.documents.chunk_reconstruction import ReconstructionError
    class Reader:
        backend='hybrid'
        async def retrieve(self,question,scope):
            if scope['source_type']=='CONTENT':
                return await DenseEvidenceRetriever.retrieve(self,question,scope)
            return dict(corpus_version_id=('other' if changed and scope['source_type']=='BCTN' else 'corpus'),
                        data_version={'kind':'INDEX','id':'index'},items=[{'evidence_id':scope['source_type']}])
    async def run():
        return await Reader().retrieve('question',{'source_type':'CONTENT','companies':['BID']})
    if changed:
        with pytest.raises(ReconstructionError,match='changed'):
            asyncio.run(run())
    else:
        pack=asyncio.run(run())
        assert [article['evidence_id'] for article in pack['items']] == ['BCTN', 'NEWS']
        assert [step['source'] for step in pack['retrieval_trace']] == ['NEWS', 'BCTN']
