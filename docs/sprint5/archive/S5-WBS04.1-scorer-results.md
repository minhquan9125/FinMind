# Tối ưu cách chấm ý định — 12/11/2026

**Có cải thiện rõ nhưng chưa thay baseline:** linear còn 1 ca cũ đúng→sai (T038), centroid còn 3 ca. Cả hai chưa đạt ràng buộc không hồi quy đã chốt.

## Phương pháp và cách chọn

- Huấn luyện/thống kê chỉ trên 202 hàng LIBRARY (90 mẫu gốc + 112 mẫu DRAFT), 58 family, cùng embedding BGE-M3 đã lưu. Không fit trên test/dev hoặc 28 câu đã xem.
- Chia 4 fold theo family và nhãn; mọi biến thể cùng family ở cùng fold. Cân trọng số để các nhãn có tổng bằng nhau, các family trong một nhãn có tổng bằng nhau.
- Linear: Logistic Regression L2, lbfgs; C trong {0,1; 1; 10}, chọn bằng macro-F1 OOF rồi accuracy rồi C nhỏ hơn. C được chọn = **1.0**, macro-F1 OOF = **0.7073**. Chọn trước khi chấm các tập đánh giá.
- Centroid: chuẩn hóa trung bình từng family, rồi trung bình các family của nhãn và chuẩn hóa lại; score là cosine query với đại diện nhãn.
- So với baseline 90 mẫu đã duyệt. Hai phương pháp mới dùng cùng 202 hàng nên so sánh hai phương pháp mới có cùng dữ liệu; so với baseline đồng thời thay dữ liệu và cách chấm, không quy toàn bộ cải thiện cho thuật toán. Vòng additive trước đã đo max-cosine trên chính 202 hàng: dev 40/84, regression 27/47.

## Kết quả

| Tập | Cấu hình | Top-1 | Top-3 | Top-5 | Macro-F1 |
|---|---|---:|---:|---:|---:|
| development | original | 34/84 (40.48%) | 67/84 (79.76%) | 80/84 (95.24%) | 0.3897 |
| development | centroid | 66/84 (78.57%) | 82/84 (97.62%) | 84/84 (100.00%) | 0.7800 |
| development | linear | 66/84 (78.57%) | 84/84 (100.00%) | 84/84 (100.00%) | 0.7771 |
| regression | original | 22/47 (46.81%) | 41/47 (87.23%) | 46/47 (97.87%) | 0.4680 |
| regression | centroid | 34/47 (72.34%) | 44/47 (93.62%) | 47/47 (100.00%) | 0.7207 |
| regression | linear | 35/47 (74.47%) | 43/47 (91.49%) | 47/47 (100.00%) | 0.7019 |
| previous_check | original | 19/28 (67.86%) | 26/28 (92.86%) | 26/28 (92.86%) | 0.6581 |
| previous_check | centroid | 23/28 (82.14%) | 27/28 (96.43%) | 28/28 (100.00%) | 0.8159 |
| previous_check | linear | 24/28 (85.71%) | 28/28 (100.00%) | 28/28 (100.00%) | 0.8518 |
| known_diagnostic | original | 3/8 (37.50%) | 7/8 (87.50%) | 7/8 (87.50%) | 0.1286 |
| known_diagnostic | centroid | 6/8 (75.00%) | 6/8 (75.00%) | 8/8 (100.00%) | 0.2619 |
| known_diagnostic | linear | 6/8 (75.00%) | 8/8 (100.00%) | 8/8 (100.00%) | 0.2619 |

Development = 84 câu; regression = 47 có nhãn trong 56 câu; previous_check = 28 câu đã chấm ở lượt trước; known = 8 probe đã biết. Cả bốn đều đã xem, chỉ dùng phát triển/hồi quy, không gọi là nghiệm thu độc lập.

## Hồi quy so với baseline

| Cấu hình | Sai → đúng | Đúng → sai | ID đúng → sai |
|---|---:|---:|---|
| centroid | 15 | 3 | S5-T-014, S5-T-034, S5-T-038 |
| linear | 14 | 1 | S5-T-038 |

### Ca T038

- original: MIXED (0.5402) → PERSON_ROLE (0.5363) → REPORT_CONTENT (0.5203).
- centroid: REPORT_CONTENT (0.5623) → PERSON_ROLE (0.5533) → MIXED (0.5216).
- linear: PERSON_ROLE (0.2584) → REPORT_CONTENT (0.2444) → MIXED (0.1588).

Gold MIXED: hỏi chức danh trong BCTN và hỏi chính sách kiểm soát nội bộ. Không sửa gold sang một nhãn đơn hoặc đưa nguyên câu này vào training để xóa hồi quy.

## Hai nhóm lỗi cần xử lý trên development

| Cấu hình | Nhóm đổi nhãn theo công ty / 21 | Nhóm cả 4 công ty đúng / 21 | Đơn → MIXED | MIXED → đơn | Sai tuyến argmax, chưa xét ngưỡng / 84 |
|---|---:|---:|---:|---:|---:|
| original | 21/21 | 0/21 | 16 | 6 | 35/84 |
| centroid | 5/21 | 15/21 | 3 | 3 | 7/84 |
| linear | 6/21 | 13/21 | 1 | 6 | 9/84 |

Cột cuối không phải số tuyến sai đã chạy trong hệ thống; chưa áp policy hoặc ngưỡng của Huyền lên score mới. Không dùng cột này thay cho phép đo accepted/fallback.

## Theo nhãn — top-1

| Tập / nhãn | Baseline | Centroid | Linear |
|---|---:|---:|---:|
| development / ENTITY_RELATION | 2/12 | 12/12 | 12/12 |
| development / MIXED | 6/12 | 9/12 | 6/12 |
| development / NEWS | 4/12 | 8/12 | 10/12 |
| development / NUMERIC | 5/12 | 12/12 | 11/12 |
| development / PERSON_ROLE | 8/12 | 12/12 | 12/12 |
| development / REPORT_CONTENT | 2/12 | 6/12 | 6/12 |
| development / TREND | 7/12 | 7/12 | 9/12 |
| regression / ENTITY_RELATION | 3/6 | 5/6 | 5/6 |
| regression / MIXED | 1/6 | 2/6 | 0/6 |
| regression / NEWS | 4/8 | 5/8 | 8/8 |
| regression / NUMERIC | 5/7 | 7/7 | 7/7 |
| regression / PERSON_ROLE | 3/8 | 4/8 | 4/8 |
| regression / REPORT_CONTENT | 1/6 | 6/6 | 5/6 |
| regression / TREND | 5/6 | 5/6 | 6/6 |

## Ảnh hưởng tới Huyền và điểm dừng

- Kết quả linear là CLASSIFIER_PROBABILITY_UNCALIBRATED, centroid là cosine đại diện nhãn, đều có policy/version riêng. Không dùng ngưỡng 0,65/0,08 của max-cosine cho hai loại điểm mới; không ghép nhãn mới với điểm cũ.
- Baseline và payload top-3 không đổi. Guard thử nghiệm từ chối loại điểm không hỗ trợ trước khi áp ngưỡng; chưa xác nhận guard trong source 04.2 của Huyền.
- Các sai tuyến không ngưỡng được lưu như phép đo argmax riêng. Không báo accepted/fallback cho ứng viên từ ngưỡng cũ, không tuyên bố đã chạy E2E hoặc đạt 90%.
- **Không ứng viên nào qua điều kiện không hồi quy. Dừng ở checkpoint sau bước 3.** Chưa chấm bộ mới hoặc calibration; không hạ tiêu chí để chọn model. Đây là dừng đề nghị thay baseline, không phải lỗi kỹ thuật ngăn fit hay tính điểm.
- Phân biệt rõ: số câu đầu bảng tăng là bằng chứng có hướng cải thiện; chưa chứng minh vận hành đủ tốt hoặc độ tin cậy của probability đã được hiệu chỉnh.

## Tái tạo và giới hạn

- Kiểm chứng không fit lại: `python backend/scripts/audit_s5_intent_scorer.py` (cần NumPy). Tính lại grouped OOF selection, centroid, softmax và 528 thứ hạng.
- Tạo lại báo cáo: `python backend/scripts/report_s5_intent_scorer.py`.
- Lượt fit đầu lỗi ghi báo cáo do probe thiếu family_id; đã thêm test tái hiện và sửa. Lượt sau đã có đủ summary nhưng lỗi đường dẫn tương đối khi ghi pointer cuối. Đã sửa và khôi phục pointer sau kiểm tra; không fit lần ba. Tham số và CV của hai lượt giống nhau từng phần tử. Xem recovery-note.json, không ẩn các lượt lỗi.
- Artifact giữ coefficients/intercepts/centroids dạng NPZ, không dùng pickle. Dữ liệu thư viện mới vẫn là DRAFT; dữ liệu ít, cùng tác giả và family_id không bảo đảm không có gần nghĩa giữa các family. OOF không thay cho test mới.
- Phạm vi mã: module/runner thử nghiệm; không thay code matcher/router/WebChat chính thức.
