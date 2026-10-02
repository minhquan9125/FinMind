# Source Register — BCTC, BCTN, News (Sprint 1, 10 công ty)

**Trạng thái:** bản rà soát để nhóm duyệt; chưa có bằng chứng biên bản/ý kiến duyệt cuối cùng.  
**Ngày chốt kiểm tra URL:** 30/09/2026.  
**Phạm vi kế thừa, không mở lại:** 10 mã VCB, BID, CTG, MBB, TCB, FPT, CMG, ELC, ITD, ICT; core gồm dữ liệu tài chính và BCTN; News là nguồn bổ sung. Review Sprint 1 nói OHLCV/News chưa được đóng băng nếu chưa duyệt (F05 trong `docs/review/v3_summary.txt`).

## Luồng crawl và chuẩn hóa đang có trong repo

Luồng BCTC/OHLCV thực tế **không dựa vào PDF CafeF**. `data_pipeline/collector.py` lấy OHLCV từ Entrade Chart API và BCTC/chỉ số tài chính từ Vietcap VCI API; pipeline giữ payload gốc ở `data/raw/{SYMBOL}_raw.json` và dữ liệu chuẩn hóa ở `data/normalized/{SYMBOL}.json`. Mỗi JSON đã ghi `sources.prices=ENTRADE`, `sources.fundamentals=VIETCAP_VCI`.

| Nguồn và loại dữ liệu | Endpoint đang gọi trong code | Hiện trạng |
|---|---|---|
| Entrade — giá OHLCV ngày | `https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?symbol={SYMBOL}&from={UNIX}&to={UNIX}&resolution=1D` | Có trong JSON chuẩn hóa của 10/10 mã. |
| Vietcap VCI — BCTC (KQKD, CĐKT, LCTT) | `https://iq.vietcap.com.vn/api/iq-insight-service/v1/company/{SYMBOL}/financial-statement?section={INCOME_STATEMENT\|BALANCE_SHEET\|CASH_FLOW}` | Có trong JSON chuẩn hóa của 10/10 mã. |
| Vietcap VCI — chỉ số tài chính | `https://iq.vietcap.com.vn/api/iq-insight-service/v1/company/{SYMBOL}/statistics-financial` | Có trong JSON chuẩn hóa của 10/10 mã. |

Đây là mapping nguồn hiện hữu: `prices → ENTRADE`; `ratios + income_statement + balance_sheet + cash_flow → VIETCAP_VCI`. PDF CafeF được giữ **chỉ làm tài liệu tham chiếu để đối chiếu và chuẩn hóa mapping** (tên dòng chỉ tiêu, kỳ, đơn vị, giá trị, riêng/hợp nhất); không phải nguồn ingest/OCR và không tạo ra 10 JSON này. BCTN không có trong các endpoint trên, nên cần nguồn IR riêng.

## Quy tắc dùng nguồn

| Nhóm nguồn | Vai trò hiện tại | Quy tắc ghi nhận |
|---|---|---|
| Entrade Chart API — OHLCV | **Nguồn đã được pipeline gọi**, dữ liệu chuẩn hóa có trong 10 JSON. | Ghi endpoint, tham số, ngày crawl, khoảng ngày giá và chất lượng record; đây là nguồn của OHLCV. |
| Vietcap VCI API — BCTC và ratios | **Nguồn đã được pipeline gọi**, dữ liệu chuẩn hóa có trong 10 JSON. | Ghi endpoint/section, ngày crawl, kỳ, field mapping và trạng thái chất lượng; lưu raw payload để truy nguyên. Đây là nguồn của BCTC/ratios trong JSON. |
| IR doanh nghiệp, HOSE/HNX | Nguồn báo cáo công bố chính thức; dùng cho BCTN và làm tài liệu đối chiếu dòng/kỳ khi cần. | Ghi URL report cụ thể, năm/kỳ, loại báo cáo, ngày công bố và hash tài liệu. Không nhầm URL tham chiếu với endpoint tạo JSON API. |
| CafeF — trang tài liệu và PDF | **Tài liệu tham chiếu để đối chiếu/chuẩn hóa mapping API**, không phải nguồn dữ liệu ingest/OCR. | Lưu liên kết và định danh PDF tham chiếu; dùng để kiểm tra label, kỳ, đơn vị, riêng/hợp nhất và giá trị mẫu. Không gắn PDF CafeF làm provenance của các record API. |
| CafeF News / RSS | Trang công khai có thể kiểm tra được; **News provider và cửa sổ ngày chưa được nhóm đóng băng trong artifact**. | Tạm loại khỏi corpus và Golden Test Set theo F05. Chỉ đưa vào sau khi nhóm chốt provider, phạm vi bài và khoảng ngày. |

> News vẫn tách biệt với luồng API BCTC/giá. Provider và khoảng ngày News cần được nhóm chốt theo F05.

## Quyền sử dụng và tình trạng kiểm tra nguồn

URL mở được chỉ xác nhận khả năng truy cập tại thời điểm kiểm tra; không tự chứng minh quyền crawl tự động, lưu trữ, tái sử dụng hoặc phân phối dữ liệu. Trong repo hiện chưa thấy văn bản chấp thuận của provider hoặc quyết định nhóm cho các mục dưới đây. Vì vậy bảng này ghi trạng thái quyền là **chưa có bằng chứng**, không tự kết luận nguồn được phép crawl.

| Nguồn | Phạm vi dự kiến | Bằng chứng hiện có | Trạng thái để nhóm duyệt |
|---|---|---|---|
| Entrade Chart API | OHLCV cho 10 mã | Endpoint đang được collector gọi; JSON 10/10 có provenance `ENTRADE`. Chưa thấy điều khoản/chấp thuận crawl và tái sử dụng được lưu trong repo. | **Đã dùng kỹ thuật; quyền tự động hóa/tái sử dụng chưa được xác nhận.** Cần ghi căn cứ provider hoặc giới hạn sử dụng được nhóm chấp thuận. |
| Vietcap VCI API | BCTC và ratios cho 10 mã | Endpoint đang được collector gọi; JSON 10/10 có provenance `VIETCAP_VCI`. Tài liệu hướng dẫn sản phẩm không thay thế chấp thuận dùng API/tái sử dụng; repo chưa lưu căn cứ đó. | **Đã dùng kỹ thuật; quyền tự động hóa/tái sử dụng chưa được xác nhận.** Cần ghi căn cứ provider hoặc giới hạn sử dụng được nhóm chấp thuận. |
| IR doanh nghiệp / HOSE / HNX | Báo cáo công bố; BCTN và đối chiếu | Có URL trang IR/báo cáo trong bảng bên dưới; một số là trang danh mục, không phải URL tệp báo cáo. Chưa có đăng ký từng tài liệu/năm cho toàn bộ 10 mã. | **Có URL đầu mối; danh sách tài liệu còn thiếu.** Dùng tài liệu công bố để tham chiếu; việc tải hàng loạt/tái phân phối cần căn cứ riêng. |
| VietstockFinance — BCTN | Chỉ mục theo mã/năm và link tệp BCTN để thu thập PDF | [Trang BCTN](https://finance.vietstock.vn/tai-lieu/bao-cao-thuong-nien.htm) hiển thị các kỳ năm; trang hiện nạp danh sách qua endpoint JSON nội bộ của website (`getrptdoctype`, `getrptterm`, `getrptfile`), không phải API đối tác được tài liệu hóa. | **Đã xác nhận kỹ thuật; chưa có bằng chứng quyền thu thập hàng loạt/tái sử dụng.** Collector không bỏ qua đăng nhập/CAPTCHA/giới hạn truy cập. |

Catalog kiểm tra ngày 30/09/2026 có URL cho **70/70 tổ hợp mã–năm** (10 mã × 2019–2025), tổng 71 tài liệu do CMG năm 2025 có thêm bản điều chỉnh. Đã tải 21 tệp năm 2024–2025; hash và đường dẫn local nằm trong [manifest](../../data/references/vietstock/annual_reports/manifest.json). Trích xuất text 21 tài liệu: 2.939 trang, 252 trang chưa có lớp chữ dùng được; OCR chưa chạy vì máy chưa có OCRmyPDF/Tesseract.
| CafeF tài liệu/PDF | Chỉ tham chiếu để chuẩn hóa mapping API | Trang tài liệu theo mã và một số PDF cục bộ đã được ghi trong manifest; đây không phải provenance của JSON API. Trang/hướng dẫn công khai không phải giấy phép tái sử dụng. | **Tham chiếu mapping nội bộ; chưa duyệt làm nguồn ingest hoặc phân phối.** |
| CafeF News / RSS | News bổ sung, nếu nhóm chốt | Có trang News theo từng mã; RSS hỗ trợ đăng ký đọc feed. Chưa có quyết định provider/cửa sổ ngày và chưa có bằng chứng cấp quyền đưa nội dung vào corpus. | **Chờ nhóm duyệt; loại khỏi corpus và Golden Test Set theo F05.** Cửa sổ 28/09/2024–27/09/2026 chỉ là đề xuất. |

**Phân biệt trạng thái:** `URL kiểm tra được` = đã xác nhận trang/endpoint tồn tại; `nguồn được dùng` = cần căn cứ điều khoản hoặc quyết định nhóm ghi rõ mục đích/phạm vi. Hiện chưa có nguồn nào trong bảng được đánh dấu “đã duyệt quyền crawl/tái sử dụng” bằng chứng cứ lưu trong repo.

## Bảng URL và tình trạng 10 công ty

Các URL PDF CafeF dưới đây là **đầu mối tài liệu tham chiếu mapping**; chúng không đại diện cho nguồn crawl của JSON. URL News dùng trang Tin tức theo mã trên CafeF; cửa sổ ngày đề xuất chung là **28/09/2024–27/09/2026 (bao gồm hai đầu ngày)**, chờ nhóm xác nhận. Đây là cửa sổ đề xuất theo mốc kết thúc Sprint 1, không phải ngày đã được nhóm chốt trong artifact hiện có.

| Mã | JSON Entrade/Vietcap đã có | OHLCV trong JSON | Ratios | KQKD | CĐKT | LCTT |
|---|---|---:|---:|---:|---:|---:|
| VCB | Có | 2018-01-02–2026-09-25 · 2.174 phiên | 41 | 42 | 42 | 42 |
| BID | Có | 2018-01-02–2026-09-25 · 2.176 phiên | 41 | 42 | 42 | 42 |
| CTG | Có | 2018-01-02–2026-09-25 · 2.176 phiên | 41 | 42 | 42 | 42 |
| MBB | Có | 2018-01-02–2026-09-25 · 2.175 phiên | 41 | 42 | 42 | 42 |
| TCB | Có | 2018-06-04–2026-09-25 · 2.076 phiên | 40 | 42 | 42 | 42 |
| FPT | Có | 2018-01-02–2026-09-25 · 2.175 phiên | 41 | 42 | 42 | 42 |
| CMG | Có | 2018-01-02–2026-09-25 · 2.176 phiên | 41 | 42 | 42 | 42 |
| ELC | Có | 2018-01-02–2026-09-25 · 2.176 phiên | 41 | 42 | 42 | 41 |
| ITD | Có | 2018-01-02–2026-09-25 · 2.173 phiên | 41 | 42 | 42 | 41 |
| ICT | Có | 2020-01-15–2026-09-25 · 1.655 phiên | 31 | 41 | 41 | 41 |

Các số đếm là record đang xuất trong `data/normalized/{SYMBOL}.json`, không phải số lượng kỳ duy nhất đã quy về ma trận 7 kỳ. Tất cả 10 JSON có `sources.prices=ENTRADE` và `sources.fundamentals=VIETCAP_VCI`.

| Mã | Trang IR chính thức cho BCTN / đối chiếu (URL đầu mối, trừ khi ghi PDF) | CafeF: PDF tham chiếu mapping | News URL / cửa sổ ngày đề xuất | PDF tham chiếu có trong repo | Kết luận / thiếu |
|---|---|---|---|---|---|
| VCB | [IR Vietcombank](https://vietcombank.com.vn/vi-VN/Nha-dau-tu) | [CafeF VCB tài liệu](https://cafef.vn/du-lieu/hose/vcb-tai-lieu.chn) | [Tin VCB](https://cafef.vn/du-lieu/hose/vcb-tin-tuc.chn) · 28/09/2024–27/09/2026 đề xuất | Có 30 BCTC và 2 tài liệu BCTN CafeF (2024, 2025) làm mẫu đối chiếu. | JSON API đã có. Vietstock catalog có link BCTN 2019–2025; file 2024–2025 đã tải. News chờ duyệt. |
| BID | [IR BIDV — Báo cáo và tài liệu](https://bidv.com.vn/vn/quan-he-nha-dau-tu/bao-cao-va-tai-lieu/) | [CafeF BID tài liệu](https://cafef.vn/du-lieu/hose/bid-tai-lieu.chn) | [Tin BID](https://cafef.vn/du-lieu/hose/bid-tin-tuc.chn) · 28/09/2024–27/09/2026 đề xuất | Có 31 BCTC và 2 tài liệu BCTN CafeF (2024, 2025) làm mẫu đối chiếu. | JSON API đã có. Vietstock catalog có link BCTN 2019–2025; file 2024–2025 đã tải. News chờ duyệt. |
| CTG | [IR VietinBank](https://investor.vietinbank.vn/vi) · [Báo cáo định kỳ](https://beta-investor.vietinbank.vn/vi/periodicreports.aspx/-/categories/471001) · [BCTN](https://beta-investor.vietinbank.vn/vi/annualreports.aspx) | [CafeF CTG tài liệu](https://cafef.vn/du-lieu/hose/ctg-tai-lieu.chn) | [Tin CTG](https://cafef.vn/du-lieu/hose/ctg-tin-tuc.chn) · 28/09/2024–27/09/2026 đề xuất | Có 29 BCTC và 2 BCTN CafeF làm mẫu đối chiếu. | JSON API đã có. Vietstock catalog có link BCTN 2019–2025; file 2024–2025 đã tải. News chờ duyệt. |
| MBB | [IR MBBank](https://www.mbbank.com.vn/Investor/nha-dau-tu?lang=EN) | [CafeF MBB tài liệu](https://cafef.vn/du-lieu/hose/mbb-tai-lieu.chn) | [Tin MBB](https://cafef.vn/du-lieu/hose/mbb-tin-tuc.chn) · 28/09/2024–27/09/2026 đề xuất | Có 28 BCTC, 2 BCTN CafeF và điều lệ làm mẫu đối chiếu. | JSON API đã có. Vietstock catalog có link BCTN 2019–2025; file 2024–2025 đã tải. News chờ duyệt. |
| TCB | [BCTC Techcombank](https://techcombank.com/en/investors/financial-information/financial-statements-vas) · [BCTN](https://techcombank.com/en/investors/annual-report) | [CafeF TCB tài liệu](https://cafef.vn/du-lieu/hose/tcb-tai-lieu.chn) | [Tin TCB](https://cafef.vn/du-lieu/hose/tcb-tin-tuc.chn) · 28/09/2024–27/09/2026 đề xuất | Có 30 BCTC, 2 BCTN CafeF và điều lệ làm mẫu đối chiếu. | JSON API đã có. Vietstock catalog có link BCTN 2019–2025; file 2024–2025 đã tải. News chờ duyệt. |
| FPT | [IR FPT](https://fpt.com/vi/nha-dau-tu) · [BCTN](https://fpt.com/vi/nha-dau-tu/bao-cao-thuong-nien) | [CafeF FPT tài liệu](https://cafef.vn/du-lieu/hose/fpt-tai-lieu.chn) | [Tin FPT](https://cafef.vn/du-lieu/hose/fpt-tin-tuc.chn) · 28/09/2024–27/09/2026 đề xuất | 25 PDF CafeF phụ trợ ngoài manifest; dùng Vietstock làm chỉ mục BCTN. | JSON API đã có. Vietstock catalog có link BCTN 2019–2025; file 2024–2025 đã tải. News chờ duyệt. |
| CMG | [CMC — Báo cáo tài chính / tài liệu cổ đông](https://www.cmc.com.vn/shareholder/financial-report) | [CafeF CMG tài liệu](https://cafef.vn/du-lieu/hose/cmg-tai-lieu.chn) | [Tin CMG](https://cafef.vn/du-lieu/hose/cmg-tin-tuc.chn) · 28/09/2024–27/09/2026 đề xuất | Không có PDF CafeF phụ trợ cục bộ. | JSON API đã có. Vietstock catalog có link BCTN 2019–2025; file 2024–2025 đã tải, gồm bản CMG 2025 điều chỉnh. News chờ duyệt. |
| ELC | [ELCOM — BCTC](https://www.elcom.com.vn/co-dong/bao-cao-tai-chinh) · [BCTN 2025 PDF](https://www.elcom.com.vn/documents/1776653024_20260417_elc_bao_cao_thuong_nien_2025.pdf/view) | [CafeF ELC tài liệu](https://cafef.vn/du-lieu/hose/elc-tai-lieu.chn) | [Tin ELC](https://cafef.vn/du-lieu/hose/elc-tin-tuc.chn) · 28/09/2024–27/09/2026 đề xuất | Không có PDF CafeF phụ trợ cục bộ. | JSON API đã có (LCTT ít hơn 1 record). Vietstock catalog có link BCTN 2019–2025; file 2024–2025 đã tải. News chờ duyệt. |
| ITD | [ITD — Quan hệ cổ đông](https://itd.com.vn/quan-he-co-dong.html) | [CafeF ITD tài liệu](https://cafef.vn/du-lieu/hose/itd-tai-lieu.chn) | [Tin ITD](https://cafef.vn/du-lieu/hose/itd-tin-tuc.chn) · 28/09/2024–27/09/2026 đề xuất | Không có PDF CafeF phụ trợ cục bộ. | JSON API đã có (LCTT ít hơn 1 record). Vietstock catalog có link BCTN 2019–2025; file 2024–2025 đã tải. News chờ duyệt. |
| ICT | [CTIN — Báo cáo thường niên 2024 PDF](https://ctin.vn/wp-content/uploads/2025/04/Bao-cao-thuong-nien-CTIN-2024.pdf) · [CTIN — trang chủ](https://ctin.vn/) | [CafeF ICT tài liệu](https://cafef.vn/du-lieu/hose/ict-tai-lieu.chn) | [Tin ICT](https://cafef.vn/du-lieu/hose/ict-tin-tuc.chn) · 28/09/2024–27/09/2026 đề xuất | Không có PDF CafeF phụ trợ cục bộ. | JSON API đã có, lịch sử OHLCV bắt đầu 2020. Vietstock catalog có link BCTN 2019–2025; file 2024–2025 đã tải. News chờ duyệt. |

## Coverage — cách hiểu “10 công ty × 7 kỳ”

JSON chuẩn hóa đã có cho **đủ 10/10 mã** từ Entrade/Vietcap. Số record tài chính hiện là 40–42 kỳ tùy mã (ICT có 31 ratios và 41 record cho mỗi báo cáo; ELC/ITD thiếu một record LCTT so với các báo cáo khác). Đây là coverage API đang có. Không cần cào lại để test nạp BANK: quyết định hiện tại là dùng nguyên các JSON BANK sẵn có; cả ba báo cáo BCTC của BID, CTG, MBB, TCB, VCB có kỳ từ **2018-Q1 đến 2026-Q2**, 42 kỳ/báo cáo/mã. Ratios có 40–41 kỳ tùy mã.

“7 kỳ” trong yêu cầu khảo sát nguồn chưa có danh sách kỳ cụ thể trong artifact. Điều này **không chặn test nạp BANK** theo JSON hiện có; chỉ cần quay lại nếu nhóm yêu cầu báo cáo coverage riêng cho đúng một bộ 7 kỳ. Không tự suy ra phải cào lại từ một năm mới.

Tập PDF CafeF là artifact riêng, không phải nguồn tạo ra JSON API: manifest có 169 bản ghi cho 5 mã ngân hàng (148 BCTC, 10 BCTN, 11 tài liệu annual-category khác); tất cả được tải ngày 28/09/2026, sau mốc Sprint 1 27/09. FPT có 25 PDF chưa ghi vào manifest; CMG, ELC, ITD, ICT không có PDF CafeF cục bộ. Các con số này **không mô tả coverage JSON API**. Manifest: [`data/references/cafef/pdfs/manifest.json`](../../data/references/cafef/pdfs/manifest.json).

| Nhóm mã | Coverage dữ liệu API | BCTN / nguồn báo cáo | Trạng thái ma trận 7 kỳ |
|---|---|---|---|
| VCB, BID, CTG, MBB, TCB, FPT, CMG, ELC, ITD, ICT | Có JSON BCTC + ratios từ Vietcap; OHLCV từ Entrade. Chi tiết theo mã ở bảng coverage phía trên. | Vietcap không trả BCTN. Vietstock đã catalog URL cho 70/70 tổ hợp mã–năm 2019–2025 (71 tài liệu do CMG 2025 có bản điều chỉnh); 21 tệp 2024–2025 đã tải, có local path và hash trong manifest. | BCTC 7 kỳ riêng vẫn cần danh sách kỳ mục tiêu; việc này không chặn test nạp BANK đã chốt. |

PDF CafeF: VCB/BID/CTG/MBB/TCB có 28–31 BCTC/mã và 2 BCTN/mã (2024–2025); FPT có 25 PDF ngoài manifest; CMG/ELC/ITD/ICT không có PDF CafeF cục bộ. Đây là đối chiếu phụ, không phải tiêu chí độ phủ JSON API.

## Quyết nghị cần nhóm xác nhận để freeze

1. Xác nhận Entrade/Vietcap là nguồn API nhóm duyệt cho OHLCV và dữ liệu tài chính; ghi căn cứ điều khoản/chấp thuận và giới hạn dùng. Nếu chưa có căn cứ, ghi rõ phạm vi sử dụng nội bộ tạm thời được nhóm chấp thuận và người/ngày duyệt.
2. Map chính xác 7 kỳ đã chốt tới `period_label` và trạng thái từng record trong 10 JSON; không dùng tổng record để thay ma trận kỳ.
3. Dùng VietstockFinance làm chỉ mục tìm BCTN theo mã/năm; ưu tiên lưu URL công bố của doanh nghiệp khi có. Catalog/download ghi direct URL, mã tài liệu, năm, hash và trạng thái vào manifest; xác nhận quyền/phạm vi dùng trước khi coi là nguồn crawl đã duyệt.
4. Duyệt hoặc loại News CafeF; nếu duyệt thì xác nhận cửa sổ đề xuất 28/09/2024–27/09/2026, danh mục chủ đề, loại trùng, căn cứ quyền sử dụng và lưu URL bài gốc.
5. Giữ PDF CafeF ở vai trò tài liệu mapping: gắn nhãn chỉ tiêu API ↔ tên dòng trên báo cáo, period label ↔ kỳ báo cáo, đơn vị, công ty mẹ/hợp nhất và giá trị đối chiếu. Không dùng PDF này làm đầu vào ingest/OCR hay provenance của JSON.

**Gate kết luận:** Với mục tiêu test nạp BANK, dùng 5 JSON hiện có, không cào lại; BCTC có 42 kỳ/mã từ 2018-Q1 đến 2026-Q2. BCTN đã có URL theo mã/năm 2019–2025 trên Vietstock và đã tải 21 tệp năm 2024–2025; trích xuất xác định 252 trang cần OCR. OCR engine chưa cài nên 252 trang chưa được OCR. Quyền thu thập hàng loạt/tái sử dụng Vietstock và quyền dùng Entrade/Vietcap chưa có bằng chứng duyệt trong repo; News tiếp tục loại khỏi corpus/Golden Test Set theo F05. Các mục quyền và OCR này không chặn test nạp BANK nội bộ bằng JSON có sẵn.

## Các trang nguồn đã kiểm tra

- Official IR: [Vietcombank](https://vietcombank.com.vn/vi-VN/Nha-dau-tu), [BIDV báo cáo và tài liệu](https://bidv.com.vn/vn/quan-he-nha-dau-tu/bao-cao-va-tai-lieu/), [VietinBank định kỳ](https://beta-investor.vietinbank.vn/vi/periodicreports.aspx/-/categories/471001), [MBBank](https://www.mbbank.com.vn/Investor/nha-dau-tu?lang=EN), [Techcombank BCTC](https://techcombank.com/en/investors/financial-information/financial-statements-vas) và [BCTN](https://techcombank.com/en/investors/annual-report), [FPT IR](https://fpt.com/vi/nha-dau-tu), [CMC reports](https://www.cmc.com.vn/shareholder/financial-report), [ELCOM BCTC](https://www.elcom.com.vn/co-dong/bao-cao-tai-chinh), [ITD IR](https://itd.com.vn/quan-he-co-dong.html), [CTIN BCTN 2024](https://ctin.vn/wp-content/uploads/2025/04/Bao-cao-thuong-nien-CTIN-2024.pdf).
- VietstockFinance BCTN: [trang chỉ mục theo năm/mã](https://finance.vietstock.vn/tai-lieu/bao-cao-thuong-nien.htm); endpoint nội bộ của trang trả về danh sách kỳ, metadata báo cáo và URL tệp. Catalog/download: [`data_pipeline/documents/vietstock_annual.py`](../../data_pipeline/documents/vietstock_annual.py); manifest URL/file: [`data/references/vietstock/annual_reports/manifest.json`](../../data/references/vietstock/annual_reports/manifest.json); extract/OCR: [`data_pipeline/documents/extract_vietstock_annuals.py`](../../data_pipeline/documents/extract_vietstock_annuals.py); hướng dẫn: [`data_pipeline/documents/README.md`](../../data_pipeline/documents/README.md).
- CafeF xác nhận trang tài liệu từng mã có các nhóm “Báo cáo tài chính” và “Bản cáo bạch & BCTN”; trang dữ liệu nêu nội dung chỉ có giá trị tham khảo và không chịu trách nhiệm rủi ro sử dụng: [ví dụ ICT tài liệu](https://cafef.vn/du-lieu/hose/ict-tai-lieu.chn), [hướng dẫn dữ liệu CafeF](https://cafef.vn/du-lieu/huong-dan-su-dung.chn), [RSS CafeF](https://cafef.vn/index.rss).
