"""End-to-end test and live-execution endpoints backed by the hybrid router."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from functools import lru_cache

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

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
from ...retrieval_orchestration.hybrid_router.vector_adapter import VectorRAGAdapter
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
    source_type: Literal['BCTN','BCTC','NEWS','COMPANY_PROFILE'] | None = None
    corpus_version_id: str | None = None
    index_version_id: str | None = None


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


def _build_live_content_adapter(event_loop) -> VectorRAGAdapter | None:
    """Bind WBS10 to the research chat's corpus-pinned retriever and cache."""
    try:
        from ...core.config import get_settings
        settings = get_settings()
        index_id = settings.hybrid_router_index_id
        if not settings.research_corpus_version_id:
            logger.warning("Pinned corpus not set; Vector adapter unavailable")
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
            / f"corpus-{corpus_version_id}.json"
        )
        # Share the existing BM25/retrieval instance; do not load a new index per request.
        from .research_chat import get_store
        research=get_store().engine
        retriever=(research.retriever._hybrid_instance() if research is not None
                   and research.retriever.corpus_version_id==corpus_version_id else
                   HybridRetriever(pool, embedder, corpus_version_id=corpus_version_id))

        async def search_fn(question: str, *,company, period, doc_type,top_k: int):
            active_index=await pool.fetchval('SELECT index_version_id::text FROM corpus_versions WHERE corpus_version_id=$1::uuid',corpus_version_id)
            if not active_index or index_id and active_index!=index_id:
                from ...vector_retrieval.backend import RetrievalError
                raise RetrievalError('VECTOR_VERSION_MISMATCH')
            return await retriever.search(
                question, active_index, str(cache_path),
                company=company, period=period,doc_type=doc_type,exact_period=doc_type=='FINANCIAL_STATEMENT' and bool(period),
                top_k=top_k, candidates=max(top_k * 5, 50),
            )

        adapter=VectorRAGAdapter(search_fn,event_loop,corpus_version_id=corpus_version_id,top_k=5)
        async def warmup():
            active_index=await pool.fetchval('SELECT index_version_id::text FROM corpus_versions WHERE corpus_version_id=$1::uuid',corpus_version_id)
            if not active_index or index_id and active_index!=index_id:
                from ...vector_retrieval.backend import RetrievalError
                raise RetrievalError('VECTOR_VERSION_MISMATCH')
            await asyncio.to_thread(embedder.embed_query,'Khởi tạo truy xuất Vector RAG')
            return await retriever.prepare_cache(active_index,cache_path)
        adapter.warmup=warmup
        return adapter
    except Exception as exc:
        logger.warning("Vector adapter init failed (%s)", type(exc).__name__)
        return None


def _registry_tickers() -> dict[str, str]:
    """Ticker -> company entity ID; a ticker claimed by two entities is left out."""
    default = Path(__file__).resolve().parents[2] / "sprint4_runtime" / "company.registry.json"
    rows = json.loads(Path(os.environ.get("SPRINT4_COMPANY_REGISTRY", default)).read_text("utf-8"))
    owners: dict[str, set[str]] = {}
    for row in rows:
        for ticker in row.get("ticker_aliases") or []:
            owners.setdefault(ticker.upper(), set()).add(row["entity_id"])
    return {t: ids.pop() for t, ids in owners.items() if len(ids) == 1}


def _build_live_graph_adapter() -> LiveGraphAdapter | None:
    """Build a LiveGraphAdapter connecting to Neo4j."""
    try:
        from ...graph.graph_store import GraphStore
        store = GraphStore.from_environment()
        # WBS09: comma-separated READY graph versions to answer relationship questions.
        versions = [v.strip() for v in os.environ.get("SPRINT4_GRAPH_VERSIONS", "").split(",") if v.strip()]
        if not versions:
            return LiveGraphAdapter(store)
        from ...graph.relation_retrieval import RelationRetrieval
        return LiveGraphAdapter(store, RelationRetrieval(store.driver, database=store.database),
                                versions, _registry_tickers())
    except Exception as exc:
        logger.warning("LiveGraphAdapter init failed (Neo4j may be unavailable): %s", exc)
        return None


def _get_live_engine(event_loop) -> DecisionEngine:
    """Build a DecisionEngine with real adapters where available."""
    predictor = ArtifactPredictor()
    engine = DecisionEngine(predictor, threshold=predictor.threshold)

    content = _build_live_content_adapter(event_loop)

    if content is not None:
        engine.content_adapter = content
        logger.info("Hybrid router: LiveContentAdapter activated")
    else:
        engine.content_adapter = UnavailableAdapter("CONTENT", "CONTENT_NOT_READY")
        logger.warning("Hybrid router: LiveContentAdapter unavailable")

    # VECTOR must not even open a Neo4j connection. Create it only for a GRAPH task.
    engine.graph_adapter = _LazyGraphAdapter()

    return engine


class _LazyGraphAdapter:
    def __init__(self):self.calls=[]

    def execute(self,task,*,dependency=None):
        self.calls.append(dict(task_id=task.id,operation=task.operation))
        adapter=_build_live_graph_adapter()
        if adapter is None:return UnavailableAdapter('GRAPH','GRAPH_NOT_READY').execute(task,dependency=dependency)
        try:return adapter.execute(task,dependency=dependency)
        finally:
            store=getattr(adapter,'_store',None)
            driver=getattr(store,'driver',None)
            if driver is not None:driver.close()


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
            source_type=payload.context.source_type,corpus_version_id=payload.context.corpus_version_id,index_version_id=payload.context.index_version_id,
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
            source_type=payload.context.source_type,corpus_version_id=payload.context.corpus_version_id,index_version_id=payload.context.index_version_id,
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
                "evidence_pack": ar.evidence_pack,
            }
            for ar in result.adapter_results
        ],
    }
