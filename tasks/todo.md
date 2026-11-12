# Tối ưu ý định — danh sách đề xuất 12/11/2026

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
