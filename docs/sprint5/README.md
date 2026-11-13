# Sprint 5 — Hồ Phạm Đăng Nhân

## Mở file nào?

Bản hiện tại ngày 13/11 là [ý định v2 — 11 nhãn, sửa luật r2](intent-v2/README.md),
theo đề xuất mới của Hưng. Các báo cáo 7 nhãn bên dưới được giữ để truy vết v1.

| Việc cần làm | File |
|---|---|
| Review bản sửa r2: 409 test, API và điều kiện còn thiếu | [Bàn giao v2](intent-v2/README.md) |
| Tra cứu bản bàn giao 7 nhãn trước đây | [Bàn giao v1](S5-WBS04.1-HANDOFF.md) |
| Tra cứu kết quả vòng 2 của v1 | [Báo cáo kiểm chứng v1](S5-WBS04.1-news-mixed-results.md) |
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

V2 có hàm phân loại dùng chung; Hưng/Huyền kiểm tra contract trước khi nối Chat.
Chưa tích hợp consumer 04.2/router/Web Chat hoặc calibration. Kết quả chạy lại
trên bộ đã xem là hồi quy, không chứng minh mọi câu mới đều đúng. Task 01.2 vẫn
tạm dừng theo yêu cầu Nhân.
