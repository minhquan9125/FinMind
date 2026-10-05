"""Vector search endpoint (FR07/FR08-style structured retrieval branch,
scoped down to the Vector RAG baseline for this module: no graph branch,
no fusion/reranking - that is introduced later, in the Hybrid Graph-Vector
Retrieval module per Section 12.3)."""

from fastapi import APIRouter, Depends, HTTPException

from ...core.config import Settings, get_settings
from ...core.db import get_pool
from ...documents import repository
from ...documents.embeddings import EmbeddingService, get_embedding_service
from ...documents.schemas import SearchRequest, SearchResponse, SearchResultOut
from ...documents.text_analysis import tokenize

router = APIRouter(prefix="/api/search", tags=["search"])


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
    index_version_id = repository.index_version_id_for(
        settings.chunk_words,
        settings.chunk_words - settings.chunk_stride,
        settings.embedding_model,
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
