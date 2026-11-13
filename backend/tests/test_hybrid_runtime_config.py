"""The live router must honor the same env-file settings as other services."""

from types import SimpleNamespace
import asyncio

from src.api.routers import hybrid_router as api
from src.core.config import Settings
from src.retrieval_orchestration.hybrid_router.adapters import AdapterResult
from src.retrieval_orchestration.hybrid_router.decision_engine import DecisionEngine


def test_graph_versions_are_loaded_from_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("SPRINT4_GRAPH_VERSIONS", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("SPRINT4_GRAPH_VERSIONS=graph-ready-v1,graph-ready-v2\n", encoding="utf-8")

    settings = Settings(_env_file=env_file)

    assert settings.sprint4_graph_versions == "graph-ready-v1,graph-ready-v2"


def test_graph_factory_uses_configured_versions_without_process_env(monkeypatch):
    from src.graph import graph_store, relation_retrieval

    monkeypatch.delenv("SPRINT4_GRAPH_VERSIONS", raising=False)
    monkeypatch.setattr(api, "get_settings", lambda: SimpleNamespace(
        sprint4_graph_versions="graph-ready-v1, graph-ready-v2"))
    monkeypatch.setattr(graph_store.GraphStore, "from_environment", classmethod(
        lambda cls: SimpleNamespace(driver=object(), database="neo4j")))
    monkeypatch.setattr(relation_retrieval, "RelationRetrieval", lambda *args, **kwargs: object())
    monkeypatch.setattr(api, "_registry_tickers", lambda: {"TCB": "CMP-TCB"})

    adapter = api._build_live_graph_adapter()

    assert adapter is not None
    assert adapter._versions == ("graph-ready-v1", "graph-ready-v2")


def test_content_factory_reuses_frozen_corpus_cache(monkeypatch):
    from src.core import db
    from src.documents import embeddings
    from src.vector_retrieval import backend

    seen = {}

    class Retriever:
        def __init__(self, pool, embedder, **kwargs):
            seen["max_cache_age"] = kwargs.get("max_cache_age")

        async def search(self, question, index_id, cache_path, **kwargs):
            seen["cache_path"] = cache_path
            return {"results": []}

    monkeypatch.setattr(api, "get_settings", lambda: SimpleNamespace(
        hybrid_router_index_id="index-id", research_corpus_version_id="corpus-id"))
    monkeypatch.setattr(db, "get_pool", lambda: object())
    monkeypatch.setattr(embeddings, "get_embedding_service", lambda: object())
    monkeypatch.setattr(backend, "HybridRetriever", Retriever)

    async def check():
        adapter = await asyncio.to_thread(api._build_live_content_adapter, asyncio.get_running_loop())
        assert adapter is not None
        await adapter._search_fn("question", "TCB", "2024", 5)

    asyncio.run(check())

    assert seen["cache_path"].endswith("corpus-corpus-id.json")
    assert seen["max_cache_age"] == 7 * 24 * 3600


def test_successful_live_both_reports_live_reason_and_source_provenance():
    class Predictor:
        model_version = "test"

        def predict(self, question):
            return 0.9, 0.9

    class Graph:
        def execute(self, task, *, dependency=None):
            return AdapterResult(task.id, "GRAPH", "OK", "GRAPH_RELATIONS_OK",
                evidence=({"source_id": "edge-1", "source_verified": True},),
                data=({"resolved_companies": ["TCB", "FPT"]},), provenance="LIVE/GRAPH")

    class Content:
        def execute(self, task, *, dependency=None):
            company = task.params["companies"][0]
            return AdapterResult(task.id, "CONTENT", "OK", "CONTENT_OK",
                evidence=({"source_id": f"chunk-{company}", "source_verified": True,
                           "company": company, "period": "2024"},),
                provenance="LIVE/VECTOR")

    result = DecisionEngine(Predictor(), graph_adapter=Graph(), content_adapter=Content()).run(
        "TCB với FPT năm 2024 bên nào khỏe hơn?")

    assert result.status == "OK"
    assert result.execution_mode == "LIVE"
    assert result.reason_code == "LIVE_EXECUTION_OK"
    assert {source["provenance"] for row in result.consolidation["evidence"]
            for source in row["sources"]} == {"LIVE/GRAPH", "LIVE/VECTOR"}
