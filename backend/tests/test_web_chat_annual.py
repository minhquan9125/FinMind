"""Annual-report routing, exact report years and replayed PDF-page evidence."""
import asyncio
import copy
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.documents.db_chunking import SourceDocument, SourceSection, SourceRow, chunk_document
from src.documents.chunk_reconstruction import ReconstructionError
from src.b1_answering.evidence.citations import prepare_evidence
from src.retrieval_orchestration.live_research import analyze_live, LiveResearchService, DenseEvidenceRetriever
from src.vector_retrieval import backend as cache

CID, IID = str(uuid4()), str(uuid4())


def annual_pack():
    doc = SourceDocument('annual_reports', str(uuid4()), 'ANNUAL_REPORT', 'FPT — BCTN 2025', 'FPT', 'vi',
        [SourceSection('Định hướng', 'FPT | BCTN năm 2025 | trang PDF 3',
            [SourceRow('page:3', 'FPT định hướng phát triển trí tuệ nhân tạo.')])],
        dict(reporting_year=2025, pdf_page=3))
    chunk = chunk_document(doc)[0]
    loc = {**chunk.locator, 'reporting_year':2025, 'symbol':'FPT', 'pdf_page':3}
    return dict(schema_version='1.1', query_id=str(uuid4()), corpus_version_id=CID,
        data_version=dict(kind='INDEX', id=IID), retrieval_backend='hybrid', items=[dict(
            evidence_id=chunk.chunk_id, chunk_id=chunk.chunk_id, source_id=doc.document_id,
            source_type='BCTN', title=doc.title, passage=chunk.text, locator=loc,
            content_sha256=chunk.content_hash, source_sha256='a'*64, source_verified=True,
            score=dict(type='RRF', value=1.0))])


@pytest.mark.parametrize('question', [
    'BCTN FPT 2025 nói gì về quản trị rủi ro?',
    'Tóm tắt chiến lược FPT trong báo cáo thường niên năm 2025.',
    'Theo BCTN FPT năm 2025, doanh thu thuần là bao nhiêu?',
    'Báo cáo thường niên FPT năm 2025 có những nội dung gì?',
])
def test_explicit_annual_requests_search_without_metric_clarification(question):
    value = analyze_live(question)
    assert value['decision'] == 'SEARCH'
    assert value['scope']['source_type'] == 'BCTN'
    assert value['scope']['periods'] == ['2025']
    assert value['scope']['metric_code'] is None  # OCR pages do not use BCTC row codes.
    assert not value.get('clarification_options')


def test_report_year_is_not_the_future_strategy_horizon():
    value = analyze_live('Theo BCTN FPT năm 2025, kế hoạch đến năm 2030 là gì?')
    assert value['decision'] == 'SEARCH'
    assert value['scope']['periods'] == ['2025']


def test_annual_year_followup_keeps_topic_and_latest_does_not_keep_old_year():
    first = analyze_live('Tóm tắt chiến lược FPT theo BCTN năm 2025.')
    second = analyze_live('Còn năm 2024?', first['scope'])
    assert second['decision'] == 'SEARCH'
    assert second['scope']['periods'] == ['2024']
    assert 'chiến lược' in second['scope']['_annual_question']
    assert '2025' not in second['scope']['_annual_question']
    latest = analyze_live('BCTN FPT mới nhất', second['scope'])
    assert latest['scope']['periods'] == ['LATEST_AVAILABLE_PERIOD']
    changed = analyze_live('Tổng tài sản FPT năm 2025 theo BCTC?', first['scope'])
    assert changed['scope']['source_type'] == 'BCTC'


def test_company_clarification_keeps_annual_topic():
    first = analyze_live('BCTN năm 2025 nói gì về chiến lược?')
    assert first['reason_code'] == 'MISSING_COMPANY'
    second = analyze_live('FPT', first['scope'])
    assert second['scope']['source_type'] == 'BCTN'
    assert second['scope']['periods'] == ['2025']
    assert 'chiến lược' in second['scope']['_annual_question']


def test_annual_service_does_not_let_news_intercept_the_source_request():
    class Retriever:
        async def retrieve(self, question, scope):
            assert 'Báo cáo thường niên' in question
            assert scope['source_type'] == 'BCTN'
            return annual_pack()
    news = AsyncMock()
    service = LiveResearchService(Retriever(), admin_news=news)
    result = asyncio.run(service.answer('Theo BCTN FPT năm 2025 có tin gì về chiến lược?', 'test'))
    assert result['status'] == 'EVIDENCE_READY'
    assert result['answering']['reason_code'] == 'PROVIDER_NOT_CONFIGURED'
    assert result['scope']['periods'] == ['2025']
    news.answer.assert_not_awaited()
    assert prepare_evidence(result['evidence_pack'])


def test_service_rejects_verified_but_wrong_report_year():
    class Retriever:
        async def retrieve(self, *args):
            value = annual_pack()
            value['items'][0]['locator']['reporting_year'] = 2024
            return value
    result = asyncio.run(LiveResearchService(Retriever()).answer('BCTN FPT năm 2025 nói gì về chiến lược?', 'test'))
    assert result['reason_code'] == 'ANNUAL_SCOPE_MISMATCH'
    assert result['status'] == 'INSUFFICIENT_EVIDENCE'
    assert not result.get('answering')


def test_web_api_annual_topic_uses_vector_then_existing_answering(tmp_path):
    import json
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from src.api.routers import research_chat as api
    from src.retrieval_orchestration.hybrid_router.decision_engine import DecisionEngine
    from src.retrieval_orchestration.web_chat_router import WebChatRouter
    from src.retrieval_orchestration.web_sessions import SessionStore
    class Predictor:
        model_version = 'annual-contract'
        def predict(self, question): return (0.01, 0.99)
    class Retriever:
        calls = []
        async def retrieve(self, question, scope):
            self.calls.append(copy.deepcopy(scope))
            return annual_pack()
    class Provider:
        async def count_tokens(self, request): return 100
        async def generate(self, request):
            body = json.loads(request['contents'][0]['parts'][0]['text'])
            assert body['scope']['source_type'] == 'BCTN'
            eid = body['evidence'][0]['evidence_id']
            quote = 'FPT định hướng phát triển trí tuệ nhân tạo.'
            return dict(model_version='isolated-provider', usage=dict(input_tokens=100, output_tokens=20, total_tokens=120),
                payload=dict(claims=[dict(text=quote, evidence_ids=[eid],
                    support_quotes=[dict(evidence_id=eid, quote=quote)])]))
    reader = Retriever()
    graph = AsyncMock()
    service = LiveResearchService(reader, provider=Provider(),
        hybrid_router=WebChatRouter(lambda: DecisionEngine(Predictor()), graph, reader))
    app = FastAPI()
    app.include_router(api.router)
    owner = str(uuid4())
    app.dependency_overrides[api.get_owner] = lambda: owner
    store = SessionStore(tmp_path, engine=service)
    app.dependency_overrides[api.get_store] = lambda: store
    with TestClient(app) as client:
        created = client.post('/api/research/chat/sessions').json()
        response = client.post(f"/api/research/chat/sessions/{created['session_id']}/messages",
            json=dict(text='Tóm tắt chiến lược FPT trong BCTN năm 2025.', revision=0))
        assert response.status_code == 200, response.text
        result = response.json()['messages'][-1]['result']
        assert result['scope']['source_type'] == 'BCTN'
        assert result['answering']['status'] == 'DRAFT_READY'
        assert result['answering']['citations'][0]['source_type'] == 'BCTN'
        assert reader.calls[0]['periods'] == ['2025']
        graph.retrieve.assert_not_awaited()


def test_annual_retriever_selects_annual_document_and_replays_pages():
    sample = annual_pack()['items'][0]
    class Retriever(DenseEvidenceRetriever):
        async def _corpus(self): return dict(index_version_id=IID)
        async def _hybrid_rows(self, question, scope, corpus, company, period, doc_type=None):
            assert (company, period, doc_type) == ('FPT', '2025', 'ANNUAL_REPORT')
            return [dict(chunk_id=sample['chunk_id'], score=0.1)]
        async def _annual_rows(self, rows, corpus, company, year):
            self.replayed = True
            return [dict(chunk_id=sample['chunk_id'], document_id=sample['source_id'],
                text=sample['passage'], content_hash=sample['content_sha256'],
                source_sha256=sample['source_sha256'], locator_json=sample['locator'], title=sample['title'], score=0.1)]
    reader = Retriever(None, None, corpus_version_id=CID, backend='hybrid')
    result = asyncio.run(reader.retrieve('chiến lược', dict(companies=['FPT'], periods=['2025'], source_type='BCTN')))
    assert reader.replayed
    assert result['items'][0]['source_type'] == 'BCTN'
    assert prepare_evidence(result)


def test_annual_replay_rejects_wrong_year_even_if_candidate_search_returns_it(monkeypatch):
    from src.documents import annual_source_reader
    sample = annual_pack()['items'][0]
    @asynccontextmanager
    async def tx(**options):
        assert options['readonly'] is True
        yield
    class Conn:
        transaction = staticmethod(tx)
    class Pool:
        @asynccontextmanager
        async def acquire(self): yield Conn()
    monkeypatch.setattr(annual_source_reader, 'read_annual_chunk', AsyncMock(return_value=dict(
        locator={**sample['locator'], 'reporting_year':2024}, index_version_id=IID)))
    reader = DenseEvidenceRetriever(Pool(), None, corpus_version_id=CID, backend='hybrid')
    with pytest.raises(ReconstructionError, match='Annual source differs'):
        asyncio.run(reader._annual_rows([dict(chunk_id=sample['chunk_id'])], dict(index_version_id=IID), 'FPT', '2025'))


def test_cache_uses_report_year_instead_of_publication_date_and_invalidates_v2():
    row = dict(chunk_id=str(uuid4()), content_hash='a'*64, company='FPT', symbols=[],
        period='2026-04-01', doc_type='ANNUAL_REPORT', locator_json=dict(reporting_year=2025))
    assert cache._metadata(row)['period'] == '2025'
    import json
    assert cache._metadata({**row, 'locator_json':json.dumps(row['locator_json'])})['period'] == '2025'
    assert cache._metadata({**row, 'locator_json':{}})['period'] is None
    assert "d.doc_type='ANNUAL_REPORT'" in cache.FIELDS
    assert 'reporting_year' in cache.FIELDS
    old = dict(version=2, tokenizer=cache.TOKENIZER_VERSION, index_id=IID, model=cache.MODEL,
        built_at=1, fingerprint='a'*32, rows=[])
    with pytest.raises(cache.RetrievalError, match='CACHE_VERSION_MISMATCH'):
        cache._validate_cache(old, IID, cache.MODEL, 1, 3600)


def test_shared_release_alias_requires_exact_frozen_parent_and_same_origin(monkeypatch):
    import hashlib, uuid
    from src.documents.annual_source_reader import _annual_binding
    from src.documents.release_identity import release_document_id
    from src.documents import shared_source
    origin, parent, source_doc, parent_chunk = [str(uuid4()) for _ in range(4)]
    chunk = str(uuid.UUID(hashlib.md5(f'shared:{IID}:{parent_chunk}'.encode()).hexdigest()))
    row = dict(document_id=release_document_id(origin, source_doc), index_version_id=IID,
               chunk_id=chunk, content_hash='a'*64)
    locator = dict(reconstruction=dict(document_id=source_doc))
    async def root(conn, index, cache):
        return dict(corpus_version_id=CID, source_index_version_id=origin)
    monkeypatch.setattr(shared_source, 'read_release_root', root)
    class Conn:
        async def fetch(self, sql, *args):
            assert "cv.status='FROZEN'" in sql and 'p.locator_json=$3::jsonb' in sql
            assert 'cd.document_hash=d.sha256' in sql and "md5('shared:'" in sql
            return [dict(index_version_id=parent)] if str(args[-1]) == chunk else []
    value = asyncio.run(_annual_binding(Conn(), row, locator, CID, {}))
    assert value['mode'] == 'SHARED_RELEASE_SOURCE_ALIAS_V1'
    assert value['source_index_version_id'] == origin
    with pytest.raises(ReconstructionError, match='No unique frozen parent'):
        asyncio.run(_annual_binding(Conn(), {**row, 'chunk_id':str(uuid4())}, locator, CID, {}))
    with pytest.raises(ReconstructionError, match='Stored document'):
        asyncio.run(_annual_binding(Conn(), {**row, 'document_id':str(uuid4())}, locator, CID, {}))
    with pytest.raises(ReconstructionError, match='No registered source-release lineage'):
        asyncio.run(_annual_binding(Conn(), row, locator, str(uuid4()), {}))
