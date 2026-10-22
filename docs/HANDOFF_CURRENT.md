# FinMind current handoff

## Latest deployment — 2026-10-22, 23:16 Asia/Bangkok

User approved deployment and overnight testing. V4 is registered FROZEN, index ACTIVE, and backend/.env now defaults to v4 with SOURCE_READ_BACKEND=supabase and no local snapshot path. No commit/push performed. Older notes below describe preceding stages; use current receipts for status.

- Corpus: 33d33730-0f0a-5274-a7f8-8d32a6be07e8; index: e3725b7d-1a39-5196-b000-3496dbab388f.
- Registered manifest SHA: 73f2e87a1cf5cd50a8fec3ee825e8bad211070c9e994b37c45a61ee86c6723c1.
- One metadata root deployed, reusing 43 pinned original payloads. No 676-source-copy plan, no chunk_text column, no schema addition.
- DB audit: 7,158 vectors / 675 documents; runtime reader reconstructed all 7,158 chunks from actual Supabase sources with hash guards intact. Membership: 72,096 financial facts + 737 historical prices. Other corpora preserved.
- 190 regression tests passed. Real HTTP: 40 questions + 3 source-family queries passed transport/source checks. Q31-Q39: all 12 requested evidence rows matched observation IDs, periods and release-rendered values. Q40 correctly empty; unknown corpus returns 409, not 500.
- Added conservative financial query constraints for explicit company/period and source metric labels, then vector ranking within candidates. This changes retrieval from unrestricted dense baseline; record query-code revision in benchmarking. No financial value/unit certification is inferred from aliases.
- FPT FY2024 and Q2/2026 numeric reader each selects one clean report with 160 rows. Historical VCB 2026-04-15 close=59.46, scale=1000, read from pinned raw bars.
- Backup of only the four prior release settings: backend/.tmp/pre-v4-release-settings.json, ignored by Git. Secrets and unrelated .env settings preserved.
- Member guide: docs/CORPUS_V4_QUICK_START.md. Morning: cd backend; npm run check:sources; npm run dev. Restart older backend processes to load new settings.
- Detailed results/limitations: outputs/corpus-v4-reuse-audit-20261022/Ket_qua_kiem_thu.md. PDF citation for Q21-Q29, full calculation/answer/refusal validation and unverified units remain outside this retrieval/source PASS. Do not claim all 40 final answers certified. No full crawler run or physical second-machine run.

Temporary GPU HTTP server on port 8014 was stopped after final checks to release GPU memory. Port 8000 was not running during verification. Start the normal backend with npm run dev when needed. No unrelated process was stopped.

Updated: 2026-10-22 21:07 (Asia/Ho_Chi_Minh)

## 1. Goal and decisions confirmed by the user

The goal is to let members search financial data without `SOURCE_CHANGED` failures,
while keeping source/hash checks strict and using the approved Excel workbook for
financial unit mapping.

Confirmed decisions:

- Keep the existing corpus-v2 immutable.
- Use append-only corpus releases; do not mutate a frozen corpus or its vectors.
- Keep all `clean-v1` financial data in the final release.
- Exclude financial data from the old `schema_version = 1.0` pipeline.
- Keep news, prices, companies, market indices, and the other non-financial sources.
- For clean rows that do not have an Excel mapping, keep the value but do not invent
  a unit and do not add the text `(đơn vị chưa xác minh)`.
- Apply the Excel mapping where available. The currently verified plan has 61 mapped
  rows: 60 `VERIFIED_SNAPSHOT` and 1 `WORKBOOK_APPROVED`.
- `WORKBOOK_APPROVED` is not a `VERIFIED_SNAPSHOT`; citation policy remains restricted
  for that status.
- Do not disable source fingerprints, content hashes, or fail-closed reconstruction.
- Do not expose credentials, tokens, or `.env` contents in this handoff.

## 2. Files changed or created

### Runtime and reconstruction

- `backend/src/documents/source_snapshot.py`
  - Loads and validates immutable source snapshots.
  - Resolves indexed text by source identity, locator, and content hash.
  - Fails closed on invalid, missing, or changed snapshot data.
- `backend/src/documents/core_snapshot.py`
  - Provides cached opt-in snapshot loading from `SOURCE_SNAPSHOT_PATH`.
- `backend/src/documents/repository.py`
  - Uses the configured immutable snapshot for release reconstruction before
    falling back to the legacy live-source path.
- `backend/src/documents/renderer_context.py`
  - Existing strict renderer-context validation remains in place.
- `backend/src/documents/chunk_reconstruction.py`
  - Existing strict `SOURCE_CHANGED`/hash validation remains in place.
- `backend/src/documents/corpus_manifest.py`
  - `read_manifest()` now passes the index identity into reconstruction lookup.
- `backend/src/documents/corpus_scope.py`
  - The corpus-v2 index-ID compatibility check is now limited to the
    `corpus-v2` label; corpus-v3/v4 use their registered corpus/index binding.
- `backend/src/core/config.py`
  - Added optional `source_snapshot_path` configuration.

### Clean renderer and release builders

- `backend/src/documents/db_chunking.py`
  - Added `db-financial-v4`.
  - The v4 financial renderer does not add the unverified warning text.
  - Existing renderer behavior for older versions remains covered by tests.
- `backend/scripts/prepare_workbook_corpus_release.py`
  - Builds the earlier full immutable release snapshot.
- `backend/scripts/build_workbook_ingest_manifest.py`
  - Converts an immutable snapshot into the append-only ingest manifest format.
- `backend/scripts/prepare_clean_mapped_release.py`
  - Builds the current clean-only financial rendering policy:
    all `clean-v1` rows are retained; only old schema-v1 financial rows are
    excluded; Excel mappings are applied where present.
- `backend/scripts/ingest_corpus_v2.py`
  - Added an immutable snapshot preflight option. The script still uses the
    append-only index insertion behavior and does not update/supersede old indexes.
- `backend/scripts/prepare_workbook_vector_plan.py`
  - Creates a no-write vector plan.

### Tests

- `backend/tests/test_source_snapshot.py`
  - Tests snapshot resolution and fail-closed locator/hash changes.
- Existing `backend/tests/test_chunk_reconstruction.py`,
  `backend/tests/test_corpus_manifest.py`, and corpus/API tests were run during
  the release work.

### Generated release artifacts

- `outputs/corpus-v3-workbook-approved-20261022/source-snapshot.json`
- `outputs/corpus-v3-workbook-approved-20261022/registered-manifest.json`
- `outputs/corpus-v3-workbook-approved-20261022/ingest-manifest.json`
- `outputs/corpus-v3-workbook-approved-20261022/ingest-progress.json`
- `outputs/corpus-v4-clean-mapped-20261022/source-snapshot.json`
- `outputs/corpus-v4-clean-mapped-20261022/release-manifest.json`
- `outputs/corpus-v4-clean-mapped-20261022/ingest-manifest.json`
- `outputs/corpus-v4-clean-mapped-20261022/ingest-progress.json`

## 3. Active corpus and corpus-v4 status

### Active and registered corpus

The last verified active release is:

```text
label: corpus-v3-workbook
corpus_version_id: 06171160-c31a-5ff7-8bf0-66308ad72520
index_version_id: 6e8dc44b-f682-5dfa-b0ed-a117deb2e963
manifest_sha256: 79a7aa2b5c33fc7d4d7cb96f674c562e5d9d2f1b55b812610ae90e8caf1485ab
corpus status: FROZEN
index status: ACTIVE
documents: 675
chunks: 15058
```

Corpus-v2 remains frozen and unchanged:

```text
corpus_version_id: 232fbd29-355f-5a77-ba28-a06b8d5ceb40
index_version_id: 434ef5e0-6516-578d-8d18-721d21347e01
manifest_sha256: 86e880eef3b39ddf2515951252025a8f58e700f80416ba24d6fabfe324362bd7
```

The project `.env` was changed earlier to point the default configuration to
corpus-v3 and its snapshot. The backend was subsequently stopped. The running
default after the next restart must be rechecked; do not assume a server process
is currently active.

### Corpus-v4

The current v4 policy artifact contains:

```text
release policy: keep all clean-v1; exclude schema-v1 financial; keep other sources
clean financial rows: 72096
Excel-mapped rows: 61
normal/schema-v1 financial rows: 0 in the selected clean input
documents: 675
chunks: 7158
```

The clean financial snapshot was checked to contain no `đơn vị chưa xác minh` text.
This is an offline artifact check, not yet an API check.

The v4 index is:

```text
index_version_id: e3725b7d-1a39-5196-b000-3496dbab388f
```

It is not registered, frozen, active, or configured as the default.

## 4. Ingest progress and how to check it

The v4 ingest was started with:

```powershell
cd C:\NhanhFrontend\FinMind
.\.venv\Scripts\python.exe backend\scripts\ingest_corpus_v2.py `
  --manifest outputs\corpus-v4-clean-mapped-20261022\ingest-manifest.json `
  --progress outputs\corpus-v4-clean-mapped-20261022\ingest-progress.json `
  --source-snapshot outputs\corpus-v4-clean-mapped-20261022\source-snapshot.json `
  --batch-size 8 --device cpu --apply
```

The progress file is:

`outputs/corpus-v4-clean-mapped-20261022/ingest-progress.json`

Last verified progress at handoff:

```text
status: BUILDING
completed: 5807
expected: 7158
newly_embedded: 4116
reused_exact_hash: 1691
elapsed_seconds: 9134
device: cpu
batch_size: 8
```

The last progress read is the source of truth for the numbers above. The process
state after that read was not independently confirmed as still running. Check it
before restarting; do not launch a second ingest against the same index while the
first one may still be active.

PowerShell check:

```powershell
Get-Content `
  C:\NhanhFrontend\FinMind\outputs\corpus-v4-clean-mapped-20261022\ingest-progress.json `
  -Raw
```

When `completed` reaches `expected` and status becomes
`VECTORS_WRITTEN_PENDING_VERIFICATION`, run a read-only vector audit. Verify:

- exactly 7,158 active chunks for the v4 index;
- all vectors have dimension 1024;
- every stored locator/content hash resolves from the v4 snapshot;
- no v4 financial text contains `đơn vị chưa xác minh`;
- corpus-v2 and corpus-v3 counts/statuses remain unchanged.

## 5. Verified Supabase changes

Verified writes already made:

- corpus-v3 index `6e8dc44b-f682-5dfa-b0ed-a117deb2e963` received 15,058
  append-only vector rows and its index was activated.
- corpus-v3 was registered as frozen with 675 document memberships.
- No corpus-v4 registration has been performed.
- No corpus-v4 index activation has been performed.
- No default corpus database setting was changed through Supabase.
- Corpus-v2 was not mutated.

The v4 ingest writes, if still running or already partly complete, are confined
to the new v4 `BUILDING` index and new append-only document/chunk rows. The exact
current database row count must be rechecked before any retry or registration.

## 6. Tests and known errors

Verified test results:

```text
test_source_snapshot.py + test_chunk_reconstruction.py: 18 passed
test_corpus_manifest.py + test_source_snapshot.py: 11 passed
test_api_corpus_search.py + test_corpus_manifest.py: 17 passed
test_chunk_reconstruction.py after renderer compatibility fix: 16 passed
clean snapshot text check: PASS
Python syntax checks for changed scripts/modules: PASS
```

Known issue fixed during the work:

- `read_manifest()` initially omitted `index_version_id`, causing
  `Archived financial source requires index identity`.
- `load_scope()` initially applied the corpus-v2 ID formula to corpus-v3;
  it now only applies that compatibility rule to the `corpus-v2` label.

Known remaining issues:

- The API result from corpus-v3 still showed the old financial text with
  `đơn vị chưa xác minh`; this is why v4 is being built.
- v4 has not yet passed DB vector audit, freeze, registration, activation,
  FPT `bsa90` API testing, or default switch.
- The backend was stopped at the last check; port 8000 was verified not to be
  listening. Frontend port 5173 was not verified as listening.
- The current ingest process state was not verified after the last progress read.

## 7. Next steps

1. Check whether the v4 ingest process is still alive and read the progress file.
2. If it stopped, inspect the final output and resume the same append-only
   command only after confirming the current DB/index inventory.
3. After 7,158 chunks are present, run read-only vector/hash/snapshot audit.
4. Generate a v4 registered manifest using the v4 snapshot path.
5. Register/freeze v4 and activate only after all preflight checks pass.
6. Run API smoke tests:
   - default corpus ID/index ID;
   - FPT Q2/2026 `RETAINED_EARNINGS` (`bsa90`);
   - no `đơn vị chưa xác minh` in returned financial text;
   - clean rows without Excel mapping remain values without an invented unit;
   - changed snapshot content fails closed.
7. Only after those tests pass, update the default configuration to v4 and
   restart the backend.

## 8. Actions requiring explicit user approval

Ask the user before:

- registering/freezing corpus-v4;
- activating the v4 index;
- changing the default corpus from corpus-v3 to corpus-v4;
- importing or changing financial configuration in Supabase;
- deleting or cleaning up the abandoned/partial v3 or v4 index rows;
- changing citation eligibility for `WORKBOOK_APPROVED`;
- changing the policy for clean rows without Excel mappings;
- running any destructive database operation.


## Update: shared versioned source plan (2026-10-22)

The user superseded the per-member ZIP approach: backend must read versioned shared sources from Supabase, retaining hash guards. Source ZIP is now only an offline release artifact, not the desired member dependency.

Prepared locally (not deployed):
- backend/src/documents/shared_source.py normalizes frozen v4 documents into source sections, checks payload/root/index/corpus bindings and resolves exact locator spans.
- SOURCE_READ_BACKEND=supabase selects shared-source reading in repository; current default remains local and actual .env was not changed.
- backend/scripts/prepare_shared_source_plan.py has no apply mode. The plan contains 675 normalized-source payloads + one release root in existing raw_payloads (676 inserts, 15585845 canonical payload bytes). No new table/column, no text_chunks.chunk_text.
- This stores versioned normalized source text, not original PDF/JSON bytes and not vector-to-text decoding. It is derived from the frozen v4 snapshot and retains existing original payloads.
- READ ONLY ERD inspection verified required columns/job_id nullable; proposed URIs do not exist and have no current conflict.
- Every v4 chunk (7158) reconstructed offline with exact locator/hash. 44 tests passed including two independent fake DB clients without local file access. No claim of two real machines or deployed API success yet.
- Member doctor: cd backend; npm run check:sources. It uses only DB after approved deployment and requires registered FROZEN/ACTIVE corpus. No ZIP is required for this path.
- Read docs/CORPUS_V4_SHARED_SOURCES.md and outputs/corpus-v4-shared-source-plan-20261022/summary.json/source-plan.json before any write.

Approval still required for inserting the 676 source rows, registering/activating v4 and switching actual runtime settings. No apply script was run or provided for these actions. Prior authorization to resume v4 vector ingest is separate; it remains underway (latest observed REUSE_LOOKUP 704/1351; progress still 5807/7158). Do not launch another ingest worker. Never delete source releases still referenced by frozen corpus/citations independently of the retention agreement.

## Superseding update: reuse existing raw payloads (2026-10-22)

The user chose minimizing duplicate sources. DO NOT APPLY the old 676-row normalized-source plan; its source-plan.json/summary.json are explicitly marked SUPERSEDED_DO_NOT_APPLY.

READ ONLY audits now verified 419 clean financial reports + 234 news articles + 6 stock price histories + 3 market-index histories against 43 existing raw_payloads. 13 small profile field sets and bar indicators are the missing historical supplements. No financial values, article bodies or OHLCV are copied into the new plan.

Replacement: outputs/corpus-v4-reuse-audit-20261022/reuse-root.proposed.json is ONE raw_payloads metadata root (2428715 canonical JSON bytes). It pins existing payload IDs/stored/semantic hashes, deduplicated renderer/unit/label definitions, dates/indicator history and profile fields. Proposed ID 2c56f129-9ebf-559f-bb4b-cc287dffc452, SHA be789fe1389980c2d32e1f77d4837ce41c29332a856a6fb93615188cac83f280. Not inserted, runtime unchanged.

shared_source.py supports existing-clean-payload / existing-news-payload / existing-bars-payload / profile-version-metadata, with fingerprint/hash reconstruction. reused_source.py provides renderers and raw-payload semantic guard. verify_v4_reuse_plan.py used real original payloads read from DB with a simulated proposed root/registry: two fresh clients each 7158/7158 exact reconstructions, no runtime local snapshot; not a deployed HTTP/two-real-machines test. 49 regression tests passed.

Found a future recurrence cause: supabase_sink set STABLE_PAYLOAD_IDS=True and market/news ingestion overwrote raw payloads by path. Code now uses content-version IDs always, DO NOTHING plus exact readback conflict checks; sink flag false. This changes future ingest code only; no crawler or payload write ran in this task. Version growth/30-day source retention still needs alignment with supported corpus history.

Read docs/CORPUS_V4_REUSE_EXISTING_SOURCES.md. Still obtain user approval before inserting the ONE metadata root, registering/activating v4, or changing actual runtime source/default configuration. Prior vector-ingest authorization is separate.
