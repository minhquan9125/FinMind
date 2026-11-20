# Kiểm tra dữ liệu cho khung phân tích giá và dòng tiền

Ngày kiểm tra: 10/11/2026. Snapshot DB: **19:41:39 giờ Việt Nam** (`2026-11-10T12:41:39.526328+00:00`). Chỉ đọc PostgreSQL và file cục bộ; không gọi nguồn giá bên ngoài, không tải dữ liệu mới hoặc sửa ứng dụng.

## Kết luận

**Cập nhật sau khi thử nguồn thật:** audit tiếp theo đã lấy được OHLCV/index mới đến 10/11 và quote có khối ngoại/value; xem [kết quả thử ScrapersOHLCV](S5-ScrapersOHLCV-capability-audit.md). Báo cáo dưới đây giữ nguyên kết quả kiểm tra dữ liệu đã lưu lúc 19:41, không phải kết luận nguồn bên ngoài không lấy được dữ liệu mới. Lịch sử ngày flow/value vẫn chưa có trong kho lưu hiện tại.

**Đủ dữ liệu để tính và kiểm chứng diễn biến giá, khối lượng và biên độ lịch sử của 10 mã đến 29/10/2026. Chưa đủ dữ liệu đồng bộ để vận hành toàn bộ khung năm phần cho thời điểm hiện tại.** Cần bổ sung lịch sử khối ngoại, giá trị giao dịch, cập nhật chỉ số tham chiếu và đối soát cơ sở giá giữa các nguồn.

| Thành phần | Bằng chứng quan sát | Mức sẵn sàng |
|---|---|---|
| Giá OHLC | `price_bars`: 21.365 dòng, 10 mã, ngày cuối 29/10/2026; không null OHLCV, không phát hiện OHLC/volume sai ràng buộc trong kiểm tra | Tính được lịch sử; chưa phải dữ liệu hiện tại |
| Khối lượng | Có volume từng phiên trên toàn bộ chuỗi trên | Tính được thay đổi và mức giao dịch tương đối; không đồng nhất với giá trị giao dịch |
| Giá trị giao dịch | Chưa có chuỗi ngày trong `price_bars` hoặc payload lịch sử; `total_value` chỉ thấy trong quote snapshot | Chưa đủ để so sánh 5/20 phiên |
| Khối ngoại | Snapshot có `foreign_buy_volume` và `foreign_sell_volume`; chưa thấy lịch sử ngày hoặc trường giá trị mua/bán riêng | Chưa đủ phân tích dòng tiền khối ngoại theo tuần/tháng |
| Thị trường tham chiếu | VNINDEX: 123 phiên đến 07/10; VN30/HNXINDEX: 123 phiên mỗi chỉ số đến 08/10 | Có dữ liệu lịch sử; chưa đồng bộ với cổ phiếu đến 29/10 |
| Mức biến động | Có high/low và close phiên trước; đủ đầu vào biên độ, TR, ATR hoặc độ lệch chuẩn lợi suất | Có thể tính sau khi quy định rõ công thức và cơ sở điều chỉnh |
| Chỉ báo lưu sẵn | `price_indicators` có **0 dòng** | Cần tính từ OHLCV, không đọc chỉ báo rỗng như số 0 |

10 mã là BID, CMG, CTG, ELC, FPT, ICT, ITD, MBB, TCB và VCB. Tất cả được khai báo HOSE trong `companies`. VNINDEX là ứng viên tham chiếu toàn thị trường cho nhóm này; VN30 chỉ được dùng khi có mục đích so sánh riêng, không giả định mọi mã thuộc rổ VN30.

## Khối ngoại và giá trị giao dịch đang ở đâu?

Trong PostgreSQL, `market_live_snapshots` có hai dòng: FPT và VNINDEX. Chỉ dòng FPT có các trường khối ngoại/giá trị giao dịch; timestamp lấy dữ liệu là **11:01:58 ngày 07/10/2026**, chưa phải đóng phiên.

Trong `data_pipeline/ScrapersOHLCV/data/stocks/*/live.json`, có bốn snapshot cổ phiếu **CTR, FPT, MSN, NLG**, mỗi mã một row, cùng ngày 07/10/2026, thời điểm lấy từ 09:36 đến 11:01 giờ Việt Nam. Các trường tìm thấy:

- `foreign_buy_volume`, `foreign_sell_volume`: khối lượng mua/bán theo trường nguồn.
- `foreign_room`, `foreign_ownership_ratio`, `foreign_buy_count`: thông tin khác, không thay thế giá trị mua/bán ròng.
- `total_value`, `put_through_value`: hai trường giá trị riêng; cần xác minh quy ước/đơn vị và có bao gồm giao dịch thỏa thuận hay không trước khi dùng.

**Chưa thấy `foreign_buy_value` hoặc `foreign_sell_value` trong nguồn thị trường đã lưu.** Không thể đổi khối lượng ròng thành giá trị ròng chính xác bằng cách nhân giá đóng cửa. Không dùng snapshot lúc 11 giờ làm số tổng kết cả ngày.

Đã quét toàn bộ field paths của 15 raw payload thuộc nguồn MARKET_DATA trong DB, các snapshot `data.json/live.json`, 16 runtime `history.json` và schema SQLite `public-candles.sqlite3`. Payload ENTRADE chỉ có ngày, OHLC, volume, source timestamp. Runtime history không chứa khối ngoại/giá trị giao dịch; schema candles SQLite cũng chỉ lưu nến và provenance. Không quét fixture/demo làm dữ liệu thực.

Code SDK hiện gọi `Market.quote(..., get_all=True)`, nên raw quote có thể chứa các trường bổ sung. `LiveCoordinator` giữ raw row trong overlay RAM, nhưng hợp đồng OHLCV trả ra qua `normalize_quote` chỉ gồm nến và metadata; chưa có chuỗi lưu trữ/báo cáo lịch sử khối ngoại tương ứng. Luồng crawler cũ lưu `live.json` thay thế snapshot mới nhất, không tạo lịch sử ngày cho từng trường.

## Độ mới và tính tương thích nguồn

- Giá cổ phiếu DB đến 29/10; VNINDEX chỉ đến 07/10. Cả 10 mã đều không có chỉ số VNINDEX cho đúng phiên cổ phiếu cuối cùng. Không được so biến động cổ phiếu đến 29/10 với chỉ số kết thúc 07/10 như cùng một kỳ.
- Runtime/file đã lưu được kiểm tra có ngày cuối không muộn hơn 23/10. Luồng lấy mới hiện có trong code chưa được gọi thử; audit này không chứng minh nguồn hiện còn hoạt động hoặc có thể lấy đủ lịch sử khối ngoại.
- Nguồn DB ENTRADE và vnstock_kbs đều `approval_status=PENDING`, `is_enabled=false`. Audit không đổi trạng thái nguồn; các flag này cũng không tự chứng minh đường đọc dữ liệu hiện tại đã chặn nguồn chưa duyệt.
- Giá DB có `price_scale=1000`, `is_adjusted=false`. File crawler có cơ sở giá chưa xác nhận và nến `open`/`pending_reconciliation`; chưa xác minh giá điều chỉnh sự kiện doanh nghiệp.

Đối chiếu **số đóng cửa được lưu** ở các ngày giao nhau cho thấy:

| Mã | Ngày giao nhau | Số ngày khác close | Số ngày khác volume |
|---|---:|---:|---:|
| FPT | 123 | 111 | 1 |
| MBB | 122 | 25 | 0 |
| VCB | 123 | 72 | 0 |

Ví dụ FPT ngày 07/10: DB close `59.7000`, file crawler `60.2`. Đây là chênh lệch số đã quan sát, **chưa kết luận nguồn nào sai**. Chưa xác minh nguyên nhân là làm tròn, điều chỉnh, thời điểm chụp trong phiên hay cập nhật/revision khác. Không ghép hai chuỗi cho phân tích trước khi đối soát.

## Công thức có thể dùng và yêu cầu dữ liệu

Các công thức sau đã kiểm tra được trên dữ liệu hiện có; không phải kết quả kiểm định hiệu quả đầu tư hoặc ngưỡng phân loại xu hướng.

| Chỉ tiêu | Công thức/quy ước | Tối thiểu |
|---|---|---|
| Thay đổi n phiên | `(C[t] / C[t-n] - 1) × 100`, n=1/5/20 | n+1 giá đóng cửa, cùng cơ sở giá |
| SMA20 | Trung bình 20 close, gồm phiên t | 20 close |
| Volume tương đối | `V[t] / mean(V[t-20] ... V[t-1])`; không đưa phiên hiện tại vào mẫu nền | 21 phiên |
| So sánh khối lượng hai kỳ | Trung bình 5 phiên gần nhất so với 5 phiên ngay trước đó | 10 phiên |
| Biên độ phiên (%) | `(H[t] - L[t]) / C[t-1] × 100` | OHLC phiên t, close phiên trước |
| Khối ngoại ròng | Mua trừ bán, tách riêng khối lượng và giá trị; cộng trên cùng khoảng | Lịch sử mua/bán đúng đơn vị, không chỉ snapshot |
| Chênh lệch với chỉ số | Lợi suất cổ phiếu trừ lợi suất chỉ số, cùng hai ngày; đơn vị điểm phần trăm | Cả hai chuỗi có đúng ngày đầu/cuối |

20 phiên có bản ghi không luôn là một tháng lịch: mốc đầu cho return20 đến 29/10 là 01/10 ở tám mã, **24/09 ở ICT**, **29/09 ở ITD**. Chưa đối soát lịch sàn để kết luận ngày vắng là thiếu dữ liệu hay không phát sinh giao dịch. Khi so nhiều mã phải công bố khoảng thực tế hoặc chọn mốc ngày chung theo quy tắc rõ ràng.

Đã tính độc lập bằng Python Decimal và SQL trên **cả 10 mã**, đối chiếu return1/5/20, SMA20 và volume bình quân 20 phiên trước: đạt. SQL ép precision của phép chia để không nhầm chênh lệch làm tròn số học thành lỗi dữ liệu. Hàm `indicators` tại `data_pipeline/ScrapersOHLCV/ohlcv/history/vnstock.py` đã có SMA20/SMA50 và Wilder RSI14 để xem xét tái sử dụng khi triển khai; audit chưa ghép helper này vào backend.

Ví dụ **lịch sử FPT tại 29/10/2026**, không phải nhận định hiện tại: close `52.7000`, return1 `-2.4074%`, return5 `-8.1882%`, return20 `-15.9490%`, SMA20 `57.6400`, volume `12.591.100`, bằng `1.8749` lần bình quân 20 phiên trước. Các con số giữ cơ sở giá chưa điều chỉnh của DB; chưa diễn giải thành kết luận đầu tư.

## Bằng chứng và bước tiếp theo

Receipt: `outputs/sprint5/price-flow-readiness-20261110/audit.json`; hash tại `sha256.json`. Receipt lưu schema, coverage, field paths và metadata, phép tính đối chiếu, độ phủ benchmark và chênh lệch nguồn. Không lưu mật khẩu/DSN hoặc dump raw payload. Script chỉ phục vụ audit nằm ở `.agent-state/audit_price_flow_readiness.py`, chưa phải chức năng ứng dụng.

Thứ tự công việc tiếp theo được đề xuất từ kết quả kiểm tra:

1. Đối soát nguồn/cơ sở giá và quy tắc phiên; cập nhật cổ phiếu và benchmark đến cùng ngày chốt.
2. Kiểm tra nguồn có thể cung cấp **lịch sử ngày** của giá trị giao dịch và khối ngoại; xác nhận đơn vị, matched/put-through và mốc đóng phiên.
3. Lập hợp đồng dữ liệu theo mã/ngày/nguồn/revision; số thiếu giữ thiếu, không thay bằng 0.
4. Triển khai nhóm chỉ tiêu có đủ bằng chứng trước; phần thiếu hiển thị rõ giới hạn. Sau đó mới tích hợp diễn giải năm phần vào luồng người dùng đã chọn.

Chưa gọi nhà cung cấp, chưa ingest/migration, chưa sửa app/DB, chưa triển khai mô hình hoặc chạy app E2E. Workflow công cụ xuất giá cũ vẫn giữ nguyên trạng thái, không được tiếp tục trong audit này.
