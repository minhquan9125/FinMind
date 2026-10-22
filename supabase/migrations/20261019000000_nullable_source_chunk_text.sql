-- Stage: stop duplicating text for new source-backed chunks. Do not delete old text.
-- Deploy locator-v2 readers before enabling source-backed ingest with this schema.
BEGIN;
ALTER TABLE public.text_chunks ALTER COLUMN chunk_text DROP NOT NULL;
ALTER TABLE public.text_chunks DROP CONSTRAINT IF EXISTS ck_source_chunk_without_text;
ALTER TABLE public.text_chunks ADD CONSTRAINT ck_source_chunk_without_text CHECK (
    chunk_text IS NOT NULL OR
    COALESCE(locator_json->'reconstruction'->>'schema_version', '') = 'source-locator-v2'
);
COMMIT;
