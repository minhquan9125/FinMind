# S3-G02: cấu hình embedding BAAI/bge-m3

## Cấu hình cần review

Mở [`bge-m3-v1.json`](bge-m3-v1.json) để review model ID, commit Hugging Face, số chiều, chuẩn hóa vector, batch size và runtime. Model được ghim bằng commit SHA để các máy trong nhóm tải cùng bộ trọng số.

Backend đọc các biến `EMBEDDING_MODEL`, `EMBEDDING_MODEL_REVISION`, `EMBEDDING_DEVICE`, `EMBEDDING_DIM` và `EMBEDDING_BATCH_SIZE`. Cấu hình mặc định khớp với file JSON trên.

## Vector mẫu

[`bge-m3-sample-v1.json`](bge-m3-sample-v1.json) được tạo từ ba chunk có `document_id` khác nhau trong `chunks_thu.json`. Mỗi mẫu lưu chunk ID, SHA-256 của text, text đầu vào, vector 1024 chiều và L2 norm. Script kiểm tra số chiều và vector đã chuẩn hóa trước khi ghi file.

## Tạo lại mẫu

Từ thư mục gốc repo, dùng Python 3.12 và môi trường ảo backend:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\generate_embedding_sample.py
```

Lần đầu cần internet để tải model từ Hugging Face; các lần sau dùng cache. Kết quả được ghi đè vào `docs/embedding/bge-m3-sample-v1.json`.

## Batch size

Giá trị khởi đầu là 8, lấy từ cấu hình chạy trên CPU; đây là batch size để ingestion theo lô, không phải tuyên bố đã benchmark tối ưu throughput. Có thể điều chỉnh bằng biến môi trường `EMBEDDING_BATCH_SIZE`, sau đó cần tạo lại sample và review.

Khi thay model revision, mã index version cũng đổi để tránh trộn vector từ hai bộ trọng số. Corpus đã lưu theo version cũ cần được ingest lại để API tìm kiếm dùng version mới.
