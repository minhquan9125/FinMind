# WBS20 + WBS25: chỉ mục pgvector và truy vấn có lọc

> Kết quả baseline bên dưới dùng fixture cố định của bộ Golden trước v6 và index `db-v1`. Sau khi file `Golden_TestSet_Lo1_Lo2_TinTuc_GiaCoPhieu.md` chuyển sang Golden40 v6 đề xuất, không dùng kết quả 10/10 ở đây để tuyên bố v6 đạt. Chạy `backend/scripts/audit_golden_v6.py` để khảo sát kỹ thuật trên index v2; v6 chưa có gold được duyệt.

## Phạm vi

Task gộp này dùng vector `db-v1` đang có trên Supabase chính, không nạp lại corpus. API mới `POST /api/search/filtered` có bộ lọc tùy chọn theo mã công ty, kỳ và loại tài liệu; mỗi truy vấn luôn giới hạn vào `index_version_id` đã cấu hình và chunk chưa bị supersede. Kết quả trả chunk/document, nội dung, điểm tương đồng, locator nguồn và index version.

Schema hiện tại chưa gắn corpus manifest tới từng chunk, nên API bảo đảm ranh giới theo index và trạng thái chunk hiện hành, chưa thể khẳng định membership của một manifest đóng băng.

## Cấu hình và kết quả benchmark

- Index version: `1e029e66-0adf-53ac-8f28-431ed7312745` (`db-v1`, `BAAI/bge-m3@5617a9f61b02`, 1024 chiều).
- PostgreSQL 17.6, pgvector 0.8.2; 2.048 chunk `db-v1` đang active lúc kiểm tra.
- Tạo HNSW cosine với `m=16`, `ef_construction=64`, partial index chỉ trên chunk active.
- Bộ test có 10 ca: 8 câu hỏi (4 câu hỏi tiếng Việt và bản dịch tiếng Anh) trên tin/giá, 2 ca có bộ lọc sai kỳ/công ty phải trả rỗng. Tập test dựa trên các mục Q03, Q09, Q15, Q17 trong `Golden_TestSet_Lo1_Lo2_TinTuc_GiaCoPhieu.md`. Q10 bị loại do đáp án đếm bài viết cũ; Q21-Q40 cần chunk tài chính chưa có trong index hiện tại.

| Đo | HNSW | Thời gian retrieval trung bình | Trung vị | Nguồn mong đợi | Đúng phạm vi |
| --- | --- | ---: | ---: | ---: | ---: |
| Trước khi tạo index | Không | 771.259 ms | 715.424 ms | 10/10 | 10/10 |
| Sau khi tạo index | Có | 563.085 ms | 539.490 ms | 10/10 | 10/10 |

Trung bình giảm khoảng 27% trong lượt đo này, trong khi cả kiểm tra nguồn và phạm vi đều đạt. Đây là một lần benchmark trên DB chia sẻ, vì vậy thời gian có thể thay đổi theo tải và cache; không nên xem mức giảm này là cam kết hiệu năng. Thời gian embedding được đo riêng và không tính vào retrieval.

`EXPLAIN (ANALYZE, BUFFERS)` trên truy vấn nearest-neighbor xác nhận PostgreSQL chọn `idx_text_chunks_embedding_hnsw` (Index Scan); truy vấn kiểm tra trả 5 dòng trong 21.485 ms. Query chạy với vector thử nghiệm, nên đây là xác nhận planner sử dụng index, không phải số đo người dùng.

Kết quả tóm tắt theo từng câu hỏi nằm tại [`results/wbs20-pgvector-benchmark.json`](results/wbs20-pgvector-benchmark.json). Tập câu hỏi có tại `backend/scripts/fixtures/wbs20_filtered_questions.json`; script đo tại `backend/scripts/benchmark_pgvector.py`.

Lượt kiểm tra mở rộng Q01–Q20 chỉ dùng tiếng Việt nằm tại [`results/golden-q01-q20-audit.md`](results/golden-q01-q20-audit.md). Bộ 10 ca đo tốc độ ở trên chỉ chứa 4 câu Golden gốc, bản dịch và ca lọc sai phạm vi; kết quả 10/10 của nó không đại diện cho toàn bộ Q01–Q20.

Sau khi đối chứng, năm câu giá bị trượt ở top 5 cũng trượt khi tắt HNSW và tìm vector chính xác. Vì vậy có thêm `POST /api/search/price` để tra đúng phiên và tính các thống kê từ `price_bars` bằng SQL chỉ đọc. Lượt thử trên Q11–Q20 đạt 10/10 đáp án Golden; endpoint này không thay đổi phép đo vector/HNSW ở trên. Kết quả và giới hạn nằm trong báo cáo Q01–Q20 đã liên kết.

## API và chạy lại benchmark

Request mẫu:

```json
{
  "query": "Giá đóng cửa VCB ngày 20/05/2026 là bao nhiêu?",
  "company_symbol": "VCB",
  "period": "2026-05",
  "doc_type": "PRICE_HISTORY",
  "top_k": 5
}
```

Bộ lọc có thể bỏ trống. Bộ lọc không khớp trả danh sách rỗng. Để chạy lại benchmark (không ghi DB):

```powershell
cd backend
$env:HF_HUB_OFFLINE = "1"  # Nếu model đã có trong cache
.\.venv\Scripts\python.exe scripts\benchmark_pgvector.py --out .tmp\benchmark.json --runs 3
```

Script dùng transaction read-only cho các truy vấn benchmark và ghi kết quả chi tiết vào đường dẫn `--out`.

## Thử Q31–Q32 trên index v2 qua backend API (22/10/2026)

`POST /api/search/filtered` giữ index v1 khi không gửi `index_version_id`. Để thử index v2 đang `BUILDING`, truyền ID `434ef5e0-6516-578d-8d18-721d21347e01` tường minh. Endpoint chỉ chấp nhận index mặc định và ID v2 thử nghiệm này; truy vấn không ghi database. Loại tài liệu tài chính đúng là `FINANCIAL_STATEMENT`.

Trong CMD, khởi động backend từ thư mục `backend` (model BGE-M3 cần có sẵn trong cache khi bật offline):

```cmd
set FINMIND_LIVE_ENABLED=0
set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1
.venv\Scripts\python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

Mở `http://127.0.0.1:8000/docs`, chọn `POST /api/search/filtered` → `Try it out`. Body Q31:

```json
{
  "query": "Trong bản dữ liệu clean FPT đã đóng băng, tại kỳ 2026-Q2, tiền và các khoản tương đương tiền có giá trị gốc bao nhiêu?",
  "index_version_id": "434ef5e0-6516-578d-8d18-721d21347e01",
  "company_symbol": "FPT",
  "period": "2026-Q2",
  "doc_type": "FINANCIAL_STATEMENT",
  "top_k": 5
}
```

Q32 dùng cùng body, thay `query` bằng: `Trong bản dữ liệu clean FPT đã đóng băng, tại kỳ 2026-Q2, dư nợ vay và nợ thuê tài chính ngắn hạn có giá trị gốc bao nhiêu?`

Lần gọi HTTP thật ngày 22/10/2026: **Q31 và Q32 đều trả 409 `SOURCE_CHANGED`**. API đã chọn v2 và truy vấn được tới bước dựng lại chunk, nhưng fingerprint của nguồn tài chính hiện tại lệch bản đã index; đây không phải kết quả truy xuất đúng hay đáp án Golden đã đạt. Lần chạy đầu khi chưa bật offline trả 500 vì môi trường thử không kết nối được Hugging Face để kiểm tra model, trước khi truy vấn DB. Nếu máy chưa tải BGE-M3 vào cache, cần chuẩn bị model trước; bật offline không tự tải model.

## Thử theo corpus-v2 đã đóng băng

Để kiểm tra đúng phiên corpus `232fbd29-355f-5a77-ba28-a06b8d5ceb40`, dùng `corpus_version_id` thay cho `index_version_id` trong body `POST /api/search/filtered`. Backend lấy index gắn với corpus từ DB, chỉ tìm trong các tài liệu thuộc `corpus_documents` có `document_hash` trùng với `documents.sha256`, và bỏ chunk đã supersede. Không gửi hai ID phiên bản cùng lúc. Ví dụ Q31:

```json
{
  "query": "Trong bản dữ liệu clean FPT đã đóng băng, tại kỳ 2026-Q2, tiền và các khoản tương đương tiền có giá trị gốc bao nhiêu?",
  "corpus_version_id": "232fbd29-355f-5a77-ba28-a06b8d5ceb40",
  "company_symbol": "FPT",
  "period": "2026-Q2",
  "doc_type": "FINANCIAL_STATEMENT",
  "top_k": 5
}
```

Chạy audit Golden v6 từ thư mục repo bằng CMD (chỉ đọc DB, ghi file kết quả cục bộ):

```cmd
set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1
backend\.venv\Scripts\python.exe -X utf8 backend\scripts\audit_golden_v6.py --corpus-version-id 232fbd29-355f-5a77-ba28-a06b8d5ceb40 --ids Q01,Q31,Q32 --out backend\.tmp\golden-v6-corpus-v2.json
```

Audit này đo retrieval tạm thời, chưa chấm đáp án Golden. Nếu nguồn hiện tại không dựng lại được đúng hash chunk đã index, API vẫn trả `409 SOURCE_CHANGED`; chọn đúng corpus không tự khắc phục lỗi nguồn.

Lần chạy toàn bộ Golden v6 ngày 22/10/2026 với corpus trên, `top_k=5`: Q01–Q10 có 5 hit/câu, không lỗi dựng nguồn; Q31–Q38 cũng có 5 hit/câu nhưng cả 5 hit ở từng câu đều lỗi dựng lại nguồn. Cả 18 câu đều trả rỗng khi cố ý lọc sai công ty hoặc kỳ. Q11–Q20 và Q39 thuộc nhánh SQL giá/tính toán, Q21–Q29 cần PDF chưa có trong v2, Q30/Q40 là ca từ chối; audit vector không chấm các câu đó. Không có `retrieval_error`, nhưng 8 câu tài chính **chưa đạt kiểm tra nguồn** và không có điểm chất lượng chính thức vì Golden chưa có nhãn đáp án/nguồn được duyệt. Báo cáo chi tiết cục bộ: `backend/.tmp/golden-v6-corpus-v2-full.json`.

Thử qua HTTP thật cùng `corpus_version_id`: Q03 trả `200` với 5 kết quả; Q31 trả `409 SOURCE_CHANGED`. Đây là lỗi xác minh nguồn của chunk tài chính, không phải lỗi chọn corpus hay không tìm được vector.

### Xem trước khi nguồn đổi (chỉ dùng để chẩn đoán)

Trong Swagger, thêm `"preview_source_changed": true` vào body Q31 ở trên rồi Execute. Nếu phần nguồn hiện tại còn đúng định danh báo cáo, section và `row_keys`, API trả kết quả kèm `source_verified: false`, `source_warning: "SOURCE_CHANGED"`; trường `text` là chữ dựng từ **Supabase hiện tại**, không phải chữ đã xác minh của corpus-v2. Điểm `score` vẫn là điểm của vector cũ. Chế độ này không tạo câu trả lời hay bằng chứng được duyệt. Bỏ trường này hoặc đặt `false` để quay về kiểm tra nghiêm ngặt và HTTP 409. Chỉ dùng công tắc với `corpus_version_id`.

Đã thử HTTP thật với Q31: bật preview trả `200`/5 hit, cả 5 có `source_verified: false`; tắt preview vẫn trả `409 SOURCE_CHANGED`. Không sửa hay ghi dữ liệu Supabase.

## Thay đổi database và rollback

Migration `supabase/migrations/20261020000100_text_chunks_hnsw.sql` đã tạo index trên Supabase chính sau khi có baseline trước index. Tạo/xóa index chỉ thay đổi schema và tài nguyên lưu trữ/thời gian build; không sửa hay xóa các hàng chunk/vector. Rollback index:

```sql
DROP INDEX IF EXISTS public.idx_text_chunks_embedding_hnsw;
```

## Giới hạn

Benchmark này đo retrieval và scope, không đánh giá chất lượng câu trả lời cuối. HNSW là approximate nearest-neighbor; cần tiếp tục theo dõi recall và latency khi dữ liệu tăng. API nay có lọc tài liệu theo `corpus_version_id`; kiểm chứng dữ liệu nguồn dựng lại và chất lượng đáp án vẫn là bước riêng.
