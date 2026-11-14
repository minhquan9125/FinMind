-- DESTRUCTIVE: clears every object and all data in the public schema, then rebuilds the ERD schema.
-- Run this entire file once in Supabase SQL Editor. Do not run only the FK section.
BEGIN;
DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON SCHEMA public TO postgres, service_role;

-- Baseline schema generated from the user supplied ERD in ERD.md.
-- The ERD specifies columns, SQL-like types, primary keys, and foreign-key relationships only.
-- Defaults, non-PK nullability, unique/check constraints, indexes, and RLS policies are not inferred.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE public."users" (
    "user_id" uuid NOT NULL,
    "email" varchar(255),
    "username" varchar(50),
    "password_hash" varchar(255),
    "full_name" varchar(255),
    "is_active" boolean,
    "last_login_at" timestamptz,
    "updated_at" timestamptz,
    "created_at" timestamptz,
    PRIMARY KEY ("user_id")
);

CREATE TABLE public."user_roles" (
    "user_id" uuid NOT NULL,
    "role_id" uuid NOT NULL,
    PRIMARY KEY ("user_id", "role_id")
);

CREATE TABLE public."sessions" (
    "session_id" uuid NOT NULL,
    "user_id" uuid,
    "token_hash" varchar(128),
    "issued_at" timestamptz,
    "expires_at" timestamptz,
    "revoked_at" timestamptz,
    "ip_address" inet,
    "user_agent" text,
    PRIMARY KEY ("session_id")
);

CREATE TABLE public."config_versions" (
    "config_version_id" uuid NOT NULL,
    "version_label" varchar(30),
    "description" text,
    "is_active" boolean,
    "frozen_at" timestamptz,
    "frozen_by" uuid,
    "created_by" uuid,
    "created_at" timestamptz,
    PRIMARY KEY ("config_version_id")
);

CREATE TABLE public."system_configs" (
    "config_version_id" uuid NOT NULL,
    "config_key" varchar(100) NOT NULL,
    "config_value" jsonb,
    PRIMARY KEY ("config_version_id", "config_key")
);

CREATE TABLE public."roles" (
    "role_id" uuid NOT NULL,
    "role_code" varchar(30),
    "description" text,
    PRIMARY KEY ("role_id")
);

CREATE TABLE public."permissions" (
    "permission_id" uuid NOT NULL,
    "resource" varchar(50),
    "action" varchar(30),
    "description" text,
    PRIMARY KEY ("permission_id")
);

CREATE TABLE public."role_permissions" (
    "role_id" uuid NOT NULL,
    "permission_id" uuid NOT NULL,
    PRIMARY KEY ("role_id", "permission_id")
);

CREATE TABLE public."audit_logs" (
    "audit_id" uuid NOT NULL,
    "user_id" uuid,
    "action" varchar(50),
    "resource_type" varchar(50),
    "resource_id" varchar(64),
    "outcome" varchar(20),
    "ip_address" inet,
    "user_agent" text,
    "metadata_json" jsonb,
    "created_at" timestamptz,
    PRIMARY KEY ("audit_id")
);

CREATE TABLE public."watchlists" (
    "user_id" uuid NOT NULL,
    "company_id" uuid NOT NULL,
    "pinned_at" timestamptz,
    PRIMARY KEY ("user_id", "company_id")
);

CREATE TABLE public."sources" (
    "source_id" uuid NOT NULL,
    "name" varchar(100),
    "source_type" varchar(30),
    "base_url" text,
    "approval_status" varchar(20),
    "approved_by" uuid,
    "approved_at" timestamptz,
    "scope_note" text,
    "is_enabled" boolean,
    PRIMARY KEY ("source_id")
);

CREATE TABLE public."ingestion_jobs" (
    "job_id" uuid NOT NULL,
    "source_id" uuid,
    "triggered_by" uuid,
    "trigger_type" varchar(20),
    "status" varchar(20),
    "schema_version" varchar(20),
    "started_at" timestamptz,
    "finished_at" timestamptz,
    "records_ok" integer,
    "records_quarantined" integer,
    PRIMARY KEY ("job_id")
);

CREATE TABLE public."raw_payloads" (
    "payload_id" uuid NOT NULL,
    "job_id" uuid,
    "source_uri" text,
    "sha256" char(64),
    "payload" jsonb,
    "stored_at" timestamptz,
    PRIMARY KEY ("payload_id")
);

CREATE TABLE public."quarantine_records" (
    "record_id" uuid NOT NULL,
    "job_id" uuid,
    "payload_id" uuid,
    "extraction_id" uuid,
    "entity_type" varchar(30),
    "reason_code" varchar(50),
    "status" varchar(20),
    "reviewed_by" uuid,
    "reviewed_at" timestamptz,
    PRIMARY KEY ("record_id")
);

CREATE TABLE public."companies" (
    "company_id" uuid NOT NULL,
    "symbol" varchar(10),
    "company_name" varchar(255),
    "industry_type" varchar(30),
    "sector" varchar(100),
    "exchange" varchar(10),
    "is_active" boolean,
    PRIMARY KEY ("company_id")
);

CREATE TABLE public."metrics" (
    "metric_id" uuid NOT NULL,
    "code" varchar(50),
    "canonical_name" varchar(255),
    "section" varchar(30),
    "default_unit" varchar(20),
    "industry_scope" varchar(30),
    "mapping_status" varchar(20),
    PRIMARY KEY ("metric_id")
);

CREATE TABLE public."financial_reports" (
    "report_id" uuid NOT NULL,
    "company_id" uuid,
    "period_id" uuid,
    "document_id" uuid,
    "payload_id" uuid,
    "job_id" uuid,
    "statement_scope" varchar(20),
    "audit_status" varchar(20),
    "report_version" integer,
    "restated_from_id" uuid,
    "published_at" date,
    PRIMARY KEY ("report_id")
);

CREATE TABLE public."reporting_periods" (
    "period_id" uuid NOT NULL,
    "period_code" varchar(10),
    "fiscal_year" integer,
    "quarter" smallint,
    "period_type" varchar(10),
    "start_date" date,
    "end_date" date,
    PRIMARY KEY ("period_id")
);

CREATE TABLE public."metric_aliases" (
    "alias_id" uuid NOT NULL,
    "metric_id" uuid,
    "raw_label" varchar(255),
    "industry_scope" varchar(30),
    PRIMARY KEY ("alias_id")
);

CREATE TABLE public."price_bars" (
    "price_id" uuid NOT NULL,
    "company_id" uuid,
    "payload_id" uuid,
    "trade_date" date,
    "is_adjusted" boolean,
    "price_scale" integer,
    "open" numeric(18, 4),
    "high" numeric(18, 4),
    "low" numeric(18, 4),
    "close" numeric(18, 4),
    "volume" bigint,
    PRIMARY KEY ("price_id")
);

CREATE TABLE public."observations" (
    "observation_id" uuid NOT NULL,
    "report_id" uuid,
    "metric_id" uuid,
    "value" numeric(24, 4),
    "unit" varchar(20),
    "scale" integer,
    "currency" char(3),
    "locator_json" jsonb,
    PRIMARY KEY ("observation_id")
);

CREATE TABLE public."documents" (
    "document_id" uuid NOT NULL,
    "company_id" uuid,
    "period_id" uuid,
    "job_id" uuid,
    "doc_type" varchar(30) NOT NULL,
    "file_type" varchar(10) NOT NULL,
    "title" varchar(500) NOT NULL,
    "storage_uri" text,
    "source_url" text,
    "external_id" varchar(100),
    "language" char(2),
    "page_count" integer,
    "file_size" bigint,
    "published_at" timestamptz,
    "sha256" char(64) NOT NULL,
    "parse_status" varchar(20),
    "created_at" timestamptz NOT NULL,
    PRIMARY KEY ("document_id")
);

CREATE TABLE public."text_chunks" (
    "chunk_id" uuid NOT NULL,
    "document_id" uuid NOT NULL,
    "index_version_id" uuid NOT NULL,
    "chunk_index" integer NOT NULL,
    "page_number" integer,
    "section_label" varchar(255),
    "chunk_text" text NOT NULL,
    "token_count" integer NOT NULL,
    "char_start" integer NOT NULL,
    "char_end" integer NOT NULL,
    "content_hash" char(64) NOT NULL,
    "embedding" vector(1024) NOT NULL,
    "created_at" timestamptz NOT NULL,
    PRIMARY KEY ("chunk_id")
);

CREATE TABLE public."index_versions" (
    "index_version_id" uuid NOT NULL,
    "chunker_version" varchar(30),
    "chunk_size" integer,
    "chunk_overlap" integer,
    "embedding_model" varchar(50),
    "built_at" timestamptz,
    "status" varchar(20),
    PRIMARY KEY ("index_version_id")
);

CREATE UNIQUE INDEX IF NOT EXISTS "uq_documents_sha256"
    ON public."documents" ("sha256");
CREATE UNIQUE INDEX IF NOT EXISTS "uq_text_chunks_index_document_chunk"
    ON public."text_chunks" ("index_version_id", "document_id", "chunk_index");

CREATE TABLE public."evidence" (
    "evidence_id" uuid NOT NULL,
    "evidence_type" varchar(10),
    "chunk_id" uuid,
    "observation_id" uuid,
    "price_id" uuid,
    "extraction_id" uuid,
    "calc_formula" text,
    "company_id" uuid,
    "period_id" uuid,
    "unit" varchar(20),
    "statement_scope" varchar(20),
    "source_sha256" char(64),
    "locator_json" jsonb,
    "created_at" timestamptz,
    PRIMARY KEY ("evidence_id")
);

CREATE TABLE public."calc_inputs" (
    "evidence_id" uuid NOT NULL,
    "input_evidence_id" uuid NOT NULL,
    "position" integer,
    PRIMARY KEY ("evidence_id", "input_evidence_id")
);

CREATE TABLE public."graph_versions" (
    "graph_version_id" uuid NOT NULL,
    "built_at" timestamptz,
    "node_count" integer,
    "edge_count" integer,
    "status" varchar(20),
    PRIMARY KEY ("graph_version_id")
);

CREATE TABLE public."graph_extractions" (
    "extraction_id" uuid NOT NULL,
    "graph_version_id" uuid,
    "document_id" uuid,
    "method" varchar(10),
    "subject" varchar(255),
    "relation_type" varchar(50),
    "object" varchar(255),
    "source_span" text,
    "validation_status" varchar(20),
    "reject_reason" varchar(100),
    "neo4j_edge_key" varchar(100),
    "manual_check" varchar(10),
    PRIMARY KEY ("extraction_id")
);

CREATE TABLE public."queries" (
    "query_id" uuid NOT NULL,
    "user_id" uuid,
    "run_id" uuid,
    "question_text" text,
    "question_type" varchar(20),
    "configuration" varchar(10),
    "corpus_version_id" uuid,
    "config_version_id" uuid,
    "language" char(2),
    "trace_id" varchar(64),
    "created_at" timestamptz,
    "deleted_at" timestamptz,
    PRIMARY KEY ("query_id")
);

CREATE TABLE public."reason_codes" (
    "code" varchar(50) NOT NULL,
    "result_status" varchar(20),
    "user_message" text,
    "is_active" boolean,
    PRIMARY KEY ("code")
);

CREATE TABLE public."gate_decision_evidence" (
    "decision_id" uuid NOT NULL,
    "evidence_id" uuid NOT NULL,
    "role" varchar(10),
    "drop_reason" varchar(50),
    PRIMARY KEY ("decision_id", "evidence_id")
);

CREATE TABLE public."answers" (
    "answer_id" uuid NOT NULL,
    "query_id" uuid,
    "attempt" integer,
    "decision_id" uuid,
    "answer_text" text,
    "status" varchar(20),
    "reason_code" varchar(50),
    "model_name" varchar(50),
    "prompt_version" varchar(30),
    "latency_ms" integer,
    "latency_breakdown_json" jsonb,
    "created_at" timestamptz,
    PRIMARY KEY ("answer_id")
);

CREATE TABLE public."claim_verifications" (
    "verification_id" uuid NOT NULL,
    "claim_id" uuid,
    "check_type" varchar(10),
    "passed" boolean,
    "detail" jsonb,
    "created_at" timestamptz,
    PRIMARY KEY ("verification_id")
);

CREATE TABLE public."query_companies" (
    "query_id" uuid NOT NULL,
    "company_id" uuid NOT NULL,
    PRIMARY KEY ("query_id", "company_id")
);

CREATE TABLE public."retrieval_results" (
    "result_id" uuid NOT NULL,
    "query_id" uuid,
    "attempt" integer,
    "evidence_id" uuid,
    "branch" varchar(10),
    "score" double precision,
    "rank_before" integer,
    "rank_after" integer,
    PRIMARY KEY ("result_id")
);

CREATE TABLE public."gate_decisions" (
    "decision_id" uuid NOT NULL,
    "query_id" uuid,
    "attempt" integer,
    "status" varchar(20),
    "reason_code" varchar(50),
    "reference_date" date,
    "is_stale" boolean,
    "has_conflict" boolean,
    "mandatory_branch_missing" boolean,
    "relevance_score" double precision,
    "created_at" timestamptz,
    PRIMARY KEY ("decision_id")
);

CREATE TABLE public."claims" (
    "claim_id" uuid NOT NULL,
    "answer_id" uuid,
    "ordinal" integer,
    "claim_text" text,
    "claim_type" varchar(10),
    "verification_status" varchar(20),
    PRIMARY KEY ("claim_id")
);

CREATE TABLE public."citations" (
    "citation_id" uuid NOT NULL,
    "claim_id" uuid,
    "evidence_id" uuid,
    "ordinal" integer,
    PRIMARY KEY ("citation_id")
);

CREATE TABLE public."feedback" (
    "feedback_id" uuid NOT NULL,
    "user_id" uuid,
    "query_id" uuid,
    "citation_id" uuid,
    "evidence_id" uuid,
    "issue_type" varchar(30),
    "comment" text,
    "status" varchar(20),
    "created_at" timestamptz,
    "resolved_at" timestamptz,
    "resolved_by" uuid,
    PRIMARY KEY ("feedback_id")
);

CREATE TABLE public."corpus_versions" (
    "corpus_version_id" uuid NOT NULL,
    "version_label" varchar(30),
    "description" text,
    "graph_version_id" uuid,
    "index_version_id" uuid,
    "frozen_at" timestamptz,
    "frozen_by" uuid,
    "manifest_sha256" char(64),
    "status" varchar(20),
    PRIMARY KEY ("corpus_version_id")
);

CREATE TABLE public."corpus_facts" (
    "corpus_version_id" uuid NOT NULL,
    "observation_id" uuid NOT NULL,
    "value_hash" char(64),
    PRIMARY KEY ("corpus_version_id", "observation_id")
);

CREATE TABLE public."corpus_prices" (
    "corpus_version_id" uuid NOT NULL,
    "price_id" uuid NOT NULL,
    "value_hash" char(64),
    PRIMARY KEY ("corpus_version_id", "price_id")
);

CREATE TABLE public."evaluation_runs" (
    "run_id" uuid NOT NULL,
    "run_type" varchar(12),
    "configuration" varchar(10),
    "corpus_version_id" uuid,
    "golden_set_id" uuid,
    "config_version_id" uuid,
    "model_name" varchar(50),
    "judge_model" varchar(50),
    "ragas_version" varchar(20),
    "temperature" double precision,
    "seed" integer,
    "prompt_version" varchar(30),
    "prompt_hash" varchar(64),
    "git_commit" varchar(40),
    "config_json" jsonb,
    "status" varchar(20),
    "started_at" timestamptz,
    "completed_at" timestamptz,
    "triggered_by" uuid,
    PRIMARY KEY ("run_id")
);

CREATE TABLE public."usage_events" (
    "usage_id" uuid NOT NULL,
    "event_type" varchar(20),
    "model_name" varchar(50),
    "answer_id" uuid,
    "run_id" uuid,
    "graph_version_id" uuid,
    "index_version_id" uuid,
    "tokens_input" bigint,
    "tokens_output" bigint,
    "cost_usd" numeric(10, 6),
    "recorded_at" timestamptz,
    PRIMARY KEY ("usage_id")
);

CREATE TABLE public."corpus_documents" (
    "corpus_version_id" uuid NOT NULL,
    "document_id" uuid NOT NULL,
    "document_hash" char(64),
    PRIMARY KEY ("corpus_version_id", "document_id")
);

CREATE TABLE public."golden_sets" (
    "golden_set_id" uuid NOT NULL,
    "version_label" varchar(20),
    "description" text,
    "frozen_at" timestamptz,
    "frozen_by" uuid,
    "created_at" timestamptz,
    PRIMARY KEY ("golden_set_id")
);

CREATE TABLE public."golden_questions" (
    "question_id" uuid NOT NULL,
    "golden_set_id" uuid,
    "question_text" text,
    "question_type" varchar(20),
    "period_id" uuid,
    "answerability" varchar(20),
    "expected_status" varchar(20),
    "expected_reason_code" varchar(50),
    "reference_answer" text,
    "canonical_numeric_value" numeric(24, 4),
    "gold_locators_json" jsonb,
    "dataset_split" varchar(10),
    "created_at" timestamptz,
    PRIMARY KEY ("question_id")
);

CREATE TABLE public."golden_question_companies" (
    "question_id" uuid NOT NULL,
    "company_id" uuid NOT NULL,
    PRIMARY KEY ("question_id", "company_id")
);

CREATE TABLE public."evaluation_results" (
    "result_id" uuid NOT NULL,
    "run_id" uuid,
    "question_id" uuid,
    "answer_id" uuid,
    "gate_status" varchar(20),
    "correctness" double precision,
    "faithfulness" double precision,
    "citation_correctness" double precision,
    "citation_coverage" double precision,
    "context_precision" double precision,
    "retrieval_recall_json" jsonb,
    "latency_ms" integer,
    "trace_id" varchar(64),
    "created_at" timestamptz,
    PRIMARY KEY ("result_id")
);

ALTER TABLE public."user_roles" ADD FOREIGN KEY ("user_id") REFERENCES public."users" ("user_id");
ALTER TABLE public."user_roles" ADD FOREIGN KEY ("role_id") REFERENCES public."roles" ("role_id");
ALTER TABLE public."role_permissions" ADD FOREIGN KEY ("role_id") REFERENCES public."roles" ("role_id");
ALTER TABLE public."role_permissions" ADD FOREIGN KEY ("permission_id") REFERENCES public."permissions" ("permission_id");
ALTER TABLE public."sessions" ADD FOREIGN KEY ("user_id") REFERENCES public."users" ("user_id");
ALTER TABLE public."audit_logs" ADD FOREIGN KEY ("user_id") REFERENCES public."users" ("user_id");
ALTER TABLE public."config_versions" ADD FOREIGN KEY ("frozen_by") REFERENCES public."users" ("user_id");
ALTER TABLE public."config_versions" ADD FOREIGN KEY ("created_by") REFERENCES public."users" ("user_id");
ALTER TABLE public."system_configs" ADD FOREIGN KEY ("config_version_id") REFERENCES public."config_versions" ("config_version_id");
ALTER TABLE public."watchlists" ADD FOREIGN KEY ("user_id") REFERENCES public."users" ("user_id");
ALTER TABLE public."watchlists" ADD FOREIGN KEY ("company_id") REFERENCES public."companies" ("company_id");
ALTER TABLE public."sources" ADD FOREIGN KEY ("approved_by") REFERENCES public."users" ("user_id");
ALTER TABLE public."ingestion_jobs" ADD FOREIGN KEY ("source_id") REFERENCES public."sources" ("source_id");
ALTER TABLE public."ingestion_jobs" ADD FOREIGN KEY ("triggered_by") REFERENCES public."users" ("user_id");
ALTER TABLE public."raw_payloads" ADD FOREIGN KEY ("job_id") REFERENCES public."ingestion_jobs" ("job_id");
ALTER TABLE public."quarantine_records" ADD FOREIGN KEY ("job_id") REFERENCES public."ingestion_jobs" ("job_id");
ALTER TABLE public."quarantine_records" ADD FOREIGN KEY ("payload_id") REFERENCES public."raw_payloads" ("payload_id");
ALTER TABLE public."quarantine_records" ADD FOREIGN KEY ("extraction_id") REFERENCES public."graph_extractions" ("extraction_id");
ALTER TABLE public."quarantine_records" ADD FOREIGN KEY ("reviewed_by") REFERENCES public."users" ("user_id");
ALTER TABLE public."metric_aliases" ADD FOREIGN KEY ("metric_id") REFERENCES public."metrics" ("metric_id");
ALTER TABLE public."price_bars" ADD FOREIGN KEY ("company_id") REFERENCES public."companies" ("company_id");
ALTER TABLE public."price_bars" ADD FOREIGN KEY ("payload_id") REFERENCES public."raw_payloads" ("payload_id");
ALTER TABLE public."financial_reports" ADD FOREIGN KEY ("company_id") REFERENCES public."companies" ("company_id");
ALTER TABLE public."financial_reports" ADD FOREIGN KEY ("period_id") REFERENCES public."reporting_periods" ("period_id");
ALTER TABLE public."financial_reports" ADD FOREIGN KEY ("document_id") REFERENCES public."documents" ("document_id");
ALTER TABLE public."financial_reports" ADD FOREIGN KEY ("payload_id") REFERENCES public."raw_payloads" ("payload_id");
ALTER TABLE public."financial_reports" ADD FOREIGN KEY ("job_id") REFERENCES public."ingestion_jobs" ("job_id");
ALTER TABLE public."financial_reports" ADD FOREIGN KEY ("restated_from_id") REFERENCES public."financial_reports" ("report_id");
ALTER TABLE public."observations" ADD FOREIGN KEY ("report_id") REFERENCES public."financial_reports" ("report_id");
ALTER TABLE public."observations" ADD FOREIGN KEY ("metric_id") REFERENCES public."metrics" ("metric_id");
ALTER TABLE public."documents" ADD FOREIGN KEY ("company_id") REFERENCES public."companies" ("company_id");
ALTER TABLE public."documents" ADD FOREIGN KEY ("period_id") REFERENCES public."reporting_periods" ("period_id");
ALTER TABLE public."documents" ADD FOREIGN KEY ("job_id") REFERENCES public."ingestion_jobs" ("job_id");
ALTER TABLE public."text_chunks" ADD FOREIGN KEY ("document_id") REFERENCES public."documents" ("document_id");
ALTER TABLE public."text_chunks" ADD FOREIGN KEY ("index_version_id") REFERENCES public."index_versions" ("index_version_id");
ALTER TABLE public."evidence" ADD FOREIGN KEY ("chunk_id") REFERENCES public."text_chunks" ("chunk_id");
ALTER TABLE public."evidence" ADD FOREIGN KEY ("observation_id") REFERENCES public."observations" ("observation_id");
ALTER TABLE public."evidence" ADD FOREIGN KEY ("price_id") REFERENCES public."price_bars" ("price_id");
ALTER TABLE public."evidence" ADD FOREIGN KEY ("extraction_id") REFERENCES public."graph_extractions" ("extraction_id");
ALTER TABLE public."evidence" ADD FOREIGN KEY ("company_id") REFERENCES public."companies" ("company_id");
ALTER TABLE public."evidence" ADD FOREIGN KEY ("period_id") REFERENCES public."reporting_periods" ("period_id");
ALTER TABLE public."calc_inputs" ADD FOREIGN KEY ("evidence_id") REFERENCES public."evidence" ("evidence_id");
ALTER TABLE public."calc_inputs" ADD FOREIGN KEY ("input_evidence_id") REFERENCES public."evidence" ("evidence_id");
ALTER TABLE public."graph_extractions" ADD FOREIGN KEY ("graph_version_id") REFERENCES public."graph_versions" ("graph_version_id");
ALTER TABLE public."graph_extractions" ADD FOREIGN KEY ("document_id") REFERENCES public."documents" ("document_id");
ALTER TABLE public."queries" ADD FOREIGN KEY ("user_id") REFERENCES public."users" ("user_id");
ALTER TABLE public."queries" ADD FOREIGN KEY ("run_id") REFERENCES public."evaluation_runs" ("run_id");
ALTER TABLE public."queries" ADD FOREIGN KEY ("corpus_version_id") REFERENCES public."corpus_versions" ("corpus_version_id");
ALTER TABLE public."queries" ADD FOREIGN KEY ("config_version_id") REFERENCES public."config_versions" ("config_version_id");
ALTER TABLE public."query_companies" ADD FOREIGN KEY ("query_id") REFERENCES public."queries" ("query_id");
ALTER TABLE public."query_companies" ADD FOREIGN KEY ("company_id") REFERENCES public."companies" ("company_id");
ALTER TABLE public."retrieval_results" ADD FOREIGN KEY ("query_id") REFERENCES public."queries" ("query_id");
ALTER TABLE public."retrieval_results" ADD FOREIGN KEY ("evidence_id") REFERENCES public."evidence" ("evidence_id");
ALTER TABLE public."gate_decisions" ADD FOREIGN KEY ("query_id") REFERENCES public."queries" ("query_id");
ALTER TABLE public."gate_decisions" ADD FOREIGN KEY ("reason_code") REFERENCES public."reason_codes" ("code");
ALTER TABLE public."gate_decision_evidence" ADD FOREIGN KEY ("decision_id") REFERENCES public."gate_decisions" ("decision_id");
ALTER TABLE public."gate_decision_evidence" ADD FOREIGN KEY ("evidence_id") REFERENCES public."evidence" ("evidence_id");
ALTER TABLE public."answers" ADD FOREIGN KEY ("query_id") REFERENCES public."queries" ("query_id");
ALTER TABLE public."answers" ADD FOREIGN KEY ("decision_id") REFERENCES public."gate_decisions" ("decision_id");
ALTER TABLE public."answers" ADD FOREIGN KEY ("reason_code") REFERENCES public."reason_codes" ("code");
ALTER TABLE public."claims" ADD FOREIGN KEY ("answer_id") REFERENCES public."answers" ("answer_id");
ALTER TABLE public."citations" ADD FOREIGN KEY ("claim_id") REFERENCES public."claims" ("claim_id");
ALTER TABLE public."citations" ADD FOREIGN KEY ("evidence_id") REFERENCES public."evidence" ("evidence_id");
ALTER TABLE public."claim_verifications" ADD FOREIGN KEY ("claim_id") REFERENCES public."claims" ("claim_id");
ALTER TABLE public."feedback" ADD FOREIGN KEY ("user_id") REFERENCES public."users" ("user_id");
ALTER TABLE public."feedback" ADD FOREIGN KEY ("query_id") REFERENCES public."queries" ("query_id");
ALTER TABLE public."feedback" ADD FOREIGN KEY ("citation_id") REFERENCES public."citations" ("citation_id");
ALTER TABLE public."feedback" ADD FOREIGN KEY ("evidence_id") REFERENCES public."evidence" ("evidence_id");
ALTER TABLE public."feedback" ADD FOREIGN KEY ("resolved_by") REFERENCES public."users" ("user_id");
ALTER TABLE public."corpus_versions" ADD FOREIGN KEY ("graph_version_id") REFERENCES public."graph_versions" ("graph_version_id");
ALTER TABLE public."corpus_versions" ADD FOREIGN KEY ("index_version_id") REFERENCES public."index_versions" ("index_version_id");
ALTER TABLE public."corpus_versions" ADD FOREIGN KEY ("frozen_by") REFERENCES public."users" ("user_id");
ALTER TABLE public."corpus_documents" ADD FOREIGN KEY ("corpus_version_id") REFERENCES public."corpus_versions" ("corpus_version_id");
ALTER TABLE public."corpus_documents" ADD FOREIGN KEY ("document_id") REFERENCES public."documents" ("document_id");
ALTER TABLE public."corpus_facts" ADD FOREIGN KEY ("corpus_version_id") REFERENCES public."corpus_versions" ("corpus_version_id");
ALTER TABLE public."corpus_facts" ADD FOREIGN KEY ("observation_id") REFERENCES public."observations" ("observation_id");
ALTER TABLE public."corpus_prices" ADD FOREIGN KEY ("corpus_version_id") REFERENCES public."corpus_versions" ("corpus_version_id");
ALTER TABLE public."corpus_prices" ADD FOREIGN KEY ("price_id") REFERENCES public."price_bars" ("price_id");
ALTER TABLE public."golden_sets" ADD FOREIGN KEY ("frozen_by") REFERENCES public."users" ("user_id");
ALTER TABLE public."golden_questions" ADD FOREIGN KEY ("golden_set_id") REFERENCES public."golden_sets" ("golden_set_id");
ALTER TABLE public."golden_questions" ADD FOREIGN KEY ("period_id") REFERENCES public."reporting_periods" ("period_id");
ALTER TABLE public."golden_questions" ADD FOREIGN KEY ("expected_reason_code") REFERENCES public."reason_codes" ("code");
ALTER TABLE public."golden_question_companies" ADD FOREIGN KEY ("question_id") REFERENCES public."golden_questions" ("question_id");
ALTER TABLE public."golden_question_companies" ADD FOREIGN KEY ("company_id") REFERENCES public."companies" ("company_id");
ALTER TABLE public."evaluation_runs" ADD FOREIGN KEY ("corpus_version_id") REFERENCES public."corpus_versions" ("corpus_version_id");
ALTER TABLE public."evaluation_runs" ADD FOREIGN KEY ("golden_set_id") REFERENCES public."golden_sets" ("golden_set_id");
ALTER TABLE public."evaluation_runs" ADD FOREIGN KEY ("config_version_id") REFERENCES public."config_versions" ("config_version_id");
ALTER TABLE public."evaluation_runs" ADD FOREIGN KEY ("triggered_by") REFERENCES public."users" ("user_id");
ALTER TABLE public."evaluation_results" ADD FOREIGN KEY ("run_id") REFERENCES public."evaluation_runs" ("run_id");
ALTER TABLE public."evaluation_results" ADD FOREIGN KEY ("question_id") REFERENCES public."golden_questions" ("question_id");
ALTER TABLE public."evaluation_results" ADD FOREIGN KEY ("answer_id") REFERENCES public."answers" ("answer_id");
ALTER TABLE public."usage_events" ADD FOREIGN KEY ("answer_id") REFERENCES public."answers" ("answer_id");
ALTER TABLE public."usage_events" ADD FOREIGN KEY ("run_id") REFERENCES public."evaluation_runs" ("run_id");
ALTER TABLE public."usage_events" ADD FOREIGN KEY ("graph_version_id") REFERENCES public."graph_versions" ("graph_version_id");
ALTER TABLE public."usage_events" ADD FOREIGN KEY ("index_version_id") REFERENCES public."index_versions" ("index_version_id");

COMMIT;
