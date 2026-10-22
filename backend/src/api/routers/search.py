"""Vector search endpoint (FR07/FR08-style structured retrieval branch,
scoped down to the Vector RAG baseline for this module: no graph branch,
no fusion/reranking - that is introduced later, in the Hybrid Graph-Vector
Retrieval module per Section 12.3)."""

import json

from fastapi import APIRouter, Depends, HTTPException

from ...core.config import Settings, get_settings
from ...core.db import get_pool
from ...documents import repository
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

router = APIRouter(prefix="/api/search", tags=["search"])


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
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query must not be empty.")

    index_version_id = repository.index_for_document(
        {"file_type": "DB"},
        settings.chunk_words,
        settings.chunk_words - settings.chunk_stride,
        settings.embedding_model_ref,
    )
    query_embedding = embedder.embed_query(query)
    rows = await repository.vector_search_filtered(
        get_pool(),
        index_version_id,
        query_embedding,
        payload.top_k,
        company_symbol=payload.company_symbol,
        period=payload.period,
        doc_type=payload.doc_type,
    )
    results = [
        FilteredSearchResultOut(
            chunk_id=row["chunk_id"],
            document_id=row["document_id"],
            chunk_index=row["chunk_index"],
            title=row["title"],
            doc_type=row["doc_type"],
            company_symbol=row["company_symbol"],
            period=row["period"],
            locator=(json.loads(row["locator_json"])
                     if isinstance(row["locator_json"], str) else row["locator_json"]),
            text=row["text"],
            score=float(row["score"]),
        )
        for row in rows
    ]
    return FilteredSearchResponse(index_version_id=index_version_id, results=results)


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
