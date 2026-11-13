# Tối ưu ý định — danh sách đề xuất 12/11/2026

## Chốt lại phạm vi — chỉ task Nhân

- [x] Chạy lại 192 test dữ liệu/vector/đối chiếu của Nhân: không lỗi hoặc skip.
- [x] Audit 345 quyết định: không refit, không hồi quy hoặc thay điểm gốc.
- [x] Kiểm tra dữ liệu 90 mẫu/56 test và artifact 90 × 1024, checksum đạt.
- [x] Sửa báo cáo hiện tại và script sinh báo cáo để loại phần nghiệm thu consumer.
- [ ] Hưng review phần Nhân; chưa chốt Done hoặc kết luận mọi câu đều đúng.

Các mục consumer/ngưỡng/fallback/router bên dưới chỉ lưu lịch sử hoặc phụ thuộc,
không phải danh sách việc Nhân sẽ tiếp tục thực hiện.

Các bước 1–3 và checkpoint raw scorer được lưu dưới đây. Cập nhật cuối file:
V3 đã qua kiểm soát hồi quy và chạy bộ mới; calibration/consumer vẫn còn mở.
Xem [kế hoạch](plan.md).

## 1. Chốt hợp đồng đầu ra — nhỏ, 2–3 file

- [x] Kiểm source local: chưa có consumer 04.2 mới của Huyền; đã ghi rõ giới hạn.
- [x] Định nghĩa kết quả baseline/classifier/centroid riêng, không ghép nhãn mới với điểm cũ.
- [x] Viết test contract từ chối loại điểm không hỗ trợ; mutation bị test phát hiện.

Điều kiện đạt: baseline không đổi; loại điểm mới không tự đi qua ngưỡng cũ.
Kiểm chứng: test contract và đọc payload mẫu. Phụ thuộc: không.
File dự kiến: tài liệu contract, test mới và adapter thử nghiệm nếu cần.

## 2. Đóng băng dữ liệu và cách đánh giá — nhỏ, 2–3 file

- [x] Lập manifest dữ liệu/vector nguồn; không đưa test vào training.
- [x] Tạo group split theo 58 family, 4 fold, kiểm không giao nhau và đủ nhãn từng fold.
- [x] Đóng băng cấu hình, cách chọn và tiêu chí không hồi quy trước huấn luyện.

Điều kiện đạt: checksum và kiểm tra split qua; tất cả biến thể một family cùng fold.
Kiểm chứng: test leakage/split, kiểm tra manifest. Phụ thuộc: 1.
File dự kiến: manifest/split, script chuẩn bị và test split.

## 3. Thử hai cách chấm điểm — vừa, tối đa 5 file

- [x] Fit classifier tuyến tính từ embedding cố định, cân trọng số family; C=1 từ OOF.
- [x] Tính centroid theo family làm đối chứng; giữ max-cosine làm baseline.
- [x] Lưu thứ hạng, score_type, metrics, các ca sửa đúng/đang đúng thành sai.

Điều kiện đạt: tái tạo được model/ranking; không chỉnh nhãn hoặc áp ngưỡng cosine cho probability.
Kiểm chứng: unit test và tính lại thứ hạng từ artifact đã lưu. Phụ thuộc: 2.
File dự kiến: module thử nghiệm, runner, audit và tests.

## Điểm dừng sau 3

- [x] Báo đầy đủ mọi cấu hình; không ứng viên nào qua điều kiện không hồi quy.
- [x] Giữ baseline; linear còn T038, centroid còn T014/T034/T038; không hạ tiêu chí.

## 4. Kiểm tra mới, calibration và bàn giao — vừa, tách thành phần nếu quá 5 file

Chưa thực hiện theo điểm dừng đã đặt trước; không gọi 28 câu cũ là test mới.

- [ ] Đóng băng ứng viên trước khi đánh giá mới; không dùng lại 28 câu như test chưa xem.
- [ ] Tách tập calibration khỏi training/final check và báo coverage–sai tuyến.
- [ ] Chốt cách dùng score với 04.2 trước khi đề nghị tích hợp; chưa sửa router trong thử nghiệm.

Điều kiện đạt: có bằng chứng chất lượng và hợp đồng điểm rõ; chưa tuyên bố E2E/90% khi chưa chạy thật.
Kiểm chứng: test riêng, trace khi có bản tích hợp và báo cáo hồi quy. Phụ thuộc: 3 và điểm dừng.
File dự kiến: dữ liệu kiểm tra, báo cáo và script calibration; runtime thay đổi là bước riêng.

## Bổ sung sau kiểm tra đơn/kết hợp — 12/11/2026

- [x] Giữ kết quả V1 không đạt và kiểm soát không hồi quy cho V2/V3.
- [x] T038 được sửa; 32/32 kiểm soát đạt, hồi quy 41/47; score thô giữ nguyên.
- [x] Đóng băng V3 và đo bộ mới 28 câu: 25/28, không chỉnh quy tắc sau kết quả.
- [x] Lưu lượt lỗi mã hóa và guard UTF-8; audit đối chiếu cùng head/rules.
- [x] Báo cáo từng câu, test và gói có thể chạy lại, ghi giới hạn đầu ra advisory.
- [ ] Calibration và hợp đồng consumer 04.2; chưa có source mới của Huyền tại local.
- [ ] Kiểm thử router tích hợp, fallback/coverage và E2E khi có bản tích hợp.

Chỉ phần đóng băng/kiểm tra mới của bước 4 đã thực hiện cho V3. Các checkbox
calibration/consumer ở trên vẫn mở; không đổi trạng thái thành Done toàn luồng.

## Sau review Hưng — 12/11/2026

- [x] Tái hiện lỗi AI/ai và mẫu hỏi chức vụ bằng test trên V3: 10 fail, 6 pass.
- [x] Sửa ở module kế tiếp, giữ nguyên source/artifact V3 đã kiểm chứng; 18 test mới qua.
- [x] Chạy hồi quy 278 câu: không đổi nhãn; 15 probe với model thật đạt 14, giữ ca sai.
- [x] Đề xuất ranh giới nhãn riêng ở DRAFT để nhóm chốt, giữ schema APPROVED không đổi.
- [x] Ghi yêu cầu consumer bắt buộc ranking_policy/score_type và bốn điểm contract.
- [x] Lưu bằng chứng, audit 293 quyết định, 119 test; cập nhật history/hướng dẫn review.
- [ ] Nhóm xác nhận ranh giới kế hoạch lợi nhuận; chưa cập nhật schema chính thức.
- [ ] Huyền nhận bản sửa/patch vòng 2 từ nhánh Nhân và kiểm trên nhánh của mình; chưa tích hợp router.

## Guard số liệu sau REVIEW-03

- [x] Test trên V4: 10 fail, 12 pass, tái hiện lỗi và các ranh giới cần giữ.
- [x] Thêm guard NUMERIC theo mục tiêu, giữ nguyên raw score và confidence=null.
- [x] Replay 293 câu: sửa REVIEW-03 và FINAL-NUMERIC-2-DPM, không phát sinh đúng→sai.
- [x] Bộ 15 review đã xem đạt 15; 20 kiểm tra bổ sung bằng model thật đạt 17, giữ ba lỗi.
- [x] Audit 313 quyết định, toàn bộ 144 unit test qua, báo cáo và history; chưa nối router.

## Sửa NEWS/MIXED sau NV-13/NV-19/NV-20

- [x] Viết test tái hiện trên bản cũ: 9 fail, 9 pass.
- [x] Thêm mục tiêu thao tác bài tin và tách vế Đọc độc lập; 18 test mới qua.
- [x] Replay 313 câu: sửa NV-13/NV-19/NV-20 và FINAL-MIXED-2-DPM/VRE; không đúng→sai.
- [x] Audit 313 quyết định, raw ranking/checksum bất biến; 162 unit test ý định qua.
- [x] Cập nhật báo cáo/history; bộ 20 nay đã xem đạt 20/20 hồi quy, chưa nối runtime.

## Review vòng 2 — chính tả, cách hỏi và consumer

- [x] Tái hiện bằng test đọc/độc, lương/lượng và các cách hỏi được review.
- [x] Đọc consumer Huyền tại 8e854d47, tái hiện thiếu metadata bị SEARCH.
- [x] Hoàn thiện guard có dấu/ngữ cảnh, role/news/giải thích; 276 test qua.
- [x] Replay 313 hàng không đúng→sai; 32 probe: 27/27 gold, 5/5 không ép nhãn.
- [x] Audit độc lập 345 quyết định; test consumer, bàn giao và luồng giá hiện có.
- [x] Cập nhật cùng trang bàn giao, lưu patch Huyền và lỗi/giới hạn còn lại.

Câu độc lập vẫn có đề xuất thô sai/chưa rõ mục tiêu, không tính là phân loại
thành công. Handoff dừng NEED_VALIDATION; các payload classifier chưa được nhận
tự động. Huyền/nhóm cần review contract, nhận patch, chốt ranh giới và tích hợp
07.2/router trước khi nghiệm thu; không đánh dấu Done toàn luồng.
