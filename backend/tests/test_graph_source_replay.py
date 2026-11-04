"""Graph citations must be replayed from PostgreSQL before API exposure."""

import asyncio
from dataclasses import replace
from hashlib import sha256
from types import SimpleNamespace

import pytest

from src.graph_review.models import SourceProblem, VerifiedSource
from src.retrieval_orchestration.hybrid_router.graph_source import verify_relation_paths


TEXT = "TCBS là công ty con của TCB tại ngày 31/12/2025."
HASH = sha256(TEXT.encode("utf-8")).hexdigest()
LOCATOR = {"kind": "db_text_span", "page": 39}


def path(quote="TCBS là công ty con của TCB"):
    return [{"graph_version_id": "graph-v1", "relations": [{
        "relation_id": "rel-1", "corpus_id": "corpus-v1", "index_version_id": "index-v1",
        "evidence": [{"document_id": "doc-1", "chunk_id": "chunk-1",
                      "document_version": "doc-hash", "locator": LOCATOR,
                      "quote": quote}],
    }]}]


def source(**changes):
    return replace(VerifiedSource(
        "doc-1", "doc-hash", "chunk-1", "corpus-v1", "index-v1",
        "source-hash", HASH, LOCATOR, TEXT,
    ), **changes)


class Reader:
    def __init__(self, value):
        self.value = value
        self.calls = []

    async def read_current(self, chunk_id, corpus_id):
        self.calls.append((chunk_id, corpus_id))
        return self.value


def test_verified_source_yields_citation_with_pinned_ids():
    reader = Reader(source())
    citations = asyncio.run(verify_relation_paths(path(), reader))
    assert reader.calls == [("chunk-1", "corpus-v1")]
    assert len(citations) == 1
    assert citations[0]["source_verified"] is True
    assert citations[0]["graph_version_id"] == "graph-v1"
    assert citations[0]["content_hash"] == HASH


@pytest.mark.parametrize("changes", [
    {"document_id": "other-doc"}, {"document_version": "other-version"},
    {"corpus_id": "other-corpus"}, {"index_version_id": "other-index"},
    {"locator": {"page": 40}}, {"content_hash": "0" * 64},
    {"active": False}, {"verification_mode": "FIXTURE"},
])
def test_wrong_source_never_becomes_a_citation(changes):
    with pytest.raises(SourceProblem):
        asyncio.run(verify_relation_paths(path(), Reader(source(**changes))))


def test_quote_must_appear_in_replayed_text():
    with pytest.raises(SourceProblem):
        asyncio.run(verify_relation_paths(path("không có trong nguồn"), Reader(source())))


def test_one_bad_source_blocks_the_whole_result():
    paths = path()
    paths[0]["relations"][0]["evidence"].append({
        "document_id": "doc-2", "chunk_id": "chunk-2", "document_version": "doc-hash",
        "locator": LOCATOR, "quote": "không có trong nguồn",
    })
    with pytest.raises(SourceProblem):
        asyncio.run(verify_relation_paths(paths, Reader(source())))


def test_live_adapter_does_not_claim_unverified_graph_citation():
    from src.retrieval_orchestration.hybrid_router.adapters import LiveGraphAdapter
    from src.retrieval_orchestration.hybrid_router.schemas import RouterTask

    retrieval = SimpleNamespace(query=lambda *args, **kwargs: path())
    task = RouterTask(id="g1", adapter="GRAPH", operation="find_relationships",
                      params={"companies": ["TCB"]})
    adapter = LiveGraphAdapter(None, retrieval, ["graph-v1"], {"TCB": "company-tcb"})
    result = adapter.execute(task)
    assert result.reason_code == "GRAPH_SOURCE_READER_NOT_READY"
    assert not result.evidence and not result.data

    def mismatch(paths):
        raise SourceProblem("ERR_SOURCE_HASH_MISMATCH")

    adapter = LiveGraphAdapter(None, retrieval, ["graph-v1"], {"TCB": "company-tcb"},
                               verify_sources=mismatch)
    result = adapter.execute(task)
    assert result.reason_code == "GRAPH_SOURCE_MISMATCH"
    assert not result.evidence and not result.data

    def timeout(paths):
        raise TimeoutError()

    adapter = LiveGraphAdapter(None, retrieval, ["graph-v1"], {"TCB": "company-tcb"},
                               verify_sources=timeout)
    result = adapter.execute(task)
    assert result.reason_code == "GRAPH_SOURCE_TIMEOUT"
    assert not result.evidence and not result.data


def test_api_exposes_verified_graph_data_and_citation(monkeypatch):
    from src.api.routers import hybrid_router as api
    from src.retrieval_orchestration.hybrid_router.adapters import AdapterResult
    from src.retrieval_orchestration.hybrid_router.decision_engine import ExecutionResult
    from src.retrieval_orchestration.hybrid_router.schemas import RouterOutput, RouterScope, RouterTask

    # Use the real response serializer; no model, database or network is needed.
    graph = AdapterResult("g1", "GRAPH", "OK", "GRAPH_RELATIONS_OK",
                          data=({"relation_id": "rel-1"},),
                          evidence=({"chunk_id": "chunk-1", "source_verified": True},),
                          provenance="LIVE/GRAPH")
    decision = RouterOutput(decision="SEARCH", route="GRAPH",
                            scope=RouterScope(companies=["TCB"]),
                            tasks=[RouterTask(id="g1", adapter="GRAPH",
                                              operation="find_relationships")])
    result = ExecutionResult(decision, "OK", "GRAPH_RELATIONS_OK", (graph,), "LIVE")
    monkeypatch.setattr(api, "get_settings", lambda: SimpleNamespace(hybrid_router_mode="live"))
    monkeypatch.setattr(api, "_get_live_engine", lambda loop: SimpleNamespace(run=lambda *a, **k: result))
    response = asyncio.run(api.run_router(api.RouterTestRequest(question="TCB có công ty con nào?")))
    assert response["adapter_results"][0]["data"][0]["relation_id"] == "rel-1"
    assert response["adapter_results"][0]["evidence"][0]["source_verified"] is True


def test_elc_symbol_resolves_from_official_company_name(monkeypatch):
    from src.api.routers import hybrid_router as api

    monkeypatch.delenv("SPRINT4_COMPANY_REGISTRY", raising=False)
    result = api._registry_tickers({
        "ELC": "Công ty Cổ phần Công nghệ - Viễn thông Elcom",
        "UNKNOWN": "Tên không tồn tại trong registry",
    })
    assert result["ELC"] == "CMP-5e8ffe9a518de32ce4d6"
    assert "UNKNOWN" not in result
