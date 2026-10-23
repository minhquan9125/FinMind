"""Vector search endpoint (FR07/FR08-style structured retrieval branch,
scoped down to the Vector RAG baseline for this module: no graph branch,
no fusion/reranking - that is introduced later, in the Hybrid Graph-Vector
Retrieval module per Section 12.3)."""

import json
import logging
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from ...core.config import Settings, get_settings
from ...core.db import get_pool
from ...documents import repository
from ...documents.chunk_reconstruction import ReconstructionError
from ...documents.embeddings import EmbeddingService, get_embedding_service
from ...documents.price_queries import PriceQueryError, query_price
from ...documents.schemas import (
    FilteredSearchRequest,
    FilteredSearchResponse,
    FilteredSearchResultOut,
    PriceQueryRequest,
    PriceQueryResponse,
    SearchRequest,
    SearchResponse,
    SearchResultOut,
)
from ...documents.text_analysis import tokenize
from ...documents.retrieval_trace import write_retrieval_trace

router = APIRouter(prefix="/api/search", tags=["search"])

# Keep the existing direct-index trial alongside frozen-corpus selection.
V2_TRIAL_INDEX_ID = "434ef5e0-6516-578d-8d18-721d21347e01"


@router.post("/price", response_model=PriceQueryResponse)
async def price_search(payload: PriceQueryRequest) -> PriceQueryResponse:
    """Read exact price rows or calculate over them using fixed, read-only SQL."""
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question must not be empty.")
    try:
        result = await query_price(
            get_pool(), question, payload.company_symbol, payload.period,
        )
    except PriceQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PriceQueryResponse(**result)


@router.post("/filtered", response_model=FilteredSearchResponse)
async def filtered_search(
    payload: FilteredSearchRequest,
    settings: Settings = Depends(get_settings),
    embedder: EmbeddingService = Depends(get_embedding_service),
) -> FilteredSearchResponse:
    """Search one pinned database index with optional company/period/type filters."""
    trace_id = str(uuid.uuid4())
    started = time.perf_counter()
    index_version_id = None
    embedding_ms = None
    retrieval_ms = None
    rows = None
    ranked_hits = None
    status = "error"
    error_code = None
    stage = "validation"
    try:
        query = payload.query.strip()
        if not query:
            error_code = "INVALID_QUERY"
            raise HTTPException(status_code=400, detail="Query must not be empty.")
        if payload.corpus_version_id and payload.index_version_id:
            error_code = "INVALID_SCOPE"
            raise HTTPException(status_code=400, detail="Choose corpus_version_id or index_version_id, not both.")
        if payload.preview_source_changed and not payload.corpus_version_id:
            error_code = "INVALID_SCOPE"
            raise HTTPException(status_code=400, detail="Preview requires corpus_version_id.")

        default_index_id = repository.index_for_document(
            {"file_type": "DB"}, settings.chunk_words,
            settings.chunk_words - settings.chunk_stride, settings.embedding_model_ref,
        )
        if payload.corpus_version_id:
            stage = "corpus_lookup"
            pool = get_pool()
            corpus = await repository.get_corpus_index(pool, payload.corpus_version_id)
            if corpus is None:
                error_code = "CORPUS_NOT_FOUND"
                raise HTTPException(status_code=404, detail="Corpus version not found.")
            if corpus["corpus_status"] != "FROZEN" or corpus["index_status"] != "ACTIVE":
                error_code = "CORPUS_NOT_READY"
                raise HTTPException(status_code=409, detail="Corpus or its index is not ready for search.")
            if corpus["embedding_model"] != settings.embedding_model_ref:
                error_code = "MODEL_MISMATCH"
                raise HTTPException(status_code=409, detail="Corpus embedding model differs from the configured model.")
            index_version_id = corpus["index_version_id"]
        else:
            index_version_id = payload.index_version_id or default_index_id
            if index_version_id not in {default_index_id, V2_TRIAL_INDEX_ID}:
                error_code = "UNSUPPORTED_INDEX"
                raise HTTPException(status_code=400, detail="Unsupported index_version_id.")
            pool = get_pool()

        stage = "embedding"
        step_started = time.perf_counter()
        try:
            query_embedding = embedder.embed_query(query)
        finally:
            embedding_ms = round((time.perf_counter() - step_started) * 1000, 3)

        corpus_scope = ({"corpus_version_id": payload.corpus_version_id}
                        if payload.corpus_version_id else {})
        preview_scope = ({"preview_source_changed": True}
                         if payload.preview_source_changed else {})
        stage = "retrieval"
        step_started = time.perf_counter()
        def remember_ranked(hits):
            nonlocal ranked_hits
            ranked_hits = hits

        try:
            rows = await repository.vector_search_filtered(
                pool, index_version_id, query_embedding, payload.top_k,
                company_symbol=payload.company_symbol, period=payload.period,
                doc_type=payload.doc_type, on_ranked=remember_ranked,
                **corpus_scope, **preview_scope,
            )
            if ranked_hits is None:
                ranked_hits = [{"chunk_id": row["chunk_id"], "score": row["score"]}
                               for row in rows]
        finally:
            retrieval_ms = round((time.perf_counter() - step_started) * 1000, 3)

        stage = "response"
        results = [
            FilteredSearchResultOut(
                chunk_id=row["chunk_id"], document_id=row["document_id"],
                chunk_index=row["chunk_index"], title=row["title"],
                doc_type=row["doc_type"], company_symbol=row["company_symbol"],
                period=row["period"],
                locator=(json.loads(row["locator_json"])
                         if isinstance(row["locator_json"], str) else row["locator_json"]),
                text=row["text"], score=float(row["score"]),
                source_verified=row.get("source_verified", True),
                source_warning=row.get("source_warning"),
            )
            for row in rows
        ]
        status = "success" if results else "empty"
        return FilteredSearchResponse(index_version_id=index_version_id,
                                      corpus_version_id=payload.corpus_version_id,
                                      results=results)
    except Exception as exc:
        if isinstance(exc, ReconstructionError):
            error_code = exc.code
        elif error_code is None:
            error_code = {"embedding": "EMBEDDING_ERROR",
                          "corpus_lookup": "CORPUS_LOOKUP_ERROR",
                          "retrieval": "RETRIEVAL_ERROR"}.get(stage, "REQUEST_ERROR")
        raise
    finally:
        try:
            write_retrieval_trace({
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": status,
                "index_version_id": index_version_id,
                "corpus_version_id": str(payload.corpus_version_id) if payload.corpus_version_id else None,
                "company_symbol": payload.company_symbol,
                "period": payload.period,
                "doc_type": payload.doc_type,
                "top_k": payload.top_k,
                "preview_source_changed": payload.preview_source_changed,
                "embedding_ms": embedding_ms,
                "retrieval_ms": retrieval_ms,
                "total_ms": round((time.perf_counter() - started) * 1000, 3),
                "rows": rows,
                "ranked_hits": ranked_hits,
                "error_code": error_code,
            })
        except Exception:
            logging.getLogger("uvicorn.error").warning("retrieval_trace_unavailable")


@router.post("", response_model=SearchResponse)
async def search(
    payload: SearchRequest,
    settings: Settings = Depends(get_settings),
    embedder: EmbeddingService = Depends(get_embedding_service),
) -> SearchResponse:
    pool = get_pool()
    document = await repository.get_document(pool, payload.document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query must not be empty.")

    top_k = payload.top_k or settings.default_top_k
    query_embedding = embedder.embed_query(query)
    index_version_id = repository.index_for_document(
        document,
        settings.chunk_words,
        settings.chunk_words - settings.chunk_stride,
        settings.embedding_model_ref,
    )
    rows = await repository.vector_search(
        pool, payload.document_id, index_version_id, query_embedding, top_k
    )

    matched_terms = tokenize(query)
    results = [
        SearchResultOut(
            chunk_index=row["chunk_index"],
            page=row["page"],
            text=row["text"],
            score=float(row["score"]),
            matched_terms=matched_terms,
        )
        for row in rows
    ]
    return SearchResponse(results=results)
