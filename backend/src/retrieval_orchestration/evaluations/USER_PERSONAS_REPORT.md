# Mô phỏng người dùng phổ thông và có chuyên môn

Phần parser kiểm tra hội thoại xác định; phần LIVE (nếu chạy) dùng corpus thật và Gemini thật. Kiểm tra qua service backend hiện có, chưa mô phỏng thao tác trình duyệt/auth.

## Kết quả và giới hạn

- Hiểu câu hỏi: 24/24 hội thoại đạt kỳ vọng.
- Luồng LIVE: 9/9 hội thoại đạt; trạng thái COMPLETED.
- Đây là các kịch bản mẫu, không phải xác nhận mọi câu tiếng Việt đều được hỗ trợ.
- Ca hỏi nguồn kiểm tra tham chiếu đã lưu; ca SSI cho phép NO_DATA khi vẫn giữ đúng mã/kỳ/chỉ tiêu.
- Transcript LIVE giữ nguyên lúc chạy; tên nguồn được làm gọn thêm sau lượt đo và đã kiểm tra bằng regression lưu phiên.

- Gemini: 8 generation; 10499 token đã dùng hoặc giữ dự phòng; 0 lượt chưa xác định usage chính xác.

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
- Hệ thống: Bạn muốn lợi nhuận trước thuế hay sau thuế?
- Người dùng: sau thuế
- Hệ thống: Bạn muốn xem kỳ nào? Ví dụ: quý 2/2026, năm 2025 hoặc tin tức tháng 9/2026.
- Người dùng: quý 4 2025
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.

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
- Hệ thống: Bạn muốn lợi nhuận trước thuế hay sau thuế?
- Người dùng: sau thuế
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.

### ĐẠT — Gõ không dấu (pho_thong)

- Người dùng: loi nhuan cua fpt quy 4 sau thue nam 2025
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.

### ĐẠT — Gõ sai một dấu trong lợi nhuận (pho_thong)

- Người dùng: lợi nhuân fpt năm 2025
- Hệ thống: Bạn muốn lợi nhuận trước thuế hay sau thuế?
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
- Hệ thống: Câu hỏi giá cần luồng tra cứu giá có cấu trúc; chat này hiện tìm báo cáo tài chính và tin tức.

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
- Hệ thống: Bạn muốn xem chỉ tiêu nào trước? Hãy tách mỗi chỉ tiêu thành một câu hỏi.

### ĐẠT — Hai nhà xuất bản cần làm rõ (chuyen_mon)

- Người dùng: tin tức FPT từ CafeF và FireAnt tháng 9/2026
- Hệ thống: Bạn muốn xem nguồn CafeF hay FireAnt trước?

### ĐẠT — Ngày tin tức chính xác (chuyen_mon)

- Người dùng: tin tức FPT CafeF ngày 29/9/2026
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.

### ĐẠT — Kỳ không hợp lệ phải hỏi lại (chuyen_mon)

- Người dùng: lợi nhuận sau thuế FPT quý 5/2025
- Hệ thống: Bạn muốn xem quý nào? Vui lòng nêu một kỳ hợp lệ từ quý 1 đến quý 4.

## Nguồn và trả lời thật: 9/9 hội thoại đạt

### ĐẠT — Bổ sung thông tin và lấy số lợi nhuận (pho_thong)

- Người dùng: lợi nhuận là bao nhiêu
- Hệ thống: Bạn muốn xem công ty nào?
- Người dùng: fpt
- Hệ thống: Bạn muốn lợi nhuận trước thuế hay sau thuế?
- Người dùng: sau thuế
- Hệ thống: Bạn muốn xem kỳ nào? Ví dụ: quý 2/2026, năm 2025 hoặc tin tức tháng 9/2026.
- Người dùng: quý 4 2025
- Hệ thống: Lợi nhuận sau thuế của Công ty Cổ phần FPT trong quý 4/2025 (riêng quý) là 2,994,964,817,096. [1]

Nguồn chưa xác minh đơn vị của chỉ tiêu; giữ nguyên giá trị gốc.

Nguồn chưa xác định phạm vi báo cáo hợp nhất hay riêng lẻ.
- Người dùng: nguồn đâu
- Hệ thống: Nguồn của câu trả lời trước:

[1] Clean mapped financial report 57d5a4ab-366e-55f6-8a4a-025d70490673 — Báo cáo Kết quả hoạt động kinh doanh · quý 4/2025 (riêng quý)

### ĐẠT — Câu tự nhiên đủ thông tin (pho_thong)

- Người dùng: lợi nhuận của fpt quý 4 sau thuế năm 2025 là bao nhiêu
- Hệ thống: FPT ghi nhận lợi nhuận sau thuế trong quý 4/2025 là 2,994,964,817,096. [1]

Nguồn chưa xác minh đơn vị của chỉ tiêu; giữ nguyên giá trị gốc.

Nguồn chưa xác định phạm vi báo cáo hợp nhất hay riêng lẻ.

### ĐẠT — Đổi mã giữ câu trước (pho_thong)

- Người dùng: tiền và tương đương tiền FPT quý 2/2026
- Hệ thống: Tại cuối quý 2/2026, tiền và các khoản tương đương tiền của FPT là 8,843,161,132,730. [1]

Nguồn chưa xác minh đơn vị của chỉ tiêu; giữ nguyên giá trị gốc.

Nguồn chưa xác định phạm vi báo cáo hợp nhất hay riêng lẻ.
- Người dùng: còn SSI
- Hệ thống: Chưa tìm thấy bằng chứng phù hợp trong corpus cho đúng mã, kỳ và chỉ tiêu này.

### ĐẠT — Lợi nhuận trước thuế riêng quý (chuyen_mon)

- Người dùng: lợi nhuận trước thuế FPT quý 4/2025
- Hệ thống: Lợi nhuận trước thuế của Công ty Cổ phần FPT trong quý 4/2025 là 3,503,168,140,397. [1]

Nguồn chưa xác minh đơn vị của chỉ tiêu; giữ nguyên giá trị gốc.

Nguồn chưa xác định phạm vi báo cáo hợp nhất hay riêng lẻ.

### ĐẠT — Tin theo nhà xuất bản và ngày (chuyen_mon)

- Người dùng: tin tức FPT theo CafeF ngày 29/9/2026
- Hệ thống: Ngày 25/9, Công ty Cổ phần FPT công bố báo cáo kết quả đợt phát hành cổ phiếu để tăng vốn từ nguồn vốn chủ sở hữu với hơn 171,4 triệu cổ phiếu đã được phân phối cho 181.748 cổ đông. [1]

Lũy kế 8 tháng đầu năm 2026, FPT ghi nhận doanh thu 35.408 tỷ đồng và lợi nhuận trước thuế 7.648 tỷ đồng, lần lượt tăng 13,5% và 17,5% so với cùng kỳ. [2]

### ĐẠT — Kỳ tương lai không có nguồn (chuyen_mon)

- Người dùng: tổng tài sản FPT quý 4/2099
- Hệ thống: Chưa tìm thấy bằng chứng phù hợp trong corpus cho đúng mã, kỳ và chỉ tiêu này.

### ĐẠT — LNST thuộc cổ đông công ty mẹ (chuyen_mon)

- Người dùng: LNST cổ đông công ty mẹ FPT quý 4/2025
- Hệ thống: FPT ghi nhận lợi nhuận sau thuế thuộc cổ đông công ty mẹ trong quý 4/2025 là 2,509,522,220,120. [1]

Nguồn chưa xác minh đơn vị của chỉ tiêu; giữ nguyên giá trị gốc.

Nguồn chưa xác định phạm vi báo cáo hợp nhất hay riêng lẻ.

### ĐẠT — Bổ sung năm giữ quý trước đó (pho_thong)

- Người dùng: lợi nhuận của FPT quý 4 sau thuế là bao nhiêu
- Hệ thống: Bạn muốn xem quý 4 của năm nào?
- Người dùng: 2025
- Hệ thống: Lợi nhuận sau thuế quý 4/2025 của Công ty Cổ phần FPT đạt 2,994,964,817,096. [1]

Nguồn chưa xác minh đơn vị của chỉ tiêu; giữ nguyên giá trị gốc.

Nguồn chưa xác định phạm vi báo cáo hợp nhất hay riêng lẻ.

### ĐẠT — Viết tắt LNTT (chuyen_mon)

- Người dùng: LNTT FPT quý 4/2025
- Hệ thống: Lợi nhuận trước thuế của Công ty Cổ phần FPT trong quý 4/2025 là 3,503,168,140,397. [1]

Nguồn chưa xác minh đơn vị của chỉ tiêu; giữ nguyên giá trị gốc.

Nguồn chưa xác định phạm vi báo cáo hợp nhất hay riêng lẻ.
