# Corpus-v2 — bản nội dung đã đóng băng

## Trạng thái

Đã tạo `backend/.tmp/corpus-v2.content.manifest.json` từ các bảng nguồn hiện có
trên Supabase, trong transaction READ ONLY REPEATABLE READ.
Trạng thái: **CONTENT_FROZEN_AWAITING_VECTOR_INGEST**.
Chưa đăng ký corpus trên database và **chưa sẵn sàng benchmark vector WBS20**.

| Dữ liệu | Tài liệu | Chunk |
| --- | ---: | ---: |
| Báo cáo tài chính clean | 419 | 13.003 |
| Tin tức | 234 | 1.750 |
| Lịch sử giá cổ phiếu | 6 | 204 |
| Hồ sơ doanh nghiệp | 13 | 13 |
| Chỉ số thị trường | 3 | 88 |
| **Tổng** | **675** | **15.058** |

Manifest SHA-256 (canonical payload):
`86e880eef3b39ddf2515951252025a8f58e700f80416ba24d6fabfe324362bd7`.

Nội dung giữ text đóng băng, source_chunk_id, locator, content_hash, số từ và
snapshot hash từng tài liệu. Mã source_chunk_id là ID đầu ra chunker, **không
phải khóa text_chunks đã ingest**. Dùng schema riêng `finmind-source-corpus-v2`
để công cụ đăng ký manifest v1 không vô tình coi bản nội dung là corpus vector.
Đã kiểm tra đủ từng mã dòng, ID chunk không lặp, dựng lại nội dung/hash cho
toàn bộ chunk. Hai test cho tính xác định và chống nhầm trạng thái đều đạt.

## Phạm vi nguồn

- Bao gồm toàn bộ dữ liệu do năm bộ đọc nguồn production trả về tại snapshot,
  không lấy file dữ liệu thử trên máy thay cho dữ liệu đã nhập.
- Báo cáo tài chính: 10 công ty BID, CMG, CTG, ELC, FPT, ICT, ITD, MBB, TCB, VCB.
- Giá cổ phiếu: FPT, MBB, VCB, MSN, NLG, CTR.
- Chỉ số: VNINDEX, VN30, HNXINDEX. **Chưa gồm UPCOMINDEX**, vì nguồn này chưa có
  trong các bảng được đọc ở snapshot. File UPCOMINDEX cục bộ không tự được nhập.
- Dữ liệu mới cào ở `backend/.tmp/new-financial-flow/` chưa nhập Supabase, nên
  không nằm trong bản này. Không tự thay 419 báo cáo đã nhập bằng 429 hợp kỳ từ
  dữ liệu thử. Nếu muốn đổi phạm vi, tạo candidate khác, không sửa bản đã đóng băng.

## Bước để có corpus-v2 vector thực tế

1. Thống nhất phạm vi nội dung này hoặc chuẩn bị candidate khác có dữ liệu mới.
2. Dùng index riêng, không dùng lại index_version_id của corpus-v1. Code ingest
   hiện ghim CHUNKER_VERSION=db-v1 khi tạo index, trong khi financial mới dùng
   db-financial-v3; phải xử lý versioning này trước khi chạy ingest v2.
3. Bộ đọc search `resolve_result_rows` cũng cần chọn/cache nguồn theo phiên bản
   renderer của locator; hiện lời gọi fetch_locator_document trong nhánh này
   vẫn dùng mặc định db-v1. Hàm reconstruct_chunk riêng đã chọn đúng phiên bản.
4. Nhúng bằng model đã ghim, ghi vector và locator vào index mới, kiểm tra đủ
   ID và hash ứng với snapshot. Không coi vector cũ là vector cho text mới.
5. Xuất manifest từ ID thực tế đã ingest, đăng ký corpus-v2 và thử truy vấn chỉ
   trên membership của bản đó. Chỉ sau khi đạt mới đánh dấu benchmark-ready.

Đã đọc kiểm kê vector: index db-v1 có 2.051 hàng, 2.048 active; index upload
word-window-v1 có 50 hàng. Các con số này **không xác nhận vector của 15.058
chunk v2 đã tồn tại**.

## Bảo toàn corpus-v1 và bàn giao

Không ghi Supabase, không tải/chạy model embedding và không sửa manifest v1.
Script so SHA-256 toàn file v1 trước/sau và xác nhận không thay đổi.
Không đăng ký label corpus-v2 trên database cho một bản chưa ingest.

File manifest nằm trong thư mục bị Git ignore. Nếu cần gửi qua Git:

```powershell
git add -- backend/scripts/prepare_corpus_v2.py backend/tests/test_prepare_corpus_v2.py docs/embedding/corpus-v2-handoff.md history.md
git add -f -- backend/.tmp/corpus-v2.content.manifest.json
```

Kiểm tra danh sách stage trước khi commit. Khi WBS20 cần manifest vector,
không dùng file `.content.manifest.json` này thay cho manifest đã ingest.
