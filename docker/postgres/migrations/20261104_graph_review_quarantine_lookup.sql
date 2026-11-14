-- UPDATE ... WHERE review_id requires SELECT on that lookup column.
-- Reviewer still cannot INSERT quarantine rows or change immutable candidates.
GRANT SELECT(review_id) ON public.quarantine_records TO finmind_graph_reviewer;
