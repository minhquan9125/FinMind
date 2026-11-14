# Mô phỏng người dùng phổ thông và có chuyên môn

Phần parser kiểm tra hội thoại xác định; phần LIVE (nếu chạy) dùng corpus thật và Gemini thật. Kiểm tra qua service backend hiện có, chưa mô phỏng thao tác trình duyệt/auth.

## Kết quả và giới hạn

- Hiểu câu hỏi: 16/24 hội thoại đạt kỳ vọng.
- Luồng LIVE: 4/6 hội thoại đạt; trạng thái COMPLETED.
- Đây là các kịch bản mẫu, không phải xác nhận mọi câu tiếng Việt đều được hỗ trợ.
- Ca hỏi nguồn là kiểm tra chức năng mong đợi chưa có; ca SSI cho phép NO_DATA khi vẫn giữ đúng mã/kỳ/chỉ tiêu.

- Gemini: 4 generation; 7585 token đã dùng hoặc giữ dự phòng; 1 lượt chưa xác định usage chính xác.

## Ưu tiên xử lý

1. Sai chỉ tiêu: LNST thuộc cổ đông công ty mẹ đang bị hiểu thành LNST tổng và phạm vi báo cáo riêng.
2. Sai kỳ: quý/năm nằm xa nhau hoặc bổ sung năm ở lượt sau làm mất quý; kỳ canonical chưa gắn basis.
3. Thiếu cách nói phổ biến: lời, LNST, LNTT; mã viết tắt chỉ tiêu còn bị coi là ticker.
4. Hỏi nguồn của câu trước đang truy vấn lại, chưa trả tham chiếu của lượt trước.
5. Tin tức nhiều đoạn có thể vượt trần output 2048, cần giảm số claim/quote hoặc chia phạm vi; không suy ra lỗi do thiếu nguồn.

## Hiểu câu hỏi: 16/24 hội thoại đạt

### ĐẠT — Hỏi bổ sung từng thông tin (pho_thong)

- Người dùng: lợi nhuận là bao nhiêu
- Hệ thống: Bạn muốn xem công ty nào?
- Người dùng: fpt
- Hệ thống: Bạn muốn lợi nhuận trước thuế hay sau thuế?
- Người dùng: sau thuế
- Hệ thống: Bạn muốn xem kỳ nào? Ví dụ: quý 2/2026, năm 2025 hoặc tin tức tháng 9/2026.
- Người dùng: quý 4 2025
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.

### CHƯA ĐẠT — Câu đầy đủ nhưng thứ tự từ tự nhiên (pho_thong)

- Người dùng: lợi nhuận của fpt quý 4 sau thuế năm 2025 là bao nhiêu
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.
- Lệch kỳ vọng: periods: cần ['2025-Q4'], nhận ['2025']

### CHƯA ĐẠT — Nhớ quý khi người dùng bổ sung năm (pho_thong)

- Người dùng: lợi nhuận của fpt quý 4 sau thuế là bao nhiêu
- Hệ thống: Bạn muốn xem kỳ nào? Ví dụ: quý 2/2026, năm 2025 hoặc tin tức tháng 9/2026.
- Người dùng: 2025
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.
- Lệch kỳ vọng: periods: cần ['2025-Q4'], nhận ['2025']

### CHƯA ĐẠT — Dùng từ lời thay lợi nhuận (pho_thong)

- Người dùng: FPT lời bao nhiêu năm 2025
- Hệ thống: Bạn muốn xem chỉ tiêu nào? Ví dụ: tổng tài sản, tiền và tương đương tiền, doanh thu thuần.
- Người dùng: sau thuế
- Hệ thống: Bạn muốn xem chỉ tiêu nào? Ví dụ: tổng tài sản, tiền và tương đương tiền, doanh thu thuần.
- Lệch kỳ vọng: decision: cần SEARCH, nhận ASK_CLARIFICATION
- Lệch kỳ vọng: metric_code: cần PROFIT_AFTER_TAX, nhận None

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

### CHƯA ĐẠT — Hỏi nguồn của câu trước (pho_thong)

- Người dùng: tổng tài sản FPT năm 2025
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.
- Người dùng: nguồn đâu
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.
- Lệch kỳ vọng: decision: cần RESOLVE_REFERENCE, nhận SEARCH

### ĐẠT — Hỏi giá cổ phiếu (pho_thong)

- Người dùng: giá cổ phiếu FPT hôm nay
- Hệ thống: Câu hỏi giá cần luồng tra cứu giá có cấu trúc; chat này hiện tìm báo cáo tài chính và tin tức.

### ĐẠT — Hỏi nên mua hay không (pho_thong)

- Người dùng: nên mua FPT không
- Hệ thống: Chức năng này không cung cấp tư vấn mua bán.

### CHƯA ĐẠT — Viết tắt LNST (chuyen_mon)

- Người dùng: LNST FPT quý 4/2025
- Hệ thống: Bạn muốn xem chỉ tiêu nào? Ví dụ: tổng tài sản, tiền và tương đương tiền, doanh thu thuần.
- Lệch kỳ vọng: decision: cần SEARCH, nhận ASK_CLARIFICATION
- Lệch kỳ vọng: metric_code: cần PROFIT_AFTER_TAX, nhận None

### CHƯA ĐẠT — Viết tắt LNTT (chuyen_mon)

- Người dùng: LNTT FPT quý 4/2025
- Hệ thống: Bạn muốn xem chỉ tiêu nào? Ví dụ: tổng tài sản, tiền và tương đương tiền, doanh thu thuần.
- Lệch kỳ vọng: decision: cần SEARCH, nhận ASK_CLARIFICATION
- Lệch kỳ vọng: metric_code: cần PROFIT_BEFORE_TAX, nhận None

### CHƯA ĐẠT — LNST cổ đông công ty mẹ phải khác LNST tổng (chuyen_mon)

- Người dùng: lợi nhuận sau thuế thuộc cổ đông công ty mẹ FPT quý 4/2025
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.
- Lệch kỳ vọng: metric_code: cần PARENT_NET_PROFIT, nhận PROFIT_AFTER_TAX
- Lệch kỳ vọng: reporting_entity: cần UNKNOWN, nhận PARENT

### ĐẠT — Lợi nhuận chưa phân phối phải khác LNST (chuyen_mon)

- Người dùng: lợi nhuận sau thuế chưa phân phối FPT quý 4/2025
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.

### ĐẠT — Lũy kế không được lấy riêng quý (chuyen_mon)

- Người dùng: lợi nhuận sau thuế FPT lũy kế quý 3/2025
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.

### ĐẠT — Riêng quý không được lấy lũy kế (chuyen_mon)

- Người dùng: lợi nhuận sau thuế FPT quý 4/2025
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.

### CHƯA ĐẠT — Kỳ canonical vẫn phải hiểu riêng quý (chuyen_mon)

- Người dùng: PROFIT_AFTER_TAX FPT 2025-Q4
- Hệ thống: Đang tìm bằng chứng trong corpus đã chọn.
- Lệch kỳ vọng: measure_basis: cần STANDALONE_QUARTER, nhận None

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

## Nguồn và trả lời thật: 4/6 hội thoại đạt

### ĐẠT — Bổ sung thông tin và lấy số lợi nhuận (pho_thong)

- Người dùng: lợi nhuận là bao nhiêu
- Hệ thống: Bạn muốn xem công ty nào?
- Người dùng: fpt
- Hệ thống: Bạn muốn lợi nhuận trước thuế hay sau thuế?
- Người dùng: sau thuế
- Hệ thống: Bạn muốn xem kỳ nào? Ví dụ: quý 2/2026, năm 2025 hoặc tin tức tháng 9/2026.
- Người dùng: quý 4 2025
- Hệ thống: FPT ghi nhận lợi nhuận sau thuế trong quý 4/2025 là 2,994,964,817,096. [1]

Nguồn chưa xác minh đơn vị của chỉ tiêu; giữ nguyên giá trị gốc.

Nguồn chưa xác định phạm vi báo cáo hợp nhất hay riêng lẻ.

### CHƯA ĐẠT — Câu tự nhiên đủ thông tin (pho_thong)

- Người dùng: lợi nhuận của fpt quý 4 sau thuế năm 2025 là bao nhiêu
- Hệ thống: Chưa tìm thấy bằng chứng phù hợp trong corpus cho đúng mã, kỳ và chỉ tiêu này.
- Lệch kỳ vọng: periods: cần ['2025-Q4'], nhận ['2025']

### ĐẠT — Đổi mã giữ câu trước (pho_thong)

- Người dùng: tiền và tương đương tiền FPT quý 2/2026
- Hệ thống: Tại thời điểm cuối quý 2/2026, tiền và các khoản tương đương tiền của FPT là 8,843,161,132,730. [1]

Nguồn chưa xác minh đơn vị của chỉ tiêu; giữ nguyên giá trị gốc.

Nguồn chưa xác định phạm vi báo cáo hợp nhất hay riêng lẻ.
- Người dùng: còn SSI
- Hệ thống: Chưa tìm thấy bằng chứng phù hợp trong corpus cho đúng mã, kỳ và chỉ tiêu này.

### ĐẠT — Lợi nhuận trước thuế riêng quý (chuyen_mon)

- Người dùng: lợi nhuận trước thuế FPT quý 4/2025
- Hệ thống: Lợi nhuận trước thuế của Công ty Cổ phần FPT trong quý 4/2025 (riêng quý) là 3,503,168,140,397. [1]

Nguồn chưa xác minh đơn vị của chỉ tiêu; giữ nguyên giá trị gốc.

Nguồn chưa xác định phạm vi báo cáo hợp nhất hay riêng lẻ.

### CHƯA ĐẠT — Tin theo nhà xuất bản và ngày (chuyen_mon)

- Người dùng: tin tức FPT theo CafeF ngày 29/9/2026
- Hệ thống: Đã tìm thấy tài liệu nhưng dịch vụ tạo câu trả lời đang tạm thời không khả dụng. Vui lòng thử lại sau.

### ĐẠT — Kỳ tương lai không có nguồn (chuyen_mon)

- Người dùng: tổng tài sản FPT quý 4/2099
- Hệ thống: Chưa tìm thấy bằng chứng phù hợp trong corpus cho đúng mã, kỳ và chỉ tiêu này.
