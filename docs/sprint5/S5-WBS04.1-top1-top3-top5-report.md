# S5-WBS04.1 — So sánh top-1, top-3 và top-5

Ngày phân tích: 11/11/2026. Người thực hiện: Hồ Phạm Đăng Nhân.

## Kết quả chính

| Chỉ số | Nhãn đúng nằm trong danh sách | Bỏ sót | Số nhãn trả mỗi câu |
|---|---:|---:|---:|
| Top-1 | 22/47 (46.81%) | 25 | 1 |
| Top-3 | 41/47 (87.23%) | 6 | 3 |
| Top-5 | 46/47 (97.87%) | 1 | 5 |

Top-3 thêm **19 câu** so với top-1 (**40.43 điểm phần trăm**). Top-5 thêm **5 câu** so với top-3 (**10.64 điểm phần trăm**).

## Cách đo và phạm vi

- Dùng cùng đầu ra model thật của run01 ngày 10/11, đã lưu đủ thứ hạng của **7 nhãn khác nhau**; cắt danh sách tại 1, 3 và 5. Đây là phân tích bổ sung, không phải ba lần chạy model mới.
- BGE-M3 cùng full revision và artifact 03.3. Policy cosine-max-per-label-v1: điểm một nhãn là cosine cao nhất trong các câu mẫu mang nhãn đó. Không đổi mẫu, model hoặc điểm.
- Top-k ở đây là **nhóm ý định**, không phải k câu mẫu trong trường examples. Mỗi câu có đúng một gold label; MIXED được tính là một nhãn. Không đánh giá component_intents.
- Công thức: số câu có gold label trong k nhóm đầu / 47. Top-1 trùng accuracy; top-3/top-5 là Hit@k (cũng là Recall@k khi mỗi câu có một gold label), không phải accuracy của một quyết định cuối cùng.
- Tổng 56 câu: 47 có nhãn (44 RESOLVED, 3 PARTIAL) dùng tính điểm; 9 câu null bị loại khỏi mẫu số và vẫn được lưu trong JSON. PARTIAL có thể rõ ý định nhưng thiếu doanh nghiệp/ngữ cảnh để trả lời.
- Top-1/top-3 đối chiếu khớp summary cũ. Run01 giữ nguyên checksum. Top-5 là chỉ số phân tích sau lượt đo, chưa phải tiêu chí nghiệm thu định trước.

## Theo nhãn

| Nhãn | Top-1 | Top-3 | Top-5 |
|---|---:|---:|---:|
| NUMERIC | 5/7 (71.43%) | 6/7 (85.71%) | 7/7 (100.00%) |
| REPORT_CONTENT | 1/6 (16.67%) | 6/6 (100.00%) | 6/6 (100.00%) |
| NEWS | 4/8 (50.00%) | 7/8 (87.50%) | 8/8 (100.00%) |
| PERSON_ROLE | 3/8 (37.50%) | 6/8 (75.00%) | 8/8 (100.00%) |
| ENTITY_RELATION | 3/6 (50.00%) | 5/6 (83.33%) | 5/6 (83.33%) |
| TREND | 5/6 (83.33%) | 6/6 (100.00%) | 6/6 (100.00%) |
| MIXED | 1/6 (16.67%) | 5/6 (83.33%) | 6/6 (100.00%) |

### Nhận xét theo nhãn

- REPORT_CONTENT tăng từ 1/6 ở top-1 lên 6/6 ở top-3; trong bộ này nhãn đúng đã có trong ba ứng viên đầu nhưng thường chưa đứng đầu. Tăng lên top-5 không bổ sung thêm câu nào của nhóm này.
- PERSON_ROLE tăng từ 3/8 lên 6/8 rồi 8/8; hai câu T021/T024 chỉ xuất hiện ở hạng 4/5. NEWS, NUMERIC và MIXED mỗi nhóm được bổ sung một câu khi tăng từ 3 lên 5.
- MIXED chỉ đúng 1/6 ở top-1 dù đạt 6/6 ở top-5: chưa thể suy ra hệ thống đã tách được các ý định thành phần hoặc chọn đúng nhánh.
- ENTITY_RELATION không tăng từ top-3 lên top-5 (đều 5/6). T027 hỏi quan hệ hợp tác nhưng ENTITY_RELATION ở hạng 6. Có thể câu gần mẫu theo bối cảnh báo cáo hơn thao tác hỏi quan hệ; đây là giả thuyết từ câu hỏi/thứ hạng, chưa phải nguyên nhân được kiểm chứng. Cần bộ câu development riêng để kiểm tra thay vì sửa mẫu theo riêng T027.

## Theo độ đầy đủ ngữ cảnh

| Nhóm | Top-1 | Top-3 | Top-5 |
|---|---:|---:|---:|
| PARTIAL | 1/3 (33.33%) | 3/3 (100.00%) | 3/3 (100.00%) |
| RESOLVED | 21/44 (47.73%) | 38/44 (86.36%) | 43/44 (97.73%) |

## Theo hình thức câu hỏi

| Nhóm | Top-1 | Top-3 | Top-5 |
|---|---:|---:|---:|
| ABBREVIATED | 8/17 (47.06%) | 14/17 (82.35%) | 17/17 (100.00%) |
| ACCENTED | 7/15 (46.67%) | 14/15 (93.33%) | 15/15 (100.00%) |
| UNACCENTED | 7/15 (46.67%) | 13/15 (86.67%) | 14/15 (93.33%) |

## Các câu chỉ được bổ sung khi mở từ top-3 lên top-5

| ID | Câu hỏi | Nhãn đúng | Hạng | Năm nhãn đầu |
|---|---|---|---:|---|
| S5-T-005 | Giá ĐC SSI ngày 15/09/2025 là bn đồng/cp? | NUMERIC | 4 | TREND → MIXED → ENTITY_RELATION → NUMERIC → PERSON_ROLE |
| S5-T-013 | Có những bài báo nào về quyết định miễn nhiệm Giám đốc tài chính HPG trong tháng 08/2025? | NEWS | 4 | MIXED → PERSON_ROLE → TREND → NEWS → ENTITY_RELATION |
| S5-T-021 | BCTN REE 2022 ghi nhan ai phu trach vi tri ke toan truong tai cuoi nam? | PERSON_ROLE | 4 | NUMERIC → REPORT_CONTENT → TREND → PERSON_ROLE → MIXED |
| S5-T-024 | Theo BCTN REE 2022, ai được bổ nhiệm làm KTT? Trích câu làm bằng chứng cho câu trả lời; KTT = kế toán trưởng. | PERSON_ROLE | 5 | MIXED → REPORT_CONTENT → TREND → NEWS → PERSON_ROLE |
| S5-T-042 | Cty Hoa Mai có phải đơn vị do PNJ kiểm soát cuối 2023 không, và XH giá PNJ trong Q1/2024 ra sao? | MIXED | 5 | TREND → ENTITY_RELATION → PERSON_ROLE → NUMERIC → MIXED |

## Các câu vẫn bị bỏ sót ở top-5

- **S5-T-027**, gold `ENTITY_RELATION`, hạng 6: Theo BCTN REE 2023, REE va cong ty Song Xanh co quan he hop tac khong? Năm nhãn đầu: NUMERIC → PERSON_ROLE → REPORT_CONTENT → TREND → MIXED.

## Ý nghĩa và đề xuất gửi reviewer

- Top-1 đo khả năng xếp đúng nhãn đầu. Kết quả còn thấp; chưa có cơ sở mặc định dùng nhãn đầu để điều phối câu hỏi.
- Top-3/top-5 đo khả năng giữ lại nhãn đúng cho bước xử lý sau. Mở rộng danh sách không làm nhãn đầu chính xác hơn và không tự giải quyết các ca sai.
- Top-5 giữ 5/7 nhãn (71,43% không gian nhãn), nên tỷ lệ cao cần được đọc cùng độ rộng danh sách. Tỷ lệ 5/7 này không phải accuracy của một baseline ngẫu nhiên đã chạy.
- Nếu luôn trả đủ k nhãn, top-3/top-5 sẽ luôn kèm ít nhất 2/4 nhãn không phải gold. Chưa đo chất lượng tầng chọn cuối, latency hoặc chi phí các nhánh khi tích hợp; ba top-k dùng cùng embedding và thứ hạng nên không có ba số latency độc lập.
- Đề nghị Hưng review riêng: công thức/thứ hạng, khả năng giữ ứng viên và chất lượng top-1. Có thể dùng top-3 làm mốc so sánh ứng viên, xem top-5 như phân tích độ bao phủ bổ sung; chưa chốt k cho production hoặc tự thêm tầng chọn nhãn.
- Nếu cần cải thiện, thống nhất tiêu chí trên tập development riêng và đánh giá bằng test mới. Bộ hiện tại nhỏ, do cùng tác giả soạn mẫu/test và đã được xem kết quả; các chênh lệch là mô tả bộ này, chưa chứng minh ý nghĩa thống kê hoặc hiệu quả Web Chat.

## Tái tạo và truy vết

Chạy từ repository: `python backend/scripts/report_s5_intent_topk.py` (Python chuẩn, không cần model/DB). Lệnh chỉ tạo lại báo cáo phân tích; không ghi run01.

Dữ liệu chi tiết, thứ hạng gold của từng câu và checksum nguồn: `outputs/s5_wbs041_topk_20261111/comparison.json`. Lượt kiểm chứng model thật trước đó: `outputs/s5_wbs041_review_20261111/real-model-audit.json`.
