# Bàn giao hiện tại S5-WBS04.1 — 12/11/2026

Phụ trách: Hồ Phạm Đăng Nhân. Nhánh: `nhan-sprint-501`.
Đây là bản chờ review, chưa xác nhận hoàn thành tích hợp router/Web Chat.

## Gửi Hưng review

Đọc [báo cáo sửa NEWS/MIXED mới nhất](S5-WBS04.1-news-mixed-results.md).
Nhờ kiểm tra ba điểm:

1. Phân biệt tìm/tóm tắt bài tin với lấy số liệu từ bài đã chỉ định.
2. Tách yêu cầu mở đầu bằng Đọc và ghép các mục tiêu độc lập thành MIXED;
   danh sách chỉ tiêu hoặc nhiều yêu cầu cùng nhãn không tự thành MIXED.
3. Chạy lại audit để kiểm điểm gốc, vector/head và các ca đang đúng không bị sai.

## Đã kiểm chứng

- NV-13/NV-19/NV-20 đã đúng; bộ 20 câu **đã xem** đạt 20/20 khi chạy hồi quy.
- 313 hàng hồi quy: sửa đúng thêm 5 ca, không phát sinh đúng→sai so với V5.
  Các tập cũ vẫn còn lỗi, liệt kê đầy đủ trong báo cáo; không gọi đây là test mù.
- 162/162 unit test ý định Sprint 5 qua; audit tái tạo 313 quyết định đạt.
- Giữ BGE-M3/revision, classifier C=1, training, gold và raw ranking.
  Lớp quyết định trả evidence riêng với `confidence=null`.

Kết quả từng câu: `outputs/s5_intent_news_20261112/run01/`.
Module: `backend/src/retrieval_orchestration/intent_news_requests.py`.
Test: `backend/tests/test_s5_intent_news_requests.py`.

Từ thư mục gốc, kiểm lại artifact đã lưu bằng:

```powershell
$env:PYTHONUTF8='1'
$env:OPENBLAS_NUM_THREADS='4'
.\backend\.venv\Scripts\python.exe backend/scripts/audit_s5_intent_news.py
```

## Còn chờ nhóm

- Hưng review logic và cách tái tạo; chưa tự ghi là đã được duyệt.
- Huyền đối chiếu [hợp đồng loại điểm](contracts/S5-WBS04.1-scorer-contract.md)
  và [bốn điểm consumer/ranh giới nhãn DRAFT](contracts/S5-WBS04.1-boundary-and-consumer-DRAFT.md).
- Chưa calibration hoặc tích hợp 04.2/router/Web Chat. Không áp ngưỡng cosine
  0,65/0,08 lên xác suất chưa hiệu chỉnh; không gắn điểm nhãn cũ cho nhãn mới.
  MIXED không mặc định là BOTH. Task 01.2 vẫn tạm dừng theo yêu cầu Nhân.

Tra cứu task 03.1–03.3 tại [README](README.md), các mốc ở [history](history.md).
Các kết quả và hướng dẫn cũ nằm trong `archive/`; bản bàn giao dài trước dọn ở
[đây](archive/S5-WBS04.1-HANDOFF-before-cleanup.md).
