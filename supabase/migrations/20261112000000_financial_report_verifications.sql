-- Append-only BCTC metadata verifications; the current row of a report is the newest by verified_at.
CREATE TABLE IF NOT EXISTS public.financial_report_verifications (
 verification_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 report_id uuid NOT NULL REFERENCES public.financial_reports(report_id),
 document_id uuid REFERENCES public.documents(document_id),
 job_id uuid REFERENCES public.ingestion_jobs(job_id),
 statement_scope varchar(20) NOT NULL DEFAULT 'UNKNOWN' CHECK (statement_scope IN ('CONSOLIDATED','SEPARATE','UNKNOWN')),
 audit_status varchar(20) NOT NULL DEFAULT 'UNKNOWN' CHECK (audit_status IN ('AUDITED','REVIEWED','NOT_STATED','UNKNOWN')),
 unit varchar(20),
 unit_status varchar(20) NOT NULL DEFAULT 'UNKNOWN' CHECK (unit_status IN ('VERIFIED','UNKNOWN')),
 period_basis varchar(30) NOT NULL DEFAULT 'UNKNOWN' CHECK (period_basis IN ('ANNUAL','STANDALONE_QUARTER','YEAR_TO_DATE','UNKNOWN')),
 comparison_basis varchar(20) NOT NULL DEFAULT 'UNKNOWN' CHECK (comparison_basis IN ('AS_REPORTED','RESTATED','UNKNOWN')),
 fiscal_label_convention varchar(20) NOT NULL DEFAULT 'UNKNOWN' CHECK (fiscal_label_convention IN ('CALENDAR','START_YEAR','END_YEAR','UNKNOWN')),
 period_start date,
 period_end date,
 fiscal_year_end varchar(5) CHECK (fiscal_year_end ~ '^(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$'),
 checks jsonb NOT NULL DEFAULT '{}'::jsonb,
 evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
 status varchar(20) NOT NULL CHECK (status IN ('VERIFIED','PARTIAL','MISMATCH')),
 verified_at timestamptz NOT NULL DEFAULT now(),
 supersedes_id uuid REFERENCES public.financial_report_verifications(verification_id)
);
CREATE INDEX IF NOT EXISTS financial_report_verifications_report_verified
 ON public.financial_report_verifications(report_id, verified_at DESC);
CREATE OR REPLACE FUNCTION public.financial_report_verifications_block_change() RETURNS trigger
 LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'append-only'; END $$;
DROP TRIGGER IF EXISTS financial_report_verifications_append_only ON public.financial_report_verifications;
CREATE TRIGGER financial_report_verifications_append_only
 BEFORE UPDATE OR DELETE ON public.financial_report_verifications
 FOR EACH ROW EXECUTE FUNCTION public.financial_report_verifications_block_change();
DROP TRIGGER IF EXISTS financial_report_verifications_no_truncate ON public.financial_report_verifications;
CREATE TRIGGER financial_report_verifications_no_truncate
 BEFORE TRUNCATE ON public.financial_report_verifications
 FOR EACH STATEMENT EXECUTE FUNCTION public.financial_report_verifications_block_change();
-- Same access pattern as the other financial tables on the VPS, minus UPDATE/DELETE/TRUNCATE (append-only).
-- Roles are skipped when absent (local/test clusters).
DO $$
BEGIN
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'finmind_developer') THEN
  GRANT SELECT, INSERT ON public.financial_report_verifications TO finmind_developer;
 END IF;
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'finmind_graph_reader') THEN
  GRANT SELECT ON public.financial_report_verifications TO finmind_graph_reader;
 END IF;
END $$;
