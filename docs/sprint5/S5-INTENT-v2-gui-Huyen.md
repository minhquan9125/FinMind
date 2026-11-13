# Gửi Huyền: router v2 theo bộ nhãn mới và điều kiện tự chọn nhánh

Người gửi: Hưng. Ngày: 13/11/2026.
Liên quan: S5-WBS04.2, 04.3, 07.1, 07.3 (sheet Sprint 5).
Nhánh của Huyền hiện tại: `huyen-sprint-sprint501` @ `985ad536`. Hưng đã review 07.1 ở commit này: đạt (391/391 test, 345 quyết định V7 thật, 0 lỗi).

## 1. Bối cảnh
- Nhân sẽ đổi bộ nhãn từ 7 lên 11 nhóm tầng 1 (chi tiết trong file `S5-INTENT-v2-gui-Nhan.md`, gửi kèm). Router và contract fallback của Huyền phải theo bộ nhãn mới.
- Hưng sẽ nối router vào chat (05.1) và gọi AI fallback (07.2). Hưng cần router trả ra **nhánh dùng được ngay**, không phải lúc nào cũng `NEED_FALLBACK`.

## 2. Bộ nhãn mới cần cập nhật

| Mã nội bộ | Mã fallback (`ALLOWED_LABELS`) | Nhánh đề xuất (`INTENT_ROUTES`) |
|---|---|---|
| PRICE | GIA | `MARKET` (dữ liệu giá đã lưu và đang cập nhật) |
| NUMERIC | SO_LIEU | `VECTOR` (BCTC) |
| ANALYSIS | PHAN_TICH | `MARKET` (phân tích: giá, xu hướng, tài chính đã đối chiếu, tin) |
| NEWS | NEWS | `MARKET` (tin đang cập nhật); câu có ngày cũ thì `VECTOR` |
| REPORT_CONTENT | BCTC_BCTN | `VECTOR` |
| PERSON_ROLE | CHUC_VU | `GRAPH` |
| ENTITY_RELATION | QUAN_HE | `GRAPH` |
| COMPANY_OVERVIEW | TONG_QUAN | `BOTH` |
| CONVERSATION | HOI_THOAI | `SESSION` (xử lý trong phiên, không tìm kiếm) |
| OUT_OF_SCOPE | NGOAI_PHAM_VI | `REFUSE` (từ chối có lý do, không tìm kiếm) |
| MIXED | KET_HOP | theo thành phần (`_mixed_route`) |
| — | CLARIFY | `ASK_CLARIFICATION` |

Việc cần làm:
- Thêm 3 giá trị nhánh mới (`MARKET`, `SESSION`, `REFUSE`) vào `INTENT_ROUTES`, cập nhật `LABEL_ALIASES` và `ALLOWED_LABELS`.
- Viết lại các luật cấm ghép nhãn/nhánh sai (`LABEL_ROUTE_MISMATCH`) cho đủ 11 nhóm.
- **Ràng buộc an toàn:** NGOAI_PHAM_VI chỉ được đi `REFUSE`. Nếu AI trả NGOAI_PHAM_VI kèm một nhánh tìm kiếm thì phải báo lỗi và hỏi lại.
- `_mixed_route`: xác định nhánh khi các thành phần thuộc các nhóm mới. Ví dụ PRICE + NUMERIC thì đi `MARKET` + `VECTOR`; Hưng sẽ xử lý như `BOTH`.

## 3. Quyết định quan trọng nhất: khi nào router được tự chọn nhánh
Hiện `decide_intent_route` mặc định `allow_direct_search=False`. Kết quả của luật V7 (`EVIDENCE_SCORE_TYPE`) và của classifier (`CLASSIFIER_SCORE_TYPE`) cũng luôn đi `_evidence_fallback`. Như vậy **mọi câu hỏi đều phải gọi AI hoặc hỏi lại**. Nối vào chat như vậy sẽ gây ra:
- mỗi câu hỏi tốn thêm 1 lần gọi Gemini: chậm thêm vài giây, tốn quota. Hôm nay Gemini còn lỗi 503 hoặc timeout khoảng 2/7 lần;
- câu đơn giản như "giá fpt" cũng phải chờ AI.

Đề xuất, nhờ Huyền xem và chốt:
1. **Cho tự chọn nhánh** khi luật V7 nhận diện rõ:
   - `reason='EXPLICIT_REQUEST_TYPE'`, có một nhãn và `unresolved_requests=[]`;
   - hoặc `TWO_EXPLICIT_REQUEST_TYPES` kèm thành phần đã xác minh (07.1 đã có).
2. **Cho tự chọn nhánh** khi điểm embedding vượt ngưỡng đã hiệu chỉnh trên bộ test kín v2, cả điểm cao nhất lẫn khoảng cách giữa hai nhãn đầu. Ngưỡng cũ 0,65/0,08 đo trên bộ cũ: top-1 46,7%, chọn sai 5/15 câu SEARCH. Ngưỡng này không dùng lại được.
3. Các trường hợp còn lại: `NEED_FALLBACK` (AI) hoặc hỏi lại như hiện nay.
4. OUT_OF_SCOPE có thể được tự chọn `REFUSE` ngay khi luật nhận diện rõ (ví dụ "nên mua", "giá mục tiêu"), vì từ chối không tốn tìm kiếm và không trả số liệu sai.

Đầu ra cần có, để Hưng ghi trace: `decision`, `route`, `label`, `reason_code`, điểm cao nhất, khoảng cách hai nhãn đầu, và nguồn quyết định (luật V7 / embedding / AI).

## 4. Việc theo task

### 04.2 (cập nhật)
- Áp dụng bộ nhãn và nhánh mới.
- Thêm điều kiện tự chọn nhánh theo mục 3, có cờ bật/tắt để demo có thể quay về chế độ chỉ dùng fallback.
- Test cho từng điều kiện: luật rõ thì `SEARCH`; điểm thấp thì `NEED_FALLBACK`; OUT_OF_SCOPE thì `REFUSE`; câu kép thì đi theo thành phần.

### 04.3 Bộ câu test router
- Viết **bộ test kín** cho Nhân: khoảng 10 câu mỗi nhãn tầng 1, Nhân không được xem trước. Phải có các cặp dễ nhầm trong mục 4 của file gửi Nhân.
- Bảng kết quả gồm: câu, nhãn kỳ vọng, nhãn thực tế, điểm, lý do, nhánh, và nguồn quyết định (luật / embedding / AI).

### 07.1 (cập nhật contract)
- Đổi `ALLOWED_LABELS` theo bộ mới, cập nhật JSON schema và doc `S5-WBS07.1-fallback-contract.md`.
- Chạy lại 391 test và phần kiểm 345 quyết định V7 với nhãn mới.

### 07.3 Test fallback
- AI trả đúng; sai nhãn; nhãn và nhánh không khớp; NGOAI_PHAM_VI kèm nhánh tìm kiếm; timeout; lỗi 503; JSON hỏng.
- Mọi ca thất bại đều phải hỏi lại người dùng. Câu đã rõ ý định (luật V7) thì xử lý nội bộ, không gọi AI.

## 5. Không làm
- Không sửa code chat (`live_research.py`, `market_research.py`, `b1_answering/**`). Hưng nối ở 05.1 và 07.2.
- Không gọi Gemini thật trong test; dùng phản hồi mẫu.
- Không hạ an toàn hiện có: lỗi nào cũng phải hỏi lại, không đoán nhãn.

## 6. Bàn giao
- Một commit trên `huyen-sprint-sprint501`: router v2, contract v2 kèm test, bộ test kín (gửi riêng cho Hưng, không gửi Nhân), báo cáo đề xuất ngưỡng.
- Đề xuất hạn: chốt điều kiện tự chọn nhánh (mục 3) trước 15/11; router v2 và contract v2 trước 18/11; bộ test kín gửi Hưng trước 16/11, để Nhân kịp chạy run04 trên bộ này.
