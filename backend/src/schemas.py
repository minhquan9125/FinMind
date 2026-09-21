"""Pydantic request/response models for the Vector RAG API."""

from pydantic import BaseModel


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
    page: int
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
    page: int
    text: str
    score: float
    matched_terms: list[str]


class SearchResponse(BaseModel):
    results: list[SearchResultOut]
