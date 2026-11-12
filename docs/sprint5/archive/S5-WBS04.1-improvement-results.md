# S5-WBS04.1 — Thử nghiệm cải thiện mẫu và ảnh hưởng ticker

Ngày: 11/11/2026. Trạng thái: **DRAFT, chưa thay bản đã review hoặc đưa vào runtime.**

## Thiết kế trước lượt đo

Theo `S5-WBS04.1-improvement-plan.md`: bốn cấu hình, cùng BGE-M3/revision và cosine-max-per-label-v1; không thay ngưỡng 0,65/0,08 hoặc payload top-3. Chấm top-1/3/5 bằng đủ bảy nhóm được lưu, không tăng payload production.

- original: thư viện 90 dòng đã duyệt, văn bản nguyên gốc.
- original_masked: thư viện gốc nhưng che ticker trong cả mẫu và query.
- balanced: thư viện mới 112 dòng (7 nhãn × 4 khung × 4 công ty), không che ticker.
- balanced_masked: thư viện mới và che ticker cả hai phía.

Thư viện mới là ứng viên DRAFT. 84 câu development thuộc các khung riêng; 56 câu regression cũ đã xem, trong đó 47 có nhãn; 8 known probes được tính riêng. 28 câu later-check chưa được runner đọc/chấm và cần nhóm review. Cùng tác giả soạn các phần nên không coi test là mù/độc lập.

## Development — 84 câu

| Cấu hình | Top-1 | Top-3 | Top-5 | Fallback | Nhận đúng tuyến | Nhận sai tuyến |
|---|---:|---:|---:|---:|---:|---:|
| original | 34/84 (40.48%) | 67/84 (79.76%) | 80/84 (95.24%) | 69 | 8 | 7 |
| original_masked | 56/84 (66.67%) | 68/84 (80.95%) | 80/84 (95.24%) | 72 | 8 | 4 |
| balanced | 40/84 (47.62%) | 79/84 (94.05%) | 83/84 (98.81%) | 80 | 4 | 0 |
| balanced_masked | 44/84 (52.38%) | 84/84 (100.00%) | 84/84 (100.00%) | 76 | 8 | 0 |

Đúng/sai tuyến ở đây là **mô phỏng policy trên các câu có nhãn**, không phải E2E WebChat hay xác nhận code 04.2 đã chạy. Fallback không bị tính là đã chuyển sai tuyến. Cosine không phải xác suất.

## Regression cũ — 47 câu có nhãn

| Cấu hình | Top-1 | Top-3 | Top-5 | Fallback | Nhận đúng tuyến | Nhận sai tuyến |
|---|---:|---:|---:|---:|---:|---:|
| original | 22/47 (46.81%) | 41/47 (87.23%) | 46/47 (97.87%) | 45 | 2 | 0 |
| original_masked | 24/47 (51.06%) | 43/47 (91.49%) | 47/47 (100.00%) | 40 | 5 | 2 |
| balanced | 26/47 (55.32%) | 41/47 (87.23%) | 46/47 (97.87%) | 42 | 5 | 0 |
| balanced_masked | 27/47 (57.45%) | 42/47 (89.36%) | 46/47 (97.87%) | 41 | 5 | 1 |

Đúng/sai tuyến ở đây là **mô phỏng policy trên các câu có nhãn**, không phải E2E WebChat hay xác nhận code 04.2 đã chạy. Fallback không bị tính là đã chuyển sai tuyến. Cosine không phải xác suất.

## Known probes — 8 câu đã biết lỗi

| Cấu hình | Top-1 | Top-3 | Top-5 | Fallback | Nhận đúng tuyến | Nhận sai tuyến |
|---|---:|---:|---:|---:|---:|---:|
| original | 3/8 (37.50%) | 7/8 (87.50%) | 7/8 (87.50%) | 3 | 2 | 3 |
| original_masked | 6/8 (75.00%) | 8/8 (100.00%) | 8/8 (100.00%) | 7 | 1 | 0 |
| balanced | 8/8 (100.00%) | 8/8 (100.00%) | 8/8 (100.00%) | 2 | 6 | 0 |
| balanced_masked | 6/8 (75.00%) | 8/8 (100.00%) | 8/8 (100.00%) | 2 | 6 | 0 |

Đúng/sai tuyến ở đây là **mô phỏng policy trên các câu có nhãn**, không phải E2E WebChat hay xác nhận code 04.2 đã chạy. Fallback không bị tính là đã chuyển sai tuyến. Cosine không phải xác suất.

## Đổi công ty và ranh giới đơn/kết hợp trên development

| Cấu hình | Nhóm đổi nhãn đầu khi đổi công ty / 21 | Nhóm cả 4 công ty đúng / 21 | Câu đơn → MIXED | MIXED → câu đơn |
|---|---:|---:|---:|---:|
| original | 21/21 | 0/21 | 16 | 6 |
| original_masked | 0/21 | 14/21 | 16 | 4 |
| balanced | 2/21 | 9/21 | 8 | 4 |
| balanced_masked | 0/21 | 11/21 | 8 | 4 |

Che toàn bộ ticker tạo đầu vào giống nhau trong một khung nên giảm biến động nhãn theo công ty là hệ quả trực tiếp của phép biến đổi; cần đọc cùng tỷ lệ đúng, không dùng riêng chỉ số bất biến này để tuyên bố model tốt.

## Hồi quy: sửa được gì, làm hỏng gì trên 47 câu cũ

| Cấu hình | Sai → đúng | Đúng → sai | ID đúng → sai |
|---|---:|---:|---|
| original | 0 | 0 | — |
| original_masked | 7 | 5 | S5-T-004, S5-T-011, S5-T-036, S5-T-038, S5-T-055 |
| balanced | 13 | 9 | S5-T-014, S5-T-015, S5-T-016, S5-T-028, S5-T-031, S5-T-033, S5-T-034, S5-T-036, S5-T-038 |
| balanced_masked | 14 | 9 | S5-T-001, S5-T-014, S5-T-015, S5-T-016, S5-T-028, S5-T-031, S5-T-034, S5-T-036, S5-T-038 |

ID tất cả ca sửa đúng và regression, thứ hạng/điểm từng câu: `run01/results.json` và `run01/summary.json`. Không đổi gold label hoặc âm thầm loại ca giảm chất lượng.

## Theo nhãn — top-1

| Tập / nhãn | original | original_masked | balanced | balanced_masked |
|---|---:|---:|---:|---:|
| development / NUMERIC | 5/12 | 12/12 | 8/12 | 8/12 |
| development / REPORT_CONTENT | 2/12 | 8/12 | 3/12 | 4/12 |
| development / NEWS | 4/12 | 4/12 | 4/12 | 4/12 |
| development / TREND | 7/12 | 8/12 | 5/12 | 4/12 |
| development / PERSON_ROLE | 8/12 | 12/12 | 8/12 | 8/12 |
| development / ENTITY_RELATION | 2/12 | 4/12 | 4/12 | 8/12 |
| development / MIXED | 6/12 | 8/12 | 8/12 | 8/12 |
| regression / NUMERIC | 5/7 | 5/7 | 6/7 | 5/7 |
| regression / REPORT_CONTENT | 1/6 | 1/6 | 5/6 | 6/6 |
| regression / NEWS | 4/8 | 5/8 | 3/8 | 2/8 |
| regression / TREND | 5/6 | 5/6 | 2/6 | 3/6 |
| regression / PERSON_ROLE | 3/8 | 2/8 | 4/8 | 4/8 |
| regression / ENTITY_RELATION | 3/6 | 3/6 | 4/6 | 4/6 |
| regression / MIXED | 1/6 | 3/6 | 2/6 | 3/6 |

## Ứng viên theo điều kiện đã đặt trước

Điều kiện: top-1 dev tăng, số sai tuyến vượt ngưỡng không tăng trên dev và regression. Các cấu hình qua bộ lọc này: **balanced**. Đây chỉ là lọc ứng viên gửi review, không phải nghiệm thu hoặc tự triển khai.

## Giới hạn và cách chạy lại

- **Chưa có cấu hình nào được đề nghị thay baseline chính thức.** Balanced qua bộ lọc ứng viên nhưng làm hỏng 9 câu cũ và chỉ nhận 4/84 câu dev, còn 80/84 fallback. Không coi số sai tuyến bằng 0 là đã có hệ thống phân loại tốt.
- Balanced sửa cả 8 known probes nhưng chỉ đúng 40/84 câu dev (47,62%). Đây là minh họa vì sao không nghiệm thu chỉ bằng các câu lỗi đã biết. Original_masked có dev top-1 cao nhất nhưng tăng sai tuyến vượt ngưỡng trên regression từ 0 lên 2; balanced_masked tăng lên 1. Chưa chọn các cấu hình này để tích hợp.
- Bước tiếp theo cần Huyền/Hưng review bộ mẫu ứng viên và tiêu chí chấp nhận hồi quy; bổ sung bộ riêng rồi đánh giá lại. 28 câu later-check vẫn để nguyên chưa chấm. Không chỉnh tiếp dữ liệu sau lượt này rồi gọi cùng các tập vừa xem là kiểm thử độc lập.
- Số ca sai tuyến phụ thuộc cả độ bao phủ: phải đọc accepted_coverage và wrong_route_rate_among_accepted trong summary, không chỉ đếm lỗi tuyệt đối.
- Bản cân bằng thay nội dung/số lượng/cách phân bố ticker cùng lúc; chưa quy được cải thiện cho riêng một thay đổi trong đó.
- Che ticker chỉ dùng registry hữu hạn, không giải quyết đầy đủ tên doanh nghiệp/alias. Chưa kiểm tra câu hỏi so sánh nhiều công ty mà masking có thể mất phân biệt.
- File library-draft là định dạng tối thiểu của thí nghiệm, chưa là artifact 03.2 được duyệt. Runner gắn component_intents cho bốn family MIXED để mô tả mẫu; chưa trích thành phần query và chưa dùng loader artifact chính thức cho bản DRAFT.
- Chưa hiệu chỉnh ngưỡng, chưa gọi LLM/fallback, chưa tích hợp WebChat.

Kiểm chứng không cần model: `python backend/scripts/audit_s5_intent_experiment.py` (cần NumPy). Tạo lại báo cáo: `python backend/scripts/report_s5_intent_experiment.py`.

Muốn chạy lại inference: `python backend/scripts/run_s5_intent_experiment.py --output outputs/s5_intent_experiment_20261111/run02` (từ chối ghi đè); cần cache BGE-M3 đúng revision và thiết lập offline/CPU như tài liệu 04.1. Bản gốc, run01 cũ và ngưỡng không thay đổi.
