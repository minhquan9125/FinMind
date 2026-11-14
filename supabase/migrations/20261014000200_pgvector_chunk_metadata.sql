-- WBS12: make the live Supabase tables match the chunk upsert contract and
-- preserve the source locator needed to trace a vector back to its source row.
-- Existing upload paths may leave locator_json NULL; db-v1 chunks populate it.
BEGIN;

ALTER TABLE public.text_chunks
    ADD COLUMN IF NOT EXISTS locator_json jsonb;

ALTER TABLE public.text_chunks
    ALTER COLUMN document_id SET NOT NULL,
    ALTER COLUMN index_version_id SET NOT NULL,
    ALTER COLUMN chunk_index SET NOT NULL,
    ALTER COLUMN embedding SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_text_chunks_index_document_chunk
    ON public.text_chunks (index_version_id, document_id, chunk_index);

-- The existing document upload repository also uses ON CONFLICT (sha256).
CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_sha256
    ON public.documents (sha256);

COMMENT ON COLUMN public.text_chunks.locator_json IS
    'db-v1 source locator: source_table, source_id, row_keys and optional URL/period metadata';

COMMIT;
