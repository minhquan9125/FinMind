# Kiểm tra luồng tài chính thực tế — 20/10/2026

> Cập nhật: collector đã được sửa và kiểm tra lại bằng dữ liệu vừa cào của 10 mã.
> Xem [kết quả mới](financial-flow-fresh-data-20261020.md). Nội dung dưới đây là
> kết quả kiểm tra trước khi sửa collector.

## Kết luận

Năm sửa đổi chunker không chặn bộ dữ liệu thực tế đã kiểm tra. Tuy nhiên chưa thể
chốt luồng cào mới đến tìm kiếm: collector hiện không khởi chạy được vì lỗi thụt
lề ở dòng đầu tiên. Không sửa collector trong lượt kiểm tra này.

| Chặng | Thao tác thực hiện | Kết quả |
| --- | --- | --- |
| Khởi chạy collector | Biên dịch Python file collect_financial_data.py | FAIL: IndentationError, unexpected indent, dòng 1 |
| Dữ liệu normalized đã cào → clean | Chạy clean_file thật cho 10 công ty, ghi bản thử trong FinancialCleaner/.tmp/flow-check | PASS |
| Clean → bộ đọc nhập DB | Chạy read_input thật và CLI import_clean_financials.py mặc định dry-run | PASS: 419 kỳ/báo cáo, 72.096 giá trị |
| Đầu vào theo cấu trúc importer → chunk | Dựng đúng report/metric/observation ID theo importer, tạo chunk trong bộ nhớ | PASS cho cả 10 công ty |
| Supabase thực tế → chunk | Đọc FINANCIAL_SQL trong transaction READ ONLY REPEATABLE READ | PASS: 419 báo cáo, 72.096 observations, 13.003 chunk |
| Kiểm tra nội dung chunk | So đủ mã dòng, không lặp ID chunk, dựng lại từ locator và kiểm tra hash cho toàn bộ chunk | PASS ở cả nhánh file và nhánh Supabase |
| Kích thước chunk từ dữ liệu thật | Đếm chunk trên 130 từ | 0 ở cả hai nhánh |
| Ghi nhập mới → embedding → tìm kiếm | Không chạy trong lượt này | Chưa kiểm chứng |

Các mã đã kiểm tra: BID, CMG, CTG, ELC, FPT, ICT, ITD, MBB, TCB, VCB.
Snapshot Supabase: 2026-10-20 08:36:01.860058+00:00.

## Giới hạn và ảnh hưởng

- Không gọi API để cào mới do collector chưa qua bước biên dịch. Dữ liệu đầu vào
  cho lượt replay là file normalized đang có trên máy, không phải dữ liệu vừa cào.
- Không INSERT/UPDATE/DELETE hoặc thay schema trên Supabase; chưa chạy importer
  chế độ apply, không gọi embedding hoặc cập nhật chỉ mục tìm kiếm.
- Các kiểm tra mới không phát hiện kỳ/công ty mâu thuẫn hoặc observation trùng
  trong bộ dữ liệu đã kiểm tra. Điều này không đảm bảo mọi dữ liệu cào tương lai hợp lệ.
- Cảnh báo đơn vị làm thay đổi nội dung, cách đóng gói và ID chunk mới; số chunk
  ở đây không phải số vector đã ghi trên database. Không so trực tiếp số chunk
  giữa các phiên bản dựng chữ hoặc giữa file và DB nếu tên/metadata nguồn khác.
- CLI chunk_from_supabase.py bắt lỗi theo nguồn. Nếu nguồn tài chính lỗi, nguồn
  đó bị bỏ qua trong dry-run; chế độ apply dừng trước khi ghi khi có nguồn đọc lỗi.

## Tái kiểm tra

Từ thư mục FinMind, chạy bằng Python của môi trường dự án:

```powershell
.\.venv\Scripts\python.exe -X utf8 backend/scripts/check_financial_flow.py
.\.venv\Scripts\python.exe -X utf8 backend/scripts/import_clean_financials.py
```

Script đầu chỉ đọc Supabase, tạo bản clean thử riêng và kết quả tại
`backend/.tmp/financial-flow-check/result.json`. Nếu collector lỗi cú pháp,
script vẫn kiểm tra các chặng độc lập nhưng trả exit code 1 để không báo nhầm
toàn luồng thành công. Lượt chạy đầu đã phát hiện lỗi cú pháp bằng py_compile
riêng; sau đó script được bổ sung kiểm tra này tự động.

Bước cần làm để kiểm tra toàn luồng tiếp: sửa lỗi collector, cào mới ra thư mục
thử, rồi kiểm chứng nhập và tìm kiếm trên môi trường thử phù hợp.
