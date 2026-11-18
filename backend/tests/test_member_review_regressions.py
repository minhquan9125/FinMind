"""Regression cases from the independent 18 November web/graph review."""
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.retrieval_orchestration.hybrid_router.decision_engine import ScopeResolver
from src.retrieval_orchestration.live_research import DenseEvidenceRetriever, LiveResearchService
from src.vector_retrieval.backend import RetrievalError
from backend.tests.test_web_chat_router import service, Graph, Content, pack, Predictor
from src.retrieval_orchestration.web_chat_router import WebChatRouter
from src.retrieval_orchestration.hybrid_router.decision_engine import DecisionEngine


@pytest.mark.parametrize('symbol', ['VCB','BID','CTG','MBB','TCB','FPT','CMG','ELC','ITD','ICT'])
@pytest.mark.parametrize('question,relation', [
    ('Theo tin tức, ai là Chủ tịch {}?', 'HOLDS_ROLE'),
    ('Theo tin tức, {} hợp tác với những đối tác nào?', 'COOPERATES_WITH')])
def test_news_relationship_uses_graph_with_explicit_news_scope(symbol, question, relation):
    engine, graph, content = service()
    result = asyncio.run(engine.answer(question.format(symbol), 'isolated'))
    assert len(graph.calls) == 1
    assert graph.calls[0]['source_type'] == 'NEWS'
    assert graph.calls[0]['relation_types'] == [relation]
    assert result['hybrid_router']['route'] == 'GRAPH'
    assert not content.calls


def test_content_fallback_timeout_is_not_reported_as_graph_timeout():
    class EmptyGraph(Graph):
        async def retrieve(self, scope):
            value = pack(); value['items'] = []
            return value, []
    class SlowContent(Content):
        async def retrieve(self, question, scope):
            await asyncio.sleep(1)
    route = WebChatRouter(lambda: DecisionEngine(Predictor()), EmptyGraph(), SlowContent(), timeout=.1)
    result = asyncio.run(LiveResearchService(SlowContent(), hybrid_router=route).answer('Ai là Chủ tịch VCB?', 'isolated'))
    assert result['reason_code'] == 'CONTENT_FALLBACK_TIMEOUT'
    assert result['hybrid_router']['graph_calls'] == 1
    assert result['hybrid_router']['vector_calls'] == 1


@pytest.mark.parametrize('code', ['CACHE_BUILD_REQUIRED','CACHE_EXPIRED','CACHE_STALE','CACHE_VERSION_MISMATCH'])
def test_cold_cache_reads_scoped_dense_sources_without_full_rebuild(monkeypatch, code):
    obj = object.__new__(DenseEvidenceRetriever)
    obj.cache_dir = Path('unused-cache'); obj.corpus_version_id = 'pinned-corpus'; obj.pool = object()
    hybrid = SimpleNamespace(search=AsyncMock(side_effect=RetrievalError(code)), build_cache=AsyncMock())
    obj._hybrid = hybrid; obj._hybrid_instance = lambda: hybrid
    obj._embed = AsyncMock(return_value=[1.0])
    read = AsyncMock(return_value=[dict(score=.9)])
    monkeypatch.setattr('src.retrieval_orchestration.live_research.repository.vector_search_filtered', read)
    rows = asyncio.run(obj._hybrid_rows('chair', dict(source_type='BCTN'),
        dict(index_version_id='pinned-index'), 'VCB', '2025'))
    assert rows[0]['score_type'] == 'COSINE_SIMILARITY'
    hybrid.build_cache.assert_not_called()
    assert read.call_args.kwargs == dict(company_symbol='VCB', period='2025', doc_type='ANNUAL_REPORT',
        corpus_version_id='pinned-corpus', exact_period=True)


def test_parent_question_explicitly_requests_incoming_relationship():
    scope = ScopeResolver().resolve('Công ty mẹ của FPT là ai?').scope
    assert scope.relation_types == ['HAS_SUBSIDIARY']
    assert scope.relation_direction == 'INCOMING'
