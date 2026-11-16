# S5-WBS13.2 — Đánh giá router và fallback

Commit: `cd2726409aeb2b74b27ee1b777edb1fde3a78d33`. Bộ câu: `s5-wbs132-evaluation-v1`; SHA-256 `886f0651fc20c4cf0179da39e1fc333970e921ca5cc27b6bbda92f6fea89a8fa`.

## Kết quả

| Chỉ số | Kết quả |
| --- | --- |
| Nhãn đề xuất v2 đúng (luật + classifier) | 56/60 (93.3%) |
| Nhãn top-1 mô hình tuyến tính trước luật | 51/60 (85.0%) |
| Planner đúng trên các ca có quan sát planner | 41/52 (chỉ số có điều kiện) |
| Nhánh chọn trong harness đúng | 38/60 (63.3%) |
| Đồng thời đúng nhãn, thành phần và nhánh | 35/60 (58.3%) |
| Câu thực sự bắt đầu fallback | 3/60 (5.0%) |
| Lượt generation fallback | 3 |
| Lỗi runner / thiếu kết quả | 0 / 0 |
| p50 / p95 định tuyến ấm | 994.9 / 3050.4 ms |
| Nạp model/artifact ban đầu | 94.67 giây |

Thời gian ấm gồm classifier gọi trong Chat, planner và fallback Gemini khi có. Không gồm HTTP/UI, truy xuất nguồn thật hoặc sinh câu trả lời. Các lỗi vẫn nằm trong mẫu số; số mẫu thời gian là 60. Cold start tách riêng. Fallback đếm lúc bắt đầu countTokens thật, generation được đếm riêng; nhãn gate FALLBACK không đồng nghĩa đã gọi Gemini.

## Theo nhãn kỳ vọng

| Nhãn | Số câu | Đúng nhãn | Đúng nhánh | Đồng thời đúng |
| --- | ---: | ---: | ---: | ---: |
| ANALYSIS | 6 | 5 | 2 | 2 |
| COMPANY_OVERVIEW | 4 | 4 | 3 | 3 |
| CONVERSATION | 6 | 6 | 4 | 4 |
| ENTITY_RELATION | 6 | 6 | 3 | 3 |
| MIXED | 4 | 3 | 1 | 0 |
| NEWS | 6 | 6 | 2 | 2 |
| NUMERIC | 6 | 5 | 5 | 4 |
| OUT_OF_SCOPE | 4 | 4 | 4 | 4 |
| PERSON_ROLE | 6 | 6 | 5 | 5 |
| PRICE | 6 | 6 | 4 | 4 |
| REPORT_CONTENT | 6 | 5 | 5 | 4 |

## Các ca cần review

| ID | Câu hỏi | Nhãn kỳ vọng → thực tế | Nhánh kỳ vọng → thực tế | Lý do/trạng thái |
| --- | --- | --- | --- | --- |
| W132-003 | Hôm nay SSI có bao nhiêu cổ phiếu được giao dịch? | PRICE → PRICE | PRICE → VECTOR | NO_DATA |
| W132-006 | Giá đóng cửa của cổ phiếu hôm qua là mấy đồng vậy? | PRICE → PRICE | ASK_CLARIFICATION → REFUSE | PRICE_QUERY_SEPARATE |
| W132-011 | Trong bài tin công bố kết quả 2024 của PNJ, lấy riêng số lợi nhuận sau thuế, không tóm tắt bài. | NUMERIC → NEWS | VECTOR → VECTOR | NO_DATA |
| W132-012 | BID có doanh thu thuần quý hai là bao nhiêu, mình chưa chọn năm. | NUMERIC → NUMERIC | ASK_CLARIFICATION → VECTOR | NO_DATA |
| W132-014 | Diễn biến RSI của cổ phiếu VNM đang nói lên điều gì? | ANALYSIS → ANALYSIS | ANALYSIS → VECTOR | NO_DATA |
| W132-015 | Chỉ báo Bollinger trên mã TCB đang phản ánh trạng thái nào? | ANALYSIS → ANALYSIS | ANALYSIS → VECTOR | NO_DATA |
| W132-016 | giai thich ly do co phieu SSI giam trong nhung phien vua qua | ANALYSIS → ANALYSIS | ANALYSIS → VECTOR | NO_DATA |
| W132-017 | Giải thích sự khác nhau giữa EPS cơ bản và EPS pha loãng, không cần ví dụ công ty. | ANALYSIS → NUMERIC | KNOWLEDGE → ASK_CLARIFICATION | MISSING_COMPANY |
| W132-019 | Liệt kê các bài báo mới nhất nói về kết quả kinh doanh của HDB. | NEWS → NEWS | NEWS → VECTOR | NO_DATA |
| W132-020 | Tìm bài tin về quyết định bổ nhiệm tổng giám đốc của PNJ trong năm 2024. | NEWS → NEWS | NEWS → GRAPH | NO_DATA |
| W132-021 | tom tat cac tin lien quan den ACB trong thang 10 nam 2025 | NEWS → NEWS | NEWS → BOTH | NO_DATA |
| W132-022 | Có bài báo nào gần đây đưa tin HPG mở rộng nhà máy không? | NEWS → NEWS | NEWS → ANALYSIS | EVALUATION_EMPTY_MARKET |
| W132-026 | Trích đoạn chính sách ghi nhận doanh thu trong thuyết minh BCTC hợp nhất VNM năm 2024. | REPORT_CONTENT → REPORT_CONTENT | VECTOR → ASK_CLARIFICATION | MISSING_METRIC |
| W132-028 | doc muc dinh huong phat trien trong annual report 2024 cua MBB | REPORT_CONTENT → NUMERIC | VECTOR → VECTOR | NO_DATA |
| W132-036 | Theo hồ sơ nhân sự HPG, ông Trần Minh Hải giữ chức gì vào năm 2024? | PERSON_ROLE → PERSON_ROLE | GRAPH → VECTOR | NO_DATA |
| W132-037 | Kể tên những công ty con của PNJ được ghi nhận trong năm 2024. | ENTITY_RELATION → ENTITY_RELATION | GRAPH → VECTOR | NO_DATA |
| W132-040 | cong ty me cua CTR la don vi nao theo ho so doanh nghiep? | ENTITY_RELATION → ENTITY_RELATION | GRAPH → BOTH | NO_DATA |
| W132-041 | HDB có quan hệ hợp tác với những doanh nghiệp nào theo tài liệu đã công bố? | ENTITY_RELATION → ENTITY_RELATION | GRAPH → VECTOR | NO_DATA |
| W132-044 | PNJ hoạt động chủ yếu bằng những sản phẩm và dịch vụ nào? | COMPANY_OVERVIEW → COMPANY_OVERVIEW | OVERVIEW → VECTOR | NO_DATA |
| W132-047 | Xin chào FinMind, mình muốn bắt đầu một phiên nghiên cứu nhé. | CONVERSATION → CONVERSATION | CONVERSATION → ASK_CLARIFICATION | MISSING_COMPANY |
| W132-048 | Cho mình quay lại mã ACB, giữ chỉ tiêu và kỳ vừa hỏi nhé. | CONVERSATION → CONVERSATION | VECTOR → ASK_CLARIFICATION | MISSING_METRIC |
| W132-057 | Nêu chủ tịch HĐQT ACB theo tài liệu 2024 và cho biết tổng tài sản ACB cuối năm 2024. | MIXED → NUMERIC | BOTH → BOTH | NO_DATA |
| W132-058 | Liệt kê công ty con của VNM rồi trích phần rủi ro trong BCTN VNM năm 2024. | MIXED → MIXED | BOTH → VECTOR | NO_DATA |
| W132-059 | Lấy doanh thu thuần MWG năm 2024; sau đó đánh giá xu hướng tài chính của MWG. | MIXED → MIXED | MULTI → PRICE | PRICE_NOT_AVAILABLE |
| W132-060 | Tìm tin bổ nhiệm CEO của PNJ năm 2024 và xác định người được bổ nhiệm là ai. | MIXED → MIXED | BOTH → GRAPH | NO_DATA |

## Phân tích để bàn giao

- Ca nhãn classifier khác kỳ vọng: W132-011, W132-017, W132-028, W132-057. Đối chiếu note trong fixture trước khi chốt nhãn chuẩn.
- Gate của lần phân loại độc lập: {'DIRECT': 45, 'FALLBACK': 9, 'NEEDS_CONTEXT': 2, 'REFUSE': 4}. Chỉ 3 câu thực sự bắt đầu fallback trong Chat. Hai số khác nhau vì Chat chỉ áp dụng fallback khi luật hiện có hỏi lại.
- Ca có nhãn v2 ANALYSIS/NEWS nhưng scope cuối là BCTN: W132-014, W132-015, W132-016, W132-019, W132-020. Đây là khác biệt giữa nhãn và pipeline sau đó; đối chiếu câu hỏi và scope, chưa tự sửa parser/gate.
- Kế hoạch GRAPH/BOTH và nhánh cuối có thể khác sau khi graph trả rỗng; xem cả planner_outputs, boundary_calls, scope và reason_code, không quy mọi ca lệch nhánh thành lỗi classifier.

| Ca fallback thật | Gemini trả | Chat áp dụng nhãn | Nhánh cuối | Thời gian định tuyến |
| --- | --- | --- | --- | ---: |
| W132-047 | HOI_THOAI | False | ASK_CLARIFICATION | 5153.4 ms |
| W132-048 | HOI_THOAI | False | ASK_CLARIFICATION | 4333.4 ms |
| W132-052 | HOI_THOAI | False | ASK_CLARIFICATION | 3913.7 ms |

Kết quả fallback được giữ nguyên, kể cả nhãn hợp lệ nhưng Chat chưa có nhánh áp dụng. Không kết luận AI sai chỉ vì Chat vẫn hỏi lại. Không điều chỉnh ngưỡng hoặc nhãn để tăng tỷ lệ.

## Phạm vi và giới hạn

- Nhãn kỳ vọng do người triển khai tự soạn, chờ peer review. Không phải bộ kín độc lập; không dùng số này làm bảo đảm chất lượng trên mọi câu mới.
- Audit trước chạy không trùng sau chuẩn hóa với các nguồn trong dataset-audit.json; độ giống ký tự cao nhất 0.8545. Không trùng nguyên câu không chứng minh độc lập ngữ nghĩa.
- BGE-M3 và hai classifier/artifact thật; gọi Gemini thật chỉ ở fallback nếu mode là real. Không fit lại hay sửa luật/ngưỡng để tăng điểm.
- Dùng LiveResearchService + WebChatRouter + DecisionEngine + PriceAnalytics thật. Corpus, graph, feed thị trường và price bars trả rỗng tại biên có ghi trace; AdminNewsChat bỏ qua. Không truy cập DB/Neo4j hoặc lịch sử thật.
- GRAPH/BOTH lấy từ kế hoạch mà bridge đã chọn; biên graph rỗng có thể dừng trước VECTOR. Đúng BOTH không chứng minh cả hai loại bằng chứng đã được lấy. Xem planner_outputs/boundary_calls từng ca.
- Điểm planner chỉ tính các ca có planner_outputs và có mục tiêu ánh xạ được: PRICE/NEWS/ANALYSIS/OVERVIEW/KNOWLEDGE là VECTOR ở tầng planner, GRAPH/BOTH giữ nguyên, hỏi lại là CLARIFY. Các nhánh chuyên biệt ở tầng Chat vẫn đo riêng. Không dùng tỷ lệ có điều kiện này thay tỷ lệ toàn bộ 60 câu.
- PRICE, NEWS, ANALYSIS, OVERVIEW là các nhánh chuyên biệt hiện có, không đổi tên thành VECTOR. MULTI là kỳ vọng xử lý hai mục tiêu không có graph, không mặc định BOTH.
- REFUSE trong bảng là phép gom action UNSUPPORTED của backend; phải xem reason_code để phân biệt từ chối yêu cầu ngoài phạm vi và chưa hỗ trợ một truy vấn giá thiếu dữ kiện.
- Nhãn/gate độc lập dùng nguyên câu đã khóa; Chat có bước normalize_user_text trước khi gọi lại classifier. Không mặc định hai lần nhận đầu vào giống hệt nhau.
- Score classifier chưa hiệu chỉnh; confidence Gemini tự báo chỉ là cổng 0,60 hiện có. Không gọi các điểm này là xác suất đúng.
- Chỉ đánh giá định tuyến trong harness, không xác nhận số liệu, citation, quyền hoặc giao diện Web Chat. Có ca sai là kết quả task đánh giá; không tự sửa phần của Huyền/Hưng.

## Chạy lại

Từ thư mục gốc dự án (Python môi trường backend và model đã cache):

```powershell
backend\.venv\Scripts\python.exe -X utf8 backend/scripts/evaluate_s5_wbs132.py --fallback real --out outputs/s5_wbs132_20261116/run02
```

Tái sinh báo cáo từ đầu ra đã lưu, không gọi model/Google:

```powershell
backend\.venv\Scripts\python.exe -X utf8 backend/scripts/evaluate_s5_wbs132.py --replay outputs/s5_wbs132_20261116/run01/results.json --out outputs/s5_wbs132_20261116/replay01
```

Kỳ vọng được khóa trong `dataset-lock.json` ở thư mục cha. Không ghi đè lượt chạy cũ. Dùng `--fallback none` để đo khi không cấu hình provider; phải giữ kết quả chế độ đó riêng.
