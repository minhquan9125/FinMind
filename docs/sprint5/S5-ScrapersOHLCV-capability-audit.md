# ScrapersOHLCV — Khả năng thu thập và kết quả thử nguồn

Kiểm tra ngày **10/11/2026**, khoảng **19:56–20:00 giờ Việt Nam**. Phạm vi: đọc code hiện tại, chạy test và gọi nguồn thật bằng các hàm hiện có; không sửa code ứng dụng, không ingest DB hoặc thay file giá đang dùng.

## Kết luận

**Cập nhật tài liệu production:** tài liệu Vnstock hiện tuyên bố ngừng xác thực các thế hệ cũ từ 10/11 và chuyển sang v6 dùng key OpenAPI của nguồn. Các lượt thử 4.0.9 thành công dưới đây vẫn là bằng chứng quan sát thật, nhưng không phải cam kết hỗ trợ bản cũ. Xem [quota, free tier và mô phỏng nhiều người dùng](S5-production-free-tier.md) trước khi chọn kiến trúc production.

**Bộ cào đang lấy được dữ liệu mới đến 10/11/2026.** Mốc 29/10 trong PostgreSQL và các file cũ phản ánh dữ liệu đã lưu tại thời điểm audit trước, không chứng minh nguồn bên ngoài ngừng cập nhật.

Giá/khối lượng lịch sử, bốn chỉ số thị trường và bảng điện hoạt động trong lượt thử này. Vướng mắc cho khung phân tích năm phần là **chưa có kho lịch sử hằng ngày của khối ngoại và giá trị giao dịch**, chưa phải mọi trường đó đều không lấy được từ nguồn.

## Hàm nào làm gì?

Các đường dẫn dưới đây tính từ `data_pipeline/ScrapersOHLCV/`.

| Hàm/đường code | Dữ liệu hoặc chức năng |
|---|---|
| `ohlcv/sdk/worker.py:request`, action `catalog` | `Reference().equity.list_by_exchange()`: mã, loại công cụ, sàn, tên công ty |
| `ohlcv/sdk/worker.py:request`, action `history` | `Market().equity(symbol).ohlcv(...)`: time, open, high, low, close, volume; mặc định 180 ngày, nến 1D, count tối đa 400 trong lệnh hiện tại |
| Cùng action `history`, mã thuộc `INDEXES` | `Market().index(symbol).ohlcv(...)`: VNINDEX, VN30, HNXINDEX, UPCOMINDEX; đơn vị điểm |
| `ohlcv/history/vnstock.py:normalize_history` | Kiểm tra ngày/OHLCV; chuẩn hóa nến, provenance và trạng thái `pending_reconciliation` |
| `ohlcv/history/vnstock.py:indicators` | Tự tính **SMA20, SMA50, RSI14 theo Wilder** từ close; thiếu warm-up trả null |
| `ohlcv/history/vnstock.py:StockService.load` | Cache, kiểm mã/sàn, tải lịch sử và ghi atomic `data/stocks/<mã>/data.json`, giữ revision |
| `ohlcv/sdk/worker.py:request`, action `quote` | `equity.quote(get_all=True)`: bảng điện đầy đủ của một mã; chỉ số dùng nến 1D mới nhất |
| `ohlcv/realtime/quote.py:normalize_quote` | Chuẩn hóa quote thành nến 1D; giá cổ phiếu quote chia 1.000 để khớp giá lịch sử của SDK |
| `ohlcv/realtime/quote.py:LiveService.quote` | Trong phiên, cập nhật nến ngày và lưu raw receipt `live.json`; file này giữ snapshot mới nhất |
| `ohlcv/history/public.py:request_url/fetch_response/parse_response` | DNSE public chart: một request OHLCV ngày; khoảng yêu cầu tối đa 366 ngày, không retry khi lỗi |
| `ohlcv/providers/dnse.py:DNSEProvider.history` | Signed OpenAPI `/price/ohlc`; code hiện cố định STOCK/1D, cần API key/secret |
| `ohlcv/realtime/runner.py:LiveRunner` | Signed WebSocket, subscribe `ohlc.1D.json` và `ohlc_closed.1D.json`; code hiện không subscribe kênh khối ngoại/tick |

SMA/RSI là **chỉ báo tự tính**, không phải trường chỉ báo được nhà cung cấp trả về. Return 1/5/20, volume tương đối, ATR, MACD hoặc Bollinger có thể được tính từ chuỗi phù hợp, nhưng folder hiện chưa có hàm sản phẩm cho các chỉ tiêu đó. Chưa coi khả năng có đầu vào là đã triển khai chỉ báo.

## Những trường bảng điện thực tế đã lấy được

Ba lần gọi FPT đều trả được và nhất quán ở các trường đã đối chiếu:

- Giá: tham chiếu, trần/sàn, open/high/low/close, thay đổi giá và phần trăm, giá trung bình.
- Khối lượng lũy kế `volume_accumulated`; giá trị giao dịch `total_value`.
- Khối ngoại: `foreign_buy_volume`, `foreign_sell_volume`, `foreign_room`.
- Giao dịch thỏa thuận: `put_through_qty`, `put_through_value`.
- Ba mức giá/khối lượng chờ mua và chờ bán: `bid_price_1..3`, `bid_vol_1..3`, `ask_price_1..3`, `ask_vol_1..3`.
- Mã/sàn, ngày giao dịch `TD`, listed shares và một số metadata nguồn khác.

Giá trị/room/độ sâu là **snapshot**; nến lưu chuẩn hóa chỉ chứa OHLCV và metadata. Việc có trường trong raw quote không có nghĩa đã có API phân tích hoặc chuỗi lịch sử ngày của trường đó.

Hai nhãn SDK cần thận trọng: `foreign_buy_count` đang trả chuỗi `"10"`, `foreign_ownership_ratio` trả `924006547`. Audit chưa xác minh ý nghĩa và đơn vị với nhà cung cấp; **không dùng chúng như số lượt mua hoặc phần trăm sở hữu chỉ vì tên cột**. SDK KBS map `FC` và `FO` sang hai nhãn này; tên mapping không phải kiểm chứng ngữ nghĩa.

## Dữ liệu còn thiếu và có thể lấy theo đường nào?

| Nhu cầu | Hiện tại | Kết quả xác minh / hướng phù hợp |
|---|---|---|
| Lịch sử giá và volume ngày | Đã có | vnstock/KBS và DNSE public đều lấy được đến 10/11 |
| Giá trị giao dịch của ngày đang quan sát | Có raw `total_value` | Ba quote FPT có trường này; mapping SDK ghi đơn vị VND. Chưa xác minh total có gồm thỏa thuận hay không |
| Lịch sử giá trị giao dịch 5/20 phiên | Chưa có trong history OHLCV hoặc kho lưu hiện tại | Cần nguồn lịch sử có trường value, hoặc ghi nhận số ngày từ các lần chốt quan sát sau này; không phục hồi quá khứ chỉ từ một snapshot |
| Khối lượng ngoại mua/bán tại ngày quan sát | Có raw snapshot | FPT ba lượt có buy/sell volume; lấy ròng khối lượng bằng mua trừ bán khi đã xác nhận đơn vị |
| Lịch sử ngoại mua/bán ngày | Chưa có | Bản cài `vnstock 4.0.9` free không có UI `foreign_flow/trade_history`; chưa xác nhận một đường miễn phí lấy lịch sử này ổn định |
| **Giá trị tiền ngoại mua/bán** | Quote hiện không có buy/sell value riêng | DNSE có kênh Foreign Investor được tài liệu hóa, gồm buy/sell traded amount và tổng ngày; cần credentials/quyền dữ liệu, chưa thử trực tiếp |
| Chỉ số thị trường | Đã có đường lấy | Đã lấy mới cả VNINDEX/VN30/HNXINDEX/UPCOMINDEX, có dữ liệu cùng ngày cổ phiếu |
| SMA20/50 và RSI14 | Đã có | Tính được từ nến mới, giữ null khi chưa đủ chuỗi |
| Nến phút, tick và mua/bán chủ động | Pipeline hiện chỉ 1D | Nhà cung cấp có thêm API/kênh, nhưng worker/adapter hiện chưa thu thập và lưu chúng; chưa kiểm thử live |

Tài liệu hiện tại của Vnstock mô tả `foreign_flow` và `trade_history` thuộc bản Mở rộng. Tài liệu thế hệ mới không được coi là khả năng đã có trong bản 4.0.9 đang cài. Không nâng cấp SDK hoặc đăng ký gói trong audit này. [Vnstock Market](https://www.vnstocks.com/docs/vnstock/thi-truong-market), [chuyển từ 4.x](https://www.vnstocks.com/docs/vnstock/chuyen-doi/tu-vnstock-4x).

DNSE hiện có kênh Foreign Investor với khối lượng và giá trị mua/bán ngày. Adapter hiện tại chỉ xử lý nến ngày, chưa xử lý kênh này; credentials `DNSE_API_KEY`/`DNSE_API_SECRET` không có trong môi trường audit. Vì vậy mới xác minh được tài liệu, **chưa xác minh khả năng kết nối hoặc độ ổn định thực tế của kênh ngoại**. [DNSE Market Data](https://developers.dnse.com.vn/docs/guide/market-data/connect/), [DNSE OHLC](https://developers.dnse.com.vn/docs/dnse/get-ohlc-history/).

## Bằng chứng ổn định đã chạy

| Phép thử | Kết quả |
|---|---|
| SDK hiện cài | Python 3.13.11, vnstock 4.0.9, vnai 2.6.3, pandas 2.3.3 |
| Vnstock/KBS | **13/13 lượt thành công**: FPT history ×3, FPT quote ×3, catalog ×1, bốn index history, MBB history và ICT history |
| Lịch sử FPT/MBB và bốn index | Mỗi lần lấy 126 phiên, 14/05–10/11/2026 |
| Lịch sử ICT | 111 phiên cùng khoảng; không tạo ngày giả để bằng số phiên mã khác |
| FPT history lặp ba lần | Hash nội dung `rows` giống nhau; cả ba qua normalize và tính chỉ báo |
| FPT quote lặp ba lần | TD/close/volume/value/foreign volumes/put-through đã đối chiếu: giống nhau, ngày nguồn 10/11 |
| Catalog | 3.250 dòng công cụ; 1.517 dòng stock thuộc HOSE/HNX/UPCOM sau lọc, không coi toàn bộ catalog là cổ phiếu |
| DNSE public FPT | **3/3 lượt thành công**, 126 phiên đến 10/11, SHA raw body giống nhau |
| Test Python bằng môi trường SDK | **232 passed, 4 skipped**, không failure/error; bốn skip do thiếu quyền tạo symlink Windows |
| Test JavaScript | **23 passed**, không failure |
| File dữ liệu đã lưu trước audit | Hash không thay đổi so với inventory audit trước |

Phép thử SDK dùng **một child process tồn tại xuyên suốt**, gọi tuần tự, nghỉ ít nhất 10 giây sau mỗi lượt. DNSE public nghỉ 12 giây giữa các lần quan sát độc lập và dừng nếu lỗi. Không tắt SDK quota/auth, không đổi key hoặc quay vòng tài khoản. SDK được phép cập nhật cache hoạt động bình thường; không gọi `StockService.load` hoặc ingest để ghi đè giá gốc.

Lượt sandbox ban đầu không truy cập mạng hoặc tạo thư mục tạm/tiến trình test được. Sau khi chạy lại ngoài sandbox, network và test đều đạt như bảng trên. Lỗi sandbox được giữ receipt riêng, **không tính là lỗi nhà cung cấp**. Môi trường backend chung thiếu pandas, nên test crawler phải dùng môi trường SDK đã cài sẵn; không cài thêm dependency.

Ví dụ FPT quan sát ngày 10/11: history close `50.9`, quote close `50900`, volume cùng bằng `7.268.500`; `total_value=374.485.200.000`, foreign buy volume `643.213`, sell volume `2.358.479`. Đây là dữ liệu lấy được trong audit, không phải suy ra từ giá. Không nhân close×volume để thay giá trị giao dịch thực tế hoặc ngoại ròng tiền.

Các lượt thành công sau khởi động thường khoảng 0,7–1,3 giây; lượt đầu gồm khởi động SDK khoảng 17,5 giây. DNSE public ba lượt khoảng 0,16–0,38 giây. Đây là độ trễ quan sát trong audit, không phải SLA.

## Giới hạn và bước sử dụng tiếp theo

Lượt thử này diễn ra buổi tối, ngoài phiên. **Chưa chứng minh streaming/cập nhật mỗi 5 giây trong phiên, độ ổn định nhiều ngày, độ phủ mọi mã, finality của giá cuối ngày hoặc cơ sở giá điều chỉnh.** Ba lần giống nhau trong vài phút chỉ chứng minh tính nhất quán ngắn hạn. Nguồn public vẫn có thể đổi schema, giới hạn truy cập hoặc sửa dữ liệu.

Để phục vụ khung đã chốt, có thể giữ vnstock/KBS cho OHLCV/index và dùng DNSE public làm đường OHLCV kiểm tra/dự phòng sau khi đối soát cơ sở giá. Cần bổ sung lịch sử ngày cho quote/flow, nguồn ngoại giá trị và quy tắc đối soát phiên. Chưa tự động đưa dữ liệu thử vào DB hoặc thay đổi app.

ECC independent reviewer đã được gọi qua manager cho cùng audit, nhưng gateway trả HTTP 413; **không có review PASS**. Các kết quả trên là kiểm chứng trực tiếp của coordinator, kèm receipt; không phải tuyên bố workflow phát triển phần mềm đã nghiệm thu.

## Artifact

Tại `outputs/sprint5/scrapers-audit-20261110/`:

- `sdk-receipts.json`, `sdk-*.json`: lượt SDK và dữ liệu nguồn thử riêng.
- `public-receipts.json`, `public-1..3.json`: lượt DNSE public và body JSON.
- `stability-verification.json`: đối chiếu lặp, hash và xác nhận file giá cũ giữ nguyên.
- `tests-sdk-elevated.xml`, `tests-node.xml`: receipt test đạt; các file sandbox ghi rõ trong tên.
- `source-inventory.json`: danh sách hàm/line và hash chín file trọng tâm.
- `sha256.json`: hash của các artifact kết quả tại thời điểm hoàn tất audit.

Script probe tại `.agent-state/probe_scrapers_live.py`; request reviewer tại `.agent-state/harness-requests/scrapers-review.json`. Không file nguồn của crawler nào được sửa trong lượt kiểm tra.
