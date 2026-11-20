-- WBS03 DB contract drafts: immutable envelopes; never auto-publish approved edges.
CREATE TABLE IF NOT EXISTS graph_metadata.wbs03_envelopes (
 graph_version_id uuid PRIMARY KEY REFERENCES public.graph_versions,
 corpus_version_id uuid NOT NULL REFERENCES public.corpus_versions,
 index_version_id uuid NOT NULL REFERENCES public.index_versions,
 schema_version text NOT NULL CHECK(schema_version='2.1.0'),
 content_sha256 text NOT NULL UNIQUE CHECK(content_sha256 ~ '^[0-9a-f]{64}$'),
 payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS wbs03_envelopes_corpus ON graph_metadata.wbs03_envelopes(corpus_version_id,index_version_id);
ALTER TABLE graph_metadata.wbs03_envelopes ENABLE ROW LEVEL SECURITY;
ALTER TABLE graph_metadata.wbs03_envelopes FORCE ROW LEVEL SECURITY;
DO $$ BEGIN
 IF NOT EXISTS(SELECT FROM pg_policies WHERE schemaname='graph_metadata' AND tablename='wbs03_envelopes' AND policyname='graph_read') THEN
  CREATE POLICY graph_read ON graph_metadata.wbs03_envelopes FOR SELECT TO finmind_graph_reader USING(true);
 END IF;
 IF NOT EXISTS(SELECT FROM pg_policies WHERE schemaname='graph_metadata' AND tablename='wbs03_envelopes' AND policyname='graph_write') THEN
  CREATE POLICY graph_write ON graph_metadata.wbs03_envelopes FOR INSERT TO finmind_graph_writer
   WITH CHECK(payload->>'schema_version'=schema_version AND payload->>'corpus_id'=corpus_version_id::text AND payload->>'dataset_version'=index_version_id::text
    AND NOT EXISTS(SELECT FROM jsonb_array_elements(payload->'relations') r WHERE r->'review'->>'status' IS DISTINCT FROM 'PENDING'));
 END IF;
 IF NOT EXISTS(SELECT FROM pg_policies WHERE schemaname='public' AND tablename='graph_versions' AND policyname='wbs03_draft_insert') THEN
  CREATE POLICY wbs03_draft_insert ON public.graph_versions FOR INSERT TO finmind_graph_writer WITH CHECK(status='EXTRACTED_PENDING');
 END IF;
 IF NOT EXISTS(SELECT FROM pg_policies WHERE schemaname='public' AND tablename='graph_extractions' AND policyname='wbs03_draft_insert') THEN
  CREATE POLICY wbs03_draft_insert ON public.graph_extractions FOR INSERT TO finmind_graph_writer
   WITH CHECK(method='WBS03' AND validation_status='CONTRACT_VALIDATED' AND manual_check='PENDING'
    AND EXISTS(SELECT FROM graph_metadata.wbs03_envelopes x WHERE x.graph_version_id=graph_extractions.graph_version_id));
 END IF;
 IF NOT EXISTS(SELECT FROM pg_policies WHERE schemaname='public' AND tablename='evidence' AND policyname='wbs03_draft_insert') THEN
  CREATE POLICY wbs03_draft_insert ON public.evidence FOR INSERT TO finmind_graph_writer
   WITH CHECK(evidence_type='GRAPH' AND locator_json->>'kind'='wbs03_db_contract'
    AND EXISTS(SELECT FROM public.graph_extractions g JOIN graph_metadata.wbs03_envelopes x USING(graph_version_id) WHERE g.extraction_id=evidence.extraction_id));
 END IF;
 IF NOT EXISTS(SELECT FROM pg_policies WHERE schemaname='public' AND tablename='evidence' AND policyname='wbs03_source_read') THEN
  CREATE POLICY wbs03_source_read ON public.evidence FOR SELECT TO finmind_graph_reader USING(true);
 END IF;
 IF NOT EXISTS(SELECT FROM pg_policies WHERE schemaname='public' AND tablename='raw_payloads' AND policyname='wbs03_snapshot_read') THEN
  CREATE POLICY wbs03_snapshot_read ON public.raw_payloads FOR SELECT TO finmind_graph_writer
   USING(source_uri LIKE 'finmind:shared-source:%' OR source_uri LIKE 'finmind:shared-source-release:%');
 END IF;
END $$;
GRANT SELECT ON graph_metadata.wbs03_envelopes TO finmind_graph_reader;
GRANT INSERT ON graph_metadata.wbs03_envelopes TO finmind_graph_writer;
GRANT INSERT ON public.graph_versions,public.graph_extractions,public.evidence TO finmind_graph_writer;
GRANT SELECT ON public.raw_payloads TO finmind_graph_writer;
GRANT SELECT ON public.evidence TO finmind_graph_reader;
