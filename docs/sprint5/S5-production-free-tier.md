# Free tier, quota và khả năng phục vụ nhiều người dùng

Ngày tra cứu: **10/11/2026**. Phạm vi: tài liệu chính thức, giấy phép đi kèm bản cài và mô phỏng collector hiện có. Không đổi SDK, key, cấu hình hoặc dữ liệu ứng dụng.

## Kết luận cho FinMind

Có thể giảm tải nguồn bằng collector dùng chung và cache theo mã/ngày. Tuy nhiên **chưa thể kết luận toàn bộ ứng dụng production nhiều người dùng được miễn phí hoặc đã có quyền phân phối dữ liệu**. Cần tách bốn vấn đề: phiên bản Vnstock, quota nguồn, quota do code tự đặt và quyền sử dụng/hiển thị dữ liệu.

Với báo cáo lịch sử ngày/tuần, dữ liệu đã lưu và chỉ tiêu tính sẵn có thể phục vụ nhiều lượt đọc mà không gọi nguồn mỗi lần người dùng hỏi. Quota chủ yếu phụ thuộc số mã, loại dữ liệu và chu kỳ cập nhật; số người dùng chỉ làm tăng lượt đọc ứng dụng nếu việc thu thập đã được gộp đúng.

## Vnstock: số cũ và chính sách mới khác nhau

| Dòng phiên bản | Điều xác minh được | Không được suy ra |
|---|---|---|
| Bản 4.x cũ | Tài liệu nhà phát hành trên PyPI 4.0.3 nêu Guest **20 request/phút**, Community đăng ký miễn phí **60/phút** | Không coi đây là quota hiện hành của v6 hoặc cam kết từ KBS |
| Bản đang cài 4.0.9 + vnai 2.6.3 | Source vnai có Guest 20/phút; worker crawler xóa `VNSTOCK_API_KEY` trong child, chạy theo cấu hình guest hiện có | Đặt key ở môi trường cha chưa chắc chuyển worker này sang Community |
| Thế hệ 5 | Tài liệu tham chiếu riêng có quota/nhóm quyền khác, và đã gắn nhãn bản cũ | Không ghép các bảng v5 vào v6 hoặc 4.0.9 |
| Thế hệ 6 | `Market`/`Reference` dùng Open API key của nguồn; tài liệu ghi không áp hạn mức lượt gọi từ phía Vnstock | Không có nghĩa nguồn không giới hạn hoặc mọi quyền sử dụng là miễn phí |

Nguồn số legacy: [PyPI của nhà phát hành, vnstock 4.0.3](https://pypi.org/project/vnstock/4.0.3/). Nguồn cơ chế mới: [Vnstock thế hệ 6](https://www.vnstocks.com/docs/vnstock/v6/gioi-thieu), [vnstock-oapi](https://www.vnstocks.com/docs/vnstock-oapi/gioi-thieu).

Tài liệu migration hiện tuyên bố vnstock 4.x, vnstock_data 3.x và thế hệ 5 ngừng xác thực từ **10/11/2026**. Điều này không khớp hoàn toàn với quan sát trực tiếp: smoke test bản 4.0.9 trong cùng ngày đã lấy được dữ liệu. Giữ cả hai bằng chứng; chưa xác định nguyên nhân khác biệt, và không lấy lần chạy được làm bằng chứng bản cũ tiếp tục được hỗ trợ cho production. [Thông báo chuyển thế hệ 6](https://www.vnstocks.com/onboard-member/migration).

V6 kết nối giá, chỉ số, khớp lệnh và dòng tiền qua nguồn do người dùng chọn; khả năng thực tế phụ thuộc nguồn, key và quyền ở nguồn đó. Phần kết nối cộng đồng được mô tả miễn phí cho cá nhân, học tập và nghiên cứu. Chưa cài hoặc chạy v6 trong audit này, không coi số lượng hàm trên website là quyền đã có trên máy.

## DNSE: quota công bố cho OpenAPI có key

Các giới hạn sau áp dụng **theo API key và endpoint**, không áp cho chart public ẩn danh. Tài liệu dùng đơn vị giờ/ngày; không công bố trần burst theo phút tại bảng này.

| Endpoint dữ liệu | Request/giờ | Request/ngày |
|---|---:|---:|
| OHLC | 50.000 | 100.000 |
| Foreign Trading | 10.000 | 100.000 |
| Market Index | 1.000 | 10.000 |
| Working Dates | 100 | 1.000 |

HTTP 429 là vượt rate; vượt quota ngày trả 403 theo tài liệu. Theo dõi các header quota và reset. **Không chia quota giờ cho 60 rồi coi kết quả là giới hạn burst/phút được bảo đảm.** [DNSE Rate Limits](https://developers.dnse.com.vn/docs/guide/ratelimits/).

WebSocket: tối đa **10 connections/user**, **200 streams/connection**, mỗi kết nối tối đa **8 giờ**. Đây là giới hạn tài khoản/kết nối nguồn, không phải 10 người dùng cuối của FinMind. [DNSE Market Data WebSocket](https://developers.dnse.com.vn/docs/guide/market-data/connect/).

Đăng ký OpenAPI cần tài khoản DNSE ACTIVE và nhận key/secret. Các trang chính thức đã đọc chưa đủ để xác nhận giá bằng 0 cho cấu hình production này hoặc quyền hiển thị lại dữ liệu cho người dùng bên ngoài. Quota kỹ thuật được công bố không tự xác nhận hai quyền đó. [DNSE FAQ](https://developers.dnse.com.vn/docs/guide/faq/), [đăng ký dịch vụ](https://developers.dnse.com.vn/docs/guide/intro/register_guide/).

## DNSE public và KBS qua thư viện

Đường `api.dnse.com.vn/chart-api/v2/ohlcs/stock` đã thử được mà không dùng key, nhưng chưa tìm thấy quota/SLA production chính thức cho chính endpoint này. Không áp bảng 50.000/giờ của signed OpenAPI sang đây. Tương tự, hạn mức Vnstock 4.x không phải cam kết quota độc lập của KBS. Không coi endpoint công khai là quyền truy cập không giới hạn.

## Giới hạn thật do code hiện tại đặt

- Chart server trong ScrapersOHLCV chỉ bind **127.0.0.1**, là công cụ cục bộ. `RateBudget` dùng chung 16 credit/60 giây, cách lượt ít nhất 5 giây; quote tốn 1 credit, history/catalog dự phòng 3 credit. Nhịp 5 giây tạo khoảng 12 lượt/phút trước khi tính credit bổ sung.
- `LiveService.quote` của chart xử lý một mã mỗi lần gọi; `live.json` thay snapshot mới nhất. Không có gộp nhiều mã vào một quote trong worker của folder này.
- Backend chính đã có `LiveCoordinator`: gộp mã người xem, gọi một batch và cho lượt đọc dùng overlay/cache. Có giới hạn 100 mã khác nhau và 1.000 đăng ký viewer; đây là chặn kỹ thuật, không phải kết quả benchmark số người dùng đồng thời.
- Backend vẫn có ngân sách 16 lượt/60 giây và khoảng cách tối thiểu theo `poll_seconds` mặc định 5; cache lịch sử/manual khoảng 60 giây. History, quote, index, retry và lỗi cùng ảnh hưởng ngân sách.
- Collector hiện nằm trong một process; khóa file giữ một collector trên cùng root/máy. Chạy nhiều Uvicorn worker hoặc nhiều máy không tự biến cache/limiter thành trạng thái dùng chung giữa các máy.

Các nguồn code: `ohlcv/realtime/session.py`, `ohlcv/app/server.py`, `ohlcv/sdk/worker.py`, `backend/src/market_data/live.py`, `backend/src/market_data/app.py`, `backend/src/market_data/sdk.py`.

## Mô phỏng tình huống nhiều người cùng xem

Chạy bộ điều phối **thật trong code**, thay fetch bằng SDK giả và đồng hồ kiểm soát. Trong 60 giây, mỗi viewer gia hạn đăng ký mỗi 5 giây, cùng xem 10 mã. Sau đó đọc dữ liệu từ cache theo số viewer.

| Đăng ký viewer | Mã khác nhau | Chu kỳ | Fetch batch trong 60 giây | Fetch thêm do lượt đọc |
|---:|---:|---:|---:|---:|
| 100 | 10 | 5 giây | **12** | **0** cho 100 lượt đọc |
| 1.000 | 10 | 5 giây | **12** | **0** cho 1.000 lượt đọc |

Nếu mỗi viewer tự gọi nguồn mỗi 5 giây, nhu cầu tương ứng là 1.200 hoặc 12.000 lượt/phút. Batch/cache giảm số lần fetch trong mô phỏng; một lần fetch SDK vẫn có thể sinh thêm HTTP request khi chia trang, chia nhóm hoặc retry.

Đây **không phải** kiểm thử HTTP đồng thời, CPU/RAM, đăng nhập, latency/SLA hoặc key nguồn thật dưới tải lớn. Không thể kết luận server chịu được 1.000 user chỉ từ mô phỏng này. Bộ test `backend.tests.test_market_data_live` cũng chạy lại: **16/16 đạt**.

Với nhánh dữ liệu ngày, có thể tải 10 mã và vài index một lần theo lịch thay vì lặp theo viewer. Nếu cần 5 giây, phải gộp/cached tập mã đang xem và theo dõi quota thực; với OpenAPI không hỗ trợ batch, lịch cập nhật phải tính theo từng mã/endpoint. WebSocket phù hợp cho stream khi nguồn và quyền sử dụng cho phép.

## Quyền dùng cho production

Giấy phép đi kèm bản cài 4.0.9 mang mã `license-2026.09`: giấy phép phần mềm không cấp quyền dữ liệu bên thứ ba; sản phẩm có giá trị chính là cấp khả năng truy xuất dữ liệu thị trường cho người khác cần thỏa thuận riêng. FinMind cần xác định phạm vi sản phẩm và quyền dữ liệu thực tế, không suy ra quyền phục vụ nhiều người từ việc API trả HTTP 200.

Đường giấy phép web cũ hiện redirect sang `license-2026.11`, trang ghi **hiệu lực 30/11/2026**, chưa tới ngày áp dụng tại thời điểm tra cứu. Không viện bản mới này như điều khoản đã có hiệu lực ngày 10/11. [Trang giấy phép và ngày hiệu lực](https://www.vnstocks.com/policies/license). Bản tóm tắt hiện cài ở `vnstock-4.0.9.dist-info/licenses/LICENSE.md` vẫn được giữ nguyên.

Kết luận: ứng dụng có thể được thiết kế tiết kiệm lượt gọi cho nhiều viewer, nhưng **chưa xác nhận production công khai nhiều người dùng có thể chạy miễn phí hoàn toàn**. Ưu tiên nguồn có key/hạn mức/quyền rõ ràng, collector chung, dữ liệu lưu và cache. Các quyền và phí còn chưa rõ phải được xác minh với bên cung cấp trước khi chọn làm nền production.

## Receipt

`outputs/sprint5/production-source-limits-20261110/collector-simulation.json` và `existing-batch-tests.txt`. Không gửi tải dồn tới nhà cung cấp, không đổi key, không cài/nâng thư viện hoặc chuyển kiến trúc trong bước đọc tài liệu này.
