# Gửi Nhân: bộ nhãn ý định v2 và hàm phân loại chạy trong chat

Người gửi: Hưng. Ngày: 13/11/2026.
Liên quan: S5-WBS03.1, 03.2, 03.3, 04.1 (sheet Sprint 5).
Nhánh của Nhân hiện tại: `nhan-sprint-501` @ `c5a9bf3c` (luật V7, policy `intent-request-objectives-v5`).

## 1. Vì sao phải làm lại
- Bộ nhãn hiện tại có 7 nhãn: NUMERIC, REPORT_CONTENT, NEWS, PERSON_ROLE, ENTITY_RELATION, TREND, MIXED. Chat thật có nhiều loại câu hỏi hơn: hỏi giá, phân tích, hỏi lại nguồn, nối tiếp hội thoại, câu ngoài phạm vi… Các câu này hiện chưa có nhãn, nên router sẽ ép chúng vào 7 nhãn và chọn sai nhánh.
- Code của Nhân hiện chỉ chạy offline (script đánh giá). Chat chưa có hàm nào nhận câu hỏi và trả ra kết quả phân loại lúc chạy. Task 05.1 (Hưng nối router vào chat) đang chờ hàm này.

## 2. Nguyên tắc: phân loại 2 tầng
- **Tầng 1 (Nhân làm):** khoảng 11 nhóm lớn, phân loại bằng embedding, thư viện câu mẫu và luật V7.
- **Tầng 2 (Hưng làm):** ý định con và slot (mã, kỳ, chỉ tiêu, định dạng), làm bằng luật trong `analyze_live`.

Lý do chia 2 tầng: embedding phân biệt nhóm lớn tốt. Nếu bắt nó phân biệt khoảng 40 nhãn nhỏ thì mỗi nhãn phải có rất nhiều câu mẫu, và độ chính xác sẽ giảm.

## 3. Bộ nhãn tầng 1 (v2)
Cột "Mã nội bộ" là mã trong code của Nhân. Cột "Mã fallback" là nhãn gửi cho AI ở contract 07.1 của Huyền.

| Mã nội bộ | Mã fallback | Thay cho nhãn cũ | Gồm các ý định con (tầng 2, chỉ để hiểu phạm vi) |
|---|---|---|---|
| PRICE | GIA | (mới) | giá hiện tại; giá theo ngày; biến động trong khoảng; so sánh giá; khối lượng |
| NUMERIC | SO_LIEU | NUMERIC | 1 chỉ tiêu 1 kỳ; tăng trưởng giữa các kỳ; chỉ số (ROE, P/E…); nhiều chỉ tiêu; so sánh công ty |
| ANALYSIS | PHAN_TICH | TREND | phân tích cổ phiếu; phân tích tài chính; phân tích kỹ thuật/xu hướng; nguyên nhân giá tăng/giảm; so sánh doanh nghiệp |
| NEWS | NEWS | NEWS | danh sách tin; tóm tắt tin; chi tiết 1 bài; tin thị trường chung; tin theo nguồn |
| REPORT_CONTENT | BCTC_BCTN | REPORT_CONTENT | nội dung/thuyết minh BCTC; nội dung BCTN (chiến lược, rủi ro…) |
| PERSON_ROLE | CHUC_VU | PERSON_ROLE | ai giữ chức gì; một người giữ chức gì |
| ENTITY_RELATION | QUAN_HE | ENTITY_RELATION | công ty con; cổ đông lớn; công ty liên kết/liên quan |
| COMPANY_OVERVIEW | TONG_QUAN | (mới) | giới thiệu doanh nghiệp (ngành, hoạt động chính) |
| CONVERSATION | HOI_THOAI | (mới) | nối tiếp ("còn SSI"); chọn phương án ("số 2"); hỏi nguồn; tổng hợp nãy giờ; liệt kê ý vừa nói; phiên mới; chào hỏi |
| OUT_OF_SCOPE | NGOAI_PHAM_VI | (mới) | tư vấn mua/bán; giá mục tiêu; dự báo giá; câu không liên quan tài chính |
| MIXED | KET_HOP | MIXED | từ 2 nhóm trở lên trong một câu |
| — | CLARIFY | — | chỉ dùng cho đầu ra fallback, không nằm trong thư viện |

Ghi chú:
- **"Định dạng" (danh sách, bảng, tóm tắt) là slot, không phải nhãn.** Ví dụ: "lập bảng doanh thu fpt 3 năm" vẫn là NUMERIC.
- Câu OUT_OF_SCOPE không bao giờ được rơi vào nhánh trả lời số liệu. Đây là lỗi nặng nhất, phải đo riêng.

## 4. Các cặp dễ nhầm (bắt buộc có trong thư viện và bộ test)

| Câu | Nhãn đúng | Dễ nhầm với |
|---|---|---|
| phân tích tài chính fpt / sức khỏe tài chính fpt | ANALYSIS | NUMERIC |
| doanh thu fpt quý 3/2026 | NUMERIC | ANALYSIS |
| xu hướng giá fpt / phân tích kỹ thuật fpt | ANALYSIS | PRICE |
| giá fpt hôm nay | PRICE | ANALYSIS |
| vì sao fpt giảm | ANALYSIS | NEWS |
| tin fpt hôm nay | NEWS | ANALYSIS |
| fpt mạnh hay yếu | ANALYSIS | OUT_OF_SCOPE |
| có nên mua fpt / giá mục tiêu fpt | OUT_OF_SCOPE | ANALYSIS |
| fpt tuần sau lên bao nhiêu | OUT_OF_SCOPE | PRICE |
| ai là chủ tịch fpt | PERSON_ROLE | COMPANY_OVERVIEW |
| fpt là công ty gì | COMPANY_OVERVIEW | PERSON_ROLE |
| fpt có những công ty con nào | ENTITY_RELATION | NUMERIC |
| doanh thu của công ty con fpt | NUMERIC | ENTITY_RELATION |
| thuyết minh nợ vay fpt | REPORT_CONTENT | NUMERIC |
| nợ vay fpt năm 2025 | NUMERIC | REPORT_CONTENT |
| còn ssi thì sao / số 2 / nguồn ở đâu | CONVERSATION | NUMERIC, NEWS |
| ban kiểm soát fpt gồm ai | PERSON_ROLE | ENTITY_RELATION |
| chủ tịch fpt là ai và doanh thu 2025 bao nhiêu | MIXED (PERSON_ROLE + NUMERIC) | PERSON_ROLE |

## 5. Việc cần làm

### 5.1 Thư viện câu mẫu v2 (03.2, 03.3)
- **Đề xuất (nhóm chốt lại):** mỗi nhãn tầng 1 có ít nhất 20 câu mẫu, và mỗi ý định con có ít nhất 3 câu.
- Có đủ các dạng: có dấu, không dấu, viết tắt (`bctc`, `lnst`, `dt`), sai chính tả hay gặp, cả mã viết thường lẫn viết hoa.
- Tách riêng bộ test khỏi thư viện, không câu nào trùng.
- Thêm một **bộ test kín** do người khác viết; đề xuất Huyền viết khoảng 10 câu mỗi nhãn. Bộ 167 câu cũ đã dùng để chỉnh luật nên không còn khách quan.
- Vector hóa bằng đúng mô hình backend đang dùng: `BAAI/bge-m3`, revision ghim trong `settings.embedding_model_revision`. `IntentMatcher` sẽ báo `MODEL_MISMATCH` hoặc `REVISION_MISMATCH` nếu lệch.
- Commit `library.jsonl`, `vectors.npy` và `manifest.json` (có phiên bản thư viện, sha256, model, revision).

### 5.2 Hàm chạy trong chat (04.1)
Cần một hàm duy nhất để Hưng gọi trong chat, ví dụ:
```python
def classify_intent(question: str, *, embedder) -> dict:
    """Trả envelope {'base_ranking': ..., 'resolution': ...}, đúng dạng decide_intent_route của Huyền đang nhận."""
```
Yêu cầu:
- Không đọc file mỗi lần gọi: nạp thư viện và vector **một lần**, giữ trong RAM.
- Dùng lại embedder của backend (`get_embedding_service`), không nạp thêm một bản BGE-M3 thứ hai.
- Thuần đọc: không ghi DB, không gọi mạng.
- Trả đúng envelope mà `_confidence_and_route` / `_validated_resolution` của Huyền đang nhận (`ranking_policy`, `score_type`, `runtime_enabled`, `explicit_evidence`, `unresolved_requests`, `component_labels`). Đổi tên nhãn thì báo Huyền cùng lúc.
- Có test: 1 câu cho mỗi nhãn tầng 1, chạy với embedder giả (vector cố định), để test không cần tải mô hình.

### 5.3 Đo lại (run04)
- Chạy với BGE-M3 thật trên bộ test riêng và bộ test kín.
- Báo các số sau:
  - độ chính xác top-1 theo từng nhãn;
  - ma trận nhầm lẫn;
  - số câu OUT_OF_SCOPE bị đưa vào nhánh trả lời (mục tiêu đề xuất: 0);
  - độ trễ mỗi câu sau khi mô hình đã nạp (p50, p95).
- Chỉ tiêu đề xuất, nhóm chốt: top-1 ≥ 90% trên bộ test kín; p95 ≤ 500 ms trên máy demo.

## 6. Không làm
- Không đổi code chat (`live_research.py`, `market_research.py`, `b1_answering/**`). Hưng nối ở 05.1.
- Không ghi vector vào DB production.
- Không dùng bộ test để chỉnh luật rồi báo số trên chính bộ đó.

## 7. Bàn giao
- Một commit trên `nhan-sprint-501`: bảng nhãn v2 (file JSON thay cho `docs/sprint5/intent-labels.v1.json`), thư viện v2, hàm `classify_intent` kèm test, báo cáo run04.
- Đề xuất hạn: bảng nhãn v2 chốt với nhóm trước 15/11; thư viện, hàm và run04 trước 18/11, để Hưng còn thời gian nối vào chat trong tuần 2 (16–22/11).
