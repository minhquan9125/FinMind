"""End-to-end test and live-execution endpoints backed by the hybrid router."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import unicodedata
from pathlib import Path
from functools import lru_cache
from typing import Literal
from dataclasses import replace
import re

from fastapi import APIRouter, HTTPException, Depends
from ...auth.authorization import bearer, current_principal, READ_ROLES
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


async def router_access(credentials=Depends(bearer)):
    settings = get_settings()
    if (getattr(settings, "hybrid_router_mode", "mock") == "mock"
            and not getattr(settings, "research_corpus_version_id", None)):
        return  # Pure synthetic fixtures access no private data.
    principal = await current_principal(credentials)
    if not principal.roles.intersection(READ_ROLES):
        raise HTTPException(status_code=403, detail="Insufficient role")
    return principal


class RouterContextTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company: str | None = None
    period: str | None = None
    reporting_entity: Literal["CONSOLIDATED", "PARENT"] | None = None
    reporting_entities: list[Literal["CONSOLIDATED", "PARENT"]] = Field(default_factory=list)
    measure_basis: str | None = None


class RouterContextPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    companies: list[str] = Field(default_factory=list)
    periods: list[str] = Field(default_factory=list)
    metric_code: str | None = None
    detected_industry: str | None = None
    entity_mentions: list[str] = Field(default_factory=list)
    topic: str | None = None
    source_type: str | None = None
    operation: str | None = None
    route_hint: Literal["VECTOR", "GRAPH", "BOTH"] | None = None
    reporting_entity: str | None = None
    reporting_entities: list[Literal["CONSOLIDATED", "PARENT"]] = Field(default_factory=list)
    targets: list[RouterContextTarget] = Field(default_factory=list)
    measure_basis: str | None = None
    person_name: str | None = None
    position_code: str | None = None
    event_type: str | None = None
    relation_types: list[str] = Field(default_factory=list)

    def to_session_scope(self) -> SessionScope:
        values = self.model_dump()
        values["targets"] = [target.model_dump(exclude_unset=True) for target in self.targets]
        for key in ("companies", "periods", "entity_mentions", "relation_types", "reporting_entities", "targets"):
            values[key] = tuple(values[key])
        return SessionScope(**values)


class RouterTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=1)
    context: RouterContextPayload | None = None


@lru_cache(maxsize=1)
def get_router_engine() -> DecisionEngine:
    predictor = ArtifactPredictor()
    return DecisionEngine(predictor, threshold=predictor.threshold)


async def _coverage_periods(task):
    """Read real indexed reporting periods from the configured frozen corpus."""
    from ...core.db import get_pool
    settings = get_settings()
    index_id = getattr(settings, "hybrid_router_index_id", None) or None
    corpus_id = getattr(settings, "research_corpus_version_id", None)
    if not corpus_id or not task.params.get("companies"):
        return []
    async with get_pool().acquire() as conn:
        async with conn.transaction(readonly=True, isolation="repeatable_read"):
            rows = await conn.fetch("""
                SELECT DISTINCT CASE WHEN d.doc_type='ANNUAL_REPORT'
                  THEN coalesce(p.period_code,t.locator_json->>'period_code',substring(d.title from '((19|20)[0-9]{2})$'))
                  ELSE coalesce(p.period_code,t.locator_json->>'period_code') END AS period
                FROM public.text_chunks t
                JOIN public.documents d USING(document_id)
                JOIN public.index_versions i USING(index_version_id)
                JOIN public.corpus_versions cv ON cv.index_version_id=i.index_version_id
                JOIN public.corpus_documents cd ON cd.corpus_version_id=cv.corpus_version_id
                  AND cd.document_id=d.document_id AND cd.document_hash=d.sha256
                LEFT JOIN public.companies c USING(company_id)
                LEFT JOIN public.reporting_periods p USING(period_id)
                WHERE ($1::uuid IS NULL OR i.index_version_id=$1::uuid) AND cv.corpus_version_id=$2::uuid
                  AND i.status='ACTIVE' AND cv.status='FROZEN' AND t.superseded_at IS NULL
                  AND coalesce(c.symbol,t.locator_json->>'symbol')=ANY($3::text[])
                  AND d.doc_type=ANY($4::text[])
            """, index_id, corpus_id, task.params["companies"],
                [task.params.get("doc_type") or ("ANNUAL_REPORT" if task.adapter == "GRAPH" else "FINANCIAL_STATEMENT")])
    periods = set()
    requested = (task.params.get("periods") or [""])[0]
    for row in rows:
        raw = row["period"] or ""
        raw = re.sub(r"-YEAR$", "", raw)
        if not re.fullmatch(r"\d{4}(?:-Q[1-4])?", raw):
            continue
        if requested.startswith("LATEST_YEAR-Q") and not raw.endswith(requested[-3:]):
            continue
        if requested not in {"LATEST_AVAILABLE_PERIOD", "LATEST_PUBLISHED_PERIOD"} and not requested.startswith("LATEST_YEAR-Q"):
            continue
        periods.add(raw)
    return [max(periods, key=lambda p: (int(p[:4]), int(p[-1]) if "-Q" in p else 4, "-Q" not in p))] if periods else []


def _with_coverage(engine, event_loop):
    settings = get_settings()
    if not getattr(settings, "research_corpus_version_id", None):
        return engine
    def resolve(task):
        future = asyncio.run_coroutine_threadsafe(_coverage_periods(task), event_loop)
        try:
            return future.result(timeout=15)
        except Exception:
            future.cancel()
            raise
    return replace(engine, period_resolver=resolve)


def warmup_router() -> None:
    """Exercise the complete shared embedding and classifier path at startup."""
    engine = get_router_engine()
    engine.predictor.predict("Tổng tài sản FPT năm 2025?")


@lru_cache(maxsize=1)
def _content_retriever(pool, embedder, corpus_version_id, index_id, cache_path):
    """Reuse one pool/scope-bound BM25 index across per-request router engines."""
    from ...vector_retrieval.backend import HybridRetriever
    retriever = HybridRetriever(pool, embedder, corpus_version_id=corpus_version_id)
    retriever.load_local_cache(index_id, cache_path)
    return retriever


def _build_live_content_adapter(event_loop) -> LiveContentAdapter | None:
    """Build a LiveContentAdapter using the research chat's retriever pool."""
    try:
        settings = get_settings()
        index_id = settings.hybrid_router_index_id
        if not index_id and settings.research_corpus_version_id:
            from ...core.db import get_pool
            async def corpus_index():
                async with get_pool().acquire() as conn:
                    return await conn.fetchval("""SELECT cv.index_version_id::text
                        FROM corpus_versions cv JOIN index_versions i USING(index_version_id)
                        WHERE cv.corpus_version_id=$1::uuid AND cv.status='FROZEN' AND i.status='ACTIVE'""",
                        settings.research_corpus_version_id)
            future = asyncio.run_coroutine_threadsafe(corpus_index(), event_loop)
            try:
                index_id = future.result(timeout=15)
            except Exception:
                future.cancel()
                raise
        if not index_id:
            logger.warning("hybrid_router_index_id not set; LiveContentAdapter unavailable")
            return None

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
        retriever = _content_retriever(pool, embedder, corpus_version_id, index_id, str(cache_path))

        async def search_fn(question: str, company, period, top_k: int):
            return await retriever.search(
                question, index_id, str(cache_path),
                company=company, period=period,
                top_k=top_k, candidates=max(top_k * 5, 50),
            )

        async def scope_search_fn(question, company, period, top_k, *, reporting_entity=None,
                                  measure_basis=None, doc_type=None):
            from ...b1_answering.evidence.live_contract import reporting_entity_matches
            result = await retriever.search(question, index_id, str(cache_path), company=company,
                period=period, doc_type=doc_type, top_k=20, candidates=200,
                exact_period=doc_type == "FINANCIAL_STATEMENT")
            matching = []
            for hit in result.get("results") or []:
                header = (hit.get("text") or "").split("\n", 1)[0]
                if reporting_entity and not reporting_entity_matches(header, reporting_entity):
                    continue
                norm = normalize_router_question(header)
                if measure_basis == "YTD" and not re.search(r"\b(?:luy ke|ytd)\b", norm):
                    continue
                if measure_basis == "STANDALONE_QUARTER" and (
                        not re.search(r"\b(?:rieng quy|quy rieng)\b", norm)
                        or re.search(r"\b(?:luy ke|ytd|(?:6|9|12) thang|khong|chua|co the|du kien)\b", norm)
                        or "?" in header):
                    continue
                matching.append(hit)
            return {**result, "results": matching[:top_k]}

        async def price_search_fn(question, company, period):
            from ...documents.price_queries import query_price, PriceQueryError
            from datetime import date
            try:
                day = date.fromisoformat(period)
            except (ValueError, TypeError):
                return {"sources": [], "data": {}}
            try:
                return await query_price(pool, f"Giá {company} ngày {day:%d/%m/%Y}", company, period)
            except PriceQueryError:
                return {"sources": [], "data": {}}

        return LiveContentAdapter(search_fn, event_loop, top_k=5,
                                  scope_search_fn=scope_search_fn, price_search_fn=price_search_fn)
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

    return _with_coverage(engine, event_loop)


@router.post("/test", dependencies=[Depends(router_access)])
async def test_router(payload: RouterTestRequest) -> dict:
    """Return routing decision without executing adapters (mode-independent)."""
    context = None
    if payload.context is not None:
        context = payload.context.to_session_scope()
    engine = _with_coverage(get_router_engine(), asyncio.get_running_loop())
    decision = await asyncio.to_thread(
        engine.decide, payload.question, context=context
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
        "tasks": [task.model_dump() for task in decision.tasks],
        "period_resolution_required": any(t.params.get("period_resolution_required") for t in decision.tasks),
    }


@router.post("/run", dependencies=[Depends(router_access)])
async def run_router(payload: RouterTestRequest) -> dict:
    """Execute routing decision AND run adapters (respects hybrid_router_mode)."""
    settings = get_settings()
    mode = settings.hybrid_router_mode

    context = None
    if payload.context is not None:
        context = payload.context.to_session_scope()

    if mode == "live":
        loop = asyncio.get_event_loop()
        engine = await asyncio.to_thread(_get_live_engine, loop)
    else:
        engine = _with_coverage(get_router_engine(), asyncio.get_running_loop())

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
