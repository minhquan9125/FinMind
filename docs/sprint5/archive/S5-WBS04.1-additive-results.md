# S5-WBS04.1 — Giữ mẫu gốc và bổ sung: kết quả 12/11/2026

**Chưa đề nghị thay baseline chính thức.** Không ứng viên nào đạt đủ điều kiện đã đặt trước. Không sửa taxonomy, artifact gốc, ngưỡng 0,65/0,08, router hoặc payload top-3.

## Điều đã làm

- Phân tích 9 ca hồi quy ở bản thay thế; mất mẫu tin, sự kiện, xu hướng và câu kết hợp. Chi tiết trong `S5-WBS04.1-additive-plan.md`.
- add_all: 90 mẫu gốc + 112 mẫu mới = 202 hàng; add_focused: 90 gốc + 48 mẫu PERSON_ROLE/ENTITY_RELATION/MIXED = 138 hàng. Giữ nguyên từng hàng và byte vector cũ.
- Không che ticker. Dùng lại embedding BGE-M3 thật đã lưu cho mẫu/query cũ, cùng revision và cosine-max-per-label-v1. Không thêm câu test vào thư viện.
- Hai ứng viên được định trước. Đóng băng selection.json trước khi đọc/chấm 28 câu để dành. Chỉ ứng viên đã chọn và baseline được chạy trên bộ 28; không chọn lại theo điểm bộ này.

## 84 câu phát triển đã xem

| Cấu hình | Top-1 | Top-3 | Top-5 | Fallback | Nhận đúng tuyến | Nhận sai tuyến |
|---|---:|---:|---:|---:|---:|---:|
| original | 34/84 (40.48%) | 67/84 (79.76%) | 80/84 (95.24%) | 69 | 8 | 7 |
| add_all | 40/84 (47.62%) | 78/84 (92.86%) | 83/84 (98.81%) | 80 | 4 | 0 |
| add_focused | 30/84 (35.71%) | 49/84 (58.33%) | 77/84 (91.67%) | 75 | 9 | 0 |

## 47 câu cũ có nhãn

| Cấu hình | Top-1 | Top-3 | Top-5 | Fallback | Nhận đúng tuyến | Nhận sai tuyến |
|---|---:|---:|---:|---:|---:|---:|
| original | 22/47 (46.81%) | 41/47 (87.23%) | 46/47 (97.87%) | 45 | 2 | 0 |
| add_all | 27/47 (57.45%) | 41/47 (87.23%) | 46/47 (97.87%) | 44 | 3 | 0 |
| add_focused | 27/47 (57.45%) | 41/47 (87.23%) | 46/47 (97.87%) | 45 | 2 | 0 |

## 8 câu chẩn đoán đã biết

| Cấu hình | Top-1 | Top-3 | Top-5 | Fallback | Nhận đúng tuyến | Nhận sai tuyến |
|---|---:|---:|---:|---:|---:|---:|
| original | 3/8 (37.50%) | 7/8 (87.50%) | 7/8 (87.50%) | 3 | 2 | 3 |
| add_all | 8/8 (100.00%) | 8/8 (100.00%) | 8/8 (100.00%) | 3 | 5 | 0 |
| add_focused | 7/8 (87.50%) | 7/8 (87.50%) | 8/8 (100.00%) | 4 | 4 | 0 |

## Hồi quy trên bộ cũ

| Ứng viên | Sai → đúng | Đúng → sai | ID đúng → sai |
|---|---:|---:|---|
| add_all | 7 | 2 | S5-T-034, S5-T-036 |
| add_focused | 5 | 0 | — |

add_all còn hỏng T034/T036: hai câu xu hướng bị cạnh tranh bởi mẫu đọc số mới. Giữ mẫu cũ ngăn mất độ phủ nhưng không bảo đảm nhãn cũ giữ hạng đầu khi thêm đối thủ.

## Chọn ứng viên trước khi đo 28 câu

Đã chọn **add_focused** theo thứ tự ưu tiên đã ghi trước: điều kiện đạt, sai tuyến vượt ngưỡng, hồi quy, điểm dev/regression, kích thước thư viện. Cờ đủ điều kiện trước later-check: **False**. Đây là chọn để đo chẩn đoán, không phải chấp nhận thay runtime.

add_focused có 0 hồi quy trên bộ cũ và sửa thêm 5 câu, nhưng dev top-1 giảm 34→30/84; top-3 cũng giảm 67→49/84. Vì vậy chưa phải cải thiện tổng quát.

## Một lượt kiểm tra sau — 28 câu

| Cấu hình | Top-1 | Top-3 | Top-5 | Fallback | Nhận đúng tuyến | Nhận sai tuyến |
|---|---:|---:|---:|---:|---:|---:|
| original | 19/28 (67.86%) | 26/28 (92.86%) | 26/28 (92.86%) | 27 | 1 | 0 |
| add_focused | 19/28 (67.86%) | 25/28 (89.29%) | 26/28 (92.86%) | 26 | 2 | 0 |

### Theo nhãn: baseline so với ứng viên được chọn

| Tập / nhãn | Baseline top-1 | add_focused top-1 |
|---|---:|---:|
| Dev / NUMERIC | 5/12 | 2/12 |
| Dev / REPORT_CONTENT | 2/12 | 0/12 |
| Dev / NEWS | 4/12 | 0/12 |
| Dev / TREND | 7/12 | 2/12 |
| Dev / PERSON_ROLE | 8/12 | 9/12 |
| Dev / ENTITY_RELATION | 2/12 | 7/12 |
| Dev / MIXED | 6/12 | 10/12 |
| Later / NUMERIC | 1/4 | 1/4 |
| Later / REPORT_CONTENT | 3/4 | 2/4 |
| Later / NEWS | 1/4 | 1/4 |
| Later / TREND | 4/4 | 3/4 |
| Later / PERSON_ROLE | 3/4 | 4/4 |
| Later / ENTITY_RELATION | 3/4 | 4/4 |
| Later / MIXED | 4/4 | 4/4 |

Trên 28 câu: sửa đúng **2**, đúng→sai **2**. ID đúng→sai: LATER-REPORT_CONTENT-1-DGC, LATER-TREND-2-PNJ.

Bộ này do cùng tác giả chuẩn bị từ vòng trước, không phải kiểm thử mù độc lập. Đã được dùng đúng một lượt sau khi đóng băng ứng viên; từ giờ không còn là bộ chưa xem.

## Kết luận và giới hạn

- Hướng bổ sung giảm hồi quy rõ so với thay toàn bộ (9→0 hoặc 2 câu hỏng trên bộ cũ), nhưng chưa đồng thời đạt mục tiêu tăng chất lượng trên các tập phát triển/kiểm tra sau.
- Điểm tổng tăng trên 47 câu cũ không đủ để thay baseline: phải đọc cùng dev, top-3, từng nhãn, tỷ lệ nhận và các ca sai tuyến vượt ngưỡng.
- Các cột tuyến là mô phỏng theo ánh xạ đã trao đổi, chưa gọi code 04.2/WebChat. Fallback không tính là chuyển sai tuyến. Số ca sai bằng 0 khi nhận rất ít câu không đồng nghĩa chất lượng vận hành tốt.
- Chưa có bằng chứng để sửa ngưỡng hoặc tự bật một thư viện mới. Lượt này kiểm chứng hướng bổ sung và chỉ ra giới hạn; không tuyên bố đã sửa xong bài toán.
- Không tiếp tục chỉnh mẫu theo 28 câu rồi gọi điểm đo lại là holdout. Nếu đổi phương pháp đối chiếu tiếp, dùng tập phát triển hiện có và chuẩn bị một phép đánh giá mới; không phải chờ nhóm mới phân tích hoặc thử nghiệm được.

## Chạy lại bằng chứng

- Không cần model: `python backend/scripts/audit_s5_intent_additive.py` (cần NumPy).
- Tạo lại báo cáo: `python backend/scripts/report_s5_intent_additive.py`.
- Chuẩn bị/chốt ứng viên: `python backend/scripts/run_s5_intent_additive.py --output <thư_mục_mới>` (dùng cache vector thật của vòng trước, không đọc later-check).
- Script `check_s5_intent_additive_later.py` từ chối khi lượt later-check đã tồn tại. Không chạy inference lần hai để lựa chọn lại kết quả.
- Nguồn: `outputs/s5_intent_additive_20261112/` gồm method, selection, thư viện DRAFT và vector, kết quả từng câu, summary later-check và audit.
