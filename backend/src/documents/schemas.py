"""Pydantic request/response models for the Vector RAG API."""

from pydantic import BaseModel, Field
from uuid import UUID


class DocumentOut(BaseModel):
    id: str
    filename: str
    page_count: int
    chunk_count: int
    vocab_size: int
    total_tokens: int


class TraceWordOut(BaseModel):
    word: str
    kept: bool
    reason: str | None = None


class ChunkDetailOut(BaseModel):
    index: int
    page: int | None
    text: str
    word_count: int
    token_count: int
    unique_count: int
    top_terms: list[tuple[str, float]]
    trace: list[TraceWordOut]


class VocabRowOut(BaseModel):
    token: str
    document_frequency: int
    total_frequency: int
    idf: float


class VocabResponse(BaseModel):
    vocab_size: int
    rows: list[VocabRowOut]
    truncated: bool


class SearchRequest(BaseModel):
    document_id: str
    query: str
    top_k: int | None = None


class SearchResultOut(BaseModel):
    chunk_index: int
    page: int | None
    text: str
    score: float
    matched_terms: list[str]


class SearchResponse(BaseModel):
    results: list[SearchResultOut]


class FilteredSearchRequest(BaseModel):
    """Search across stored database chunks with optional source-scope filters."""

    query: str = Field(min_length=1, max_length=4000)
    index_version_id: str | None = Field(
        default=None,
        description="Omit for the default v1 index; the pinned v2 index is available for read-only trials.",
    )
    corpus_version_id: UUID | None = Field(
        default=None,
        description="Frozen corpus to search; do not combine with index_version_id.",
    )
    company_symbol: str | None = Field(default=None, min_length=1, max_length=16)
    period: str | None = Field(default=None, min_length=1, max_length=32)
    doc_type: str | None = Field(default=None, min_length=1, max_length=40)
    top_k: int = Field(default=5, ge=1, le=20)
    preview_source_changed: bool = Field(
        default=False,
        description="Diagnostic only: show current source text when SOURCE_CHANGED; result is unverified.",
    )


class FilteredSearchResultOut(BaseModel):
    chunk_id: str
    document_id: str
    chunk_index: int
    title: str
    doc_type: str
    company_symbol: str | None = None
    period: str | None = None
    locator: dict
    text: str
    score: float
    source_verified: bool = True
    source_warning: str | None = None


class FilteredSearchResponse(BaseModel):
    index_version_id: str
    corpus_version_id: UUID | None = None
    results: list[FilteredSearchResultOut]


class PriceQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    company_symbol: str | None = Field(default=None, min_length=1, max_length=16)
    period: str | None = Field(default=None, min_length=1, max_length=32)


class PriceQueryResponse(BaseModel):
    question: str
    operation: str
    scope: dict
    data: dict
    sources: list[dict]
