-- User explicitly accepted losing text for these three superseded corpus-v1
-- company chunks. IDs, embeddings, hashes and corpus membership stay unchanged.
-- Deploy the source-only reader/writers before applying this migration.
BEGIN;
SET LOCAL lock_timeout = '10s';
LOCK TABLE public.text_chunks IN ACCESS EXCLUSIVE MODE;
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM public.text_chunks t
        WHERE COALESCE(locator_json->'reconstruction'->>'schema_version', '') <> 'source-locator-v2'
          AND NOT (
            t.chunk_id IN (
              '71705bc5-edd7-58d5-bd5d-89503cfa7d6c'::uuid,
              'ed1a5bcf-6ef9-50d5-b265-5bda9883c83a'::uuid,
              '876c5bf1-8d1e-583b-9029-e5eb4ab6448c'::uuid)
            AND t.superseded_at IS NOT NULL
            AND NOT EXISTS (SELECT 1 FROM public.evidence e WHERE e.chunk_id=t.chunk_id)
          )
          AND NOT COALESCE((
            locator_json->>'schema_version'='upload-source-v1'
            AND locator_json->>'source_table'='raw_payloads'
          ), false)
    ) THEN
        RAISE EXCEPTION 'Other chunks lack source locators; dropping text would lose unapproved content';
    END IF;
END $$;
ALTER TABLE public.text_chunks DROP CONSTRAINT IF EXISTS ck_source_chunk_without_text;
ALTER TABLE public.text_chunks DROP COLUMN IF EXISTS chunk_text;
COMMIT;
