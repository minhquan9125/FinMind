"""End-to-end test and live-execution endpoints backed by the hybrid router."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import unicodedata
from pathlib import Path
from functools import lru_cache

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ...retrieval_orchestration.hybrid_router.decision_engine import (
    ArtifactPredictor,
    DecisionEngine,
    SessionScope,
    _normalize as normalize_router_question,
)
from ...retrieval_orchestration.hybrid_router.adapters import (
    LiveContentAdapter,
    LiveGraphAdapter,
    MockContentAdapter,
    MockGraphAdapter,
    UnavailableAdapter,
)
from ...core.config import get_settings

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/api/hybrid-router", tags=["hybrid-router"])


class RouterContextPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    companies: list[str] = Field(default_factory=list)
    periods: list[str] = Field(default_factory=list)
    metric_code: str | None = None
    detected_industry: str | None = None
    entity_mentions: list[str] = Field(default_factory=list)


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


def _registry_tickers(company_names=None) -> dict[str, str]:
    """Map tickers to unique verified registry IDs, using exact DB names as backup."""
    default = Path(__file__).resolve().parents[2] / "sprint4_runtime" / "company.registry.json"
    configured = os.environ.get("SPRINT4_COMPANY_REGISTRY") or getattr(get_settings(), "sprint4_company_registry", "")
    rows = json.loads(Path(configured or default).read_text("utf-8"))
    owners: dict[str, set[str]] = {}
    names: dict[str, set[str]] = {}

    def norm(value):
        return " ".join(unicodedata.normalize("NFC", value).casefold().split())

    for row in rows:
        if not row.get("verified"):
            continue
        for ticker in row.get("ticker_aliases") or []:
            owners.setdefault(ticker.upper(), set()).add(row["entity_id"])
        for name in [row.get("canonical_name"), *(row.get("aliases") or [])]:
            if name:
                names.setdefault(norm(name), set()).add(row["entity_id"])
    for ticker, name in (company_names or {}).items():
        exact = names.get(norm(name), set())
        if len(exact) == 1:
            owners.setdefault(ticker.upper(), set()).update(exact)
    return {t: ids.pop() for t, ids in owners.items() if len(ids) == 1}


async def _company_names(pool):
    async with pool.acquire() as connection:
        async with connection.transaction(readonly=True):
            rows = await connection.fetch(
                "SELECT symbol, company_name FROM public.companies "
                "WHERE symbol IS NOT NULL AND company_name IS NOT NULL")
    return {row["symbol"]: row["company_name"] for row in rows}


async def _verify_graph_sources(paths, pool):
    """Replay all citations in one read-only PostgreSQL snapshot."""
    from ...graph_review.sources import PostgresSourceReader
    from ...retrieval_orchestration.hybrid_router.graph_source import verify_relation_paths

    async with pool.acquire() as connection:
        async with connection.transaction(readonly=True, isolation="repeatable_read"):
            return await verify_relation_paths(paths, PostgresSourceReader(connection))


def _build_live_graph_adapter(event_loop=None) -> LiveGraphAdapter | None:
    """Build a LiveGraphAdapter connecting to Neo4j."""
    store = None
    try:
        from ...graph.graph_store import GraphStore
        store = GraphStore.from_environment()
        # WBS09: comma-separated READY graph versions to answer relationship questions.
        configured = os.environ.get("SPRINT4_GRAPH_VERSIONS", getattr(get_settings(), "sprint4_graph_versions", ""))
        versions = [v.strip() for v in configured.split(",") if v.strip()]
        if not versions:
            return LiveGraphAdapter(store)
        from ...graph.relation_retrieval import RelationRetrieval
        from ...core.db import get_pool

        relations = RelationRetrieval(store.driver, database=store.database)
        if not relations.all_versions_ready(versions):
            logger.warning("Configured Sprint 4 graph version is missing or not READY")
            store.close()
            return None
        pool = get_pool()
        names_future = asyncio.run_coroutine_threadsafe(_company_names(pool), event_loop)
        try:
            names = names_future.result(timeout=15)
        except TimeoutError:
            names_future.cancel()
            raise

        def verify_sources(paths):
            future = asyncio.run_coroutine_threadsafe(_verify_graph_sources(paths, pool), event_loop)
            try:
                return future.result(timeout=30)
            except TimeoutError:
                future.cancel()
                raise

        return LiveGraphAdapter(store, relations,
                                versions, _registry_tickers(names), verify_sources=verify_sources)
    except Exception as exc:
        if store is not None:
            store.close()
        logger.warning("LiveGraphAdapter init failed (Neo4j may be unavailable): %s", exc)
        return None


def _get_live_engine(event_loop) -> DecisionEngine:
    """Build a DecisionEngine with real adapters where available."""
    predictor = ArtifactPredictor()
    engine = DecisionEngine(predictor, threshold=predictor.threshold)

    content = _build_live_content_adapter(event_loop)
    graph = _build_live_graph_adapter(event_loop)

    if content is not None:
        engine.content_adapter = content
        logger.info("Hybrid router: LiveContentAdapter activated")
    else:
        engine.content_adapter = UnavailableAdapter("CONTENT", "CONTENT_NOT_READY")
        logger.warning("Hybrid router: LiveContentAdapter unavailable")

    if graph is not None:
        engine.graph_adapter = graph
        logger.info("Hybrid router: LiveGraphAdapter activated")
    else:
        engine.graph_adapter = UnavailableAdapter("GRAPH", "GRAPH_NOT_READY")
        logger.warning("Hybrid router: LiveGraphAdapter unavailable")

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
            detected_industry=payload.context.detected_industry,
            entity_mentions=tuple(payload.context.entity_mentions),
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
        "reason_code": decision.reason_code,
        "route_reason": decision.route_reason,
        "model_version": decision.model_version,
        "normalized_question": normalize_router_question(payload.question),
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
            detected_industry=payload.context.detected_industry,
            entity_mentions=tuple(payload.context.entity_mentions),
            confirmed=True,
        )

    if mode == "live":
        loop = asyncio.get_event_loop()
        engine = await asyncio.to_thread(_get_live_engine, loop)
    else:
        engine = get_router_engine()

    try:
        result = await asyncio.to_thread(engine.run, payload.question, context=context)
    finally:
        if mode == "live" and isinstance(getattr(engine, "graph_adapter", None), LiveGraphAdapter):
            await asyncio.to_thread(engine.graph_adapter._store.close)

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
                "data": list(ar.data),
                "evidence": list(ar.evidence),
            }
            for ar in result.adapter_results
        ],
    }
