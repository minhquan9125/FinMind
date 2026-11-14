# Lọc báo cáo tài chính bằng tên tiếng Việt

Bộ lọc đọc `../../data/normalized/*.json`, đối chiếu với `../../backend/src/financial/mapping.py` và tạo bản mới tại `data/<MÃ>/tai_chinh_clean.json`. Không sửa hoặc xóa JSON nguồn. Không truy cập folder ScrapersOHLCV.

## Chạy

Máy cần Python 3.10 trở lên, không cần cài thư viện hoặc API key. Double-click **Loc-tai-chinh.cmd** để lọc tất cả các mã hiện có. Hoặc mở terminal trong folder này:

```powershell
python -B -X utf8 -m cleaner
python -B -X utf8 -m cleaner --symbols FPT BID
```

Theo yêu cầu đã xác nhận: giữ PE, PB, PS và các chỉ số định giá/tài chính đã có mapping; chỉ bỏ dữ liệu giá/OHLCV đã lưu ở task cũ. Hai lệnh trên và launcher đều giữ nhóm định giá. Tùy chọn nâng cao `--bo-dinh-gia` có thể loại nhóm này, nhưng không dùng trong quy trình hiện tại. Chạy lại sẽ cập nhật bản clean của mã tương ứng. Báo cáo của lần chạy gần nhất nằm tại `reports/bao_cao_loc.json`.

## Dữ liệu giữ lại

- Bảng cân đối kế toán.
- Kết quả kinh doanh.
- Lưu chuyển tiền tệ.
- Chỉ số tài chính.

Mỗi phần giữ thứ tự các kỳ nguồn. Mỗi chỉ tiêu có `mã_chuẩn`, `tên_chỉ_tiêu`, `trường_gốc` và `giá_trị` để dễ kiểm tra. Tên từ mapping gốc được ưu tiên; `config/labels_vi.json` chỉ bổ sung tên còn thiếu. Các trường không được mapping, mã placeholder và giá trị null bị loại, có thống kê để đối chiếu. Giá trị 0, số âm và các kỳ không có chỉ tiêu phù hợp vẫn được giữ.

Không chia triệu/tỷ, làm tròn, đổi đơn vị hoặc nhân tỷ số với 100. Giá trị JSON số được đọc bằng Decimal và ghi lại dưới dạng số JSON để giữ độ chính xác. Đơn vị giữ theo nguồn; bộ lọc không tự suy đoán đơn vị. Quý `5` trong báo cáo năm được xuất thành `quý: null` và `loại_kỳ: Năm`.

Mapping hiện hỗ trợ BANK và TECH. Các ngành khác báo lỗi, không lấy mapping ngân hàng thay thế. Hiện đã tạo dữ liệu cho BID, CTG, MBB, TCB, VCB, CMG, ELC, FPT, ICT và ITD. Chưa có JSON FTS để lọc. Trang Vietstock được cung cấp không truy cập trực tiếp được trong phiên thực hiện; các nhãn dựa trên mapping và bản bổ sung đã kiểm tra, chưa xác nhận tương đương toàn bộ biểu mẫu Vietstock.

## Hàm và cấu trúc

### Cấu hình giá trị dễ đọc và chuẩn bị nhập DB

Chỉnh `config/display.json`, sau đó chạy lại launcher để cập nhật các JSON:

```json
{
  "bật": true,
  "dấu_phân_cách_nghìn": ".",
  "dấu_thập_phân": ",",
  "số_chữ_số_thập_phân": null,
  "bỏ_số_0_thập_phân_cuối": true
}
```

Ví dụ một chỉ tiêu sẽ có hai trường:

```json
{
  "giá_trị": 45603129033273.0,
  "giá_trị_hiển_thị": "45.603.129.033.273"
}
```

`giá_trị` luôn giữ nguyên số liệu và kiểu dữ liệu nguồn. `giá_trị_hiển_thị` chỉ là chuỗi để đọc. `số_chữ_số_thập_phân: null` giữ toàn bộ phần thập phân; đổi thành `2` để làm tròn riêng chuỗi hiển thị đến hai chữ số theo quy tắc half-up. Đặt `bỏ_số_0_thập_phân_cuối: false` nếu muốn hiện đủ hai chữ số. Đặt `bật: false` để không thêm trường hiển thị. Các số với dạng mở rộng trên 10.000 ký tự dùng dạng khoa học trong chuỗi hiển thị. Không tự đổi đơn vị hoặc đổi tỷ số thành phần trăm.

Khi nhập DB, dùng số gốc; không parse chuỗi hiển thị ngược thành số. Đã có hàm chuẩn bị các record với tên trường chuẩn, loại trừ cấu hình và chuỗi hiển thị:

```python
from pathlib import Path
from cleaner import codec, iter_database_records

cleaned = codec.loads(Path('data/FPT/tai_chinh_clean.json').read_text(encoding='utf-8'))
records = list(iter_database_records(cleaned))
# records có symbol, industry, section, period_label, period_type,
# year, quarter, metric_code và value. value là số/chuỗi số gốc.
```

Hàm này chưa kết nối hoặc ghi DB. Importer sau này cần chọn rõ các trường trên và cột `NUMERIC/DECIMAL` phù hợp để lưu số chính xác qua driver hỗ trợ Decimal, không ép sang float. Không đưa toàn bộ JSON vào bảng dưới dạng các cột tự suy đoán. Các kiểm tra xác nhận dữ liệu export không đổi khi bật/tắt hiển thị, đổi dấu phân cách hoặc làm tròn chuỗi.

```python
from cleaner import clean_symbols, clean_file

clean_symbols(['FPT', 'BID'])
clean_file('../../data/normalized/FPT.json')
```

`cleaner/core.py` chứa hàm thuần `clean_financial_data(...)`; adapter trong `cleaner/files.py` chọn mapping ngành và ghi file atomically trong folder này. Hàm thuần cần truyền `section_maps`, `labels_vi` và `meta_keys`; không sửa object đầu vào.

```text
FinancialCleaner/
  Loc-tai-chinh.cmd
  cleaner/       # hàm lọc, mapping, đọc/ghi và CLI
  config/        # tên tiếng Việt bổ sung và cấu hình hiển thị
  data/<MÃ>/     # JSON đã clean của từng mã
  reports/       # thống kê lần chạy
  tests/         # kiểm tra tính toàn vẹn số liệu
  .agent-state/  # checkpoint và đề xuất ECC workers
```

Kiểm tra sau khi đã tạo dữ liệu:

```powershell
python -B -X utf8 -m unittest discover -s tests -t . -v
```

Batch dừng nếu gặp nguồn không hợp lệ; những mã đã ghi trước lỗi vẫn còn bản clean, báo cáo tổng chỉ cập nhật khi cả lần chạy thành công. File kết quả từng mã được thay thế nguyên tử. SHA256 nguồn và mapping được ghi trong từng JSON để truy xuất nguồn.
