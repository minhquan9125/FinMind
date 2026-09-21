-- FinMind backend - pgvector index for document_chunks.embedding.
--
-- ADR01 requires that the HNSW index parameters be recorded (not just
-- "default settings") so recall behaviour is reproducible across runs.
-- m = max connections per graph layer, ef_construction = candidate list
-- size while building the index. These are pgvector's own documented
-- defaults; recorded explicitly here rather than left implicit.
--
-- Must run after init_postgres_schema.sql (needs the vector extension and
-- the document_chunks table to already exist).

CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding
    ON document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

ANALYZE document_chunks;
