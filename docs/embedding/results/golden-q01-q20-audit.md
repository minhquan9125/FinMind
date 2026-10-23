# Kiểm tra Golden Q01–Q20 trên pgvector

> Báo cáo lịch sử cho câu hỏi Golden trước v6 và index `db-v1`. File Golden hiện tại đã đổi sang v6 với câu hỏi/ngày giá khác; các kết quả Q01–Q20 bên dưới không áp dụng cho v6. Dùng `backend/scripts/audit_golden_v6.py` để khảo sát v6, chưa chấm gold chính thức.

Ngày chạy: 21/10/2026. Đọc Supabase chính qua `backend/.env`, index version `1e029e66-0adf-53ac-8f28-431ed7312745` (`db-v1`, BAAI/bge-m3), chỉ xét chunk có `superseded_at IS NULL`. Chạy đúng câu hỏi tiếng Việt trong Golden Test Set với `top_k=5`. Bộ lọc công ty, tháng đăng tin/giá và loại tài liệu lấy từ nguồn đã ghi trong Golden Set; câu hỏi bao quát nhiều mã hoặc nhiều tháng không bị lọc vào một mã/tháng.

**Kết quả tìm nguồn:** 12/17 câu có một nguồn hoặc các phiên giá xác định đã lấy đủ nguồn cần thiết trong top 5. Năm câu còn lại có nguồn trong index nhưng truy vấn vector top 5 không lấy đủ. Ba câu Q10, Q14, Q18 là phép đếm/trung bình trên toàn bảng, được đối chiếu bằng SQL và không chấm như bài toán tìm một chunk.

| Câu | Nguồn gốc có trong index? | Vector top 5 | Đối chiếu |
| --- | --- | --- | --- |
| Q01 | Có | Đúng bài MSN | Đoạn trả về có `3.984` và `230%`. |
| Q02 | Có | Đúng bài CTR | Các đoạn trả về có `7.959`, `402`, `33%`, `20%`. |
| Q03 | Có | Đúng bài FPT | Đoạn trả về có `171,4`, `181.748`, `22/09/2026`. |
| Q04 | Có | Đúng bài FPT | Có `182.000` và `28,5%`. |
| Q05 | Có | Đúng bài ngân hàng | Có VietinBank, Vietcombank, MB và VPBank. |
| Q06 | Có | Đúng bài MBB | Có quy mô `1 73 triệu tỷ` (văn bản nguồn bỏ dấu phẩy) và 8 doanh nghiệp. |
| Q07 | Có | Đúng bài CTR | Có `13.723.654` và ngày giao dịch `21.8.2026`. |
| Q08 | Có | Đúng bài tin chung | Có hơn 14 triệu tài khoản và `14%`. |
| Q09 | Có | Đúng bài CTR | Có `97,4` tỷ. |
| Q10 | Không áp dụng | Không chấm vector | DB hiện có **234** bài: cafef 119, fireant 115. Golden cố định ghi **224** bài: cafef 114, fireant 110. Cần ghi rõ dùng tập nào khi đánh giá. |
| Q11 | Có cả hai phiên VCB | **Thiếu cả hai** phiên trong top 5 | SQL xác nhận 58,96 → 57,30; biến động −2,82%. |
| Q12 | Có phiên MBB cần đối chiếu | **Không lấy** phiên MBB 20/05 | SQL xác nhận đây là volume lớn nhất: 38.940.600. |
| Q13 | Có cả hai phiên FPT | **Thiếu cả hai** phiên trong top 5 | SQL xác nhận max 69,70 ngày 10/04; min 56,56 ngày 27/07. |
| Q14 | Có dữ liệu CTR | Không chấm vector | SQL xác nhận trung bình 316.524 cổ phiếu/phiên trên 123 phiên. |
| Q15 | Có | Đúng phiên VCB 20/05 | OHLC lần lượt 63,23 / 64,22 / 61,35 / 64,13. |
| Q16 | Có cả hai phiên NLG | **Thiếu cả hai** phiên trong top 5 | SQL so sánh sáu mã: NLG giảm mạnh nhất, −24,26%. |
| Q17 | Có | Đúng phiên MSN 27/07 | Close 63,90; high − low = 1,60. |
| Q18 | Có dữ liệu giá | Không chấm vector | SQL xác nhận **737** phiên, số phiên từng mã khớp Golden. |
| Q19 | Có | Đúng phiên VCB 23/04 | Volume 35.200.000; OHLC khớp Golden. |
| Q20 | Có cả hai phiên MBB | **Thiếu cả hai** phiên trong top 5 | SQL xác nhận 19,65 → 19,20; giảm 0,45 (−2,29%). |

“Đúng bài” nghĩa là `article_id` của chunk trả về trùng bài báo Golden chỉ định. “Đúng phiên” nghĩa là `price_id` của phiên nằm trong `row_keys` của chunk trả về. Riêng bài giá theo nhiều ngày, phải có **đủ tất cả phiên cần thiết** mới đạt. Phép tính SQL kiểm tra đáp án trên dữ liệu gốc; API vector hiện chỉ trả chunk và điểm, chưa sinh câu trả lời hay tự tính toán.

Đây là kết quả của `top_k=5` với các bộ lọc đã khai báo. Năm câu không tìm đủ phiên là **lỗi recall/cách truy vấn cho câu tổng hợp**, không phải thiếu bản ghi nguồn hoặc vector. Câu Q07 có `published_at` là 13/08/2026 17:00 UTC, nên văn bản tái dựng hiển thị ngày 14/08 theo UTC+7.

Chạy lại (chỉ đọc DB, ghi báo cáo JSON vào máy):

```powershell
cd backend
$env:HF_HUB_OFFLINE = "1"  # Nếu BGE-M3 đã có trong cache
.\.venv\Scripts\python.exe -X utf8 scripts\audit_golden_q01_q20.py --out .tmp\golden-q01-q20-audit.json --top-k 5
```

## Đối chứng và cải tiến truy vấn giá

Đã chạy lại riêng năm câu vector bị trượt với HNSW và tìm vector chính xác, mỗi cách ở top 5 và top 20. Hai cách tìm cho kết quả nguồn giống nhau:

| Câu | Top 5 | Top 20 |
| --- | --- | --- |
| Q11 | 0/2 phiên | 1/2 phiên |
| Q12 | 0/1 phiên | 0/1 phiên |
| Q13 | 0/2 phiên | 2/2 phiên |
| Q16 | 0/2 phiên NLG | 0/2 phiên NLG |
| Q20 | 0/2 phiên | 2/2 phiên |

Vì tìm chính xác cũng bỏ sót cùng các phiên, nguyên nhân chính là xếp hạng theo ngữ nghĩa của câu hỏi, không phải riêng HNSW. Tăng `top_k` chỉ giúp một số câu và không bảo đảm kết quả. Script đối chứng: `backend/scripts/diagnose_golden_price_recall.py` (chỉ đọc DB).

API mới `POST /api/search/price` đọc `price_bars` bằng các truy vấn SQL cố định: lấy đúng phiên theo mã/ngày, so sánh hai ngày, tìm volume lớn nhất, close cao/thấp nhất, trung bình volume, đếm phiên và mã giảm mạnh nhất. Nó không gọi BGE-M3 và không cho câu hỏi tự sinh SQL. Mỗi phiên trả `price_id`; kết quả tổng hợp ghi bảng nguồn, phạm vi và số phiên dùng để tính. Endpoint vector `POST /api/search/filtered` vẫn giữ nguyên để đo baseline và tìm tin.

Chạy **nguyên văn câu hỏi tiếng Việt Q11–Q20, không truyền sẵn mã hay kỳ**, API giá trả đúng giá trị Golden cho **10/10 câu** trên DB hiện tại. Q01–Q09 tiếp tục tìm đúng bài báo bằng vector; Q10 chưa chấm theo một đáp án duy nhất vì tập Golden cố định 224 bài khác phạm vi DB chính 234 bài. Script kiểm tra giá và đối chiếu đáp án:

```powershell
cd backend
.\.venv\Scripts\python.exe -X utf8 scripts\audit_golden_price_sql.py --out .tmp\golden-price-sql-audit.json
```

Ví dụ request:

```json
{"question":"So sánh giá đóng cửa của MBB giữa phiên 30/09/2026 và phiên 06/10/2026: chênh lệch bao nhiêu và theo hướng tăng hay giảm?"}
```

Response có `operation=compare_closes`, `data.change=-0.4500`, `data.change_percent=-2.29` và hai bản ghi nguồn MBB ngày 30/09, 06/10 với `price_id` riêng. Bộ nhận dạng hiện chỉ hỗ trợ những dạng câu giá nêu trên; câu không nhận dạng được trả lỗi rõ ràng để tránh đưa ra phép tính sai.
