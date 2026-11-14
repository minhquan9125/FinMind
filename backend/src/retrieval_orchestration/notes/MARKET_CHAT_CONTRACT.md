# Chat với giá và tin đang cập nhật

Cập nhật 23/10/2026. Dùng trang `/research` và API chat hiện có; khởi động lại backend sau khi cập nhật mã nguồn rồi gửi câu hỏi mới. Tin nhắn đã lưu giữ nguyên kết quả cũ.

## Phiên bản mới nhất — hỏi thẳng bài và trả lời có bối cảnh

Không cần hỏi danh sách tin trước. `Cho tôi biết chi tiết về: <tiêu đề>` hoặc `tóm tắt <đoạn nội dung>` được nhận là truy vấn bài NEWS, lấy feed của mã rồi chọn bài khớp tiêu đề/nội dung trong tối đa10 bài nguồn trả. Không có bài khớp rõ thì báo `ARTICLE_NOT_FOUND`, không lấy bài đầu thay thế hoặc chuyển sang hỏi chỉ tiêu tài chính. Không dùng các mốc thời gian trong tiêu đề/nội dung làm bộ lọc ngày đăng. USD/EUR/UBND/CTCP/TNHH không bị coi là ticker.

Trong hội thoại, khớp theo title trước, rồi theo `claims[].text → evidence_ids` đã lưu, sau đó theo độ phủ từ có ngưỡng và khoảng cách giữa hai ứng viên. Nội dung chép lại từ câu trả lời được nối đúng bài nếu đã khớp rõ; trường hợp còn mơ hồ vẫn chọn bài. Không tự chọn bài cũ duy nhất nếu user đang hỏi một tiêu đề mới khác. Không thêm URL tùy ý hoặc bỏ kiểm tra snapshot.

Prompt `b1-grounded-v7` tách tóm tắt 1–2 ý/bài và chi tiết 3–4 ý khi nội dung đủ: sự việc mới, người/đơn vị liên quan, mốc cần làm và bối cảnh/quy mô/tiến độ. Gộp các ý đã kiểm tra dưới từng tiêu đề, không chỉ một câu viết lại title. Với feed có body: tối đa4 claim,600 ký tự/claim,2 quote/claim,600 ký tự/quote. Đây là trần chấp nhận nội dung đúng; prompt ưu tiên ngắn gọn. Corpus NEWS không có snapshot body vẫn giữ2claim/450text/1quote300. Trần2048 outputtoken không đổi, không tự sinh lại khi lỗi.

Binding có thể tìm tối đa2 đoạn nguyên văn cùng bài để chứng minh các số/mã ở vị trí cách xa nhau; không ghép thành quote giả. Quote thật dài quá giới hạn có thể được rút thành các đoạn thật ngắn hơn rồi revalidate. Chặn quote không có trong bài, nguồn khác, số không có trong nội dung; trace lưu trước/sau. Không gọi đây là kiểm chứng ngữ nghĩa B3. Các quy tắc mục này thay mô tả giới hạn cũ ở các mục lịch sử bên dưới. Bằng chứng mới nhất: `.agent-state/ARTICLE_INTENT_CHECKPOINT.md`.

## Bổ sung sau kiểm thử hội thoại ngày 23/10/2026

Giá hiện gọn: `Giá FPT ngày 23/10/2026: 57,000 VND.` Không hiện giờ lấy, citation số hoặc thẻ nguồn giá. Ngày/giờ nguồn, freshness, snapshot và citation nội bộ vẫn lưu trong JSON. Giao diện ẩn nguồn PRICE kể cả với bản ghi trước thay đổi này.

Giữ mã và loại tra cứu khi hỏi tiếp `còn hôm qua`, `hôm kia thì sao`, `hôm 22/10/2026`, `còn hôm 21/10/2026`, `ngày 20/10/2026 thì sao` hoặc ISO `2026-10-19`. Ngày tương đối tính theo Việt Nam. Ngày sai phải hỏi lại và giữ ngữ cảnh giá để nhận ngày sửa; ngày tương lai không gọi nguồn. Giá ngày cũ là giá đóng cửa đúng ngày yêu cầu; không dùng giá hôm nay hoặc tự chuyển sang phiên liền trước khi không có bar. Nguồn SDK hiện có khoảng lịch sử 180 ngày; không bảo đảm tra được mọi ngày quá khứ.

SDK history ghim rõ `source=kbs`; đã kiểm tra SDK đang cài: lịch sử cổ phiếu KBS chia giá gốc cho 1000. Child phát metadata `price_unit=thousand_vnd`, normalize_history giữ metadata ở từng bar mới. Chỉ history có đơn vị được khai báo mới đổi về VND, không đoán scale của file cũ. Không thay giá trị dùng vẽ chart hoặc sửa crawler cũ.

Hỏi `tin tức FPT hôm nay có gì mới` trả danh sách tiêu đề/ngày và link, không gọi Gemini. Chỉ `tóm tắt`, `tổng hợp` hoặc yêu cầu chi tiết mới tải nội dung bài và chuyển cho Gemini. `Cho tôi biết chi tiết về: <tiêu đề vừa hiện>`, `chi tiết bài 2`, hoặc chọn bài trong menu dùng đúng URL từ snapshot đã xác minh; không tải URL tùy ý do user dán. Có thể nối tiếp từ bản tin từng bị lỗi sinh đáp án. Đổi sang câu tài chính không dùng lại bài cũ.

Nội dung đọc từ endpoint bài FireAnt theo postID, bỏ HTML. Dùng chính client, khóa, cache60s, giới hạn10 request/phút và cách2s của NewsService. Mỗi lượt đọc tối đa2 bài; nếu chỉ vướng spacing thì chờ tối đa2s và thử đúng1 lần, không đợi rồi chạy vượt quota phút. Tải lỗi không dùng tiêu đề/mô tả để giả vờ đã đọc bài. Mỗi body dùng tối đa7000 ký tự, có `content_truncated` trong snapshot; prompt nhận tối đa8500 ký tự/bài. Link của tóm tắt chỉ gồm các bài có citation thực sự dùng; không hiện passage/locator/thẻ nguồn ứng viên cho NEWS. Trích dẫn BCTC giữ giao diện hiện có.

Prompt mới `b1-grounded-v6` phân biệt ngày đăng và ngày sự kiện, hướng dẫn chọn quote chứa đúng ý trong thân bài. Nếu model chọn quote tiêu đề hợp lệ nhưng câu có số/mã ở thân bài, `news_binding.py` có thể gắn lại một đoạn nguyên văn tối đa300 ký tự từ chính bài đã gửi Gemini, khi đoạn đó chứa đủ số/đơn vị/mã được kiểm tra. Không viết lại claim, không thêm nguồn, không sửa quote bịa, không gọi Gemini lần2. Chỉ áp cho snapshot NEWS có body; kiểm tra đầy đủ lại bằng validate_grounded. Trace `article_quotes_bound` lưu original_quote/bound_quote. Đây là binding B1, không phải kiểm chứng ngữ nghĩa B3. Giá trị không có trong bài vẫn bị chặn.

Các quy tắc mới trong mục này thay thế cách trình bày giá/tin mô tả ở phần ban đầu bên dưới. Xem `.agent-state/MARKET_DIALOGUE_CHECKPOINT.md` để biết bằng chứng.

## Cách hỏi

- `Giá cổ phiếu FPT hôm nay là bao nhiêu?`
- `FPT giá hiện tại bao nhiêu?`
- `Tóm tắt tin tức mới hôm nay của FPT`
- `Tin tức mới nhất FPT`
- Thiếu mã sẽ hỏi lại; trả lời `FPT` hoặc chọn mã trong menu. `Còn SSI` giữ loại tra cứu. `/moi` xóa ngữ cảnh.

Giá/tin mới dùng `MARKET_LOOKUP → MarketResearch`. Tin có kỳ lịch sử rõ ràng, ví dụ tháng 9/2026, tiếp tục dùng corpus/hybrid; báo cáo tài chính vẫn dùng corpus và kiểm tra nguồn đang có. Đổi từ hỏi giá sang tài chính không mang ngày giá sang kỳ báo cáo.

## Nguồn và tải hệ thống

`main.lifespan` gắn chính `app.state.live` và `app.state.news` vào chat. Không khởi tạo collector, HTTP client FireAnt hoặc tiến trình SDK thứ hai trong chat. Tra cứu đồng bộ chạy ngoài event loop; không đăng ký viewer, không polling sau câu trả lời. Khóa, backoff, cache 60 giây và hạn mức của các dịch vụ hiện có vẫn áp dụng chung với giao diện giá/tin. Khi nguồn bận, trả `MARKET_BUSY` và `retry_after`, không tự gọi lại để vượt quota.

Giá đọc qua `LiveCoordinator.refresh`, có thể dùng snapshot RAM còn hiệu lực. Chỉ giá overlay được `normalize_quote` xác nhận mới có cơ sở đổi từ nghìn VND về VND bằng Decimal. Giá lịch sử không rõ đơn vị không được tự nhân 1.000. Trả ngày giao dịch và thời điểm lấy dữ liệu, không gọi thời điểm lấy là thời điểm khớp lệnh. Khi chỉ có ngày giao dịch cũ, nói rõ chưa có giá ngày yêu cầu; khi chỉ có cache sau lỗi, hiển thị chưa cập nhật được giá mới. Đây là trả giá tại thời điểm hỏi, không phải stream realtime trong bubble.

Giá được trình bày trực tiếp từ snapshot đã kiểm tra, `response_mode=MARKET_QUOTE`, `gemini=false`; không tốn generation. Tin mới gọi `NewsService.refresh`, nguồn FireAnt công khai hiện có. Không cần API key riêng cho hai nguồn này; phần diễn đạt tin vẫn cần cấu hình Gemini/Free Tier hiện có.

## Ngày tin và phạm vi bao phủ

“Hôm nay” dùng ngày Việt Nam UTC+7 và lọc ngày đăng. Không thay tin cũ thành tin hôm nay; bỏ ngày tương lai hoặc datetime thiếu múi giờ. “Mới nhất” có thể chứa tin ngày trước và giữ ngày đăng thật. Chỉ xét tối đa 10 bài mới nhất nguồn trả, chọn tối đa 3 bài hợp lệ để tóm tắt; không bảo đảm bao phủ mọi tin của doanh nghiệp.

Lấy tin lỗi không được báo là không có dữ liệu. Có cache phù hợp thì giữ ngày đăng thật và cảnh báo lần cập nhật mới thất bại; không có cache phù hợp thì `SYSTEM_UNAVAILABLE`. Yêu cầu nguồn CafeF không được âm thầm thay bằng FireAnt. Tin đúng ngày nhưng không có trong feed trả `NO_CURRENT_NEWS`, không thông báo rằng corpus tài chính thiếu dữ liệu.

## Evidence snapshot 1.2

Pack có `schema_version=1.2`, `data_version.kind=MARKET_FEED_SNAPSHOT`, UUID query và hash của các item. Mỗi item có snapshot canonical, title/passage/hash/locator dựng lại từ snapshot. NEWS dùng URL HTTPS bài FireAnt, ngày đăng, thời điểm quan sát; PRICE dùng mã, provider, ngày giao dịch, thời điểm lấy. Không tạo ID corpus/index/document UUID hoặc locator PDF giả.

`prepare_evidence` kiểm tra lại snapshot, locator, passage, ID và hash toàn pack; chỉnh một phần sẽ bị từ chối. `source_verified=true` trong schema này chỉ có nghĩa binding tới snapshot từ adapter nguồn, được ghi rõ `verification_basis=FEED_SNAPSHOT_BINDING`; không chứng nhận độc lập tính đúng đắn của báo, không phải ingest vào corpus/Supabase. Schema 1.0 fixture và 1.1 corpus giữ quy tắc riêng.

Tin chuyển qua cùng `complete_retrieval`, provider và budget của chat. Prompt `b1-grounded-v5` cho phép diễn đạt gọn; quote phải nguyên văn. Kiểm tra số/đơn vị/mã dựa trên quote và tiêu đề cùng bài; ngày đăng snapshot là metadata được phép dùng. Không bật B3, không tự retry Gemini. Frontend hiện có hiển thị citation số, title, ngày đăng và URL gốc; JSON hội thoại lưu snapshot để mở lại/xem nguồn mà không gọi source hoặc Gemini thêm.

## Kiểm thử

Deterministic: `backend/tests/test_market_research.py` (routing, đơn vị, múi giờ, cache lỗi, quota, hash/locator, Gemini, JSON phiên và source reference). Opt-in mạng: `backend/tests/test_market_research_live.py`; `RUN_MARKET_NEWS_SMOKE=1` kiểm tra feed, thêm `RUN_MARKET_GEMINI_SMOKE=1` cho tối đa một generation. `RUN_MARKET_QUOTE_SMOKE=1` kiểm tra một lượt SDK có khóa độc quyền, bỏ qua nếu collector khác đang sở hữu khóa; không polling. Không in API key hoặc ghi vào folder crawler cũ.
