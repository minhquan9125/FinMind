# Sửa collector và kiểm tra dữ liệu vừa cào — 20/10/2026

## Thay đổi

`data_pipeline/financial_data/collect_financial_data.py` có một lớp thụt lề bốn
khoảng trắng dư bao quanh toàn bộ module. Đã bỏ lớp này, giữ nguyên logic gọi
API, retry, kiểm tra nguồn và ghi file. `git diff --ignore-all-space` không có
khác biệt. CLI `run_financial_pipeline.py --help` import và chạy thành công.

Thêm `backend/scripts/check_new_financial_flow.py` để cào mới vào thư mục thử
riêng, chạy các hàm clean/display và bộ đọc clean thật, dựng các dòng theo
quy tắc ID của importer, rồi kiểm tra chunk. Không dùng lại file cũ để thay
thế nguồn thất bại; mã nào không cào đủ các nguồn sẽ được đánh dấu FAILED.

## Kết quả dữ liệu mới

Thời gian gọi API: 2026-10-20 08:41:08–08:41:33 UTC.
Nguồn trực tiếp: Entrade cho giá, Vietcap cho ba báo cáo tài chính và ratios.

| Mã | Báo cáo theo hợp kỳ | Giá trị tài chính giữ sau clean | Chunk | Kết quả |
| --- | ---: | ---: | ---: | --- |
| VCB | 43 | 7.894 | 1.428 | PASS |
| BID | 43 | 7.894 | 1.504 | PASS |
| CTG | 43 | 7.894 | 1.428 | PASS |
| MBB | 43 | 7.892 | 1.428 | PASS |
| TCB | 43 | 7.844 | 1.420 | PASS |
| FPT | 43 | 6.720 | 1.176 | PASS |
| CMG | 43 | 6.720 | 1.176 | PASS |
| ELC | 43 | 6.688 | 1.211 | PASS |
| ITD | 43 | 6.688 | 1.211 | PASS |
| ICT | 42 | 6.290 | 1.144 | PASS |
| **Tổng** | **429** | **72.524** | **13.126** | **10/10 mã** |

Số báo cáo là hợp các kỳ giữa các nhóm và ratios, không có nghĩa mỗi nhóm
đều có đủ 43 kỳ. Ví dụ ELC/ITD có 41 kỳ LCTT, ICT có 32 kỳ ratios và 41 kỳ
các báo cáo khác. Không tự điền dữ liệu cho các kỳ nhà cung cấp không trả.

Toàn bộ chunk được kiểm tra đủ observation đúng một lần, ID chunk không trùng,
dựng lại từ locator đúng nội dung/hash. Không chunk nào vượt 130 từ.
Các kiểm tra mới không phát hiện lẫn kỳ, lẫn công ty hoặc observation trùng.

Giá có 21.298 phiên hợp lệ sau chuẩn hóa. Có 18 bản ghi bị loại vì trùng ngày
hoặc OHLC không hợp lệ; đây là quy tắc kiểm tra nguồn đã có, không phải logic
mới trong bản sửa thụt lề. Mỗi mã có nhật ký chi tiết trong result.json.

## Kiểm tra hồi quy và giới hạn

- Backend: 90 passed (chunk, source reader, reconstruction, clean edge cases và import reader).
- FinancialCleaner: 15 passed, 1 failed do thiếu file
  `.agent-state/source-hashes.json`. Không tạo baseline mới giả làm bằng chứng lịch sử.
- Chạy hai suite riêng theo thư mục vì cùng có package tên `tests`; gom chung
  bằng chế độ import mặc định gây lỗi collection, không phải lỗi collector.
- Không ghi Supabase, không gọi embedding hoặc kiểm tra tìm kiếm trên dữ liệu mới.
  Bước nhập được kiểm tra ở bộ đọc/định danh, chưa chạy INSERT thực tế.
- Dữ liệu thử nằm trong `backend/.tmp/new-financial-flow/20261020T084108964907Z/`
  gồm raw, normalized, clean và result.json. Dữ liệu chuẩn hiện có không bị ghi đè.

## Tái chạy

Từ thư mục FinMind:

```powershell
.\.venv\Scripts\python.exe -u -X utf8 backend/scripts/check_new_financial_flow.py
```

Chỉ kiểm tra hai công ty mẫu:

```powershell
.\.venv\Scripts\python.exe -u -X utf8 backend/scripts/check_new_financial_flow.py --symbols FPT VCB
```

Mỗi lần tạo một thư mục mới, không ghi database. Exit code khác 0 nếu có mã thất bại.
