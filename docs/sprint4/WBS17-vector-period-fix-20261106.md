# Sửa cấu hình VECTOR và lọc năm BCTN — 06/11/2026

## Nguyên nhân và thay đổi

Kiểm tra PostgreSQL LIVE ở chế độ chỉ đọc xác nhận corpus `b2550a0b-c423-5c50-9b15-6fb6af12e2c6` FROZEN, index `ecfbf20f-b3e0-5077-bd3e-03f0efb95e6d` ACTIVE, đúng model `BAAI/bge-m3@5617a9f61b02` và `vector(1024)`. Có 44.930 chunk hiện hành trên 1.875 tài liệu, tất cả có embedding khác 0. Không cần tạo lại embedding.

Local trước sửa để trống `HYBRID_ROUTER_INDEX_ID`; corpus mặc định `33d33730-0f0a-5274-a7f8-8d32a6be07e8` không tồn tại trên PostgreSQL VPS này. Tài liệu cũ về corpus đó thuộc môi trường khác, không dùng làm bằng chứng tồn tại trên VPS hiện tại.

Lọc kỳ cũ lấy `PDF_PAGE_…` từ section trước khi xét năm BCTN: 1.075 chunk FPT BCTN 2024 tồn tại nhưng bộ lọc `2024` không chọn được chunk nào. Đã thêm `documents/retrieval_period.py`, dùng chung trong dense SQL và metadata/cache hybrid:

- Ưu tiên kỳ có cấu trúc trong reporting_periods hoặc locator.
- Riêng ANNUAL_REPORT, khi thiếu kỳ có cấu trúc, chỉ nhận năm ở cuối tiêu đề có định dạng “Báo cáo thường niên YYYY” hoặc “Annual Report YYYY”. Không lấy năm từ nhãn trang, ngày phát hành, hoặc tiêu đề không đủ rõ.
- Không suy quý từ một BCTN năm. Giữ bộ lọc kỳ chính xác của tài chính và cách dùng ngày tin tức/nhãn tháng cho các loại tài liệu khác.
- Cạnh, chunk, locator, document ID, corpus và embedding không bị sửa. Khi metadata năm không đủ rõ, báo cáo không tự khớp với bộ lọc năm.

Cache chuyển schema từ 2 lên 3 để chặn cache còn lưu nhãn trang. Fingerprint có thêm tiêu đề vì fallback năm phụ thuộc trường này. Kết quả hybrid trả thêm company/period/doc_type lấy từ chính hàng đã xác minh; LiveContentAdapter có thể trả đúng kỳ thay vì null.

## Timeout phát hiện khi kiểm HTTP

Sau khi dựng cache, lần đầu router trả CONTENT_TIMEOUT. Đo riêng cho thấy tạo retriever mới phải đọc, kiểm checksum và dựng BM25 từ cache khoảng 27 giây mỗi lần, gần hết giới hạn CONTENT 30 giây trước khi hoàn tất truy vấn.

Đã thêm `HybridRetriever.load_local_cache()` để nạp local cache trước bước search có timeout. API dùng LRU giới hạn một retriever theo pool, embedder, corpus, index và đường dẫn cache, thay vì tạo lại BM25 cho mỗi router engine. Đổi pool/scope tạo instance mới. Không tăng timeout hoặc bỏ các bước kiểm index/corpus/fingerprint/nguồn: search vẫn thực hiện chúng mỗi lần. Lần nạp lạnh có thể chậm; thay đổi này không phải bằng chứng đạt mục tiêu latency WBS17.

## Cấu hình và cache local

Đã cập nhật cả `.env` và `backend/.env`:

```dotenv
HYBRID_ROUTER_INDEX_ID=ecfbf20f-b3e0-5077-bd3e-03f0efb95e6d
RESEARCH_CORPUS_VERSION_ID=b2550a0b-c423-5c50-9b15-6fb6af12e2c6
```

Giữ cấu hình GRAPH/version/registry đã kiểm trước đó. Bản sao `.env` trước thay đổi nằm trong `backend/.tmp/vector-config-20261106/`, đã xác nhận bị Git ignore; không chia sẻ các file đó vì chứa bí mật.

Đã dựng cache schema 3, kiểm nguồn và hash đủ 44.930 chunk, 53.439.157 byte; cache index và bản sao cùng corpus dành cho research-chat warmup đều nằm trong `.cache` bị Git ignore. Không có PostgreSQL/Neo4j write trong bước này.

Cache là dữ liệu local có thể tái tạo, không commit. Máy khác cần cập nhật hai biến, giữ tunnel, và dựng cache theo corpus. Cache schema 2 của các index khác cũng cần được dựng lại khi dùng code mới; không đổi version để lách kiểm tra. Cache hiện có thời hạn mặc định một giờ; `prepare_cache()`/warmup kiểm và dựng lại khi cần. Tiến trình backend đang chạy cần khởi động lại để nhận code và Settings mới.

## Kiểm chứng

- **155 test offline đạt**: dense API/repository, toàn module vector retrieval, cache, corpus, live adapter, runtime config, warmup và runner WBS17. Test mới thất bại trước sửa cho cache cũ, kỳ hybrid bị thiếu và vòng đời retriever.
- **14 ca SQL PostgreSQL đạt**: năm 2024/2025, title tiếng Anh, trang mang số 2024, ngày phát hành khác năm báo cáo, metadata ưu tiên, không suy quý, tiêu đề mơ hồ, quý tài chính, ngày tin tức, tháng giá và fallback title legacy.
- Mutation làm hỏng regex năm bị ma trận SQL bắt; đã khôi phục đúng byte nguồn và chạy lại 14/14 đạt.
- HTTP thật `/api/search/filtered`, model local và DB thật: FPT/2024 và FPT/2025 mỗi ca trả 3 kết quả, đúng kỳ/tiêu đề và `source_verified=true`; FPT/2001 trả 0.
- HTTP router với câu hỏi rủi ro FPT 2024: VECTOR / LIVE / OK / CONTENT_OK, 5 evidence xác minh nguồn, cả 5 kết quả có period 2024. Đây là kiểm tra vận hành retrieval, không phải chấm mức liên quan hoặc đáp án gold.

Kiểm HTTP sử dụng app thử riêng cổng 8012 với chính router/search production, pool PostgreSQL READ ONLY, không collector, không tạo session hoặc gọi Gemini. Không thay cấu hình tiến trình ứng dụng của người dùng. Lần đo lạnh gồm tải model/cache nên không đưa vào bảng latency chất lượng B1/B2.

Receipt local: `backend/.tmp/annual-period-postgres-20261106-final.json`, `annual-period-cache-20261106.json`, `annual-period-http-FPT*.json`, `annual-period-router-fixed-*.json`. Dữ liệu SQL regression tái lập được bằng:

```powershell
.\backend\.venv\Scripts\python.exe -m backend.scripts.verify_annual_period `
  --output backend/.tmp/annual-period-check-new.json
```

Output phải là file mới. Script chỉ SELECT, trả nonzero nếu một ca sai. Phần WBS17 vẫn cần Huyền duyệt gold, chạy benchmark đầy đủ, E2E và full-load; chưa tự đóng task hoặc đồng bộ review store.
