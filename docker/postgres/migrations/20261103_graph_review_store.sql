-- WBS06 persistence only. No source approval, identity resolution or Neo4j writes.
CREATE TABLE IF NOT EXISTS public.graph_review_results (
 review_id uuid PRIMARY KEY,
 graph_version_id uuid NOT NULL REFERENCES public.graph_versions(graph_version_id),
 candidate_id text NOT NULL,
 candidate_sha256 text NOT NULL CHECK(candidate_sha256 ~ '^[0-9a-f]{64}$'),
 candidate jsonb NOT NULL CHECK(jsonb_typeof(candidate)='object'),
 status text NOT NULL CHECK(status IN ('PENDING','APPROVED','REJECTED')),
 reasons jsonb NOT NULL CHECK(jsonb_typeof(reasons)='array'),
 evaluation jsonb NOT NULL CHECK(jsonb_typeof(evaluation)='object'),
 revision integer NOT NULL DEFAULT 1 CHECK(revision>0),
 created_by uuid NOT NULL REFERENCES public.users(user_id),
 created_at timestamptz NOT NULL DEFAULT now(),
 reviewed_by uuid REFERENCES public.users(user_id), reviewed_at timestamptz,
 UNIQUE(graph_version_id,candidate_id),
 CHECK(candidate->>'candidate_id'=candidate_id),
 CHECK(evaluation->>'candidate_id'=candidate_id),
 CHECK(evaluation->>'candidate_sha256'=candidate_sha256),
 CHECK(evaluation->>'status'=status), CHECK(evaluation->'reasons'=reasons)
);
CREATE TABLE IF NOT EXISTS public.graph_review_audit (
 audit_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 review_id uuid NOT NULL REFERENCES public.graph_review_results(review_id),
 actor_id uuid NOT NULL REFERENCES public.users(user_id),
 decision text NOT NULL CHECK(decision IN ('PENDING','APPROVED','REJECTED')),
 note text NOT NULL CHECK(length(trim(note))>0),
 evidence_confirmed boolean NOT NULL DEFAULT false,
 source_evaluation jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS graph_review_version_status ON public.graph_review_results(graph_version_id,status);
CREATE INDEX IF NOT EXISTS graph_review_candidate_status ON public.graph_review_results(candidate_id,status);
CREATE INDEX IF NOT EXISTS graph_review_audit_history ON public.graph_review_audit(review_id,created_at,audit_id);

-- A row per candidate makes terminal rejection serializable even when callers
-- use repeatable-read and review the same candidate in different graph versions.
CREATE TABLE IF NOT EXISTS public.graph_review_candidate_state (
 candidate_id text PRIMARY KEY, ever_rejected boolean NOT NULL DEFAULT false
);
DO $$ BEGIN
 IF NOT EXISTS(SELECT FROM pg_trigger WHERE tgname='graph_review_state_internal') THEN
  INSERT INTO public.graph_review_candidate_state(candidate_id,ever_rejected)
   SELECT candidate_id,bool_or(status='REJECTED') FROM public.graph_review_results GROUP BY candidate_id
   ON CONFLICT(candidate_id) DO UPDATE SET ever_rejected=graph_review_candidate_state.ever_rejected OR EXCLUDED.ever_rejected;
 END IF;
END $$;
CREATE OR REPLACE FUNCTION public.guard_graph_review_state() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' OR pg_trigger_depth()<2 THEN RAISE EXCEPTION 'Internal review state only'; END IF;
 IF TG_OP='UPDATE' AND (NEW.candidate_id<>OLD.candidate_id OR (OLD.ever_rejected AND NOT NEW.ever_rejected)) THEN
  RAISE EXCEPTION 'Terminal review state cannot be reset';
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS graph_review_state_internal ON public.graph_review_candidate_state;
CREATE TRIGGER graph_review_state_internal BEFORE INSERT OR UPDATE OR DELETE ON public.graph_review_candidate_state
 FOR EACH ROW EXECUTE FUNCTION public.guard_graph_review_state();

ALTER TABLE public.quarantine_records ADD COLUMN IF NOT EXISTS review_id uuid REFERENCES public.graph_review_results(review_id);
ALTER TABLE public.quarantine_records ADD COLUMN IF NOT EXISTS reasons jsonb;
ALTER TABLE public.quarantine_records ADD COLUMN IF NOT EXISTS candidate_payload jsonb;
ALTER TABLE public.quarantine_records ADD COLUMN IF NOT EXISTS evaluation_payload jsonb;
CREATE INDEX IF NOT EXISTS quarantine_graph_review ON public.quarantine_records(review_id);

DO $$ BEGIN
 IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='finmind_graph_intake') THEN
  CREATE ROLE finmind_graph_intake NOLOGIN NOSUPERUSER NOBYPASSRLS;
 END IF;
END $$;

-- Dedicated inactive audit principal: no password, application roles or login.
INSERT INTO public.users(user_id,username,full_name,is_active,created_at,updated_at)
 VALUES('e0679567-7344-5f81-bf20-4a4ed0c24c28','graph_intake_service',
 'Graph intake automation (no login; not a human reviewer)',false,now(),now())
 ON CONFLICT(user_id) DO NOTHING;
DO $$ BEGIN
 IF NOT EXISTS(SELECT FROM public.users WHERE user_id='e0679567-7344-5f81-bf20-4a4ed0c24c28'
 AND username='graph_intake_service' AND is_active=false AND password_hash IS NULL) THEN
  RAISE EXCEPTION 'Graph intake audit principal identity conflict';
 END IF;
END $$;

CREATE OR REPLACE FUNCTION public.guard_graph_review_transition() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE rejected boolean;
BEGIN
 PERFORM pg_advisory_xact_lock(hashtextextended(NEW.candidate_id,0));
 INSERT INTO public.graph_review_candidate_state(candidate_id,ever_rejected) VALUES(NEW.candidate_id,NEW.status='REJECTED')
  ON CONFLICT(candidate_id) DO UPDATE SET ever_rejected=graph_review_candidate_state.ever_rejected OR EXCLUDED.ever_rejected
  RETURNING ever_rejected INTO rejected;
 IF TG_OP='UPDATE' THEN
  IF ROW(NEW.review_id,NEW.graph_version_id,NEW.candidate_id,NEW.candidate_sha256,NEW.candidate,NEW.created_by,NEW.created_at)
     IS DISTINCT FROM ROW(OLD.review_id,OLD.graph_version_id,OLD.candidate_id,OLD.candidate_sha256,OLD.candidate,OLD.created_by,OLD.created_at) THEN
   RAISE EXCEPTION 'Immutable review candidate';
  END IF;
  IF OLD.status='REJECTED' OR NEW.revision<>OLD.revision+1 THEN
   RAISE EXCEPTION 'Terminal rejection or invalid review revision';
  END IF;
 END IF;
 IF NEW.status<>'REJECTED' AND rejected THEN
  RAISE EXCEPTION 'Rejected candidate cannot be reopened in another graph';
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS graph_review_transition ON public.graph_review_results;
CREATE TRIGGER graph_review_transition BEFORE INSERT OR UPDATE ON public.graph_review_results
 FOR EACH ROW EXECUTE FUNCTION public.guard_graph_review_transition();

CREATE OR REPLACE FUNCTION public.graph_review_audit_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Review audit is append-only'; END $$;
DROP TRIGGER IF EXISTS graph_review_audit_immutable ON public.graph_review_audit;
CREATE TRIGGER graph_review_audit_immutable BEFORE UPDATE OR DELETE ON public.graph_review_audit
 FOR EACH ROW EXECUTE FUNCTION public.graph_review_audit_immutable();

ALTER TABLE public.graph_review_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.graph_review_results FORCE ROW LEVEL SECURITY;
ALTER TABLE public.graph_review_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.graph_review_audit FORCE ROW LEVEL SECURITY;
DO $$ BEGIN
 IF NOT EXISTS(SELECT FROM pg_policies WHERE schemaname='public' AND tablename='graph_review_results' AND policyname='graph_review_read') THEN
  CREATE POLICY graph_review_read ON public.graph_review_results FOR SELECT
   TO finmind_graph_reader,finmind_graph_reviewer,finmind_graph_intake USING(true);
  CREATE POLICY graph_review_initial ON public.graph_review_results FOR INSERT TO finmind_graph_intake
   WITH CHECK(status IN ('PENDING','REJECTED') AND created_by=current_setting('app.graph_review_actor',true)::uuid);
  -- Repository uses SELECT FOR UPDATE. Permit locking its own intake rows, but
  -- no actual UPDATE can satisfy this role's WITH CHECK(false).
  CREATE POLICY graph_review_lock_only ON public.graph_review_results FOR UPDATE TO finmind_graph_intake
   USING(created_by=current_setting('app.graph_review_actor',true)::uuid) WITH CHECK(false);
  CREATE POLICY graph_review_decision ON public.graph_review_results FOR UPDATE TO finmind_graph_reviewer USING(true)
   WITH CHECK(reviewed_by=current_setting('app.graph_review_actor',true)::uuid);
  CREATE POLICY graph_review_audit_read ON public.graph_review_audit FOR SELECT
   TO finmind_graph_reader,finmind_graph_reviewer,finmind_graph_intake USING(true);
  CREATE POLICY graph_review_audit_insert ON public.graph_review_audit FOR INSERT
   TO finmind_graph_intake,finmind_graph_reviewer WITH CHECK(actor_id=current_setting('app.graph_review_actor',true)::uuid
    AND (decision<>'APPROVED' OR pg_has_role(current_user,'finmind_graph_reviewer','member')));
 END IF;
END $$;
-- Extend the existing quarantine table without opening legacy ingestion rows.
DO $$ BEGIN
 IF NOT EXISTS(SELECT FROM pg_policies WHERE schemaname='public' AND tablename='quarantine_records' AND policyname='graph_review_quarantine_insert') THEN
  CREATE POLICY graph_review_quarantine_insert ON public.quarantine_records FOR INSERT TO finmind_graph_intake
   WITH CHECK(review_id IS NOT NULL AND reviewed_by=current_setting('app.graph_review_actor',true)::uuid
    AND EXISTS(SELECT FROM public.graph_review_results r WHERE r.review_id=quarantine_records.review_id
       AND r.created_by=current_setting('app.graph_review_actor',true)::uuid
       AND r.status=quarantine_records.status AND r.candidate=quarantine_records.candidate_payload
       AND r.evaluation=quarantine_records.evaluation_payload));
  CREATE POLICY graph_review_quarantine_read ON public.quarantine_records FOR SELECT
   TO finmind_graph_intake,finmind_graph_reviewer USING(review_id IS NOT NULL);
  CREATE POLICY graph_review_quarantine_update ON public.quarantine_records FOR UPDATE TO finmind_graph_reviewer
   USING(review_id IS NOT NULL) WITH CHECK(review_id IS NOT NULL
    AND reviewed_by=current_setting('app.graph_review_actor',true)::uuid
    AND EXISTS(SELECT FROM public.graph_review_results r WHERE r.review_id=quarantine_records.review_id
       AND r.status=quarantine_records.status AND r.evaluation=quarantine_records.evaluation_payload));
 END IF;
END $$;
GRANT USAGE ON SCHEMA public TO finmind_graph_intake;
GRANT SELECT ON public.graph_review_results,public.graph_review_audit TO finmind_graph_reader,finmind_graph_intake,finmind_graph_reviewer;
GRANT SELECT,INSERT,UPDATE(ever_rejected) ON public.graph_review_candidate_state TO finmind_graph_intake,finmind_graph_reviewer;
GRANT INSERT ON public.graph_review_results,public.graph_review_audit TO finmind_graph_intake;
GRANT UPDATE(revision) ON public.graph_review_results TO finmind_graph_intake;
GRANT UPDATE ON public.graph_review_results TO finmind_graph_reviewer;
GRANT INSERT ON public.graph_review_audit TO finmind_graph_reviewer;
GRANT USAGE,SELECT ON SEQUENCE public.graph_review_audit_audit_id_seq TO finmind_graph_intake,finmind_graph_reviewer;
GRANT INSERT,SELECT(record_id) ON public.quarantine_records TO finmind_graph_intake;
GRANT SELECT(record_id),UPDATE(reason_code,status,reviewed_by,reviewed_at,reasons,evaluation_payload) ON public.quarantine_records TO finmind_graph_reviewer;
