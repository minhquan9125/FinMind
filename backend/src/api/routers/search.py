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
    document = None
    if payload.document_id:
        document = await repository.get_document(pool, payload.document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found.")

    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query must not be empty.")

    top_k = payload.top_k or settings.default_top_k
    # Uploads retain their own index. A configured default applies to DB sources
    # and corpus-wide requests, never to an unrelated private upload.
    explicit_corpus = payload.corpus_version_id
    corpus_id = explicit_corpus or (settings.default_corpus_version_id
        if document is None or document.get('file_type') == 'DB' else None)
    scope = None
    if corpus_id:
        from ...documents.query_scope import financial_query_scope,financial_metric_codes
        symbols,period_codes=financial_query_scope(query)
        metric_codes=financial_metric_codes(query,symbols)
        query_embedding = embedder.embed_query(query)
        scope,rows = await repository.corpus_vector_search(pool,str(corpus_id),query_embedding,top_k,
            model=settings.embedding_model_ref,document_id=payload.document_id,
            expected_hash=settings.default_corpus_manifest_sha256 if not explicit_corpus else None,
            symbols=symbols,period_codes=period_codes,metric_codes=metric_codes)
        index_version_id=scope.index_version_id
    else:
        if document is None:
            raise HTTPException(status_code=400,detail='Choose corpus_version_id or document_id; no default corpus is active.')
        query_embedding = embedder.embed_query(query)
        index_version_id = repository.index_for_document(document,settings.chunk_words,
            settings.chunk_words-settings.chunk_stride,settings.embedding_model_ref)
        rows = await repository.vector_search(pool,payload.document_id,index_version_id,query_embedding,top_k)

    matched_terms = tokenize(query)
    results = [
        SearchResultOut(
            chunk_id=row.get('chunk_id'),document_id=row.get('document_id'),
            chunk_index=row["chunk_index"],
            page=row["page"],
            text=row["text"],
            score=float(row["score"]),
            matched_terms=matched_terms,
        )
        for row in rows
    ]
    return SearchResponse(results=results,corpus_version_id=scope.corpus_version_id if scope else None,
                          index_version_id=index_version_id)
