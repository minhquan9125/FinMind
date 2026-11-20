# Existing source-reader interface
Verified from complete resolve_result_rows in backend/src/documents/repository.py.
Original source SHA256: b15f6478c60c4251c49798b438734c755797a65cbd0972fd1591b986e2b9a0e6. Full original remains pinned by the workflow.
async resolve_result_rows(conn, rows) -> list[dict]: uses caller connection and transaction;
each row includes chunk_id, chunk_index, page, content_hash, locator_json.
Preserves row metadata, normalizes locator_json from JSON string to dict and adds text.
Source reconstruction metadata selects renderer/version and reuses loaded sources within the call.
Raises ReconstructionError with code for missing/changed source, invalid locator or hash mismatch.
Upload locator upload-source-v1 reads raw_payloads and checks source hash/page/index.
No original chunk_text fallback; no writes. Caller must handle failure without exposing raw exceptions.
Do not replace this existing reader. New module injects it for testing and calls it for build and final hits.
