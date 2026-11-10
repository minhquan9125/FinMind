# S5-WBS04.1 — Kết quả baseline run01 và phân tích ca sai

Ngày: 10/11/2026. Policy cố định: cosine-max-per-label-v1. Model thật BGE-M3,
cùng full revision với artifact 03.3. Không sửa mẫu, test, vector thư viện hoặc
policy sau khi xem kết quả lượt này. Không chọn threshold hoặc route.

## Kết quả

| Chỉ số | Giá trị |
|---|---:|
| Câu test tổng | 56 |
| Câu có nhãn để tính điểm | 47 |
| Top-1 đúng | 22/47 = 46,81% |
| Nhãn đúng trong top-3 | 41/47 = 87,23% |
| Macro-F1 bảy nhãn | 0,4680 |
| Ca null chỉ quan sát | 9 |

Tổng thời gian batch bao gồm nạp model lazy là khoảng 140 giây; không phải độ trễ
mỗi request. Chức năng đối chiếu chạy đúng và trả đủ điểm/ứng viên; chất lượng
top-1 hiện thấp, chưa phù hợp để mặc định chọn nhãn đầu làm quyết định điều phối.
Không có ngưỡng chất lượng nghiệm thu được định trước để kết luận đạt về accuracy.

| Nhãn | Đúng top-1 / số ca | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| NUMERIC | 5/7 | 0.5000 | 0.7143 | 0.5882 |
| REPORT_CONTENT | 1/6 | 0.2500 | 0.1667 | 0.2000 |
| NEWS | 4/8 | 0.6667 | 0.5000 | 0.5714 |
| PERSON_ROLE | 3/8 | 0.7500 | 0.3750 | 0.5000 |
| ENTITY_RELATION | 3/6 | 1.0000 | 0.5000 | 0.6667 |
| TREND | 5/6 | 0.5000 | 0.8333 | 0.6250 |
| MIXED | 1/6 | 0.1000 | 0.1667 | 0.1250 |

## Nhận xét theo bằng chứng

- REPORT_CONTENT chỉ đúng 1/6; thường bị đứng sau câu mẫu đọc số, tin hoặc chức vụ.
  T007 hỏi tóm lược cam kết trong BCTN nhưng gần nhất là mẫu đọc tỷ lệ trong BCTN.
- MIXED chỉ đúng 1/6; ngược lại 10 câu được xếp MIXED đầu nhưng chỉ một câu đúng.
  Các nhãn đơn NEWS/PERSON_ROLE cũng bị lẫn vào MIXED. Không thể coi một điểm gần
  mẫu kết hợp là bằng chứng đã tách được nhiều ý định trong câu hỏi.
- C07 bổ nhiệm đạt trên cả T055/T056: hỏi người nhận chức -> PERSON_ROLE; tìm bài
  tin -> NEWS. Tuy nhiên T013 xin tin miễn nhiệm và T024 xin bằng chứng chức vụ
  vẫn sai; thành công một cặp không chứng minh toàn bộ ranh giới đã được học.
- T041 hỏi tóm tắt tin và bảng EPS đứng NEWS đầu, MIXED thứ hai. T037 đối chiếu
  báo cáo/tin đứng REPORT_CONTENT đầu, MIXED thứ ba. Có nhãn đúng trong top-3
  nhưng vẫn cần tầng quyết định sau; chưa tự chọn nhãn đúng dựa vào đáp án test.
- Cả ba hình thức có dấu/không dấu/viết tắt đều khoảng 46–47% top-1. Không có
  bằng chứng đây chỉ là lỗi dấu tiếng Việt. Độ phủ 30 câu gốc và cách embedding
  phản ánh chủ đề/từ ngữ có thể góp phần gây nhầm; đây là giả thuyết từ quan sát,
  chưa phải kết luận nguyên nhân đã được kiểm chứng bằng thí nghiệm riêng.

## Tất cả ca sai top-1

| ID | Nhãn kỳ vọng | Top-1 | Điểm top-1 | Hạng nhãn đúng | Ví dụ gần nhất |
|---|---|---|---:|---:|---|
| S5-T-002 | NUMERIC | MIXED | 0.5791 | 3 | S5-L-090 |
| S5-T-005 | NUMERIC | TREND | 0.5285 | 4 | S5-L-070 |
| S5-T-007 | REPORT_CONTENT | NUMERIC | 0.6447 | 3 | S5-L-006 |
| S5-T-008 | REPORT_CONTENT | NEWS | 0.6069 | 2 | S5-L-034 |
| S5-T-009 | REPORT_CONTENT | TREND | 0.6649 | 2 | S5-L-065 |
| S5-T-010 | REPORT_CONTENT | NUMERIC | 0.7269 | 2 | S5-L-005 |
| S5-T-012 | REPORT_CONTENT | PERSON_ROLE | 0.6260 | 2 | S5-L-045 |
| S5-T-013 | NEWS | MIXED | 0.5195 | 4 | S5-L-088 |
| S5-T-017 | NEWS | MIXED | 0.5713 | 2 | S5-L-089 |
| S5-T-018 | NEWS | MIXED | 0.5777 | 2 | S5-L-081 |
| S5-T-021 | PERSON_ROLE | NUMERIC | 0.6168 | 4 | S5-L-005 |
| S5-T-022 | PERSON_ROLE | REPORT_CONTENT | 0.6067 | 2 | S5-L-023 |
| S5-T-023 | PERSON_ROLE | MIXED | 0.5255 | 2 | S5-L-076 |
| S5-T-024 | PERSON_ROLE | MIXED | 0.5803 | 5 | S5-L-087 |
| S5-T-025 | ENTITY_RELATION | NUMERIC | 0.5349 | 2 | S5-L-004 |
| S5-T-026 | ENTITY_RELATION | MIXED | 0.5491 | 2 | S5-L-073 |
| S5-T-027 | ENTITY_RELATION | NUMERIC | 0.6273 | 6 | S5-L-005 |
| S5-T-032 | TREND | REPORT_CONTENT | 0.6041 | 2 | S5-L-016 |
| S5-T-037 | MIXED | REPORT_CONTENT | 0.6620 | 3 | S5-L-013 |
| S5-T-039 | MIXED | TREND | 0.7147 | 2 | S5-L-065 |
| S5-T-040 | MIXED | TREND | 0.6160 | 3 | S5-L-065 |
| S5-T-041 | MIXED | NEWS | 0.6059 | 2 | S5-L-030 |
| S5-T-042 | MIXED | TREND | 0.5563 | 5 | S5-L-070 |
| S5-T-053 | NEWS | MIXED | 0.7090 | 2 | S5-L-080 |
| S5-T-054 | PERSON_ROLE | MIXED | 0.6016 | 3 | S5-L-087 |

Sáu câu không có nhãn đúng trong top-3: T005, T013, T021, T024, T027, T042.
Văn bản câu hỏi và các ví dụ đối chiếu đầy đủ nằm trong results.jsonl, không chỉ
trong bảng tổng hợp. Không đổi nhãn kỳ vọng để biến các ca này thành đúng.

## Chín câu chưa gán nhãn

Không có threshold/abstention ở 04.1 nên các câu này vẫn có hàng xóm gần nhất.
Chúng không được tính thành đúng hay sai bảy lớp. Một câu chưa rõ loại tài liệu
(T050) có điểm đầu khoảng 0,6516, cao hơn nhiều ca có nhãn rõ. Vì vậy không diễn
giải cosine thành xác suất đúng, cũng không tự đặt một ngưỡng từ chín câu này.

| ID | Trạng thái kỳ vọng | Nhóm gần nhất | Điểm |
|---|---|---|---:|
| S5-T-043 | NEEDS_CONTEXT | MIXED | 0.3895 |
| S5-T-044 | NEEDS_CONTEXT | NEWS | 0.3588 |
| S5-T-045 | NEEDS_CONTEXT | REPORT_CONTENT | 0.4893 |
| S5-T-046 | OUTSIDE_TAXONOMY | MIXED | 0.3399 |
| S5-T-047 | OUTSIDE_TAXONOMY | TREND | 0.4531 |
| S5-T-048 | OUTSIDE_TAXONOMY | NEWS | 0.5239 |
| S5-T-049 | UNRESOLVED | TREND | 0.4634 |
| S5-T-050 | UNRESOLVED | REPORT_CONTENT | 0.6516 |
| S5-T-051 | UNRESOLVED | NEWS | 0.5406 |

## Đề xuất sau review

Giữ run01 làm baseline; leader review riêng hai phần: chức năng trả nhóm/điểm và
chất lượng nhãn đứng đầu. Nếu cần nâng chất lượng, thống nhất bộ development và
bộ đánh giá mới, mở rộng mẫu/phiên bản có kiểm soát rồi đo lại trên phần chưa dùng
để điều chỉnh. Chưa tự sửa thư viện 03.2/03.3 đã được duyệt trong lượt này.

Không đưa baseline hiện tại vào WebChat để tự động chọn route. Task 04.2 hoặc
tầng điều phối phải có hợp đồng riêng về ngưỡng, ngữ cảnh và ý định kết hợp.
