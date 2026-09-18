"""Vector search endpoint (FR07/FR08-style structured retrieval branch,
scoped down to the Vector RAG baseline for this module: no graph branch,
no fusion/reranking - that is introduced later, in the Hybrid Graph-Vector
Retrieval module per Section 12.3)."""

from fastapi import APIRouter, Depends, HTTPException

from .. import repository
from ..config import Settings, get_settings
from ..db import get_pool
from ..embeddings import EmbeddingService, get_embedding_service
from ..schemas import SearchRequest, SearchResponse, SearchResultOut
from ..text_analysis import tokenize

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
    rows = await repository.vector_search(pool, payload.document_id, query_embedding, top_k)

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
