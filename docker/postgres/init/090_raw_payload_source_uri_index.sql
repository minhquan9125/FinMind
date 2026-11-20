-- Shared-source reconstruction locates immutable envelopes by source_uri.
-- Keep duplicate detection in the reader; this is deliberately non-unique.
CREATE INDEX IF NOT EXISTS raw_payloads_source_uri_idx
    ON public.raw_payloads (source_uri);
