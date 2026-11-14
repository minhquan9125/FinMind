# S3-WBS07: tạo embedding theo lô và theo dõi lỗi

Script đọc fixture chunk JSON, gọi BAAI/bge-m3 theo lô, rồi ghi mỗi vector thành công cùng `chunk_id`; chunk lỗi được ghi riêng với lý do, số lần thử và khả năng thử lại. Mặc định dùng batch size 8, lấy từ cấu hình embedding đã chốt.

## Chạy thử

Từ thư mục gốc repo trên PowerShell:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\embed_chunks_batch.py --limit 8
```

Mặc định script đọc `chunks_thu.json` và ghi kết quả vào `backend/.tmp/embedding-batch-results.json`. Bỏ `--limit 8` để chạy toàn bộ fixture. Có thể đổi lô và số lần thử:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\embed_chunks_batch.py --batch-size 8 --max-retries 2 --output backend/.tmp/embedding-results.json
```

## Quy tắc lỗi

- Batch chạy được: mỗi chunk nhận đúng một vector 1024 chiều.
- Batch lỗi: script cô lập từng chunk; chunk chạy được vẫn được giữ lại đúng một lần.
- Lỗi từ model/runtime ở một chunk: thử lần đầu và tối đa 2 lần bổ sung.
- Text rỗng/sai định dạng, ID trùng, vector sai chiều hoặc giá trị không hữu hạn: báo lỗi không thử lại.
- File kết quả có `succeeded` (chunk, vector, số lần gọi) và `failed` (`chunk_id`, lỗi, số lần thử, có thể retry hay không).

Script không kết nối Supabase và không ghi database. Kết quả JSON được đặt trong `backend/.tmp/` để không commit các vector thử nghiệm lớn. WBS12 sẽ chịu trách nhiệm lưu vector cùng metadata vào pgvector.
