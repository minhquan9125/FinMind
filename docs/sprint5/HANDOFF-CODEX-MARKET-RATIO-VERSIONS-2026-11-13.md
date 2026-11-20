# Handoff Codex: market ratios must not create new BCTC versions (13/11/2026)

Branch: `feature/bctc-health-chat`. Owner: Hưng. Do not commit or push; Hưng reviews first.

## Problem
The BCTC refresh job (`backend/scripts/refresh_financial_statements.py`) creates a new `financial_reports` version whenever a metric value changes between runs (`values_differ` in `backend/src/financial/verification_store.py`).
Vietcap (VIETCAP_VCI) recomputes **market ratios** from the latest share price on every request: P/E, P/B, P/S, dividend yield, market cap, and the share counts used for them.
Result: each run creates a new version for every period, although the report itself did not change. Task 10 (13/11) produced its new versions only because of these ratios. There was one exception: VCB 2024 EPS 5571→3727 after a bonus-share issue, which is a real restatement.

## Goal
A change that affects **only** market-price-derived ratios must not create a new version, neither in `append_reports` (with `--apply`) nor in `plan_reports` (dry run).
A change in any accounting metric (revenue, profit, assets, EPS, ROE, ROA, NIM, NPL, ...) must still create a new version, exactly as today.

## Scope
- Fix the root cause once, in the shared comparison used by both callers (`values_differ`, or a helper both call).
- Find the market-derived metric codes from the data. Do not guess them:
  - `SELECT code, section, name FROM metrics WHERE section='RATIO'` (test DB `127.0.0.1:15434`, user `finmind_test`; read-only on production `15433` only if needed);
  - the Vietcap payload fields in `data_pipeline/financial_data/` (the fields with price-based names such as priceToEarning, priceToBook, marketCap, dividendYield).
- Keep EPS and book value per share as accounting metrics. EPS changed for VCB 2024 because of a real restatement.
- Write a one-line comment on the code set explaining why: "recomputed from the daily price by the source".
- Tests (TDD) in `backend/tests/test_financial_statements_refresh.py` and/or `test_financial_verification_store.py`:
  1. only P/E or P/B changed → no new version (both `plan_reports` and `append_reports`);
  2. P/E changed and revenue changed → new version;
  3. EPS changed → new version.

## Do not
- Do not touch these files (Hưng is editing them): `backend/src/b1_answering/**`, `backend/src/retrieval_orchestration/**`, `backend/src/market_data/trend.py`, `backend/src/financial/health_passage.py`.
- Do not change rows already stored in the DB (append-only). Do not run `--apply` on production.
- Do not enable `FINMIND_BCTC_REFRESH`.
- Never connect tests to production `15433`. Never print credentials.

## Done when
- The new tests pass, and `backend/tests/test_financial_*.py` all pass (run from the repo root: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_financial_statements_refresh.py ...`).
- A read-only dry run reports `phien ban moi 0` for symbols whose only change is market ratios: `backend/scripts/refresh_financial_statements.py --symbols FPT,MBB`, without `--apply`.
- Report: the list of codes treated as market ratios and where each was found, the diff, and the test output.
