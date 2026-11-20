-- Optional after bulk loading; vectors work without this index.
CREATE INDEX idx_text_chunks_embedding_hnsw ON public.text_chunks USING hnsw (embedding public.vector_cosine_ops) WITH (m='16', ef_construction='64') WHERE (superseded_at IS NULL);
