# Nhãn xu hướng giá — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cào bù lịch sử VNINDEX/HNXINDEX/UPCOMINDEX tới khoảng 250 phiên. Sau đó tính nhãn xu hướng 20/60/200 phiên từ giá đã lưu, hiện nhãn trên trang công ty và đưa vào chatbot làm bằng chứng trích dẫn được.

**Architecture:**
- Một hàm thuần `analyze_trend` (Decimal, không I/O) trong `backend/src/market_data/trend.py`.
- Một truy vấn chỉ đọc `get_price_trend` trong `analysis_queries.py`.
- Endpoint `analysis` có sẵn gắn thêm khối `trend`.
- Chatbot nhận loại bằng chứng mới `PRICE_TREND` trong luồng `MARKET_ANALYSIS`.
- Cào bù chỉ số là một chế độ mới của `refresh_market_prices.py`, chạy tay khi backend đã dừng.

**Tech Stack:** Python 3.13, FastAPI, asyncpg, pytest/unittest; React (Vite), `node --test`.

**Spec:** `docs/superpowers/specs/2026-11-12-price-trend-design.md`

## Global Constraints

- DB thật: VPS qua `127.0.0.1:15433/finmind`. Chỉ Task 3 được ghi, và chỉ thêm các phiên chỉ số cũ hơn phiên đầu đang lưu.
- Không sửa hay xoá dòng giá/chỉ số đã lưu, kể cả SMA/RSI của dòng cũ. Không đổi `approval_status`/`is_enabled` của nguồn.
- Nguồn chỉ số giữ nguyên `vnstock_kbs`. Không trộn nguồn khác.
- Ngưỡng: khung 20/60/200 phiên; `L` = 5/15/50; `R` = 8%/15%/30%; độ dốc 1%. Biên độ sàn HOSE 7%, HNX 10%, UPCOM 15%, cộng dung sai 0,5 điểm %.
- Số học Decimal, 4 chữ số, ROUND_HALF_UP; số trả về là chuỗi, giống `analysis.py`.
- Không khuyến nghị mua/bán, không dự báo. Dòng nhắc cố định: "Mô tả từ dữ liệu giá đã lưu, không phải khuyến nghị".
- Giữ nguyên chỉnh sửa của user trong `backend/src/graph/graph_store.py`. **Không commit/push khi user chưa bảo.** Bước "Checkpoint" thay cho bước commit: thêm 1–3 dòng vào `docs/sprint5/CHECKPOINT-CLAUDE-2026-11-11.md`.
- Lệnh test: `backend\.venv\Scripts\python.exe -m pytest <file> -q -p no:cacheprovider` (chạy ở gốc repo).

## Review Focus

1. **Chỉ số chưa có dòng nào trong DB:** nạp lần đầu được, biên bản ghi `initial_load=true`. Chỉ số đã có dòng mà không có phiên chồng lấp thì dừng. (Task 2)
2. **Mã có đúng `h+L−1` phiên:** khung đó trả `INSUFFICIENT_DATA`, không chia cho số phiên thiếu. (Task 4)
3. **Có ngày vượt biên độ sàn trong khung:** khung đó là `UNCLEAR` với `possible_corporate_action:<ngày>`, và đỉnh/đáy 52 tuần để trống nếu ngày đó nằm trong 250 phiên. (Task 4)
4. **Tính `trend` lỗi (DB timeout, dữ liệu lệch):** `analysis` vẫn trả 200, kèm `trend=null` và cảnh báo `trend_unavailable`; chatbot vẫn trả lời bằng giá và tin. (Task 5, Task 7)
5. **Chỉ số thiếu một số ngày cổ phiếu có giao dịch:** `index_return_percent=null` cho khung đó, không nội suy. (Task 4)

---

### Task 1: SDK lấy được lịch sử chỉ số dài hơn

**Files:**
- Modify: `backend/src/market_data/sdk.py` (`history`)
- Modify: `backend/src/market_data/sdk_worker.py` (nhánh `index_history`/`stock_history`)
- Modify: `backend/src/market_data/history.py` (`normalize_history`, `normalize_index_history`)
- Test: `backend/tests/test_market_data_sdk.py`, `backend/tests/test_market_indices.py`

**Interfaces:**
- Produces:
  - `BatchSDKClient.history(symbol: str, days: int = 180) -> dict`. Gửi `{"action": ..., "symbol": ..., "days": days}`. `days` ngoài khoảng 1..400 thì `ValueError`.
  - Worker: `start = today - days`, `count = 300`, mặc định 180 khi request không có `days`.
  - `normalize_index_history(symbol, result, *, max_age_days: int = 366)` và `normalize_history(..., max_age_days=366)`. Kiểm ngày theo `max_age_days`; giới hạn số dòng vẫn ≤ 400.

- [ ] **Step 1: Viết test lỗi trước**
  - `test_index_history_passes_days`: `client.history("HNXINDEX", days=400)` gửi đúng payload có `"days": 400`; `days=0` và `days=401` đều raise `ValueError`.
  - `test_child_uses_requested_window`: chạy worker với `{"action":"index_history","symbol":"VNINDEX","days":400}`, kiểm `ohlcv` được gọi với `start=str(today - 400 ngày)` và `count=300`.
  - `test_normalize_accepts_longer_window`: dòng cũ 390 ngày bị từ chối khi `max_age_days=366`, được nhận khi `max_age_days=400`.
- [ ] **Step 2: Chạy, thấy FAIL** — `pytest backend/tests/test_market_data_sdk.py backend/tests/test_market_indices.py -q`
- [ ] **Step 3: Implement** theo Interfaces. Mặc định giữ hành vi cũ, vì `live.py` gọi `history(symbol)` không có `days`.
- [ ] **Step 4: Chạy, thấy PASS** (kể cả các test cũ trong 2 file).
- [ ] **Step 5: Checkpoint.**

### Task 2: Chế độ cào bù chỉ số trong `refresh_market_prices.py`

**Files:**
- Modify: `backend/scripts/refresh_market_prices.py`
- Test: `backend/tests/test_market_price_refresh.py`

**Interfaces:**
- Consumes: `BatchSDKClient.history(symbol, days=400)`; `normalize_index_history(symbol, raw, max_age_days=400)`; `_indicators(rows)`, `ingest.store_payload(...)` đã có.
- Produces:
  - `BACKFILL_INDEXES = ("VNINDEX", "HNXINDEX", "UPCOMINDEX")`
  - `INDEX_META = {"VNINDEX": ("VN-Index", "HOSE"), "HNXINDEX": ("HNX-Index", "HNX"), "UPCOMINDEX": ("UPCOM-Index", "UPCOM")}`
  - `plan_index_backfill(symbol: str, stored: list[dict], offered: list[dict]) -> dict`, trả về `{"rows": [bar...], "initial_load": bool, "matched_overlap": int}`.
    - `rows` là các bar có ngày < phiên đầu đang lưu, sắp tăng dần.
    - Mọi ngày chồng lấp phải khớp OHLC và volume, lệch thì `ValueError`.
    - `stored` có dòng mà không chồng lấp ngày nào thì `ValueError`.
    - `stored` có dòng nguồn khác `vnstock_kbs` thì `ValueError`.
    - `stored` rỗng thì `rows` = toàn bộ `offered` và `initial_load=True`.
  - `async def run_index_backfill(apply: bool, *, now=None, index_history=None) -> int`. Mỗi chỉ số lưu raw và `report.json` trong `outputs/market-refresh/<time>-index-backfill/`, `report["indexes"][symbol] = {"new_dates": [...], "initial_load": bool, "matched_overlap": int, "stored_before": int}`. Cả ba chỉ số ghi trong **một** transaction, khoá `market_index_bars` như `_write`.
  - SMA20/SMA50/RSI14 của phiên mới tính bằng `_indicators` trên chính chuỗi được thêm, sắp tăng dần. Không cập nhật dòng cũ.
  - CLI: `--backfill-index` (xem trước) và `--backfill-index --apply`.
  - `index_history` mặc định là SDK client riêng, giữ `collector.lock` như `run`. Gọi `history(symbol, days=400)`.

- [ ] **Step 1: Viết test lỗi trước** trong `test_market_price_refresh.py`:
  - `test_backfill_prepends_only_older_days`: stored 10–11/11/2026, offered các phiên 06, 09, 10, 11/11/2026 (07–08/11 là cuối tuần) → `rows` là 06/11 và 09/11, `matched_overlap=2`, `initial_load=False`.
  - `test_backfill_rejects_mismatch_and_unanchored_series`: offered 10/11 lệch close → `ValueError`; offered chỉ có 01–05/11 khi stored 10–11/11 → `ValueError`; stored có `source_name="other"` → `ValueError`.
  - `test_backfill_initial_load_when_nothing_stored`: stored rỗng → `rows == offered`, `initial_load=True`.
- [ ] **Step 2: Chạy, thấy FAIL.**
- [ ] **Step 3: Implement** theo Interfaces. Câu INSERT dùng cột như `_write` hiện tại, thêm `index_name`/`exchange` từ `INDEX_META`.
- [ ] **Step 4: Chạy, thấy PASS** — cả file `test_market_price_refresh.py`.
- [ ] **Step 5: Checkpoint.**

### Task 3: Chạy cào bù (vận hành, ghi VPS)

**Files:** không đổi code. Bằng chứng ở `outputs/market-refresh/*-index-backfill/`.

- [ ] **Step 1: Mở tunnel** bằng `Start-FinMindTunnel` trong `scripts/bootstrap-finmind.ps1` (dot-source rồi gọi). **Chỉ một lần**; lỗi thì dừng và báo user, không thử lại, vì VPS khoá IP khi sai mật khẩu nhiều lần.
- [ ] **Step 2: Đọc số phiên hiện có**, chỉ đọc: `SELECT index_symbol, count(*), min(trade_date), max(trade_date) FROM market_index_bars GROUP BY 1`. Ghi kết quả vào biên bản.
- [ ] **Step 3: Diễn tập trên PostgreSQL thử 15434.** Start bằng `pg_ctl` như checkpoint ghi; chép dòng chỉ số từ VPS sang; chạy `--backfill-index --apply` bằng cách patch `get_settings` và `asyncpg.connect` như `outputs/sprint5/price-flow-implementation-20261111/rehearse_daily_refresh.py`. Kỳ vọng:
  - Lần đầu ghi.
  - Chạy lặp không ghi thêm.
  - Sửa lệch một dòng chồng lấp thì cả lượt bị chặn.
  - Dừng 15434 sau khi xong.
- [ ] **Step 4: Xem trước trên VPS** (backend phải đang dừng): `backend\.venv\Scripts\python.exe -B -m backend.scripts.refresh_market_prices --backfill-index`. Kỳ vọng: không có `LOI`; mỗi chỉ số báo số phiên mới; tổng mỗi chỉ số sau khi thêm ≥ 250 phiên. Nếu KBS trả ít hơn, ghi số thực có và đi tiếp.
- [ ] **Step 5: Ghi:** cùng lệnh, thêm `--apply`. Kỳ vọng `Da ghi ... dong.`
- [ ] **Step 6: Hậu kiểm chỉ đọc:**
  - Số dòng mỗi chỉ số = trước + mới.
  - Hash các dòng cũ không đổi (so dump trước/sau).
  - `source` của dòng mới là `vnstock_kbs`.
- [ ] **Step 7: Checkpoint**, ghi số phiên trước/sau của từng chỉ số.

### Task 4: Hàm tính xu hướng `analyze_trend`

**Files:**
- Create: `backend/src/market_data/trend.py`
- Test: `backend/tests/test_market_price_trend.py`

**Interfaces:**
- Consumes: `analysis._decimal`, `analysis._row_day`, `analysis._formatted`.
- Produces:
  - `HORIZONS = {20: (5, Decimal("8")), 60: (15, Decimal("15")), 200: (50, Decimal("30"))}`
  - `BENCHMARK = {"HOSE": "VNINDEX", "HNX": "HNXINDEX", "UPCOM": "UPCOMINDEX"}`
  - `analyze_trend(price_rows: list[dict], index_rows: list[dict], *, exchange: str, rsi14: Decimal | None) -> dict`
    - `price_rows` là các dòng `price_bars` cùng nguồn/cơ sở, tối đa 260, sắp tăng dần.
    - `index_rows` là các dòng `market_index_bars` của chỉ số sàn, chỉ cần `trade_date`, `close`.
    - Trả về đúng khối `trend` trong spec (mục Hợp đồng dữ liệu). Mỗi horizon có `label` ∈ {`UP`, `DOWN`, `SIDEWAYS`, `UNCLEAR`, `INSUFFICIENT_DATA`} và `reasons` là mã cố định:
      - `close_above_sma` / `close_below_sma`
      - `sma_rising` / `sma_falling` / `sma_flat`
      - `positive_return` / `negative_return`
      - `narrow_range`
      - `mixed_signals`
      - `possible_corporate_action:<ngày>`
      - `not_enough_sessions`
      - `index_not_enough_sessions`
    - Trùng ngày hoặc nhiều nguồn/cơ sở thì `ValueError`, giống `analysis._prices`.
  - `trend_passage(symbol: str, trend: dict) -> str`: đoạn tiếng Việt cố định cho chatbot. Gồm nhãn từng khung (Tăng/Giảm/Đi ngang/tích lũy/Chưa rõ xu hướng/Chưa đủ dữ liệu), lợi suất, so với SMA, so với chỉ số, đỉnh/đáy 52 tuần, RSI14, ngày `as_of`, nguồn và trạng thái duyệt, câu "Giá chưa điều chỉnh theo sự kiện doanh nghiệp".
- Thứ tự xét nhãn và cờ sự kiện doanh nghiệp: đúng theo spec, mục Quy tắc tính.

- [ ] **Step 1: Viết test lỗi trước** (dựng chuỗi giá tổng hợp bằng một helper `series(closes, start=date(2025,1,2))`, cách ngày làm việc):
  - `test_rising_series_is_up_on_all_horizons`: 260 phiên, close tăng 0,2%/phiên → cả ba khung `UP`, reasons có `close_above_sma`, `sma_rising`, `positive_return`.
  - `test_falling_series_is_down`: giảm 0,2%/phiên → `DOWN`.
  - `test_flat_band_is_sideways`: dao động ±2% quanh 100 → khung 20 là `SIDEWAYS`, có `narrow_range`.
  - `test_mixed_signals_is_unclear`: tăng đều 250 phiên rồi giảm mạnh 10 phiên cuối, sao cho close < SMA20 trong khi SMA20 còn dốc lên → khung 20 là `UNCLEAR`, có `mixed_signals`.
  - `test_insufficient_sessions_boundary`: 24 phiên → khung 20 là `INSUFFICIENT_DATA` (cần 25); 25 phiên → khung 20 có nhãn khác `INSUFFICIENT_DATA`.
  - `test_corporate_action_day_forces_unclear`: một ngày giảm 20% trong 20 phiên cuối, `exchange="HOSE"` → khung 20 là `UNCLEAR` với `possible_corporate_action:<ngày>`, và `context.high_52w is None`.
  - `test_limit_move_within_band_is_not_flagged`: một ngày giảm đúng 7% → không có cờ.
  - `test_index_comparison_uses_stock_dates_only`: thiếu một ngày chỉ số trong 20 phiên → `index_return_percent is None`, có `index_not_enough_sessions`.
  - `test_rsi_and_context_numbers`: `rsi14=Decimal("45.1234")` → `context.rsi14 == "45.1234"`; đỉnh/đáy 52 tuần đúng giá trị và ngày.
  - `test_passage_states_labels_and_disclaimer`: passage chứa "Ngắn hạn: Tăng", ngày `as_of`, "chưa điều chỉnh" và "không phải khuyến nghị".
- [ ] **Step 2: Chạy, thấy FAIL.**
- [ ] **Step 3: Implement** theo Interfaces và spec.
- [ ] **Step 4: Chạy, thấy PASS.**
- [ ] **Step 5: Checkpoint.**

### Task 5: Truy vấn và gắn `trend` vào API `analysis`

**Files:**
- Modify: `backend/src/market_data/analysis_queries.py`
- Modify: `backend/src/api/routers/market_data.py` (`price_analysis`)
- Test: `backend/tests/test_price_analysis_api.py`

**Interfaces:**
- Consumes: `analyze_trend`, `BENCHMARK` (Task 4).
- Produces:
  - `async def get_price_trend(pool, symbol: str, as_of: date | None = None) -> dict`
    - Một transaction chỉ đọc, `repeatable_read`, timeout 10 giây.
    - Đọc: `companies.exchange`; 260 dòng `price_bars` mới nhất ≤ `as_of` kèm provenance (`PROVENANCE`/`SOURCE` có sẵn); RSI14 của phiên cuối từ `price_indicators`; `market_index_bars` của `BENCHMARK[exchange]` đúng các ngày đó.
    - Trả kết quả `analyze_trend`, thêm `as_of`, `source`.
    - Không có giá thì `LookupError`.
  - `price_analysis` gọi `get_price_trend` sau phân tích cũ. Lỗi bất kỳ (gồm `ValueError`, `RuntimeError`, lỗi asyncpg, timeout) thì `result["trend"] = None` và thêm `"trend_unavailable"` vào `result["warnings"]`.

- [ ] **Step 1: Viết test lỗi trước:**
  - `test_analysis_includes_trend`: `FakePool` trả đủ 260 phiên → `body["trend"]["horizons"]["20"]["label"]` có mặt; câu SQL không chứa ký hiệu mã hay ngày (tham số hoá).
  - `test_trend_failure_keeps_analysis`: pool làm `get_price_trend` raise `TimeoutError` → HTTP 200, `body["trend"] is None`, `"trend_unavailable" in body["warnings"]`, các trường `metrics` vẫn đúng như test cũ.
  - Mở rộng `FakePool.fetch` để trả dòng theo tên bảng (`price_indicators`, `market_index_bars`, cột `exchange`).
- [ ] **Step 2: Chạy, thấy FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Chạy, thấy PASS** — cả file.
- [ ] **Step 5: Checkpoint.**

### Task 6: Mục "Xu hướng giá" trên trang công ty

**Files:**
- Modify: `frontend/src/pages/companies/PriceAnalysis.jsx`
- Test: `frontend/tests/priceAnalysis.test.mjs`

**Interfaces:**
- Consumes: khối `data.trend` (Task 5).
- Produces: component `TrendSection({ trend })`, render đầu `PriceAnalysisResult`.
  - Ba thẻ Ngắn hạn/Trung hạn/Dài hạn. Nhãn dịch: `UP`→"Tăng", `DOWN`→"Giảm", `SIDEWAYS`→"Đi ngang/tích lũy", `UNCLEAR`→"Chưa rõ xu hướng", `INSUFFICIENT_DATA`→"Chưa đủ dữ liệu".
  - Màu theo `StatusBadge`: Tăng = success, Giảm = danger (nếu không có thì warning), còn lại = neutral.
  - Mỗi thẻ có 2–3 lý do bằng số: lợi suất, so với SMA, so với chỉ số.
  - Một dòng ngữ cảnh: đỉnh/đáy 52 tuần, RSI14, KL20/KL60.
  - Dòng nhắc: "Mô tả từ dữ liệu giá đã lưu, không phải khuyến nghị".
  - `trend` null thì hiện "Chưa tính được xu hướng giá".

- [ ] **Step 1: Viết test lỗi trước:** `trend renders three horizons, labels, reasons and disclaimer`; `missing trend shows unavailable note without breaking metrics`.
- [ ] **Step 2: Chạy, thấy FAIL** — `cd frontend; node --test tests/priceAnalysis.test.mjs`
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Chạy, thấy PASS**, rồi `npm.cmd run build` thành công.
- [ ] **Step 5: Checkpoint.**

### Task 7: Chatbot dùng `PRICE_TREND`

**Files:**
- Modify: `backend/src/b1_answering/evidence/market_contract.py` (`feed_item`)
- Modify: `backend/src/retrieval_orchestration/market_research.py` (`MarketResearch`)
- Modify: `backend/src/api/routers/research_chat.py` (chỗ tạo `MarketResearch`)
- Modify: `backend/src/b1_answering/evidence/grounded.py` (prompt `MARKET_ANALYSIS`)
- Test: test có sẵn của `market_research` và `market_contract`. Tìm bằng `grep -rl "MarketResearch\|feed_pack" backend/src/b1_answering/tests backend/tests backend/src/retrieval_orchestration` và thêm test vào file đó.

**Interfaces:**
- Consumes: `get_price_trend` (Task 5), `trend_passage` (Task 4).
- Produces:
  - `feed_item` nhận snapshot `{kind: "PRICE_TREND", provider: "finmind_db", symbol, observed_at, as_of, trend: {...}}`.
    - `passage = trend_passage(symbol, trend)`
    - `title = f"Xu hướng giá {symbol} · dữ liệu FinMind"`
    - `locator` thêm `trading_day=as_of`, `section=f"FinMind DB · {symbol} · {as_of}"`
    - Thiếu trường hoặc `as_of` sai định dạng thì `CitationError("INVALID_EVIDENCE")`.
  - `MarketResearch.__init__(repository, *, services, now=None, trend_reader=None)`, với `trend_reader: Callable[[str], Awaitable[dict | None]]`.
  - `lookup`: khi `source_type == "MARKET_ANALYSIS"` và đúng 1 mã, `await trend_reader(symbol)` trước `to_thread`. Lỗi thì coi như `None`. Kết quả truyền vào `_analysis(..., trend=...)`. `_analysis` thêm snapshot `PRICE_TREND` lên đầu danh sách (trước giá và tin), tổng vẫn ≤ 10.
  - `research_chat.py`: `trend_reader=lambda symbol: get_price_trend(get_pool(), symbol)`.
  - `grounded.py`: thêm vào prompt `MARKET_ANALYSIS` đúng câu sau:

    > Nếu có bằng chứng xu hướng giá từ FinMind, nêu đúng nhãn của từng khung như bằng chứng ghi; không đổi, không nâng hay hạ nhãn; nhãn "Chưa rõ xu hướng" hoặc "Chưa đủ dữ liệu" phải nói đúng như vậy.

- [ ] **Step 1: Viết test lỗi trước:**
  - `test_feed_item_accepts_price_trend`: passage chứa nhãn; snapshot thiếu `as_of` → `CitationError`.
  - `test_analysis_includes_trend_evidence_first`: `trend_reader` trả trend giả → item đầu tiên của evidence pack có `source_type == "PRICE_TREND"`.
  - `test_analysis_survives_trend_failure`: `trend_reader` raise `OSError` → vẫn `EVIDENCE_READY` với giá/tin như cũ.
  - `test_prompt_mentions_trend_rule`: request `MARKET_ANALYSIS` chứa câu prompt mới.
- [ ] **Step 2: Chạy, thấy FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Chạy, thấy PASS**, cùng toàn bộ test của router chat và `b1_answering` liên quan.
- [ ] **Step 5: Checkpoint.**

### Task 8: Kiểm thật và chốt

- [ ] **Step 1: Toàn bộ test.** Các file market (`backend/tests/test_market_*.py`, `test_price_analysis_api.py`, `test_api_roles.py`), test chat liên quan, `node --test` frontend, `npm.cmd run build`. Ghi số passed/skipped.
- [ ] **Step 2: Kiểm trên VPS, chỉ đọc.** Gọi `get_price_trend` cho 30 mã của rổ (`BACKGROUND_SYMBOLS`). Mỗi mã phải có nhãn cho cả ba khung, hoặc `INSUFFICIENT_DATA` có lý do. Lưu `outputs/sprint5/price-trend-20261112/vps-trend.json`.
- [ ] **Step 3: Đối chiếu SQL độc lập** cho FPT, MBB, VCB: SMA, lợi suất và biên độ 20/60/200 tính bằng SQL thuần phải khớp đến 4 chữ số.
- [ ] **Step 4: Kiểm trình duyệt.** Khởi động lại backend, mở `/companies/FPT` ở rộng 1440 và 390: có mục "Xu hướng giá", không tràn ngang, không lỗi trang. Lưu ảnh vào cùng thư mục.
- [ ] **Step 5: Kiểm chat.** Hỏi "Xu hướng giá FPT dạo này thế nào?". Câu trả lời trích bằng chứng `PRICE_TREND` và nêu đúng nhãn như widget.
- [ ] **Step 6: Checkpoint cuối** trong `docs/sprint5/CHECKPOINT-CLAUDE-2026-11-11.md`: việc đã xong, bằng chứng, việc chưa kiểm. Không commit.
