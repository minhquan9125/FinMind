"""Startup warms the shared retriever, never Gemini or a saved chat session."""
import asyncio
import threading
from contextlib import asynccontextmanager

import pytest

from src.retrieval_orchestration.live_research import DenseEvidenceRetriever, MODEL
from src.documents import repository
from src.vector_retrieval import backend
from tests.test_corpus_hybrid import CORPUS, INDEX


@pytest.mark.parametrize('mode', ['dense', 'hybrid'])
def test_warmup_embeds_off_loop_and_prepares_only_selected_backend(monkeypatch, tmp_path, mode):
    events, main_thread = [], threading.get_ident()
    class Embedder:
        model_name = 'BAAI/bge-m3'
        revision = '5617a9f61b028005a4858fdac845db406aefb181'
        def embed_query(self, text):
            assert threading.get_ident() != main_thread
            events.append('embed')
            return [1.0]+[0.0]*1023
    class Hybrid:
        async def prepare_cache(self, index, path):
            assert index == INDEX
            assert path.name == f'corpus-{CORPUS}.json'
            events.append('bm25')
            return {'status': 'CACHE_READY', 'chunks': 10}
    async def corpus(*args):
        events.append('corpus')
        return dict(index_version_id=INDEX, corpus_status='FROZEN', index_status='ACTIVE', embedding_model=MODEL)
    monkeypatch.setattr(repository, 'get_corpus_index', corpus)
    monkeypatch.setattr(backend, 'HybridRetriever', lambda *args, **kwargs: Hybrid())
    adapter = DenseEvidenceRetriever(object(), Embedder(), backend=mode, cache_dir=tmp_path)
    result = asyncio.run(adapter.warmup())
    assert events == ['corpus', 'embed']+(['bm25'] if mode == 'hybrid' else [])
    assert result['backend'] == mode
    assert result['index_version_id'] == INDEX


def test_warmup_rejects_invalid_corpus_before_loading_model(monkeypatch):
    async def corpus(*args): return None
    monkeypatch.setattr(repository, 'get_corpus_index', corpus)
    adapter = DenseEvidenceRetriever(object(), object())
    with pytest.raises(Exception) as error: asyncio.run(adapter.warmup())
    assert getattr(error.value, 'code', None) == 'CORPUS_NOT_READY'


class Connection:
    @asynccontextmanager
    async def transaction(self, **kwargs):
        assert kwargs == {'readonly': True, 'isolation': 'repeatable_read'}
        yield


class Pool:
    @asynccontextmanager
    async def acquire(self): yield Connection()


@pytest.mark.parametrize('initial', ['ready', 'CACHE_BUILD_REQUIRED', 'CACHE_EXPIRED', 'CACHE_STALE', 'CACHE_VERSION_MISMATCH'])
def test_prepare_cache_reuses_or_repairs_once_and_loads_into_memory(monkeypatch, initial):
    retriever = backend.HybridRetriever(Pool(), object())
    events = []
    state = {'cache': initial}
    async def index(*args): return {'embedding_model': MODEL}
    async def value(*args): return 'current'
    def cache(*args):
        events.append('load')
        if state['cache'] == 'CACHE_STALE':
            return {'fingerprint': 'old', 'rows': [1, 2]}, object()
        if state['cache'] != 'ready': raise backend.RetrievalError(state['cache'])
        return {'fingerprint': 'current', 'rows': [1, 2]}, object()
    async def build(*args):
        events.append('build')
        state['cache'] = 'ready'
    monkeypatch.setattr(retriever, '_index', index)
    monkeypatch.setattr(retriever, '_value', value)
    monkeypatch.setattr(retriever, '_cache', cache)
    monkeypatch.setattr(retriever, 'build_cache', build)
    result = asyncio.run(retriever.prepare_cache(INDEX, 'unused-cache.json'))
    assert result['chunks'] == 2
    assert events == (['load'] if initial == 'ready' else ['load', 'build', 'load'])


@pytest.mark.parametrize('code', ['CACHE_CHECKSUM_MISMATCH', 'INVALID_CACHE', 'HASH_MISMATCH', 'CORPUS_NOT_READY'])
def test_prepare_cache_does_not_hide_integrity_errors(monkeypatch, code):
    retriever = backend.HybridRetriever(Pool(), object())
    async def index(*args): return {'embedding_model': MODEL}
    def cache(*args): raise backend.RetrievalError(code)
    async def forbidden(*args): raise AssertionError('must not rebuild corrupt evidence')
    monkeypatch.setattr(retriever, '_index', index)
    monkeypatch.setattr(retriever, '_cache', cache)
    monkeypatch.setattr(retriever, 'build_cache', forbidden)
    with pytest.raises(backend.RetrievalError) as error:
        asyncio.run(retriever.prepare_cache(INDEX, 'unused-cache.json'))
    assert error.value.code == code
