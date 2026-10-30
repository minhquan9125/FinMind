# Hybrid router contracts

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
