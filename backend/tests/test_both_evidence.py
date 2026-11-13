"""Acceptance checks for BOTH execution and branch-aware evidence merging."""

from types import SimpleNamespace

from src.retrieval_orchestration.hybrid_router.decision_engine import DecisionEngine
from src.retrieval_orchestration.hybrid_router.evidence import consolidate


class Predictor:
    model_version = "fixture"

    def predict(self, question):
        return 0.9, 0.9


def test_both_fixture_runs_both_branches_and_keeps_trace():
    engine = DecisionEngine(Predictor())
    result = engine.run("Doanh thu công ty con FPT năm 2025?", fixture_case="B01")
    merged = result.consolidation
    assert result.status == "OK"
    assert [row["branch"] for row in merged["execution_trace"]] == ["GRAPH", "VECTOR"]
    assert all(row["executed"] for row in merged["execution_trace"])
    assert {"GRAPH", "VECTOR"} == set(merged["branch_states"])
    assert {"GRAPH", "VECTOR"} == {b for row in merged["evidence"] for b in row["branches"]}
    assert engine.content_adapter.calls[0]["dependency_task_id"] == "g1"


def test_both_fixture_graph_empty_reports_vector_skipped():
    result = DecisionEngine(Predictor()).run("Doanh thu công ty con FPT năm 2025?", fixture_case="B02")
    assert result.consolidation["branch_states"]["GRAPH"]["status"] == "NO_DATA"
    assert result.consolidation["branch_states"]["VECTOR"]["status"] == "SKIPPED_DEPENDENCY"
    assert result.consolidation["execution_trace"][1]["executed"] is False


def test_consolidation_deduplicates_chunk_and_preserves_provenance_without_score_mixing():
    task = lambda ident, adapter: SimpleNamespace(id=ident, adapter=adapter, operation="search",
        depends_on=None, params={"companies": ["FPT"], "periods": ["2025"]})
    decision = SimpleNamespace(tasks=[task("g1", "GRAPH"), task("v1", "CONTENT")])
    result = lambda ident, adapter, provenance, evidence: SimpleNamespace(
        task_id=ident, adapter=adapter, status="OK", reason_code="OK", provenance=provenance,
        evidence=tuple(evidence))
    common = {"chunk_id": "c1", "source_verified": True, "document_version": "v1"}
    graph = result("g1", "GRAPH", "LIVE/GRAPH", [{**common, "source_id": "edge:c1"}])
    vector = result("v1", "CONTENT", "LIVE/VECTOR", [
        {**common, "source_id": "c1", "company": "FPT", "period": "2025", "cosine": 0.99},
        {"source_id": "c2", "company": "VCB", "period": "2025", "source_verified": True},
        {**common, "source_id": "c1-other", "document_version": "v2", "company": "FPT", "period": "2025"},
    ])
    merged = consolidate(decision, (graph, vector))
    assert len(merged["evidence"]) == 1
    assert merged["evidence"][0]["branches"] == ["GRAPH", "VECTOR"]
    assert len(merged["evidence"][0]["sources"]) == 2
    assert merged["evidence"][0]["rank_method"] == "RRF_BY_BRANCH_RANK_K60"
    assert {r["reason_code"] for r in merged["rejected_evidence"]} == {
        "EVIDENCE_OUT_OF_SCOPE", "EVIDENCE_VERSION_MISMATCH"}


def test_same_chunk_without_comparable_versions_is_not_merged_across_branches():
    task = lambda ident, adapter: SimpleNamespace(id=ident, adapter=adapter,
        operation="search", depends_on=None, params={"companies": ["FPT"], "periods": ["2025"]})
    decision = SimpleNamespace(tasks=[task("g1", "GRAPH"), task("v1", "CONTENT")])
    result = lambda ident, adapter, provenance, evidence: SimpleNamespace(
        task_id=ident, adapter=adapter, status="OK", reason_code="OK", provenance=provenance,
        evidence=(evidence,))
    graph = result("g1", "GRAPH", "LIVE/GRAPH",
                   {"source_id": "edge:c1", "chunk_id": "c1", "document_version": "extract-v1",
                    "source_verified": True})
    vector = result("v1", "CONTENT", "LIVE/VECTOR",
                    {"source_id": "c1", "chunk_id": "c1", "source_sha256": "source-v1",
                     "company": "FPT", "period": "2025", "source_verified": True})
    merged = consolidate(decision, (graph, vector))
    assert len(merged["evidence"]) == 2
    assert merged["alignment_warnings"][0]["reason_code"] == "CROSS_BRANCH_VERSION_UNVERIFIED"
