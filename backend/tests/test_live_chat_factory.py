"""The actual router factory selects live corpus retrieval; no secret/network use."""
from src.api.routers import research_chat as api
from src.core.config import Settings
from src.core import db
from src.documents import embeddings


def test_router_defaults_to_corpus_hybrid_without_gemini(monkeypatch):
    settings = Settings(_env_file=None, research_chat_live=True, research_retrieval_backend='hybrid',
                        gemini_api_key='', b1_gemini_free_tier_confirmed=False)
    monkeypatch.setattr(api, 'get_settings', lambda: settings)
    monkeypatch.setattr(db, 'get_pool', lambda: object())
    monkeypatch.setattr(embeddings, 'get_embedding_service', lambda: object())
    api.get_store.cache_clear()
    try:
        store = api.get_store()
        assert store.engine.execution_mode == 'LIVE'
        assert store.engine.provider is None
        assert store.engine.retriever.backend == 'hybrid'
        assert store.engine.retriever.corpus_version_id == settings.research_corpus_version_id
    finally:
        api.get_store.cache_clear()


def test_fixture_override_does_not_touch_database(monkeypatch):
    monkeypatch.setattr(api, 'get_settings', lambda: Settings(_env_file=None, research_chat_live=False))
    def forbidden(): raise AssertionError('fixture mode must not acquire DB pool')
    monkeypatch.setattr(db, 'get_pool', forbidden)
    api.get_store.cache_clear()
    try: assert api.get_store().engine is None
    finally: api.get_store.cache_clear()
