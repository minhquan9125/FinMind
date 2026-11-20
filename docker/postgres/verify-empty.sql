-- Read-only checks: schemas/constraints exist and all application tables are empty.
BEGIN READ ONLY;
DO $verify$
DECLARE item record; total bigint; tables integer;
BEGIN
  SELECT count(*) INTO tables FROM pg_tables WHERE schemaname IN ('public','research_chat');
  IF tables <> 56 THEN RAISE EXCEPTION 'Expected 56 application tables, found %',tables; END IF;
  FOR item IN SELECT schemaname,tablename FROM pg_tables WHERE schemaname IN ('public','research_chat') LOOP
    EXECUTE format('SELECT count(*) FROM %I.%I',item.schemaname,item.tablename) INTO total;
    IF total <> 0 THEN RAISE EXCEPTION 'Table %.% is not empty: % rows',item.schemaname,item.tablename,total; END IF;
  END LOOP;
  IF EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='text_chunks' AND column_name='chunk_text') THEN
    RAISE EXCEPTION 'Legacy chunk_text must not be present';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector') THEN RAISE EXCEPTION 'pgvector missing'; END IF;
  RAISE NOTICE 'PASS: 56 empty application tables; pgvector enabled; no legacy chunk_text';
END $verify$;
SELECT '[1,0,0]'::vector <=> '[1,0,0]'::vector AS cosine_distance_expected_zero;
COMMIT;
