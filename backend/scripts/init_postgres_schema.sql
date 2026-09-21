-- FinMind backend - PostgreSQL schema for the Vector RAG module.
--
-- Scope note: this only covers the tables needed by the Vector RAG demo
-- (document upload -> chunk -> embed -> search) that was ported from
-- VectorRAG_Demo.html. The full structured financial-fact schema described
-- in the project proposal (Section 12.4, Figure 4 - Logical Data and
-- Provenance Model) is a separate, not-yet-built module and is intentionally
-- NOT created here; adding those tables now would be speculative since no
-- code in this repository reads/writes them yet. See readmerepair.md.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id           UUID PRIMARY KEY,
    filename     TEXT NOT NULL,
    page_count   INTEGER NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- embedding dimension (1024) matches BAAI/bge-m3 (ADR04). If the embedding
-- model is ever changed, this column must be recreated and every document
-- re-embedded and re-indexed - it cannot be resized in place.
CREATE TABLE IF NOT EXISTS document_chunks (
    id            UUID PRIMARY KEY,
    document_id   UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index   INTEGER NOT NULL,
    page          INTEGER NOT NULL,
    text          TEXT NOT NULL,
    word_count    INTEGER NOT NULL,
    token_count   INTEGER NOT NULL,
    unique_count  INTEGER NOT NULL,
    embedding     vector(1024) NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks (document_id);
