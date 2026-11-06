"""Persisted Sprint 4 router configuration must work without shell exports."""
import json
from types import SimpleNamespace

from src.api.routers import hybrid_router as api
from src.core.config import Settings


def test_live_content_reuses_preloaded_retriever_for_same_pool_and_scope(monkeypatch):
    from src.vector_retrieval import backend
    constructed, loaded = [], []
    class Retriever:
        def __init__(self, pool, embedder, **kwargs):
            constructed.append((pool, kwargs))
        def load_local_cache(self, index, path):
            loaded.append((index, path))
    monkeypatch.setattr(backend, 'HybridRetriever', Retriever)
    api._content_retriever.cache_clear()
    pool, embedder = object(), object()
    try:
        one = api._content_retriever(pool, embedder, 'corpus1', 'index1', 'cache1')
        assert api._content_retriever(pool, embedder, 'corpus1', 'index1', 'cache1') is one
        assert len(constructed) == len(loaded) == 1
        assert api._content_retriever(pool, embedder, 'corpus2', 'index2', 'cache2') is not one
        assert len(constructed) == len(loaded) == 2
    finally:
        api._content_retriever.cache_clear()


def test_settings_read_graph_scope_and_registry_from_env_file(tmp_path):
    env = tmp_path / 'runtime.env'
    env.write_text('SPRINT4_GRAPH_VERSIONS=v1,v2\nSPRINT4_COMPANY_REGISTRY=registry-r3.json\n', 'utf-8')
    settings = Settings(_env_file=env)
    assert settings.sprint4_graph_versions == 'v1,v2'
    assert settings.sprint4_company_registry == 'registry-r3.json'


def test_ticker_mapping_uses_configured_registry_file(monkeypatch, tmp_path):
    registry = tmp_path / 'registry.json'
    registry.write_text(json.dumps([{'entity_id': 'ftel-verified', 'verified': True,
        'canonical_name': 'FPT Telecom', 'aliases': ['FOX'], 'ticker_aliases': ['FOX']}]), 'utf-8')
    monkeypatch.delenv('SPRINT4_COMPANY_REGISTRY', raising=False)
    monkeypatch.setattr(api, 'get_settings', lambda: SimpleNamespace(sprint4_company_registry=str(registry)))
    assert api._registry_tickers()['FOX'] == 'ftel-verified'


def test_live_graph_adapter_reads_persisted_ready_version_scope(monkeypatch):
    from src.graph.graph_store import GraphStore
    from src.graph import relation_retrieval
    from src.core import db
    monkeypatch.delenv('SPRINT4_GRAPH_VERSIONS', raising=False)
    monkeypatch.setattr(api, 'get_settings', lambda: SimpleNamespace(sprint4_graph_versions='v1,v2'))
    store = SimpleNamespace(driver=object(), database='neo4j', close=lambda: None)
    monkeypatch.setattr(GraphStore, 'from_environment', lambda: store)
    monkeypatch.setattr(relation_retrieval, 'RelationRetrieval',
                        lambda *a, **k: SimpleNamespace(all_versions_ready=lambda versions: versions == ['v1', 'v2']))
    monkeypatch.setattr(db, 'get_pool', lambda: object())
    monkeypatch.setattr(api, '_registry_tickers', lambda names: {'FOX': 'ftel-verified'})
    def schedule(coro, loop):
        coro.close()
        return SimpleNamespace(result=lambda timeout: {}, cancel=lambda: None)
    monkeypatch.setattr(api.asyncio, 'run_coroutine_threadsafe', schedule)
    adapter = api._build_live_graph_adapter(object())
    assert adapter is not None and adapter._versions == ('v1', 'v2')
