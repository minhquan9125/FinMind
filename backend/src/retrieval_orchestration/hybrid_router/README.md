# Hybrid router contracts

## Routing policy agreed on 2026-11-01

`intent_policy.py` is the current business policy. `ScopeResolver` first resolves
the target (company, market, industry, or investing concept). Missing ticker/year
does not by itself make a market, sector or knowledge question ambiguous.

| Route | Use |
| --- | --- |
| VECTOR | Financial metrics/dividends, price explanations, forecasts, market views, investing knowledge and portfolio education |
| GRAPH | Leadership, ownership, subsidiaries and company business fields without a second content request |
| BOTH | Entity discovery followed by content, overall company comparison, industry impact/beneficiary discovery, event verification |
| CLARIFY | Missing or genuinely ambiguous target/context, or an invalid explicit reporting period |

Business policy takes priority over classifier scores for recognized intents.
Numeric-only comparisons use VECTOR, with separate content tasks for every
company and period; they do not wait for Graph. Explicit multi-quarter inputs
retain all year–quarter pairs.

### Scope/context handoff (2026-11-05)

The router emits `reporting_entity` (`CONSOLIDATED`/`PARENT`) and
`measure_basis` when established by the question. A bare quarter does not prove
standalone versus YTD. Personnel task parameters include `person_name`,
`position_code`, `event_type` and `relation_types`; codes follow the existing
person-role rules. A resignation request is `RESIGNATION_REQUESTED`, not a
completed dismissal. These are query filters, not extracted facts.

Clients must round-trip `topic`, `operation`, `route_hint` and the scope filters
alongside companies/periods for listing follow-ups. The interactive client does
this; a new standalone market/knowledge question still resets company scope.

Calendar years/quarters resolve with the Vietnam clock (`reference_date` is
injectable for fixtures). Latest/source-dependent periods require an injected
`DecisionEngine.period_resolver(task) -> list[str]` backed by scoped corpus
coverage. The API now wires this resolver to indexed document periods in the
configured frozen corpus, with ACTIVE index, document-hash membership and active
chunks checked in a read-only transaction. An omitted hybrid index is derived
from that corpus; no latest year is invented. `/test` returns concrete periods
when coverage exists and exposes `period_resolution_required` otherwise.
Before LIVE calls, unresolved/invalid periods stop execution with
`PERIOD_RESOLUTION_REQUIRED`; they are never silently dropped. Exact daily price
lookups use a calendar date and the existing price service, not report coverage.

Every explicit numeric quarter is checked, including a later invalid quarter.
Year-before-quarter and quarter-before-year are supported. Company-specific
period clauses are stored in `scope.targets`; shared periods still expand to
each requested company. Listing/company-switch follow-ups retain topic, role,
operation and reporting scope. `reporting_entities` retains both CONSOLIDATED
and PARENT when compared, with separate tasks; `reporting_entity` is null when
both are requested. Parent financial reports use VECTOR; parent-company identity
lookups still use GRAPH.

The live content adapter accepts an optional `scope_search_fn` that receives
reporting_entity/measure_basis. Without this capability an explicit reporting
entity returns `CONTENT_REPORTING_SCOPE_UNSUPPORTED` before retrieval, rather
than searching without the requested filter. Current database statement_scope
values describe statement sections, so they must not be used as a fabricated
consolidated/parent mapping. The factory now installs this callback and reuses
the LIVE evidence header matcher for reporting entity and quarter basis.
Missing scope labels return no matching evidence, rather than another report.
Search is bounded to 20 verified candidates before header filtering; it is not
an exhaustive scan of all documents.

For BOTH, the content task declares `company_scope_policy`:
`RELATED_COMPANIES` requires Graph result rows to supply explicit ticker lists
in `resolved_companies`; `EXPLICIT_OR_RESOLVED` keeps explicitly requested
companies, otherwise uses those lists. Person IDs, relation IDs and path nodes
are never guessed as tickers. Missing mapping stops before Vector with
`GRAPH_COMPANY_MAPPING_REQUIRED`. The engine bridges declared tickers into the
current content dependency format and executes one company/period per call.
The Graph adapter now populates this mapping from registry company IDs on the
returned edges, passes requested relation types and checks position/event stage.
Unknown relation types remain errors; requests are never widened to all edges.

`source_type` is retained in scope/context. BCTN uses ANNUAL_REPORT for coverage
and retrieval; its pinned document report-year metadata can resolve the latest
report. BCTC uses FINANCIAL_STATEMENT. Report years are not relation effective dates.
Exact daily prices use `find_price` and the existing read-only price query service.
No trading row for the requested date means NO_DATA, not substitution of another day.

Both endpoints require current server authentication and a READ_ROLES grant when
LIVE/shadow or configured-corpus data can be accessed. Only pure MOCK without a
configured corpus remains anonymous. Set `FINMIND_ACCESS_TOKEN` for the interactive
client to attach the bearer token; the client does not print or persist it.

Regression suite for this handoff: `backend/tests/test_hybrid_router.py`.

The existing pinned BGE-M3 + Logistic Regression classifier remains the fallback
for resolved questions without a policy match; model artifacts were not retrained.
Original questions are retained in every task. Forecast/partial period tokens
are not passed as invalid exact corpus filters. New global/conceptual requests
do not inherit a stale company or metric from conversation context.

Current acceptance examples live in `backend/tests/fixtures/router_acceptance_v2.json`.
`test_router_acceptance_v2.py` tries each against four adversarial score pairs,
checks company scope, adapter plans, context boundaries and actual HTTP validation.
The original Section 6 fixtures below describe a legacy MVP; their JSON schema
checks are not a measurement of routing accuracy or financial answer quality.

### Shared input normalization

The router and live-research path both use `input_normalization.py`. Its domain
vocabulary and protected identifiers live in `config/input_aliases.json`.
Telex vowel shapes and a tone key are decoded before or after each other to
support suffix and infix typing. Shape-only input is accepted when it resolves
uniquely to a known word. Existing canonical words and ambiguous candidates are
retained; this is not a general spelling corrector or a ticker autocorrector.

`test_telex_router_contract.py` independently encodes Unicode Vietnamese into
three Telex variants for 128 base questions. It checks normalized text, company
scope, route, repeat-normalization stability and identifier preservation. It
also covers the literal user input `duwj ddoan thij truongf chuwsng khoans sawp towi`.
These generated examples supplement the base acceptance suite; they are not an
independent measure of general Vietnamese-language accuracy.

Tasks retain the original `question` and send `retrieval_question` to content
search, so raw Telex is not passed through as the search query. `/test` exposes
`normalized_question`; enter `/debug` in `interactive_test.py` to inspect it and
the resolved scope when testing a new way of typing.

To verify the running backend without executing live retrieval:

```powershell
python backend/scripts/verify_router_acceptance.py --output router-http-results.json
```

`/test` selects routes only. `/run` still depends on adapter capabilities and
available data; relationship retrieval can return `GRAPH_RELATIONSHIPS_NOT_INDEXED`.
Selecting VECTOR for a forecast does not guarantee that a prediction is correct.

This module defines the requested MVP JSON contract only; it does not enable
GRAPH/BOTH retrieval or change the LIVE chat contract. Unsupported/no-data/system
errors continue to require the existing orchestration status handling.

`RouterOutput.model_validate(payload)` validates input JSON dictionaries;
`result.model_dump(mode="json", exclude_none=True)` produces JSON-compatible output.
`example_both.json` is MOCK data: company availability, operations, metric names,
and the relation date are illustrative, not verified financial facts.

BOTH currently supports the planned graph-then-content workflow. Dependencies
must refer to earlier tasks. CLARIFY never contains executable tasks. Period and
metric requirements are operation-specific and must be checked by the future
policy/adapter, not imposed on every graph operation by this schema.

## Reuse the existing embedding service

For an offline training script run with backend on PYTHONPATH:

```python
from src.documents.embeddings import get_embedding_service

embedder = get_embedding_service()
query_vector = embedder.embed_query("Tong tai san FPT nam 2025?")
training_vectors = embedder.embed_texts(["Cau hoi 1", "Cau hoi 2"])
```

Do not instantiate SentenceTransformer in router code. The existing cached
service pins the model revision and normalizes embeddings. When integrating into
LIVE, coordinate with the embedding concurrency lock used in live_research.py
and move synchronous encoding off the async event loop. This step adds no LIVE
embedding calls and does not load another model.

## Development fixtures and keyword baseline

`router_fixtures.json` contains 42 proposed MOCK cases: the revised 30 original
cases plus market/explain, owner isolation, model lifecycle, threshold boundary,
evidence mismatch and negation/paraphrase challenges. Review operation names,
metric codes and status mappings with the team before acceptance use.

`classify_by_keywords(resolved_question)` in `baseline_rule.py` returns independent
binary graph/content labels and a proposed route. Call it only AFTER the existing
intent, context, scope and capability gates. It does not replace those modules,
resolve a ticker/year, create tasks, check scores or call any adapter.
A no-keyword match returns `(0, 0)` and `route=None`, never forced BOTH.
Negation and unseen wording are deliberate limitations to compare against ML.

From `backend`, run:

```powershell
..\.venv\Scripts\python.exe -B -m src.retrieval_orchestration.hybrid_router.evaluate_baseline
..\.venv\Scripts\python.exe -B -m pytest tests/test_hybrid_router_baseline.py -q -p no:cacheprovider
```

The evaluator validates MVP SEARCH/CLARIFY contracts and scores eligible resolved
retrieval inputs only. It reports unique-input precision/recall/F1 and exact match,
plus fixture mismatches; repeated adapter-failure scenarios are deduplicated by
exact input. It does NOT execute mocks or validate actual upstream/final behavior.
These are development fixtures, not an independent ML holdout. Keep them out of
training and freeze a separate unseen acceptance set for the final comparison.

## Step 12 — Controlled Live Adapters and Execution

Bước 12 cung cấp 2 adapter thật để kết nối router với hạ tầng retrieval và graph thực tế:

- **`LiveContentAdapter`**: Bọc `HybridRetriever` (dense BGE-M3 + BM25 + RRF), thực hiện truy vấn văn bản BCTC thật với `provenance="LIVE/VECTOR"`. Tự động ánh xạ mã lỗi hệ thống (`CACHE_BUILD_REQUIRED`, `HASH_MISMATCH`, v.v.).
- **`LiveGraphAdapter`**: Bọc `GraphStore` (Neo4j). Hỗ trợ đọc chỉ tiêu tài chính qua `find_observations`. Các truy vấn quan hệ công ty con/sở hữu chưa có trong schema Neo4j hiện tại sẽ trả về an toàn `SYSTEM_UNAVAILABLE` (`GRAPH_RELATIONSHIPS_NOT_INDEXED`) với `provenance="LIVE/GRAPH"`.

### Cấu hình kiểm soát (Feature Flags)

Khai báo trong `.env`:
```env
HYBRID_ROUTER_MODE=mock      # "mock" (mặc định), "shadow", hoặc "live"
HYBRID_ROUTER_INDEX_ID=      # UUID index vector active
```

### Endpoints
- `POST /api/hybrid-router/test`: Chỉ phân loại tuyến và xác định phạm vi (không gọi adapter).
- `POST /api/hybrid-router/run`: Thực thi pipeline đầy đủ qua adapter tương ứng theo `HYBRID_ROUTER_MODE`.

### Kiểm thử Bước 12
```powershell
..\.venv\Scripts\python.exe -m pytest tests/test_live_adapters.py -v
..\.venv\Scripts\python.exe -m pytest tests/test_hybrid_router.py -v
```
