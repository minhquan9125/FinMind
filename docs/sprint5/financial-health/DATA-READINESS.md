# BCTC thực tế — 12/11/2026

Đọc FinMind VPS qua settings runtime trong transaction READ ONLY/REPEATABLE READ; không ghi DB. Receipt `outputs/sprint5/financial-health-20261112/audit.json`, snapshot1752observation chọn lọc từ2024 ở `observations.json`. Mọi kết luận dưới đây gắn với snapshot, chưa tự thu nguồn mới.

## Phạm vi có dữ liệu

| Nhóm DB | Mã có BCTC | Kỳ gần nhất trong DB |
|---|---|---|
| BANK | BID CTG MBB VCB | 2026-Q2 |
| BANK | TCB | 2026-Q3 |
| TECH (phân nhóm rộng, chưa chứng nhận peer tương đồng mô hình kinh doanh) | CMG ELC FPT ICT ITD | 2026-Q2 |

24company mới thêm cho rổ giá không có BCTC trong DB này. Không coi đã có30mã giá là đã có30mã tài chính. Không dùng kỳQ2 của đối thủ để xếp hạng vớiQ3 của TCB. Giá trị tuyệt đối lớn hơn thể hiện quy mô, không tự chứng minh hiệu quả/tài chính khỏe hơn.

## Các điểm chưa được phép đoán

- `financial_reports.statement_scope` hiện lưu BALANCE_SHEET/INCOME_STATEMENT/CASH_FLOW/RATIO. Đây là section, không phải bằng chứng phạm vi hợp nhất/riêng. Metadata audit_status UNKNOWN; published_at có ở statement, ratio không có.
- Observation tiền ghi VND/scale1; tỷ số ghi SOURCE_NATIVE. Việc importer tự gán không chứng minh unit/basis đã đối soát. Locator legacy không có unit_status/period_basis/comparison_basis/fiscal_year_end/window dates đã xác minh. Không tự đổi0.27 thành27% hoặc quý thành lũy kế.
- [IAS34](https://www.ifrs.org/issued-standards/list-of-standards/ias-34-interim-financial-reporting/) phân biệt nội dung kỳ giữa niên độ và thông tin kỳ so sánh. Đây là căn cứ thiết kế kiểm soát kỳ, không tuyên bố các doanh nghiệp Việt Nam trong DB áp dụng IFRS. Lưu chuyển tiền theo lũy kế không được cộng các snapshot lũy kế hoặc so với số quý riêng.
- [CMC công bố năm tài chính01/04–31/03](https://cms.cmc.com.vn/media/Shareholder/%C4%90H%C4%90C%C4%90%202022/2022.07.06.D%E1%BB%B1%20th%E1%BA%A3o%20%C4%90i%E1%BB%81u%20l%E1%BB%87%20CMC%20L%E1%BA%A7n%2020%20Final%20V2.pdf). Cần xác minh kỳ thực từng bộ số liệu, không ghép peer chỉ vì cùng nhãn2026-Q2.
- [FPT công bố đổi phương pháp hợp nhất FPT Telecom năm2026](https://fpt.com/vi/tin-tuc/9-thang-doanh-thu-va-loi-nhuan-truoc-thue-cua-fpt-tang-12-4-va-17-0); số2025 trong báo cáo so sánh được điều chỉnh cùng phương pháp. Vì vậy so2026 với bản2025 cũ có thể tạo tín hiệu giảm sai về khả năng so sánh. Không thay bản lịch sử hoặc suy ngược prior từ phần trăm đã làm tròn.
- Source VIETCAP_VCI vẫn PENDING/disabled. Bộ tính không tự phê duyệt nguồn; dữ liệu có metadata đủ vẫn ghi provisional nếu nguồn chưa approved.

## Một quan sát có nguồn trực tiếp

FPT công bố ngày21/10/2026: doanh thu9tháng40.023tỷVND, tăng12,4%; lợi nhuận trước thuế8.770tỷVND, tăng17,0% trên cơ sở cùng phương pháp hợp nhất. Đây là **số do doanh nghiệp công bố**, từ link FPT ở trên, chưa phải tín hiệu tính lại từ bộ DB đang tớiQ2 hoặc kết luận mạnh hơn toàn ngành. Không đưa trực tiếp các phần trăm này vào đầu vào BCTC để giả định đã có giá trị kỳ trước chính xác.

## Bước dữ liệu cần có để kết luận mạnh/yếu

Theo từng mã/kỳ: lấy statement đúng phạm vi, unit, fiscal window; ghép cả giá trị cùng kỳ đã restated nếu có. Giữ observation/payload/source/hash/locator. Chỉ so các chỉ tiêu cùng nghĩa và công thức, tối thiểu3peer ngoài target có cùng kỳ thực. TECH xem tăng doanh thu/lợi nhuận, margin, CFO và leverage; BANK xem lợi nhuận/ROE/ROA/NIM/nợ xấu/CIR theo định nghĩa phù hợp, không chấm CFO âm như doanh nghiệp phi tài chính. Theo [IMF FSIs](https://data.imf.org/en/news/12225bank%20profitability%20increases%20globally), ROA có quy tắc kỳ/annualization/tài sản bình quân; không tự tính nhãn ROA bằng một phép PAT/tài sản cuối kỳ.

Bản đầu ưu tiên **không kết luận sai**. Output trả riêng từng chiều và nguyên nhân thiếu; không phát sinh nhãn “mạnh nhất” hoặc điểm tổng hợp khi dữ liệu chưa đủ.
