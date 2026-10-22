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

## Thay đổi database và rollback

Migration `supabase/migrations/20261020000100_text_chunks_hnsw.sql` đã tạo index trên Supabase chính sau khi có baseline trước index. Tạo/xóa index chỉ thay đổi schema và tài nguyên lưu trữ/thời gian build; không sửa hay xóa các hàng chunk/vector. Rollback index:

```sql
DROP INDEX IF EXISTS public.idx_text_chunks_embedding_hnsw;
```

## Giới hạn

Benchmark này đo retrieval và scope, không đánh giá chất lượng câu trả lời cuối. HNSW là approximate nearest-neighbor; cần tiếp tục theo dõi recall và latency khi dữ liệu tăng. `corpus_version_id` chưa được áp dụng vào API này; manifest-based isolation vẫn là phần việc riêng.
