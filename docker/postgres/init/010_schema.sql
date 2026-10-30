-- Schema-only snapshot of live Supabase application catalogs. No table data.

-- Source PostgreSQL 17.6

BEGIN;

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;

CREATE SCHEMA IF NOT EXISTS research_chat;

DO $roles$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='finmind_chat_runtime') THEN CREATE ROLE finmind_chat_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS; END IF; END $roles$;

GRANT finmind_chat_runtime TO CURRENT_USER;

GRANT USAGE ON SCHEMA research_chat TO finmind_chat_runtime;

CREATE TABLE "public"."answers" (
    "answer_id" uuid NOT NULL,
    "query_id" uuid,
    "attempt" integer,
    "decision_id" uuid,
    "answer_text" text,
    "status" character varying(20),
    "reason_code" character varying(50),
    "model_name" character varying(50),
    "prompt_version" character varying(30),
    "latency_ms" integer,
    "latency_breakdown_json" jsonb,
    "created_at" timestamp with time zone
);

ALTER TABLE "public"."answers" ADD CONSTRAINT "answers_pkey" PRIMARY KEY (answer_id);

CREATE TABLE "public"."audit_logs" (
    "audit_id" uuid NOT NULL,
    "user_id" uuid,
    "action" character varying(50),
    "resource_type" character varying(50),
    "resource_id" character varying(64),
    "outcome" character varying(20),
    "ip_address" inet,
    "user_agent" text,
    "metadata_json" jsonb,
    "created_at" timestamp with time zone
);

ALTER TABLE "public"."audit_logs" ADD CONSTRAINT "audit_logs_pkey" PRIMARY KEY (audit_id);

CREATE TABLE "public"."calc_inputs" (
    "evidence_id" uuid NOT NULL,
    "input_evidence_id" uuid NOT NULL,
    "position" integer
);

ALTER TABLE "public"."calc_inputs" ADD CONSTRAINT "calc_inputs_pkey" PRIMARY KEY (evidence_id, input_evidence_id);

CREATE TABLE "public"."citations" (
    "citation_id" uuid NOT NULL,
    "claim_id" uuid,
    "evidence_id" uuid,
    "ordinal" integer
);

ALTER TABLE "public"."citations" ADD CONSTRAINT "citations_pkey" PRIMARY KEY (citation_id);

CREATE TABLE "public"."claim_verifications" (
    "verification_id" uuid NOT NULL,
    "claim_id" uuid,
    "check_type" character varying(10),
    "passed" boolean,
    "detail" jsonb,
    "created_at" timestamp with time zone
);

ALTER TABLE "public"."claim_verifications" ADD CONSTRAINT "claim_verifications_pkey" PRIMARY KEY (verification_id);

CREATE TABLE "public"."claims" (
    "claim_id" uuid NOT NULL,
    "answer_id" uuid,
    "ordinal" integer,
    "claim_text" text,
    "claim_type" character varying(10),
    "verification_status" character varying(20)
);

ALTER TABLE "public"."claims" ADD CONSTRAINT "claims_pkey" PRIMARY KEY (claim_id);

CREATE TABLE "public"."companies" (
    "company_id" uuid NOT NULL,
    "symbol" character varying(10),
    "company_name" character varying(255),
    "industry_type" character varying(30),
    "sector" character varying(100),
    "exchange" character varying(10),
    "is_active" boolean
);

ALTER TABLE "public"."companies" ADD CONSTRAINT "companies_pkey" PRIMARY KEY (company_id);

ALTER TABLE "public"."companies" ADD CONSTRAINT "companies_symbol_key" UNIQUE (symbol);

CREATE TABLE "public"."config_versions" (
    "config_version_id" uuid NOT NULL,
    "version_label" character varying(30),
    "description" text,
    "is_active" boolean,
    "frozen_at" timestamp with time zone,
    "frozen_by" uuid,
    "created_by" uuid,
    "created_at" timestamp with time zone
);

ALTER TABLE "public"."config_versions" ADD CONSTRAINT "config_versions_pkey" PRIMARY KEY (config_version_id);

CREATE TABLE "public"."corpus_documents" (
    "corpus_version_id" uuid NOT NULL,
    "document_id" uuid NOT NULL,
    "document_hash" character(64)
);

ALTER TABLE "public"."corpus_documents" ADD CONSTRAINT "corpus_documents_pkey" PRIMARY KEY (corpus_version_id, document_id);

CREATE TABLE "public"."corpus_facts" (
    "corpus_version_id" uuid NOT NULL,
    "observation_id" uuid NOT NULL,
    "value_hash" character(64)
);

ALTER TABLE "public"."corpus_facts" ADD CONSTRAINT "corpus_facts_pkey" PRIMARY KEY (corpus_version_id, observation_id);

CREATE TABLE "public"."corpus_prices" (
    "corpus_version_id" uuid NOT NULL,
    "price_id" uuid NOT NULL,
    "value_hash" character(64)
);

ALTER TABLE "public"."corpus_prices" ADD CONSTRAINT "corpus_prices_pkey" PRIMARY KEY (corpus_version_id, price_id);

CREATE TABLE "public"."corpus_versions" (
    "corpus_version_id" uuid NOT NULL,
    "version_label" character varying(30),
    "description" text,
    "graph_version_id" uuid,
    "index_version_id" uuid,
    "frozen_at" timestamp with time zone,
    "frozen_by" uuid,
    "manifest_sha256" character(64),
    "status" character varying(20)
);

ALTER TABLE "public"."corpus_versions" ADD CONSTRAINT "corpus_versions_pkey" PRIMARY KEY (corpus_version_id);

CREATE TABLE "public"."documents" (
    "document_id" uuid NOT NULL,
    "company_id" uuid,
    "period_id" uuid,
    "job_id" uuid,
    "doc_type" character varying(30),
    "file_type" character varying(10),
    "title" character varying(500),
    "storage_uri" text,
    "source_url" text,
    "external_id" character varying(100),
    "language" character(2),
    "page_count" integer,
    "file_size" bigint,
    "published_at" timestamp with time zone,
    "sha256" character(64),
    "parse_status" character varying(20),
    "created_at" timestamp with time zone
);

ALTER TABLE "public"."documents" ADD CONSTRAINT "documents_pkey" PRIMARY KEY (document_id);

CREATE TABLE "public"."evaluation_results" (
    "result_id" uuid NOT NULL,
    "run_id" uuid,
    "question_id" uuid,
    "answer_id" uuid,
    "gate_status" character varying(20),
    "correctness" double precision,
    "faithfulness" double precision,
    "citation_correctness" double precision,
    "citation_coverage" double precision,
    "context_precision" double precision,
    "retrieval_recall_json" jsonb,
    "latency_ms" integer,
    "trace_id" character varying(64),
    "created_at" timestamp with time zone
);

ALTER TABLE "public"."evaluation_results" ADD CONSTRAINT "evaluation_results_pkey" PRIMARY KEY (result_id);

CREATE TABLE "public"."evaluation_runs" (
    "run_id" uuid NOT NULL,
    "run_type" character varying(12),
    "configuration" character varying(10),
    "corpus_version_id" uuid,
    "golden_set_id" uuid,
    "config_version_id" uuid,
    "model_name" character varying(50),
    "judge_model" character varying(50),
    "ragas_version" character varying(20),
    "temperature" double precision,
    "seed" integer,
    "prompt_version" character varying(30),
    "prompt_hash" character varying(64),
    "git_commit" character varying(40),
    "config_json" jsonb,
    "status" character varying(20),
    "started_at" timestamp with time zone,
    "completed_at" timestamp with time zone,
    "triggered_by" uuid
);

ALTER TABLE "public"."evaluation_runs" ADD CONSTRAINT "evaluation_runs_pkey" PRIMARY KEY (run_id);

CREATE TABLE "public"."evidence" (
    "evidence_id" uuid NOT NULL,
    "evidence_type" character varying(10),
    "chunk_id" uuid,
    "observation_id" uuid,
    "price_id" uuid,
    "extraction_id" uuid,
    "calc_formula" text,
    "company_id" uuid,
    "period_id" uuid,
    "unit" character varying(20),
    "statement_scope" character varying(20),
    "source_sha256" character(64),
    "locator_json" jsonb,
    "created_at" timestamp with time zone
);

ALTER TABLE "public"."evidence" ADD CONSTRAINT "evidence_pkey" PRIMARY KEY (evidence_id);

CREATE TABLE "public"."feedback" (
    "feedback_id" uuid NOT NULL,
    "user_id" uuid,
    "query_id" uuid,
    "citation_id" uuid,
    "evidence_id" uuid,
    "issue_type" character varying(30),
    "comment" text,
    "status" character varying(20),
    "created_at" timestamp with time zone,
    "resolved_at" timestamp with time zone,
    "resolved_by" uuid
);

ALTER TABLE "public"."feedback" ADD CONSTRAINT "feedback_pkey" PRIMARY KEY (feedback_id);

CREATE TABLE "public"."financial_reports" (
    "report_id" uuid NOT NULL,
    "company_id" uuid,
    "period_id" uuid,
    "document_id" uuid,
    "payload_id" uuid,
    "job_id" uuid,
    "statement_scope" character varying(20),
    "audit_status" character varying(20),
    "report_version" integer,
    "restated_from_id" uuid,
    "published_at" date
);

ALTER TABLE "public"."financial_reports" ADD CONSTRAINT "financial_reports_pkey" PRIMARY KEY (report_id);

CREATE TABLE "public"."gate_decision_evidence" (
    "decision_id" uuid NOT NULL,
    "evidence_id" uuid NOT NULL,
    "role" character varying(10),
    "drop_reason" character varying(50)
);

ALTER TABLE "public"."gate_decision_evidence" ADD CONSTRAINT "gate_decision_evidence_pkey" PRIMARY KEY (decision_id, evidence_id);

CREATE TABLE "public"."gate_decisions" (
    "decision_id" uuid NOT NULL,
    "query_id" uuid,
    "attempt" integer,
    "status" character varying(20),
    "reason_code" character varying(50),
    "reference_date" date,
    "is_stale" boolean,
    "has_conflict" boolean,
    "mandatory_branch_missing" boolean,
    "relevance_score" double precision,
    "created_at" timestamp with time zone
);

ALTER TABLE "public"."gate_decisions" ADD CONSTRAINT "gate_decisions_pkey" PRIMARY KEY (decision_id);

CREATE TABLE "public"."golden_question_companies" (
    "question_id" uuid NOT NULL,
    "company_id" uuid NOT NULL
);

ALTER TABLE "public"."golden_question_companies" ADD CONSTRAINT "golden_question_companies_pkey" PRIMARY KEY (question_id, company_id);

CREATE TABLE "public"."golden_questions" (
    "question_id" uuid NOT NULL,
    "golden_set_id" uuid,
    "question_text" text,
    "question_type" character varying(20),
    "period_id" uuid,
    "answerability" character varying(20),
    "expected_status" character varying(20),
    "expected_reason_code" character varying(50),
    "reference_answer" text,
    "canonical_numeric_value" numeric(24,4),
    "gold_locators_json" jsonb,
    "dataset_split" character varying(10),
    "created_at" timestamp with time zone
);

ALTER TABLE "public"."golden_questions" ADD CONSTRAINT "golden_questions_pkey" PRIMARY KEY (question_id);

CREATE TABLE "public"."golden_sets" (
    "golden_set_id" uuid NOT NULL,
    "version_label" character varying(20),
    "description" text,
    "frozen_at" timestamp with time zone,
    "frozen_by" uuid,
    "created_at" timestamp with time zone
);

ALTER TABLE "public"."golden_sets" ADD CONSTRAINT "golden_sets_pkey" PRIMARY KEY (golden_set_id);

CREATE TABLE "public"."graph_extractions" (
    "extraction_id" uuid NOT NULL,
    "graph_version_id" uuid,
    "document_id" uuid,
    "method" character varying(10),
    "subject" character varying(255),
    "relation_type" character varying(50),
    "object" character varying(255),
    "source_span" text,
    "validation_status" character varying(20),
    "reject_reason" character varying(100),
    "neo4j_edge_key" character varying(100),
    "manual_check" character varying(10)
);

ALTER TABLE "public"."graph_extractions" ADD CONSTRAINT "graph_extractions_pkey" PRIMARY KEY (extraction_id);

CREATE TABLE "public"."graph_versions" (
    "graph_version_id" uuid NOT NULL,
    "built_at" timestamp with time zone,
    "node_count" integer,
    "edge_count" integer,
    "status" character varying(20)
);

ALTER TABLE "public"."graph_versions" ADD CONSTRAINT "graph_versions_pkey" PRIMARY KEY (graph_version_id);

CREATE TABLE "public"."index_versions" (
    "index_version_id" uuid NOT NULL,
    "chunker_version" character varying(30),
    "chunk_size" integer,
    "chunk_overlap" integer,
    "embedding_model" character varying(50),
    "built_at" timestamp with time zone,
    "status" character varying(20)
);

ALTER TABLE "public"."index_versions" ADD CONSTRAINT "index_versions_pkey" PRIMARY KEY (index_version_id);

CREATE TABLE "public"."ingestion_jobs" (
    "job_id" uuid NOT NULL,
    "source_id" uuid,
    "triggered_by" uuid,
    "trigger_type" character varying(20),
    "status" character varying(20),
    "schema_version" character varying(20),
    "started_at" timestamp with time zone,
    "finished_at" timestamp with time zone,
    "records_ok" integer,
    "records_quarantined" integer
);

ALTER TABLE "public"."ingestion_jobs" ADD CONSTRAINT "ingestion_jobs_pkey" PRIMARY KEY (job_id);

CREATE TABLE "public"."market_index_bars" (
    "index_symbol" character varying(20) NOT NULL,
    "index_name" character varying(100),
    "exchange" character varying(10),
    "trade_date" date NOT NULL,
    "open" numeric(18,4),
    "high" numeric(18,4),
    "low" numeric(18,4),
    "close" numeric(18,4),
    "volume" bigint,
    "sma20" numeric,
    "sma50" numeric,
    "rsi14" numeric,
    "payload_id" uuid
);

ALTER TABLE "public"."market_index_bars" ADD CONSTRAINT "market_index_bars_pkey" PRIMARY KEY (index_symbol, trade_date);

CREATE TABLE "public"."market_live_snapshots" (
    "symbol" character varying(20) NOT NULL,
    "instrument_type" character varying(10) DEFAULT 'stock'::character varying NOT NULL,
    "fetched_at" timestamp with time zone,
    "data" jsonb NOT NULL,
    "payload_id" uuid,
    "updated_at" timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE "public"."market_live_snapshots" ADD CONSTRAINT "market_live_snapshots_pkey" PRIMARY KEY (symbol);

CREATE TABLE "public"."metric_aliases" (
    "alias_id" uuid NOT NULL,
    "metric_id" uuid,
    "raw_label" character varying(255),
    "industry_scope" character varying(30)
);

ALTER TABLE "public"."metric_aliases" ADD CONSTRAINT "metric_aliases_pkey" PRIMARY KEY (alias_id);

CREATE TABLE "public"."metrics" (
    "metric_id" uuid NOT NULL,
    "code" character varying(100),
    "canonical_name" character varying(255),
    "section" character varying(30),
    "default_unit" character varying(20),
    "industry_scope" character varying(30),
    "mapping_status" character varying(20)
);

ALTER TABLE "public"."metrics" ADD CONSTRAINT "metrics_pkey" PRIMARY KEY (metric_id);

CREATE TABLE "public"."news_articles" (
    "article_id" uuid NOT NULL,
    "source" character varying(30) NOT NULL,
    "external_id" character varying(64),
    "url" text NOT NULL,
    "title" text NOT NULL,
    "description" text,
    "content" text,
    "published_at" timestamp with time zone,
    "crawled_at" timestamp with time zone,
    "symbols" text[] DEFAULT '{}'::text[] NOT NULL,
    "attachments" jsonb DEFAULT '[]'::jsonb NOT NULL,
    "marker" character varying(20),
    "cross_check" jsonb,
    "payload_id" uuid,
    "created_at" timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE "public"."news_articles" ADD CONSTRAINT "news_articles_pkey" PRIMARY KEY (article_id);

CREATE TABLE "public"."observations" (
    "observation_id" uuid NOT NULL,
    "report_id" uuid,
    "metric_id" uuid,
    "value" numeric,
    "unit" character varying(20),
    "scale" integer,
    "currency" character(3),
    "locator_json" jsonb
);

ALTER TABLE "public"."observations" ADD CONSTRAINT "observations_pkey" PRIMARY KEY (observation_id);

CREATE TABLE "public"."permissions" (
    "permission_id" uuid NOT NULL,
    "resource" character varying(50),
    "action" character varying(30),
    "description" text
);

ALTER TABLE "public"."permissions" ADD CONSTRAINT "permissions_pkey" PRIMARY KEY (permission_id);

CREATE TABLE "public"."price_bars" (
    "price_id" uuid NOT NULL,
    "company_id" uuid,
    "payload_id" uuid,
    "trade_date" date,
    "is_adjusted" boolean,
    "price_scale" integer,
    "open" numeric(18,4),
    "high" numeric(18,4),
    "low" numeric(18,4),
    "close" numeric(18,4),
    "volume" bigint
);

ALTER TABLE "public"."price_bars" ADD CONSTRAINT "price_bars_pkey" PRIMARY KEY (price_id);

CREATE TABLE "public"."price_indicators" (
    "price_id" uuid NOT NULL,
    "sma20" numeric,
    "sma50" numeric,
    "rsi14" numeric,
    "updated_at" timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE "public"."price_indicators" ADD CONSTRAINT "price_indicators_pkey" PRIMARY KEY (price_id);

CREATE TABLE "public"."quarantine_records" (
    "record_id" uuid NOT NULL,
    "job_id" uuid,
    "payload_id" uuid,
    "extraction_id" uuid,
    "entity_type" character varying(30),
    "reason_code" character varying(50),
    "status" character varying(20),
    "reviewed_by" uuid,
    "reviewed_at" timestamp with time zone
);

ALTER TABLE "public"."quarantine_records" ADD CONSTRAINT "quarantine_records_pkey" PRIMARY KEY (record_id);

CREATE TABLE "public"."queries" (
    "query_id" uuid NOT NULL,
    "user_id" uuid,
    "run_id" uuid,
    "question_text" text,
    "question_type" character varying(20),
    "configuration" character varying(10),
    "corpus_version_id" uuid,
    "config_version_id" uuid,
    "language" character(2),
    "trace_id" character varying(64),
    "created_at" timestamp with time zone,
    "deleted_at" timestamp with time zone
);

ALTER TABLE "public"."queries" ADD CONSTRAINT "queries_pkey" PRIMARY KEY (query_id);

CREATE TABLE "public"."query_companies" (
    "query_id" uuid NOT NULL,
    "company_id" uuid NOT NULL
);

ALTER TABLE "public"."query_companies" ADD CONSTRAINT "query_companies_pkey" PRIMARY KEY (query_id, company_id);

CREATE TABLE "public"."raw_payloads" (
    "payload_id" uuid NOT NULL,
    "job_id" uuid,
    "source_uri" text,
    "sha256" character(64),
    "payload" jsonb,
    "stored_at" timestamp with time zone
);

ALTER TABLE "public"."raw_payloads" ADD CONSTRAINT "raw_payloads_pkey" PRIMARY KEY (payload_id);

CREATE TABLE "public"."reason_codes" (
    "code" character varying(50) NOT NULL,
    "result_status" character varying(20),
    "user_message" text,
    "is_active" boolean
);

ALTER TABLE "public"."reason_codes" ADD CONSTRAINT "reason_codes_pkey" PRIMARY KEY (code);

CREATE TABLE "public"."reporting_periods" (
    "period_id" uuid NOT NULL,
    "period_code" character varying(10),
    "fiscal_year" integer,
    "quarter" smallint,
    "period_type" character varying(10),
    "start_date" date,
    "end_date" date
);

ALTER TABLE "public"."reporting_periods" ADD CONSTRAINT "reporting_periods_period_code_key" UNIQUE (period_code);

ALTER TABLE "public"."reporting_periods" ADD CONSTRAINT "reporting_periods_pkey" PRIMARY KEY (period_id);

CREATE TABLE "public"."retrieval_results" (
    "result_id" uuid NOT NULL,
    "query_id" uuid,
    "attempt" integer,
    "evidence_id" uuid,
    "branch" character varying(10),
    "score" double precision,
    "rank_before" integer,
    "rank_after" integer
);

ALTER TABLE "public"."retrieval_results" ADD CONSTRAINT "retrieval_results_pkey" PRIMARY KEY (result_id);

CREATE TABLE "public"."role_permissions" (
    "role_id" uuid NOT NULL,
    "permission_id" uuid NOT NULL
);

ALTER TABLE "public"."role_permissions" ADD CONSTRAINT "role_permissions_pkey" PRIMARY KEY (role_id, permission_id);

CREATE TABLE "public"."roles" (
    "role_id" uuid NOT NULL,
    "role_code" character varying(30),
    "description" text
);

ALTER TABLE "public"."roles" ADD CONSTRAINT "roles_pkey" PRIMARY KEY (role_id);

CREATE TABLE "public"."sessions" (
    "session_id" uuid NOT NULL,
    "user_id" uuid,
    "token_hash" character varying(128),
    "issued_at" timestamp with time zone,
    "expires_at" timestamp with time zone,
    "revoked_at" timestamp with time zone,
    "ip_address" inet,
    "user_agent" text
);

ALTER TABLE "public"."sessions" ADD CONSTRAINT "sessions_pkey" PRIMARY KEY (session_id);

CREATE TABLE "public"."sources" (
    "source_id" uuid NOT NULL,
    "name" character varying(100),
    "source_type" character varying(30),
    "base_url" text,
    "approval_status" character varying(20),
    "approved_by" uuid,
    "approved_at" timestamp with time zone,
    "scope_note" text,
    "is_enabled" boolean
);

ALTER TABLE "public"."sources" ADD CONSTRAINT "sources_pkey" PRIMARY KEY (source_id);

CREATE TABLE "public"."system_configs" (
    "config_version_id" uuid NOT NULL,
    "config_key" character varying(100) NOT NULL,
    "config_value" jsonb
);

ALTER TABLE "public"."system_configs" ADD CONSTRAINT "system_configs_pkey" PRIMARY KEY (config_version_id, config_key);

CREATE TABLE "public"."text_chunks" (
    "chunk_id" uuid NOT NULL,
    "document_id" uuid NOT NULL,
    "index_version_id" uuid NOT NULL,
    "chunk_index" integer NOT NULL,
    "page_number" integer,
    "section_label" character varying(255),
    "token_count" integer,
    "char_start" integer,
    "char_end" integer,
    "content_hash" character(64),
    "embedding" public.vector(1024) NOT NULL,
    "created_at" timestamp with time zone,
    "locator_json" jsonb,
    "superseded_at" timestamp with time zone,
    "superseded_by_chunk_id" uuid
);

ALTER TABLE "public"."text_chunks" ADD CONSTRAINT "text_chunks_pkey" PRIMARY KEY (chunk_id);

CREATE TABLE "public"."usage_events" (
    "usage_id" uuid NOT NULL,
    "event_type" character varying(20),
    "model_name" character varying(50),
    "answer_id" uuid,
    "run_id" uuid,
    "graph_version_id" uuid,
    "index_version_id" uuid,
    "tokens_input" bigint,
    "tokens_output" bigint,
    "cost_usd" numeric(10,6),
    "recorded_at" timestamp with time zone
);

ALTER TABLE "public"."usage_events" ADD CONSTRAINT "usage_events_pkey" PRIMARY KEY (usage_id);

CREATE TABLE "public"."user_roles" (
    "user_id" uuid NOT NULL,
    "role_id" uuid NOT NULL
);

ALTER TABLE "public"."user_roles" ADD CONSTRAINT "user_roles_pkey" PRIMARY KEY (user_id, role_id);

CREATE TABLE "public"."users" (
    "user_id" uuid NOT NULL,
    "email" character varying(255),
    "username" character varying(50),
    "password_hash" character varying(255),
    "full_name" character varying(255),
    "is_active" boolean,
    "last_login_at" timestamp with time zone,
    "updated_at" timestamp with time zone,
    "created_at" timestamp with time zone
);

ALTER TABLE "public"."users" ADD CONSTRAINT "users_pkey" PRIMARY KEY (user_id);

CREATE TABLE "public"."watchlists" (
    "user_id" uuid NOT NULL,
    "company_id" uuid NOT NULL,
    "pinned_at" timestamp with time zone
);

ALTER TABLE "public"."watchlists" ADD CONSTRAINT "watchlists_pkey" PRIMARY KEY (user_id, company_id);

CREATE TABLE "research_chat"."conversations" (
    "conversation_id" uuid NOT NULL,
    "user_id" uuid NOT NULL,
    "schema_version" text DEFAULT '1.0'::text NOT NULL,
    "revision" integer DEFAULT 0 NOT NULL,
    "started_at" timestamp with time zone NOT NULL,
    "saved_at" timestamp with time zone NOT NULL,
    "metadata" jsonb NOT NULL,
    "preview" text DEFAULT ''::text NOT NULL,
    "turns" integer DEFAULT 0 NOT NULL,
    "lease_id" uuid,
    "lease_expires_at" timestamp with time zone
);

ALTER TABLE "research_chat"."conversations" ADD CONSTRAINT "conversations_check" CHECK ((lease_id IS NULL) = (lease_expires_at IS NULL));

ALTER TABLE "research_chat"."conversations" ADD CONSTRAINT "conversations_conversation_id_user_id_key" UNIQUE (conversation_id, user_id);

ALTER TABLE "research_chat"."conversations" ADD CONSTRAINT "conversations_metadata_check" CHECK (jsonb_typeof(metadata) = 'object'::text);

ALTER TABLE "research_chat"."conversations" ADD CONSTRAINT "conversations_pkey" PRIMARY KEY (conversation_id);

ALTER TABLE "research_chat"."conversations" ADD CONSTRAINT "conversations_preview_check" CHECK (length(preview) <= 80);

ALTER TABLE "research_chat"."conversations" ADD CONSTRAINT "conversations_revision_check" CHECK (revision >= 0);

ALTER TABLE "research_chat"."conversations" ADD CONSTRAINT "conversations_schema_version_check" CHECK (schema_version = '1.0'::text);

ALTER TABLE "research_chat"."conversations" ADD CONSTRAINT "conversations_turns_check" CHECK (turns >= 0);

CREATE TABLE "research_chat"."messages" (
    "conversation_id" uuid NOT NULL,
    "user_id" uuid NOT NULL,
    "position" integer NOT NULL,
    "payload" jsonb NOT NULL
);

ALTER TABLE "research_chat"."messages" ADD CONSTRAINT "messages_payload_check" CHECK (jsonb_typeof(payload) = 'object'::text AND payload ?& ARRAY['role'::text, 'content'::text, 'timestamp'::text] AND jsonb_typeof(payload -> 'role'::text) = 'string'::text AND ((payload ->> 'role'::text) = ANY (ARRAY['user'::text, 'assistant'::text])) AND jsonb_typeof(payload -> 'content'::text) = 'string'::text AND jsonb_typeof(payload -> 'timestamp'::text) = 'string'::text AND octet_length(payload::text) <= 2097152);

ALTER TABLE "research_chat"."messages" ADD CONSTRAINT "messages_pkey" PRIMARY KEY (conversation_id, "position");

ALTER TABLE "research_chat"."messages" ADD CONSTRAINT "messages_position_check" CHECK ("position" >= 0 AND "position" < 2000);

CREATE TABLE "research_chat"."schema_migrations" (
    "version" text NOT NULL,
    "sha256" text NOT NULL,
    "applied_at" timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE "research_chat"."schema_migrations" ADD CONSTRAINT "schema_migrations_pkey" PRIMARY KEY (version);

ALTER TABLE "public"."answers" ADD CONSTRAINT "answers_decision_id_fkey" FOREIGN KEY (decision_id) REFERENCES public.gate_decisions(decision_id);

ALTER TABLE "public"."answers" ADD CONSTRAINT "answers_query_id_fkey" FOREIGN KEY (query_id) REFERENCES public.queries(query_id);

ALTER TABLE "public"."answers" ADD CONSTRAINT "answers_reason_code_fkey" FOREIGN KEY (reason_code) REFERENCES public.reason_codes(code);

ALTER TABLE "public"."audit_logs" ADD CONSTRAINT "audit_logs_user_id_fkey" FOREIGN KEY (user_id) REFERENCES public.users(user_id);

ALTER TABLE "public"."calc_inputs" ADD CONSTRAINT "calc_inputs_evidence_id_fkey" FOREIGN KEY (evidence_id) REFERENCES public.evidence(evidence_id);

ALTER TABLE "public"."calc_inputs" ADD CONSTRAINT "calc_inputs_input_evidence_id_fkey" FOREIGN KEY (input_evidence_id) REFERENCES public.evidence(evidence_id);

ALTER TABLE "public"."citations" ADD CONSTRAINT "citations_claim_id_fkey" FOREIGN KEY (claim_id) REFERENCES public.claims(claim_id);

ALTER TABLE "public"."citations" ADD CONSTRAINT "citations_evidence_id_fkey" FOREIGN KEY (evidence_id) REFERENCES public.evidence(evidence_id);

ALTER TABLE "public"."claim_verifications" ADD CONSTRAINT "claim_verifications_claim_id_fkey" FOREIGN KEY (claim_id) REFERENCES public.claims(claim_id);

ALTER TABLE "public"."claims" ADD CONSTRAINT "claims_answer_id_fkey" FOREIGN KEY (answer_id) REFERENCES public.answers(answer_id);

ALTER TABLE "public"."config_versions" ADD CONSTRAINT "config_versions_created_by_fkey" FOREIGN KEY (created_by) REFERENCES public.users(user_id);

ALTER TABLE "public"."config_versions" ADD CONSTRAINT "config_versions_frozen_by_fkey" FOREIGN KEY (frozen_by) REFERENCES public.users(user_id);

ALTER TABLE "public"."corpus_documents" ADD CONSTRAINT "corpus_documents_corpus_version_id_fkey" FOREIGN KEY (corpus_version_id) REFERENCES public.corpus_versions(corpus_version_id);

ALTER TABLE "public"."corpus_documents" ADD CONSTRAINT "corpus_documents_document_id_fkey" FOREIGN KEY (document_id) REFERENCES public.documents(document_id);

ALTER TABLE "public"."corpus_facts" ADD CONSTRAINT "corpus_facts_corpus_version_id_fkey" FOREIGN KEY (corpus_version_id) REFERENCES public.corpus_versions(corpus_version_id);

ALTER TABLE "public"."corpus_facts" ADD CONSTRAINT "corpus_facts_observation_id_fkey" FOREIGN KEY (observation_id) REFERENCES public.observations(observation_id);

ALTER TABLE "public"."corpus_prices" ADD CONSTRAINT "corpus_prices_corpus_version_id_fkey" FOREIGN KEY (corpus_version_id) REFERENCES public.corpus_versions(corpus_version_id);

ALTER TABLE "public"."corpus_prices" ADD CONSTRAINT "corpus_prices_price_id_fkey" FOREIGN KEY (price_id) REFERENCES public.price_bars(price_id);

ALTER TABLE "public"."corpus_versions" ADD CONSTRAINT "corpus_versions_frozen_by_fkey" FOREIGN KEY (frozen_by) REFERENCES public.users(user_id);

ALTER TABLE "public"."corpus_versions" ADD CONSTRAINT "corpus_versions_graph_version_id_fkey" FOREIGN KEY (graph_version_id) REFERENCES public.graph_versions(graph_version_id);

ALTER TABLE "public"."corpus_versions" ADD CONSTRAINT "corpus_versions_index_version_id_fkey" FOREIGN KEY (index_version_id) REFERENCES public.index_versions(index_version_id);

ALTER TABLE "public"."documents" ADD CONSTRAINT "documents_company_id_fkey" FOREIGN KEY (company_id) REFERENCES public.companies(company_id);

ALTER TABLE "public"."documents" ADD CONSTRAINT "documents_job_id_fkey" FOREIGN KEY (job_id) REFERENCES public.ingestion_jobs(job_id);

ALTER TABLE "public"."documents" ADD CONSTRAINT "documents_period_id_fkey" FOREIGN KEY (period_id) REFERENCES public.reporting_periods(period_id);

ALTER TABLE "public"."evaluation_results" ADD CONSTRAINT "evaluation_results_answer_id_fkey" FOREIGN KEY (answer_id) REFERENCES public.answers(answer_id);

ALTER TABLE "public"."evaluation_results" ADD CONSTRAINT "evaluation_results_question_id_fkey" FOREIGN KEY (question_id) REFERENCES public.golden_questions(question_id);

ALTER TABLE "public"."evaluation_results" ADD CONSTRAINT "evaluation_results_run_id_fkey" FOREIGN KEY (run_id) REFERENCES public.evaluation_runs(run_id);

ALTER TABLE "public"."evaluation_runs" ADD CONSTRAINT "evaluation_runs_config_version_id_fkey" FOREIGN KEY (config_version_id) REFERENCES public.config_versions(config_version_id);

ALTER TABLE "public"."evaluation_runs" ADD CONSTRAINT "evaluation_runs_corpus_version_id_fkey" FOREIGN KEY (corpus_version_id) REFERENCES public.corpus_versions(corpus_version_id);

ALTER TABLE "public"."evaluation_runs" ADD CONSTRAINT "evaluation_runs_golden_set_id_fkey" FOREIGN KEY (golden_set_id) REFERENCES public.golden_sets(golden_set_id);

ALTER TABLE "public"."evaluation_runs" ADD CONSTRAINT "evaluation_runs_triggered_by_fkey" FOREIGN KEY (triggered_by) REFERENCES public.users(user_id);

ALTER TABLE "public"."evidence" ADD CONSTRAINT "evidence_chunk_id_fkey" FOREIGN KEY (chunk_id) REFERENCES public.text_chunks(chunk_id);

ALTER TABLE "public"."evidence" ADD CONSTRAINT "evidence_company_id_fkey" FOREIGN KEY (company_id) REFERENCES public.companies(company_id);

ALTER TABLE "public"."evidence" ADD CONSTRAINT "evidence_extraction_id_fkey" FOREIGN KEY (extraction_id) REFERENCES public.graph_extractions(extraction_id);

ALTER TABLE "public"."evidence" ADD CONSTRAINT "evidence_observation_id_fkey" FOREIGN KEY (observation_id) REFERENCES public.observations(observation_id);

ALTER TABLE "public"."evidence" ADD CONSTRAINT "evidence_period_id_fkey" FOREIGN KEY (period_id) REFERENCES public.reporting_periods(period_id);

ALTER TABLE "public"."evidence" ADD CONSTRAINT "evidence_price_id_fkey" FOREIGN KEY (price_id) REFERENCES public.price_bars(price_id);

ALTER TABLE "public"."feedback" ADD CONSTRAINT "feedback_citation_id_fkey" FOREIGN KEY (citation_id) REFERENCES public.citations(citation_id);

ALTER TABLE "public"."feedback" ADD CONSTRAINT "feedback_evidence_id_fkey" FOREIGN KEY (evidence_id) REFERENCES public.evidence(evidence_id);

ALTER TABLE "public"."feedback" ADD CONSTRAINT "feedback_query_id_fkey" FOREIGN KEY (query_id) REFERENCES public.queries(query_id);

ALTER TABLE "public"."feedback" ADD CONSTRAINT "feedback_resolved_by_fkey" FOREIGN KEY (resolved_by) REFERENCES public.users(user_id);

ALTER TABLE "public"."feedback" ADD CONSTRAINT "feedback_user_id_fkey" FOREIGN KEY (user_id) REFERENCES public.users(user_id);

ALTER TABLE "public"."financial_reports" ADD CONSTRAINT "financial_reports_company_id_fkey" FOREIGN KEY (company_id) REFERENCES public.companies(company_id);

ALTER TABLE "public"."financial_reports" ADD CONSTRAINT "financial_reports_document_id_fkey" FOREIGN KEY (document_id) REFERENCES public.documents(document_id);

ALTER TABLE "public"."financial_reports" ADD CONSTRAINT "financial_reports_job_id_fkey" FOREIGN KEY (job_id) REFERENCES public.ingestion_jobs(job_id);

ALTER TABLE "public"."financial_reports" ADD CONSTRAINT "financial_reports_payload_id_fkey" FOREIGN KEY (payload_id) REFERENCES public.raw_payloads(payload_id);

ALTER TABLE "public"."financial_reports" ADD CONSTRAINT "financial_reports_period_id_fkey" FOREIGN KEY (period_id) REFERENCES public.reporting_periods(period_id);

ALTER TABLE "public"."financial_reports" ADD CONSTRAINT "financial_reports_restated_from_id_fkey" FOREIGN KEY (restated_from_id) REFERENCES public.financial_reports(report_id);

ALTER TABLE "public"."gate_decision_evidence" ADD CONSTRAINT "gate_decision_evidence_decision_id_fkey" FOREIGN KEY (decision_id) REFERENCES public.gate_decisions(decision_id);

ALTER TABLE "public"."gate_decision_evidence" ADD CONSTRAINT "gate_decision_evidence_evidence_id_fkey" FOREIGN KEY (evidence_id) REFERENCES public.evidence(evidence_id);

ALTER TABLE "public"."gate_decisions" ADD CONSTRAINT "gate_decisions_query_id_fkey" FOREIGN KEY (query_id) REFERENCES public.queries(query_id);

ALTER TABLE "public"."gate_decisions" ADD CONSTRAINT "gate_decisions_reason_code_fkey" FOREIGN KEY (reason_code) REFERENCES public.reason_codes(code);

ALTER TABLE "public"."golden_question_companies" ADD CONSTRAINT "golden_question_companies_company_id_fkey" FOREIGN KEY (company_id) REFERENCES public.companies(company_id);

ALTER TABLE "public"."golden_question_companies" ADD CONSTRAINT "golden_question_companies_question_id_fkey" FOREIGN KEY (question_id) REFERENCES public.golden_questions(question_id);

ALTER TABLE "public"."golden_questions" ADD CONSTRAINT "golden_questions_expected_reason_code_fkey" FOREIGN KEY (expected_reason_code) REFERENCES public.reason_codes(code);

ALTER TABLE "public"."golden_questions" ADD CONSTRAINT "golden_questions_golden_set_id_fkey" FOREIGN KEY (golden_set_id) REFERENCES public.golden_sets(golden_set_id);

ALTER TABLE "public"."golden_questions" ADD CONSTRAINT "golden_questions_period_id_fkey" FOREIGN KEY (period_id) REFERENCES public.reporting_periods(period_id);

ALTER TABLE "public"."golden_sets" ADD CONSTRAINT "golden_sets_frozen_by_fkey" FOREIGN KEY (frozen_by) REFERENCES public.users(user_id);

ALTER TABLE "public"."graph_extractions" ADD CONSTRAINT "graph_extractions_document_id_fkey" FOREIGN KEY (document_id) REFERENCES public.documents(document_id);

ALTER TABLE "public"."graph_extractions" ADD CONSTRAINT "graph_extractions_graph_version_id_fkey" FOREIGN KEY (graph_version_id) REFERENCES public.graph_versions(graph_version_id);

ALTER TABLE "public"."ingestion_jobs" ADD CONSTRAINT "ingestion_jobs_source_id_fkey" FOREIGN KEY (source_id) REFERENCES public.sources(source_id);

ALTER TABLE "public"."ingestion_jobs" ADD CONSTRAINT "ingestion_jobs_triggered_by_fkey" FOREIGN KEY (triggered_by) REFERENCES public.users(user_id);

ALTER TABLE "public"."market_index_bars" ADD CONSTRAINT "market_index_bars_payload_id_fkey" FOREIGN KEY (payload_id) REFERENCES public.raw_payloads(payload_id);

ALTER TABLE "public"."market_live_snapshots" ADD CONSTRAINT "market_live_snapshots_payload_id_fkey" FOREIGN KEY (payload_id) REFERENCES public.raw_payloads(payload_id);

ALTER TABLE "public"."metric_aliases" ADD CONSTRAINT "metric_aliases_metric_id_fkey" FOREIGN KEY (metric_id) REFERENCES public.metrics(metric_id);

ALTER TABLE "public"."news_articles" ADD CONSTRAINT "news_articles_payload_id_fkey" FOREIGN KEY (payload_id) REFERENCES public.raw_payloads(payload_id);

ALTER TABLE "public"."observations" ADD CONSTRAINT "observations_metric_id_fkey" FOREIGN KEY (metric_id) REFERENCES public.metrics(metric_id);

ALTER TABLE "public"."observations" ADD CONSTRAINT "observations_report_id_fkey" FOREIGN KEY (report_id) REFERENCES public.financial_reports(report_id);

ALTER TABLE "public"."price_bars" ADD CONSTRAINT "price_bars_company_id_fkey" FOREIGN KEY (company_id) REFERENCES public.companies(company_id);

ALTER TABLE "public"."price_bars" ADD CONSTRAINT "price_bars_payload_id_fkey" FOREIGN KEY (payload_id) REFERENCES public.raw_payloads(payload_id);

ALTER TABLE "public"."price_indicators" ADD CONSTRAINT "price_indicators_price_id_fkey" FOREIGN KEY (price_id) REFERENCES public.price_bars(price_id) ON DELETE CASCADE;

ALTER TABLE "public"."quarantine_records" ADD CONSTRAINT "quarantine_records_extraction_id_fkey" FOREIGN KEY (extraction_id) REFERENCES public.graph_extractions(extraction_id);

ALTER TABLE "public"."quarantine_records" ADD CONSTRAINT "quarantine_records_job_id_fkey" FOREIGN KEY (job_id) REFERENCES public.ingestion_jobs(job_id);

ALTER TABLE "public"."quarantine_records" ADD CONSTRAINT "quarantine_records_payload_id_fkey" FOREIGN KEY (payload_id) REFERENCES public.raw_payloads(payload_id);

ALTER TABLE "public"."quarantine_records" ADD CONSTRAINT "quarantine_records_reviewed_by_fkey" FOREIGN KEY (reviewed_by) REFERENCES public.users(user_id);

ALTER TABLE "public"."queries" ADD CONSTRAINT "queries_config_version_id_fkey" FOREIGN KEY (config_version_id) REFERENCES public.config_versions(config_version_id);

ALTER TABLE "public"."queries" ADD CONSTRAINT "queries_corpus_version_id_fkey" FOREIGN KEY (corpus_version_id) REFERENCES public.corpus_versions(corpus_version_id);

ALTER TABLE "public"."queries" ADD CONSTRAINT "queries_run_id_fkey" FOREIGN KEY (run_id) REFERENCES public.evaluation_runs(run_id);

ALTER TABLE "public"."queries" ADD CONSTRAINT "queries_user_id_fkey" FOREIGN KEY (user_id) REFERENCES public.users(user_id);

ALTER TABLE "public"."query_companies" ADD CONSTRAINT "query_companies_company_id_fkey" FOREIGN KEY (company_id) REFERENCES public.companies(company_id);

ALTER TABLE "public"."query_companies" ADD CONSTRAINT "query_companies_query_id_fkey" FOREIGN KEY (query_id) REFERENCES public.queries(query_id);

ALTER TABLE "public"."raw_payloads" ADD CONSTRAINT "raw_payloads_job_id_fkey" FOREIGN KEY (job_id) REFERENCES public.ingestion_jobs(job_id);

ALTER TABLE "public"."retrieval_results" ADD CONSTRAINT "retrieval_results_evidence_id_fkey" FOREIGN KEY (evidence_id) REFERENCES public.evidence(evidence_id);

ALTER TABLE "public"."retrieval_results" ADD CONSTRAINT "retrieval_results_query_id_fkey" FOREIGN KEY (query_id) REFERENCES public.queries(query_id);

ALTER TABLE "public"."role_permissions" ADD CONSTRAINT "role_permissions_permission_id_fkey" FOREIGN KEY (permission_id) REFERENCES public.permissions(permission_id);

ALTER TABLE "public"."role_permissions" ADD CONSTRAINT "role_permissions_role_id_fkey" FOREIGN KEY (role_id) REFERENCES public.roles(role_id);

ALTER TABLE "public"."sessions" ADD CONSTRAINT "sessions_user_id_fkey" FOREIGN KEY (user_id) REFERENCES public.users(user_id) ON DELETE CASCADE;

ALTER TABLE "public"."sources" ADD CONSTRAINT "sources_approved_by_fkey" FOREIGN KEY (approved_by) REFERENCES public.users(user_id);

ALTER TABLE "public"."system_configs" ADD CONSTRAINT "system_configs_config_version_id_fkey" FOREIGN KEY (config_version_id) REFERENCES public.config_versions(config_version_id);

ALTER TABLE "public"."text_chunks" ADD CONSTRAINT "text_chunks_document_id_fkey" FOREIGN KEY (document_id) REFERENCES public.documents(document_id);

ALTER TABLE "public"."text_chunks" ADD CONSTRAINT "text_chunks_index_version_id_fkey" FOREIGN KEY (index_version_id) REFERENCES public.index_versions(index_version_id);

ALTER TABLE "public"."usage_events" ADD CONSTRAINT "usage_events_answer_id_fkey" FOREIGN KEY (answer_id) REFERENCES public.answers(answer_id);

ALTER TABLE "public"."usage_events" ADD CONSTRAINT "usage_events_graph_version_id_fkey" FOREIGN KEY (graph_version_id) REFERENCES public.graph_versions(graph_version_id);

ALTER TABLE "public"."usage_events" ADD CONSTRAINT "usage_events_index_version_id_fkey" FOREIGN KEY (index_version_id) REFERENCES public.index_versions(index_version_id);

ALTER TABLE "public"."usage_events" ADD CONSTRAINT "usage_events_run_id_fkey" FOREIGN KEY (run_id) REFERENCES public.evaluation_runs(run_id);

ALTER TABLE "public"."user_roles" ADD CONSTRAINT "user_roles_role_id_fkey" FOREIGN KEY (role_id) REFERENCES public.roles(role_id);

ALTER TABLE "public"."user_roles" ADD CONSTRAINT "user_roles_user_id_fkey" FOREIGN KEY (user_id) REFERENCES public.users(user_id) ON DELETE CASCADE;

ALTER TABLE "public"."watchlists" ADD CONSTRAINT "watchlists_company_id_fkey" FOREIGN KEY (company_id) REFERENCES public.companies(company_id);

ALTER TABLE "public"."watchlists" ADD CONSTRAINT "watchlists_user_id_fkey" FOREIGN KEY (user_id) REFERENCES public.users(user_id);

ALTER TABLE "research_chat"."conversations" ADD CONSTRAINT "conversations_user_id_fkey" FOREIGN KEY (user_id) REFERENCES public.users(user_id) ON DELETE CASCADE;

ALTER TABLE "research_chat"."messages" ADD CONSTRAINT "messages_conversation_id_user_id_fkey" FOREIGN KEY (conversation_id, user_id) REFERENCES research_chat.conversations(conversation_id, user_id) ON DELETE CASCADE;

CREATE UNIQUE INDEX uq_documents_sha256 ON public.documents USING btree (sha256);

CREATE INDEX idx_news_articles_published_at ON public.news_articles USING btree (published_at DESC);

CREATE INDEX idx_news_articles_symbols ON public.news_articles USING gin (symbols);

CREATE UNIQUE INDEX uq_news_articles_source_url ON public.news_articles USING btree (source, url);

CREATE UNIQUE INDEX uq_text_chunks_current_position ON public.text_chunks USING btree (index_version_id, document_id, chunk_index) WHERE (superseded_at IS NULL);

CREATE INDEX chat_owner_saved_idx ON research_chat.conversations USING btree (user_id, saved_at DESC, conversation_id);

CREATE INDEX chat_message_owner_idx ON research_chat.messages USING btree (user_id, conversation_id, "position");

ALTER TABLE "public"."answers" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."audit_logs" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."calc_inputs" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."citations" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."claim_verifications" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."claims" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."companies" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."config_versions" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."corpus_documents" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."corpus_facts" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."corpus_prices" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."corpus_versions" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."documents" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."evaluation_results" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."evaluation_runs" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."evidence" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."feedback" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."financial_reports" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."gate_decision_evidence" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."gate_decisions" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."golden_question_companies" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."golden_questions" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."golden_sets" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."graph_extractions" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."graph_versions" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."index_versions" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."ingestion_jobs" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."market_index_bars" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."market_live_snapshots" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."metric_aliases" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."metrics" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."news_articles" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."observations" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."permissions" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."price_bars" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."price_indicators" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."quarantine_records" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."queries" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."query_companies" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."raw_payloads" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."reason_codes" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."reporting_periods" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."retrieval_results" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."role_permissions" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."roles" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."sessions" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."sources" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."system_configs" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."text_chunks" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."usage_events" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."user_roles" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."users" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."watchlists" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "research_chat"."conversations" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "research_chat"."conversations" FORCE ROW LEVEL SECURITY;

ALTER TABLE "research_chat"."messages" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "research_chat"."messages" FORCE ROW LEVEL SECURITY;

CREATE POLICY "conversation_owner" ON "research_chat"."conversations" AS PERMISSIVE FOR ALL TO "finmind_chat_runtime" USING ((user_id = (NULLIF(current_setting('app.chat_user_id'::text, true), ''::text))::uuid)) WITH CHECK ((user_id = (NULLIF(current_setting('app.chat_user_id'::text, true), ''::text))::uuid));

CREATE POLICY "message_owner" ON "research_chat"."messages" AS PERMISSIVE FOR ALL TO "finmind_chat_runtime" USING ((user_id = (NULLIF(current_setting('app.chat_user_id'::text, true), ''::text))::uuid)) WITH CHECK ((user_id = (NULLIF(current_setting('app.chat_user_id'::text, true), ''::text))::uuid));

GRANT DELETE ON TABLE "research_chat"."conversations" TO finmind_chat_runtime;

GRANT INSERT ON TABLE "research_chat"."conversations" TO finmind_chat_runtime;

GRANT SELECT ON TABLE "research_chat"."conversations" TO finmind_chat_runtime;

GRANT UPDATE ON TABLE "research_chat"."conversations" TO finmind_chat_runtime;

GRANT DELETE ON TABLE "research_chat"."messages" TO finmind_chat_runtime;

GRANT INSERT ON TABLE "research_chat"."messages" TO finmind_chat_runtime;

GRANT SELECT ON TABLE "research_chat"."messages" TO finmind_chat_runtime;

GRANT UPDATE ON TABLE "research_chat"."messages" TO finmind_chat_runtime;

COMMIT;
