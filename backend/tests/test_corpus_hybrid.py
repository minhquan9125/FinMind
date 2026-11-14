"""Hybrid SQL must bind corpus membership before either ranking branch."""
import asyncio
from uuid import UUID

import pytest

from src.vector_retrieval.backend import HybridRetriever, ROWS, FINGERPRINT, RetrievalError

CORPUS = '33d33730-0f0a-5274-a7f8-8d32a6be07e8'
INDEX = 'e3725b7d-1a39-5196-b000-3496dbab388f'


class Embedder:
    model_name = 'BAAI/bge-m3'
    revision = '5617a9f61b028005a4858fdac845db406aefb181'


def test_corpus_binding_is_parameterized_for_rows_fingerprint_and_dense():
    engine = HybridRetriever(object(), Embedder(), corpus_version_id=CORPUS)
    for query, args in ((ROWS+' LIMIT $2', (INDEX, 500)), (FINGERPRINT, (INDEX,))):
        sql, bound = engine._statement(query, args)
        assert 'public.corpus_documents' in sql
        assert 'cd.document_hash=d.sha256' in sql
        assert CORPUS not in sql
        assert bound[:-1] == args
        assert bound[-1] == UUID(CORPUS)
        assert f'cd.corpus_version_id=${len(args)+1}::uuid' in sql
    assert 't.index_version_id::text' in ROWS
    assert 'i.chunker_version' in ROWS


def test_corpus_cannot_silently_search_another_index():
    class Connection:
        async def fetchrow(self, sql, *args):
            if 'corpus_versions' in sql:
                return dict(index_version_id='00000000-0000-0000-0000-000000000000',
                            status='FROZEN')
            return dict(embedding_model='BAAI/bge-m3@5617a9f61b02', status='ACTIVE')
        async def fetchval(self, *args): return 'vector(1024)'
    async def run():
        engine = HybridRetriever(object(), Embedder(), corpus_version_id=CORPUS)
        with pytest.raises(RetrievalError) as error:
            await engine._index(Connection(), INDEX, False)
        assert error.value.code == 'CORPUS_INDEX_MISMATCH'
    asyncio.run(run())


def test_web_hybrid_builds_missing_cache_once_and_keeps_rrf_type(tmp_path, monkeypatch):
    from src.documents import repository
    from src.retrieval_orchestration.live_research import DenseEvidenceRetriever, analyze_live
    from src.vector_retrieval import backend
    from tests.test_live_research import pack
    item = pack()['items'][0]
    events = []
    class FakeHybrid:
        ready = False
        async def search(self, question, index, cache, **kwargs):
            events.append(('search', kwargs))
            if not self.ready: raise RetrievalError('CACHE_BUILD_REQUIRED')
            return {'results': [dict(chunk_id=item['chunk_id'], document_id=item['source_id'],
                    text=item['passage'], content_hash=item['content_sha256'], source_sha256=item['source_sha256'],
                    title='FPT', locator=item['locator'], rrf_score=0.03)]}
        async def build_cache(self, *args):
            events.append(('build', {}))
            self.ready = True
    fake = FakeHybrid()
    def construct(pool, embedder, **kwargs):
        assert kwargs['corpus_version_id'] == CORPUS
        return fake
    async def corpus(*args):
        return dict(index_version_id=INDEX, corpus_status='FROZEN', index_status='ACTIVE',
                    embedding_model='BAAI/bge-m3@5617a9f61b02')
    monkeypatch.setattr(repository, 'get_corpus_index', corpus)
    monkeypatch.setattr(backend, 'HybridRetriever', construct)
    async def run():
        engine = DenseEvidenceRetriever(object(), Embedder(), backend='hybrid', cache_dir=tmp_path)
        scope = analyze_live('tiền và tương đương tiền FPT quý 2/2026')['scope']
        for _ in range(2):
            evidence = await engine.retrieve('tiền FPT', scope)
            assert evidence['items'][0]['score'] == {'type': 'RRF', 'value': 0.03}
        assert sum(kind == 'build' for kind, _ in events) == 1
        assert all(options['exact_period'] for kind, options in events if kind == 'search')
    asyncio.run(run())
