"""Offline WBS12 contract tests; no Neo4j or PostgreSQL connection."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

from src.retrieval_orchestration.hybrid_router.decision_engine import DecisionEngine
from src.retrieval_orchestration.hybrid_router.schemas import RouterTask
from src.retrieval_orchestration.hybrid_router.sprint4_graph_adapter import Sprint4GraphAdapter


def relation():
    return {
        "relation_id": "rel-1", "relation_type": "HAS_SUBSIDIARY",
        "subject_id": "company-a", "object_id": "company-b",
        "review_status": "APPROVED", "graph_version_id": "graph-v1",
        "corpus_version_id": "corpus-v1", "matched_companies": ["FPT"],
        "matched_period": "2025", "temporal": {"as_of": "2025-12-31"},
        "path": ["company-a", "rel-1", "company-b"],
        "evidence": [{"document_id": "doc-1", "chunk_id": "chunk-1",
                      "quote": "FPT owns company B"}],
    }


def source(document_id, chunk_id, corpus_version_id):
    text = "According to the report, FPT owns company B."
    return {"document_id": document_id, "chunk_id": chunk_id,
            "corpus_version_id": corpus_version_id,
            "chunk_text": text,
            "content_hash": sha256(text.encode("utf-8")).hexdigest(),
            "locator": {"page": 12}}


def task():
    return RouterTask(id="g1", adapter="GRAPH", operation="find_relationships",
                      params={"companies": ["FPT"], "periods": ["2025"],
                              "topic": "RELATIONSHIP_LOOKUP", "question": "FPT subsidiaries?"})


def adapter(rows=None, source_fn=source):
    return Sprint4GraphAdapter(lambda request: deepcopy([relation()] if rows is None else rows),
                               source_fn, graph_version_id="graph-v1",
                               corpus_version_id="corpus-v1")


def test_maps_router_scope_and_returns_replayed_citation():
    bridge = adapter()
    result = bridge.execute(task())
    assert result.status == "OK"
    assert result.data[0]["path"] == ["company-a", "rel-1", "company-b"]
    assert result.evidence[0]["locator"] == {"page": 12}
    assert result.evidence[0]["source_verified"] is True
    assert bridge.calls[0]["companies"] == ["FPT"]
    assert bridge.calls[0]["periods"] == ["2025"]
    assert bridge.calls[0]["graph_version_id"] == "graph-v1"
    assert bridge.calls[0]["corpus_version_id"] == "corpus-v1"
    assert "cypher" not in bridge.calls[0]


def test_pending_relation_never_leaks_to_data_or_citations():
    pending = relation()
    pending["review_status"] = "PENDING"
    bridge = adapter([pending])
    result = bridge.execute(task())
    assert result.status == "NO_DATA"
    assert result.data == result.evidence == ()


def test_wrong_company_period_and_version_fail_closed():
    for field, value, reason in (
        ("matched_companies", ["VCB"], "GRAPH_COMPANY_SCOPE_MISMATCH"),
        ("matched_period", "2024", "GRAPH_PERIOD_SCOPE_MISMATCH"),
        ("corpus_version_id", "corpus-v2", "GRAPH_VERSION_MISMATCH"),
        ("graph_version_id", "graph-v2", "GRAPH_VERSION_MISMATCH"),
    ):
        row = relation()
        row[field] = value
        result = adapter([row]).execute(task())
        assert result.status == "INSUFFICIENT_EVIDENCE"
        assert result.reason_code == reason
        assert not result.data and not result.evidence


def test_missing_source_or_changed_quote_fails_without_partial_citation():
    row = relation()
    row["evidence"].append({"document_id": "doc-2", "chunk_id": "chunk-2",
                            "quote": "not in the pinned source"})
    result = adapter([row]).execute(task())
    assert result.reason_code == "GRAPH_SOURCE_MISMATCH"
    assert result.data == result.evidence == ()

    def changed_hash(document_id, chunk_id, corpus_version_id):
        replay = source(document_id, chunk_id, corpus_version_id)
        replay["content_hash"] = "different"
        return replay

    result = adapter([relation()], changed_hash).execute(task())
    assert result.reason_code == "GRAPH_SOURCE_MISMATCH"
    assert not result.evidence


def test_empty_timeout_and_missing_version_are_distinct():
    assert adapter([]).execute(task()).status == "NO_DATA"

    def timeout(_request):
        raise TimeoutError()

    bridge = Sprint4GraphAdapter(timeout, source, graph_version_id="graph-v1",
                                 corpus_version_id="corpus-v1")
    assert bridge.execute(task()).reason_code == "GRAPH_TIMEOUT"
    bridge = Sprint4GraphAdapter(timeout, source, graph_version_id="",
                                 corpus_version_id="corpus-v1")
    assert bridge.execute(task()).reason_code == "GRAPH_VERSION_REQUIRED"
    assert bridge.calls == []


def test_graph_route_stays_graph_after_source_replay():
    class Predictor:
        model_version = "fixture"

        def predict(self, question):
            return 0.9, 0.1

    engine = DecisionEngine(Predictor(), graph_adapter=adapter())
    result = engine.run("FPT có công ty con nào năm 2025?")
    assert result.decision.route == "GRAPH"
    assert result.status == "OK"
    assert result.adapter_results[0].provenance == "LIVE/GRAPH"
    assert result.adapter_results[0].evidence[0]["document_id"] == "doc-1"


def test_both_stops_before_content_when_graph_has_no_approved_relation():
    class Predictor:
        model_version = "fixture"

        def predict(self, question):
            return 0.9, 0.9

    class Content:
        def __init__(self):
            self.calls = []

        def execute(self, task, *, dependency=None):
            self.calls.append(task)
            raise AssertionError("content must not run after graph NO_DATA")

    content = Content()
    engine = DecisionEngine(Predictor(), graph_adapter=adapter([]),
                            content_adapter=content)
    result = engine.run("Tìm công ty con FPT rồi xem lợi nhuận của chúng năm 2025")
    assert result.decision.route == "BOTH"
    assert result.status == "NO_DATA"
    assert len(result.adapter_results) == 1
    assert content.calls == []


def test_live_mode_without_graph_never_falls_back_to_fixture(monkeypatch):
    from src.api.routers import hybrid_router

    class Predictor:
        model_version = "fixture"
        threshold = 0.65

        def predict(self, question):
            return 0.9, 0.1

    monkeypatch.setattr(hybrid_router, "ArtifactPredictor", Predictor)
    monkeypatch.setattr(hybrid_router, "_build_live_graph_adapter", lambda loop: None)
    monkeypatch.setattr(hybrid_router, "_build_live_content_adapter", lambda loop: None)
    engine = hybrid_router._get_live_engine(None)
    result = engine.run("FPT có công ty con nào năm 2025?")
    assert result.status == "SYSTEM_UNAVAILABLE"
    assert result.adapter_results[0].reason_code == "GRAPH_NOT_READY"
    assert result.adapter_results[0].provenance == "LIVE/GRAPH"
    assert not result.adapter_results[0].data
    assert not result.adapter_results[0].evidence
