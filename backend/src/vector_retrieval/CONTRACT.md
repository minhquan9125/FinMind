# Truy vấn vector kết hợp BM25 tại backend

## Phần mở rộng corpus/web 23/10/2026

`HybridRetriever(..., corpus_version_id=UUID)` xác nhận corpus FROZEN/index ACTIVE/đúng model và index, đồng thời ràng buộc document ID/hash trong mọi query metadata, fingerprint, dense và đọc kết quả. Chế độ không truyền corpus giữ hành vi INDEX cũ. `exact_period=True` dành cho năm/quý tài chính. Cache vẫn token-only/atomic/TTL, source reader mặc định dựng cả batch trong một call để chia sẻ cache release, không đọc lại release một lần mỗi document. ROWS giữ index/chunker metadata để chọn đúng reader v4. Trường rrf_score giữ nguyên ý nghĩa; web dùng score.type RRF. Xem [LIVE_CHAT_CONTRACT](../retrieval_orchestration/notes/LIVE_CHAT_CONTRACT.md). Những hướng dẫn INDEX/CLI bên dưới vẫn áp dụng cho chế độ CLI.

Chỉ viết mã trong backend/src/vector_retrieval. Không sửa router hiện tại, bảng Supabase hoặc module B1. Module độc lập và có CLI. Không tự cài dependency hay tải model, ghi DB, đổi trạng thái index/corpus. Chỉ dùng stdlib và dependency đã có của backend. Không đưa bí mật vào cache/lỗi/log. Cấu hình và import module không mở DB hoặc tải model.

## Thiết kế đã chốt

HNSW cosine + BM25 Okapi trên cùng tập chunk và scope -> RRF -> dựng lại nội dung từ locator bằng source reader hiện có, kiểm tra hash -> trả kết quả. BM25 chạy backend. Cache JSON trong folder .cache của package, chỉ lưu token/tần suất, metadata, không lưu toàn bộ passage. Cache tạo lại được, ghi atomic, schema/tokenizer/index/model có version và kiểm tra checksum. Cache là dữ liệu không đáng tin: không pickle/eval, giới hạn kích thước và kiểm tra cấu trúc, không dùng đường dẫn trong cache để truy cập file.

Database trực tiếp đã kiểm tra: pg17.6/vector0.8.2; text_chunks vector(1024), locator_json, content_hash, document_id,index_version_id,chunk_index,page_number,superseded_at. text_chunks không có chunk_text. Có HNSW cosine active global. Index v2 434ef5e0-6516-578d-8d18-721d21347e01 có15058active,modelBAAI/bge-m3@5617a9f61b02,statusBUILDING; corpus_versions chưa đăng kýv2. Không nói corpus frozen nếu chỉ dùngindex. Một mẫuprice sourcechanged,4nhómkhácpass. Không tạo cache bằng manifest source_chunk_id vì khác DBchunk_id.

## Interface cốt lõi (ranking.py)

- tokenize(text: str) -> list[str]: NFKC/casefold, bỏ dấu tiếng Việt (đ -> d), chữ/số, giữ mã/mốc kỳ bằng token hóa nhất quán; document và query dùng cùng tokenizer. Phiên bản TOKENIZER_VERSION. Không dùng english stemming.
- BM25Index(documents: dict[str,list[str]], k1=1.5,b=0.75): postings sparse, IDF log(1+(N-df+.5)/(df+.5)), length normalization; validate parameters/IDs/tokens. search(query:str, limit:int=50, allowed_ids:set[str]|None=None)->list[tuple[str,float]]. IDF từ toàn index; scope áp dụng trước topk. Chỉ score>0, tie chunk_id ascending, empty/corpus/repeatedqueryterms hợp lý. Không tính BM25 chỉ trên top vector. Không đánh đồng BM25 với ts_rank_cd.
- rrf(dense:list[tuple[str,float]],lexical:list[tuple[str,float]],limit=10,k=60.0,dense_weight=1.0,lexical_weight=1.0)->list[dict]: union dedupe eachlist, rank 1-based, score=sum(weight/(k+rank)), missing contributes0; validate bounded finite positive parameters/nonnegative weightsnotboth0; deterministic ties chunk_id; preserve dense_score,bm25_score,dense_rank,bm25_rank,rrf_score,chunk_id. Never sum raw scores.

## Backend runtime (backend.py)

Provide HybridRetriever with async build_cache(index_id, cache_path, allow_building=False), async search(question, index_id, cache_path, company=None, period=None, doc_type=None, top_k=5, candidates=50, allow_building=False) and injected pool/embedder for tests. No global DB writes. Default index configurable via CLI, never auto select v1. Validate UUID, bounds(topk1..20,candidates>=topk<=200), querynonblank<=4000, normalized exactcompany/doctypes, period allowed YYYY/YYYY-MM/YYYY-Q[1-4]/YYYY-MM-DD with realdatevalidation. Period has common explicitprefixsemantics with delimiterbounds, not raw ILIKEwildcards.

Index metadata must exist, dimension1024, model matches embedder's configured modelref. Refuse nonACTIVE unless explicit allow_building and exactBUILDING; never modify status. Responses always index_version_id,index_status,scope_mode=INDEX, never fabricate corpus_id or frozenmembership. Reject mismatched/corrupt/cacheindex/model/tokenizerversion, expired cache (default1hour, injectable clock) or changed membership/contenthash. Query must not rebuild all source passages. Cache metadata manifest hash from sorted activechunk IDs+hashes checked by one readonlymetadataquery per request; sourcevalidationfinalhits independent of cache.

Cache build transaction read-only repeatableread. Fetch active rows in explicit index joined documents/companies/reporting_periods. Include news symbolarray from source for scoping; period metadata fallback locatorperiod_code/published_at/section. Reconstruct with existing repository.resolve_result_rows(conn,rows) one documentgroup atatime (reuse sourcecache within group). Sourcechanged/missing must not be silentlyaccepted: raise clear safe cachebuilderror, don't replace previouscache. Cache only validated tokenlists and scope metadata; final search refetches selected rows then uses repository.resolve_result_rows to validate current source. If one finalhit stale, return explicit structurederror, no unverifiableanswer/fallback. Cache does not store raw DBDSN, embeddingvector,passage,APIkeys.

Query dense branch uses ORDER BY t.embedding <=> $vector LIMIT candidatecount, predicates active and explicitindex plus allowed scope IDs BEFORE LIMIT; never force indexplanner. Lexical applies same allowedIDs, not denseIDs. Use pgvector.register_vector existingpool init or registeredconnections. EmbeddingService.embed_query is sync CPU: run with asyncio.to_thread, not on eventloop. API result preserve perbranchscores/ranks and source chunk_id,document_id,locator,content_hash,text; scope failures and invalidsources safe codes, no rawexception/DSN logging. Close resources atCLIboundary. No automaticperusercache or conversationmemory mixing.

## CLI, documentation (hoi.py, README.md)

From FinMind: backend/.venv/Scripts/python.exe -X utf8 backend/src/vector_retrieval/hoi.py build --index UUID --allow-building
... hoi.py search --index UUID --allow-building --question "câu hỏi" [--company FPT --period 2026-Q2 --doc-type FINANCIAL_STATEMENT --json]
... hoi.py search --index UUID --allow-building (interactive loop exit). Reuse onepool/model/retriever forloop. Default .cache/indexUUID.json insidepackage, no externalpathbydefault. Explicitbuild needed; searchmissingcache tellsbuildcommand. Model offline by default set HF_HUB_OFFLINE and TRANSFORMERS_OFFLINE before constructing service; --allow-model-download optional only explicit flag. Do not call Gemini. Banner says index mode not corpusfrozen, BUILDINGonlyexplicitflag. CLI errors safe code not tracebacksecret. README explainscache rebuild, sourcechanges,normalizationlimits, offlinefirst and exactscope. Include no unobservedpassclaims.

## Kiểm chứng

Offline tests must exercise real BM25 formula/scope/rrf/cache corruption, validation, duplicate/tie/Unicode, indexrefusal, failedsourcebuildpreservesoldcache, queryrequiresbuild, no rebuilding everyquery, readonly SQL, stale finalsourcefailsclosed, interactiveinput/reuse/errors. No actual modeldownload/DB/network in tests. Coordinator may run readonly Supabase smoke AFTER tests/review, no unsolicitedreembeddingormigration.
