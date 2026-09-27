-- FinMind backend - PostgreSQL schema for the Vector RAG module.
--
-- RAG uses dedicated table names to coexist with the financial documents and
-- text_chunks tables already present in the Supabase database.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS rag_documents (
    id           UUID PRIMARY KEY,
    filename     TEXT NOT NULL,
    page_count   INTEGER NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- embedding dimension (1024) matches BAAI/bge-m3 (ADR04). If the embedding
-- model is ever changed, this column must be recreated and every document
-- re-embedded and re-indexed - it cannot be resized in place.
CREATE TABLE IF NOT EXISTS rag_document_chunks (
    id            UUID PRIMARY KEY,
    document_id   UUID NOT NULL REFERENCES rag_documents(id) ON DELETE CASCADE,
    chunk_index   INTEGER NOT NULL,
    page          INTEGER NOT NULL,
    text          TEXT NOT NULL,
    word_count    INTEGER NOT NULL,
    token_count   INTEGER NOT NULL,
    unique_count  INTEGER NOT NULL,
    embedding     public.vector(1024) NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_rag_document_chunks_document_id
    ON rag_document_chunks (document_id);
