# Kết quả kiểm tra Golden40 với Supabase thật — 22/10/2026

**Chưa đo được chất lượng HNSW + BM25 + RRF: bước dựng cache bị chặn bởi `SOURCE_CHANGED`.** Đây là kết quả chạy thật trên database, không phải kết quả fixture hay điểm chất lượng tìm kiếm.

Chi tiết từng câu, phạm vi và lỗi: [golden40-supabase-20261022.json](golden40-supabase-20261022.json).

## Cách thực hiện

- Chạy CLI `hoi.py build` của module đã tích hợp với index `434ef5e0-6516-578d-8d18-721d21347e01`, chọn rõ `--allow-building`. CLI kết thúc exit 1, lỗi `SOURCE_CHANGED`, không tạo cache.
- Sau đó gọi trực tiếp `HybridRetriever.search` đã tích hợp cho nguyên văn 27 câu loại vector trong Golden40 v6. Không thay resolver, không tạo cache giả, không bỏ qua xác minh hash.
- Chỉ dùng mã doanh nghiệp, kỳ và loại nguồn suy ra từ câu hỏi. Q05 hỏi hai doanh nghiệp nên không ép lọc về một mã. Không đưa đáp án hoặc mã bằng chứng tham khảo vào truy vấn.
- `top_k=5`, `candidates=50`; chưa đi tới bước embedding, tìm kiếm HNSW hoặc hợp nhất BM25. Thời gian ghi ở từng câu là thời gian trả lỗi, không phải độ trễ tìm kiếm thành công. Không có kết quả top 5/top 10, so sánh có/không lọc hoặc nghiệm thu các ca lọc sai.
- Toàn bộ truy vấn kiểm tra nằm trong transaction READ ONLY REPEATABLE READ; quan sát `transaction_read_only=on`. Không sửa database, nguồn, vector, schema hoặc code sản phẩm. Không gọi Gemini, tải model hoặc cài dependency.
- Công cụ chẩn đoán tạm thời do coordinator chạy nằm trong `.work/golden_readonly.py`; đây không phải feature mới hay một vòng ECC triển khai sản phẩm. Các lỗi helper ban đầu về symbols NULL và tham số HNSW chưa nạp đã được sửa trong helper trước lần chạy hoàn tất, không sửa module sản phẩm.

## Dữ liệu quan sát được

Index tồn tại, trạng thái `BUILDING`, model `BAAI/bge-m3@5617a9f61b02`, **15.058 chunk active / 675 tài liệu**. BUILDING không có nghĩa là chưa có vector; lần kiểm tra này chủ động cho phép đọc index đó. Phạm vi là INDEX, chưa khẳng định corpus membership theo manifest đã đăng ký.

| Nguồn | Chunk active | Tài liệu |
| --- | ---: | ---: |
| Báo cáo tài chính | 13.003 | 419 |
| Tin tức | 1.750 | 234 |
| Giá cổ phiếu | 204 | 6 |
| Chỉ số thị trường | 88 | 3 |
| Hồ sơ doanh nghiệp | 13 | 13 |

HNSW index cosine có trong database; không chạy truy vấn xếp hạng trong lần này vì cache chưa sẵn sàng. `hnsw.ef_search` chưa được backend PostgreSQL của phiên chẩn đoán nạp nên ghi null, không tự gán một mức giả định.

## Kết quả theo nhóm

| Nhóm | Số câu | Kết quả |
| --- | ---: | --- |
| Q01–Q10: tin tức | 10 | Đã gọi search thật; cùng lỗi `CACHE_BUILD_REQUIRED` |
| Q21–Q29: PDF FPT 2024 | 9 | Đã gọi search thật; cùng lỗi cache. Ngoài ra index được chọn không có chunk nguồn PDF (`raw_payloads`); không thay bằng dữ liệu clean |
| Q31–Q38: tài chính clean | 8 | Đã gọi search thật; cùng lỗi cache. Phạm vi FPT/2026-Q2 có 27 chunk theo metadata, chưa xác minh được kết quả tìm kiếm |
| Câu tính toán | 9 | Ngoài chức năng của module retrieval này; chưa chạy phép tính |
| Tra đúng phiên giá | 2 | Cần truy vấn dữ liệu giá có provenance; chưa chạy |
| Từ chối khi thiếu bằng chứng | 2 | Cần tầng trả lời/đánh giá phạm vi; chưa chạy |

Tổng: **27 câu truy xuất bị chặn, 13 câu cần tầng chức năng khác**. Đây không phải 0/40 câu trả lời sai và cũng không phải một bộ kiểm thử end-to-end đã đạt.

## Nguyên nhân chặn đã xác minh

Theo thứ tự duyệt cache, chunk đầu tiên là báo cáo FPT 2026-Q1, `chunk_id=67c086c3-467b-5e97-bdbc-027e1f6344b4`. Resolver dùng renderer ghi trong locator (`db-financial-v3`) nhưng fingerprint section đọc lại khác fingerprint khi lập chỉ mục:

- Lúc lập chỉ mục: `dc79f6c9e967decc383fe40551afcd877d3b0fe3ea25f5cc58d2ec017d078769`.
- Đọc lại hiện tại: `1834dca8f2b734c640dcb74eb8425efa250223a815778bfdffd7ecbc801c38ca`.

Mẫu hồ sơ FPT cũng có fingerprint khác. Ba mẫu khác — một bản tin VIC, một đoạn giá CTR và một đoạn chỉ số — đọc lại và xác minh content hash thành công. Mỗi nhóm chỉ lấy mẫu nhỏ theo thứ tự document/chunk; không suy rộng thành toàn bộ nguồn của nhóm đều đúng hoặc đều lỗi.

Fingerprint khác xác nhận biểu diễn nguồn hiện tại không khớp biểu diễn đã lập chỉ mục; **chưa đủ để kết luận số liệu gốc thay đổi hay renderer thay đổi**. Cần đối chiếu snapshot và renderer đã dùng lúc ingest.

`build_cache` hiện yêu cầu xác minh toàn index và dừng ngay khi có một nguồn lỗi. Do đó lỗi một nguồn tài chính có thể chặn cả truy vấn tin tức, dù mẫu tin tức vẫn xác minh được. Đây là trở ngại thực tế của cơ chế dựng cache hiện tại.

## Việc cần xử lý trước lần đo tiếp theo

1. Đối chiếu nguồn/snapshot và renderer của chunk lỗi, đồng bộ theo phiên bản được chốt; không xóa hash hoặc bỏ qua xác minh để làm đẹp kết quả.
2. Dựng cache thành công rồi đo cùng bộ câu với lọc/không lọc, top 5/top 10 và các ca cố ý sai công ty/kỳ. Có thể cân nhắc cache theo phạm vi để nguồn lỗi ngoài phạm vi không chặn tất cả, nhưng chưa thực hiện trong lần kiểm tra này.
3. Nạp/chốt đúng PDF FPT 2024 cho Q21–Q30; dữ liệu clean cùng năm không thay thế PDF.
4. Chạy các ca giá, tính toán và từ chối ở tầng tương ứng. Golden hiện là bản đề xuất, chưa có gold đã duyệt nên chưa công bố Recall/MRR hoặc kết luận 40/40.

File Golden giữ nguyên, SHA-256 `403b9d49eed3192ae2a2212a1b5469ac019ee37771fb95cb51a2efbefac3a65b`. Lần chạy chẩn đoán hoàn tất có exit 0 trong 38,68 giây; exit 0 chỉ xác nhận báo cáo đã được ghi, không xác nhận retrieval đã đạt.
