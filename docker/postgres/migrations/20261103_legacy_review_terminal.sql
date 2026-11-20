-- Requires the graph_review_candidate_state guard from 20261103_graph_review_store.
-- No historical decision or source payload is changed.
CREATE OR REPLACE FUNCTION graph_metadata.guard_terminal_review() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,graph_metadata,public AS $$
DECLARE rejected boolean;
BEGIN
 INSERT INTO public.graph_review_candidate_state(candidate_id,ever_rejected)
 VALUES('legacy:'||NEW.extraction_id::text,NEW.decision='REJECTED' OR EXISTS(
   SELECT FROM graph_metadata.reviews WHERE extraction_id=NEW.extraction_id AND decision='REJECTED'))
 ON CONFLICT(candidate_id) DO UPDATE
 SET ever_rejected=graph_review_candidate_state.ever_rejected OR EXCLUDED.ever_rejected
 RETURNING ever_rejected INTO rejected;
 IF rejected AND NEW.decision<>'REJECTED' THEN
  RAISE EXCEPTION 'REJECTED is terminal; submit a corrected extraction' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS legacy_review_terminal ON graph_metadata.reviews;
CREATE TRIGGER legacy_review_terminal BEFORE INSERT ON graph_metadata.reviews
 FOR EACH ROW EXECUTE FUNCTION graph_metadata.guard_terminal_review();
