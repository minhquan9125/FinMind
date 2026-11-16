# S5-WBS05.1 / 07.2 — nối ý định v2 và Gemini fallback vào Chat (Hưng, 14/11/2026)

Nhánh `hung/intent-router-v2`, dựng trên `backup-demo` `b2c9f1bc`, đã gộp `nhan-intent-v2-integration`.
Bật/tắt bằng `INTENT_ROUTER_V2` (mặc định `true`; đặt `false` để Chat chỉ dùng luật như trước).

## Luồng

1. Sau lời chào, Chat gọi `classify_intent` của Nhân trong luồng riêng. Giới hạn 3 giây; quá hạn hay lỗi thì bỏ qua lượt này. Kết quả đi qua `decide_intent_route_v2` của Huyền (04.2 v2). Hàm này kiểm lại bằng chứng luật trên đúng câu hỏi; kết quả cũ hay sai contract thì bỏ qua lượt này.
   - `REFUSE`: luật của Nhân nhận ra yêu cầu hạn chế (tư vấn mua bán, dự báo, giá mục tiêu, ngoài lĩnh vực). Chat **từ chối ngay**, trước khi tìm giá, đồ thị hay tin.
   - `SEARCH`: nhãn do luật nhận ra (`VERIFIED_V2_RULE`).
   - `NEED_FALLBACK`: nhãn mô hình đoán hoặc câu còn vế chưa rõ. Một OUT_OF_SCOPE đoán ra chưa đủ để từ chối.
   - `ASK_CLARIFICATION` (`CONTEXT_REQUIRED`, kỳ sai…) và `SESSION`: Chat xử lý như cũ.
2. Luật hiện có (`analyze_live`) chạy như cũ. **Chỉ khi luật phải hỏi lại** thì mới dùng nhãn v2. Lúc này gọi lại `decide_intent_route_v2` với mã công ty Chat đã xác minh (đúng 1 mã), `company_required=False`:
   - SEARCH: dùng thẳng.
   - NEED_FALLBACK: hỏi Gemini (07.2), dùng `prepare_fallback_request_v2` và `validate_fallback_response_v2` của Huyền. Gemini lỗi, quá 8 giây, hết budget của câu hỏi, hỏi lại (`CLARIFY`), lệch mã công ty, KET_HOP chưa xác minh thành phần, hoặc tự đánh giá dưới 0,60 thì **giữ câu hỏi lại như cũ**, không đoán.
   - Tuyến `REFUSE` thì từ chối; ANALYSIS, PRICE, NEWS, COMPANY_OVERVIEW với đúng 1 mã thì chuyển sang câu chuẩn ("phân tích FPT", "giá FPT hôm nay"…) mà luật đã xử lý được. Nhãn khác giữ nguyên câu hỏi lại.
3. Mỗi lượt có `result['intent'] = {label, decision, source: RULES|CLASSIFIER|AI, applied, reason?}` để đo router (13.2). `decision` là quyết định của Huyền; `source=AI` là lượt đã gọi Gemini phân loại.
   Trace admin (`research_metrics`) ghi khối này vào `details.intent`; lần gọi Gemini phân loại cũng nằm trong `calls` (model, token) cùng với lần sinh câu trả lời.

## Contract fallback (07.1 v2 của Huyền, từ 16/11)

- Quyết định và kiểm tra là code của Huyền: `intent_routing.decide_intent_route_v2`, `intent_fallback_contract.prepare_fallback_request_v2`, `validate_fallback_response_v2`. `intent_gate_v2.py` chỉ còn phần gọi Gemini (prompt, 8 giây, budget) và rút gọn kết quả cho Chat.
- Gửi đi đúng 3 khóa: `question`, `conversation_scope{company_ticker, period}`, `allowed_labels` (11 mã + `CLARIFY`).
- Gemini trả JSON theo `V2_RESPONSE_JSON_SCHEMA`: `intent_label`, `confidence`, `reason`, `extracted_company`. Không được thêm khóa nào khác. Tuyến do server tính, kỳ giữ nguyên từ request.
- Ngưỡng tự đánh giá của AI là 0,60. Đây là điểm tự báo, chưa hiệu chỉnh, chỉ dùng làm cổng, không coi là xác suất.
- AI không gỡ được yêu cầu hạn chế mà luật đã thấy (`RESTRICTED_LABEL_CONFLICT`).

## Đã kiểm

- Test: `test_intent_gate_v2.py`, `test_intent_router_chat.py` (dùng classifier thật của Nhân với encoder giả, để contract của Huyền kiểm cùng bằng chứng luật như khi chạy thật), `test_s5_huyen_v2.py`, `test_research_metrics_pipeline.py` (trace).
- 16/11: `classify_intent` thật (BGE-M3) qua `decide_intent_route_v2`: 9 câu mẫu ra đúng loại quyết định (từ chối, luật, fallback, cần ngữ cảnh). Chưa gọi lại Gemini thật sau khi đổi sang contract của Huyền; schema gửi Gemini giống hệt bản đã chạy thật 14/11.
- Chạy thật với BGE-M3 và Gemini (phần sinh câu trả lời dùng dữ liệu giả):

| Câu | Kết quả |
|---|---|
| fpt tuần sau lên bao nhiêu · có nên mua mbb · thời tiết hôm nay | Từ chối (luật), khoảng 120–230 ms |
| vì sao fpt giảm | Phân tích (luật v2) |
| fpt đang đắt hay rẻ · rsi của fpt · chỉ báo bollinger của mbb ra sao | Gemini PHAN_TICH, 0,9–1,0 → phân tích, khoảng 2 s |
| giá fpt hôm nay · macd fpt đang thế nào | Luật cũ đã xử lý; không gọi Gemini |

## Sửa thêm luật v2 của Nhân (review 14/11, Hưng sửa theo yêu cầu)

Sửa trong `intent_v2_rules.py` và `intent_v2_classifier.py` của Nhân; test ở `backend/tests/test_intent_v2_review_fixes.py`.

| Câu | Trước | Sau |
|---|---|---|
| fpt định giá thế nào / fpt đang đắt hay rẻ | PRICE / mô hình đoán | ANALYSIS (luật) |
| fpt có đáng đầu tư không / có nên đầu tư vào mbb / mbb bao giờ tăng lại | ANALYSIS hoặc đoán | OUT_OF_SCOPE (luật) |
| hôm nay ăn gì | CONVERSATION, `NEEDS_CONTEXT` | mô hình đoán, `PROPOSED`, nên Gemini quyết (NGOAI_PHAM_VI) |
| doanh thu fpt 2025 và tin tức mới về fpt | NUMERIC, mất vế tin | MIXED [NEWS, NUMERIC] |

- Chỉ câu nối tiếp do luật nhận ra mới chờ ngữ cảnh. CONVERSATION do mô hình đoán thì giữ `PROPOSED`.
- Tách theo "và" chỉ khi vế sau mở đầu bằng tin tức. Bản rộng hơn đã làm tách sai 8 câu mẫu ("đánh giá tín hiệu từ giá và khối lượng…"), nên đã bỏ.
- Kiểm lại: 580 câu thư viện và phát triển không câu nào đổi nhãn; `check_s5_intent_v2_fixes.py` 0 lỗi; test v2 của Nhân 183/183. Không fit lại classifier, không đổi vector hay nhãn chuẩn.

Phía chat: "định giá" không còn bị luật chat đọc là giá; nhãn COMPANY_OVERVIEW mở hồ sơ công ty ("fpt là công ty gì").

## Còn hạn chế

- Câu kép (MIXED) đã nhận đúng thành phần, nhưng chat chưa trả lời cả hai vế; hiện theo luật cũ, thường chỉ một vế.
- "vn-index hôm nay": Gemini xếp GIA, nhưng chat chỉ chuyển nhánh khi có mã công ty, nên vẫn hỏi lại.
- "p/e là gì": chat chưa có nhánh giải thích thuật ngữ khi không có mã công ty.
- Chỉ báo kỹ thuật (RSI, MACD…) vẫn do mô hình đoán. Gemini xử lý đúng, nhưng mỗi câu tốn khoảng 2 giây. Muốn nhanh hơn thì cần thêm câu mẫu và fit lại (Nhân).
- Chưa có bộ kín, nên chưa đo tỷ lệ chọn đúng nhánh.
