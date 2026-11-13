-- The corpus the Chat serves, shared by every backend that talks to this database.
-- Written by the admin (owner/operator role) when a corpus is activated or switched;
-- the runtime roles can only read it. One row, enforced by the CHECK on id.
CREATE TABLE IF NOT EXISTS public.admin_serving_corpus (
    id smallint PRIMARY KEY CHECK (id = 1),
    corpus_version_id uuid NOT NULL REFERENCES public.corpus_versions (corpus_version_id),
    index_version_id uuid NOT NULL REFERENCES public.index_versions (index_version_id),
    updated_at timestamptz NOT NULL DEFAULT now(),
    updated_by text NOT NULL
);

-- Same protection as the other tables: row level security on, no access except the policies below.
ALTER TABLE public.admin_serving_corpus ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE
    reader text;
BEGIN
    FOREACH reader IN ARRAY ARRAY['finmind_app_runtime', 'finmind_graph_reader'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = reader) THEN
            EXECUTE format('GRANT SELECT ON public.admin_serving_corpus TO %I', reader);
            IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public'
                           AND tablename = 'admin_serving_corpus' AND policyname = 'serving_read_' || reader) THEN
                EXECUTE format('CREATE POLICY %I ON public.admin_serving_corpus FOR SELECT TO %I USING (true)',
                               'serving_read_' || reader, reader);
            END IF;
        END IF;
    END LOOP;
END $$;
