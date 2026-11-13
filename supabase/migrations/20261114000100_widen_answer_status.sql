-- answers.status holds answering statuses such as INSUFFICIENT_EVIDENCE and CLARIFICATION_STALLED (21 chars).
ALTER TABLE public.answers ALTER COLUMN status TYPE character varying(30);
