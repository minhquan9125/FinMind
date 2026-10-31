# Bản đồ source và danh sách dọn trước mentor review

Rà lại ngày 31/10/2026 trên checkout `reivew`. Báo cáo này phân biệt **đường chạy của ứng dụng**, **module/CLI thử nghiệm** và **dữ liệu sinh ra**. Các file đang bị xóa hoặc sửa trong working tree là thay đổi có sẵn của dự án; lượt rà này không xóa source.

## Đường chạy hiện tại

| Phần | Entry point và dữ liệu | Kết luận khi dọn |
| --- | --- | --- |
| Backend web | `backend/scripts/run-backend.mjs` mở `src.main:app` trên cổng 8000. `src.main` đăng ký router auth, documents, search, market-data, research-chat và hybrid-router. | Giữ `backend/src/api`, `auth`, `core`, `documents`, `market_data`, `retrieval_orchestration`, `vector_retrieval`, `b1_answering` cùng các phụ thuộc của chúng. Tên folder không chứng minh file thừa. |
| Chat `/research` | `frontend/src/pages/research/ResearchChat.jsx` gọi `/api/research/chat/sessions`; backend dùng `PostgresSessionStore`, retriever corpus đã ghim và B1. | Đây là luồng thật; `retrieval_orchestration/web_sessions.py` là luồng file cũ cho test/offline, không phải web default. |
| Giá/tin thị trường | `src.main` dùng `market_lifespan` từ `backend/src/market_data/app.py`; router đọc dữ liệu đã lưu và dùng SDK khi cập nhật. | Không xóa `market_data/app.py` chỉ vì README gốc nói không mở cổng 8001; app chính vẫn import lifespan của file đó. |
| Giao diện đồ thị `/graph` | `frontend/src/pages/graph/api.js` trả `graphFixture` từ `mock.js`. Có backend graph store/CLI nhưng chưa có endpoint đọc graph cho trang này. | Giữ graph code để review WBS, nhưng giới thiệu trang web là **demo fixture**, không tuyên bố event đã hiện trên graph thật. |
| Event News | `event_news.py` và `news_event_extractor.py` chỉ được CLI/test gọi; không thấy import từ `src.main` hay web router. `data/News/stock_news_kg_template.json` hiện không được code đọc. | Xem đây là ba tài sản khác nhau: extractor rule based, extractor batch theo manifest, và template graph. Chưa gộp bằng thao tác chuyển file; phải chốt contract/taxonomy trước. |

## Có thể dọn với rủi ro thấp

| File/nhóm | Bằng chứng | Việc cần làm |
| --- | --- | --- |
| `data_pipeline/annual_reports/OCR_annuals.py.bak` | Bản sao lưu 22 KiB; không có import hay tài liệu gọi đường dẫn `.bak`. | Bỏ khỏi Git sau khi soát diff cần lưu; lịch sử phiên bản đã có trong Git. |
| `package-lock.json`, `.github/package-lock.json` | Hai lockfile rỗng, không có `package.json` cùng cấp. | Bỏ; giữ `frontend/package-lock.json`. |
| `.tmp-review-pages/`, `.tmp-ocr-batch-test-*/` | 39 file thử/review đã bị xóa sẵn trong working tree. | Chỉ chốt phần xóa khi người đang làm xác nhận đây là đầu ra tạm; sửa ignore để test không commit lại. |
| `tmp/*.log` và phần lớn `tmp/` | `tmp/` có 1.605 file được Git theo dõi, khoảng 186 MiB; log/OCR/IR theo lượt chạy. | Giữ script và fixture có test tham chiếu; loại đầu ra sinh tự động sau khi có cách tái tạo. |
| `data_pipeline/ScrapersOHLCV/data/runtime/my-test.json` | Trùng byte với `demo-ohlcv.json`; không thấy tham chiếu tên `my-test.json` trong repo. | Ứng viên bỏ sau khi xác nhận không có người dùng ngoài repo cần tên này. |

## Đừng xóa/gộp vội

| Nhóm | Lý do |
| --- | --- |
| `backend/src/person_role/contract/` và `backend/src/sprint4_runtime/` | Một số Python/schema trùng byte nhưng là bản bàn giao có provenance. `sprint4_runtime` đang được graph/WBS03 dùng; `contracts.py` còn sửa cục bộ. Gộp cần chuyển toàn bộ import, test và cam kết provenance. |
| `backend/src/b1_answering/hoi.py` | Shim CLI còn được README và nhiều test gọi. |
| `backend/src/market_data/app.py` | App web chính dùng `market_lifespan` trong file này. |
| `data/News/stock_news_kg_template.json` | Template chủ dự án đã chuyển vào `data/News/`; giữ như tài sản thiết kế. Nó chưa phải schema runtime của hai extractor hiện có. |
| `models/`, Golden40, `docs/`, `history.md` | Model/fixture và bằng chứng bàn giao có tham chiếu cụ thể. Có thể làm trang hướng dẫn mentor ngắn hơn thay vì xóa lịch sử. |
| `data/references/vietstock/annual_reports/` | Gần 6.000 file OCR và 20 PDF nguồn, khoảng 1,3 GiB. Đây là dữ liệu lớn; chỉ gỡ khỏi Git khi đã lưu nơi khác, đối chiếu manifest/hash và sửa đường dẫn đọc. |

## Các thay đổi đang làm đứt phụ thuộc

- `supabase/migrations/` hiện mất cả 9 migration trong working tree. README, tài liệu pgvector và `backend/scripts/migrate_chat_history.py` cần chúng để dựng hoặc nâng cấp DB. Không chốt xóa nếu muốn người khác clone và dựng lại.
- `data_pipeline/supabase_sink.py` đang bị xóa. Collector tin và OHLCV vẫn nạp file này động; lỗi bị bắt thành cảnh báo, nên đồng bộ Supabase có thể ngừng mà lưu JSON vẫn thành công. Điều này **không chặn mọi chức năng web**, nhưng làm sai luồng pipeline đã mô tả.
- `chunks_thu.json` đang bị xóa. Hai script embedding còn dùng nó làm input mặc định/cố định. Chuyển fixture thì sửa script và hướng dẫn cùng lúc.
- `docs/fireant-event-labeling-10-symbols.md` đang bị xóa nhưng handoff WBS16 vẫn dẫn đến taxonomy này.
- `backend/tests/test_wbs16_event_extractor.py` không collect được: import `parse_dates_extended` và `detect_status_rigorous` không có trong `event_news.py`. `backend/scripts/run_wbs16_extractor.py` cũng gọi constructor với `target_symbols`, trong khi class nhận `as_of`. Đây là lỗi thật của nhánh thử nghiệm, không chứng minh nhánh đó phải bị xóa.

## Tài liệu cần chỉnh trước mentor review

- README gốc mô tả backend chung cổng 8000. `backend/src/market_data/README.md` vẫn hướng dẫn mở app riêng cổng 8001 như đường mặc định cũ.
- `backend/src/retrieval_orchestration/README.md` còn nói lịch sử web lưu file JSON, còn router thực tế dùng Postgres. Tài liệu `notes/POSTGRES_HISTORY.md` mới hơn đã ghi sự thay đổi.
- README gốc kết thúc bằng mục `6.` rỗng và lệnh `py-m uvicorn` sai cú pháp; nên sửa trước khi gửi mentor.

## Kiểm tra đã thực hiện

- `pytest --collect-only -q backend/tests`: **1.129 test được thu thập, 1 lỗi import** ở test WBS16 cũ; chưa chạy toàn bộ backend suite.
- 33 test chọn lọc cho person-role, graph store và batch News pass.
- Frontend Vite build thành công. Có cảnh báo pattern Tailwind trên Windows; chưa kết luận là lỗi cấu hình hay lý do xóa file.

## Thứ tự dọn hợp lý

1. Chốt trạng thái các file đang bị xóa và sửa đường dẫn phụ thuộc tương ứng.
2. Sửa test/CLI event cũ hoặc ghi rõ đó là prototype không nằm trong bộ test mặc định; chọn contract với mentor trước khi gộp extractor.
3. Làm README cho đúng app cổng 8000, Postgres chat và graph fixture.
4. Bỏ `.bak`, lockfile rỗng, log và đầu ra test/OCR có thể tái tạo.
5. Chạy lại backend tests, frontend build và một luồng demo từ máy mới trước khi gửi review.
