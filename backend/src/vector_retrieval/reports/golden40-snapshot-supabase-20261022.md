# Golden40 trên Supabase thật — kết quả sau sửa ngày 22/10/2026

**Đã sửa lỗi dựng cache và chạy thành công 18 câu đủ nguồn qua luồng truy xuất. Chưa chấm đúng/sai câu trả lời tài chính.**

Dữ liệu chi tiết từng câu, top 10, điểm BM25/dense/RRF, mã chunk, locator, hash và nội dung: [JSON kết quả](golden40-snapshot-supabase-20261022.json).

## Kết quả quan sát

| Nhóm | Số câu | Kết quả |
| --- | ---: | --- |
| Tin tức Q01–Q10 | 10 | Truy xuất thật thành công, có lọc và không lọc |
| Tài chính clean Q31–Q38 | 8 | Truy xuất thật thành công, có lọc và không lọc |
| PDF FPT 2024 Q21–Q29 | 9 | Chưa có đúng nguồn PDF trong index; không thay bằng dữ liệu clean |
| Tính toán / tra phiên giá / từ chối | 13 | Ngoài tầng retrieval của module; chưa kiểm thử các chức năng đó |

18 câu đủ nguồn chạy 4 biến thể/câu: **72 lượt truy vấn không lỗi**, gồm 36 lượt có thể trả dữ liệu và **36 ca cố ý sai mã/kỳ đều trả rỗng**. Bộ lọc công ty/kỳ/loại tài liệu đúng phạm vi ở mọi kết quả trả về. Tổng cộng 177 hit có lọc và 180 hit không lọc; SHA-256 nội dung của cả **357 lượt hit** đều khớp hash lưu cùng chunk. Đây không phải 357 chunk phân biệt.

Q02 trả 7 hit có lọc vì phạm vi chỉ có 7 chunk; không tự lấy thêm dữ liệu ngoài phạm vi để đủ top 10. Các câu đủ nguồn còn lại trả 10 hit có lọc.

## Nguồn, model và phạm vi kiểm tra

- Index: `434ef5e0-6516-578d-8d18-721d21347e01`, **15.058 chunk active**, trạng thái quan sát **ACTIVE**. Task này không đổi trạng thái hoặc ghi dữ liệu Supabase.
- Vector và metadata truy vấn từ Supabase thật, transaction READ ONLY REPEATABLE READ. Nội dung là snapshot gốc `backend/.tmp/corpus-v2.content.manifest.json`, không phải dữ liệu mới nhất của bảng nguồn.
- Pin payload snapshot: `86e880eef3b39ddf2515951252025a8f58e700f80416ba24d6fabfe324362bd7`. Kết quả CLI ghi rõ `FROZEN_SNAPSHOT`; từng chunk phải khớp locator, vị trí và hash DB trước khi trả nội dung.
- Model embedding thật chạy cục bộ trên CPU: `BAAI/bge-m3@5617a9f61b028005a4858fdac845db406aefb181`. Đã tải đủ 2.271.145.830 byte, hash chính thức `b5e0ce3470abf5ef3831aa1bd5553b486803e83251590ab7ff35a117cf6aad38`. Không token Hugging Face, không gọi Gemini, không gửi dữ liệu nguồn lên API embedding.
- 18 vector câu hỏi được nhúng thật; vector của cùng câu được dùng lại giữa các biến thể bộ lọc. Chỉ dùng nguyên văn câu hỏi đã sửa, bộ lọc suy từ câu hỏi; không dùng đáp án hoặc ID gold làm đầu vào.
- Thời gian chạy: `2026-10-22T06:44:35.707877+00:00` → `2026-10-22T06:47:24.457526+00:00`; tổng **170.43 giây**, có dựng cache và tải model từ ổ đĩa.
- File Golden giữ nguyên SHA-256 `403b9d49eed3192ae2a2212a1b5469ac019ee37771fb95cb51a2efbefac3a65b`. Đề hiện chưa có gold được duyệt; `Recall`, `MRR`, `quality_pass` không được gán điểm.

## Lỗi đã xử lý và kiểm chứng

1. **Nguồn hiện tại lệch nguồn đã tạo vector.** Ví dụ snapshot ghi `CTCP FPT`, còn bảng doanh nghiệp hiện tại ghi `Công ty Cổ phần FPT`; tên trong header tài chính cũng đổi. Thêm chế độ snapshot tường minh có caller pin và xác minh từng row. Không bỏ hash, sửa nguồn, bỏ chunk lỗi hay nhúng lại vector.
2. **Kết nối bị ngắt khi lấy toàn bộ metadata trong một phản hồi.** Đổi sang keyset pagination 500 dòng theo `chunk_id` trong cùng transaction, chặn trùng/không tiến cursor, chỉ ghi cache khi đọc và kiểm tra đầy đủ. Actual candidate build đủ 15.058 chunk qua 31 trang trong 13,16 giây. CLI tích hợp cũng build thành công, exit 0.
3. **Thiếu model cục bộ.** Tải có giới hạn 2 luồng HTTPS theo từng phần, ghép file rồi xác minh hash chính thức; dọn đúng file phần do helper tạo sau khi xác minh thành công. Model nằm trong `.cache` được Git bỏ qua.

**76 kiểm thử offline của module đạt**, gồm paging, hash nguồn, cache, bộ lọc và CLI. Hai job nguồn/CLI và job paging đã qua cổng review độc lập trước tích hợp. Một lượt CLI `search` thực tế với Q01 cũng exit 0, trả 5 hit có provenance snapshot và hash nội dung hợp lệ.

## Độ trễ và kế hoạch truy vấn

- Trung vị có lọc: **1.97 giây/lượt**. Trung vị không lọc: **2.18 giây/lượt**. Câu đầu gồm khởi tạo model nên khoảng 35.32 giây; không dùng câu đầu đại diện cho trạng thái model đã nạp.
- Nhúng câu hỏi sau lần đầu có trung vị khoảng **215 ms**. Lượt không lọc tái sử dụng vector của lượt có lọc; hai thời gian trên không phải phép so sánh hai thuật toán độc lập.
- Chẩn đoán EXPLAIN ANALYZE riêng trên cùng SQL: phạm vi toàn index dùng `idx_text_chunks_embedding_hnsw`; phạm vi FPT/2026-Q2 chỉ có 27 chunk nên planner đọc theo khóa và sort khoảng cách chính xác. Đây là lựa chọn của PostgreSQL, không ép index hoặc đổi cấu hình DB.
- `hnsw.ef_search=40`, `candidates=50` là trần mỗi nhánh. Trong plan chẩn đoán không lọc, dense trả 40 ứng viên; không khẳng định luôn có đủ 50. Vector lưu DB chỉ được dùng cho chẩn đoán plan này; lượt Golden phía trên dùng embedding câu hỏi thật.

## Quan sát nội dung cần duyệt tiếp

Luồng chạy thành công và bộ lọc đúng chưa chứng minh các đoạn đứng đầu đã đủ bằng chứng. Chưa ghép kết quả thành câu trả lời tài chính và chưa tuyên bố 18 câu đúng.

- **Q03:** câu hỏi yêu cầu bài CafeF, nhưng hit đầu là bài FireAnt về cùng sự kiện. Bộ lọc hiện có mã/kỳ/loại tài liệu, chưa khóa nhà xuất bản theo một tham số riêng.
- **Q08:** hit đầu có nhãn ngày 06/08/2026 trong khi đề nhắc 05/08/2026. Cần duyệt bài/ngày gốc và quy ước múi giờ trước khi chấm đúng nguồn.
- **Q31:** hit đầu thuộc lưu chuyển tiền tệ và nhắc tiền đầu kỳ, trong khi đề hỏi chỉ tiêu tiền và tương đương tiền tại kỳ. Không lấy riêng hit đầu làm đáp án; cần duyệt đúng dòng và phạm vi báo cáo trong top-k.
- Nhãn `UNKNOWN` hoặc đơn vị nguồn chưa xác minh trong snapshot được giữ nguyên; không tự quy đổi thành VND, hợp nhất hay riêng quý.

Cần nạp/chốt đúng PDF cho 9 câu PDF; kiểm tra 13 câu còn lại ở tầng SQL/Decimal hoặc trả lời/từ chối; duyệt gold evidence và xem xét lọc nhà xuất bản/ngày/chỉ tiêu trước khi nghiệm thu chất lượng tìm kiếm.

## Tóm tắt từng câu đã truy xuất

Bảng dưới mô tả hit đầu và số hit, không phải đáp án được duyệt. Nội dung đầy đủ và các thứ hạng 1–10 nằm trong JSON.

| Câu | Hit có lọc | Có lọc (giây) | Không lọc (giây) | Đầu đoạn đứng thứ nhất |
| --- | ---: | ---: | ---: | --- |
| Q01 | 10 | 35.32 | 2.46 | Tin fireant \| 2026-10-01 \| TCB: Techcombank tất toán 2 lô trái phiếu sau 1 năm phát hành |
| Q02 | 7 | 2.04 | 2.23 | Tin fireant \| 2026-10-01 \| Lãi suất VietinBank cao nhất, gửi 300 triệu đồng nhận 36 triệu đồng tiền lãi |
| Q03 | 10 | 2.02 | 2.15 | Tin fireant \| 2026-09-29 \| FPT: Có gần 182.000 cổ đông, khối ngoại còn nắm 28,5% vốn |
| Q04 | 10 | 1.86 | 2.00 | Tin fireant \| 2026-09-29 \| FPT: Có gần 182.000 cổ đông, khối ngoại còn nắm 28,5% vốn |
| Q05 | 10 | 2.49 | 2.20 | Tin fireant \| 2026-09-29 \| Những ngân hàng có thể lãi trên 10.000 tỷ đồng trong quý III |
| Q06 | 10 | 1.82 | 2.15 | Tin fireant \| 2026-09-30 \| MB mở rộng vai trò kết nối dòng vốn |
| Q07 | 10 | 1.91 | 2.83 | Tin fireant \| 2026-10-14 \| Tài chính doanh nghiệp 24/7: Techcombank được chấp thuận tăng vốn, FPT thúc đẩy hợp tác lượng tử |
| Q08 | 10 | 1.99 | 2.05 | Tin cafef \| 2026-08-06 \| Không chỉ lãi lớn từ cho vay, vì đâu Vietcombank có khoản lãi 2.900 tỷ ngay sau khi nắm trọn toà tháp 35 tầng đắc địa hàng đầu phường Sài Gòn? |
| Q09 | 10 | 1.94 | 2.21 | Tin cafef \| 2026-09-28 \| TCBS: FPT viết code bằng AI nhanh hơn 30% nhưng năng suất dự án chỉ tăng 10% |
| Q10 | 10 | 1.91 | 2.25 | Tin cafef \| 2026-10-13 \| Nhân sự FPT xấp xỉ 90.000 người, tăng 3.682 người trong 9 tháng |
| Q31 | 10 | 1.98 | 2.23 | CTCP FPT (FPT) \| Báo cáo Lưu chuyển tiền tệ \| quý 2/2026 (riêng quý) \| Phạm vi: UNKNOWN \| Đơn vị: theo từng chỉ tiêu; đơn vị nguồn chưa xác minh nếu không ghi rõ |
| Q32 | 10 | 1.96 | 2.29 | CTCP FPT (FPT) \| Bảng Cân đối kế toán \| tại cuối quý 2/2026 \| Phạm vi: UNKNOWN \| Đơn vị: theo từng chỉ tiêu; đơn vị nguồn chưa xác minh nếu không ghi rõ |
| Q33 | 10 | 1.98 | 2.02 | CTCP FPT (FPT) \| Bảng Cân đối kế toán \| tại cuối quý 2/2026 \| Phạm vi: UNKNOWN \| Đơn vị: theo từng chỉ tiêu; đơn vị nguồn chưa xác minh nếu không ghi rõ |
| Q34 | 10 | 1.97 | 1.87 | CTCP FPT (FPT) \| Báo cáo Kết quả hoạt động kinh doanh \| quý 2/2026 (riêng quý) \| Phạm vi: UNKNOWN \| Đơn vị: theo từng chỉ tiêu; đơn vị nguồn chưa xác minh nếu không g |
| Q35 | 10 | 1.95 | 1.87 | CTCP FPT (FPT) \| Báo cáo Kết quả hoạt động kinh doanh \| quý 2/2026 (riêng quý) \| Phạm vi: UNKNOWN \| Đơn vị: theo từng chỉ tiêu; đơn vị nguồn chưa xác minh nếu không g |
| Q36 | 10 | 1.96 | 1.94 | CTCP FPT (FPT) \| Báo cáo Lưu chuyển tiền tệ \| quý 2/2026 (riêng quý) \| Phạm vi: UNKNOWN \| Đơn vị: theo từng chỉ tiêu; đơn vị nguồn chưa xác minh nếu không ghi rõ |
| Q37 | 10 | 2.04 | 2.21 | CTCP FPT (FPT) \| Bảng Cân đối kế toán \| tại cuối quý 2/2026 \| Phạm vi: UNKNOWN \| Đơn vị: theo từng chỉ tiêu; đơn vị nguồn chưa xác minh nếu không ghi rõ |
| Q38 | 10 | 2.02 | 1.96 | CTCP FPT (FPT) \| Chỉ số tài chính \| quý 2/2026 \| Phạm vi: UNKNOWN \| Đơn vị: theo từng chỉ tiêu; đơn vị nguồn chưa xác minh nếu không ghi rõ |

Mã nguồn và cách chạy: [README](../README.md). Báo cáo trước sửa được giữ riêng: [lần bị chặn cache](golden40-supabase-20261022.md).
