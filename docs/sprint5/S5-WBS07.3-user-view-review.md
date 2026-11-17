# 07.3 — kiểm thử từ góc nhìn người dùng, bộ riêng

Lần kiểm nghiệp vụ: 16/11/2026 trên nền 1087dc29. Bàn giao lên backup-demo ngày 17/11/2026. Không thay code production.

## Cách tránh lấy code làm đáp án

Một agent riêng không nhận lịch sử hội thoại được giao chỉ yêu cầu nghiệp vụ: giá, số liệu, phân tích, tin, nội dung báo cáo, nhân sự, quan hệ, tổng quan; câu thiếu thông tin phải làm rõ; giữ mã/kỳ và mọi mục tiêu; không tư vấn mua bán/dự báo. Người soạn không đọc code, test cũ, dataset hoặc báo cáo. Bộ 32 câu viết xong và khóa checksum trước khi chạy.

Gold: `docs/sprint5/user-acceptance-073-v1/scenarios.jsonl`, SHA256:
`b9fc8f2eaf509bfb8309b9f64d37f6712532e32c42eb3e11fb23d9b373fbc3e6`.

10 câu rõ, 5 câu mơ hồ, 5 câu nhiều mục tiêu, 4 câu nối tiếp, 6 ca mô phỏng lỗi và 2 ca ngoài phạm vi. Không trùng nguyên văn sau chuẩn hóa khoảng trắng/chữ thường với library/development v2 hiện có. Đây là soạn độc lập bởi AI; không gọi là bộ kín do người dùng/hội đồng giữ kín, vì người điều phối đã từng xem code.

## Thực thi

- Dùng BGE-M3 thật, revision 5617a9f61b028005a4858fdac845db406aefb181, classifier/artifact đang có trên demo, không refit hay ép nhãn bằng encoder giả. Không cấp gold cho classifier.
- Chạy câu hỏi qua LiveResearchService và 07.2 thật. Lượt trước trong nhóm context được chạy trước, lấy scope thực tế để nối lượt sau, không tự điền context từ gold.
- Provider AI được mô phỏng có chủ đích. NORMAL mô phỏng phản hồi đúng theo gold nghiệp vụ để kiểm luồng fallback; không đo accuracy Gemini. Các ca sai nhãn/timeout chỉ tính đã thực thi khi hệ thống thực sự gọi provider.
- Adapter dữ liệu do lượt kiểm này viết mới chỉ ghi nhận query/scope và trả không có dữ liệu; không dùng fixture của Hưng để quyết định kỳ vọng.
- Chỉ kiểm biên định tuyến, bảo toàn mã/kỳ, hỏi lại/từ chối và số lần gọi AI phân loại. Không có dữ liệu trả lời thật, không nghiệm thu số liệu/citation/đủ nội dung câu trả lời.
- Không nối adapter tùy chọn PriceAnalytics, hybrid router và admin-news trong harness này. Vì vậy lỗi quan sát được, đặc biệt giá lịch sử/nhân sự/quan hệ, cần chạy lại stack đủ cấu hình trước khi kết luận là lỗi production.

## Kết quả sau rà soát công cụ chấm

**15 ca qua kiểm tra tại biên định tuyến, 17 ca lệch kỳ vọng nghiệp vụ trong harness.** Đây không phải 15 câu trả lời đã được nghiệm thu nội dung. Số câu được xác minh nội dung factual: 0.

**4/6 tình huống lỗi provider chưa được thực thi**: USER-025/026/027/029, vì hệ thống đã đi truy vấn trước khi gọi fallback. Các lỗi hành vi nghiệp vụ của bốn ca vẫn được giữ trong nhóm FAIL; không dùng NOT_EXERCISED để che lỗi. Hai ca còn lại thực sự đi vào timeout/low-confidence, nhưng lời hỏi lại chưa đúng chủ đề.

Các điểm đáng chú ý:

- USER-003 hỏi RSI của HPG ngày 30/06/2025: scope thực tế trở thành báo cáo năm 2025, mất độ chính xác ngày và lệch nguồn cần cho chỉ báo. Cần đối chiếu trên stack đầy đủ.
- USER-015 câu “Kết quả của FPT thế nào?” chưa rõ mục tiêu/kỳ nhưng được chuyển thành phân tích thị trường thay vì làm rõ.
- USER-017 yêu cầu tin 2024 và RSI ngày cụ thể: đích thị trường quan sát được chỉ là tin. Chưa kiểm được nội dung cuối có đủ cả hai phần.
- USER-022 câu nối tiếp đã có HPG/ngày ở lượt trước nhưng lại hỏi công ty; lưu đầy đủ kết quả lượt trước để Hưng đối chiếu.
- USER-028 cần làm rõ nhân sự hay quan hệ đơn vị, nhưng phản hồi hỏi loại nợ. USER-030 cần làm rõ chức vụ hay tỷ lệ sở hữu, nhưng phản hồi hỏi vốn chủ sở hữu hay vốn điều lệ. Không tính cứ có câu hỏi lại là đáp ứng yêu cầu.
- USER-021/023: classifier trung gian khác gold nhưng đích truy vấn cuối đúng mục tiêu/mã/kỳ, nên không đánh trượt chỉ vì nhãn classifier. Giữ nhãn đó làm thông tin chẩn đoán.
- Với câu nhiều mục tiêu được gửi nguyên văn vào một truy vấn corpus rộng, chưa thể kết luận đã bỏ vế chỉ dựa vào tên endpoint. Đánh dấu nội dung cần review; không chứng minh đủ câu trả lời từ trace.
- USER-002 doanh thu có thể cần làm rõ doanh thu gộp/thuần: giữ nguyên kỳ vọng SERVE của bộ đã khóa và ghi đây là điểm nhóm cần chốt lại về sản phẩm, không sửa gold để tăng điểm sau chạy.

Người soạn gold được cho đọc phản hồi sau chạy để đánh giá tính liên quan của lời hỏi lại (không đọc code, không đổi gold). Annotations lưu riêng trong `observed-review.json`; review sau chạy không bị diễn đạt thành kỳ vọng đã khóa trước chạy.

## File bàn giao

- Excel cuối: `outputs/s5_wbs073_user_view_20261116/run03/S5_WBS07_3_USER_VIEW_20261116.xlsx`.
- `run01`: quan sát BGE-M3 thật gốc và gold không đổi.
- `run03`: chấm lại cùng quan sát sau sửa lỗi công cụ chấm, thêm review phản hồi và mô tả giới hạn cấu hình; không chạy/fit lại model hay thay kết quả thực thi.
- Bộ 38 ca kiểm lỗi kỹ thuật trước đó đã xóa theo yêu cầu người dùng; không gộp tỷ lệ PASS với bộ mới.
- 522 test công cụ và hồi quy intent/chat hiện có qua. Đây không phải tỷ lệ qua của 32 câu nghiệp vụ. Full backend chưa được báo PASS; cổng trước đó dừng ở thiếu PIL.

Chạy lại:

```powershell
$env:PYTHONPATH='backend'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$env:PYTHONIOENCODING='utf-8'
.venv/Scripts/python.exe backend/scripts/run_s5_user_acceptance.py --output outputs/s5_wbs073_user_view_20261116/new-inference
```

Xuất lại cùng quan sát với review lời phản hồi:

```powershell
.venv/Scripts/python.exe backend/scripts/run_s5_user_acceptance.py --replay outputs/s5_wbs073_user_view_20261116/run01 --review docs/sprint5/user-acceptance-073-v1/observed-review.json --output outputs/s5_wbs073_user_view_20261116/new-report
```

Exit 1 của bộ chạy phản ánh còn ca lệch kỳ vọng hoặc tình huống lỗi chưa thực thi; không phải tự động lỗi xuất Excel. Không hoàn tất nghiệm thu đầu ra người dùng chỉ bằng báo cáo này. Cần Hưng chạy lại với adapter/data thực và xử lý các điểm đã nêu.


## Bàn giao 17/11/2026

Trước bàn giao, huyen-test được cập nhật fast-forward lên origin/backup-demo 1fca08df, có thêm thay đổi tích hợp của Hưng. Bộ test/công cụ được kiểm hồi quy trên nền mới; Excel và các quan sát BGE ngày 16/11 vẫn giữ nguyên snapshot 1087dc29. Không dùng kết quả 15/17 này để khẳng định bản demo mới vẫn có đúng các lỗi đó; cần chạy lại bộ nghiệp vụ/full-stack trên nền mới khi nghiệm thu. Chỉ đưa script, test, gold đã khóa, review và bằng chứng cần để tái lập lên demo; không đưa .env, model/cache hoặc Excel tên ngắn trùng lặp.
