A. Tách cấu trúc trang — giải quyết G1–G3
- Chốt định dạng chung Document IR: mỗi trang có khối chữ, bảng, dòng và ô.
- Chuyển nội dung từ lớp chữ PDF và Tesseract sang định dạng đó.
- Đổi Gemini để trả về cùng cấu trúc, rồi hợp nhất kết quả theo từng ô.
- Loại menu/header/footer lặp lại.
- Phân loại trang: bảng cân đối, kết quả kinh doanh, lưu chuyển tiền tệ, thuyết minh, văn xuôi…
B. Chuẩn hoá và ánh xạ vào template
- Nhận diện thông tư, mẫu báo cáo, kỳ, đơn vị, công ty và phạm vi riêng/hợp nhất.
- Chuẩn hoá số nhưng giữ nguyên chuỗi gốc.
- Ánh xạ dòng báo cáo sang metric_id trong template.
- Xử lý nhãn mơ hồ hoặc thiếu mã dòng; riêng biểu mẫu ngân hàng TT49 cần cách xử lý phù hợp.
Điểm cần cập nhật: README có đoạn B4 nói template còn thiếu sign_convention, statement/section và có vấn đề về phạm vi. Nhưng template hiện có trong thư mục templates/ đã ở schema 2.3.0 và tài liệu cập nhật nói các trường đó đã được bổ sung/xử lý. Có vẻ README phần này đang dựa trên bản template cũ. Dù vậy, ánh xạ từ mã dòng của mẫu báo cáo sang metric_id vẫn là việc riêng cần làm; template chỉ số chung chưa thay thế phần đó.
C. Kiểm chứng và đưa trường hợp không chắc chắn cho người duyệt
- Tạo luật kiểm tra đẳng thức kế toán.
- Quyết định theo từng ô, không gắn cờ cả trang chỉ vì hai bộ OCR lệch nhau.
- Dùng mã lý do rõ ràng như EXTRACTOR_DISAGREE, SUM_MISMATCH, TEMPLATE_UNKNOWN.
- Làm màn hình để người dùng xem ô cần duyệt cạnh ảnh trang.
D. Lưu dữ liệu có cấu trúc
- Tạo nơi lưu từng trang và kết quả Document IR.
- Lưu template báo cáo, template chỉ số và dữ liệu quan sát.
- Lưu kỳ so sánh, chiều dữ liệu, giá trị gốc, độ tin cậy, kết quả kiểm tra và vị trí truy ngược trên PDF.
- README cũng ghi một số file hợp đồng/database được tài liệu template tham chiếu nhưng chưa thấy trong repo.
E. Đưa vào vận hành và đo độ chính xác
- Chuyển từ gọi Gemini qua agy sang Gemini API.
- Thêm chống xử lý trùng, retry và giới hạn số tác vụ chạy đồng thời.
- Đóng gói môi trường chạy để không phụ thuộc riêng macOS.
- Tạo bộ báo cáo đã chép/kiểm tra thủ công để đo độ chính xác và hiệu chỉnh ngưỡng.
Tóm lại theo thứ tự: tách trang thành bảng/dòng/ô → nhận diện loại trang và ngữ cảnh → ánh xạ vào template → chuẩn hoá và kiểm chứng → lưu vào database → đánh giá trên bộ dữ liệu chuẩn.