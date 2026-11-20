# Price analysis implementation plan

Goal: expose deterministic, source-traceable daily price/volume analysis from PostgreSQL through the authenticated market API, implementing the already approved five-part framework with honest missing-data states.

Architecture: a focused analysis module reads a bounded PostgreSQL window in a read-only repeatable-read transaction and computes metrics without network/crawler/LLM calls. The existing router adds one authenticated GET endpoint. This slice does not change DB schema, import raw snapshots, refresh prices, implement a UI, or pretend snapshot-only foreign flows constitute daily history.

Authorization: user said to continue building price analysis on 11/11/2026 after previously approving the framework. No new provider/key selection or migration is authorized. Existing user edit in graph_store.py remains untouched.

## WBS: price-analysis

Files: new backend/src/market_data/analysis.py; existing backend/src/api/routers/market_data.py; new backend/tests/test_price_analysis.py. Context: existing core/db.py, documents/price_queries.py source contracts (briefed below), auth and market API tests. No dependency changes.

### Exact interfaces

- `summarize_price(rows, *, symbol, as_of, benchmark_rows=(), today=None) -> dict`: input rows are dict-like PostgreSQL records containing price_id, symbol, trade_date (date), price_scale, is_adjusted, open/high/low/close (Decimal), volume (int), payload_id, source_name and approval_status. Query passes ascending rows, but pure function also sorts and rejects duplicate dates. Today defaults to Vietnam date. `as_of` is a date, not a datetime. Reject future dates, future rows relative to as_of, wrong symbols, malformed OHLCV, non-finite/zero/negative prices, bool volume/scale, negative volumes, mixed scale/adjustment/source in selected window; adjustments may be all false and emit warning. Reject null or non-bool adjustment metadata and unknown/non-positive/non-integer scale. No float-based arithmetic except final standard-library sample standard deviation.
- `async query_price_analysis(pool, symbol, as_of=None) -> dict`: normalize symbol to uppercase with regex `[A-Z0-9]{1,10}` and reject invalid symbols/future as_of using ValueError. Default as_of Vietnam today. Use parameterized SQL, read-only repeatable-read transaction, get at most latest 21 price rows at/before as_of joined companies/raw_payloads/ingestion_jobs/sources (LEFT JOIN provenance so absent metadata remains visible rather than excluding price rows). Read at most 21 VNINDEX rows over the stock window, never request provider refresh. Return same summary. No DB on import.
- `GET /api/market-data/stocks/{symbol}/analysis?as_of=YYYY-MM-DD`: existing READ_ROLES auth applies. New dependency `get_price_analysis_pool` delegates core.db.get_pool. Valid response 200; unsupported/no stock rows 404; invalid symbol/future date/bad data 400 (date parsing FastAPI422); unavailable DB 503 without internal errors or secrets. Endpoint must await the service and serialize all Decimal results as strings. No migration required.

### Result contract

JSON-safe object with symbol, requested_as_of, as_of (latest stock day or null), first_date, session_count (selected window <=21), staleness_calendar_days versus today, status (`ok`, `partial`, `no_data`), metrics, benchmark, money_flow, sources, warnings. No NaN/Infinity. Empty rows give no_data with null metrics and empty sources. Insufficient periods return null for that metric, with partial status and warning. Up to 21 source entries, each price_id, payload_id, trade_date, source_name, approval_status, price_scale, is_adjusted. Missing provenance and non-APPROVED source status must be explicit warnings; no credentials/source connection config in output.

`metrics` keys: close (stored price unit), close_vnd, price_scale, is_adjusted, return_1_percent, return_5_percent, return_20_percent, sma20, close_vs_sma20_percent, volume, average_volume_prior20, volume_vs_prior20, average_volume_latest5, average_volume_prior5, intraday_range_percent, daily_volatility20_percent. Numeric metrics use Decimal, ROUND_HALF_UP to four decimals as strings except integer volume/scale and bool adjustment. Close can preserve Decimal string. `return_n`: 100*(latest close / close n actual sessions earlier -1), requiring n+1 rows. SMA20 includes latest and requires20 rows. Prior20 volume excludes latest, requires21 rows; zero prior average yields null ratio and warning. Average latest5/prior5 requires5/10 rows respectively. Intraday range 100*(high-low)/previous close requires2 rows. Daily volatility20 uses sample standard deviation of the20 daily percentage returns across21 closes; not annualized, not ATR.

`benchmark`: VNINDEX, with return_1/5/20_percent and excess_return_1/5/20_percentage_points. For each n, require benchmark valid positive finite closes on ALL n+1 stock dates for that window; never substitute nearest dates or older benchmark windows. Missing/duplicate/invalid dates mean that window null and warning. Compare benchmark independently of price units, but never mix stock price bases. `money_flow`: status unavailable, total_value_vnd, foreign_buy_volume, foreign_sell_volume, foreign_net_volume, foreign_buy_value_vnd, foreign_sell_value_vnd, foreign_net_value_vnd all null; reason says no daily history stored. Never estimate actual transaction values or foreign trades from close*volume. Do not read latest snapshot to stand in for historical daily flow.

Warnings are stable plain text/code strings; include unadjusted-price warning for is_adjusted false, stale-data warning whenever latest day precedes requested_as_of, incomplete metrics/benchmark/flow and missing provenance/approval. Descriptive results have no buy/sell advice, causal news claims, thresholds or aggregate score.

### Steps and acceptance

- [ ] Worker implementation proposes only the three allowlisted files in staging. Keep module/tests focused so independent testing/review packets fit installed limits.
- [ ] Independent testing worker covers exact n+1 arithmetic with non-calendar consecutive fixture dates, SMA/volume exclusion, constant/nonconstant volatility, absent/zero volume, short/empty input, bad numeric/OHLC/symbol/date/metadata, duplicate dates/mixed bases, benchmark alignment, provenance warnings, no_data/API auth/errors, read-only bounded parameterized query and no provider calls.
- [ ] Coordinator reviews candidate execution risks, runs fixed offline unittest and existing market API/price query regression commands, then independent reviewer checks code and real receipts.
- [ ] Integrate only approved unchanged candidate; rerun tests and run read-only service on real FPT/MBB DB, compare returns/MA/volume independently in SQL, save result. Do not mark missing flow or stale DB as solved.

Observed baseline: outputs/sprint5/price-analysis-build-20261111/db-before.json. 21,365 OHLCV bars all have volume, latest29/10; no foreign daily fields/table; DB live snapshots07/10 only. KBS requests worked11/11 but not used to silently mix price bases or overwrite existing series.
