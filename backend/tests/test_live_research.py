"""Live chat contracts with isolated sources/providers; no network or model downloads."""
import asyncio
import copy
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest

from src.b1_answering.evidence.citations import CitationError, prepare_evidence
from src.documents.db_chunking import chunk_document, financial_documents
from src.retrieval_orchestration.live_research import (
    DenseEvidenceRetriever, LiveResearchService, analyze_live,
)
from src.retrieval_orchestration.web_sessions import SessionStore

CORPUS = '33d33730-0f0a-5274-a7f8-8d32a6be07e8'
INDEX = 'e3725b7d-1a39-5196-b000-3496dbab388f'


def pack():
    doc = financial_documents([dict(
        report_id='report-fpt', period_code='2026-Q2', symbol='FPT', company_name='FPT',
        statement_scope='UNKNOWN', section='BALANCE_SHEET',
        code='CASH_AND_CASH_EQUIVALENTS', canonical_name='Tiền và tương đương tiền',
        observation_id='obs-1', value=100, unit='SOURCE_NATIVE',
    )], renderer_version='db-financial-v3')[0]
    chunk = chunk_document(doc)[0]
    return dict(schema_version='1.1', query_id='live-query',
                data_version={'kind': 'INDEX', 'id': INDEX}, corpus_version_id=CORPUS,
                items=[dict(evidence_id=str(uuid4()), chunk_id=str(uuid4()), source_id=str(uuid4()),
                            source_type='BCTC', source_sha256='a'*64,
                            content_sha256=chunk.content_hash, passage=chunk.text,
                            source_verified=True, locator=chunk.locator,
                            score={'type': 'COSINE_SIMILARITY', 'value': 0.8})])


class Retriever:
    def __init__(self, evidence=None):
        self.evidence = pack() if evidence is None else evidence
        self.calls = []

    async def retrieve(self, question, scope):
        self.calls.append((question, copy.deepcopy(scope)))
        return copy.deepcopy(self.evidence)


class Provider:
    def __init__(self):
        self.calls = 0

    async def count_tokens(self, request):
        self.last_question = json.loads(request['contents'][0]['parts'][0]['text'])['question']
        return 100

    async def generate(self, request):
        self.calls += 1
        item = json.loads(request['contents'][0]['parts'][0]['text'])['evidence'][0]
        return dict(model_version='test', usage={'input_tokens': 100, 'output_tokens': 10, 'total_tokens': 110},
                    payload={'claims': [{'text': item['passage'], 'evidence_ids': [item['evidence_id']],
                                         'support_quotes': [{'evidence_id': item['evidence_id'], 'quote': item['passage']}]}]})


def test_live_locator_accepted_without_inventing_pages():
    evidence = pack()
    out = prepare_evidence(evidence)
    assert next(iter(out.values()))['locator'] == evidence['items'][0]['locator']


def test_live_rrf_score_is_not_mislabeled_as_cosine():
    evidence = pack()
    evidence['items'][0]['score'] = {'type': 'RRF', 'value': 0.03}
    assert next(iter(prepare_evidence(evidence).values()))['score']['type'] == 'RRF'


@pytest.mark.parametrize('mutation', ['hash', 'unverified', 'locator', 'corpus'])
def test_live_evidence_fail_closed(mutation):
    evidence = pack()
    if mutation == 'hash': evidence['items'][0]['passage'] += 'changed'
    if mutation == 'unverified': evidence['items'][0]['source_verified'] = False
    if mutation == 'locator': evidence['items'][0]['locator']['row_keys'] = []
    if mutation == 'corpus': evidence['corpus_version_id'] = 'latest'
    with pytest.raises(CitationError): prepare_evidence(evidence)


def test_live_scope_period_metric_and_followups():
    first = analyze_live('tiền và tương đương tiền FPT quý 2/2026')
    assert first['decision'] == 'SEARCH'
    assert first['scope']['periods'] == ['2026-Q2']
    assert first['scope']['metric_code'] == 'CASH_AND_CASH_EQUIVALENTS'
    assert first['scope']['measure_basis'] == 'POINT_IN_TIME'
    second = analyze_live('còn SSI', first['scope'])
    assert second['scope']['companies'] == ['SSI']
    assert second['scope']['metric_code'] == first['scope']['metric_code']
    assert second['scope']['periods'] == ['2026-Q2']
    ambiguous = analyze_live('lợi nhuận FPT năm 2025', first['scope'])
    assert ambiguous['decision'] == 'ASK_CLARIFICATION'
    after = analyze_live('sau', ambiguous['scope'])
    assert after['scope']['metric_code'] == 'PROFIT_AFTER_TAX'
    assert after['scope']['periods'] == ['2025']


def test_live_news_and_advice_are_separate():
    news = analyze_live('Tin tức FPT tháng 9/2026')
    assert news['decision'] == 'SEARCH'
    assert news['scope']['source_type'] == 'NEWS'
    assert news['scope']['periods'] == ['2026-09']
    assert analyze_live('nên mua FPT không')['decision'] == 'UNSUPPORTED'
    assert analyze_live('tổng tài sản FPT')['decision'] == 'ASK_CLARIFICATION'


def test_live_pipeline_binds_draft_and_preserves_unknown_units():
    async def run():
        retriever, provider = Retriever(), Provider()
        engine = LiveResearchService(retriever, provider=provider)
        result = await engine.answer('tiền và tương đương tiền FPT quý 2/2026', 'session')
        assert result['execution_mode'] == 'LIVE'
        assert result['answering']['status'] == 'DRAFT_READY'
        assert provider.calls == 1
        assert result['answering']['citations'][0]['locator'] == retriever.evidence['items'][0]['locator']
        assert result['answering']['citations'][0]['content_sha256'] == retriever.evidence['items'][0]['content_sha256']
        assert result['answering']['cautions']
        assert 'đơn vị chưa xác minh' not in result['answering']['draft']
        assert result['answering']['presentation']['unit_annotations']
        assert not result['answering']['manifest']['components']['b3_answer_verification']
    asyncio.run(run())


def test_generation_receives_resolved_question_on_ticker_only_followup():
    async def run():
        provider = Provider()
        scope = analyze_live('tiền và tương đương tiền FPT quý 2/2026')['scope']
        await LiveResearchService(Retriever(), provider=provider).answer('còn SSI', 'session', scope)
        assert 'SSI' in provider.last_question
        assert '2026-Q2' in provider.last_question
        assert 'tiền và các khoản tương đương tiền' in provider.last_question
    asyncio.run(run())


def test_no_generation_for_empty_or_unverified_sources():
    async def run():
        for mode in ('empty', 'unverified'):
            evidence = pack()
            if mode == 'empty': evidence['items'] = []
            else: evidence['items'][0]['source_verified'] = False
            provider = Provider()
            result = await LiveResearchService(Retriever(evidence), provider=provider).answer(
                'tiền và tương đương tiền FPT quý 2/2026', 'session')
            assert result['status'] in ('NO_DATA', 'INSUFFICIENT_EVIDENCE')
            assert provider.calls == 0
    asyncio.run(run())


def test_live_session_restart_resume_does_not_repeat_retrieval(tmp_path):
    async def run():
        retriever = Retriever()
        store = SessionStore(tmp_path, engine=LiveResearchService(retriever))
        owner = str(uuid4())
        snap = await store.create(owner)
        assert snap['execution_mode'] == 'LIVE'
        sid = snap['session_id']
        snap = await store.send(owner, sid, 'tiền và tương đương tiền FPT quý 2/2026', 0)
        assert len(retriever.calls) == 1
        fresh = SessionStore(tmp_path, engine=LiveResearchService(retriever))
        loaded = await fresh.get(owner, sid)
        child = await fresh.resume(owner, sid)
        assert len(retriever.calls) == 1
        assert loaded['messages'] == snap['messages']
        await fresh.send(owner, child['session_id'], 'còn SSI', 0)
        assert retriever.calls[-1][1]['companies'] == ['SSI']
        assert retriever.calls[-1][1]['periods'] == ['2026-Q2']
        assert len(retriever.calls) == 2
        saved = json.loads((tmp_path / owner / (child['session_id']+'.json')).read_text('utf-8'))
        assert saved['metadata']['live_context']['companies'] == ['SSI']
    asyncio.run(run())


def test_dense_adapter_validates_corpus_and_offloads_embedding(monkeypatch):
    import threading
    from src.documents import repository
    main_thread = threading.get_ident()
    calls = []
    class Embedder:
        def embed_query(self, question):
            assert threading.get_ident() != main_thread
            return [1.0] + [0.0]*1023
    async def corpus(*args):
        return dict(index_version_id=INDEX, corpus_status='FROZEN', index_status='ACTIVE',
                    embedding_model='BAAI/bge-m3@5617a9f61b02')
    async def search(*args, **kwargs):
        calls.append(kwargs)
        return []
    monkeypatch.setattr(repository, 'get_corpus_index', corpus)
    monkeypatch.setattr(repository, 'vector_search_filtered', search)
    async def run():
        adapter = DenseEvidenceRetriever(object(), Embedder(), corpus_version_id=CORPUS)
        result = await adapter.retrieve('tổng tài sản', dict(companies=['FPT'], periods=['2026-Q2'],
                                      source_type='BCTC', metric_code='TOTAL_ASSETS'))
        assert result['data_version']['id'] == INDEX
        assert calls[0]['corpus_version_id'] == CORPUS
        assert not calls[0].get('preview_source_changed', False)
    asyncio.run(run())
