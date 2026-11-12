# Sprint 5 — Hồ Phạm Đăng Nhân

## Mở file nào?

| Việc cần làm | File |
|---|---|
| Gửi Hưng/Huyền review, xem phần đã làm và còn chờ | [Bàn giao hiện tại](S5-WBS04.1-HANDOFF.md) |
| Đọc kết quả sửa mới nhất và cách kiểm chứng | [Báo cáo NEWS/MIXED](S5-WBS04.1-news-mixed-results.md) |
| Xem lịch sử công việc | [history.md](history.md) |

## Tài liệu từng task

| Task | Nội dung chính |
|---|---|
| S5-WBS03.1 | [Bảng 7 nhãn và ranh giới](S5-WBS03.1-intent-labels.md) — nhóm đã xác nhận theo thông tin Nhân cung cấp. |
| S5-WBS03.2 | [90 câu mẫu và 56 câu test](S5-WBS03.2-samples-and-tests.md) — draft3 đã qua review nội dung của Hưng. |
| S5-WBS03.3 | [Vector và phiên bản thư viện](S5-WBS03.3-vector-library.md) — có bằng chứng tái tạo; không tự coi mọi cổng review đã hoàn tất. |
| S5-WBS04.1 | [Thiết kế đối chiếu gốc](S5-WBS04.1-intent-matching.md); kết quả thử nghiệm mới nhất ở hai file đầu trang. |

## Các thư mục còn lại

- `archive/`: báo cáo thử nghiệm và bản bàn giao cũ; chỉ mở khi cần tra cứu.
- `contracts/`: [hợp đồng loại điểm](contracts/S5-WBS04.1-scorer-contract.md) và
  [ranh giới nhãn/consumer còn chờ xác nhận](contracts/S5-WBS04.1-boundary-and-consumer-DRAFT.md).
- `intent-dataset-v1/`, `intent-composition-v1/`: dữ liệu dùng cho script; không phải báo cáo cần đọc mỗi ngày.
- `reviews/`: nhận xét của reviewer đã lưu.

Các file `*-plan.md` được giữ nguyên tại đây vì script/audit còn kiểm đường dẫn
và checksum của chúng. Không cần đọc các file này khi gửi review thường ngày.
JSON/JSONL, vector và kết quả từng câu trong `outputs/` giữ nguyên.

Chưa tích hợp consumer 04.2/router/Web Chat hoặc calibration. Kết quả chạy lại
trên bộ đã xem là hồi quy, không chứng minh mọi câu mới đều đúng. Task 01.2 vẫn
tạm dừng theo yêu cầu Nhân.
