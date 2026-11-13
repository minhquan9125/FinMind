# Nối dữ liệu thật lên web và vá nền `backup-demo` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the known security gaps and schema drift on `backup-demo`, and replace the web pages that still show fixture data (company list, company financials, watchlist, profile, dashboard) with data already stored in Postgres. Also log every chat turn into the existing trace tables.

**Architecture:**
- New backend routers follow the existing pattern: `APIRouter` with `require_roles(*READ_ROLES)` and `get_pool()` from `core.db`.
- Financial numbers reuse `financial/health_db.py`, which already reads BCTC observations merged with PDF verification.
- Frontend API modules keep their exported function names, so the pages change as little as possible. They switch from fixtures to `authorizedFetch`.
- The dashboard and profile reuse existing endpoints and `AuthContext`. No new endpoint is added for them.

**Tech Stack:** FastAPI + asyncpg (Python 3.13, `backend/.venv`), React + Vite, `node --test` for frontend unit tests, pytest.

**Spec:** `docs/sprint5/AUDIT-PLAN-BACKUP-DEMO-2026-11-13.md` (sections 2.1, 2.2, 2.4, 2.5, 2.6 and plan items 3–5, 9–12).

## Global Constraints

- Work on a new branch from `origin/backup-demo` (`4544ba04` or newer). Never commit to `backup-demo` directly; the change goes in through a PR.
- Postgres schema is the source of truth: `docker/postgres/init/010_schema.sql`, plus `supabase/migrations/` for the VPS. Never edit tables in place on the VPS; every schema change is a new migration file.
- Tests never connect to the production DB (`127.0.0.1:15433`). DB tests use fakes or the test DB `127.0.0.1:15434`.
- Read endpoints require one of `READ_ROLES` (`backend/src/auth/authorization.py:52`). Watchlist writes act only on the caller's own `user_id`.
- Money values travel as decimal strings in VND (`value × scale`); the UI converts to "tỷ VNĐ". Never use floats for money.
- Every financial number shown on the web carries its status: `VERIFIED` (matched against the BCTC PDF) or `UNVERIFIED` (Vietcap only), plus a source link when one exists.
- Chat trace logging is best-effort: a failure is logged as a warning and never changes or blocks the chat answer.
- Backend tests run from the repo root: `backend/.venv/Scripts/python.exe -m pytest backend/tests/<file> -q`. Frontend tests run from `frontend/`: `node --test <file>`.

## Review Focus

1. A symbol with no BCTC rows at all, e.g. a company in `companies` without `financial_reports`. Expected: the financials endpoint returns `{"periods": []}` with 200, and the page shows "chưa có dữ liệu". Covered in Task 3 (`test_financials_empty_symbol`) and Task 4.
2. A symbol that is not in `companies`, e.g. `/api/companies/ZZZ`. Expected: 404 with a Vietnamese message; never 500. Covered in Task 3.
3. A watchlist add for a ticker that does not exist, or a duplicate add. Expected: 404 for unknown, idempotent 200 for duplicate (no second row). Covered in Task 5.
4. An expired access token on the new pages. Expected: `authorizedFetch` refreshes once, then the page shows the existing session error. Covered by reusing `authorizedFetch` in Tasks 4–6, so no new test.
5. A chat turn where the trace insert fails (DB down, FK violation on `reason_code`). Expected: the chat reply is unchanged and one warning is logged. Covered in Task 7 (`test_trace_failure_never_breaks_chat`).

---

### Task 1: Security fixes (JWT secret, unauthenticated search)

**Files:**
- Modify: `backend/src/core/config.py:88`, `backend/src/main.py` (lifespan start)
- Modify: `backend/src/api/routers/search.py:40,55`
- Test: `backend/tests/test_security_hardening.py` (new)

**Interfaces:**
- Produces: `LEAKED_JWT_SECRETS: frozenset[str]` in `core/config.py`; startup raises `RuntimeError("JWT_SECRET_KEY chưa được cấu hình an toàn.")`.

- [ ] **Step 1: Write the failing tests**

```python
def test_search_price_and_filtered_require_login(client):          # TestClient without Authorization
    assert client.post('/api/search/price', json={}).status_code == 401
    assert client.post('/api/search/filtered', json={}).status_code == 401

def test_startup_rejects_the_committed_default_secret(monkeypatch):
    monkeypatch.setenv('JWT_SECRET_KEY', next(iter(LEAKED_JWT_SECRETS)))
    with pytest.raises(RuntimeError, match='JWT_SECRET_KEY'):
        check_jwt_secret(Settings())
```

- [ ] **Step 2: Run them and confirm they fail.** Run `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_security_hardening.py -q`. Expected: FAIL (200/422 instead of 401; `check_jwt_secret` is not defined).
- [ ] **Step 3: Implement the fixes.**
  - Set the `jwt_secret_key` default to `SecretStr('')`. Put the old literal in `LEAKED_JWT_SECRETS`.
  - Add `check_jwt_secret(settings) -> None` in `core/config.py`. It raises if the secret is empty, is in `LEAKED_JWT_SECRETS`, or is shorter than 32 characters. Call it first in `main.lifespan`.
  - Add `dependencies=[Depends(require_roles(*READ_ROLES))]` to the `/price` and `/filtered` decorators.
- [ ] **Step 4: Run the new tests and the auth and search suites.** Run `... -m pytest backend/tests/test_security_hardening.py backend/tests/test_research_chat_api.py backend/tests/test_search*.py -q`. Expected: PASS.
- [ ] **Step 5: Commit.** `fix(security): require a configured JWT secret and login for search endpoints`
- [ ] **Step 6: Operations note (not code).** The old default equals the real secret, so it is public in git history. Ask the user to rotate `JWT_SECRET_KEY` in the VPS and LAN `.env` files. Every logged-in user will have to sign in again.

### Task 2: Schema sync and repository cleanup

**Files:**
- Modify: `docker/postgres/init/010_schema.sql` (add `daily_market_activity`, copied from `supabase/migrations/20261111000100_daily_market_activity.sql`)
- Create: `supabase/migrations/20261114000000_admin_serving_corpus.sql` (table, keys and grants copied from the docker init definition)
- Delete: `tmp/` (tracked), `frontend/src/pages/admin/{auditMock,configurationMock,corpusMock,evaluationMock,sourcesMock,tracesMock,mock}.js`
- Modify: `.gitignore` (add `**/.agent-state/`, `**/.work/`, `pytest-cache-files-*/`)

- [ ] **Step 1: Confirm both tables exist in both places.** Run `grep -c "daily_market_activity" docker/postgres/init/010_schema.sql` (expect ≥ 1) and `grep -l "admin_serving_corpus" supabase/migrations/*.sql` (expect one file). Run `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_financial_verification_schema.py -q` (expect PASS).
- [ ] **Step 2: Remove the files.** Run `git rm -r -q tmp frontend/src/pages/admin/*Mock.js frontend/src/pages/admin/mock.js`. Then `cd frontend && node --test src/pages/admin/*.test.js` (expect PASS: nothing imported them).
- [ ] **Step 3: List the root-level files for the team, but do not delete them.** These are `chunks_thu.json`, `interactive_test.py`, `run_event_news.py`, `wbs16_extractor.py`, `test_wbs16_extractor.py`, `stock_news_kg_template.json`. Owners are unknown, so record them in the PR description.
- [ ] **Step 4: Environment note.** Run `backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt`. This installs Pillow, so `test_admin_news_ocr.py` now passes.
- [ ] **Step 5: Commit.** `chore: sync daily_market_activity/admin_serving_corpus schema and drop tracked tmp and unused admin fixtures`

### Task 3: Companies and financials API

**Files:**
- Create: `backend/src/api/routers/companies.py`
- Modify: `backend/src/main.py:17,137` (import and `include_router`)
- Modify: `backend/src/financial/health_db.py` (add `get_company_financials`)
- Test: `backend/tests/test_companies_api.py`

**Interfaces:**
- Produces (HTTP, all `require_roles(*READ_ROLES)`):
  - `GET /api/companies` → `[{"id": "FPT", "name": str, "sector": str|None, "exchange": str|None, "industry_type": str|None, "has_financials": bool}]`, from `companies WHERE is_active`, ordered by symbol.
  - `GET /api/companies/{symbol}` → the same item; 404 `"Không tìm thấy doanh nghiệp."` when the symbol is unknown.
  - `GET /api/companies/{symbol}/financials` → `{"symbol": str, "periods": [{"period": "2025-YEAR"|"2026-Q3", "facts": [{"code": str, "label": str, "value_vnd": str|None, "status": "VERIFIED"|"UNVERIFIED"}], "source": {"title": str, "url": str, "page": int}|None}]}`. Newest period first; at most 8 periods.
  - `GET /api/companies/{symbol}/health` → the dict from `get_financial_health(pool, symbol)`, or `{"status": "NO_DATA"}`.
- Produces (Python): `async def get_company_financials(pool, symbol: str) -> list[dict]` in `financial/health_db.py`.
  - It reads rows with `fetch_health_records(conn, [symbol])`.
  - It keeps the codes `TOTAL_ASSETS, TOTAL_LIABILITIES, TOTAL_EQUITY, NET_REVENUE, PROFIT_AFTER_TAX, CASH_FLOW_OPERATING`, with labels from `b1_answering/evidence/grounded.py::_METRIC_LABELS`.
  - `value_vnd = str(value * scale)`.
  - `status` is `VERIFIED` when `locator_json.get('unit_status') == 'VERIFIED'`, else `UNVERIFIED`.
  - `source` is `citation_for(conn, <first VERIFIED observation_id of the period>)`.

- [ ] **Step 1: Write the failing tests.** Use a fake pool, following `backend/tests/financial_db_fixture.py`, and FastAPI `TestClient` with `current_principal` overridden.

```python
def test_list_companies_marks_symbols_with_financials(): ...   # FPT has_financials True, ZZT False
def test_unknown_symbol_is_404(): assert client.get('/api/companies/ZZZ').status_code == 404
def test_financials_empty_symbol(): assert client.get('/api/companies/ZZT/financials').json() == {'symbol': 'ZZT', 'periods': []}
def test_financials_money_is_vnd_string_with_status():
    fact = next(f for f in body['periods'][0]['facts'] if f['code'] == 'TOTAL_ASSETS')
    assert fact['value_vnd'] == '80000000000000' and fact['status'] == 'VERIFIED'   # 80000 × 10^9 scale
def test_requires_login(): assert anon_client.get('/api/companies').status_code == 401
```

- [ ] **Step 2: Run them and confirm they fail.** Run `... -m pytest backend/tests/test_companies_api.py -q`. Expected: FAIL (404 for the unknown router).
- [ ] **Step 3: Implement `get_company_financials` and the router**, with the signatures above.
- [ ] **Step 4: Run the tests and the health tests.** Run `... -m pytest backend/tests/test_companies_api.py backend/tests/test_financial_health_db.py -q`. Expected: PASS.
- [ ] **Step 5: Commit.** `feat(api): companies, financials and health endpoints from verified BCTC data`

### Task 4: Company pages use real data

**Files:**
- Modify: `frontend/src/pages/companies/api.js` (`getCompanies`), `frontend/src/pages/companies/detailApi.js` (`getCompanyDetail`)
- Modify: `frontend/src/pages/companies/CompanyDetailPage.jsx` (period select from data; status badge; source link)
- Delete: `frontend/src/pages/companies/detailMock.js` (after `detailPeriods` is no longer imported)
- Test: `frontend/tests/companyApi.test.js` (new)

**Interfaces:**
- Consumes: Task 3 endpoints.
- Produces:
  - `getCompanies(): Promise<Array<{id, name, sector, exchange, status, tone}>>`. `status`/`tone` are `"Có dữ liệu"/"success"` when `has_financials` is true, else `"Chưa có BCTC"/"neutral"`.
  - `getCompanyDetail(ticker): Promise<{id, name, sector, exchange, financials: [{period, label, facts: [{id, label, value, status}]}], reports: [{id, title, period, url, page}]}>`. `value` is `Number(value_vnd) / 1e9` (tỷ VNĐ, display only). `reports` is built from each period's `source`.
  - Keep the existing `fixture` argument only for the test pages, i.e. `ComponentPreview`.

- [ ] **Step 1: Write the failing test.** Stub `globalThis.fetch` through `authorizedFetch`'s session in `localStorage`.

```js
test("getCompanyDetail maps periods, tỷ values and source links", async () => {
  const detail = await getCompanyDetail("FPT");   // stubbed /api/companies/FPT and /financials
  assert.equal(detail.financials[0].period, "2026-Q3");
  assert.equal(detail.financials[0].facts[0].value, 80000);
  assert.equal(detail.reports[0].url, "https://static2.vietstock.vn/x.pdf");
});
test("unknown ticker returns null so the page shows its placeholder", ...);  // 404 → null
```

- [ ] **Step 2: Run and confirm it fails.** Run `cd frontend && node --test tests/companyApi.test.js`. Expected: FAIL (values come from the fixture).
- [ ] **Step 3: Implement the API functions and update the page.**
  - The period `<Select>` options come from `detail.financials`.
  - Each fact shows "Đã đối chiếu BCTC gốc" or "Chưa đối chiếu (Vietcap)" from `status`.
  - The empty state when `financials` is empty reads "Chưa có dữ liệu BCTC cho mã này."
- [ ] **Step 4: Run the frontend tests and build.** Run `cd frontend && node --test tests/ && npm run build`. Expected: all pass, and the build succeeds.
- [ ] **Step 5: Commit.** `feat(web): company list and financials from the API`

### Task 5: Watchlist API and pages; profile from the signed-in user

**Files:**
- Create: `backend/src/api/routers/watchlist.py`; Modify: `backend/src/main.py`
- Test: `backend/tests/test_watchlist_api.py`
- Modify: `frontend/src/pages/watchlist/WatchlistPage.jsx`, `frontend/src/pages/watchlist/mock.js` → rename to `watchlistApi.js`
- Modify: `frontend/src/pages/profile/api.js`, `ProfilePage.jsx`; `frontend/src/pages/{dashboard,research,watchlist}/*.jsx` (replace `researcherMock` with `useAuth().user`)
- Test: `frontend/tests/watchlistApi.test.js`

**Interfaces:**
- Produces (HTTP, `current_principal`; rows only for `principal.user_id`):
  - `GET /api/watchlist` → `[{"id": "FPT", "name": str, "sector": str|None, "exchange": str|None, "pinned_at": iso}]`
  - `PUT /api/watchlist/{symbol}` → 200 and the full list. It is idempotent (`INSERT ... ON CONFLICT DO NOTHING`). Unknown symbol → 404.
  - `DELETE /api/watchlist/{symbol}` → 200 and the full list. Deleting a ticker that is not in the list is a no-op.
- Produces (JS): `getWatchlist()`, `addToWatchlist(ticker)`, `removeFromWatchlist(ticker)` in `watchlistApi.js`, all returning the list above.
  - On first load, tickers found in the old `localStorage["finmind_watchlist"]` are sent with `addToWatchlist`, then the key is removed. This is a one-time migration.
- Produces (JS): `getProfile()` returns `{name, email, role, initials}` from `AuthContext`'s `user`. `initials` comes from the first letters of `name`, falling back to `email`.

- [ ] **Step 1: Write the failing backend tests.**

```python
def test_add_is_idempotent(): two PUT /api/watchlist/FPT → one row, list == ['FPT']
def test_unknown_symbol_404(): assert client.put('/api/watchlist/ZZZ').status_code == 404
def test_users_see_only_their_own_rows(): user B GET → [] after user A adds FPT
```

- [ ] **Step 2: Run and confirm they fail.** Run `... -m pytest backend/tests/test_watchlist_api.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement the router.** Look up `company_id` by symbol, then `INSERT ... ON CONFLICT (user_id, company_id) DO NOTHING`.
- [ ] **Step 4: Write the failing frontend test.** Test that local tickers migrate once and that `removeFromWatchlist` calls `DELETE /api/watchlist/FPT`. Run `node --test tests/watchlistApi.test.js` and confirm it fails.
- [ ] **Step 5: Implement the frontend changes.** Remove every `researcherMock` import from pages (`grep -rn researcherMock frontend/src/pages` must print only the `dashboard/mock.js` definition, or nothing).
- [ ] **Step 6: Run the backend file, `node --test tests/`, and `npm run build`.** Expected: PASS.
- [ ] **Step 7: Commit.** `feat: server-side watchlist and profile from the signed-in user`

### Task 6: Dashboard from existing endpoints

**Files:**
- Modify: `frontend/src/pages/dashboard/api.js`, `DashboardPage.jsx`
- Test: `frontend/tests/dashboardApi.test.js`

**Interfaces:**
- Consumes:
  - `getWatchlist()` (Task 5);
  - `GET /api/market-data/indices/{VNINDEX|HNXINDEX|UPCOMINDEX}/ohlcv`;
  - `GET /api/market-data/news?limit=5`;
  - `GET /api/research/chat/sessions`.
- Produces: `getDashboard(): Promise<{market, watchlist, announcements, recentResearch}>`, with the same keys as `makeDashboardFixture()`.
  - `market[i] = {id, name, value, change}`, where `change` is the last close compared with the previous close, in %.
  - `announcements` comes from the news items.
  - `recentResearch` is the 3 newest chat sessions.
  - If any one source fails, that section is `[]` and the page shows its own empty state. The other sections still render (`Promise.allSettled`).

- [ ] **Step 1: Write the failing test.** Cover "one failing source leaves the other sections filled", and the index change % from two closes (`50.0 → 51.0` gives `"2,00"`).
- [ ] **Step 2: Run `node --test tests/dashboardApi.test.js` and confirm it fails.**
- [ ] **Step 3: Implement `getDashboard` and remove the fixture imports from `DashboardPage.jsx`.**
- [ ] **Step 4: Run `node --test tests/ && npm run build`.** Expected: PASS.
- [ ] **Step 5: Commit.** `feat(web): dashboard from market, news, watchlist and chat history`

### Task 7: Log each chat turn into the trace tables

**Files:**
- Create: `backend/src/retrieval_orchestration/chat_trace.py`
- Modify: `backend/src/retrieval_orchestration/postgres_sessions.py:38-50` (`send`)
- Test: `backend/tests/test_chat_trace.py`

**Interfaces:**
- Produces: `async def record_turn(pool, *, user_id: str, question: str, result: dict, latency_ms: int) -> str | None`. It returns the new `query_id`, or `None` when logging failed. It writes, in one transaction:
  - `queries(query_id, user_id, question_text, question_type=result['scope'].get('source_type'), corpus_version_id=<only if it exists in corpus_versions>, language='vi', trace_id=result.get('request_id'), created_at=now())`;
  - one `query_companies` row per scope company found in `companies`;
  - `answers(answer_id, query_id, attempt=1, answer_text=<rendered draft or message>, status=answering.status or result.status, reason_code=(SELECT code FROM reason_codes WHERE code=$x), model_name=manifest.model_returned, prompt_version=manifest.prompt_version, latency_ms, created_at=now())`.
- Consumes: the last assistant message's `result` in the document returned by `append_turn` (`updated['messages'][-1]['result']`).
- `PostgresSessionStore.send` calls `record_turn` after `repository.commit`, inside `try/except Exception` that only logs `logger.warning('chat_trace_failed')`.

- [ ] **Step 1: Write the failing tests.**

```python
def test_turn_writes_query_companies_and_answer(fake_pool): ... # 1 queries, 1 query_companies (FPT), 1 answers row, status 'DRAFT_READY'
def test_unknown_reason_code_is_stored_as_null(fake_pool): ...   # PARTIAL_CLAIMS not in reason_codes → NULL, no exception
def test_trace_failure_never_breaks_chat(): store.send(...) with a pool whose execute raises → snapshot returned, one warning logged
```

- [ ] **Step 2: Run them and confirm they fail.** Run `... -m pytest backend/tests/test_chat_trace.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement `record_turn` and the call in `send`.**
- [ ] **Step 4: Run the chat suites.** Run `... -m pytest backend/tests/test_chat_trace.py backend/tests/test_research_chat_api.py backend/tests/test_postgres_sessions*.py -q`. Expected: PASS.
- [ ] **Step 5: Commit.** `feat(chat): record each turn in queries, query_companies and answers`

### Final: whole-branch verification

- [ ] Run `backend/.venv/Scripts/python.exe -m pytest backend/tests backend/src/b1_answering/tests -q -p no:cacheprovider --continue-on-collection-errors`. Expected: no new failures. The only allowed failures are the 5 WBS02 tests (fixture files not committed); OCR now passes.
- [ ] Run `cd frontend && node --test tests/ && npm run build`. Expected: PASS.
- [ ] Manual check on the web after restarting the backend:
  - the company list shows 10 real symbols;
  - FPT financials show Q3/2026 with a Vietstock link;
  - a watchlist add survives a reload and another browser;
  - the dashboard shows the indices;
  - one chat question creates one `queries` row (check with a read-only `SELECT count(*) FROM queries WHERE created_at > now() - interval '5 minutes'`).
- [ ] Open a PR into `backup-demo`. In the description, list the root-level files that need owners (Task 2 Step 3) and the JWT rotation step (Task 1 Step 6).
