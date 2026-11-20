# Đánh giá mua/bán có điều kiện

Nhánh này chỉ bổ sung cho câu hỏi quyết định trực tiếp như “mua FPT thì có được không”, “có nên mua VCB” hoặc “bán MBB có ổn không”. Nó không thay các route số liệu, quan hệ, BCTN, NEWS hoặc lọc danh sách mã.

## Luồng

1. Xác định một mã cụ thể; thiếu mã hoặc có nhiều mã thì hỏi lại. Chỉ dùng mã cũ khi có lời tham chiếu rõ ràng.
2. Gọi lại nhánh phân tích thị trường hiện có để đọc giá, xu hướng, BCTC và NEWS. Không yêu cầu mô hình tự quyết định mua/bán.
3. Giữ nguyên gate nguồn, số liệu và citation. Nếu bản diễn đạt không dùng được, thử trả các dòng nguồn nguyên văn qua chính bộ kiểm tra quote/số liệu hiện có, không gọi mô hình lần nữa. Khi cả bản diễn đạt và bản trích nguồn đều chưa hợp lệ, không thêm đánh giá. Hash/source/scope lỗi vẫn bị chặn.
4. Thêm phần **Nhận định có điều kiện** bằng template tách biệt với factual claims. Chỉ diễn giải xu hướng từ evidence đã được trích dẫn và nguồn có trạng thái APPROVED; chưa đủ điều kiện thì nói chưa đủ cơ sở.
5. Chưa có thời gian nắm giữ thì hỏi ngắn hạn/dài hạn. Câu trả lời thời hạn có thể tiếp tục đánh giá đang hỏi.

## Giới hạn

- Không tự tạo số, giá mục tiêu, tỷ trọng tiền hoặc bảo đảm lợi nhuận.
- Không tự coi xu hướng tăng là giá hợp lý; định giá và rủi ro cá nhân chưa được xác định phải được nêu rõ.
- Dữ liệu chưa duyệt không tạo kết luận mua tích cực.
- Câu có nguồn/báo cáo hoặc ngày/năm lịch sử được chỉ rõ giữ route cũ, không thay bằng dữ liệu hôm nay.
- Dữ kiện từ mô hình và phần diễn giải có điều kiện được lưu riêng (`conditional_assessment`, phiên bản policy).
- Giữ nguyên prompt và citation gate của các nhánh khác. Không sửa FE, schema hoặc quyền database.

Test dùng provider giả lập và nguồn fixture qua pipeline citation thật; không coi các test này là nghiệm thu Gemini trên dữ liệu VPS.
