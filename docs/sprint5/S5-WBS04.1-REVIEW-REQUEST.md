# Nhờ review S5-WBS04.1 — 12/11/2026

Mới nhất: [sửa mục tiêu bài tin và tách nhiều ý](S5-WBS04.1-news-mixed-results.md).
NV-13/NV-19/NV-20 đã đúng; bộ 20 câu đã xem đạt 20/20 khi chạy hồi quy,
313 hàng không có đúng→sai và 162 unit test đạt. Nhờ review mục tiêu NEWS,
tách vế Đọc và hợp đồng evidence; chưa xác nhận router/Web Chat hoàn thành.

Vòng trước: [guard số liệu và các lỗi còn lại](S5-WBS04.1-numeric-results.md).
Nhờ kiểm ranh giới lấy giá trị với đếm quan hệ/tin/nội dung/nhận định;
đọc cả 20 câu kiểm tra bổ sung và ba ca chưa đúng, không chỉ REVIEW-03 đã sửa.

Cập nhật sau nhận xét Hưng: [báo cáo sửa AI/ai và cách hỏi chức vụ](S5-WBS04.1-reviewfix-results.md).
Review V3 bên dưới là lịch sử; chưa xem V4 là đã được Hưng duyệt.

Nhánh: `nhan-sprint-501`. Nhân gửi phần đối chiếu ý định và các thử nghiệm cải
thiện sau chẩn đoán của Huyền. Mục tiêu lần review này là kiểm tra chất lượng
nhãn, khả năng tái tạo và hợp đồng đầu ra trước khi cân nhắc tích hợp 04.2.
Chưa đề nghị xác nhận router/Web Chat đã hoàn thành.

## Đã làm gì

1. Báo cáo top-1/top-3/top-5 trên cùng thứ hạng baseline: 22/47, 41/47, 46/47.
   Top-k là khả năng chứa nhãn đúng, không phải accuracy quyết định tuyến.
2. Thử cân bằng/bổ sung thư viện và che ticker; lưu cả cấu hình không đạt,
   các ca sửa đúng và các ca đang đúng thành sai. Chưa thay thư viện chính.
3. Thử classifier tuyến tính và centroid trên embedding BGE-M3 cố định.
   Classifier C=1 được chọn bằng validation theo family, không fit câu test.
4. Thử tách từng yêu cầu, đối chiếu cả câu với từng phần, rồi bổ sung quy tắc
   hẹp ROLE/REPORT theo taxonomy. V1 không đạt; V2 còn lỗi kiểm soát; V3 là ứng
   viên hiện tại. Không có ngoại lệ theo mã công ty hoặc mã test.
5. Giữ nguyên bảng điểm `base_ranking`, trả nhãn đề xuất trong `resolution`
   với lý do/bằng chứng và `confidence=null`. Không gắn điểm nhãn cũ cho nhãn mới.
6. Lưu vector, manifest/checksum, từng câu, unit test và script audit. Đã giải
   nén gói bàn giao ra thư mục khác, chạy lại ba audit và 101 unit test đạt.

| Bộ đo | Cosine gốc đúng | Linear đúng | Quyết định V3 đúng |
|---|---:|---:|---:|
| Hồi quy cũ, 47 câu có nhãn | 22 | 35 | 41 |
| Kiểm soát đơn/kết hợp, 32 câu | 21 | 20 | 32 |
| Bộ mới sau đóng băng V3, 28 câu | 18 | 23 | 25 |

V3 sửa T038; không làm sai câu linear đang đúng trên các tập đã đo. Bộ mới do
cùng tác giả soạn, gồm 14 khung × hai công ty; không phải test mù độc lập.

## Cần review gì

**Hưng — logic và bằng chứng:**

- Cách phân biệt hỏi chức vụ, đọc nội dung báo cáo, câu nhiều ý và xin trích
  dẫn hỗ trợ có đúng bảng nhãn 03.1 không? T038 có được sửa bằng logic chung không?
- Tách câu/quy tắc có nhận nhầm câu một ý thành MIXED, bỏ mất ngữ cảnh hoặc
  phụ thuộc cách viết quá hẹp không? Đọc cả V1/V2 không đạt, không chỉ V3.
- Split theo family, chọn C, checksum và audit có đủ tái tạo, không lẫn test
  vào training không? Các số phát triển/hồi quy/bộ mới có được tách rõ không?

**Huyền — ranh giới với consumer 04.2:**

- Đối chiếu lỗi đổi ticker và nhầm đơn/kết hợp; kiểm cả câu bị fallback và
  câu được nhận khi có bản tích hợp. Báo cáo hiện tại chỉ đo nhãn offline.
- Review payload: `resolution` có thể khác nhãn đầu trong `base_ranking`;
  confidence chưa có. Cần thống nhất cách consumer xử lý evidence/fallback
  và cách calibration trước khi nối; chưa áp ngưỡng cosine vào điểm mới.
- MIXED không tự động đồng nghĩa BOTH; cần kiểm thành phần và policy router.

## File nên đọc theo thứ tự

1. [Kết quả V3, ba lỗi mới và giới hạn](S5-WBS04.1-objective-results.md).
2. [Payload T038](../../outputs/s5_intent_composition_20261112/objectives-v3/payload-T038.json).
3. [Logic V3](../../backend/src/retrieval_orchestration/intent_request_objectives.py),
   [đối chiếu cả câu/từng phần](../../backend/src/retrieval_orchestration/intent_request_consensus.py),
   [test V3](../../backend/tests/test_s5_intent_objectives.py).
4. [Kết quả từng câu V3](../../outputs/s5_intent_composition_20261112/objectives-v3/results.json),
   [28 câu mới](../../outputs/s5_intent_composition_20261112/final-check-v3-utf8/results.json),
   [audit V3](../../outputs/s5_intent_composition_20261112/objectives-v3/audit.json).
5. [Hợp đồng điểm](S5-WBS04.1-scorer-contract.md),
   [top-1/3/5](S5-WBS04.1-top1-top3-top5-report.md), [history](history.md).

Hướng dẫn chạy audit và toàn bộ 101 test nằm cuối báo cáo V3. Vector và kết quả
cần thiết được commit trực tiếp; clone nhánh là có dữ liệu kiểm chứng offline,
không cần ZIP cục bộ, model weights, API key, PostgreSQL hoặc Neo4j.

## Chưa hoàn tất / không đổi trong lần này

- Bộ mới còn một lỗi số liệu lợi nhuận giữ lại DPM và hai lỗi MIXED số liệu +
  tìm tin; bộ chẩn đoán cũ còn KNOWN-07/08 sai. Chưa hết ảnh hưởng của ticker.
- Chưa calibration, chưa tích hợp consumer 04.2 mới, chưa kiểm thử E2E hoặc
  chứng minh mốc 90% của 04.3. Source consumer mới của Huyền chưa có ở checkout.
- Giữ nguyên taxonomy, 90 vector thư viện chính, matcher/router runtime,
  ngưỡng 0,65/0,08 và payload top-3 hiện tại của Huyền.
- Lượt lỗi mã hóa `final-check-v3` được giữ lại và loại khỏi đo chất lượng;
  lượt hợp lệ là `final-check-v3-utf8`, cùng model/rules, có audit đối chiếu.

Nhờ ghi kết luận riêng: logic/dữ liệu đạt hay cần sửa; vấn đề còn lại; hợp đồng
consumer cần thống nhất. Review nội dung không tự đồng nghĩa đã tích hợp thành công.
