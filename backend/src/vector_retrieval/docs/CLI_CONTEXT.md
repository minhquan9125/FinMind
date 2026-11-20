# CLI integration context
Work only in declared hoi.py, README.md and tests/test_cli.py; no DB/schema/config changes, no model download during tests, no credentials in logs. Keep exact package path vector_retrieval; existing B1/frontend/OHLCV untouched.

Verified runtime interface (backend.py candidate SHA256 97f927bc64934e539e0ff47b00fbc8b3adf3bc577082b7501196dcf4af4dc2d7):
HybridRetriever(pool, embedder, *, resolver=None, clock=time.time, max_cache_age=3600).
async build_cache(index_id,cache_path,allow_building=False) -> dict status CACHE_READY,chunks,index_version_id,index_status,scope_mode INDEX.
async search(question,index_id,cache_path,*,company=None,period=None,doc_type=None,top_k=5,candidates=50,allow_building=False) -> dict index_version_id,index_status,scope_mode INDEX,scope,results.
Each result has chunk_id,rrf_score,dense_score,bm25_score,dense_rank,bm25_rank,document_id,locator,content_hash,text. It is retrieval snippets, not Gemini answer.
RetrievalError.code is a safe code; string(exception) equals code. Common errors: CACHE_BUILD_REQUIRED, CACHE_STALE, CACHE_EXPIRED, SOURCE_CHANGED, HASH_MISMATCH, INDEX_NOT_ACTIVE, MODEL_MISMATCH, INVALID_QUESTION. Do not expose raw non-RetrievalError exceptions.
Default BUILDING index refusal unless --allow-building explicitly provided. Index UUID is explicit; never auto fallback to db-v1. Cache build fails on changed sources and preserves old file. Current v2 may hit SOURCE_CHANGED in prices; do not silently skip, change data or claim success.
Cache stores tokens/metadata without raw passages. Explicit build needed; search loads/verifies/reuses it, never builds all sources automatically. No corpus-v2 registry claim: responses scope_mode INDEX. CacheTTL3600 seconds.

Existing public helpers (verified src/core/db.py and documents/embeddings.py):
from src.core.db import connect,disconnect,get_pool
await connect() initializes asyncpg/pgvector pool; get_pool() returns it; await disconnect() closes it. Ensure finally disconnect for success, error and EOF. No need to manually manage DBURL or print it.
from src.documents.embeddings import get_embedding_service
get_embedding_service() returns lazily-loaded cached bge-m3 EmbeddingService using current Settings; model only loads when embed_query runs. Runtime checks exact modelref against stored index and expected bge-m3 revision. Do not use Gemini.
Set HF_HUB_OFFLINE=1 and TRANSFORMERS_OFFLINE=1 BEFORE creating embedder by default, even if inherited environment permits downloads. Only --allow-model-download explicitly permits downloads. No dependency installer.
hoi.py direct script bootstrap adds backend root Path(__file__).resolve().parents[2] to sys.path; then imports src.vector_retrieval.backend. Importing CLI must not connect/load model.
Module must be importable in tests without touching files outside newfolder. Test CLI observable behavior with fake service/pool/input, not actual networks. JSON output for one question must be valid single object, banner/error context goes stderr. Interactive loop reuses same pool/embedder/retriever; safe errors per question can be retried. README in Vietnamese must state tested/offline limitations honestly, no fabricated pass counts.

## CLI, documentation (hoi.py, README.md)

From FinMind: backend/.venv/Scripts/python.exe -X utf8 backend/src/vector_retrieval/hoi.py build --index UUID --allow-building
... hoi.py search --index UUID --allow-building --question "câu hỏi" [--company FPT --period 2026-Q2 --doc-type FINANCIAL_STATEMENT --json]
... hoi.py search --index UUID --allow-building (interactive loop exit). Reuse onepool/model/retriever forloop. Default .cache/indexUUID.json insidepackage, no externalpathbydefault. Explicitbuild needed; searchmissingcache tellsbuildcommand. Model offline by default set HF_HUB_OFFLINE and TRANSFORMERS_OFFLINE before constructing service; --allow-model-download optional only explicit flag. Do not call Gemini. Banner says index mode not corpusfrozen, BUILDINGonlyexplicitflag. CLI errors safe code not tracebacksecret. README explainscache rebuild, sourcechanges,normalizationlimits, offlinefirst and exactscope. Include no unobservedpassclaims.

## CLI acceptance checks
Test argument handling, JSON/text output, cache build/search failures, offline model policy, no import side effects, interactive session reuse and disconnect on success/error/EOF. Inject pool/model/service only at CLI boundary; runtime/BM25 have separate accepted behavioral tests. No live DB/model/network in tests.
