-- WBS20: cosine HNSW index for active pgvector rows.
-- Apply only after saving the pre-index benchmark; this is reversible and
-- does not alter chunk/vector rows.
CREATE INDEX IF NOT EXISTS idx_text_chunks_embedding_hnsw
    ON public.text_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64)
    WHERE superseded_at IS NULL;

COMMENT ON INDEX public.idx_text_chunks_embedding_hnsw IS
    'WBS20 pgvector cosine HNSW index over active chunks; drop to roll back.';
