# Nhận diện yêu cầu kết hợp — kết quả 12/11/2026

**Qua điều kiện đã đặt trước: False.** Đây là thử nghiệm ngoài runtime, không phải kết quả E2E hoặc quyết định đã hiệu chỉnh ngưỡng.

## Thiết kế

- Giữ nguyên hệ số/intercept classifier C=1. Không fit lại hoặc sửa gold label.
- Tách yêu cầu có dấu hỏi/dấu nối, bỏ phần chỉ xin dẫn chứng hoặc giải nghĩa viết tắt khỏi việc đếm mục tiêu. Câu trích nội dung báo cáo độc lập vẫn là yêu cầu.
- Một yêu cầu còn lại sau bỏ hỗ trợ: dùng classifier cho phần đó. Hai yêu cầu có nhãn đầu khác nhau: hỗ trợ MIXED = max(min(p_top_a,p_top_b)) trên cặp khác nhãn, không gồm MIXED. Chỉ tăng score MIXED nếu hỗ trợ lớn hơn score MIXED toàn câu.
- Score COMPOSITION_SUPPORT_UNCALIBRATED không phải cosine hoặc probability đã hiệu chỉnh. Giữ raw score và mọi phần yêu cầu trong trace. Không áp 0,65/0,08.
- 32 controls mới đóng băng trước inference; cùng tác giả, không phải test mù. Các tập 84/47/8/28 đều đã xem. Không đưa controls hoặc test vào training.

## Kết quả

| Tập | Phương pháp | Top-1 | Top-3 | Top-5 | Macro-F1 |
|---|---|---:|---:|---:|---:|
| development | original | 34/84 (40.48%) | 67/84 (79.76%) | 80/84 (95.24%) | 0.3897 |
| development | linear | 66/84 (78.57%) | 84/84 (100.00%) | 84/84 (100.00%) | 0.7771 |
| development | composition | 68/84 (80.95%) | 84/84 (100.00%) | 84/84 (100.00%) | 0.8044 |
| regression | original | 22/47 (46.81%) | 41/47 (87.23%) | 46/47 (97.87%) | 0.4680 |
| regression | linear | 35/47 (74.47%) | 43/47 (91.49%) | 47/47 (100.00%) | 0.7019 |
| regression | composition | 37/47 (78.72%) | 45/47 (95.74%) | 47/47 (100.00%) | 0.7350 |
| known_diagnostic | original | 3/8 (37.50%) | 7/8 (87.50%) | 7/8 (87.50%) | 0.1286 |
| known_diagnostic | linear | 6/8 (75.00%) | 8/8 (100.00%) | 8/8 (100.00%) | 0.2619 |
| known_diagnostic | composition | 8/8 (100.00%) | 8/8 (100.00%) | 8/8 (100.00%) | 0.4286 |
| previous_check | original | 19/28 (67.86%) | 26/28 (92.86%) | 26/28 (92.86%) | 0.6581 |
| previous_check | linear | 24/28 (85.71%) | 28/28 (100.00%) | 28/28 (100.00%) | 0.8518 |
| previous_check | composition | 24/28 (85.71%) | 28/28 (100.00%) | 28/28 (100.00%) | 0.8518 |
| controls | original | 21/32 (65.62%) | 28/32 (87.50%) | 32/32 (100.00%) | 0.5675 |
| controls | linear | 20/32 (62.50%) | 31/32 (96.88%) | 32/32 (100.00%) | 0.5343 |
| controls | composition | 26/32 (81.25%) | 32/32 (100.00%) | 32/32 (100.00%) | 0.6598 |

## T038 và bằng chứng thành phần

- original: MIXED (0.5402) → PERSON_ROLE (0.5363) → REPORT_CONTENT (0.5203).
- linear: PERSON_ROLE (0.2584) → REPORT_CONTENT (0.2444) → MIXED (0.1588).
- composition: PERSON_ROLE (0.2584) → MIXED (0.2513) → REPORT_CONTENT (0.2444).

- Vế: BCTN REE 2022 ghi bà Mai đảm nhiệm chức danh nào → PERSON_ROLE (0.3358).
- Vế: Báo cáo mô tả chính sách kiểm soát nội bộ ra sao → REPORT_CONTENT (0.2513).

Các số ở ba phương pháp có nghĩa khác nhau; không so độ tin cậy trực tiếp giữa cosine, classifier probability và composition support.

## Câu thay đổi so với classifier

| Tập | Sai → đúng | Đúng → sai | ID đúng → sai |
|---|---:|---:|---|
| development | 2 | 0 | — |
| regression | 3 | 1 | S5-T-003 |
| known_diagnostic | 2 | 0 | — |
| previous_check | 0 | 0 | — |
| controls | 6 | 0 | — |

So baseline cũ trên 47 câu: các ca đúng→sai còn lại: S5-T-003, S5-T-038.

## Bộ đối chứng: kiểm tra cả câu đơn và dẫn chứng

| ID | Gold | Linear | Composition |
|---|---|---|---|
| CONTROL-ROLE-VCB | PERSON_ROLE | PERSON_ROLE | PERSON_ROLE |
| CONTROL-ROLE-MBB | PERSON_ROLE | PERSON_ROLE | PERSON_ROLE |
| CONTROL-ROLE-FPT | PERSON_ROLE | PERSON_ROLE | PERSON_ROLE |
| CONTROL-ROLE-VNM | PERSON_ROLE | PERSON_ROLE | PERSON_ROLE |
| CONTROL-ROLE-SAB | PERSON_ROLE | PERSON_ROLE | PERSON_ROLE |
| CONTROL-ROLE-HDB | PERSON_ROLE | PERSON_ROLE | PERSON_ROLE |
| CONTROL-REPORT-VCB | REPORT_CONTENT | TREND | TREND |
| CONTROL-REPORT-MBB | REPORT_CONTENT | TREND | TREND |
| CONTROL-REPORT-FPT | REPORT_CONTENT | TREND | TREND |
| CONTROL-REPORT-VNM | REPORT_CONTENT | REPORT_CONTENT | REPORT_CONTENT |
| CONTROL-REPORT-SAB | REPORT_CONTENT | TREND | TREND |
| CONTROL-REPORT-HDB | REPORT_CONTENT | TREND | TREND |
| CONTROL-COMBINED-VCB | MIXED | PERSON_ROLE | MIXED |
| CONTROL-COMBINED-MBB | MIXED | PERSON_ROLE | MIXED |
| CONTROL-COMBINED-FPT | MIXED | PERSON_ROLE | MIXED |
| CONTROL-COMBINED-VNM | MIXED | PERSON_ROLE | PERSON_ROLE |
| CONTROL-COMBINED-SAB | MIXED | PERSON_ROLE | MIXED |
| CONTROL-COMBINED-HDB | MIXED | PERSON_ROLE | MIXED |
| CONTROL-EVIDENCE-VCB | PERSON_ROLE | PERSON_ROLE | PERSON_ROLE |
| CONTROL-EVIDENCE-MBB | PERSON_ROLE | PERSON_ROLE | PERSON_ROLE |
| CONTROL-EVIDENCE-FPT | PERSON_ROLE | PERSON_ROLE | PERSON_ROLE |
| CONTROL-EVIDENCE-VNM | PERSON_ROLE | PERSON_ROLE | PERSON_ROLE |
| CONTROL-EVIDENCE-SAB | PERSON_ROLE | PERSON_ROLE | PERSON_ROLE |
| CONTROL-EVIDENCE-HDB | PERSON_ROLE | PERSON_ROLE | PERSON_ROLE |
| EDGE-01 | NUMERIC | NUMERIC | NUMERIC |
| EDGE-02 | PERSON_ROLE | PERSON_ROLE | PERSON_ROLE |
| EDGE-03 | REPORT_CONTENT | REPORT_CONTENT | REPORT_CONTENT |
| EDGE-04 | NEWS | NEWS | NEWS |
| EDGE-05 | NUMERIC | NUMERIC | NUMERIC |
| EDGE-06 | MIXED | MIXED | MIXED |
| EDGE-07 | TREND | TREND | TREND |
| EDGE-08 | PERSON_ROLE | MIXED | PERSON_ROLE |

## Giới hạn và bước tiếp

- Không dùng từ “và” hoặc hai công ty làm điều kiện đủ để gán MIXED. Tuy vậy heuristic tách câu và classifier từng vế vẫn có thể sai; không khẳng định đã hiểu mọi câu nhiều ý.
- Việc bỏ giải nghĩa viết tắt khỏi đoạn được chấm có thể mất ngữ cảnh hữu ích; query gốc vẫn lưu, cần đọc các ca này trong controls và regression.
- Giữ matcher/vector/taxonomy, ngưỡng và consumer Huyền không đổi. Chưa có source consumer 04.2 mới tại local, chưa kiểm chứng chạy WebChat.
- Nếu điều kiện thất bại, không áp bản này hoặc đổi đáp án/điểm để xóa lỗi; nếu điều kiện đạt, vẫn cần kiểm tra mới, calibration riêng và hợp đồng loại điểm trước khi đề nghị tích hợp. Không tuyên bố router đạt 90% từ unit test.

## Chạy lại bằng chứng

`python backend/scripts/audit_s5_intent_composition.py` tính lại từ vector đã lưu, không cần nạp BGE-M3. `python backend/scripts/report_s5_intent_composition.py` tạo lại báo cáo. Source: outputs/s5_intent_composition_20261112.
