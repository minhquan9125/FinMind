# S5-WBS05.1 / 07.2 — nối ý định v2 và Gemini fallback vào Chat (Hưng, 14/11/2026)

Nhánh `hung/intent-router-v2`, dựng trên `backup-demo` `b2c9f1bc`, đã gộp `nhan-intent-v2-integration`.
Bật/tắt bằng `INTENT_ROUTER_V2` (mặc định `true`; đặt `false` để Chat chỉ dùng luật như trước).

## Luồng

1. Sau lời chào, Chat gọi `classify_intent` của Nhân trong luồng riêng. Giới hạn 3 giây; quá hạn hay lỗi thì bỏ qua lượt này. Kết quả đi qua `intent_gate_v2.decide`:
   - `REFUSE`: luật của Nhân nhận ra yêu cầu hạn chế (tư vấn mua bán, dự báo, giá mục tiêu, ngoài lĩnh vực). Chat **từ chối ngay**, trước khi tìm giá, đồ thị hay tin.
   - `DIRECT`: nhãn do luật nhận ra (`EXPLICIT_REQUEST_TYPE`, `MULTIPLE_REQUEST_TYPES`).
   - `FALLBACK`: nhãn mô hình đoán (`CLASSIFIER_PROPOSAL`) hoặc câu còn vế chưa rõ (`UNRESOLVED`). Một OUT_OF_SCOPE đoán ra chưa đủ để từ chối.
   - `NEEDS_CONTEXT`: câu nối tiếp; để phiên hội thoại xử lý như cũ.
2. Luật hiện có (`analyze_live`) chạy như cũ. **Chỉ khi luật phải hỏi lại** thì mới dùng nhãn v2:
   - DIRECT: dùng thẳng.
   - FALLBACK: hỏi Gemini (07.2). Gemini lỗi, quá 8 giây, hết budget của câu hỏi, hỏi lại (`CLARIFY`), lệch mã công ty, hoặc tự đánh giá dưới 0,60 thì **giữ câu hỏi lại như cũ**, không đoán.
   - Nhãn dùng được: OUT_OF_SCOPE thì từ chối; ANALYSIS, PRICE, NEWS với đúng 1 mã thì chuyển sang câu chuẩn ("phân tích FPT", "giá FPT hôm nay", "tin FPT hôm nay") mà luật đã xử lý được. Nhãn khác giữ nguyên câu hỏi lại.
3. Mỗi lượt có `result['intent'] = {label, decision, source: RULES|GEMINI, applied, reason?}` để đo router (13.2).

## Contract fallback (chuyển từ 07.1 của Huyền sang 11 nhãn)

- Gửi đi đúng 3 khóa: `question`, `conversation_scope{company_ticker, period}`, `allowed_labels` (11 mã fallback trong `intent-labels.v2.json` + `CLARIFY`).
- Gemini trả JSON theo schema: `intent_label`, `confidence`, `reason`, `extracted_company`. Không được thêm khóa nào khác. Provider đã từ chối khóa trùng và NaN.
- Ngưỡng tự đánh giá của AI là 0,60, giống 07.1. Đây là điểm tự báo, chưa hiệu chỉnh, chỉ dùng làm cổng, không coi là xác suất.
- Nhánh không do AI chọn: FinMind tự suy từ nhãn, nên không có lỗi nhãn/nhánh không khớp.
- Code: `backend/src/retrieval_orchestration/intent_gate_v2.py`. File 07.1 gốc của Huyền không sửa; nhờ Huyền đối chiếu và review.

## Đã kiểm

- Test: `test_intent_gate_v2.py` (22), `test_intent_router_chat.py` (7); toàn bộ backend 3613 pass, 5 lỗi WBS02 có từ trước.
- Chạy thật với BGE-M3 và Gemini (phần sinh câu trả lời dùng dữ liệu giả):

| Câu | Kết quả |
|---|---|
| fpt tuần sau lên bao nhiêu · có nên mua mbb · thời tiết hôm nay | Từ chối (luật), khoảng 120–230 ms |
| vì sao fpt giảm | Phân tích (luật v2) |
| fpt đang đắt hay rẻ · rsi của fpt · chỉ báo bollinger của mbb ra sao | Gemini PHAN_TICH, 0,9–1,0 → phân tích, khoảng 2 s |
| giá fpt hôm nay · macd fpt đang thế nào | Luật cũ đã xử lý; không gọi Gemini |

## Còn hạn chế

- "fpt định giá thế nào" vẫn ra giá, vì luật cũ và luật v2 đều đọc "giá" trong "định giá" (Nhân).
- "hôm nay ăn gì" bị coi là câu nối tiếp, nên vẫn hỏi lại (Nhân).
- "p/e là gì": chat chưa có nhánh giải thích thuật ngữ khi không có mã công ty.
- Câu kép (MIXED), so sánh nhiều mã và giới thiệu công ty chưa được chuyển nhánh, vẫn theo luật cũ.
- Chưa có bộ kín, nên chưa đo tỷ lệ chọn đúng nhánh.
