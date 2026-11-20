# Phương án chuyển nguồn khi chưa có Open API key

Trạng thái: phương án đã chuẩn bị ngày 10/11/2026; user xác nhận **chưa có nguồn**. Chưa chọn tài khoản/nhà cung cấp thay user, chưa cài Vnstock 6 hoặc sửa luồng đang chạy.

## Mục tiêu

Tiếp tục S5-WBS08.1 và khung phân tích lịch sử giá–khối lượng, đồng thời chuẩn bị đường chuyển khỏi phụ thuộc vào vnstock 4.0.9 cho production. Giữ dữ liệu, provenance, giao diện và các hợp đồng API đang phục vụ người dùng.

## Hai bước thực hiện

1. **Tiếp tục phần lịch sử:** dùng snapshot đã kiểm chứng cho giá, volume và chỉ tiêu tự tính. DNSE chart public đã thử thành công có thể dùng kiểm tra dữ liệu trong phát triển theo giới hạn hiện có; chưa chọn làm nguồn cam kết cho production. Ghi rõ ngày dữ liệu, cơ sở điều chỉnh và phần thiếu. Không gọi khối ngoại/value chưa có lịch sử là đã hoàn thành.
2. **Chọn nguồn chính thức:** DNSE là phương án đề xuất để đánh giá tiếp vì đã có adapter trong repo và tài liệu có OHLC, chỉ số, dữ liệu ngoại. Chưa xác nhận phí, quyền hiển thị/phân phối cho sản phẩm này hoặc coverage lịch sử tương ứng. User cần tự có tài khoản đủ điều kiện, đăng ký dịch vụ và lưu key cục bộ; không gửi key/secret/OTP qua chat.

Nếu user chọn nguồn khác đã có tài khoản, đối chiếu khả năng dữ liệu và quota trước khi chốt implementation. Vnstock 6 là một lựa chọn lớp kết nối/chuẩn hóa; kết nối trực tiếp OpenAPI bằng adapter có sẵn cũng cần được so sánh về phạm vi sửa. Không chỉ nâng dependency rồi giữ nguyên code mặc định KBS.

## Phạm vi ảnh hưởng đã khảo sát

| Điểm tích hợp | Việc cần đối chiếu khi chọn nguồn |
|---|---|
| `data_pipeline/ScrapersOHLCV/ohlcv/sdk/worker.py` | Catalog/history/quote, nguồn mặc định, xác thực, đơn vị, cấu trúc DataFrame |
| `backend/src/market_data/sdk_worker.py` | Batch quote, cổ phiếu và chỉ số, protocol IPC, guard phiên |
| `data_pipeline/ScrapersOHLCV/requirements/vnstock.txt` | Bản SDK và dependency trong môi trường mới riêng |
| `data_pipeline/ScrapersOHLCV/ohlcv/providers/dnse.py` | Tái sử dụng phần ký/giải mã nếu chọn kết nối trực tiếp; hiện chỉ stock/1D, chưa có adapter index/foreign |
| `ohlcv/history/vnstock.py`, `ohlcv/realtime/quote.py`, `backend/src/market_data/history.py`, `validation.py` | Cột, hệ số giá, metadata đơn vị, ngày, trạng thái final/provisional và source ID |
| Test SDK/history/quote/index/collector | Thay fixture theo schema có kiểm chứng, giữ test ngày cũ/đơn vị/volume lùi/rate-limit |

Đây là bản đồ tác động, không phải allowlist cho một job sửa tất cả file. Sau khi chọn nguồn, chia WBS ECC thành các đơn vị nhỏ theo hợp đồng dữ liệu.

## Tiêu chí trước khi tích hợp

- Môi trường nguồn mới tách khỏi môi trường 4.0.9. Không ghi đè file giá/snapshot/DB cũ khi thử.
- Đọc được cùng bộ mã và các chỉ số cần dùng; đánh dấu riêng mã hoặc trường không có quyền/không được hỗ trợ.
- Đối chiếu tên cột, kiểu, ngày/múi giờ, OHLCV, đơn vị giá/volume/value, tình trạng điều chỉnh và provenance. Không chia thêm 1.000 vì giả định nguồn mới giống KBS cũ.
- Giữ ổn định giao diện và response hiện có khi có thể; không bịa dữ liệu để ép schema. Thiếu nguồn/khóa, HTTP 429 và lỗi mạng phải hiện rõ, không che thành mảng rỗng thành công.
- Quote snapshot và lịch sử ngoại/value ngày được coi là hai hợp đồng riêng. Lưu theo mã/ngày/nguồn/revision; chỉ tính ròng tiền khi có mua/bán tiền đúng đơn vị và phạm vi.
- Collector dùng chung, gộp mã/cache, budget theo từng endpoint và retry có giới hạn. Quota giờ/ngày không bị hiểu thành quota burst/phút.
- Worker QA/review đạt cùng receipt thực tế trước approve/integrate. Khi chưa có key, chỉ có thể kiểm code/fixture; chưa thể tuyên bố live source đạt.

## Quay lui và giới hạn

Quay lui code/config về bản trước chỉ bảo đảm khả năng đọc snapshot đã lưu; **không bảo đảm nguồn Vnstock cũ vẫn hoạt động**. Dữ liệu mới từ nguồn khác không tự nhập chồng vào corpus hay chuỗi cũ khi chưa đối soát cơ sở giá.

Hai URL hướng dẫn migration chi tiết của nhà phát hành đã thử đọc nhưng web tool không truy cập được: `/api/skills/migration-assistant/content` và `/api/skills/migration-assistant/reference/contract-check.md`. Không tải/chạy script không được kiểm tra; phương án này dựa trên code thực tế và các trang tài liệu công khai đọc được, chưa tự nhận đã thực hiện checklist của hai tài nguyên đó.

## Việc cần từ user để thử nguồn chính thức

Chọn nguồn và tự đăng ký/quản lý tài khoản. DNSE yêu cầu tài khoản chứng khoán ACTIVE trước khi đăng ký LightSpeed API. Thực hiện đăng ký và nhập khóa trực tiếp trên máy theo hướng dẫn nguồn; chỉ thông báo đã chuẩn bị xong, không gửi giá trị bí mật. [Hướng dẫn đăng ký DNSE](https://developers.dnse.com.vn/docs/guide/intro/register_guide/).

Nguồn tài liệu chuyển đổi: [Vnstock migration](https://www.vnstocks.com/onboard-member/migration), [chọn nguồn v6](https://www.vnstocks.com/docs/vnstock/v6/chon-nguon). Chưa có lựa chọn nguồn hoặc quyền truy cập thì chưa thể nghiệm thu thay luồng lấy dữ liệu production.
