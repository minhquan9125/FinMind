"""Bước 12: unit tests for LiveContentAdapter and LiveGraphAdapter.

All tests run offline: no real DB, no Neo4j, no network.
Mock the underlying async search function and GraphStore.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.retrieval_orchestration.hybrid_router.adapters import (
    AdapterResult,
    LiveContentAdapter,
    LiveGraphAdapter,
)
from src.retrieval_orchestration.hybrid_router.schemas import RouterTask


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _task(adapter="CONTENT", operation="find_metric", **params) -> RouterTask:
    return RouterTask(id="t1", adapter=adapter, operation=operation, params=params)


def _graph_task(operation="find_observations", **params) -> RouterTask:
    return RouterTask(id="g1", adapter="GRAPH", operation=operation, params=params)


def _make_loop():
    """Return a running event loop in a background thread."""
    import threading
    loop = asyncio.new_event_loop()

    def run():
        loop.run_forever()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return loop


# ---------------------------------------------------------------------------
# LiveContentAdapter tests
# ---------------------------------------------------------------------------

class TestLiveContentAdapter:

    def _adapter(self, search_result=None, raise_exc=None):
        loop = _make_loop()

        async def search_fn(question, company, period, top_k):
            if raise_exc:
                raise raise_exc
            return search_result or {"results": []}

        return LiveContentAdapter(search_fn, loop, top_k=5)

    def test_ok_result_maps_to_live_provenance(self):
        adapter = self._adapter(search_result={
            "index_version_id": "idx-001",
            "results": [
                {
                    "chunk_id": "c1", "document_id": "d1", "title": "BCCT FPT 2025",
                    "text": "Tổng tài sản 100 tỷ", "rrf_score": 0.9,
                    "content_hash": "abc123", "locator": {}, "period": "2025",
                }
            ],
        })
        task = _task(companies=["FPT"], periods=["2025"], metric_code="TOTAL_ASSETS",
                     question="Tổng tài sản FPT năm 2025?")
        result = adapter.execute(task)
        assert result.status == "OK"
        assert result.provenance == "LIVE/VECTOR"
        assert len(result.evidence) == 1
        assert result.evidence[0]["source_verified"] is True

    def test_empty_results_returns_no_data(self):
        adapter = self._adapter(search_result={"results": []})
        result = adapter.execute(_task(companies=["FPT"], periods=["2025"]))
        assert result.status == "NO_DATA"
        assert result.provenance == "LIVE/VECTOR"

    def test_timeout_returns_system_unavailable(self):
        loop = _make_loop()
        import asyncio as _asyncio

        async def slow_search(q, c, p, top_k):
            await _asyncio.sleep(999)
            return {"results": []}

        adapter = LiveContentAdapter(slow_search, loop, top_k=5)
        adapter.TIMEOUT_SECONDS = 0.05  # override for test speed
        result = adapter.execute(_task(companies=["FPT"], periods=["2025"]))
        assert result.status == "SYSTEM_UNAVAILABLE"
        assert result.reason_code == "CONTENT_TIMEOUT"
        assert result.provenance == "LIVE/VECTOR"

    def test_retrieval_error_code_maps_to_system_unavailable(self):
        from src.vector_retrieval.backend import RetrievalError
        adapter = self._adapter(raise_exc=RetrievalError("CACHE_BUILD_REQUIRED"))
        result = adapter.execute(_task(companies=["FPT"], periods=["2025"]))
        assert result.status == "SYSTEM_UNAVAILABLE"
        assert "CACHE_BUILD_REQUIRED" in result.reason_code
        assert result.provenance == "LIVE/VECTOR"

    def test_hash_mismatch_maps_to_insufficient_evidence(self):
        from src.vector_retrieval.backend import RetrievalError
        adapter = self._adapter(raise_exc=RetrievalError("HASH_MISMATCH"))
        result = adapter.execute(_task(companies=["FPT"], periods=["2025"]))
        assert result.status == "INSUFFICIENT_EVIDENCE"
        assert result.provenance == "LIVE/VECTOR"

    def test_calls_logged(self):
        adapter = self._adapter(search_result={"results": []})
        adapter.execute(_task(companies=["FPT"], periods=["2025"]))
        assert len(adapter.calls) == 1
        assert adapter.calls[0]["task_id"] == "t1"

    def test_only_accepts_content_adapter_type(self):
        adapter = self._adapter()
        task = RouterTask(id="g1", adapter="GRAPH", operation="find_relationships", params={})
        with pytest.raises(ValueError):
            adapter.execute(task)

    def test_dependency_companies_used(self):
        """When a dependency has data, company list comes from dependency rows."""
        dep = AdapterResult(
            "g1", "GRAPH", "OK", "MOCK_OK",
            data=({"company_id": "CMG"}, {"company_id": "ELC"}),
        )
        captured = []

        async def search_fn(q, company, period, top_k):
            captured.append(company)
            return {"results": []}

        loop = _make_loop()
        adapter = LiveContentAdapter(search_fn, loop, top_k=5)
        adapter.execute(_task(companies=["FPT"]), dependency=dep)
        # With 2 companies from dep, company=None (can't filter to one)
        assert captured[0] is None


# ---------------------------------------------------------------------------
# LiveGraphAdapter tests
# ---------------------------------------------------------------------------

class TestLiveGraphAdapter:

    def _adapter(self, observations=None, raise_exc=None):
        store = MagicMock()
        if raise_exc:
            store.get_observations.side_effect = raise_exc
        else:
            store.get_observations.return_value = observations or []
        return LiveGraphAdapter(store)

    def test_relationship_ops_return_system_unavailable(self):
        adapter = self._adapter()
        for op in ["find_relationships", "resolve_event_entities", "expand_market_context"]:
            task = _graph_task(operation=op, companies=["FPT"], periods=["2025"])
            result = adapter.execute(task)
            assert result.status == "SYSTEM_UNAVAILABLE"
            assert result.reason_code == "GRAPH_RELATIONSHIPS_NOT_INDEXED"
            assert result.provenance == "LIVE/GRAPH"

    def test_observations_ok(self):
        obs = [
            {"code": "totalAssets", "value": 100.0, "basis": "YEAR",
             "dataset_id": "FPT:v1", "dataset_version": "v1",
             "checksum": "abc", "json_pointer": "/0", "source_file": "fpt.json"},
        ]
        adapter = self._adapter(observations=obs)
        task = _graph_task(operation="find_observations",
                           companies=["FPT"], periods=["2025"], metric_code="totalAssets")
        result = adapter.execute(task)
        assert result.status == "OK"
        assert result.provenance == "LIVE/GRAPH"
        assert len(result.data) == 1
        assert result.data[0]["symbol"] == "FPT"
        assert result.data[0]["period"] == "2025-YEAR"
        assert len(result.evidence) == 1
        assert result.evidence[0]["source_verified"] is True

    def test_no_observations_returns_no_data(self):
        adapter = self._adapter(observations=[])
        task = _graph_task(operation="find_observations",
                           companies=["FPT"], periods=["2025"])
        result = adapter.execute(task)
        assert result.status == "NO_DATA"
        assert result.reason_code == "GRAPH_NO_OBSERVATIONS"
        assert result.provenance == "LIVE/GRAPH"

    def test_store_exception_returns_system_unavailable(self):
        adapter = self._adapter(raise_exc=RuntimeError("Neo4j down"))
        task = _graph_task(operation="find_observations",
                           companies=["FPT"], periods=["2025"])
        result = adapter.execute(task)
        assert result.status == "SYSTEM_UNAVAILABLE"
        assert result.provenance == "LIVE/GRAPH"

    def test_quarterly_period_converted_correctly(self):
        obs = [{"code": "revenue", "value": 50.0, "basis": "Q2",
                "dataset_id": "FPT:v1", "dataset_version": "v1",
                "checksum": "x", "json_pointer": "/0", "source_file": "f.json"}]
        adapter = self._adapter(observations=obs)
        task = _graph_task(operation="find_observations",
                           companies=["FPT"], periods=["2025-Q2"])
        result = adapter.execute(task)
        assert result.status == "OK"
        assert result.data[0]["period"] == "2025-Q2"

    def test_unsupported_period_format_returns_system_unavailable(self):
        adapter = self._adapter()
        task = _graph_task(operation="find_observations",
                           companies=["FPT"], periods=["CURRENT"])
        result = adapter.execute(task)
        assert result.status == "SYSTEM_UNAVAILABLE"
        assert result.reason_code == "GRAPH_UNSUPPORTED_PERIOD_FORMAT"

    def test_missing_scope_returns_system_unavailable(self):
        adapter = self._adapter()
        task = _graph_task(operation="find_observations", companies=[], periods=[])
        result = adapter.execute(task)
        assert result.status == "SYSTEM_UNAVAILABLE"
        assert result.reason_code == "GRAPH_MISSING_SCOPE"

    def test_calls_logged(self):
        adapter = self._adapter(observations=[])
        adapter.execute(_graph_task(operation="find_observations",
                                    companies=["VCB"], periods=["2024"]))
        assert len(adapter.calls) == 1
        assert adapter.calls[0]["task_id"] == "g1"

    def test_only_accepts_graph_adapter_type(self):
        adapter = self._adapter()
        task = RouterTask(id="v1", adapter="CONTENT", operation="find_metric", params={})
        with pytest.raises(ValueError):
            adapter.execute(task)


# ---------------------------------------------------------------------------
# ExecutionResult.execution_mode propagation
# ---------------------------------------------------------------------------

class TestExecutionModeInEngine:

    def _stub_predictor(self, scores=(0.1, 0.9)):
        from dataclasses import dataclass

        @dataclass
        class StubPredictor:
            scores: tuple
            model_version: str = "stub"
            def predict(self, q):
                return self.scores

        return StubPredictor(scores)

    def test_mock_adapters_give_mock_execution_mode(self):
        from src.retrieval_orchestration.hybrid_router.decision_engine import DecisionEngine
        engine = DecisionEngine(self._stub_predictor())
        result = engine.run("Tổng tài sản FPT năm 2025?")
        assert result.execution_mode == "MOCK"

    def test_live_content_adapter_gives_live_execution_mode(self):
        from src.retrieval_orchestration.hybrid_router.decision_engine import DecisionEngine

        loop = _make_loop()  # starts loop in background thread

        async def search_fn(q, c, p, top_k):
            return {"results": [
                {"chunk_id": "c1", "document_id": "d1", "title": "T",
                 "text": "some text", "rrf_score": 0.8, "content_hash": "hash1",
                 "locator": {}, "period": "2025"}
            ]}

        adapter = LiveContentAdapter(search_fn, loop, top_k=5)
        engine = DecisionEngine(self._stub_predictor())
        engine.content_adapter = adapter
        result = engine.run("Tổng tài sản FPT năm 2025?")
        assert result.execution_mode == "LIVE"
        loop.call_soon_threadsafe(loop.stop)
