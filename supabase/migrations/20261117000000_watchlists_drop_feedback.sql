-- Watchlist is now served from public.watchlists (GET/PUT/DELETE /api/watchlist).
-- public.feedback had no code and no rows, so it is removed. Safe to run more than once.

DROP TABLE IF EXISTS public.feedback;

ALTER TABLE public.watchlists ALTER COLUMN pinned_at SET DEFAULT now();

-- The owner role used by the backend bypasses row level security. A separate runtime role,
-- where one exists, gets the rows it needs; the API itself scopes every query to the signed-in user.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'finmind_app_runtime') THEN
        GRANT SELECT, INSERT, DELETE ON public.watchlists TO finmind_app_runtime;
        IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public'
                       AND tablename = 'watchlists' AND policyname = 'app_watchlist_rw') THEN
            CREATE POLICY app_watchlist_rw ON public.watchlists FOR ALL TO finmind_app_runtime
                USING (true) WITH CHECK (true);
        END IF;
    END IF;
END $$;
