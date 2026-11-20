# S5-WBS08.1 — Chuẩn bị chuỗi giá theo mã doanh nghiệp

Người phụ trách: Thái Quốc Hưng. Sprint 5, S5-G06. Ngày thực hiện: 10/11/2026.

## Kết quả dữ liệu

Đã chuẩn bị mẫu **2.012 phiên thuộc 10 mã** từ PostgreSQL FinMind hiện đang cấu hình cho backend. Snapshot lúc **18:53:23 ngày 10/11/2026, giờ Việt Nam**. Toàn bộ lịch sử DB có **21.365 bản ghi giá**. Các truy vấn và đối chiếu chạy trong transaction `READ ONLY`, `REPEATABLE READ`; không cập nhật DB.

Khoảng yêu cầu: **01/01/2026–29/10/2026**, bao gồm hai đầu. Khoảng thực tế cho cả 10 mã: **05/01/2026–29/10/2026**. Ngày cuối được chốt theo dữ liệu đang có, không giả lập giá tháng 11. Khoảng này được chọn để bàn giao mẫu năm 2026 có cùng mốc so sánh; chưa phải khoảng thời gian do người dùng chỉ định riêng.

| Mã | Số phiên | Đóng cửa đầu | Đóng cửa cuối | Thay đổi giá | Thay đổi (%) |
|---|---:|---:|---:|---:|---:|
| BID | 203 | 35.5800 | 33.8500 | -1.7300 | -4.86 |
| CMG | 203 | 31.6800 | 18.9000 | -12.7800 | -40.34 |
| CTG | 203 | 34.9600 | 30.7000 | -4.2600 | -12.19 |
| ELC | 203 | 22.7600 | 11.2000 | -11.5600 | -50.79 |
| FPT | 203 | 85.1900 | 52.7000 | -32.4900 | -38.14 |
| ICT | 188 | 17.0100 | 17.1000 | +0.0900 | +0.53 |
| ITD | 200 | 12.7600 | 10.3000 | -2.4600 | -19.28 |
| MBB | 203 | 20.3000 | 19.7000 | -0.6000 | -2.96 |
| TCB | 203 | 22.8200 | 22.3500 | -0.4700 | -2.06 |
| VCB | 203 | 56.6300 | 57.2000 | +0.5700 | +1.01 |

Đơn vị giá giữ nguyên DB, `price_scale=1000`: ví dụ FPT 85.1900 tương ứng 85.190 đồng/cổ phiếu. Chênh lệch tuyệt đối trong bảng cùng đơn vị với giá. Phần trăm tính `(đóng_cửa_cuối - đóng_cửa_đầu) / đóng_cửa_đầu × 100`, làm tròn hai chữ số thập phân. Đây là biến động giữa hai đầu khoảng, không phải độ biến động thống kê của lợi suất ngày.

`is_adjusted=false` trên toàn bộ mẫu. Chưa điều chỉnh cổ tức, chia tách hoặc quyền; mức thay đổi không phải tổng lợi nhuận đầu tư. Số phiên đếm ngày có bản ghi theo mã. ICT và ITD có ít phiên hơn nhóm còn lại; chưa đối soát lịch giao dịch để kết luận đó là dữ liệu thiếu hoặc ngày không phát sinh giao dịch.

## Độ phủ toàn bộ DB

| Mã | Ngày đầu có dữ liệu | Ngày cuối | Tổng phiên |
|---|---|---|---:|
| BID | 02/01/2018 | 29/10/2026 | 2.200 |
| CMG | 02/01/2018 | 29/10/2026 | 2.200 |
| CTG | 02/01/2018 | 29/10/2026 | 2.200 |
| ELC | 02/01/2018 | 29/10/2026 | 2.200 |
| FPT | 02/01/2018 | 29/10/2026 | 2.199 |
| ICT | 15/01/2020 | 29/10/2026 | 1.674 |
| ITD | 02/01/2018 | 29/10/2026 | 2.195 |
| MBB | 02/01/2018 | 29/10/2026 | 2.199 |
| TCB | 04/06/2018 | 29/10/2026 | 2.100 |
| VCB | 02/01/2018 | 29/10/2026 | 2.198 |

## Truy nguồn và giới hạn

Chuỗi liên kết đã kiểm tra: `companies.company_id` → `price_bars.company_id`; `price_bars.payload_id` → `raw_payloads.payload_id`; `raw_payloads.job_id` → `ingestion_jobs.job_id`; `ingestion_jobs.source_id` → `sources.source_id`.

Nguồn của toàn bộ mẫu là **ENTRADE**, loại `MARKET_DATA`, trạng thái **PENDING**, `base_url` chưa có. URI nguồn lưu dạng `MÃ.json#price_history`; đây là locator trong dữ liệu nhập, không phải đường dẫn web công khai. Báo cáo không đổi hoặc xác nhận phê duyệt nguồn.

Mỗi nến trong `series.json` có `price_id`, `company_id`, `payload_id`, `job_id`, `source_id`, `source_uri`, `source_sha256`, `source_name` và `approval_status`. Đối chiếu toàn bộ **2.012/2.012** phiên với phần tử cùng ngày trong JSON `raw_payloads.payload`: OHLC và volume khớp. Không thiếu liên kết nguồn, không trùng `(symbol, trade_date)` trong mẫu. Kiểm tra số phiên, ngày đầu/cuối và giá đầu/cuối giữa bảng tổng hợp và chuỗi xuất đều đạt.

Ví dụ FPT:

- Giá đầu 05/01/2026: `price_id=8ca42561-f9fb-5743-a7c1-9d434550b8ec`, đóng cửa `85.1900`.
- Giá cuối 29/10/2026: `price_id=27e23465-7e25-5994-b070-304d5be9ba08`, đóng cửa `52.7000`.
- Cùng `payload_id=495eba42-3de2-571c-af70-a1652ce18d85`, locator `FPT.json#price_history`, nguồn ENTRADE.
- SHA nguồn do DB lưu: `5c84a2f969d78649a40adb1d02c72444e6cc211b74c572cf68d864cf1110757e`.

Đã giữ SHA nguồn như metadata, **chưa tính lại SHA payload hoặc xác minh file nhập ban đầu**. `sha256.json` chỉ kiểm tra tính toàn vẹn các file bàn giao được tạo ở lượt này. Đối chiếu raw payload chứng minh khớp dữ liệu nhập trong DB, không chứng minh giá đúng với nhà cung cấp bên ngoài.

## File bàn giao và cách đối chiếu

Các đường dẫn sau tính từ gốc repository:

- `outputs/sprint5/S5-WBS08.1-db-snapshot/summary.json`: phạm vi yêu cầu, snapshot, độ phủ, mốc đầu/cuối, số phiên, giá, thay đổi và ID hai giá đầu/cuối theo mã.
- `outputs/sprint5/S5-WBS08.1-db-snapshot/series.json`: toàn bộ 2.012 nến trong khoảng, sắp theo mã/ngày, kèm nguồn.
- `outputs/sprint5/S5-WBS08.1-db-snapshot/verification.json`: kết quả đối chiếu nguồn và dữ liệu; số đếm, trạng thái nguồn và SHA file SQL.
- `outputs/sprint5/S5-WBS08.1-db-snapshot/sha256.json`: SHA-256 của ba file JSON trên.
- `outputs/sprint5/S5-WBS08.1-db-snapshot/acceptance.json`: kiểm lại SHA và đối chiếu cả 10 mã với hàm `documents.price_queries.query_price` hiện có; giá đầu/cuối, chênh lệch, phần trăm và đúng hai `price_id` đều khớp.
- `docs/sprint5/S5-WBS08.1-pgadmin.sql`: hai truy vấn tương ứng để chạy trong pgAdmin Query Tool của DB FinMind; SELECT trong transaction chỉ đọc, kết thúc bằng ROLLBACK.

Mở file SQL, chọn đúng kết nối FinMind đang dùng cho backend và chạy nguyên file. Hai truy vấn trả bảng tổng hợp rồi chuỗi nến. Nếu đổi khoảng mẫu, sửa hai mốc trong **cả hai** CTE `bounds`. Kết quả về sau có thể đổi nếu DB được cập nhật; bộ JSON bàn giao giữ snapshot nói trên.

## Các luồng dự án đã xác định

- Frontend React/Vite: trang doanh nghiệp, biểu đồ Lightweight Charts, nghiên cứu và graph; backend chung FastAPI tại `backend/src/main.py` đăng ký auth, documents, search, market data, research chat, hybrid router, graph viewer và ingestion/admin jobs.
- PostgreSQL: dữ liệu doanh nghiệp, nguồn/job/payload, giá, báo cáo và chỉ tiêu tài chính, documents/chunks/index/corpus/pgvector, tài khoản/quyền, truy vấn/evidence/citation/evaluation. Có schema riêng `research_chat` và `graph_metadata`.
- Chat nghiên cứu: chuẩn hóa câu hỏi/ngữ cảnh, định tuyến, truy xuất dense + BM25/RRF, kiểm chứng nguồn, B1 trình bày và Gemini khi cấu hình cho phép. Truy vấn giá lịch sử có nhánh SQL xác định trong `documents/price_queries.py`.
- Graph: các module review và store riêng; không dùng graph để thay giá đã lưu trong `price_bars`.
- Dữ liệu giá cho giao diện hiện đi qua `FileMarketDataRepository`, snapshot crawler và cache/runtime vnstock/KBS. Luồng này khác chuỗi giá ENTRADE trong PostgreSQL; mẫu WBS08.1 chỉ dùng DB, không trộn hai nguồn.
- Tài liệu README cũ có phần còn ghi lịch sử chat dạng file hoặc backend giá riêng cổng 8001; entrypoint và ghi chú LIVE cập nhật mô tả backend chung và lịch sử PostgreSQL. Khi làm task sau cần ưu tiên code và schema đang chạy.

Đã khảo sát cấu trúc và các điểm tích hợp liên quan; chưa kiểm tra từng dòng code toàn repository hoặc chạy toàn ứng dụng.

## Trạng thái kiểm chứng công cụ

Dữ liệu và SQL đã được coordinator kiểm chứng trên DB thật như trên. Đã chạy `..\.venv\Scripts\python.exe -B -m pytest tests/test_price_queries.py -q -p no:cacheprovider` tại thư mục `backend`: **6 passed**, một cảnh báo dependency. Đối chiếu qua `query_price` trên DB thật cho cả 10 mã cũng đạt. Hai lần thử chạy test bằng unittest trước đó không đúng cách tổ chức pytest của bộ test; chúng không được tính là kết quả đạt.

WBS `hung-s5-wbs081-series`, job `s5081-series` quản lý riêng đề xuất công cụ xuất lại dữ liệu. Vòng đầu nhận implementation `kiro/glm-5`, QA `groq/openai/gpt-oss-120b`; fixed-argv test lỗi import `backend.core`. Candidate cũng có SQL dùng tên cột không khớp schema thật, nên chưa được nhận hoặc tích hợp.

Vòng hai nhận implementation từ `kiro/glm-5`, nhưng QA trả `Gateway HTTP status 413.`; fallback đang `queued` do các route còn lại không khả dụng/quarantined. Trạng thái quan sát lúc checkpoint: `phase=testing`, `round=2`, `status=queued`; chưa có receipt test vòng hai hoặc review PASS. Budget **4/6 calls**, **45.614 tokens được báo cáo**, 900 giây toàn workflow, không tăng budget, không có reservation chưa settled. Không tự giải phóng quarantine hoặc đổi request đã phát. Candidate vòng hai vẫn nằm riêng trong `.agent-state/managed/hung-s5-wbs081-series/candidates/s5081-series/round-2/`.

Ngoại lệ coordinator: xuất snapshot và báo cáo bằng SQL chỉ đọc, đối chiếu raw payload và hàm truy vấn giá hiện có để hoàn thành phần chuẩn bị dữ liệu. Script xuất phục vụ lượt này nằm trong `.agent-state/export_s5_price_snapshot.py`, không tích hợp thành chức năng ứng dụng. **Phần dữ liệu đã có bằng chứng trực tiếp; công cụ mới chưa đạt cổng ECC và chưa được nghiệm thu.** Việc có snapshot đúng không thay thế kiểm chứng code.
