"""WBS14: route evidence must become persisted, source-bound chat content."""

from hashlib import sha256
from types import SimpleNamespace

import pytest

from src.retrieval_orchestration.routed_answer import (
    compose_routed_answer, reference_routed_answer, replay_pinned_source,
)


def execution(route, *, graph="OK", vector="OK", graph_quote="FPT dự kiến bổ nhiệm bà A làm Chủ tịch năm 2025."):
    branches = ["VECTOR"] if route == "VECTOR" else ["GRAPH"] if route == "GRAPH" else ["GRAPH", "VECTOR"]
    states = {branch: {"status": graph if branch == "GRAPH" else vector,
                       "reason_code": "OK" if (graph if branch == "GRAPH" else vector) == "OK" else "SOURCE_TIMEOUT"}
              for branch in branches}
    rows = []
    if "GRAPH" in branches and graph == "OK":
        rows.append({"evidence_id": "chunk:g", "branches": ["GRAPH"], "sources": [{
            "source_id": "rel:g", "branch": "GRAPH", "provenance": "LIVE/GRAPH",
            "document_id": "doc-g", "chunk_id": "g", "quote": graph_quote,
            "graph_version_id": "graph-ready", "source_verified": True}]})
    if "VECTOR" in branches and vector == "OK":
        rows.append({"evidence_id": "chunk:v", "branches": ["VECTOR"], "sources": [{
            "source_id": "v", "branch": "VECTOR", "provenance": "LIVE/VECTOR",
            "document_id": "doc-v", "chunk_id": "v", "source_verified": True,
            "company": "FPT", "period": "2025",
            "corpus_version_id": "corpus-frozen"}]})
    decision = SimpleNamespace(decision='SEARCH', route=route, scope=SimpleNamespace(model_dump=lambda: {
        "companies": ["FPT"], "periods": ["2025"]}),
        tasks=[SimpleNamespace(adapter="CONTENT", params={"company_scope_policy": "EXPLICIT_OR_RESOLVED"})]
        if "VECTOR" in branches else [])
    return SimpleNamespace(decision=decision, status="OK" if all(s["status"] == "OK" for s in states.values()) else "SYSTEM_UNAVAILABLE",
        reason_code="LIVE_EXECUTION_OK", execution_mode="LIVE",
        consolidation={"branch_states": states, "execution_trace": [{"branch": b, "executed": states[b]["status"] == "OK"} for b in branches],
                       "evidence": rows, "rejected_evidence": [], "alignment_warnings": []})


def replay(source):
    text = ("FPT dự kiến bổ nhiệm bà A làm Chủ tịch năm 2025." if source["branch"] == "GRAPH"
            else "Doanh thu FPT năm 2025: 100 đơn vị minh họa.")
    return {"document_id": source["document_id"], "chunk_id": source["chunk_id"],
            "corpus_version_id": "corpus-frozen", "chunk_text": text,
            "content_hash": sha256(text.encode()).hexdigest(),
            "source_sha256": "a" * 64, "title": "Nguồn minh họa",
            "locator": {"section": "Mục minh họa"}}


@pytest.mark.parametrize("route,count", [("VECTOR", 1), ("GRAPH", 1), ("BOTH", 2)])
def test_each_route_uses_replayed_source_with_claim_citation(route, count):
    result = compose_routed_answer(execution(route), replay, corpus_version_id="corpus-frozen")
    assert result["route"] == route
    assert result["answering"]["status"] == "DRAFT_READY"
    assert len(result["answering"]["claims"]) == count
    assert len(result["answering"]["citations"]) == count
    assert all(item["source_verified"] for item in result["evidence_pack"]["items"])
    assert result["answering"]["manifest"]["components"]["b3_evidence_gate"] is False
    assert result["answering"]["manifest"]["components"]["b3_answer_verification"] is False
    assert "dự kiến" in result["answering"]["draft"] if route != "VECTOR" else True


def test_both_branch_failure_reports_missing_and_never_claims_zero_or_absence():
    result = compose_routed_answer(execution("BOTH", graph="SYSTEM_UNAVAILABLE", vector="SKIPPED_DEPENDENCY"),
                                   replay, corpus_version_id="corpus-frozen")
    assert result["answering"]["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["answering"]["claims"] == []
    assert "GRAPH" in result["answering"]["message"]
    assert "VECTOR" in result["answering"]["message"]
    assert "bằng 0" not in result["answering"]["message"]


def test_mismatched_quote_cannot_be_cited():
    result = compose_routed_answer(execution("GRAPH", graph_quote="FPT đã bổ nhiệm bà A."),
                                   replay, corpus_version_id="corpus-frozen")
    assert result["answering"]["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["answering"]["citations"] == []


def test_mismatched_vector_index_is_not_cited():
    result = execution('VECTOR')
    result.consolidation['evidence'][0]['sources'][0]['index_version_id'] = 'index-a'
    def wrong_index(source):
        return {**replay(source), 'index_version_id': 'index-b'}
    answer = compose_routed_answer(result, wrong_index, corpus_version_id='corpus-frozen')
    assert answer['answering']['status'] == 'INSUFFICIENT_EVIDENCE'
    assert answer['routing']['rejected_evidence'][0]['reason_code'] == 'ANSWER_SOURCE_REPLAY_MISMATCH'


def test_source_followup_uses_saved_pack_and_does_not_replay():
    saved = compose_routed_answer(execution("BOTH"), replay, corpus_version_id="corpus-frozen")
    followup = reference_routed_answer(saved)
    assert followup["answering"]["manifest"]["response_mode"] == "SAVED_SOURCE_REFERENCE"
    assert followup["answering"]["citations"] == saved["answering"]["citations"]
    assert followup["evidence_pack"] == saved["evidence_pack"]


def test_tampered_saved_citation_is_not_reused():
    saved = compose_routed_answer(execution("GRAPH"), replay, corpus_version_id="corpus-frozen")
    saved["answering"]["citations"][0]["chunk_id"] = "another-chunk"
    followup = reference_routed_answer(saved)
    assert followup["answering"]["status"] == "INSUFFICIENT_EVIDENCE"
    assert followup["answering"]["citations"] == []


def test_tampered_saved_passage_is_not_reused():
    saved = compose_routed_answer(execution("GRAPH"), replay, corpus_version_id="corpus-frozen")
    saved["evidence_pack"]["items"][0]["passage"] = "Nội dung nguồn đã bị thay đổi."
    followup = reference_routed_answer(saved)
    assert followup["answering"]["status"] == "INSUFFICIENT_EVIDENCE"


def test_malformed_saved_passage_is_rejected_without_server_error():
    saved = compose_routed_answer(execution("GRAPH"), replay, corpus_version_id="corpus-frozen")
    saved["evidence_pack"]["items"][0]["passage"] = None
    assert reference_routed_answer(saved)["reason_code"] == "INVALID_SAVED_ROUTED_EVIDENCE"


def test_vector_extract_prefers_requested_metric_row_over_header():
    result = execution("VECTOR")
    result.decision.scope.model_dump = lambda: {"companies": ["FPT"], "periods": ["2025"],
                                                  "metric_code": "NET_REVENUE"}
    text = "FPT | năm 2025 | phạm vi hợp nhất\nTổng tài sản (TOTAL_ASSETS): 999\nDoanh thu thuần (NET_REVENUE): 100"
    def source(item):
        row = replay(item)
        return {**row, "chunk_text": text, "content_hash": sha256(text.encode()).hexdigest()}
    answer = compose_routed_answer(result, source, corpus_version_id="corpus-frozen")
    assert answer["answering"]["claims"][0]["text"] == "Doanh thu thuần (NET_REVENUE): 100"


def test_compare_does_not_claim_complete_when_one_company_is_missing():
    result = execution("BOTH")
    result.decision.scope.model_dump = lambda: {"companies": ["FPT", "TCB"], "periods": ["2025"]}
    answer = compose_routed_answer(result, replay, corpus_version_id="corpus-frozen")
    assert answer["answering"]["status"] == "INSUFFICIENT_EVIDENCE"
    assert "TCB" in answer["answering"]["message"]


@pytest.mark.parametrize('alias', [False, True])
def test_live_source_reader_pins_frozen_corpus_and_reconstructs(monkeypatch, alias):
    import asyncio
    from uuid import uuid4
    from src.documents import repository
    from src.documents.release_identity import release_document_id

    chunk_id, document_id, corpus_id = uuid4(), uuid4(), uuid4()
    index_id = uuid4()
    stored_id = release_document_id(index_id, document_id) if alias else str(document_id)
    text = 'Nguồn gốc xác nhận sự kiện.'
    seen = []

    class Context:
        async def __aenter__(self):
            return conn
        async def __aexit__(self, *_):
            return False

    class Connection:
        def transaction(self, **kwargs):
            assert kwargs['readonly'] is True
            return Context()
        async def fetchrow(self, query, *values):
            seen.append((query, values))
            return {'chunk_id': str(chunk_id), 'document_id': stored_id,
                    'content_hash': sha256(text.encode()).hexdigest(),
                    'source_sha256': 'a'*64, 'title': 'Báo cáo', 'doc_type': 'ANNUAL_REPORT',
                    'locator_json': {'section': 'Quản trị',
                                     'reconstruction': {'document_id': str(document_id)}},
                    'index_version_id': str(index_id)}

    class Pool:
        def acquire(self):
            return Context()

    async def reconstruct(_, rows):
        return [{**rows[0], 'text': text}]

    conn = Connection()
    monkeypatch.setattr(repository, 'resolve_result_rows', reconstruct)
    result = asyncio.run(replay_pinned_source(Pool(), {'chunk_id': str(chunk_id),
        'document_id': str(document_id)}, str(corpus_id)))
    assert result['chunk_text'] == text
    assert result['release_document_id'] == stored_id
    assert result['doc_type'] == 'ANNUAL_REPORT'
    assert 'cv.status=\'FROZEN\'' in seen[0][0]
    assert 'i.status=\'ACTIVE\'' in seen[0][0]
    assert 'cd.document_hash=d.sha256' in seen[0][0]
    assert seen[0][1] == (chunk_id, corpus_id)
