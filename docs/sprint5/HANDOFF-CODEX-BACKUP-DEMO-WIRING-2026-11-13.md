# Handoff Codex: company data on the web, schema sync and cleanup (13/11/2026)

Owner: Hưng. Codex does **Tasks 2, 3 and 4** of the plan `docs/superpowers/plans/2026-11-13-backup-demo-wiring.md`. Read that plan first; it holds the interfaces, tests and commands. This file only fixes scope, boundaries and how to hand back.

Hưng does Tasks 1, 5, 6 and 7 in parallel on another branch. Do not touch their files (list below).

## Branch

- Create `codex/company-data-wiring` from `origin/backup-demo` (`4544ba04` or newer): `git fetch origin && git switch -c codex/company-data-wiring origin/backup-demo`.
- Use a separate worktree if the main checkout is on another branch: `git worktree add ../FinMind-codex origin/backup-demo -b codex/company-data-wiring`.
- Commit after each task with the message given in the plan. **Do not push and do not open a PR.** Hưng reviews and pushes.

## Your tasks (from the plan)

- **Task 2:** schema sync and cleanup.
  - Add `daily_market_activity` to `docker/postgres/init/010_schema.sql`.
  - New migration `supabase/migrations/20261114000000_admin_serving_corpus.sql`.
  - `git rm -r tmp` and the 7 unused files `frontend/src/pages/admin/{auditMock,configurationMock,corpusMock,evaluationMock,sourcesMock,tracesMock,mock}.js`.
  - Add `**/.agent-state/`, `**/.work/`, `pytest-cache-files-*/` to `.gitignore`.
  - Do **not** delete root-level files (`chunks_thu.json`, `interactive_test.py`, `run_event_news.py`, `wbs16_extractor.py`, `test_wbs16_extractor.py`, `stock_news_kg_template.json`). List them in your report.
- **Task 3:** companies and financials API.
  - `backend/src/api/routers/companies.py`.
  - `get_company_financials` in `backend/src/financial/health_db.py`.
  - Tests in `backend/tests/test_companies_api.py`.
- **Task 4:** company pages use real data.
  - `frontend/src/pages/companies/api.js`, `detailApi.js`, `CompanyDetailPage.jsx`, delete `detailMock.js`.
  - Test in `frontend/tests/companyApi.test.js`.

## Boundaries

**Only you edit these files:** everything listed under Tasks 2–4 in the plan.

**You edit only the lines named here:**
- `backend/src/main.py`: add exactly two lines. Put `from .api.routers import companies` on a **new line directly after line 21** (`from .api.routers import admin_ingestion`). Put `app.include_router(companies.router)` on a **new line directly after** `app.include_router(admin_ingestion.router)`. Hưng adds his router lines elsewhere in the file, so the two branches merge without conflict.

**Do not touch these files (Hưng is editing them):**
- `backend/src/core/config.py`, `backend/src/api/routers/search.py`;
- the `lifespan` function in `backend/src/main.py`;
- `backend/src/api/routers/watchlist.py`, `backend/src/retrieval_orchestration/**`;
- `frontend/src/pages/{dashboard,watchlist,profile,research}/**`;
- `frontend/src/pages/companies/mock.js`: keep this file, because the dashboard still imports `companyCatalog` until Hưng's Task 6.

## Rules

- Tests never connect to the production DB `127.0.0.1:15433`. Use fakes, following `backend/tests/financial_db_fixture.py`, or the test DB `127.0.0.1:15434`.
- Never print or store credentials. The DB and tunnel passwords live only in `backend/.env`.
- Money values travel as decimal strings in VND (`value × scale`). Never use floats in the backend. The frontend divides by `1e9` only for display ("tỷ VNĐ").
- Every financial fact carries `status`: `VERIFIED` when `locator_json.unit_status == 'VERIFIED'`, else `UNVERIFIED`. The UI must show this status. Never present an unverified Vietcap number as checked against the PDF.
- New routes require `require_roles(*READ_ROLES)` from `backend/src/auth/authorization.py`.
- Reuse what exists:
  - `fetch_health_records`, `citation_for` and `get_financial_health` in `backend/src/financial/health_db.py`;
  - `_METRIC_LABELS` in `backend/src/b1_answering/evidence/grounded.py`;
  - `authorizedFetch` in `frontend/src/shared/api/authorization.js`.
  Do not add dependencies.

## Done when

- `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_companies_api.py backend/tests/test_financial_health_db.py backend/tests/test_financial_verification_schema.py -q` passes. Run from the repo root.
- `cd frontend && node --test tests/ && npm run build` passes.
- The full backend suite shows no new failures: `backend/.venv/Scripts/python.exe -m pytest backend/tests backend/src/b1_answering/tests -q -p no:cacheprovider --continue-on-collection-errors`. The 6 failures already known on `backup-demo` are allowed: 1 OCR test (Pillow missing) and 5 WBS02 tests (fixture files not committed).
- `grep -rn "detailMock" frontend/src` prints nothing.

## Report back (`docs/sprint5/REPORT-CODEX-BACKUP-DEMO-WIRING-2026-11-13.md`)

- The commits (hash and message), and the files changed per task.
- The test commands you ran, with their final pass/fail lines.
- The JSON returned by `/api/companies/FPT/financials` from a run against fakes, trimmed to 1 period.
- The root-level files you left in place, with a guess at their owner from `git log -1 --format=%an -- <file>`.
- Anything from the plan you could not do, and why.
