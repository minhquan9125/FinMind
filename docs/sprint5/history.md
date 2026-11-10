# Lịch sử Sprint 5 — Hồ Phạm Đăng Nhân

Nhánh: `nhan-sprint-501`. Ngày cập nhật: **10/11/2026** (UTC+7).
Các giờ dưới đây là ước lượng backlog, không phải giờ công thực tế đã ghi nhận.

## Trạng thái công việc

| Mã task | Tên công việc | Giờ dự kiến | Trạng thái |
|---|---|---:|---|
| S5-WBS03.1 | Chốt nhãn ý định và ranh giới giữa các nhãn | 2 | Đã soạn; Nhân xác nhận nhóm đã duyệt bảng nhãn. Tên người xác nhận do Nhân bổ sung. |
| S5-WBS03.2 | Soạn cụm từ mẫu và bộ câu kiểm thử riêng | 4 | Draft3 đã qua review nội dung của Hưng, đủ điều kiện làm 03.3. |
| S5-WBS03.3 | Vector hóa và lưu phiên bản thư viện | 2 | Đã tạo vector thật và tự kiểm tra; đã chuẩn bị gói gửi review, chưa có xác nhận review 03.3. |
| S5-WBS04.1 | Đối chiếu vector câu hỏi với thư viện | 3 | Chưa triển khai. |

Tổng phạm vi Nhân đã nhận: **11 giờ dự kiến**.

## 10/11/2026 — Chuẩn bị nhánh

- Hoàn tất merge `backup-demo` vào nhánh hiện tại; lấy toàn bộ `adapters.py`
  từ nguồn merge `f9f1864` theo yêu cầu Nhân. Commit: `fefa143c`.
- Sau giải quyết xung đột, kiểm tra liên quan đạt 1.096 ca, còn 24 ca thất bại
  với mock Retriever thiếu `load_local_cache`. Chưa xử lý các ca này trong nhóm
  task định nghĩa nhãn/thư viện vector. Không coi các kiểm tra Sprint 5 bên dưới
  là bằng chứng toàn bộ ứng dụng đã hết lỗi.

## 10/11/2026 — S5-WBS03.1

- Đối chiếu code sau merge, tách ý định khỏi nguồn, phạm vi và route.
- Soạn **7 nhãn, 14 quy tắc, 20 cặp ví dụ dễ nhầm**; bổ sung component_intents
  cho đủ năm ví dụ MIXED trong bảng ranh giới theo góp ý leader.
- Ghi nhận các chức năng hiện có chưa thuộc bảy nhãn bản đầu, không tự đổi
  classifier/router hoặc gán mọi câu ngoài phạm vi vào MIXED.
- Leader đánh giá tài liệu đủ để bắt đầu soạn 03.2. Sau đó Nhân xác nhận nhóm
  đã duyệt bảng nhãn; cập nhật metadata theo thông tin này, không tự đặt tên người duyệt.
- Commit chính: `2c614b73`, `d36295d2`.
- Bàn giao: [tài liệu nhãn](S5-WBS03.1-intent-labels.md), [JSON nhãn](intent-labels.v1.json).

## 10/11/2026 — S5-WBS03.2

- Bản đầu có 84 câu mẫu và 54 câu test. Qua tự review, bổ sung hai nhóm MIXED
  để thư viện có 90 câu; cố định LF và checksum để chuyển máy không lệch dữ liệu.
- Tiếp thu cả ba góp ý của Hưng: viết lại tình huống/cách hỏi của T037–T042,
  thêm T055/T056 cùng sự kiện bổ nhiệm TGĐ để phân biệt PERSON_ROLE/NEWS,
  sửa viết tắt L084/T042 và cách hỏi sở hữu T025.
- Kết quả draft3: **90 câu mẫu từ 30 câu gốc, 56 câu test**, đủ bảy nhãn và
  ba dạng có dấu/không dấu/viết tắt. Toàn bộ 24 câu MIXED có nhãn thành phần.
- Không trùng câu sau chuẩn hóa hoặc trùng family giữa hai bộ; điều này không
  chứng minh độc lập ngữ nghĩa hoàn toàn. Bộ do cùng tác giả soạn, chưa phải đánh giá mù.
- **Hưng đã xác nhận draft3 đạt review nội dung**, theo phản hồi Nhân chuyển lại.
- Có validator, 14 bài test dữ liệu và hướng dẫn; đã chạy đạt từ ZIP giải nén mới.
- Commit chính: `ba6459dd`, `d4cf4d00`, `7aa473c6`, `bd747663`, `c7c57962`, `d36295d2`.
- Bàn giao: [bảng review](S5-WBS03.2-samples-and-tests.md), [hướng dẫn](S5-WBS03.2-HANDOFF.md),
  [manifest](intent-dataset-v1/manifest.json), [câu mẫu](intent-dataset-v1/library.jsonl),
  [câu test](intent-dataset-v1/test.jsonl).

## 10/11/2026 — S5-WBS03.3

- Dùng EmbeddingService hiện có, **BAAI/bge-m3** revision
  `5617a9f61b028005a4858fdac845db406aefb181`, chạy offline từ cache, CPU, batch size 8.
- Tạo đủ **90 × 1024 vector**, float32, chuẩn hóa L2. Giữ nguyên văn bản câu mẫu;
  **không vector hóa 56 câu test**.
- Lưu version `s5-intent-library-v1`, snapshot dữ liệu/nhãn, model/revision,
  phiên bản môi trường, thứ tự ID và checksum. Đọc lại đủ hàng, đúng dtype/số chiều,
  norm gần 1, không NaN/Inf.
- Nạp lại model thật ở tiến trình khác, tạo lại ba câu đại diện: sai lệch tối đa
  `7.8231e-8`, đạt dung sai `1e-5`. Chưa đo độ chính xác phân loại.
- Tự review phát hiện và sửa việc đọc lại schema/manifest sau embedding: chụp
  toàn bộ đầu vào trước model call để không trộn phiên bản nếu nguồn bị sửa.
  Test tái hiện đã thất bại trước sửa và đạt sau sửa.
- Tổng **28 bài test đạt**: 14 dữ liệu, 14 artifact. ZIP review đã được giải nén
  sang thư mục mới và chạy lại kiểm tra đọc artifact cùng 28 test, đều đạt.
- Commit chính: `ff295719`, `eb5397e5`.
- Bàn giao: [báo cáo](S5-WBS03.3-vector-library.md), [hướng dẫn review](S5-WBS03.3-HANDOFF.md),
  [artifact](../../outputs/s5_wbs033_20261110/intent-library-v1),
  [bằng chứng model thật](../../outputs/s5_wbs033_20261110/verification.json),
  [kiểm tra trước review](../../outputs/s5_wbs033_20261110/pre-review-summary.json).

## Phần tiếp theo

- Gửi gói 03.3 cho Hưng/leader review; hiện chưa ghi nhận kết quả review 03.3.
- Triển khai 04.1: tạo vector câu hỏi bằng cùng model/revision, đối chiếu thư viện,
  trả các nhóm gần nhất và điểm tương đồng, rồi đánh giá bằng bộ test riêng.
- Ngưỡng, chọn route, fallback và tích hợp WebChat chưa nằm trong phần đã triển khai.
