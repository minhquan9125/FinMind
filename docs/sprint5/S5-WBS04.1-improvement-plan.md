# Thử nghiệm cải thiện đối chiếu ý định — 11/11/2026

Trạng thái: kế hoạch đóng băng trước chạy; không bật vào runtime.

## Thiết kế

- Giữ nguyên taxonomy, artifact 03.3, matcher hiện tại và run01.
- So sánh bốn cấu hình theo thiết kế 2 × 2: thư viện gốc / thư viện cân bằng
  mới; văn bản gốc / thay ticker trong cả mẫu và query bằng “doanh nghiệp”.
- Thư viện cân bằng là bản DRAFT thử nghiệm, không ghi đè thư viện đã duyệt:
  7 nhãn × 4 khung câu × 4 ticker = 112 câu. Mỗi nhãn có đủ cùng bốn ticker,
  nhằm giảm việc công ty chỉ xuất hiện nổi bật ở một nhãn. Không thêm đáp án test.
- Cả bốn cấu hình dùng BGE-M3 cùng revision, L2, cosine-max-per-label-v1.
  Chỉ chuẩn hóa ticker ở cấu hình mask, không bỏ dấu hoặc đổi nhãn kỳ vọng.
- Development: 7 nhãn × 3 khung câu khác mẫu × 4 ticker = 84 câu; cùng một
  thao tác được đối chứng bằng bốn công ty. Dùng để tìm vấn đề, không nghiệm thu.
- Regression: 56 câu test cũ, trong đó 47 có nhãn. Đây là tập đã xem, không độc lập.
- Tám probe từ chẩn đoán được báo riêng như known failures, không trộn vào dev.
- Chuẩn bị 28 câu kiểm tra sau (7 nhãn × 2 khung × 2 ticker mới); runner không
  nạp hoặc chấm file này. Cần Huyền/Hưng review và bổ sung câu riêng trước khi
  dùng làm nghiệm thu. Cùng người soạn nên không gọi đây là test mù độc lập.

## Chỉ số và điều kiện quyết định trước khi xem điểm

- Top-1/3/5 cho nhãn, theo tổng và từng nhãn; null không tính accuracy.
- Số nhóm đối chứng mà thay công ty làm nhãn đầu thay đổi; nhóm cả bốn đúng.
- Cặp đơn/kết hợp: nhãn đầu, câu đơn bị MIXED và câu MIXED bị nhãn đơn.
- Giao nhau trước/sau trên tập cũ: sửa sai thành đúng và đúng thành sai, ID đầy đủ.
- Mô phỏng cùng ngưỡng score ≥ 0,65 và gap ≥ 0,08, payload giữ ba nhóm:
  số fallback, đúng tuyến và sai tuyến vượt ngưỡng; báo coverage và lỗi trong
  phần đã nhận. Đây không phải gọi code 04.2 hoặc E2E WebChat của Huyền.
- Ánh xạ giả định theo trao đổi: PERSON_ROLE/ENTITY_RELATION → GRAPH;
  MIXED → BOTH; NUMERIC/REPORT_CONTENT/NEWS/TREND → VECTOR.
- Chỉ đề xuất một ứng viên để review khi top-1 dev tốt hơn baseline và không
  tăng số sai tuyến đã vượt ngưỡng trên dev lẫn regression. Nếu có ca cũ bị
  hỏng phải liệt kê, không coi chỉ tiêu tổng tăng là không có regression.
- Không tự triển khai ứng viên vào production, không đổi ngưỡng, không chốt
  tiêu chí chất lượng cuối cùng thay nhóm. Không lặp lại chỉnh mẫu sau khi nhìn
  kết quả trong cùng lượt thử nghiệm này. Lưu cả kết quả cấu hình không tốt.

## Giới hạn

Che ticker chỉ dùng registry hữu hạn, chưa xử lý tên đầy đủ hoặc alias công ty.
Thư viện cân bằng thay nhiều nội dung cùng lúc nên hiệu quả của nó không được
quy riêng cho số câu, cân bằng ticker hay cách diễn đạt. Hai yếu tố masking và
thư viện được so riêng, nhưng không tách được mọi nguyên nhân trong mỗi yếu tố.
Không thêm tầng luật chọn nhãn, LLM, fallback hoặc route vào matcher chính thức.
