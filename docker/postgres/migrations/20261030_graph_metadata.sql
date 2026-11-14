-- Additive PostgreSQL metadata repository. Version IDs are distinct from schema versions.
CREATE SCHEMA IF NOT EXISTS graph_metadata;
REVOKE ALL ON SCHEMA graph_metadata FROM PUBLIC;
DO $$ BEGIN
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='finmind_graph_reader') THEN CREATE ROLE finmind_graph_reader NOLOGIN NOSUPERUSER NOBYPASSRLS; END IF;
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='finmind_graph_writer') THEN CREATE ROLE finmind_graph_writer NOLOGIN NOSUPERUSER NOBYPASSRLS; END IF;
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='finmind_graph_reviewer') THEN CREATE ROLE finmind_graph_reviewer NOLOGIN NOSUPERUSER NOBYPASSRLS; END IF;
END $$;
GRANT finmind_graph_reader TO finmind_graph_writer,finmind_graph_reviewer;
CREATE TABLE IF NOT EXISTS graph_metadata.versions (
 graph_version_id uuid PRIMARY KEY REFERENCES public.graph_versions,
 corpus_version_id uuid NOT NULL REFERENCES public.corpus_versions,
 index_version_id uuid NOT NULL REFERENCES public.index_versions,
 metadata_schema_version text NOT NULL CHECK(metadata_schema_version='1.0.0'),
 extraction_contract_version text NOT NULL CHECK(length(extraction_contract_version)>0),
 manifest_sha256 text NOT NULL CHECK(manifest_sha256 ~ '^[0-9a-f]{64}$'),
 provenance jsonb NOT NULL CHECK(jsonb_typeof(provenance)='object'),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS graph_metadata.entities (
 graph_version_id uuid NOT NULL REFERENCES graph_metadata.versions,
 entity_id uuid NOT NULL, entity_type text NOT NULL CHECK(entity_type IN ('Person','Company','Event')),
 canonical_name text NOT NULL CHECK(length(trim(canonical_name))>0),
 resolution_status text NOT NULL CHECK(resolution_status IN ('source_scoped','resolved','unresolved','ambiguous')),
 attributes jsonb NOT NULL CHECK(jsonb_typeof(attributes)='object'),
 CHECK(resolution_status<>'resolved' OR length(trim(COALESCE(attributes->>'identity_key','')))>0),
 PRIMARY KEY(graph_version_id,entity_id)
);
CREATE TABLE IF NOT EXISTS graph_metadata.assertions (
 extraction_id uuid PRIMARY KEY REFERENCES public.graph_extractions,
 graph_version_id uuid NOT NULL REFERENCES graph_metadata.versions,
 subject_id uuid NOT NULL, object_id uuid NOT NULL,
 relation_type text NOT NULL CHECK(relation_type IN ('HOLDS_ROLE','FORMER_ROLE','RESIGNS','REQUESTS_RESIGNATION','APPOINTS','DISMISSES')),
 content_sha256 text NOT NULL CHECK(content_sha256 ~ '^[0-9a-f]{64}$'),
 payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
 UNIQUE(graph_version_id,extraction_id),
 FOREIGN KEY(graph_version_id,subject_id) REFERENCES graph_metadata.entities,
 FOREIGN KEY(graph_version_id,object_id) REFERENCES graph_metadata.entities,
 CHECK(subject_id<>object_id)
);
CREATE TABLE IF NOT EXISTS graph_metadata.source_chunks (
 graph_version_id uuid NOT NULL, extraction_id uuid NOT NULL,
 chunk_id uuid NOT NULL REFERENCES public.text_chunks,
 content_hash text NOT NULL CHECK(content_hash ~ '^[0-9a-f]{64}$'),
 PRIMARY KEY(extraction_id,chunk_id),
 FOREIGN KEY(graph_version_id,extraction_id) REFERENCES graph_metadata.assertions(graph_version_id,extraction_id)
);
CREATE TABLE IF NOT EXISTS graph_metadata.reviews (
 review_id uuid PRIMARY KEY, extraction_id uuid NOT NULL REFERENCES graph_metadata.assertions,
 decision text NOT NULL CHECK(decision IN ('PENDING','APPROVED','REJECTED','QUARANTINED')),
 reason_code text NOT NULL CHECK(length(trim(reason_code))>0),
 note text NOT NULL CHECK(length(trim(note))>0),
 actor text NOT NULL DEFAULT current_user CHECK(actor=current_user),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS graph_metadata_versions_corpus ON graph_metadata.versions(corpus_version_id,index_version_id);
CREATE INDEX IF NOT EXISTS graph_metadata_assertions_subject ON graph_metadata.assertions(graph_version_id,subject_id,relation_type);
CREATE INDEX IF NOT EXISTS graph_metadata_assertions_object ON graph_metadata.assertions(graph_version_id,object_id,relation_type);
CREATE INDEX IF NOT EXISTS graph_metadata_sources_chunk ON graph_metadata.source_chunks(chunk_id);
CREATE INDEX IF NOT EXISTS graph_metadata_reviews_history ON graph_metadata.reviews(extraction_id,created_at DESC,review_id);
-- Invoker checks use SELECT-only policies below; no security-definer bypass.
CREATE OR REPLACE FUNCTION graph_metadata.check_source_binding() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,graph_metadata,public AS $$
BEGIN
 IF TG_TABLE_NAME='versions' THEN
  IF NOT EXISTS(SELECT FROM public.corpus_documents cd JOIN public.text_chunks t USING(document_id)
   WHERE cd.corpus_version_id=NEW.corpus_version_id AND t.index_version_id=NEW.index_version_id)
  THEN RAISE EXCEPTION 'Corpus/index mismatch' USING ERRCODE='23514'; END IF;
 ELSIF TG_TABLE_NAME='assertions' THEN
  IF NOT EXISTS(SELECT FROM public.graph_extractions g JOIN graph_metadata.versions v USING(graph_version_id)
   JOIN public.corpus_documents cd ON cd.document_id=g.document_id AND cd.corpus_version_id=v.corpus_version_id
   JOIN graph_metadata.entities s ON s.graph_version_id=NEW.graph_version_id AND s.entity_id=NEW.subject_id
   JOIN graph_metadata.entities o ON o.graph_version_id=NEW.graph_version_id AND o.entity_id=NEW.object_id
   WHERE g.extraction_id=NEW.extraction_id AND g.graph_version_id=NEW.graph_version_id
   AND g.relation_type=NEW.relation_type AND g.subject=s.canonical_name AND g.object=o.canonical_name
   AND ((NEW.relation_type IN ('HOLDS_ROLE','FORMER_ROLE','RESIGNS','REQUESTS_RESIGNATION') AND s.entity_type='Person' AND o.entity_type='Company')
    OR (NEW.relation_type IN ('APPOINTS','DISMISSES') AND s.entity_type='Company' AND o.entity_type='Person')))
  THEN RAISE EXCEPTION 'Extraction/version/entity mismatch' USING ERRCODE='23514'; END IF;
 ELSIF TG_TABLE_NAME='source_chunks' THEN
  IF NOT EXISTS(SELECT FROM graph_metadata.versions v JOIN public.graph_extractions g USING(graph_version_id)
    JOIN public.text_chunks t ON t.document_id=g.document_id AND t.index_version_id=v.index_version_id
    JOIN public.corpus_documents cd ON cd.document_id=t.document_id AND cd.corpus_version_id=v.corpus_version_id
    WHERE v.graph_version_id=NEW.graph_version_id AND g.extraction_id=NEW.extraction_id
    AND t.chunk_id=NEW.chunk_id AND t.content_hash=NEW.content_hash AND t.superseded_at IS NULL)
  THEN RAISE EXCEPTION 'Chunk/corpus/hash mismatch' USING ERRCODE='23514'; END IF;
 ELSIF TG_TABLE_NAME='reviews' AND NEW.decision='APPROVED' THEN
  IF NOT EXISTS(SELECT FROM graph_metadata.assertions a
   JOIN graph_metadata.entities s ON s.graph_version_id=a.graph_version_id AND s.entity_id=a.subject_id
   JOIN graph_metadata.entities o ON o.graph_version_id=a.graph_version_id AND o.entity_id=a.object_id
   WHERE a.extraction_id=NEW.extraction_id AND a.payload->>'validation_status'='SOURCE_VERIFIED'
    AND a.relation_type IN ('HOLDS_ROLE','APPOINTS','DISMISSES')
    AND s.resolution_status='resolved' AND o.resolution_status='resolved'
    AND (NULLIF(a.payload->>'effective_date','') IS NOT NULL OR NULLIF(a.payload->>'report_year','') IS NOT NULL))
  THEN RAISE EXCEPTION 'Approval requires resolved endpoints, verified source and time basis' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN NEW;
END $$;
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['versions','assertions','source_chunks','reviews'] LOOP
  IF NOT EXISTS(SELECT FROM pg_trigger WHERE tgrelid=('graph_metadata.'||t)::regclass AND tgname='check_source_binding') THEN
   EXECUTE format('CREATE TRIGGER check_source_binding BEFORE INSERT ON graph_metadata.%I FOR EACH ROW EXECUTE FUNCTION graph_metadata.check_source_binding()',t);
  END IF;
 END LOOP;
 FOREACH t IN ARRAY ARRAY['versions','entities','assertions','source_chunks','reviews'] LOOP
  EXECUTE format('ALTER TABLE graph_metadata.%I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('ALTER TABLE graph_metadata.%I FORCE ROW LEVEL SECURITY',t);
  IF NOT EXISTS(SELECT FROM pg_policies WHERE schemaname='graph_metadata' AND tablename=t AND policyname='graph_read') THEN
   EXECUTE format('CREATE POLICY graph_read ON graph_metadata.%I FOR SELECT TO finmind_graph_reader USING(true)',t);
  END IF;
  IF t<>'reviews' AND NOT EXISTS(SELECT FROM pg_policies WHERE schemaname='graph_metadata' AND tablename=t AND policyname='graph_write') THEN
   EXECUTE format('CREATE POLICY graph_write ON graph_metadata.%I FOR INSERT TO finmind_graph_writer WITH CHECK(true)',t);
  END IF;
 END LOOP;
 IF NOT EXISTS(SELECT FROM pg_policies WHERE schemaname='graph_metadata' AND tablename='reviews' AND policyname='graph_review') THEN
  CREATE POLICY graph_review ON graph_metadata.reviews FOR INSERT TO finmind_graph_reviewer WITH CHECK(actor=current_user);
 END IF;
END $$;
GRANT USAGE ON SCHEMA graph_metadata TO finmind_graph_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA graph_metadata TO finmind_graph_reader;
GRANT INSERT ON graph_metadata.versions,graph_metadata.entities,graph_metadata.assertions,graph_metadata.source_chunks TO finmind_graph_writer;
GRANT INSERT ON graph_metadata.reviews TO finmind_graph_reviewer;
REVOKE ALL ON FUNCTION graph_metadata.check_source_binding() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION graph_metadata.check_source_binding() TO finmind_graph_writer,finmind_graph_reviewer;
GRANT SELECT ON public.graph_versions,public.graph_extractions,public.documents,public.text_chunks,public.corpus_documents,public.corpus_versions,public.index_versions TO finmind_graph_reader;
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['graph_versions','graph_extractions','documents','text_chunks','corpus_documents','corpus_versions','index_versions'] LOOP
  IF NOT EXISTS(SELECT FROM pg_policies WHERE schemaname='public' AND tablename=t AND policyname='graph_metadata_source_read') THEN
   EXECUTE format('CREATE POLICY graph_metadata_source_read ON public.%I FOR SELECT TO finmind_graph_reader USING(true)',t);
  END IF;
 END LOOP;
 IF EXISTS(SELECT FROM pg_roles WHERE rolname='finmind_developer') THEN GRANT finmind_graph_writer TO finmind_developer; END IF;
 IF EXISTS(SELECT FROM pg_roles WHERE rolname='finmind_chat_runtime') THEN GRANT finmind_graph_reader TO finmind_chat_runtime; END IF;
END $$;
