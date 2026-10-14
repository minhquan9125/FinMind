# WBS12: lưu chunk, vector và nguồn vào Supabase pgvector

## Dữ liệu đi qua đâu?

`db_source.py` đọc dữ liệu đã có trong Supabase → `db_chunking.py` tạo chunk và `locator` → BAAI/bge-m3 tạo vector 1024 chiều → `db_ingest.py` ghi ba bảng:

| Bảng | Nội dung |
| --- | --- |
| `index_versions` | Phiên bản chunker (`db-v1`), kích thước chunk và nhãn model đã ghim |
| `documents` | Một tài liệu nguồn, liên kết công ty/kỳ và hash nội dung |
| `text_chunks` | Nội dung chunk, vector 1024 chiều, vị trí và `locator_json` trỏ về dòng nguồn |

Mỗi tài liệu được ghi trong một transaction. Nếu một chunk của tài liệu không tạo được vector hoặc ghi lỗi, tài liệu đó không bị ghi dở. `chunk_id` lưu trong database có tính cả `index_version_id`, nên hai phiên bản index không dùng chung khóa. Rerun cùng đầu vào cập nhật cùng vị trí chunk, không thêm bản trùng.

## Chuẩn bị schema

Migration [`20261014000200_pgvector_chunk_metadata.sql`](../../supabase/migrations/20261014000200_pgvector_chunk_metadata.sql) thêm `locator_json`, khóa duy nhất `(index_version_id, document_id, chunk_index)`, khóa duy nhất `documents.sha256` và yêu cầu vector/khóa chunk không NULL. Schema gốc đã khai báo các ràng buộc này, nhưng database Supabase của nhóm chưa có. Migration đã được áp dụng cho project đang dùng ngày 14/10/2026. Với database khác, chạy migration trước khi dùng `--apply`.

Backend lấy `DATABASE_URL` từ `backend/.env`. Giữ file này ở máy, không đưa mật khẩu vào Git hoặc chat.

## Chạy mẫu trên PowerShell

Từ thư mục gốc repo, kiểm tra nguồn trước (chỉ đọc):

```powershell
backend\.venv\Scripts\python.exe -X utf8 backend\scripts\chunk_from_supabase.py --source companies --symbol FPT
```

Ghi một tài liệu hồ sơ FPT hoàn chỉnh:

```powershell
$env:HF_HUB_OFFLINE='1'
backend\.venv\Scripts\python.exe -X utf8 backend\scripts\chunk_from_supabase.py --source companies --symbol FPT --apply --confirmed-with-nhan --batch-size 8
Remove-Item Env:HF_HUB_OFFLINE
```

Chỉ đặt `HF_HUB_OFFLINE=1` nếu model đã có trong cache; bỏ dòng đó ở máy cần tải model lần đầu. Cờ `--apply` ghi thật lên Supabase. Khi xong WBS12, có thể mở rộng `--source`/`--symbol` cho nhiều dữ liệu ở WBS17.

## Kiểm tra dữ liệu đã lưu

Chạy SQL sau trong Supabase SQL Editor:

```sql
SELECT c.symbol, d.doc_type, d.title, t.chunk_index,
       vector_dims(t.embedding) AS dimensions,
       t.locator_json->>'source_table' AS source_table,
       t.locator_json->>'source_id' AS source_id,
       t.locator_json->'row_keys' AS row_keys,
       i.chunker_version, i.embedding_model
FROM public.text_chunks AS t
JOIN public.documents AS d ON d.document_id = t.document_id
JOIN public.index_versions AS i ON i.index_version_id = t.index_version_id
LEFT JOIN public.companies AS c ON c.company_id = d.company_id
WHERE c.symbol = 'FPT' AND d.doc_type = 'COMPANY_PROFILE'
ORDER BY t.chunk_index;
```

Ngày 14/10/2026, ghi thử hồ sơ FPT hai lần cho kết quả ổn định: 1 tài liệu, 1 chunk, 1 index version; vector 1024 chiều, norm khoảng 1, locator về `companies` và các `row_keys` của FPT. `chunk_id` và `created_at` không đổi ở lần ghi thứ hai.

API search hiện dùng index version của chunker `word-window-v1`; dữ liệu này dùng `db-v1`. Vì vậy API search cũ chưa truy ra các chunk mới. Việc chọn đúng index/corpus cho tìm kiếm thuộc WBS25; WBS12 xác nhận lưu và đọc ngược trực tiếp từ pgvector.
