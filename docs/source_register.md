# Source Register — BCTC, BCTN, News (Sprint 1, 10 công ty)

**Trạng thái:** bản rà soát để nhóm duyệt; chưa có bằng chứng biên bản/ý kiến duyệt cuối cùng.  
**Ngày chốt kiểm tra URL:** 29/09/2026.  
**Phạm vi kế thừa, không mở lại:** 10 mã VCB, BID, CTG, MBB, TCB, FPT, CMG, ELC, ITD, ICT; core gồm dữ liệu tài chính và BCTN; News là nguồn bổ sung. Review Sprint 1 nói OHLCV/News chưa được đóng băng nếu chưa duyệt (F05 trong `docs/review/v3_summary.txt`).

## Luồng crawl và chuẩn hóa đang có trong repo

Luồng BCTC/OHLCV thực tế **không dựa vào PDF CafeF**. `data_pipeline/src/scrapers/direct_vn_collector.py` lấy OHLCV từ Entrade Chart API và BCTC/chỉ số tài chính từ Vietcap VCI API; pipeline giữ payload gốc ở `data/raw/{SYMBOL}_raw.json` và dữ liệu chuẩn hóa ở `data/normalized/{SYMBOL}.json`. Mỗi JSON đã ghi `sources.prices=ENTRADE`, `sources.fundamentals=VIETCAP_VCI`.

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

| Mã | Trang IR chính thức cho BCTN / đối chiếu | CafeF: PDF tham chiếu mapping | News URL / cửa sổ ngày đề xuất | PDF tham chiếu có trong repo | Kết luận / thiếu |
|---|---|---|---|---|---|
| VCB | [IR Vietcombank](https://vietcombank.com.vn/vi-VN/Nha-dau-tu) | [CafeF VCB tài liệu](https://cafef.vn/du-lieu/hose/vcb-tai-lieu.chn) | [Tin VCB](https://cafef.vn/du-lieu/hose/vcb-tin-tuc.chn) · 28/09/2024–27/09/2026 đề xuất | Có 30 BCTC và 2 tài liệu BCTN (2024, 2025) làm mẫu đối chiếu; tải 28/09. | JSON API đã có. Cần chốt năm BCTN mục tiêu và ghi URL IR cho bộ BCTN; News chờ duyệt. |
| BID | [IR BIDV — Báo cáo và tài liệu](https://bidv.com.vn/vn/quan-he-nha-dau-tu/bao-cao-va-tai-lieu/) | [CafeF BID tài liệu](https://cafef.vn/du-lieu/hose/bid-tai-lieu.chn) | [Tin BID](https://cafef.vn/du-lieu/hose/bid-tin-tuc.chn) · 28/09/2024–27/09/2026 đề xuất | Có 31 BCTC và 2 tài liệu BCTN (2024, 2025) làm mẫu đối chiếu; tải 28/09. | JSON API đã có. Cần chốt năm BCTN mục tiêu và ghi URL IR cho bộ BCTN; News chờ duyệt. |
| CTG | [IR VietinBank](https://investor.vietinbank.vn/vi) · [Báo cáo định kỳ](https://beta-investor.vietinbank.vn/vi/periodicreports.aspx/-/categories/471001) · [BCTN](https://beta-investor.vietinbank.vn/vi/annualreports.aspx) | [CafeF CTG tài liệu](https://cafef.vn/du-lieu/hose/ctg-tai-lieu.chn) | [Tin CTG](https://cafef.vn/du-lieu/hose/ctg-tin-tuc.chn) · 28/09/2024–27/09/2026 đề xuất | Có 29 BCTC, 2 tài liệu BCTN, bản cáo bạch và điều lệ làm mẫu đối chiếu; tải 28/09. | JSON API đã có. Chỉ 2 tài liệu có tiêu đề BCTN là mẫu; cần URL IR cho bộ BCTN mục tiêu. News chờ duyệt. |
| MBB | [IR MBBank](https://www.mbbank.com.vn/Investor/nha-dau-tu?lang=EN) | [CafeF MBB tài liệu](https://cafef.vn/du-lieu/hose/mbb-tai-lieu.chn) | [Tin MBB](https://cafef.vn/du-lieu/hose/mbb-tin-tuc.chn) · 28/09/2024–27/09/2026 đề xuất | Có 28 BCTC, 2 tài liệu BCTN và điều lệ làm mẫu đối chiếu; tải 28/09. | JSON API đã có. Cần chốt năm BCTN mục tiêu và ghi URL IR cho bộ BCTN; News chờ duyệt. |
| TCB | [BCTC Techcombank](https://techcombank.com/en/investors/financial-information/financial-statements-vas) · [BCTN](https://techcombank.com/en/investors/annual-report) | [CafeF TCB tài liệu](https://cafef.vn/du-lieu/hose/tcb-tai-lieu.chn) | [Tin TCB](https://cafef.vn/du-lieu/hose/tcb-tin-tuc.chn) · 28/09/2024–27/09/2026 đề xuất | Có 30 BCTC, 2 tài liệu BCTN và điều lệ làm mẫu đối chiếu; tải 28/09. | JSON API đã có. Cần chốt năm BCTN mục tiêu và ghi URL IR cho bộ BCTN; News chờ duyệt. |
| FPT | [IR FPT](https://fpt.com/vi/nha-dau-tu) · [BCTN](https://fpt.com/vi/nha-dau-tu/bao-cao-thuong-nien) | [CafeF FPT tài liệu](https://cafef.vn/du-lieu/hose/fpt-tai-lieu.chn) | [Tin FPT](https://cafef.vn/du-lieu/hose/fpt-tin-tuc.chn) · 28/09/2024–27/09/2026 đề xuất | 25 PDF CafeF phụ trợ; không có trong manifest. Chưa thấy BCTN ở các tên PDF. | JSON API đã có. Cần bổ sung provenance BCTN từ IR; giữ PDF CafeF tách riêng; News chờ duyệt. |
| CMG | [CMC — Báo cáo tài chính / tài liệu cổ đông](https://www.cmc.com.vn/shareholder/financial-report) | [CafeF CMG tài liệu](https://cafef.vn/du-lieu/hose/cmg-tai-lieu.chn) | [Tin CMG](https://cafef.vn/du-lieu/hose/cmg-tin-tuc.chn) · 28/09/2024–27/09/2026 đề xuất | Không có PDF CafeF phụ trợ cục bộ. | JSON API đã có. BCTN vẫn cần nguồn IR; BCTC chuẩn hóa API đã có; News chờ duyệt. |
| ELC | [ELCOM — BCTC](https://www.elcom.com.vn/co-dong/bao-cao-tai-chinh) · [BCTN 2025 PDF](https://www.elcom.com.vn/documents/1776653024_20260417_elc_bao_cao_thuong_nien_2025.pdf/view) | [CafeF ELC tài liệu](https://cafef.vn/du-lieu/hose/elc-tai-lieu.chn) | [Tin ELC](https://cafef.vn/du-lieu/hose/elc-tin-tuc.chn) · 28/09/2024–27/09/2026 đề xuất | Không có PDF CafeF phụ trợ cục bộ. | JSON API đã có (LCTT ít hơn 1 record so với các statement khác). BCTN cần IR; News chờ duyệt. |
| ITD | [ITD — Quan hệ cổ đông](https://itd.com.vn/quan-he-co-dong.html) | [CafeF ITD tài liệu](https://cafef.vn/du-lieu/hose/itd-tai-lieu.chn) | [Tin ITD](https://cafef.vn/du-lieu/hose/itd-tin-tuc.chn) · 28/09/2024–27/09/2026 đề xuất | Không có PDF CafeF phụ trợ cục bộ. | JSON API đã có (LCTT ít hơn 1 record); BCTN cần URL/provenance IR; News chờ duyệt. |
| ICT | [CTIN — Báo cáo thường niên 2024 PDF](https://ctin.vn/wp-content/uploads/2025/04/Bao-cao-thuong-nien-CTIN-2024.pdf) · [CTIN — trang chủ](https://ctin.vn/) | [CafeF ICT tài liệu](https://cafef.vn/du-lieu/hose/ict-tai-lieu.chn) | [Tin ICT](https://cafef.vn/du-lieu/hose/ict-tin-tuc.chn) · 28/09/2024–27/09/2026 đề xuất | Không có PDF CafeF phụ trợ cục bộ. | JSON API đã có, nhưng lịch sử OHLCV bắt đầu 2020 và số record BCTC/ratio thấp hơn các mã khác; BCTN cần IR; News chờ duyệt. |

## Coverage — cách hiểu “10 công ty × 7 kỳ”

JSON chuẩn hóa đã có cho **đủ 10/10 mã** từ Entrade/Vietcap. Số record tài chính hiện là 40–42 kỳ tùy mã (ICT có 31 ratios và 41 record cho mỗi báo cáo; ELC/ITD thiếu một record LCTT so với các báo cáo khác). Đây là coverage API đang có, không đồng nghĩa 7/7 kỳ thuộc ma trận Sprint 1 vì artifact trong workspace không ghi tên/định nghĩa 7 kỳ. Cần map ma trận đã chốt tới `period_label` trong JSON trước khi kết luận đủ/thiếu theo scope.

Tập PDF CafeF là artifact riêng, không phải nguồn tạo ra JSON API: manifest có 169 bản ghi cho 5 mã ngân hàng (148 BCTC, 10 BCTN, 11 tài liệu annual-category khác); tất cả được tải ngày 28/09/2026, sau mốc Sprint 1 27/09. FPT có 25 PDF chưa ghi vào manifest; CMG, ELC, ITD, ICT không có PDF CafeF cục bộ. Các con số này **không mô tả coverage JSON API**. Manifest: [`data/pdfs/cafef/manifest.json`](../data/pdfs/cafef/manifest.json).

| Nhóm mã | Coverage dữ liệu API | BCTN / nguồn báo cáo | Trạng thái ma trận 7 kỳ |
|---|---|---|---|
| VCB, BID, CTG, MBB, TCB, FPT, CMG, ELC, ITD, ICT | Có JSON BCTC + ratios từ Vietcap; OHLCV từ Entrade. Chi tiết theo mã ở bảng coverage phía trên. | API hiện tại không trả BCTN; cần URL tài liệu và provenance riêng từ IR. | **Chưa thể chấm đủ/thiếu theo 7 kỳ** đến khi có danh sách 7 kỳ và map period_label. |

PDF CafeF: VCB/BID/CTG/MBB/TCB có 28–31 BCTC/mã và 2 BCTN/mã (2024–2025); FPT có 25 PDF ngoài manifest; CMG/ELC/ITD/ICT không có PDF CafeF cục bộ. Đây là đối chiếu phụ, không phải tiêu chí độ phủ JSON API.

## Quyết nghị cần nhóm xác nhận để freeze

1. Xác nhận Entrade/Vietcap là nguồn API nhóm duyệt cho OHLCV và dữ liệu tài chính; ghi nhận giới hạn dùng theo điều khoản provider nếu có.
2. Map chính xác 7 kỳ đã chốt tới `period_label` và trạng thái từng record trong 10 JSON; không dùng tổng record để thay ma trận kỳ.
3. Chốt BCTN theo URL IR chính thức, năm/kỳ yêu cầu và provenance từng tài liệu.
4. Duyệt hoặc loại News CafeF; nếu duyệt thì xác nhận cửa sổ đề xuất 28/09/2024–27/09/2026, danh mục chủ đề, loại trùng và lưu URL bài gốc.
5. Giữ PDF CafeF ở vai trò tài liệu mapping: gắn nhãn chỉ tiêu API ↔ tên dòng trên báo cáo, period label ↔ kỳ báo cáo, đơn vị, công ty mẹ/hợp nhất và giá trị đối chiếu. Không dùng PDF này làm đầu vào ingest/OCR hay provenance của JSON.

**Gate kết luận:** JSON API đã có đủ 10 mã và mapping nguồn được phản ánh trong collector. Chưa xác nhận coverage 7 kỳ vì thiếu nhãn 7 kỳ trong artifact; BCTN cần đăng ký riêng; News chờ duyệt và tiếp tục loại khỏi corpus/Golden Test Set theo F05 đến khi có quyết định.

## Các trang nguồn đã kiểm tra

- Official IR: [Vietcombank](https://vietcombank.com.vn/vi-VN/Nha-dau-tu), [BIDV báo cáo và tài liệu](https://bidv.com.vn/vn/quan-he-nha-dau-tu/bao-cao-va-tai-lieu/), [VietinBank định kỳ](https://beta-investor.vietinbank.vn/vi/periodicreports.aspx/-/categories/471001), [MBBank](https://www.mbbank.com.vn/Investor/nha-dau-tu?lang=EN), [Techcombank BCTC](https://techcombank.com/en/investors/financial-information/financial-statements-vas) và [BCTN](https://techcombank.com/en/investors/annual-report), [FPT IR](https://fpt.com/vi/nha-dau-tu), [CMC reports](https://www.cmc.com.vn/shareholder/financial-report), [ELCOM BCTC](https://www.elcom.com.vn/co-dong/bao-cao-tai-chinh), [ITD IR](https://itd.com.vn/quan-he-co-dong.html), [CTIN BCTN 2024](https://ctin.vn/wp-content/uploads/2025/04/Bao-cao-thuong-nien-CTIN-2024.pdf).
- CafeF xác nhận trang tài liệu từng mã có các nhóm “Báo cáo tài chính” và “Bản cáo bạch & BCTN”; trang dữ liệu nêu nội dung chỉ có giá trị tham khảo và không chịu trách nhiệm rủi ro sử dụng: [ví dụ ICT tài liệu](https://cafef.vn/du-lieu/hose/ict-tai-lieu.chn), [hướng dẫn dữ liệu CafeF](https://cafef.vn/du-lieu/huong-dan-su-dung.chn), [RSS CafeF](https://cafef.vn/index.rss).
