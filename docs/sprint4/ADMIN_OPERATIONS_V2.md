# Admin — vận hành mở rộng (12/11/2026)

Tài liệu cho các tính năng admin thêm sau `ADMIN_OPERATIONS.md`. Mọi thao tác yêu cầu vai trò `ADMINISTRATOR`.

## Tự động hóa tin tức

Trang **Thu thập & duyệt**, phần Nguồn FireAnt, có hai ô mới (mặc định tắt):

| Ô | Việc tự chạy sau khi thu thập và duyệt |
| --- | --- |
| Tự động tạo chunk, vector và lưu database | Tạo chunk và vector cho bài đã duyệt, ghi vào DB. Phiên mới **chưa** đổi corpus Chat đang dùng |
| Tự động chuyển corpus cho Chat | Như trên, rồi chuyển Chat sang phiên mới |

Nút **Chạy toàn bộ ngay** chạy chuỗi này một lần. `scripts/run_admin_scheduler.py` chạy nó mỗi ngày khi bật lịch hằng ngày
(script tự nạp quyền ghi từ `backend/.env.operator`). Bài còn cần OCR không bao giờ được lưu. Kết quả ghi trên lần thu thập
(`details.pipeline`) và nhật ký kiểm toán. Có thể xóa bài đã duyệt (từng bài hoặc hàng loạt); bài đã xóa không bị thu thập lại.

## Phiên kho dữ liệu

Trang **Phiên bản kho dữ liệu** đọc PostgreSQL. Thao tác:

- **Chuyển Chat sang phiên này**: chỉ đổi con trỏ phiên phục vụ (quay về phiên cũ khi lần cập nhật mới lỗi). Chỉ nhận phiên
  `FROZEN`, chỉ mục `ACTIVE`, có manifest.
- **Lưu trữ / Khôi phục**: đổi `FROZEN` ↔ `ARCHIVED` bằng kết nối ghi. Không lưu trữ được phiên đang phục vụ hoặc phiên mặc định
  `RESEARCH_CORPUS_VERSION_ID`.
- Phiên mới chỉ được tạo bởi luồng Thu thập → lưu database; không có thao tác "đóng băng" riêng vì phiên luôn được tạo ở trạng thái đóng băng.

### Dùng chung giữa nhiều máy

Hàng đợi (job, bài, nhật ký) vẫn là SQLite trên từng máy. Phần cần chung là **phiên Chat đang phục vụ**, nay được lưu trong bảng
`public.admin_serving_corpus`. Máy nào kích hoạt hoặc chuyển phiên thì ghi vào bảng; mọi backend đọc lại sau tối đa 15 giây.
Chưa có bảng hoặc DB không với tới được thì dùng con trỏ cục bộ như trước.

Tạo bảng một lần, bằng tài khoản chủ bảng (`finmind_team`, chuỗi trong `.env.operator`):

```powershell
psql "<chuỗi operator>" -f docker/postgres/init/095_admin_serving_corpus.sql
```

File chỉ thêm một bảng, bật RLS, cấp **chỉ đọc** cho `finmind_app_runtime` và `finmind_graph_reader`. Gỡ bằng `DROP TABLE public.admin_serving_corpus;`.

## Cấu hình

- **Giới hạn trả lời của Chat** (trang Cấu hình): sửa 5 giá trị, mỗi giá trị có khoảng hợp lệ, lưu theo phiên bản kèm lý do, áp dụng từ câu hỏi kế tiếp,
  không cần khởi động lại. Không sửa được model và `max_cost_usd = 0` (khóa free tier).
- **Xoay khóa Gemini**: đặt thêm khóa của nhóm vào `GEMINI_API_KEYS` (cách nhau bằng dấu phẩy hoặc xuống dòng). Khóa hết hạn mức hoặc bị từ chối thì chuyển
  sang khóa kế tiếp trong cùng câu hỏi và tạm nghỉ khóa đó (90 giây, tăng gấp đôi đến 1 giờ; khóa bị từ chối nghỉ 6 giờ). Chỉ chuyển khi yêu cầu bị từ chối **trước khi**
  sinh nội dung; lỗi timeout hoặc 5xx không chuyển để không tính hai lần. Trạng thái xem ở trang Cấu hình, không hiển thị khóa.
  Chỉ dùng khóa nhóm được phép dùng: dùng nhiều khóa miễn phí để vượt giới hạn của nhà cung cấp có thể vi phạm điều khoản của họ.

### Thêm khóa Gemini từ trang web

Trang Cấu hình, mục "Xoay khóa Gemini", cho thêm, thử, tắt/bật và xóa khóa mà không cần sửa file hay khởi động lại backend.

- Khóa là **chỉ ghi**: API và giao diện chỉ trả tên gợi nhớ, 4 ký tự cuối và trạng thái. Nội dung khóa không xuất hiện trong phản hồi, lỗi, nhật ký kiểm toán hay log.
- Khi thêm, backend kiểm tra khóa với Google bằng lệnh đếm token (không sinh nội dung). Google từ chối thì không lưu; khóa hợp lệ nhưng đang hết hạn mức vẫn được lưu.
- Khóa được mã hóa (Fernet, khóa dẫn xuất từ `GEMINI_KEYS_SECRET`) trong cơ sở dữ liệu cục bộ của backend (`outputs/admin-ingestion`). Phải đặt `GEMINI_KEYS_SECRET`
  (16 ký tự trở lên, ngẫu nhiên) trong `backend/.env`. Không dùng `JWT_SECRET_KEY` vì giá trị mặc định của nó nằm công khai trong mã nguồn.
  Đổi `GEMINI_KEYS_SECRET` thì các khóa đã lưu không đọc được nữa (hiện "không đọc được", không làm hỏng Chat): xóa và thêm lại.
- Có hiệu lực từ câu hỏi kế tiếp. Ngoại lệ: nếu lúc khởi động Chat chưa có khóa nào (kể cả trong `.env`) thì cần khởi động lại một lần để bắt đầu dùng Gemini.
- Mọi thao tác thêm, tắt/bật, xóa ghi vào nhật ký kiểm toán (ai, khi nào, tên gợi nhớ). Tối đa 20 khóa. Khóa trong `.env` và khóa thêm từ web nằm chung một vòng xoay, khóa trùng bị từ chối.
- Khóa lưu trên máy chạy backend và được mã hóa, nhưng không thay thế được kho bí mật chuyên dụng. Mọi tài khoản ADMINISTRATOR đều thêm và xóa được khóa.

## Quan sát và đánh giá

- Mỗi lượt Chat ghi thêm: tuyến xử lý, số lần gọi graph/vector, loại bằng chứng, kết quả kiểm tra nguồn của B1 và lý do khi bản nháp Gemini bị bác.
  Hiển thị ở trang Truy vấn và ba thẻ Graph, Evidence Gate, Verifier của Tổng quan. B3 Evidence Gate và Answer Verification đang **tắt** trong cấu hình và được hiển thị như vậy.
- Trang **Đánh giá chất lượng** (`/admin/evaluation`) chạy bộ câu hỏi chuẩn (`bo cau hoi cua huyen 40 cau.md`) qua Chat thật, chấm theo số liệu, ngày và mã trong
  đáp án chuẩn. Mỗi câu là một lượt Chat thật tính vào hạn mức. Điểm chỉ để người kiểm tra xem nhanh.

## Job dữ liệu

Trang **Job dữ liệu** có thể khởi chạy lần chạy **fixture** (không ghi DB, không duyệt ứng viên) từ hai tệp JSON: manifest đã ghim và danh sách bài viết.
Thư mục kết quả do máy chủ tự đặt tên (`web-fixture-...`), mỗi lần một job. Chạy toàn manifest (`full`) vẫn chỉ qua dòng lệnh vì cần biên nhận gate.
