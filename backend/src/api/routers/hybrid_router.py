"""End-to-end test and live-execution endpoints backed by the hybrid router."""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ...retrieval_orchestration.hybrid_router.decision_engine import (
    ArtifactPredictor,
    DecisionEngine,
    SessionScope,
)
from ...retrieval_orchestration.hybrid_router.adapters import (
    LiveContentAdapter,
    LiveGraphAdapter,
    MockContentAdapter,
    MockGraphAdapter,
)
from ...core.config import get_settings

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/api/hybrid-router", tags=["hybrid-router"])


class RouterContextPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    companies: list[str] = Field(default_factory=list)
    periods: list[str] = Field(default_factory=list)
    metric_code: str | None = None


class RouterTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=1)
    context: RouterContextPayload | None = None


@lru_cache(maxsize=1)
def get_router_engine() -> DecisionEngine:
    predictor = ArtifactPredictor()
    return DecisionEngine(predictor, threshold=predictor.threshold)


def warmup_router() -> None:
    """Exercise the complete shared embedding and classifier path at startup."""
    engine = get_router_engine()
    engine.predictor.predict("Tổng tài sản FPT năm 2025?")


def _build_live_content_adapter(event_loop) -> LiveContentAdapter | None:
    """Build a LiveContentAdapter using the research chat's retriever pool."""
    try:
        from ...core.config import get_settings
        settings = get_settings()
        index_id = settings.hybrid_router_index_id
        if not index_id:
            logger.warning("hybrid_router_index_id not set; LiveContentAdapter unavailable")
            return None

        from ...vector_retrieval.backend import HybridRetriever
        from ...documents.embeddings import get_embedding_service
        from ...core.db import get_pool
        from pathlib import Path

        pool = get_pool()
        embedder = get_embedding_service()
        corpus_version_id = settings.research_corpus_version_id or None
        cache_path = (
            Path(__file__).resolve().parents[3]
            / "src/vector_retrieval/.cache"
            / f"{index_id}.json"
        )
        retriever = HybridRetriever(
            pool, embedder, corpus_version_id=corpus_version_id
        )

        async def search_fn(question: str, company, period, top_k: int):
            return await retriever.search(
                question, index_id, str(cache_path),
                company=company, period=period,
                top_k=top_k, candidates=max(top_k * 5, 50),
            )

        return LiveContentAdapter(search_fn, event_loop, top_k=5)
    except Exception as exc:
        logger.warning("LiveContentAdapter init failed: %s", exc)
        return None


def _build_live_graph_adapter() -> LiveGraphAdapter | None:
    """Build a LiveGraphAdapter connecting to Neo4j."""
    try:
        from ...graph.graph_store import GraphStore
        store = GraphStore.from_environment()
        return LiveGraphAdapter(store)
    except Exception as exc:
        logger.warning("LiveGraphAdapter init failed (Neo4j may be unavailable): %s", exc)
        return None


def _get_live_engine(event_loop) -> DecisionEngine:
    """Build a DecisionEngine with real adapters where available."""
    predictor = ArtifactPredictor()
    engine = DecisionEngine(predictor, threshold=predictor.threshold)

    content = _build_live_content_adapter(event_loop)
    graph = _build_live_graph_adapter()

    if content is not None:
        engine.content_adapter = content
        logger.info("Hybrid router: LiveContentAdapter activated")
    else:
        logger.warning("Hybrid router: LiveContentAdapter unavailable, using mock")

    if graph is not None:
        engine.graph_adapter = graph
        logger.info("Hybrid router: LiveGraphAdapter activated")
    else:
        logger.warning("Hybrid router: LiveGraphAdapter unavailable, using mock")

    return engine


@router.post("/test")
async def test_router(payload: RouterTestRequest) -> dict:
    """Return routing decision without executing adapters (mode-independent)."""
    context = None
    if payload.context is not None:
        context = SessionScope(
            companies=tuple(payload.context.companies),
            periods=tuple(payload.context.periods),
            metric_code=payload.context.metric_code,
            confirmed=True,
        )
    decision = await asyncio.to_thread(
        get_router_engine().decide, payload.question, context=context
    )
    return {
        "decision": decision.decision,
        "route": decision.route,
        "scope": decision.scope.model_dump(),
        "clarification_question": decision.clarification_question,
    }


@router.post("/run")
async def run_router(payload: RouterTestRequest) -> dict:
    """Execute routing decision AND run adapters (respects hybrid_router_mode)."""
    settings = get_settings()
    mode = settings.hybrid_router_mode

    context = None
    if payload.context is not None:
        context = SessionScope(
            companies=tuple(payload.context.companies),
            periods=tuple(payload.context.periods),
            metric_code=payload.context.metric_code,
            confirmed=True,
        )

    if mode == "live":
        loop = asyncio.get_event_loop()
        engine = await asyncio.to_thread(_get_live_engine, loop)
    else:
        engine = get_router_engine()

    result = await asyncio.to_thread(engine.run, payload.question, context=context)

    return {
        "decision": result.decision.decision,
        "route": result.decision.route,
        "scope": result.decision.scope.model_dump(),
        "status": result.status,
        "reason_code": result.reason_code,
        "execution_mode": result.execution_mode,
        "adapter_results": [
            {
                "task_id": ar.task_id,
                "adapter": ar.adapter,
                "status": ar.status,
                "reason_code": ar.reason_code,
                "provenance": ar.provenance,
                "evidence_count": len(ar.evidence),
                "data_count": len(ar.data),
            }
            for ar in result.adapter_results
        ],
    }
