# Hợp đồng chat với corpus thật — phiên bản 1.1

Cập nhật 23/10/2026. Dùng lại frontend `/research` và API `/api/research/chat/sessions` hiện có. CLI fixture và evidence schema 1.0 tiếp tục phục vụ kiểm thử riêng.

**Cập nhật lưu trữ24/10/2026:** web chat hiện dùng Supabase Postgres theo [POSTGRES_HISTORY.md](POSTGRES_HISTORY.md), không ghi JSON lịch sử mới. Snapshot/auth/revision và nguồn giữ nguyên; mô tả lưu JSON ở các phần lịch sử dưới đây không còn áp dụng cho đường web mặc định.

## Luồng hiện tại

`ResearchChat → SessionStore → LiveResearchService → corpus retrieval → nguồn đã xác minh → B1.complete_retrieval → JSON phiên → giao diện/trích dẫn`.

Mặc định `RESEARCH_CHAT_LIVE=true`, `RESEARCH_RETRIEVAL_BACKEND=hybrid`. Hybrid lấy ứng viên dense và BM25 độc lập trong cùng corpus/phạm vi, rồi RRF hợp nhất. `dense` là tùy chọn chuyển về nhánh vector của Nhân. Không ép PostgreSQL phải chọn HNSW khi planner thấy exact scan phù hợp hơn.

Corpus mặc định `33d33730-0f0a-5274-a7f8-8d32a6be07e8` (v4), index được tra từ corpus; chỉ nhận corpus FROZEN, index ACTIVE, đúng phiên bản BGE-M3. SQL ràng buộc `corpus_documents` theo cả document ID và document hash trước xếp hạng. Reader dùng nguồn release/raw_payloads đã ghim của Vũ, kiểm tra locator và hash; không dùng preview `SOURCE_CHANGED` làm bằng chứng. Không ghi Supabase, không tự ingest hoặc thay vector.

Cache BM25 chứa token/metadata, không lưu đoạn văn/vector/key; file tại `vector_retrieval/.cache/corpus-<UUID>.json`. Tự dựng khi thiếu/hết hạn 60 phút/thay membership, ghi atomic sau khi xác minh đủ nguồn. Lỗi hash/nguồn không bị che bằng fallback. Khóa dựng cache và khóa nạp embedding tách biệt; warm query không bị khóa bởi thao tác dựng cache của chính nó. Source binding được kiểm tra lại khi đọc hit.

## Phạm vi câu hỏi và ngữ cảnh

Chat LIVE có bước chuẩn hóa viết tắt/Telex và điền ngày tra giá rút gọn theo ngữ cảnh đã biết; xem [chuẩn hóa câu nhập](INPUT_NORMALIZATION.md). Lịch sử vẫn giữ câu gõ nguyên bản, evidence không bị chuẩn hóa.

Parser xác định mã, kỳ và chỉ tiêu tài chính đã khai báo trong `live_research.METRIC_ALIASES`, hoặc chủ đề tin tức. Ví dụ: `tiền và tương đương tiền FPT quý 2/2026`, `tin tức FPT tháng 9/2026`. Có thể bổ sung `SSI`, `còn VCB`, `năm 2025`, hoặc chọn `sau`/`trước` khi đang làm rõ lợi nhuận. `/moi` xóa phạm vi hội thoại, giữ ngân sách đang dùng. Giá hiện tại và tin mới đi qua `MARKET_LOOKUP` dùng dịch vụ web hiện có; xem [hợp đồng nguồn đang cập nhật](MARKET_CHAT_CONTRACT.md). Câu giá lịch sử/PDF chưa hỗ trợ không tự biến thành câu tài chính cũ.

Nhận LNST/LNTT mà không coi chúng là ticker; “lời/lãi bao nhiêu” được làm rõ trước/sau thuế. `PARENT_NET_PROFIT` là chỉ tiêu LNST thuộc cổ đông công ty mẹ, tách khỏi `PROFIT_AFTER_TAX` và khỏi phạm vi báo cáo `PARENT`. “Báo cáo riêng” chỉ được xác nhận từ trường `Phạm vi:` của nguồn; chữ “riêng quý” không chứng minh phạm vi báo cáo.

Quý và năm có thể cách nhau trong câu. Khi thiếu năm, `_pending_quarter` được giữ trong ngữ cảnh để nhận năm ở lượt sau; đổi công ty/chỉ tiêu hoặc `/moi` không mang quý chờ sang câu mới. “Cả năm 2025” chủ động bỏ quý đang chờ. Kỳ canonical `2025-Q4` cũng có basis riêng quý hoặc lũy kế; nhiều quý/năm mâu thuẫn phải hỏi lại.

“Nguồn đâu”, “xem nguồn” lấy citation và evidence đã lưu của câu trả lời gần nhất cùng mã/kỳ/chỉ tiêu/phạm vi/basis/publisher. Không truy vấn hoặc gọi Gemini lại. `/moi` cắt tham chiếu; không dùng nguồn của câu cũ khác phạm vi. Manifest `response_mode: SAVED_SOURCE_REFERENCE`, `model_returned: null`, model gốc nằm trong `referenced_model`; trace ghi `saved_source_reference`. Snapshot nguồn được kiểm tra hash/binding từ dữ liệu đã lưu, không xác nhận lại trạng thái DB ở thời điểm hỏi nguồn.

Mã mới viết thường trong vị trí mã (ví dụ `tổng tài sản vic năm 2025`) thay phạm vi công ty cũ, kể cả khi corpus chưa có mã đó. Từ trong tên chỉ tiêu không được coi là ticker. Với tin tức, CafeF/FireAnt và ngày được ghi thành bộ lọc; hybrid áp dụng trước cả dense lẫn BM25.

Kỳ tài chính dùng `YYYY`/`YYYY-Qn`, so khớp chính xác; ngày cuối quý của chỉ tiêu tại thời điểm chuyển thành quý tương ứng. Kỳ tin dùng năm/tháng/ngày. Không tự ghép kỳ hoặc tính số mới. Khi yêu cầu hợp nhất/riêng hoặc lũy kế, nguồn phải phù hợp nhãn đó; UNKNOWN không được coi là đã xác nhận. Nội dung/đơn vị của nguồn giữ nguyên, không khôi phục độ chính xác đã bị làm tròn trong corpus.

## Làm rõ có lựa chọn và giới hạn vòng lặp

`clarifications.py` khai báo các nhóm nợ/nợ vay, lợi nhuận, doanh thu, tài sản, vốn và dòng tiền. “Nợ” không tự đồng nghĩa với nợ vay: menu tách tổng nợ phải trả, nợ ngắn hạn, nợ dài hạn và nhóm nợ vay. Nợ vay tiếp tục hỏi ngắn/dài hạn. Chỉ tiêu mới dùng đúng code trong financial mapping, không cộng hoặc tự suy ra tổng.

Mọi nhánh cần làm rõ đều đi qua policy chung. Scope giữ `_pending_metric` và `_clarification_state` gồm lựa chọn, chữ ký các slot và số lượt chưa tiến triển; không lưu thêm raw câu hỏi trong state. API result thêm `clarification_options: [{id,label,reply,description,metric_code?}]`. Chọn bằng nút, số thứ tự hoặc tên ngắn (“tổng”, “thuần”, “điều lệ”, “đầu tư”...) chỉ dựa trên menu đang chờ, giữ mã/kỳ đã cung cấp. Menu nhiều chỉ tiêu dùng đúng các chỉ tiêu trong câu hỏi; nguồn tin/phạm vi báo cáo có lựa chọn riêng.

Lần đầu hỏi cụ thể, lần lặp sau giải thích cách chọn. Sau 3 lần làm rõ cùng nội dung không có tiến triển, hoặc 6 lượt đổi nhóm mơ hồ nhưng không bổ sung slot cốt lõi, result chuyển `CLARIFICATION_STALLED` với hướng dẫn và menu còn hiệu lực, không tiếp tục câu hỏi chung vô hạn. User vẫn chọn được để tiếp tục; `/moi` xóa state. Thiếu công ty/kỳ hoặc giá trị chưa hỗ trợ vẫn không được tự đoán. Đây là cơ chế thoát vòng lặp, không phải bảo đảm hiểu mọi ngôn ngữ tự nhiên.

Frontend hiện có render nút chọn ngay trong bubble; chỉ menu của tin nhắn cuối được bấm, khóa trong lúc gửi. Reply gửi qua cùng sendMessage/revision/auth; không tạo frontend hoặc API riêng. Các lượt còn mơ hồ/stalled không gọi retrieval/Gemini. State được lưu JSON và tiếp tục sau khi mở lại phiên.

## Evidence 1.1 và B1

Pack gồm `schema_version: "1.1"`, `query_id`, `data_version: {kind: "INDEX", id: UUID}`, `corpus_version_id: UUID`, `retrieval_backend`, `items`.

Mỗi item có `evidence_id` (chunk UUID), `chunk_id`, `source_id` (document UUID), `source_type` BCTC/NEWS, `title`, `passage`, `source_sha256` (documents.sha256), `content_sha256` (SHA-256 chính xác của passage), `source_verified: true`, locator DB nguyên bản, và score có loại `COSINE_SIMILARITY` hoặc `RRF`. Hai loại điểm không thay thế nhau. Locator chứa source_table/source_id/row_keys/section/reconstruction; không tạo page_number/table_id giả. B1 kiểm tra cấu trúc, hash nội dung và binding locator; không bật B3.

B1 nhận câu hỏi đã ghép đủ mã/kỳ/chỉ tiêu từ ngữ cảnh. Trong chế độ LIVE, prompt `b1-grounded-v7` cho Gemini diễn đạt câu trả lời tiếng Việt tự nhiên. Mỗi claim có `text`, `evidence_ids`, `support_quotes: [{evidence_id, quote}]`; chỉ `quote` phải nguyên văn nguồn. Backend kiểm tra đoạn trích tồn tại, số liệu/đơn vị/ký hiệu mã và phạm vi báo cáo trong ngữ cảnh được trích. Với tài chính, số liệu phải thuộc dòng đúng `metric_code`, không dùng dòng chỉ tiêu khác trong cùng chunk. Với tin, tiêu đề là căn cứ cùng quote; riêng snapshot feed có thêm ngày đăng đã ràng buộc trong metadata. Không dùng nội dung thân bài ngoài quote để chứng minh số khác. Không tự làm tròn, quy đổi hoặc tính số mới; cho đổi dấu phân nhóm số nguyên có nhiều nhóm hàng nghìn.

Để tin tức không chép cả bài vượt trần output 2.048 token, prompt chỉ nhận 3 đoạn xếp hạng đầu (tối đa 3.500 ký tự/đoạn), tạo tối đa 2 claim, mỗi claim 450 ký tự/1 nguồn/1 quote tối đa 300 ký tự. Chọn đoạn đầu vẫn giữ nguyên chuỗi nguồn để bind quote vào passage gốc; không thay hash nguồn. Schema/prompt/validator cùng áp giới hạn này. Đây là tóm tắt một phần nguồn truy xuất, không khẳng định bao phủ mọi tin của kỳ. Không tăng giới hạn token hoặc tự retry Gemini.

Nếu Gemini trả JSON/claim không qua kiểm tra, với một mã + một kỳ + một chỉ tiêu BCTC đã có dòng nguồn đúng, B1 có thể dựng câu một dòng từ giá trị gốc đó và gắn citation `[1]`. Fallback chỉ đọc đúng dòng `metric_code`, yêu cầu header khớp mã/kỳ và basis/phạm vi được hỏi; không diễn giải từ dòng khác, không thêm đơn vị. Manifest giữ trạng thái model và trace ghi `draft_bound_to_source_row` cùng lý do validator từ chối claim Gemini. Các lỗi provider/timeout vẫn báo lỗi dịch vụ, không giả là Gemini trả lời. Các trường hợp scope rộng hoặc thiếu dòng khớp tiếp tục báo chưa đủ bằng chứng.

Citation giữ nguyên locator/content hash và thêm `citation_number`; câu trả lời hiển thị `[1]`, `[2]`, phần mở nguồn dùng cùng số. `answering.cautions` giữ thông tin đơn vị/phạm vi chưa xác minh trong metadata; cấu hình hiển thị mặc định ẩn các ghi chú đó khỏi draft. Đây là kiểm tra cấu trúc, đoạn trích và số liệu, **không phải kiểm chứng ngữ nghĩa đầy đủ**: diễn giải sai quan hệ, phủ định hay nhận xét định tính vẫn cần đánh giá riêng. Không gọi thêm LLM để kiểm chứng. `answering.manifest` ghi `extractive_claim_check: false`, `support_quote_check: true`, `numeric_source_check: true`; các thành phần B3 vẫn tắt. Fixture giữ prompt/validator trích nguyên văn cũ để tương thích các ca mẫu.

Gemini chỉ được khởi tạo khi có `GEMINI_API_KEY` và `B1_GEMINI_FREE_TIER_CONFIRMED=1`. Giữ limits hiện tại: input 16.384 token, output 2.048, timeout provider 600 giây, tối đa 20 generation/65.536 token cộng dồn trong vòng đời service. Không tự reset khi gửi câu mới hoặc `/moi`. Xác nhận Free Tier là cấu hình người vận hành, không phải bảo đảm từ API về billing.

Thiếu cấu hình Gemini: vẫn tìm nguồn thật, hiển thị **nguồn ứng viên**, không giả là Gemini đã trả lời. No data, lỗi nguồn, timeout và lỗi phụ thuộc là các nhánh riêng; không dùng lỗi hệ thống để kết luận không có dữ liệu. Timeout retrieval mặc định 120 giây, chờ toàn lượt session bao gồm cả retrieval và provider. Embedding chạy ngoài event loop.

## Warmup lúc khởi động

Mặc định backend mở API rồi chạy warmup ở nền: nạp BGE-M3 và một embedding khởi tạo, rồi xác minh/nạp BM25 của corpus khi dùng hybrid. Tái sử dụng cache còn hợp lệ; chỉ dựng lại cache thiếu/hết hạn/thay phiên bản hoặc fingerprint. Cache sai checksum/nguồn không được bỏ qua. Dùng đúng retriever/model/cache instance của chat, không tạo một bản warmup riêng. Không gọi Gemini, không tạo phiên hay lưu câu hỏi thử, không ghi Supabase.

Console báo `Application startup complete` trong khi warmup chạy. Sau đó có log `Research warmup started` và `Research warmup ready`. Đăng nhập/API khác dùng được trong thời gian warmup; yêu cầu chat có thể cùng chờ model/cache và dùng tài nguyên đã nạp. Thời gian query DB và Gemini vẫn còn. `/api/health` thêm `research_warmup.status` là `warming`, `ready`, `failed` hoặc `disabled`. Khi lỗi/timeout, backend vẫn chạy các chức năng khác, log mã lỗi an toàn; chat thử lại theo luồng hiện hành. Timeout không thể cưỡng bức dừng thread đang nạp model, nhưng khóa model ngăn nạp trùng.

Cấu hình tùy chọn: `RESEARCH_WARMUP_ENABLED=0` để tắt; `RESEARCH_WARMUP_TIMEOUT_SECONDS=180` là mặc định (hợp lệ trên 0 và tối đa 600 giây). Đổi cấu hình cần restart backend. Warmup dùng RAM model ngay khi startup, một lần mỗi tiến trình; không giảm thời gian xử lý phía Gemini.

## Cấu hình trình bày số tiền

`b1_answering/config/answer_style.json` phiên bản `b1-answer-style-v1`: `default_financial_currency: "VND"` và `show_source_cautions: false`. Đây là quy ước hiển thị do người vận hành cấu hình khi nguồn chưa nêu đơn vị; không xác nhận nguồn đã chứng minh VND. Có thể để currency chuỗi rỗng để chỉ dùng đơn vị nguồn. Thay config cần restart backend.

Lớp `application/presentation.py` chạy sau grounding: giữ nguyên claims/support_quotes/citations/cautions và số gốc; chỉ dựng lại `answering.draft`. Caution không nối vào chat bubble khi cấu hình false. `answering.presentation.unit_annotations` ghi `origin: SOURCE` hoặc `CONFIGURED_DEFAULT`, kèm `source_unit_verified`; `manifest.answer_style_version` ghi phiên bản. Khi nguồn ghi rõ triệu/tỷ VND hoặc USD/EUR, hiển thị đúng đơn vị đó, không ép về VND cơ sở hoặc đổi số. Tỷ lệ/EPS/NEWS không được tự gắn VND từ mặc định tiền tệ. Trường hợp sau định dạng không còn nội dung trả lời không được báo DRAFT_READY rỗng.

## Lưu phiên và giao diện

HTTP/auth/revision/khóa file/giới hạn 2 MiB và 2.000 messages giữ hợp đồng cũ. `execution_mode` là LIVE hoặc FIXTURE. `metadata.live_context` giữ phạm vi do backend phân tích, không nhận scope/owner từ client. GET và resume của phiên LIVE chỉ đọc/copy transcript, không query corpus hoặc gọi Gemini lại. Phiên fixture cũ giữ nhãn cũ; lượt gửi mới qua service LIVE cần phạm vi hợp lệ, không lấy evidence mẫu làm nguồn thật.

Giao diện giữ phần trả lời ngắn trong bong bóng chat; nguồn ứng viên được mở riêng trong `<details>`, không đổ cả chunk nhiều chỉ tiêu vào nội dung trả lời. Citation `[1]` khớp nguồn trong `<details>`; hiển thị vị trí section/row_keys và link bài gốc nếu có. URL chỉ HTTP(S), không credentials; nội dung render bằng text React. Trang so sánh mock vẫn mang nhãn dữ liệu mẫu.

## Cấu hình và chạy

Khởi động bằng `Chay-FinMind.cmd` như trước, đăng nhập và vào `/research`; sau đổi cấu hình phải restart backend. Các biến tùy chọn:

```dotenv
RESEARCH_CHAT_LIVE=true
RESEARCH_RETRIEVAL_BACKEND=hybrid
RESEARCH_CORPUS_VERSION_ID=33d33730-0f0a-5274-a7f8-8d32a6be07e8
RESEARCH_RETRIEVAL_TIMEOUT_SECONDS=120
B1_GEMINI_FREE_TIER_CONFIRMED=1
# GEMINI_API_KEY: cấp qua môi trường bí mật của backend, không commit key thật.
```

Model đã tải ở `vector_retrieval/.cache/huggingface` được tự nhận và dùng offline khi đủ file; biến HF_HUB_CACHE tường minh vẫn được ưu tiên. Máy khác phải có model/dependency và kết nối DB đúng; cache/model không nằm trong Git.

## Bằng chứng và giới hạn

Đã chạy ASGI trên Supabase thật với embedding BGE-M3 cục bộ cho cả dense/hybrid: câu tiền FPT có 1 đoạn đúng mã chỉ tiêu, tin FPT có 5 đoạn, kỳ 2099-Q4 trả NO_DATA. Mọi passage khớp hash; mở/resume lịch sử không generation lại. Provider của smoke là giả để thử contract B1, **0 cuộc gọi Gemini thật**; không coi là kiểm chứng Gemini hay Golden40.

Lượt đo 23/10: dense 9,14s cho câu đầu gồm nạp model; hybrid 27,54s cho câu đầu gồm dựng cache, lượt tin tiếp theo 3,26s. Đây là mẫu nhỏ trên máy/DB hiện tại, không phải cam kết latency. PDF, phép tính và chất lượng đủ 40 đáp án chưa được nghiệm thu ở task nối này.

Lượt kiểm tra cuối không đặt HF_HUB_CACHE, dùng khả năng tự nhận cache model của web: hybrid có nguồn đúng hash, câu đầu 47,77s gồm nạp model/dựng cache, lượt tin 3,25s; kỳ không có dữ liệu 1,84s. Thư mục lịch sử/cache của smoke được tạo riêng trong vùng tạm, không dùng lịch sử thật.

Test chính: `backend/tests/test_live_research*.py`, `test_corpus_hybrid.py`, `test_live_chat_factory.py`, `test_embedding_local_cache.py`; frontend `citationView.test.js`, `chatApi.test.js`. Smoke thật chỉ chạy khi `RUN_LIVE_RESEARCH_SMOKE=1`; mặc định test offline không gọi DB/Gemini. RED đã quan sát: chưa có live adapter, locator 1.1/RRF bị từ chối, kỳ năm dùng sai phép so, follow-up mất ngữ cảnh khi đưa vào provider; cùng các ca đó đã GREEN sau sửa. Không tạo commit theo yêu cầu người dùng; không gọi ECC worker/sub-agent.

Kiểm chứng cuối: 32 test tập trung cho phần mới đạt; B1 chạy 131 test (2 skip); fixture orchestration 125 đạt; hybrid 76 đạt; frontend 13 test đạt và Vite build thành công. Line coverage bằng stdlib trace của `live_research.py` là 88,9%, `live_contract.py` là 90,9% (không phải branch coverage). Không cài thêm dependency để đo.

Lượt ASGI cuối có thêm câu tin CafeF ngày 29/09/2026: cả dense/hybrid trả 5 hit đúng publisher và đúng hash, cùng hai câu có nguồn và một ca NO_DATA trước đó; tổng 2 test integration đạt. Hybrid cold 38,88s và câu CafeF kế tiếp 3,26s. Không dùng kết quả này để chấm Golden40.

Toàn bộ `backend/tests`: 337 passed, 2 skipped, **1 lỗi tồn tại từ trước** ở `test_json_ingest::test_financial_json_to_pages_statement_drops_none_values`, còn kỳ vọng `isa1:` trong khi formatter chuẩn hóa thành `ISA1`. `history.md` đã ghi cùng lỗi từ trước; json_ingest/mapping/test đó không bị sửa trong task này. Không đánh dấu toàn bộ suite xanh.
