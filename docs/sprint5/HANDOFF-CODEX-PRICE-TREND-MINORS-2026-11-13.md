# Bàn giao Codex — sửa các lỗi nhỏ còn để lại của phần xu hướng giá (13/11/2026)

Nguồn: review cuối của kế hoạch giá, ledger `.superpowers/sdd/2026-11-12-price-trend/progress.md` (các dòng `Final: minor (deferred)`). Spec: `docs/superpowers/specs/2026-11-12-price-trend-design.md`.

## Ranh giới

- Làm trong cây thư mục chính, nhánh `midterm_demo`. **Không commit, push, stash hay đổi nhánh.**
- **Chỉ sửa các file sau** (cùng file test tương ứng):
  - `backend/src/market_data/trend.py`, test `backend/tests/test_market_price_trend.py`;
  - `backend/src/retrieval_orchestration/market_research.py`, test `backend/tests/test_market_research.py`;
  - `backend/src/market_data/activity_store.py`, test `backend/tests/test_market_activity_collector.py`.
- **Không đụng** các file của phần BCTC đang review: `backend/src/market_data/app.py`, `backend/src/api/routers/market_data.py`, `backend/scripts/refresh_*`, `backend/src/financial/*`, `backend/src/documents/*`, các migration và `010_schema.sql`.
- Không kết nối DB thật `127.0.0.1:15433`. Test dùng DB test `127.0.0.1:15434` nếu cần. Không gọi mạng. Không khởi động lại backend.
- TDD: test đỏ trước, sửa sau. Output test phải sạch. Giữ nguyên kiểu xuống dòng của từng file.
- Xong thì ghi 1–2 dòng vào cuối `docs/sprint5/CHECKPOINT-CLAUDE-2026-11-11.md`, ghi rõ "Codex: price-trend minors", kèm lệnh test và kết quả.

## Việc cần làm

1. **`trend.py:134`** — cửa sổ 52 tuần dùng `>=`, nên khi phiên vượt biên độ rơi đúng vào `year[0]` thì các số 52 tuần bị trống. Sửa để phiên ở mép cửa sổ vẫn được tính đúng. Test với phiên vượt biên nằm đúng mép.
2. **`trend.py:128`** — một dòng chỉ số lỗi làm toàn bộ phần so với chỉ số thành null. Sửa để dòng lỗi được tính như một ngày thiếu, giống quy tắc "thiếu ngày" đang có. Test.
3. **`trend.py:176`** — đoạn văn `trend_passage` đi theo thứ tự của dict. Sửa để luôn đi theo `HORIZONS` (20, 60, 200). Test với dict có thứ tự khác.
4. **Khung bị ép UNCLEAR do sự kiện doanh nghiệp** vẫn hiện return và range đã bị méo. Khi khung có lý do sự kiện doanh nghiệp, đặt `return_percent`/`range_percent` của khung đó thành `None` và giữ nguyên lý do. Kiểm frontend `TrendSection` vẫn hiện "—" khi gặp `None`; chỉ đọc, không sửa frontend. Test.
5. **`market_research.py:45-47`** — các kiểm tra scope nằm ngoài `try`, nên scope sai định dạng làm ném lỗi thay vì trả `unavailable()`. Đưa vào trong. Test.
6. **`market_research.py:49`** — xu hướng luôn lấy theo hôm nay, kể cả khi câu hỏi nêu một ngày trong quá khứ. Nếu scope có ngày cụ thể thì truyền `as_of` vào `trend_reader` (`get_price_trend(pool, symbol, as_of=None)` đã hỗ trợ). Nếu chữ ký `trend_reader` không nhận `as_of` thì ghi lại vào checkpoint, không đổi chữ ký ở file khác. Test.
7. **`market_research.py:141`** — một bằng chứng xu hướng bị `feed_item` từ chối làm hỏng cả gói bằng chứng. Chỉ bỏ phần xu hướng, giữ các bằng chứng khác, và log cảnh báo. Test.
8. **Lỗi xu hướng trong chat bị nuốt mất, không có dòng log.** Thêm `logging.getLogger(__name__).warning(...)` ở chỗ bắt lỗi trong `market_research.py`. Không log dữ liệu nhạy cảm. Test bằng `caplog`/`assertLogs`. (Phần `/analysis` nằm trong `market_data.py`, đang khóa; không sửa.)
9. **`activity_store.py`** — khi gặp lỗi kéo dài không phải timeout, vòng lặp `break` làm các archive phía sau bị bỏ đói. Đổi thành `continue` cho lỗi không phải timeout (timeout vẫn dừng như hiện nay) và đếm vào `failed`. Test.

## Lệnh test

`backend\.venv\Scripts\python.exe -m pytest backend/tests/test_market_price_trend.py backend/tests/test_market_research.py backend/tests/test_market_activity_collector.py backend/tests/test_price_analysis_api.py -q -p no:cacheprovider`

Nếu có test viết theo kiểu `src.*` (chạy từ `backend/`), chạy đúng theo cách file đó yêu cầu và ghi lại lệnh đã dùng.

## Không làm trong gói này

- `sdk_worker` cố định 300 dòng: chỉ ghi chú.
- `daily_refresh.last_ok` khi chỉ số bị chặn: đã sửa ở I4.
