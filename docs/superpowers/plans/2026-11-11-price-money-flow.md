# Phân tích giá và dòng tiền — Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for task-by-task execution, with the project's required ECC manager workflow for implementation, independent testing and review. Do not dispatch workers or apply changes merely because this plan exists.

**Goal:** Lưu được dữ liệu giao dịch theo mã/ngày, cập nhật giá có đối soát, và cung cấp phân tích giá–volume–khối ngoại có số liệu truy nguồn.

**Architecture:** Tái sử dụng collector Vnstock dùng chung và PostgreSQL hiện có. Bổ sung bảng dòng tiền ngày; giữ bảng giá và API cũ. Bộ phân tích đọc DB, tính bằng quy tắc xác định, rồi hiển thị trong trang doanh nghiệp hiện có.

**Tech Stack:** Python, asyncpg, PostgreSQL, FastAPI, React/Vite; dùng thư viện đang cài, không thêm dependency cho MVP.

**Spec:** [Khung đã chốt](../../sprint5/S5-price-flow-design.md), [kết quả khảo sát](../../sprint5/S5-price-flow-readiness.md), [phạm vi chuyển nguồn](../../sprint5/S5-source-transition-plan.md). Hợp đồng API dự thảo cũ tại `docs/sprint5/S5-price-analysis-implementation.md` chỉ bao phủ giá/volume và dòng tiền thiếu; plan này mở rộng phần lưu dòng tiền. Khi triển khai phải ghi quyết định thay thế hợp đồng cũ, không sửa request ECC đã phát.

**Status:** Kế hoạch để review, chưa triển khai. Các lựa chọn kỹ thuật dưới đây là đề xuất của coordinator, chưa phải tính năng đã có hay bằng chứng nguồn đạt production.

## Hiện trạng đã xác minh

| Dữ liệu/luồng | Hiện có | Phần cần làm |
|---|---|---|
| Giá và volume trong `price_bars` | 21.365 phiên, 10 mã; mới nhất 29/10/2026 | Cập nhật sau khi đối soát nguồn/cơ sở giá |
| Khối ngoại mua/bán và `total_value` | JSON thô của FPT, snapshot 07/10/2026 | Lưu theo từng ngày, phân biệt trong phiên/cuối ngày |
| Tiền khối ngoại mua/bán | Chưa có trường đã kiểm chứng | Trả `null`, chỉ bổ sung khi có nguồn cung cấp thực tế |
| Collector backend | Batch/cache/quota dùng chung; hiện theo người xem | Theo dõi đủ 10 mã dù không có người xem; nối vào DB |
| DB sink crawler | Tái sử dụng importer; có chế độ raw payload ghi đè theo file | Payload tham chiếu từ dòng tiền phải bất biến |
| Vnstock 4.0.9/KBS | Đã trả dữ liệu trong thử nghiệm 11/11 | Không coi đó là cam kết hỗ trợ lâu dài |
| Kiểm chứng công thức | SQL/Python khớp 10 mã × 21 phiên | Đưa thành acceptance cho module thật |

Evidence: `outputs/sprint5/price-analysis-build-20261111/{db-before.json,baseline.json,sql_baseline.py}`; `outputs/sprint5/vnstock-recheck-20261111-085400/assessment.md`.

## Global Constraints

- Ngày giao dịch theo Asia/Ho_Chi_Minh; dùng ngày nguồn, không lấy ngày máy để thay ngày quote.
- `volume`, `foreign_buy_volume`, `foreign_sell_volume`: số cổ phiếu. Trường tiền chỉ gán đơn vị VND sau kiểm chứng mapping nguồn; lưu metadata phạm vi giá trị giao dịch.
- Khối lượng ngoại ròng = mua − bán. Không lấy giá đóng cửa nhân volume để giả làm tiền giao dịch hoặc tiền khối ngoại.
- Thiếu trường là `null`; 0 chỉ hợp lệ khi nguồn thực sự gửi 0 trong một quan sát giao dịch hợp lệ. Quote trước mở cửa có OHLC/volume 0 không trở thành một phiên hoàn chỉnh.
- Không cộng các snapshot tích lũy trong cùng ngày. Mỗi mã/ngày/nguồn chỉ có một bản quan sát hiện hành; các ngày khác nhau cùng tồn tại.
- Thời điểm sau giờ đóng cửa không tự chứng minh số liệu đã được nguồn xác nhận cuối ngày. Dùng trạng thái `after_close` + `pending_reconciliation` nếu thiếu bằng chứng chốt phiên.
- Không trộn ENTRADE và KBS hoặc chuỗi khác cơ sở điều chỉnh/đơn vị mà chưa đối soát. Không ghi đè giá cũ hàng loạt để ép dữ liệu khớp.
- Không đổi `sources.approval_status`/`is_enabled`, key, account, SDK hay lựa chọn nhà cung cấp trong plan này. Nguồn PENDING phải được hiển thị rõ.
- Giữ thay đổi có sẵn của user ở `backend/src/graph/graph_store.py`; không commit/push, cài scheduler hệ thống hoặc khởi động service ngoài phạm vi được cho phép.
- Test offline không gọi nguồn/DB thật. Test migration và persistence chạy trên DB/schema thử nghiệm; kiểm chứng DB dự án là bước riêng, có giao dịch và số liệu trước/sau.

## Hợp đồng lưu dữ liệu đề xuất

Tạo `public.daily_market_activity`, khóa `(company_id, trade_date, source_id)`; FK tới companies/sources/raw_payloads. Không thêm cột ngoại vào `price_indicators` vì đây là dữ liệu quan sát, không phải chỉ báo tính toán.

| Nhóm | Cột |
|---|---|
| Định danh | `company_id`, `trade_date`, `source_id` |
| Quan sát | `volume`, `total_value_vnd`, `foreign_buy_volume`, `foreign_sell_volume`, `foreign_buy_value_vnd`, `foreign_sell_value_vnd` |
| Phạm vi | `volume_basis`, `value_basis`; mặc định `unknown` nếu chưa xác minh khớp lệnh/thỏa thuận |
| Chất lượng | `observation_status` (`intraday`/`after_close`), `quality_status` (`pending_reconciliation`/`validated`), `source_updated_at`, `fetched_at` |
| Truy nguồn | `payload_id`, `revision`, `updated_at` |

Các giá trị không âm hoặc NULL; kiểu số hữu hạn và có giới hạn phù hợp bigint/numeric; không chấp nhận bool thay số. Không lưu net vào DB khi đã tính được từ hai trường gốc. Bật RLS theo các bảng market hiện có, không mở policy công khai.

Payload tham chiếu phải có hash nội dung và ID bất biến. Nhập lại cùng nội dung là idempotent; nội dung sửa tạo payload mới, giữ payload cũ. Bản đến muộn không thay bản mới hơn. Số tích lũy giảm bất thường không bị nhận âm thầm: giữ bản trước, lưu/ghi lý do đối soát; không tự xem đây là correction hợp lệ.

Không tạo company/source tự động từ ký hiệu tùy ý trong quote. MVP lưu 10 mã của dự án: BID, CMG, CTG, ELC, FPT, ICT, ITD, MBB, TCB, VCB; xác nhận mapping company_id khi thực thi.

## Review Focus

1. Ngày mới giữ lại ngày cũ; snapshot tích lũy không bị cộng nhiều lần — PF02/PF04.
2. Pre-open 0, NaN, ngày lễ và dữ liệu sau đóng cửa chưa chốt không bị diễn giải thành phiên đầy đủ — PF01/PF03.
3. Raw payload không bị sửa tại chỗ làm thay đổi bằng chứng của ngày cũ — PF02.
4. Không có người xem, DB lỗi, API restart và nguồn 429 vẫn bảo toàn khả năng thu thập/replay — PF03/PF04.
5. Giá mới khác cơ sở, benchmark lệch ngày, và thiếu chuỗi ngoại làm kết quả thiếu rõ ràng, không tạo số hoặc nhận định giả — PF05/PF06/PF07/PF08.

## WBS và thứ tự

`PF01 → PF02 → PF03 → PF04`; `PF05` khảo sát được ngay, chỉ ghi giá sau cổng đối soát. `PF06` xây công thức độc lập từ baseline; `PF07` ghép các phần đã đạt; `PF08` hiển thị và nghiệm thu.

### PF01 — Chuẩn hóa dữ liệu dòng tiền từ quote

**Goal/risk:** Có bản ghi định kiểu, không nhầm lượng cổ phiếu với giá trị tiền hoặc dữ liệu 0 trước mở cửa.

**Files:** Create `backend/src/market_data/activity.py`, `backend/tests/test_market_activity.py`, `backend/tests/fixtures/market_activity.json`. Context: `validation.py`, mẫu KBS đã lưu và mapping trường đã xác minh; không gửi credentials hay cả cây scraper.

**Interface:** `normalize_activity(envelope, *, symbol, source_name, now, session_status) -> dict`. Envelope có `fetched_at`, đúng một row của mã; trả ngày nguồn, các trường lưu DB, trạng thái và cảnh báo. `session_status` lấy từ lịch sàn hiện có; thiếu lịch thì không tự xác nhận phiên.

- [ ] QA tạo fixture hợp lệ từ snapshot FPT 07/10: mua 368405, bán 515600, `total_value` 105048970000; assert ròng lượng là −147195, tiền mua/bán ngoại NULL. Fixture thể hiện `value_basis=unknown` đến khi kiểm chứng phạm vi.
- [ ] Viết test đỏ cho thiếu trường so với zero thực, kiểu bool, NaN/Infinity/âm, sai mã/ngày/múi giờ, duplicate rows, pre-open zero và ngày lễ.
- [ ] Implement parser hẹp, giữ validator giá hiện có; không bỏ kiểm tra OHLC để nhận quote 0.
- [ ] Chạy `.venv/Scripts/python.exe -B -m unittest backend.tests.test_market_activity -v`; expected PASS, không I/O trên import.

### PF02 — Lưu lịch sử ngày và payload bất biến

**Goal/risk:** Dữ liệu ngày có truy nguồn và không bị ghi đè mất lịch sử.

**Files:** Create `supabase/migrations/20261111000100_daily_market_activity.sql`, `backend/src/market_data/activity_store.py`, `backend/tests/test_market_activity_store.py`; modify `backend/scripts/ingest_market_news_to_supabase.py`. Ngoại lệ 4 file vì migration, persistence và tích hợp importer là cùng một hợp đồng lưu; không sửa sink/news hoặc các bảng giá ở job này.

**Interfaces:** `async upsert_activity(conn, record, *, company_id, source_id, payload_id) -> str`, kết quả `inserted/updated/unchanged/needs_reconciliation`. Mở rộng `store_payload(..., *, immutable=False)` giữ hành vi mặc định cũ; đường dòng tiền truyền `immutable=True` dù crawler sink đang dùng `STABLE_PAYLOAD_IDS=True`. `apply_live` dùng transaction cho raw provenance và daily record, giữ response/latest-snapshot contract cũ.

- [ ] Test đỏ: ghi 07/10 rồi 08/10 vẫn còn hai ngày; gửi lại một quan sát không tăng revision; gửi snapshot mới cùng ngày thay bản hiện hành chứ không cộng dồn.
- [ ] Test payload A sau khi nhận B vẫn giữ nguyên hash/nội dung; transaction lỗi rollback cả daily/provenance; dữ liệu đến muộn/counter giảm không lùi bản hiện hành.
- [ ] Migration tạo constraints/FK/index/RLS; không sửa/drop dữ liệu cũ. Xác nhận thiết kế nullable và default bằng PostgreSQL thử nghiệm.
- [ ] Chạy `.venv/Scripts/python.exe -B -m unittest backend.tests.test_market_activity_store -v`; thêm DB round-trip có assert thật trong schema thử nghiệm, gồm rerun migration và rollback. Không dùng mock SQL làm bằng chứng migration hoạt động.
- [ ] Kiểm regression importer và DB sink; xác minh `immutable=False` giữ hành vi caller cũ. Không áp migration lên DB dự án trước review.

### PF03 — Thu thập dùng chung dù không có người xem

**Goal/risk:** Không mất dữ liệu ngày vì không có người mở trang hoặc DB tạm lỗi.

**Files:** Modify `backend/src/market_data/live.py`, `backend/src/market_data/app.py`, `backend/src/market_data/repository.py`; create `backend/tests/test_market_activity_collector.py`. Ngoại lệ 4 file vì gắn lịch chạy, bộ đệm bền và lifecycle vào cùng collector; không tạo SDK process thứ hai.

**Interfaces:** Thêm tùy chọn `tracked_symbols=()` và `snapshot_sink=None` vào LiveCoordinator, default giữ nguyên hành vi/tests hiện có. Collector lấy hợp của mã theo dõi và người xem, khử trùng lặp, dùng lock/quota/batch hiện có. Callback nhận envelope đã được chấp nhận, không gọi HTTP/DB trong khóa collector. App khởi tạo 10 mã đã map DB và tiêu thụ bản ghi qua async pool.

- [ ] Lưu atomically bản quan sát hợp lệ mới nhất theo mã/ngày trong `.agent-state/market-data/daily-quotes/symbol-<MÃ>/<YYYY-MM-DD>.json` trước khi ghi DB. Không ghi vào file crawler lịch sử từ backend. Có marker/hash để nhận biết bản nào đã nhập, không xóa file trong nghiệm thu MVP.
- [ ] Ghi DB theo batch tối đa một lần/60 giây bằng đồng hồ monotonic, gộp các quan sát cùng ngày. Kiểm soát lỗi DB riêng với lỗi nhà cung cấp; retry giữ bản local và không chiếm quota nguồn bằng việc fetch lại không cần thiết.
- [ ] Giữ polling/giới hạn/quy tắc lịch hiện có. Khi chuyển ngày, lưu được cả ngày cũ và ngày mới; khi hết phiên không gán `validated` chỉ vì đến giờ. Nếu không có snapshot chốt thì ghi rõ thiếu.
- [ ] Test 0 người xem vẫn thu đủ 10 mã trong phiên; nhiều người xem không tăng số batch; DB outage rồi hồi phục; khởi động lại còn bản replay; holiday/closed không auto gọi nguồn; callback lỗi không biến thành success đã lưu DB.
- [ ] Chạy `.venv/Scripts/python.exe -B -m unittest backend.tests.test_market_activity_collector backend.tests.test_market_data_live backend.tests.test_market_data_auth_lifespan -v`.

### PF04 — Nạp lại dữ liệu có thật và phục hồi phần chưa nhập

**Goal/risk:** Nạp được snapshot cũ/local backlog, không bịa lịch sử ngày đã mất.

**Files:** Create `backend/scripts/replay_market_activity.py`, `backend/tests/test_market_activity_replay.py`. Context PF01/PF02 và path contract PF03; không sửa file thuộc các job trước.

**Interface:** CLI `--input <file-or-folder> [--apply]`, mặc định dry-run; báo observed/inserted/updated/rejected/missing và thời gian dữ liệu. Dùng parser/persistence chung. Cho phép replay lại an toàn, không fetch nguồn hoặc tự đọc cả ổ đĩa.

- [ ] Test dry-run không ghi; apply hai lần không nhân đôi; lỗi/thiếu mã không tạo company; file sai ngày/NaN/symbol bị từ chối có lý do.
- [ ] Nạp snapshot07/10 ở trạng thái intraday, không biến thành số cuối ngày. Các audit10/11/11/11 chỉ nhập khi kiểm được envelope/hash/source/date; quote0 trước mở cửa không tạo phiên hoàn chỉnh.
- [ ] Báo rõ ngày không có dữ liệu. Không thể tạo 20 phiên khối ngoại từ một snapshot; backfill xa hơn cần nguồn thực sự có lịch sử và quyền truy cập tương ứng.
- [ ] Chạy `.venv/Scripts/python.exe -B -m unittest backend.tests.test_market_activity_replay -v`; rehearsal trên DB thử nghiệm trước dry-run DB dự án.

### PF05 — Đối soát và cập nhật chuỗi giá

**Goal/risk:** Bổ sung giá mới mà không làm sai lợi suất vì đổi nguồn/điều chỉnh.

**Files:** Create `backend/scripts/reconcile_market_prices.py`, `backend/tests/test_market_price_reconciliation.py`, fixture `backend/tests/fixtures/price_basis_cases.json`. Tái sử dụng importer hiện có qua interface, không sửa importer ở job này.

**Interface:** `compare_price_series(existing, candidate) -> dict` gồm matched/different/missing, scale, adjustment, source và kết luận `compatible/unresolved`. CLI mặc định dry-run, xuất diff; `--apply` chỉ cho tập đã có receipt đối soát đạt. Input là chuỗi có nguồn được lấy qua đường collector hiện có, không gọi SDK song song không kiểm soát.

- [ ] Test nhận diện chênh1000 lần, adjustment khác/unknown, lệch ngày/volume, duplicate và nguồn khác; số gần nhau không tự chứng minh compatible.
- [ ] Lấy cửa sổ giao nhau của cả10 mã; lưu diff đầy đủ và giải thích cơ sở giá. KBS lịch sử, quote VND và DB scale1000 phải được đối chiếu riêng.
- [ ] Nếu unresolved: không ghi giá; API tiếp tục dùng chuỗi cũ và báo ngày dữ liệu. Nếu compatible: bổ sung ngày thiếu, giao dịch có kiểm tra counts/hash trước/sau; giữ bản cũ/revision có truy nguồn cho correction được duyệt.
- [ ] Không dùng `apply_prices(... overwrite=True)` trên toàn bộ corpus để vượt cổng đối soát. Chính sách sửa giá cũ chưa chứng minh an toàn thì chỉ cho append ngày mới sau khi compatibility đạt.
- [ ] Chạy `.venv/Scripts/python.exe -B -m unittest backend.tests.test_market_price_reconciliation -v`; đối chiếu SQL sau ghi và chứng minh chạy lại không đổi dữ liệu.

### PF06 — Bộ tính giá, volume và dòng tiền

**Goal/risk:** Kết quả tái tính được, đúng số phiên và không phóng đại coverage.

**Files:** Create `backend/src/market_data/analysis.py`, `backend/tests/test_price_analysis.py`. Input contract từ PF01/PF02/PF05; không DB/nguồn trên import.

**Interface:** `analyze_series(price_rows, activity_rows, benchmark_rows, *, symbol, requested_as_of, today) -> dict`; chỉ dùng các phiên <= requested_as_of. Cửa sổ giá phải đồng nhất nguồn/cơ sở/scale, không có ngày trùng. Decimal cho giá/tiền/lợi suất; số xuất JSON là chuỗi làm tròn HALF_UP4 chữ số khi cần.

| Chỉ tiêu | Công thức/điều kiện |
|---|---|
| Lợi suất1/5/20 | `100*(close_t/close_t-n - 1)`, cần2/6/21 mức giá thực |
| MA20 | Bình quân20 close gồm phiên cuối; thiếu20 thì NULL |
| Volume tương đối | Volume phiên cuối / trung bình20 phiên trước, không gồm phiên cuối; mẫu số0 thì NULL |
| Volume5 phiên | Trung bình5 phiên gần nhất và5 phiên trước đó, nêu đúng phạm vi |
| Biên độ phiên | `100*(high-low)/previous_close` |
| Biến động20 | Độ lệch chuẩn mẫu của20 lợi suất ngày, đơn vị%; không annualize, không gọi là ATR |
| Khối ngoại lượng | Mua, bán, ròng; tổng1/5/20 chỉ khi đủ đúng các phiên và trạng thái/phạm vi tương thích |
| Khối ngoại tiền | Chỉ tính khi cả buy/sell value có thật; hiện tại có thể luôn NULL |
| Giá trị giao dịch | Tổng/bình quân từ actual total_value cùng phạm vi; value_basis unknown phải cảnh báo, không so tỷ lệ với nguồn khác basis |
| Benchmark | VNINDEX cho10 mã HOSE; căn đủ đúng ngày của từng cửa sổ, lệch ngày/thiếu thì NULL |

- [ ] Test đỏ bộ số độc lập: 21 phiên, close100..120 cho return20=20%; volume20 phiên trước=100 và phiên cuối=200 cho tỷ lệ2. Fixture validOHLC; không dùng ngày lịch thay số phiên.
- [ ] Test thiếu0/1/5/20 phiên, metadata sai, NaN/bool/âm, xáo trộn/duplicate, mixedbasis, staleness, volatility so oracle độc lập và volume không tự bị tính thành tiền.
- [ ] Cửa sổ tiền/khối ngoại thiếu bất kỳ phiên hợp lệ nào: tổng kỳ=NULL, kèm required_sessions/available_sessions/missing_dates. Có thể trả latest_observation riêng với giờ lấy và trạng thái; không gọi đó là EOD hay tổng đủ kỳ.
- [ ] Test benchmark đầy đủ/thiếu ngày/close0; lịch không có ngày giao dịch thì không suy từ thứ trong tuần. Tách facts, warnings và nhận xét mô tả; không tạo điểm mua/bán hoặc nguyên nhân tin tức.
- [ ] Chạy `.venv/Scripts/python.exe -B -m unittest backend.tests.test_price_analysis -v` và đối chiếu baseline SQL đã lưu.

### PF07 — API đọc DB và provenance

**Goal/risk:** Người dùng nhận đúng dữ liệu được phép đọc, kèm coverage/ngày/nguồn.

**Files:** Create `backend/src/market_data/analysis_queries.py`, `backend/tests/test_price_analysis_api.py`; modify `backend/src/api/routers/market_data.py`. Đây là chủ sở hữu duy nhất của router trong WBS.

**Interfaces:** `async get_price_analysis(pool, symbol, as_of=None) -> dict`; `GET /api/market-data/stocks/{symbol}/analysis?as_of=YYYY-MM-DD`, sử dụng READ_ROLES hiện có. Query parameterized/read-only/repeatable-read, tối đa21 phiên giá và bản activity đúng các ngày đó; không tự gọi nguồn. Chọn cùng một nguồn/cơ sở được khai báo, không gộp mọi hàng cùng mã/ngày.

- [ ] Response có symbol, requested_as_of, as_of, first_date, session_count, freshness, metrics, activity, benchmark, coverage, warnings và sources. Mỗi nguồn chỉ đến price_id/payload_id/source/date; không DSN/key/log nội bộ.
- [ ] Chưa có dữ liệu trả404; input/ngày tương lai sai trả400 hoặc422 theo FastAPI; DB lỗi trả503 không lộ lỗi kết nối. Partial coverage vẫn200 với status partial và NULL rõ ràng.
- [ ] Test auth401/403, date/symbol/SQL binding, DB outage, mixedsource, truy nguyên payload và API thực sự gọi calculator. Không mock mất phép tính chính hay auth để có xanh.
- [ ] Chạy `.venv/Scripts/python.exe -B -m unittest backend.tests.test_price_analysis_api backend.tests.test_market_data_api backend.tests.test_price_queries -v`.
- [ ] Gọi service thật read-only cho FPT/MBB rồi đủ10 mã, lưu response và đối chiếu SQL độc lập. Không lấy baseline/mock làm bằng chứng đã cập nhật nguồn mới.

### PF08 — Hiển thị trong trang doanh nghiệp và nghiệm thu

**Goal/risk:** Người dùng hiểu số liệu tính đến ngày nào, đủ/thiếu phần nào.

**Files:** Create `frontend/src/pages/companies/PriceAnalysis.jsx`, `frontend/tests/priceAnalysis.test.js`; modify `frontend/src/pages/companies/marketDataApi.js`, `frontend/src/pages/companies/CompanyDetailPage.jsx`. Ngoại lệ4 file cho client/component/gắn trang/test của cùng tính năng. Không đổi chart PriceHistory hoặc tạo dashboard mới.

**Interface:** `getPriceAnalysis(symbol, asOf, signal)` dùng authorized fetch hiện có; component nhận response API, không tính lại các chỉ tiêu tài chính ở frontend.

- [ ] Hiển thị giá/volume, khối ngoại, benchmark/biến động; ngày dữ liệu và nguồn ở cùng kết quả. NULL hiện “Chưa đủ dữ liệu”; intraday/sau đóng cửa/chờ đối soát có nhãn rõ.
- [ ] Chuyển mã nhanh hủy request cũ, không hiện kết quả FPT dưới tiêu đề MBB; loading/error/partial/không có dữ liệu là các trạng thái phân biệt.
- [ ] Chạy `node --test frontend/tests/priceAnalysis.test.js`, `npm --prefix frontend run build` và regression marketDataApi/pricePolling hiện có.
- [ ] Kiểm trang thật với401/503, DB cũ29/10, chuỗi chỉ có một ngày ngoại, bản intraday, benchmark thiếu và dữ liệu đầy đủ; không dùng số mock như dữ liệu thật. Render kiểm tra desktop/mobile bằng công cụ browser trước nghiệm thu.

## Cổng nguồn và tiêu chí hoàn thành

- Mốc A: migration/store/replay đạt; snapshot cũ truy được, các ngày không ghi đè nhau, chạy lại không nhân bản. Chưa đồng nghĩa đã có20 ngày lịch sử ngoại.
- Mốc B: collector lưu được10 mã khi0 người xem; sau restart/DB lỗi replay được. Có ngày/nguồn/coverage và trạng thái cuối phiên có căn cứ.
- Mốc C: giá cập nhật đạt cổng cơ sở giá; nếu chưa đạt phải báo blocked riêng, không gọi tính năng phân tích “hiện tại” là đã xong.
- Mốc D: API/UI tính đúng oracle, source IDs truy lại được, không lẫn ngày/đơn vị; đủ các test thiếu dữ liệu và quyền truy cập.
- Khối ngoại1/5/20 đủ kỳ chỉ nghiệm thu khi có đủ phiên dữ liệu đã xác minh. Muốn có ngay lịch sử trước ngày bắt đầu thu cần nguồn hỗ trợ backfill; user hiện chưa chọn nguồn/key. Thu mới không khôi phục quá khứ đã mất.
- Vnstock6/chuyển nhà cung cấp là công việc riêng sau khi chọn nguồn/quyền. Nếu KBS ngừng truy cập: giữ dữ liệu cũ, báo nguồn lỗi; không tự nâng SDK hoặc thay nguồn âm thầm.

## Quy trình ECC, ngân sách và triển khai

Mỗi PF có ID ổn định, title Việt, context/edit/test allowlist và các checks trên. Context chỉ gồm interface brief và file liên quan; job4 file phải ghi scope_exception. Không hai job cùng sở hữu một file sửa. Forecast cả Dev/QA/review trước dispatch; không bỏ test/receipt để lách kích thước.

Thứ tự gate: implementation → independent testing → coordinator duyệt rủi ro/hash/argv → local runner → independent review → coordinator approval/integration → kiểm tra DB/UI thực tế. Tests đỏ trước implementation; candidate không phải OS sandbox. Không commit/push trong MVP nếu user chưa yêu cầu.

Đề xuất ngân sách cho toàn WBS mở rộng:36 inference calls,10800 giây, không đặt trần token; tối đa3 attempts/stage,2 repair rounds/job, cùng một ledger. Đây là đề xuất để chốt trước execution, chưa cấp thêm ngân sách. Không dùng thời gian trong plan như dự báo thời gian hoàn thành.

Workflow cũ `s5-price-analysis-20261111` đang blocked do gateway localhost:20128, đã dùng1/6 calls, không có code được chấp nhận. Giữ nguyên manifest/request/attempt/budget và checkpoint. Khi thực thi, kiểm tra thời hạn và ghi quyết định tiếp tục hoặc thay thế phạm vi bằng quyền/budget rõ ràng; không tạo ID mới chỉ để reset task thất bại/hết budget. Không tự resume workflow hoặc benchmark khác.

Chỉ lập manifest/dispatch sau khi user yêu cầu thực thi plan và gateway được khôi phục. Không cần gateway để đọc/review plan này.

## Rehearsal, áp dụng và quay lui

1. Chạy test offline; migration/upsert thật trên PostgreSQL thử nghiệm; lưu receipt và counts trước/sau.
2. Review xong mới áp migration tạo bảng mới vào DB dự án, chạy dry-run replay, rồi giao dịch apply cho dữ liệu đã xác minh.
3. Bật nối collector từng mã FPT/MBB trước, xác minh đủ raw/daily/source; sau đó đủ10 mã, cuối cùng bật UI.
4. Nếu lỗi, tắt riêng persistence/UI mới và giữ collector/chart/API cũ. Giữ bảng mới và dữ liệu phục vụ điều tra; không tự DROP bảng, xóa archive hoặc quay lui bằng mất dữ liệu.
5. Quay lui code không bảo đảm nguồn Vnstock cũ còn hoạt động. Luôn giữ khả năng đọc dữ liệu DB/snapshot đã lưu.

## Tự review plan

Đã map các phần khung đã chốt vào PF06–PF08; nguồn/storage/thu thập/replay vào PF01–PF05. Đã kiểm các interface nguồn→normalizer→store→query→calculator→API→UI, quyền đọc và chính sách thiếu dữ liệu. Các điều kiện chưa chứng minh: phạm vi total_value, trạng thái cuối ngày của khối ngoại, độ tương thích cơ sở giá và nguồn backfill dài hạn; các phần này có cổng chặn/coverage thay vì giả định đã giải quyết.
