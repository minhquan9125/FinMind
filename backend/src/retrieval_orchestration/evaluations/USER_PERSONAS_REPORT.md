# Mô phỏng người dùng phổ thông và có chuyên môn

Phần parser kiểm tra hội thoại xác định; phần LIVE (nếu chạy) dùng corpus thật và Gemini thật. Kiểm tra qua service backend hiện có, chưa mô phỏng thao tác trình duyệt/auth.

## Kết quả và giới hạn

- Hiểu câu hỏi: 24/24 hội thoại đạt kỳ vọng.
- Luồng LIVE: 0/0 hội thoại đạt; trạng thái NOT_RUN.
- Đây là các kịch bản mẫu, không phải xác nhận mọi câu tiếng Việt đều được hỗ trợ.
- Ca hỏi nguồn kiểm tra tham chiếu đã lưu; ca SSI cho phép NO_DATA khi vẫn giữ đúng mã/kỳ/chỉ tiêu.
- Transcript LIVE giữ nguyên lúc chạy; tên nguồn được làm gọn thêm sau lượt đo và đã kiểm tra bằng regression lưu phiên.

## Những lỗi đã kiểm tra lại

1. Phân biệt LNST thuộc cổ đông công ty mẹ với LNST tổng và phạm vi báo cáo riêng.
2. Giữ quý khi quý/năm nằm xa nhau hoặc bổ sung năm; kỳ canonical có basis.
3. Hiểu lời, LNST, LNTT; không coi viết tắt chỉ tiêu là ticker.
4. Hỏi nguồn dùng câu trả lời đã lưu, không tìm kiếm/gọi Gemini lại.
5. Tin tức giới hạn số claim và quote trong output2048, không tăng trần token.

Bản trước sửa: `USER_PERSONAS_REPORT_BEFORE_FIXES.md` và `user_personas_results_before_fixes.json`.

## Hiểu câu hỏi: 24/24 hội thoại đạt

### ĐẠT — Hỏi bổ sung từng thông tin (pho_thong)

- Người dùng: lợi nhuận là bao nhiêu
- Hệ thống: Bạn muốn xem công ty nào?
- Người dùng: fpt
- Hệ thống: Bạn muốn xem loại lợi nhuận nào? 1. Lợi nhuận trước thuế. 2. Lợi nhuận sau thuế. 3. LNST thuộc cổ đông công ty mẹ.
- Người dùng: sau thuế
- Hệ thống: Không có thời gian cụ thể; đang dùng kỳ mới nhất có trong nguồn.

### ĐẠT — Câu đầy đủ nhưng thứ tự từ tự nhiên (pho_thong)

- Người dùng: lợi nhuận của fpt quý 4 sau thuế năm 2025 là bao nhiêu
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.

### ĐẠT — Nhớ quý khi người dùng bổ sung năm (pho_thong)

- Người dùng: lợi nhuận của fpt quý 4 sau thuế là bao nhiêu
- Hệ thống: Bạn muốn xem quý 4 của năm nào?
- Người dùng: 2025
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.

### ĐẠT — Dùng từ lời thay lợi nhuận (pho_thong)

- Người dùng: FPT lời bao nhiêu năm 2025
- Hệ thống: Bạn muốn xem loại lợi nhuận nào? 1. Lợi nhuận trước thuế. 2. Lợi nhuận sau thuế. 3. LNST thuộc cổ đông công ty mẹ.
- Người dùng: sau thuế
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.

### ĐẠT — Gõ không dấu (pho_thong)

- Người dùng: loi nhuan cua fpt quy 4 sau thue nam 2025
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.

### ĐẠT — Gõ sai một dấu trong lợi nhuận (pho_thong)

- Người dùng: lợi nhuân fpt năm 2025
- Hệ thống: Bạn muốn xem loại lợi nhuận nào? 1. Lợi nhuận trước thuế. 2. Lợi nhuận sau thuế. 3. LNST thuộc cổ đông công ty mẹ.
- Người dùng: sau thuế
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.

### ĐẠT — Đổi mã bằng câu ngắn (pho_thong)

- Người dùng: tiền và tương đương tiền FPT quý 2/2026
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.
- Người dùng: còn SSI
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.

### ĐẠT — Đổi năm bằng câu ngắn (pho_thong)

- Người dùng: tổng tài sản FPT năm 2025
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.
- Người dùng: còn năm 2024
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.

### ĐẠT — Bắt đầu lại hội thoại (pho_thong)

- Người dùng: tổng tài sản FPT năm 2025
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.
- Người dùng: /moi
- Hệ thống: Đã bắt đầu câu hỏi mới. Bạn muốn xem mã, chỉ tiêu hoặc tin tức nào?

### ĐẠT — Hỏi nguồn của câu trước (pho_thong)

- Người dùng: tổng tài sản FPT năm 2025
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.
- Người dùng: nguồn đâu
- Hệ thống: Xem nguồn của câu trả lời trước.

### ĐẠT — Hỏi giá cổ phiếu (pho_thong)

- Người dùng: giá cổ phiếu FPT hôm nay
- Hệ thống: Đang tra cứu nguồn giá hoặc tin tức đang cập nhật.

### ĐẠT — Hỏi nên mua hay không (pho_thong)

- Người dùng: nên mua FPT không
- Hệ thống: Chức năng này không cung cấp tư vấn mua bán.

### ĐẠT — Viết tắt LNST (chuyen_mon)

- Người dùng: LNST FPT quý 4/2025
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.

### ĐẠT — Viết tắt LNTT (chuyen_mon)

- Người dùng: LNTT FPT quý 4/2025
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.

### ĐẠT — LNST cổ đông công ty mẹ phải khác LNST tổng (chuyen_mon)

- Người dùng: lợi nhuận sau thuế thuộc cổ đông công ty mẹ FPT quý 4/2025
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.

### ĐẠT — Lợi nhuận chưa phân phối phải khác LNST (chuyen_mon)

- Người dùng: lợi nhuận sau thuế chưa phân phối FPT quý 4/2025
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.

### ĐẠT — Lũy kế không được lấy riêng quý (chuyen_mon)

- Người dùng: lợi nhuận sau thuế FPT lũy kế quý 3/2025
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.

### ĐẠT — Riêng quý không được lấy lũy kế (chuyen_mon)

- Người dùng: lợi nhuận sau thuế FPT quý 4/2025
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.

### ĐẠT — Kỳ canonical vẫn phải hiểu riêng quý (chuyen_mon)

- Người dùng: PROFIT_AFTER_TAX FPT 2025-Q4
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.

### ĐẠT — Yêu cầu báo cáo hợp nhất (chuyen_mon)

- Người dùng: tổng tài sản FPT hợp nhất quý 2/2026
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.

### ĐẠT — Tách câu hỏi có nhiều chỉ tiêu (chuyen_mon)

- Người dùng: doanh thu thuần và lợi nhuận sau thuế FPT năm 2025
- Hệ thống: Bạn muốn xem loại chỉ tiêu nào? 1. Doanh thu thuần. 2. Lợi nhuận sau thuế.

### ĐẠT — Hai nhà xuất bản cần làm rõ (chuyen_mon)

- Người dùng: tin tức FPT từ CafeF và FireAnt tháng 9/2026
- Hệ thống: Bạn muốn xem tin theo CafeF hay FireAnt?

### ĐẠT — Ngày tin tức chính xác (chuyen_mon)

- Người dùng: tin tức FPT CafeF ngày 29/9/2026
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.

### ĐẠT — Kỳ không hợp lệ phải hỏi lại (chuyen_mon)

- Người dùng: lợi nhuận sau thuế FPT quý 5/2025
- Hệ thống: Bạn muốn xem quý nào? Vui lòng nêu một kỳ hợp lệ từ quý 1 đến quý 4.
