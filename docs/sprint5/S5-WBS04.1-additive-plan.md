# Giữ mẫu gốc và bổ sung — kế hoạch 12/11/2026

Đóng băng trước khi xem điểm của hai ứng viên. Không thay baseline hoặc ngưỡng.

## Phân tích 9 ca hồi quy của bản thay thế balanced

- NEWS T014/T015/T016: mất các mẫu tóm tắt/chép bài tin và các biến thể không dấu;
  ví dụ thắng ở bản gốc thuộc NEWS, nhưng bản thay thế thắng bằng MIXED/REPORT_CONTENT.
- ENTITY_RELATION T028: bản gốc có mẫu tìm doanh nghiệp tham gia sự kiện; bản thay
  thế tập trung sở hữu/công ty mẹ/đối tác, chưa có mẫu cùng thao tác sự kiện.
- TREND T031/T033/T034/T036: mất các mẫu chuỗi giá, nhận định chiều hướng và các
  biến thể; các mẫu đọc số/so chênh lệch của bản thay thế thắng thay TREND.
- MIXED T038: bản gốc có mẫu chức vụ + nội dung BCTN; khi thay toàn bộ, mẫu chức vụ
  một ý đứng đầu. Đây là bằng chứng thay thư viện làm mất độ phủ, không khẳng định
  giữ mẫu cũ sẽ tự động ngăn mọi hồi quy do cạnh tranh từ mẫu bổ sung.

## Hai ứng viên, cùng cosine-max-per-label-v1

1. `add_all`: giữ nguyên 90 hàng/vector gốc, nối 112 hàng cân bằng đã đóng băng.
2. `add_focused`: giữ nguyên 90 hàng/vector gốc, chỉ nối 48 hàng PERSON_ROLE,
   ENTITY_RELATION và MIXED từ thư viện cân bằng. Các nhãn còn lại dùng mẫu gốc.

Không che ticker, không viết lại câu/nhãn từ đáp án test. Không tạo thêm mẫu mới
sau khi xem kết quả. Dùng vector model thật đã lưu của thí nghiệm trước; không
nhúng lại mẫu hoặc query đã có cache chỉ vì đổi phép nối thư viện.

## Chốt một ứng viên trước lượt kiểm tra sau

- Development: 84 câu; regression: 56 câu cũ (47 có nhãn); known: 8 câu đã biết.
  Tất cả đã xem nên chỉ phục vụ phát triển, không gọi là đánh giá độc lập.
- Chỉ đánh dấu đủ điều kiện gửi đề nghị thay bản chính nếu top-1 dev tăng,
  không có câu cũ đúng→sai và không tăng số sai tuyến vượt ngưỡng trên dev/regression.
- Chọn một ứng viên để đánh giá sau bằng thứ tự cố định: đủ điều kiện trước;
  ít sai tuyến vượt ngưỡng regression rồi dev; ít câu cũ đúng→sai; top-1 dev cao;
  top-1 regression cao; ít hàng mẫu hơn; tên tăng dần. Nếu không có ứng viên đạt
  điều kiện, vẫn đóng băng ứng viên tốt nhất để đo chẩn đoán, không coi đã đạt.
- Ghi selection.json, checksum thư viện/runner/nguồn và bộ kết quả phát triển
  trước khi runner holdout được phép đọc/chấm 28 câu later-check.
- Holdout chấm đúng một lượt cả baseline và ứng viên đã chọn, cùng model/revision;
  không thay ứng viên hoặc cách chấm sau khi nhìn kết quả. Nếu phát sinh lỗi I/O
  hoặc model, dùng output mới và ghi rõ lần không hoàn tất; không gọi là lượt mới độc lập.
- 28 câu do cùng tác giả chuẩn bị từ trước, không phải test mù bên thứ ba. Không
  đọc/chấm sớm để chọn mẫu, nhưng không khẳng định người soạn chưa từng biết câu.

## Báo cáo

Top-1/3/5, confusion theo nhãn, thay công ty, đơn/kết hợp, số câu sửa được và hỏng,
ID từng ca; fallback và đúng/sai tuyến trong phần vượt ngưỡng. Giữ 0,65/0,08,
payload top-3; bảy thứ hạng chỉ phục vụ đo. Ánh xạ tuyến là mô phỏng theo trao đổi,
không gọi code 04.2 hoặc WebChat. Không sửa thư viện chính thức hay triển khai
ứng viên trước khi chất lượng được chứng minh và nhóm chốt bàn giao.
