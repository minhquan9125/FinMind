# WBS34 — kiểm thử E2E vector retrieval trên một bài tin FPT

Ngày 23/10/2026, chọn bài CafeF dùng cho Golden Q03: “Sau màn hát ‘Tái sinh’ ... mỗi tháng FPT có thêm 6.000 cổ đông mới”. Dữ liệu đọc **trực tiếp từ Supabase**, không lấy file `data/` làm nguồn chạy. Corpus-v4 `33d33730-0f0a-5274-a7f8-8d32a6be07e8` đã đóng băng, index `e3725b7d-1a39-5196-b000-3496dbab388f` đang hoạt động. Tài liệu `66bc216c-5874-51a0-9dc9-f4c094287405` có 8 chunk hiện hành, source ID `f48b4ed9-fe8b-5f65-8d50-e3162c8b2de8`.

## Đường đi đã đối chiếu

1. `corpus_documents` trỏ tới đúng `document_id` và hash của hàng `documents`. Index ghi mô hình `BAAI/bge-m3@5617a9f61b02`, đúng cấu hình backend.
2. Cả 8 hàng `text_chunks` có vị trí liên tiếp, không trùng ID/vị trí, vector 1024 chiều, đúng index và locator `news_articles`. Reader v4 dựng lại chữ từ payload đã ghim trong `raw_payloads`, xác minh release/locator và SHA-256 của từng chunk. Không dùng `chunk_text` cũ làm bằng chứng.
3. Nhúng lại **một chunk đã xác minh** bằng BGE-M3 cho cosine với vector lưu trong DB bằng `1.0` (làm tròn 8 chữ số). Điều này đối chiếu model/vector của mẫu, không chứng minh mọi vector trong corpus đều đúng.
4. Câu Q03 được nhúng và tìm qua pgvector với bộ lọc `FPT`, `2026-09`, `NEWS`, corpus-v4, `top_k=5`. Chunk của đúng bài ở hạng 1 và chứa đồng thời `171,4 triệu cổ phiếu`, `181.748 cổ đông`, `22/09/2026`; cả 5 kết quả đọc lại nguồn không lỗi. Gọi lần hai với cùng vector trả cùng 5 chunk ID. Lọc công ty không tồn tại hoặc kỳ `1900-01` trả rỗng.
5. Gọi thật route `POST /api/search/filtered` qua ASGI HTTP test client với cùng câu hỏi và Supabase thật trả HTTP 200, 5 hit, bài đúng ở hạng 1, cả 5 `source_verified=true`.

## Chạy lại

Từ gốc repo trong CMD, sau khi `backend/.env` trỏ đến DB nhóm và BGE-M3 đã có trong cache:

```cmd
set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1
backend\.venv\Scripts\python.exe -X utf8 backend\scripts\audit_vector_e2e.py
backend\.venv\Scripts\python.exe -X utf8 -m pytest -q -p no:cacheprovider backend\tests\test_audit_vector_e2e.py backend\tests\test_db_ingest.py backend\tests\test_source_result_reader.py backend\tests\test_filtered_search_api.py
```

Script chỉ dùng transaction đọc, ghi báo cáo cục bộ `backend/.tmp/wbs34-q03-e2e.json` (Git ignore); lệnh test không ghi DB. Kết quả chạy lần này: **10/10 check trong script đạt**, 49 test liên quan đạt. Test `test_unchanged_document_writes_nothing` và `test_rerun_produces_identical_ids` kiểm tra tính idempotent của writer `db-v1` bằng fake DB.

## Phần chưa được chứng minh

Lượt WBS34 này **chưa chạy lại thao tác ghi corpus-v4 trên Supabase thật**. Repo hiện có reader cho release v4 nhưng không có CLI/writer tái nạp đúng release `db-corpus-v2`; chạy `chunk_from_supabase.py --apply` sẽ ghi theo `db-v1`, không phải phép thử rerun v4 tương đương. Hai lượt tìm giống nhau và không có vị trí trùng chứng minh đọc ổn định, **không thay cho thử ingest lại**. Biên bản WBS17 đã ghi nhận rerun thật của `db-v1` giữ ID và không nhân đôi chunk, nhưng là index khác. Cần người sở hữu luồng tạo corpus-v4 cung cấp cách rerun an toàn hoặc một DB dev cùng release để kiểm tra bước còn thiếu trước khi tuyên bố E2E v4 hoàn tất toàn bộ.

Đây là phép kiểm tra **retrieval và bằng chứng của một tài liệu**. Chưa chấm toàn bộ Golden40 hoặc chất lượng câu trả lời do LLM sinh ra.
