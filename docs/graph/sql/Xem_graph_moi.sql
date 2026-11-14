-- Chỉ xem phiên mới để tránh đếm cả các phiên lịch sử.
SELECT * FROM public.graph_versions
WHERE graph_version_id = '6f1504e8-3eef-59e7-9d20-8c5957cb4427';

SELECT e.locator_json->>'symbol' AS company,
       e.locator_json->>'name' AS person_name,
       e.locator_json->>'position' AS position,
       g.relation_type, g.validation_status,
       e.locator_json->>'stage' AS event_stage,
       e.locator_json->>'effective_date' AS effective_date,
       e.locator_json->>'source_url' AS source_url,
       g.document_id,
       e.locator_json->'corpus_binding'->>'corpus_version_id' AS corpus_version_id,
       e.locator_json->'corpus_binding'->'chunk_bindings' AS source_chunks
FROM public.graph_extractions g
JOIN public.evidence e USING (extraction_id)
JOIN public.corpus_documents cd USING (document_id)
WHERE g.graph_version_id = '6f1504e8-3eef-59e7-9d20-8c5957cb4427'
  AND cd.corpus_version_id = 'b2550a0b-c423-5c50-9b15-6fb6af12e2c6'
ORDER BY company, person_name, position;
