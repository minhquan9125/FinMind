# S5-WBS08.1 — Chuẩn bị chuỗi giá theo mã doanh nghiệp

## Phạm vi và thiết kế

Chuẩn bị mẫu từ dữ liệu PostgreSQL hiện có, không tải giá mới, không sửa DB hoặc giao diện. Khoảng yêu cầu đóng hai đầu: 2026-01-01 đến 2026-10-29; ngày đầu/cuối thực tế lấy từ từng mã. Chọn cả 10 mã hiện có, không chỉ nhóm Golden cũ. Lưu toàn bộ nến trong khoảng và bản tổng hợp để truy lại kết quả.

Nguồn chính là public.price_bars nối companies, raw_payloads, ingestion_jobs và sources. File OHLCV phục vụ chart dùng nguồn khác và không được trộn vào mẫu DB. Bảng DB hiện có price_scale=1000, is_adjusted=false; nguồn ENTRADE đang PENDING. Mức biến động là thay đổi giá đóng cửa, chưa điều chỉnh cổ tức/chia tách và không phải tổng lợi nhuận đầu tư.

## Hợp đồng triển khai

Tạo duy nhất script backend/scripts/prepare_s5_price_series.py và test backend/tests/test_s5_price_series.py. Dùng thư viện chuẩn, asyncpg và cấu hình có sẵn; không thêm dependency. CLI --start YYYY-MM-DD --end YYYY-MM-DD --out DIRECTORY đều bắt buộc. Output mới, từ chối ghi đè thư mục đã tồn tại. Không in hoặc lưu DSN, mật khẩu, username, IP, payload gốc.

Tách hàm thuần summarize(rows, start, end) cho test offline. rows là list dict, ngày ISO string, Decimal hoặc chuỗi cho giá; UUID là chuỗi. Mỗi dòng gồm symbol, company_id, company_name, trade_date, price_id, payload_id, price_scale, is_adjusted, open, high, low, close, volume, source_uri, source_sha256, job_id, source_id, source_name, approval_status. Đầu vào rows gồm toàn bộ lịch sử các mã, không chỉ khoảng mẫu. Đầu ra JSON-serializable dict gồm requested_start, requested_end, summaries và bars. bars chỉ trong khoảng mẫu, sắp theo symbol/date, mọi Decimal xuất chuỗi. summaries chứa từng symbol kể cả mã không có phiên trong khoảng, available_first/last/count, first_date/last_date/session_count, first_price_id/last_price_id, first_close/last_close, price_scale, is_adjusted, change, change_percent và reason. Tính Decimal(last-first), phần trăm = (last-first)/first*100, làm tròn ROUND_HALF_UP 0.01; giữ nguyên giá gốc, không nhân/chia thêm 1000. Khi không đủ 2 phiên hoặc giá đầu bằng 0: change/change_percent=null với reason rõ ràng. Không dữ liệu: ngày/giá null, count=0. Không ngầm lọc dòng lỗi.

Từ chối khoảng ngày đảo, trùng symbol/date, giá không hữu hạn hoặc âm, OHLC vô lý, volume âm/null, thiếu ID hoặc liên kết provenance cần thiết, price_scale không dương, hoặc trộn scale/is_adjusted trong chuỗi mẫu một mã. Dòng không thuộc khoảng vẫn dùng coverage; không cần kiểm tra giá của phần ngoài khoảng. Nguồn approval PENDING được giữ, không từ chối và không gọi là approved. Source SHA là metadata DB, không tuyên bố đã xác minh hash payload.

CLI đọc qua asyncpg.connect(get_settings().database_url, statement_cache_size=0), transaction readonly=True/isolation=repeatable_read, timeout có giới hạn. SELECT rõ cột, LEFT JOIN để không che bản ghi thiếu nguồn. Không lấy raw_payloads.payload. Kết nối đóng trong finally. Dùng transaction_timestamp() cho snapshot_at. summary.json chứa report không có bars; series.json chứa bars; cả hai allow_nan=False. Không chạy DB khi import hoặc khi chạy test. Chỉ in số mã/số phiên/output.

## WBS và kiểm chứng

Một job ổn định s5081-series: worker triển khai; worker khác thiết kế test; coordinator kiểm tra code trước chạy unittest offline; worker review code và receipt; coordinator duyệt, tích hợp, chạy xuất DB thật. Ngân sách chung 6 inference calls, tối đa 3 attempts/stage, 2 rounds, 900 giây. Nếu gateway không hoạt động, ghi nhận ngoại lệ coordinator cùng nguyên nhân, không nhận candidate lỗi hoặc tuyên bố ECC pass.

Test bắt buộc: sắp ngày, khoảng đóng hai đầu, coverage toàn bộ, Decimal/rounding, thiếu dữ liệu, một phiên, zero base, mã trộn, provenance giữ nguyên; lỗi duplicate, scale/basis mix, OHLC, thiếu provenance và date đảo. Cuối cùng đối chiếu số phiên, giá đầu/cuối và biến động bằng SQL độc lập trên DB read-only; kiểm tra JSON/ID nguồn. Báo cáo nghiệm thu tiếng Việt và SQL chạy pgAdmin sẽ được tạo từ kết quả thực tế, không từ số mẫu hardcode.

## Rủi ro và giới hạn

Không khẳng định đã đọc từng dòng toàn dự án. Chỉ sơ đồ module và schema liên quan đã khảo sát. Không xác minh nhà cung cấp bên ngoài, giá điều chỉnh hoặc lịch nghỉ sàn. Số phiên là số ngày có bản ghi; không suy ra đủ lịch giao dịch. Giữ nguyên sửa dở graph_store.py và tài liệu S5-WBS03.3 hiện có. Không commit/push.
