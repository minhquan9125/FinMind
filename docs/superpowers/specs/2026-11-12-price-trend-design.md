# Thiết kế: nhãn xu hướng giá cho trang công ty và chatbot

Ngày: 12/11/2026. Trạng thái: user duyệt 12/11/2026, kèm yêu cầu cào bù VNINDEX đủ 200 phiên trước khi làm.

## Mục đích

User muốn FinMind đưa ra nhận định khách quan về xu hướng giá của một cổ phiếu, dựa trên giá đã lưu, để:

1. Người xem trang công ty thấy ngay cổ phiếu đang tăng, giảm, đi ngang/tích lũy hay chưa rõ xu hướng.
2. Chatbot dùng đúng nhận định đó làm bằng chứng, trích dẫn được, khi trả lời các câu hỏi về xu hướng giá.

Trang và chatbot phải luôn ra cùng một kết luận cho cùng một ngày.

Phạm vi chỉ gồm phần giá. Phần chấm công ty mạnh/yếu theo BCTC do một thành viên khác trong nhóm làm (xem Không làm).

## Mục tiêu

- Nhãn xu hướng do code tính theo quy tắc cố định. Cùng dữ liệu luôn ra cùng nhãn và có test.
- Mỗi nhãn kèm lý do bằng số liệu, ngày tính và nguồn giá.
- Dùng được cho mọi mã có đủ giá ngày trong `price_bars`. Hiện là 30 mã của rổ, đến 11/11/2026.
- Widget trên trang công ty hiện nhãn và lý do.
- Chatbot nhận nhãn như một bằng chứng mới, diễn giải đúng nhãn, không tự nâng hay hạ kết luận.

## Không làm (non-goals)

- Chấm công ty mạnh/yếu theo BCTC: một thành viên khác trong nhóm phụ trách. Yêu cầu user đã nêu cho phần đó: so với các mã cùng ngành và với chính công ty các năm trước; làm trước cho 10 mã đã có BCTC. Thiết kế này chỉ chừa chỗ: bằng chứng `PRICE_TREND` là một loại riêng, để phần BCTC thêm loại bằng chứng của mình mà không phải sửa phần giá.
- Khuyến nghị mua/bán, giá mục tiêu, dự báo.
- Điều chỉnh giá theo sự kiện doanh nghiệp (chia tách, cổ tức cổ phiếu).
- Đổi luồng báo giá hiện tại của chatbot (`MarketResearch._quote`, đọc KBS).
- Giá trong phiên (intraday). Nhãn chỉ dùng nến ngày đã chốt.

## Điều phải tránh (anti-goals)

- LLM tự phán xu hướng hoặc diễn giải mạnh hơn nhãn code đưa ra. Ví dụ code nói "chưa rõ" mà chatbot nói "đang tăng".
- Gán nhãn chắc chắn khi dữ liệu không đủ, hoặc khi cửa sổ tính có thể bị méo vì giá chưa điều chỉnh.
- Trang và chatbot nói hai kết luận khác nhau cho cùng một ngày.

## Ràng buộc

- DB thật là VPS qua tunnel `127.0.0.1:15433/finmind`. Phần nhãn xu hướng chỉ đọc. Ghi duy nhất là bước 0 (thêm phiên VNINDEX cũ).
- Giá ENTRADE: `price_scale=1000`, `is_adjusted=false`. Nguồn đang PENDING, nên nhãn luôn kèm cảnh báo nguồn chưa duyệt.
- Không chạm vào chỉnh sửa của user trong `backend/src/graph/graph_store.py`. Không commit/push khi user chưa bảo.
- Prompt hiện có (`b1_answering/evidence/grounded.py`) đã cấm khuyến nghị mua/bán và dự báo chắc chắn. Giữ nguyên.

## Cách làm đã chọn

**Cách đã chọn: tính khi có người hỏi, từ DB** (cùng kiểu với widget phân tích giá đang chạy).

Mỗi lần mở trang hoặc hỏi chatbot, backend đọc khoảng 260 phiên gần nhất từ `price_bars` (kèm RSI14 trong `price_indicators`, VNINDEX trong `market_index_bars`) rồi tính nhãn. Không thêm bảng, không cần migration.

Các cách đã cân nhắc:

- **B. Đọc từ file JSON trong repo:** bị loại vì tạo hai nguồn dữ liệu và file không đi theo khi deploy. Cách này chỉ đáng cân nhắc cho dữ liệu BCTC, mà BCTC đã ra ngoài phạm vi đợt này.
- **C. Tính sẵn lúc 15:35 và lưu bảng:** để dành cho sau. Lợi thế (nhanh, có lịch sử nhãn) chưa cần với 30 mã. Nhược điểm là phải thêm migration, và kết quả cũ trong khoảng giữa hai lần tính.

## Quy tắc tính (phần của thiết kế; ngưỡng là đề xuất của Claude)

**Dữ liệu vào:**
- Tối đa 260 phiên gần nhất có `trade_date <= as_of` của một mã.
- Một mã phải có đúng một nguồn và một cơ sở giá (cùng cách kiểm như `analysis.py` hiện tại).
- Dữ liệu không nhất quán thì trả lỗi, không chọn bừa một dòng.

**Ba khung thời gian:**

| Khung | Số phiên `h` | Đo độ dốc qua `L` phiên | Biên độ tối đa để coi là đi ngang `R` |
|---|---:|---:|---:|
| Ngắn hạn | 20 | 5 | 8% |
| Trung hạn | 60 | 15 | 15% |
| Dài hạn | 200 | 50 | 30% |

**Các đại lượng tính cho mỗi khung:**
- `sma` = trung bình giá đóng cửa `h` phiên.
- `slope` = (`sma` hôm nay − `sma` của `L` phiên trước) / `sma` của `L` phiên trước.
- `ret` = lợi suất `h` phiên.
- `range` = (đỉnh cao nhất − đáy thấp nhất trong `h` phiên) / đáy thấp nhất.

**Nhãn** (bốn nhãn đầu loại trừ nhau, xét theo thứ tự):

1. `INSUFFICIENT_DATA` (Chưa đủ dữ liệu): có ít hơn `h + L` phiên.
2. `UP` (Tăng): giá đóng cửa > `sma`, `slope` > +1% và `ret` > 0.
3. `DOWN` (Giảm): giá đóng cửa < `sma`, `slope` < −1% và `ret` < 0.
4. `SIDEWAYS` (Đi ngang/tích lũy): `range` ≤ `R` và |`slope`| ≤ 1%.
5. `UNCLEAR` (Chưa rõ xu hướng): mọi trường hợp còn lại.

Nhãn hiển thị là "Đi ngang/tích lũy". Code không khẳng định có dòng tiền gom hàng; khối lượng chỉ là dữ kiện đi kèm.

**Cảnh báo giá chưa điều chỉnh:**
- Nếu trong `h` phiên có một ngày giá đóng cửa đổi vượt biên độ sàn (HOSE 7%, HNX 10%, UPCOM 15%; lấy theo `companies.exchange`, cộng 0,5 điểm % dung sai), khung đó bị coi là có thể méo do sự kiện doanh nghiệp.
- Khi đó nhãn của khung chuyển thành `UNCLEAR`, kèm lý do `possible_corporate_action:<ngày>`.

**Dữ kiện đi kèm** (không tạo nhãn, chỉ để diễn giải):
- Đỉnh/đáy 52 tuần (tối đa 250 phiên) và khoảng cách % từ giá hiện tại tới mỗi mức. Bỏ trống nếu cửa sổ có cờ sự kiện doanh nghiệp.
- RSI14 phiên `as_of`, lấy từ `price_indicators`. Không có thì để NULL. Chỉ báo con số, không gắn chữ "quá mua/quá bán".
- Khối lượng trung bình 20 phiên so với 60 phiên.
- So với chỉ số của sàn (xem bước 0): lợi suất chỉ số cùng khung, tính trên đúng các ngày cổ phiếu có giao dịch. Nếu VNINDEX vẫn thiếu phiên sau bước 0, khung đó ghi "chưa đủ dữ liệu chỉ số".

**Số học:** Decimal, làm tròn 4 chữ số HALF_UP, giống `analysis.py`.

## Bước 0: cào bù lịch sử VNINDEX, HNXINDEX, UPCOMINDEX (user yêu cầu)

VPS hiện có 148 phiên VNINDEX. Số phiên đang có của HNXINDEX và UPCOMINDEX chưa kiểm (tunnel đang tắt khi viết). Khung 200 phiên cần ít nhất khoảng 250 phiên để vừa so sánh lợi suất, vừa đo độ dốc. Cả ba chỉ số đều được cào bù tới mức đó.

**Chỉ số so sánh theo sàn của mã:** HOSE so với VNINDEX, HNX so với HNXINDEX, UPCOM so với UPCOMINDEX. Hiện cả 30 mã đều trên HOSE.

**Chỉ số chưa có dòng nào:** được nạp lần đầu, không có phiên chồng lấp để đối chiếu. Biên bản phải ghi rõ đây là lần nạp đầu.

- **Nguồn:** giữ nguyên nguồn đang lưu là vnstock_kbs qua SDK worker; không trộn nguồn khác (ví dụ ENTRADE index).
- **Lấy dữ liệu:** worker hiện chỉ lấy 180 ngày. Thêm tham số số ngày (mặc định 180, tối đa 400), và nới kiểm tra ngày trong `history.normalize_history` tương ứng.
- **Ghi:** chỉ thêm các phiên **trước** phiên đầu tiên đang lưu.
  - Mọi phiên chồng lấp phải khớp chính xác với nguồn; lệch một phiên là dừng, không ghi gì.
  - Không sửa dòng cũ, kể cả SMA/RSI của dòng cũ.
  - Phiên thêm mới có SMA20/SMA50/RSI14 tính từ chính chuỗi được thêm.
- **Thực hiện:** thêm chế độ bù lịch sử cho VNINDEX vào `backend/scripts/refresh_market_prices.py`, cùng cơ chế xem trước / `--apply` và biên bản trong `outputs/market-refresh/`. Diễn tập trên PostgreSQL thử 15434 trước, rồi mới chạy trên VPS.
- **Thứ tự:** bước này xong trước rồi mới làm nhãn xu hướng. Nếu KBS không trả đủ 250 phiên, ghi rõ số phiên thực có và khung 200 vẫn báo thiếu đến khi đủ.

## Hợp đồng dữ liệu

`GET /api/market-data/stocks/{symbol}/analysis` thêm khối `trend`. Trang đang gọi endpoint này nên không cần gọi thêm request. `trend` tính bằng truy vấn riêng; lỗi ở `trend` không làm hỏng phần phân tích cũ.

```json
"trend": {
  "as_of": "2026-11-11",
  "source": {"name": "ENTRADE", "approval_status": "PENDING", "is_adjusted": false},
  "horizons": {
    "20":  {"label": "DOWN", "sessions": 20, "sma": "...", "slope_percent": "...", "return_percent": "...",
            "range_percent": "...", "close_vs_sma_percent": "...", "index_return_percent": "...",
            "reasons": ["close_below_sma", "sma_falling", "negative_return"]},
    "60":  {...},
    "200": {...}
  },
  "context": {"high_52w": "...", "high_52w_date": "...", "low_52w": "...", "low_52w_date": "...",
              "from_high_percent": "...", "from_low_percent": "...", "rsi14": "...",
              "volume20_vs_volume60": "..."},
  "warnings": ["prices_source_not_approved", "unadjusted_prices", "possible_corporate_action:2026-06-12"]
}
```

`reasons` là các mã cố định, để frontend và chatbot dịch ra câu tiếng Việt.

## Trang công ty

Trong widget "Phân tích giá & dòng tiền" thêm mục "Xu hướng giá", đặt trên cùng:
- Ba thẻ Ngắn hạn / Trung hạn / Dài hạn, mỗi thẻ có nhãn màu và hai đến ba lý do bằng số.
- Một dòng dữ kiện: đỉnh/đáy 52 tuần, RSI14, khối lượng.
- Dòng nhắc cố định "Mô tả từ dữ liệu giá đã lưu, không phải khuyến nghị".

Theo thiết kế giao diện hiện có (`PriceAnalysis.jsx`, `StatusBadge`).

## Chatbot

- Thêm loại bằng chứng `PRICE_TREND`, provider `finmind_db`, trong `b1_answering/evidence/market_contract.py::feed_item`.
- Đoạn văn (passage) của bằng chứng do code sinh, tiếng Việt, gồm nhãn từng khung, số liệu, ngày tính, nguồn và cảnh báo. LLM trích dẫn đoạn này.
- `MarketResearch._analysis` (luồng `MARKET_ANALYSIS`, đã nhận các câu có "xu hướng", "dạo này", "tăng", "giảm"…) thêm bằng chứng `PRICE_TREND` cạnh giá hiện tại và tin FireAnt. `_lookup` đang chạy đồng bộ trong thread, còn truy vấn DB là async, nên lấy `trend` trong `lookup` (async) trước khi chuyển sang thread.
- Prompt `MARKET_ANALYSIS` trong `grounded.py` thêm một câu: nêu đúng nhãn xu hướng code đưa ra; không đổi nhãn; nếu nhãn là "Chưa rõ" hoặc "Chưa đủ dữ liệu" thì nói đúng như vậy.
- Không có `trend` (mã không có giá DB, DB lỗi) thì luồng chạy như hiện tại, không báo lỗi cả câu trả lời.

## Kiểm thử

- Test đơn vị cho từng nhãn, ranh giới ngưỡng, cờ sự kiện doanh nghiệp, thiếu dữ liệu, VNINDEX thiếu phiên.
- Test API: khối `trend` có mặt; lỗi `trend` không làm hỏng phần phân tích.
- Test chat: có bằng chứng `PRICE_TREND` trong evidence pack; passage chứa đúng nhãn.
- Kiểm thật trên VPS (chỉ đọc) cho 30 mã, đối chiếu với một phép tính SQL độc lập cho ít nhất 3 mã.
- Kiểm trình duyệt `/companies/FPT` ở rộng 1440 và 390.

## Phần để người làm tự quyết

- Cấu trúc hàm và tên module, ví dụ `market_data/trend.py` cạnh `analysis.py`.
- Câu chữ tiếng Việt cho từng mã lý do.
- Màu nhãn, theo `StatusBadge` có sẵn.

## Các quyết định do Claude đề xuất (user cần duyệt)

- Bộ ngưỡng: 20/60/200 phiên, độ dốc 1%, biên độ đi ngang 8/15/30%.
- Coi ngày vượt biên độ sàn là dấu hiệu sự kiện doanh nghiệp, và khi đó hạ nhãn xuống "Chưa rõ".
- Gắn `trend` vào endpoint `analysis` có sẵn, thay vì tạo endpoint mới.
- Áp dụng cho cả 30 mã có giá, không chỉ 10 mã.
- Không đổi luồng báo giá KBS của chatbot trong đợt này.
