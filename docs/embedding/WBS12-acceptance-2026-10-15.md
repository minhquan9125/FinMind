# WBS12 — Biên bản nghiệm thu lưu vector và metadata vào pgvector

Ngày kiểm chứng: 15/10/2026. Phạm vi là **hai tài liệu thật từ Supabase**, không phải full-load. Không đọc `data/` để tạo chunk; `chunks_thu.json` chỉ là fixture kiểm thử cố định. Tài liệu giá FPT được tạo từ 123 hàng `price_bars` của FPT tại thời điểm chạy; dữ liệu nguồn có thể thay đổi về sau.

## Tập nghiệm thu và cấu hình

| Nguồn | `document_id` | `source_id` / `external_id` | Chunk đầu vào |
| --- | --- | --- | ---: |
| Hồ sơ FPT (`companies`) | `3684f2cb-e649-51be-83c6-f6670d1ffbfe` | `8635c01b-08cb-521b-9318-5424b0b400e1` | 1 |
| Lịch sử giá FPT (`price_bars`, kèm `price_indicators`) | `d1574ee2-fe9e-5ced-aa53-32bfe5518c93` | `FPT` | 34 |

- Chunker: `db-v1`, tối đa 130 từ/chunk. Model: `BAAI/bge-m3@5617a9f61b02`, vector 1024 chiều, batch size 8.
- `index_version_id`: `1e029e66-0adf-53ac-8f28-431ed7312745`.
- Hai file chunk đầu vào của **chính lần ghi đầu** được lưu cục bộ trong `backend/.tmp/` (được Git ignore), không commit vector hoặc dữ liệu nguồn. SHA-256: `wbs12_fpt_company_first.json` = `605CA198DEB1CEA43BF34E34CB76AB51EC9470A92121672B40ED94FAC32D6CEA`; `wbs12_fpt_prices_first.json` = `4703D574EF51897388C73493A2AB1E78BF76F4A221295DB3EFA35F4E7ACFA93E`.
- Migration `20261014000300` đã được xác minh trên Supabase: đủ hai cột `superseded_at`, `superseded_by_chunk_id`; có chỉ mục `uq_text_chunks_current_position`, không còn chỉ mục cũ `uq_text_chunks_index_document_chunk`.

## Lệnh chạy

Chạy tại thư mục gốc repo bằng PowerShell. `DATABASE_URL` nằm trong `backend/.env`; không đưa thông tin kết nối vào log hoặc Git. Máy kiểm chứng có snapshot model đã ghim trong cache, nên đặt chế độ offline để dùng đúng snapshot đó.

```powershell
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
backend\.venv\Scripts\python.exe -X utf8 backend\scripts\chunk_from_supabase.py --source companies --symbol FPT --max-words 130 --batch-size 8 --apply --confirmed-with-nhan --out backend\.tmp\wbs12_fpt_company_first.json
backend\.venv\Scripts\python.exe -X utf8 backend\scripts\chunk_from_supabase.py --source prices --symbol FPT --max-words 130 --batch-size 8 --apply --confirmed-with-nhan --out backend\.tmp\wbs12_fpt_prices_first.json
```

Chạy lại đúng hai lệnh với tên file đầu ra `_second.json`, rồi so `chunk_id`, `created_at` và số hàng hiện hành. `--out` chứa chunk được tạo từ cùng lần đọc nguồn với lệnh `--apply`; dữ liệu nguồn có thể đổi giữa hai lần chạy, nên phải so cả nội dung hai file đầu vào trước khi kết luận idempotency.

## Kết quả thực tế

| Lần chạy | Chunk đầu vào | Tài liệu xử lý thành công | Chunk đầu vào xử lý thành công | Tài liệu lỗi | Chunk hiện hành trong DB thuộc đúng hai tài liệu/index |
| --- | ---: | ---: | ---: | ---: | ---: |
| Thử khi model chưa chạy offline | 1 | 0 | 0 | 1 | 1 (hồ sơ FPT đã có trước) |
| Ghi đầu | 35 | 2 | 35 | 0 | 35 |
| Chạy lại | 35 | 2 | 35 | 0 | 35 |

Hồ sơ FPT đã tồn tại từ lần thử trước; lần ghi đầu của biên bản này thêm tài liệu giá FPT. Hai file đầu vào lần đầu/lần hai trùng nhau theo từng nguồn. Đối chiếu cả 35 chunk theo ID lưu (`index_version_id` + `chunk_id` nguồn), `document_id`, `chunk_index`, `content_hash`, `locator_json.source_table`, `source_id`, `row_keys`, ký hiệu FPT, chunker/model và `vector_dims(embedding) = 1024`: **35/35 khớp, 0 sai lệch**. Hai tài liệu có lần lượt 1 và 34 chunk hiện hành. Truy vấn với một index version khác hoặc một document ID ngoài tập đều trả **0**; truy vấn riêng từng tài liệu trả 1 và 34. Sau lần chạy lại, tập 35 `chunk_id` và toàn bộ `created_at` giữ nguyên.

Lần thử đầu tiên khi chưa đặt chế độ offline thất bại ở bước tải model qua proxy: **1 tài liệu lỗi, 0 chunk ghi thành công**. Lỗi được báo rõ; sau khi dùng snapshot model đã có trong cache, cả hai tài liệu đều ghi thành công. Đây là lỗi môi trường tải model, không phải vector sai chiều hay lỗi pgvector.

Phép thử supersede trên DB thật dùng một bản sao hồ sơ FPT với nội dung tạm thay đổi và vector giả hợp lệ **chỉ trong transaction có rollback**. Trong transaction: chunk cũ vẫn giữ nguyên `chunk_id`/nội dung, có `superseded_at` và trỏ đến chunk mới; chỉ chunk mới là hiện hành. Sau rollback: chỉ còn chunk FPT ban đầu hiện hành, không có bản ghi thử tồn tại. Vector thật của tập nghiệm thu vẫn do model đã ghim tạo ra.

Test tự động liên quan: `backend/tests/test_db_ingest.py` và `backend/tests/test_batch_embeddings.py` — **18/18 đạt**. Các test bao phủ vector sai chiều, lỗi embedding không ghi dở, chạy lại không ghi thêm, supersede và hồi sinh chunk cũ.

## SQL để reviewer đối chiếu

Truy vấn này cố ý lọc **hai `document_id` của lần nghiệm thu**, `index_version_id` và `superseded_at IS NULL`; tổng số trên cả index có thể chứa tài liệu khác trong những lần ingest sau.

```sql
SELECT d.document_id, d.doc_type, d.external_id,
       count(*) AS current_chunks,
       count(*) FILTER (WHERE vector_dims(t.embedding) <> 1024
                         OR t.embedding IS NULL OR t.locator_json IS NULL) AS invalid_chunks,
       count(DISTINCT t.chunk_id) AS distinct_chunk_ids
FROM public.text_chunks AS t
JOIN public.documents AS d ON d.document_id = t.document_id
WHERE t.index_version_id = '1e029e66-0adf-53ac-8f28-431ed7312745'
  AND t.document_id IN (
    '3684f2cb-e649-51be-83c6-f6670d1ffbfe',
    'd1574ee2-fe9e-5ced-aa53-32bfe5518c93'
  )
  AND t.superseded_at IS NULL
GROUP BY d.document_id, d.doc_type, d.external_id
ORDER BY d.doc_type;
```

Kỳ vọng: `COMPANY_PROFILE` = 1, `PRICE_HISTORY` = 34, tổng = 35, `invalid_chunks = 0`, `distinct_chunk_ids = current_chunks`. Có thể mở từng hàng cùng `locator_json` và `content_hash` để truy về đúng nguồn. `corpus_version_id` và manifest đóng băng thuộc WBS16; ba khóa `index_version_id + document_id + content_hash` chứng minh phạm vi index/tài liệu/nội dung của task này, chưa chứng minh cô lập corpus hoàn chỉnh. Full-load toàn bộ nguồn Supabase là bước riêng sau nghiệm thu này.
