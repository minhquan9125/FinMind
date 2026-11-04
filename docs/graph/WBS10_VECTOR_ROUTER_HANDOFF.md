# WBS10 — Nối Vector RAG hiện có vào Hybrid Router

## Phạm vi bàn giao

Adapter thật nằm ở `backend/src/retrieval_orchestration/hybrid_router/vector_adapter.py`. Dùng lại `HybridRetriever` Vector/BM25/RRF và pool/model/cache của research chat. Không cào nguồn, không tạo lại chunk/vector tài liệu, không sửa schema hay trạng thái corpus/index, không gọi Gemini trong adapter.

`DecisionEngine` tạo task CONTENT cho route VECTOR. Factory live của `/api/hybrid-router/run` nối task đó vào `VectorRAGAdapter`. GRAPH được khởi tạo trễ: VECTOR không mở kết nối Neo4j, không phụ thuộc graph sẵn sàng. Các luồng B1/chat cũ giữ điểm vào hiện có; đây là adapter bàn giao WBS13, không tự đổi toàn bộ chat sang Hybrid Router.

## Contract đầu vào WBS13

`RouterTask.params` giữ `question`, `retrieval_question`, `companies`, `periods`, `metric_code`, `source_type`, `corpus_version_id`, `index_version_id` và các trường scope hiện có. API nhận các bộ lọc/pin mới trong `context`.

- Nguồn: BCTN → ANNUAL_REPORT; BCTC → FINANCIAL_STATEMENT; NEWS → NEWS; COMPANY_PROFILE → COMPANY_PROFILE. Nguồn được hỏi rõ trong câu mới ưu tiên hơn nguồn trong context.
- Corpus bắt buộc pin bằng cấu hình `RESEARCH_CORPUS_VERSION_ID`. Index lấy từ corpus; nếu `HYBRID_ROUTER_INDEX_ID` có giá trị thì phải khớp. Pin request khác phiên cấu hình bị chặn.
- Mỗi cặp công ty/kỳ có một truy xuất đã lọc, tối đa 6 cặp, 4 công ty hoặc 4 kỳ. Không chuyển nhiều công ty/kỳ thành không lọc.
- Kỳ số dùng định dạng được retriever hỗ trợ. Kỳ biểu tượng như NEXT_WEEK trả VECTOR_UNSUPPORTED_PERIOD, không tự mở rộng nguồn tài chính thành mọi kỳ.
- Với BOTH, chỉ nhận ticker/symbol/company rõ ràng từ graph dependency. Chỉ có company entity ID mà chưa ánh xạ ticker thì trả VECTOR_DEPENDENCY_SCOPE_UNRESOLVED; không đoán ID thành mã chứng khoán.

## Contract đầu ra

`AdapterResult.adapter=CONTENT`, `provenance=LIVE/VECTOR`. `evidence_pack` là contract B1 1.1: corpus, index, query ID; mỗi item giữ nguyên document/chunk ID, passage đầy đủ, locator, source/content SHA256, source_type và điểm RRF. `data` giữ cả dense/BM25 ranks từ retriever. Không rút passage còn 500 ký tự, không tự biến chunk ID thành document ID. Kiểm tra bằng `prepare_evidence`; citation có thể được dựng bởi B1 hiện tại.

API `/run` trả `adapter_results[].evidence_pack` để WBS13 nhận bằng chứng thật, ngoài các bộ đếm cũ. Không sinh câu trả lời hoặc coi kết quả retriever là quyết định duyệt graph.

| Trường hợp | Trạng thái / mã |
|---|---|
| Có bằng chứng hợp lệ | OK / VECTOR_EVIDENCE_READY |
| Không có kết quả | NO_DATA / VECTOR_NO_RESULTS |
| Thiếu một phần các cặp yêu cầu | INSUFFICIENT_EVIDENCE / VECTOR_PARTIAL_COVERAGE; không xuất pack như thể đủ |
| Hash/nguồn/locator không hợp lệ | INSUFFICIENT_EVIDENCE, mã lỗi an toàn |
| Cache chưa sẵn sàng/hết hạn | SYSTEM_UNAVAILABLE / CACHE_BUILD_REQUIRED hoặc CACHE_EXPIRED |
| Timeout | SYSTEM_UNAVAILABLE / VECTOR_TIMEOUT; hủy coroutine đang chạy |
| Lỗi không biết | SYSTEM_UNAVAILABLE / VECTOR_SEARCH_UNAVAILABLE; không lộ DSN/exception thô |

## Cache và chế độ chạy

Cache dùng đúng đường dẫn `backend/src/vector_retrieval/.cache/corpus-<corpus_id>.json` như research chat. Warmup có sẵn ở backend chuẩn bị cache. `adapter.warmup()` cho runner WBS13 chuẩn bị/làm mới cache BM25 trước lượt chạy; đây là cache token, không phải tạo lại vector tài liệu. Query adapter không tự xây lại cache khi lỗi.

Đã sửa ánh xạ metadata năm BCTN trong truy vấn retriever: dùng `locator_json.reporting_year` trước trường section `PDF_PAGE_N`, không lấy số trang làm kỳ báo cáo. Cache lên phiên 3 và được dựng lại bằng luồng prepare_cache có sẵn. Thuật toán Vector/BM25/RRF, nguồn và vector trong database không thay đổi.

Mặc định cấu hình router vẫn giữ nguyên. Để API thực thi adapter thật, đặt `HYBRID_ROUTER_MODE=live` trong môi trường máy chạy rồi khởi động lại backend. Không commit `.env` hay khóa kết nối.

Ví dụ body POST `/api/hybrid-router/run`:

```json
{
  "question": "Tóm tắt chiến lược kinh doanh FPT năm 2025.",
  "context": {
    "companies": ["FPT"],
    "periods": ["2025"],
    "source_type": "BCTN",
    "corpus_version_id": "b2550a0b-c423-5c50-9b15-6fb6af12e2c6"
  }
}
```

## Tái lập kiểm tra

Kết quả ngày 04/11/2026:

- 687 test hồi quy đạt: router/adapter, Vector/BM25, corpus pin và B1/chat. Trong đó 17 test adapter WBS10 đạt.
- Nguồn thật: FPT / BCTN / 2025 / corpus `b2550a0b-c423-5c50-9b15-6fb6af12e2c6`: route VECTOR, LIVE, OK; citation binding B1 PASS; graph_calls=0, database_writes=0.
- API thật POST `/api/hybrid-router/run`: VECTOR / LIVE / OK, 5 evidence, đúng corpus. Receipt bổ sung `outputs/vector-router-wbs10-20261104/api-verification.json`.
- Lần warmup sau đổi phiên cache xử lý 44.930 chunk mất khoảng 232 giây gồm chuẩn bị/cache và kiểm thử; đây không phải thời gian của một truy vấn cache nóng. API sau warmup kiểm tra thành công.
- Backend hiện được chạy với biến môi trường tiến trình `HYBRID_ROUTER_MODE=live`; không sửa `.env`. WBS13 cần bật biến này khi chạy ở máy khác.
- Đây là nghiệm thu adapter VECTOR và đường API, không phải nghiệm thu đầy đủ GRAPH/BOTH hay xác nhận thành viên WBS13 đã tích hợp. Không đưa nguồn thiếu kiểm duyệt vào graph.

Từ thư mục FinMind, chạy nhóm test router/adapter/B1. Runner nguồn thật chạy từ thư mục backend:

```powershell
$env:PYTHONPATH='.'
$env:PYTHONIOENCODING='utf-8'
..\.venv\Scripts\python.exe scripts/verify_vector_router.py
```

Mở tunnel PostgreSQL 15433. Runner dùng classifier thật, bộ tìm kiếm thật và kiểm citation B1; không gọi Gemini hay ghi database. Graph là sentinel cấm gọi cho case VECTOR. Receipt nằm ở `outputs/vector-router-wbs10-20261104/verification.json`. Không commit toàn bộ outputs/cache/model vào Git. Xem receipt và báo cáo test cuối cùng trước khi ghi nhận nghiệm thu nguồn thật.
