# -*- coding: utf-8 -*-
"""Generate clean and perfectly ordered Golden_TestSet_Lo1_Lo2_TinTuc_GiaCoPhieu.md according to Option 1."""

content = """# BỘ CÂU HỎI KIỂM THỬ GOLDEN TEST SET (GOLDEN40)
## LÔ 1, LÔ 2, LÔ 3 & LÔ 4: TIN TỨC DOANH NGHIỆP, GIÁ CỔ PHIẾU, BCTN VÀ BCTC (Q01 – Q40)

*Dự án: FinMind – Research Copilot for Vietnamese Listed Companies*  
*Ngày cập nhật: 21/10/2026*  
*Phiên bản: v5.0 – Chuẩn hóa 100% theo Phương án 1 (Khớp tuyệt đối file chuẩn hóa data/normalized/ và source_register_Quan.md)*  
*Phạm vi 10 mã đã chốt: VCB, BID, CTG, MBB, TCB, FPT, CMG, ELC, ITD, ICT (100% tuân thủ danh mục phê duyệt)*  
*Nguồn dữ liệu & Data Provenance chuẩn hóa:*  
  - **Giá OHLCV:** Nguồn Entrade Chart API (`sources.prices = ENTRADE`), lưu tại file chuẩn hóa `data/normalized/{SYMBOL}.json` (kỳ lịch sử 2.174 – 2.176 phiên từ 02/01/2018 đến 25/09/2026). Giá lưu theo `price_scale = 1000` (ví dụ: close = 58.0 tương ứng 58.000 VND).  
  - **BCTC có cấu trúc:** Nguồn Vietcap VCI API (`sources.fundamentals = VIETCAP_VCI`), lưu tại `data_pipeline/FinancialCleaner/data/{SYMBOL}/tai_chinh_clean.json` (42 kỳ từ 2018-Q1 đến 2026-Q2) và bảng CSDL `public.observations`.  
  - **Báo cáo thường niên & BCTC kiểm toán PDF 2024:** Nguồn công bố thông tin chính thức HOSE / Quan hệ cổ đông IR FPT, kiểm toán độc lập bởi PwC Việt Nam, lưu tại `data/references/vietstock/annual_reports/files_pdf/FPT/2024/FPT_2024_498332.pdf`.  
  - **Tin tức doanh nghiệp:** Bảng CSDL `public.news_articles` (thu thập từ CafeF và FireAnt), phục vụ kiểm thử trích xuất thông tin ngữ nghĩa về sự kiện và nghiệp vụ doanh nghiệp.  
*Kỳ dữ liệu:* 29/07/2026 – 14/10/2026 (Tin tức), 02/01/2018 – 25/09/2026 (Giá OHLCV chuẩn hóa), Năm tài chính 2024 (BCTN PDF), 2018-Q1 đến 2026-Q2 (42 kỳ BCTC cấu trúc).

---

## MỤC LỤC
1. [Lô 1: Câu hỏi về TIN TỨC DOANH NGHIỆP (Q01 – Q10)](#lô-1-câu-hỏi-về-tin-tức-doanh-nghiệp-q01--q10)
2. [Lô 2: Câu hỏi về GIÁ CỔ PHIẾU (Q11 – Q20)](#lô-2-câu-hỏi-về-giá-cổ-phiếu-q11--q20)
3. [Lô 3: Câu hỏi về BÁO CÁO THƯỜNG NIÊN & BCTC FPT 2024 (Q21 – Q30)](#lô-3-bộ-dữ-liệu-kiểm-thử-báo-cáo-thường-niên--bctc-fpt-2024-q21--q30)
4. [Lô 4: Câu hỏi về BÁO CÁO TÀI CHÍNH FPT ĐA KỲ (Q31 – Q40)](#lô-4-bộ-dữ-liệu-kiểm-thử-báo-cáo-tài-chính-fpt-đa-kỳ-q31--q40)
5. [Bảng tổng hợp trạng thái rà soát (Q01 – Q40)](#bảng-tổng-hợp-trạng-thái-rà-soát-q01--q40)
6. [Chú thích nguồn dữ liệu, quy ước và giải trình xử lý 4 mâu thuẫn](#chú-thích-nguồn-dữ-liệu-quy-ước-và-giải-trình-xử-lý-4-mâu-thuẫn)
7. [Bảng tổng kết phân bổ bộ kiểm thử Golden40](#bảng-tổng-kết-phân-bổ-bộ-kiểm-thử-golden40-calibration-split)

---

## LÔ 1: CÂU HỎI VỀ TIN TỨC DOANH NGHIỆP (Q01 – Q10)

> **Giải trình xử lý mâu thuẫn Quyết định F05 & Quy chuẩn hỏi thông tin:**  
> - Theo biên bản `source_register_Quan.md`, dữ liệu Tin tức chưa đóng băng provider toàn diện cho production. Do đó, Lô 1 được chuẩn hóa thành **Tập kiểm thử hiệu chuẩn khả năng trích xuất thông tin ngữ nghĩa (Semantic Information Retrieval Calibration)** đối với các sự kiện nghiệp vụ thực tế của các mã trong danh mục 10 mã đã được phê duyệt.  
> - **100% câu hỏi đều hỏi thông tin sự kiện, nghiệp vụ, số liệu tài chính cụ thể của doanh nghiệp.**  
> - **Tuyệt đối KHÔNG sử dụng dạng câu hỏi truy vấn thống kê siêu dữ liệu (metadata counting)** như "có tổng số bao nhiêu bài viết".  
> - **Đa dạng hóa nguồn tin:** Mỗi câu hỏi trích xuất từ một bài báo độc lập, không trùng lặp bài báo giữa các câu hỏi (Q01 đến Q10 trích xuất từ 10 bài báo khác nhau).

---

### Q01
*Phân loại: tin_trái_phiếu_doanh_nghiệp*

- **Câu hỏi:** Theo tin tức thị trường tài chính ngày 01/10/2026, Techcombank (TCB) đã tất toán trước hạn 2 lô trái phiếu nào sau 1 năm phát hành với tổng giá trị bao nhiêu tỷ đồng?
- **Đáp án:** Techcombank tất toán trước hạn 2 lô trái phiếu mã **TCB12517** (1.740 tỷ đồng) và **TCB12518** (2.500 tỷ đồng), tổng giá trị **4.240 tỷ đồng**.
- **Đơn vị:** Tỷ đồng (VND), mã trái phiếu
- **Kỳ báo cáo:** 01/10/2026
- **Tài liệu gốc:** Supabase `public.news_articles` (source: fireant, published_at: 2026-10-01) → Title: *"TCB: Techcombank tất toán 2 lô trái phiếu sau 1 năm phát hành"*
- **Chi tiết kiểm chứng:** source: fireant | published_at: 2026-10-01 | symbols: ["TCB"] | Trích nội dung: *"Techcombank đã chi tổng cộng 4.240 tỷ đồng để tất toán 2 lô trái phiếu TCB12517 và TCB12518 chỉ sau 1 năm phát hành... cụ thể ngày 30/9/2026, Techcombank tiến hành mua lại toàn bộ 2.000 trái phiếu mã TCB12517 và TCB12518"*
- **Trạng thái:** ✅ Chính xác – 100% khớp dữ liệu bài viết Supabase

---

### Q02
*Phân loại: tin_nghiệp_vụ_ngân_hàng*

- **Câu hỏi:** Theo thông tin biểu lãi suất huy động tháng 10/2026 của VietinBank (CTG), khách hàng gửi tiết kiệm 300 triệu đồng ở kỳ hạn 24 tháng sẽ nhận được bao nhiêu tiền lãi (với khung lãi suất huy động 0,1% – 6,0%/năm)?
- **Đáp án:** Số tiền lãi nhận được là **36 triệu đồng** (áp dụng mức lãi suất 6,0%/năm cho kỳ hạn 24 tháng).
- **Đơn vị:** Triệu đồng (VND), %/năm
- **Kỳ báo cáo:** Tháng 10/2026 (ngày đăng bài 01/10/2026)
- **Tài liệu gốc:** Supabase `public.news_articles` (source: fireant, published_at: 2026-10-01) → Title: *"Lãi suất VietinBank cao nhất, gửi 300 triệu đồng nhận 36 triệu đồng tiền lãi"*
- **Chi tiết kiểm chứng:** source: fireant | published_at: 2026-10-01 | symbols: ["CTG"] | Trích nội dung: *"Lãi suất VietinBank hiện dao động từ 0,1-6%/năm. Khách hàng gửi 300 triệu đồng kỳ hạn 24 tháng có thể nhận khoảng 36 triệu đồng tiền lãi"*
- **Trạng thái:** ✅ Chính xác – 100% khớp dữ liệu bài viết Supabase

---

### Q03
*Phân loại: tin_phát_hành_cổ_phiếu*

- **Câu hỏi:** Theo tin tức công bố, FPT đã phân phối bao nhiêu cổ phiếu tăng vốn từ nguồn vốn chủ sở hữu, cho bao nhiêu cổ đông và kết thúc đợt phát hành vào ngày nào (theo bài đăng ngày 29/09/2026)?
- **Đáp án:** FPT phân phối hơn **171,4 triệu cổ phiếu** cho **181.748 cổ đông**. Ngày kết thúc đợt phát hành là ngày **22/09/2026**.
- **Đơn vị:** Triệu cổ phiếu, cổ đông
- **Kỳ báo cáo:** 22/09/2026 (ngày kết thúc phát hành)
- **Tài liệu gốc:** Supabase `public.news_articles` (source: cafef, published_at: 2026-09-29) → Title: *"Sau màn hát “Tái sinh” của ông Trương Gia Bình, mỗi tháng FPT có thêm 6.000 cổ đông mới, sân vận động lớn nhất thế giới và Mỹ Đình cộng lại không đủ sức chứa"*
- **Chi tiết kiểm chứng:** source: cafef | published_at: 2026-09-29 | symbols: ["FPT"] | Trích nội dung: *"FPT đã phân phối hơn 171,4 triệu cổ phiếu cho 181.748 cổ đông. Ngày kết thúc đợt phát hành là 22/09/2026"*
- **Trạng thái:** ✅ Chính xác – Số liệu xác thực trực tiếp từ bài báo

---

### Q04
*Phân loại: tin_cơ_cấu_cổ_đông*

- **Câu hỏi:** Số lượng cổ đông của FPT tính đến thời điểm bài báo ngày 29/09/2026 là bao nhiêu, và tỷ lệ sở hữu của khối ngoại còn bao nhiêu phần trăm?
- **Đáp án:** FPT có gần **182.000 cổ đông**. Khối ngoại nắm giữ **28,5% vốn** (giảm từ mức 49% cuối năm 2022).
- **Đơn vị:** Cổ đông, %
- **Kỳ báo cáo:** 29/09/2026
- **Tài liệu gốc:** Supabase `public.news_articles` (source: fireant, published_at: 2026-09-29) → Title: *"FPT: Có gần 182.000 cổ đông, khối ngoại còn nắm 28,5% vốn"*
- **Chi tiết kiểm chứng:** source: fireant | published_at: 2026-09-29 | symbols: ["FPT"] | Trích nội dung: *"Khối ngoại từ tỷ lệ sở hữu 49% cuối năm 2022 giờ chỉ còn nắm giữ 28,5% vốn doanh nghiệp"*
- **Trạng thái:** ✅ Chính xác – Dữ liệu ghi rõ trong tiêu đề và nội dung

---

### Q05
*Phân loại: tin_dự_báo_KQKD*

- **Câu hỏi:** Theo ước tính của SSI Research trong bản tin ngày 29/09/2026, những ngân hàng nào trong nhóm theo dõi được dự báo đạt hoặc vượt mốc 10.000 tỷ đồng lợi nhuận trước thuế trong quý 3/2026?
- **Đáp án:** **Vietcombank (VCB)** và **VietinBank (CTG)** được dự báo vượt mốc 10.000 tỷ đồng LNTT; trong khi **MB (MBB)** và VPBank (VPB) được dự báo cùng chạm mốc 10.000 tỷ đồng.
- **Đơn vị:** Tỷ đồng (VND)
- **Kỳ báo cáo:** Quý 3/2026 (dự báo)
- **Tài liệu gốc:** Supabase `public.news_articles` (source: fireant, published_at: 2026-09-29) → Title: *"Những ngân hàng có thể lãi trên 10.000 tỷ đồng trong quý III"*
- **Chi tiết kiểm chứng:** source: fireant | published_at: 2026-09-29 | symbols: ["ACB", "BID", "CTG", "MBB", "MSB", "TCB", "TPB", "VCB", "VIB", "VPB"] | Trích: *"VietinBank và Vietcombank có thể vượt 10.000 tỷ đồng... MB và VPBank được dự báo cùng chạm mốc này"*
- **Trạng thái:** ✅ Chính xác – Trích dẫn rõ ràng từ SSI Research

---

### Q06
*Phân loại: tin_quy_mô_doanh_nghiệp*

- **Câu hỏi:** Theo tin tức công bố ngày 30/09/2026, Ngân hàng Quân đội (MBB) có quy mô tổng tài sản đạt bao nhiêu và hệ sinh thái gồm bao nhiêu doanh nghiệp thành viên?
- **Đáp án:** MBB có quy mô tài sản hơn **1,73 triệu tỷ đồng** và hệ sinh thái gồm **8 doanh nghiệp thành viên**.
- **Đơn vị:** Triệu tỷ đồng (VND), doanh nghiệp
- **Kỳ báo cáo:** 30/09/2026
- **Tài liệu gốc:** Supabase `public.news_articles` (source: fireant, published_at: 2026-09-30) → Title: *"MB mở rộng vai trò kết nối dòng vốn"*
- **Chi tiết kiểm chứng:** source: fireant | published_at: 2026-09-30 | symbols: ["MBB", "VCB"] | Trích: *"Với quy mô tài sản hơn 1 73 triệu tỷ đồng cùng hệ sinh thái 8 doanh nghiệp thành viên chiến lược của MB..."*
- **Trạng thái:** ✅ Chính xác – Dữ liệu rõ ràng trong nội dung bài báo

---

### Q07
*Phân loại: tin_tăng_vốn_điều_lệ*

- **Câu hỏi:** Theo bản tin công bố thông tin doanh nghiệp ngày 14/10/2026, Techcombank (TCB) đã nhận được văn bản chấp thuận nội dung quan trọng nào từ cơ quan quản lý?
- **Đáp án:** Techcombank nhận được văn bản chấp thuận từ Ngân hàng Nhà nước về **phương án tăng vốn điều lệ**.
- **Đơn vị:** Quyết định phê duyệt / Phương án vốn
- **Kỳ báo cáo:** 14/10/2026
- **Tài liệu gốc:** Supabase `public.news_articles` (source: fireant, published_at: 2026-10-14) → Title: *"Tài chính doanh nghiệp 24/7: Techcombank được chấp thuận tăng vốn, FPT thúc đẩy hợp tác lượng tử"*
- **Chi tiết kiểm chứng:** source: fireant | published_at: 2026-10-14 | symbols: ["FPT", "NLG", "TCB"] | Trích: *"Bản tin Tài chính doanh nghiệp 24/7 ngày 14/10 ghi nhận phương án tăng vốn của Techcombank..."*
- **Trạng thái:** ✅ Chính xác – Nội dung công bố chính thức

---

### Q08
*Phân loại: tin_phân_tích_ngân_hàng*

- **Câu hỏi:** Theo báo cáo phân tích ngành ngân hàng ngày 30/09/2026, cổ phiếu ngân hàng nào được đánh giá là điểm sáng tăng trưởng lợi nhuận nhờ lợi thế chi phí vốn thấp và chất lượng tài sản vượt trội?
- **Đáp án:** **Vietcombank (VCB)** được đánh giá là điểm sáng tăng trưởng lợi nhuận với biên lãi thuần (NIM) duy trì ổn định và chất lượng tài sản vượt trội.
- **Đơn vị:** Tên mã CP / Tổ chức
- **Kỳ báo cáo:** 30/09/2026
- **Tài liệu gốc:** Supabase `public.news_articles` (source: fireant, published_at: 2026-09-30) → Title: *"Chứng khoán thời lãi suất cao: Gọi tên PVS, BSR và điểm sáng VCB"*
- **Chi tiết kiểm chứng:** source: fireant | published_at: 2026-09-30 | symbols: ["BSR", "PVS", "VCB"] | Trích: *"trong khi VCB ghi nhận lợi nhuận tăng trưởng ấn tượng trong môi trường lãi suất cao... DSC khuyến nghị mua cổ phiếu VCB dựa trên triển vọng kết quả kinh doanh và chất lượng tài sản"*
- **Trạng thái:** ✅ Chính xác – Khớp báo cáo phân tích chuyên ngành

---

### Q09
*Phân loại: tin_chính_sách_ngân_hàng*

- **Câu hỏi:** Theo tin tức tài chính ngân hàng ngày 06/10/2026, Ngân hàng Nhà nước đã điều chỉnh nới trần tỷ lệ dư nợ cho vay trên tổng tiền gửi (LDR) từ mức bao nhiêu % lên bao nhiêu %, hướng tới tiệm cận chuẩn mực nào?
- **Đáp án:** Trần tỷ lệ LDR được nới từ **85% lên 95%**, hướng tới tiệm cận chuẩn mực quản trị an toàn thanh khoản quốc tế **Basel III**.
- **Đơn vị:** %, Chuẩn mực ngân hàng
- **Kỳ báo cáo:** 06/10/2026
- **Tài liệu gốc:** Supabase `public.news_articles` (source: fireant, published_at: 2026-10-06) → Title: *"Nới trần LDR lên 95%: Ngân hàng được 'mở khóa' thêm room cho vay"*
- **Chi tiết kiểm chứng:** source: fireant | published_at: 2026-10-06 | symbols: [] | Trích: *"Ngân hàng Nhà nước vừa nâng trần tỷ lệ cho vay trên tiền gửi (LDR) từ 85% lên 95%, đồng thời thay đổi cách tính theo hướng tiệm cận chuẩn Basel III"*
- **Trạng thái:** ✅ Chính xác – Thông tin chính sách vĩ mô ngành ngân hàng tác động trực tiếp nhóm ngân hàng (VCB, BID, CTG, MBB, TCB)

---

### Q10
*Phân loại: tin_quy_mô_nhân_sự_doanh_nghiệp*

- **Câu hỏi:** Theo tin tức công bố ngày 13/10/2026, tính đến ngày 30/09/2026, tổng quy mô nhân sự trên toàn hệ sinh thái của Tập đoàn FPT đạt xấp xỉ bao nhiêu người, tăng thêm bao nhiêu người so với cuối năm 2025?
- **Đáp án:** Tổng quy mô nhân sự toàn hệ sinh thái của FPT đạt **gần 90.000 người**, tăng thêm **3.682 người** (tương đương tăng **4,3%**) so với cuối năm 2025 (trong đó khối các đơn vị được hợp nhất trong BCTC ghi nhận 45.145 nhân sự).
- **Đơn vị:** Người, %
- **Kỳ báo cáo:** 30/09/2026 (ngày công bố 13/10/2026)
- **Tài liệu gốc:** Supabase `public.news_articles` (source: cafef, published_at: 2026-10-13) → Title: *"Nhân sự FPT xấp xỉ 90.000 người, tăng 3.682 người trong 9 tháng"*
- **Chi tiết kiểm chứng:** source: cafef | published_at: 2026-10-13 | symbols: ["FPT"] | Trích nội dung: *"Theo số liệu FPT công bố, đến ngày 30/9/2026, tổng số nhân sự trên toàn hệ sinh thái, bao gồm 7 công ty con và 4 công ty liên kết, đạt gần 90.000 người, tăng thêm 3.682 người so với cuối năm 2025, tương đương 4,3%... Nếu tính riêng các đơn vị được hợp nhất trong báo cáo tài chính, FPT có 45.145 nhân sự tại ngày 30/9/2026"*
- **Trạng thái:** ✅ Chính xác – Độc lập 100%, không trùng bài báo với Q07, hỏi số liệu nghiệp vụ/nhân sự phát triển thực tế của doanh nghiệp

---

## LÔ 2: CÂU HỎI VỀ GIÁ CỔ PHIẾU (Q11 – Q20)

> **Giải trình Phương án 1 (Chuẩn hóa 100% theo `source_register_Quan.md`):**  
> - Toàn bộ 10 câu hỏi Lô 2 được trích xuất và tính toán tất định trực tiếp từ các file dữ liệu chuẩn hóa chính thức của dự án: `data/normalized/{SYMBOL}.json` (nguồn: **Entrade Chart API**, `sources.prices = ENTRADE`).  
> - **Kỳ dữ liệu chuẩn hóa:** Bao phủ toàn diện lịch sử từ **02/01/2018 đến 25/09/2026** (2.174 – 2.176 phiên giao dịch cho mỗi mã).  
> - **Quy ước đơn vị giá:** Giá trong file JSON được chuẩn hóa theo hệ số `price_scale = 1000` (ví dụ: `close = 58.0` tương ứng giá thị trường thực tế là `58.000 VND`).  
> - **Tính nhất quán tuyệt đối:** Bất kỳ ai mở trực tiếp file `data/normalized/{SYMBOL}.json` hoặc bảng CSDL `public.price_bars` ra đối soát đều tìm thấy chính xác từng phiên, từng mức giá và khối lượng khớp lệnh mà không có độ lệch nào.

---

### Q11
*Phân loại: giá_biến_động_toàn_kỳ*

- **Câu hỏi:** Trong file dữ liệu giá chuẩn hóa `data/normalized/VCB.json`, giá đóng cửa (Close) của VCB tại phiên giao dịch cuối cùng (25/09/2026) là bao nhiêu, và so với phiên giao dịch đầu tiên (02/01/2018) thì đã biến động tăng bao nhiêu phần trăm?
- **Đáp án:** Close phiên cuối (25/09/2026): **58,0 (×1.000 VND)**. Close phiên đầu (02/01/2018): **23,06 (×1.000 VND)**. Tỷ lệ tăng trưởng toàn kỳ đạt: **+151,52%**.
- **Đơn vị:** ×1.000 VND (price_scale = 1000), %
- **Kỳ báo cáo:** 02/01/2018 – 25/09/2026 (toàn bộ 2.174 phiên)
- **Tài liệu gốc:** `data/normalized/VCB.json` & bảng `public.price_bars` (symbol="VCB")
- **Chi tiết kiểm chứng:** Record đầu tiên: `date: "2018-01-02", close: 23.06`. Record cuối cùng: `date: "2026-09-25", close: 58.0`. Biến động: `(58.0 - 23.06) / 23.06 * 100% = +151.5178% -> +151,52%`. Nguồn: ENTRADE.
- **Trạng thái:** ✅ Chính xác – Khớp 100% với dữ liệu chuỗi thời gian chuẩn hóa

---

### Q12
*Phân loại: giá_volume_kỷ_lục_lịch_sử*

- **Câu hỏi:** Trong toàn bộ lịch sử dữ liệu giá của mã cổ phiếu MBB, phiên giao dịch nào ghi nhận khối lượng (Volume) khớp lệnh kỷ lục lớn nhất mọi thời đại và khối lượng đó đạt bao nhiêu cổ phiếu?
- **Đáp án:** Phiên ngày **15/08/2025** ghi nhận khối lượng khớp lệnh kỷ lục đạt **117.471.296 cổ phiếu** (giá đóng cửa phiên đạt 22,62 ×1.000 VND).
- **Đơn vị:** Cổ phiếu, ngày giao dịch
- **Kỳ báo cáo:** 02/01/2018 – 25/09/2026 (2.175 phiên)
- **Tài liệu gốc:** `data/normalized/MBB.json` & bảng `public.price_bars` (symbol="MBB")
- **Chi tiết kiểm chứng:** `max(price_history, key=lambda x: x['volume'])` -> `date: "2025-08-15", volume: 117471296, open: 23.63, high: 23.63, low: 22.18, close: 22.62`. Nguồn: ENTRADE.
- **Trạng thái:** ✅ Chính xác – Tính toán cực trị toàn vẹn trên toàn bộ 2.175 bars lịch sử

---

### Q13
*Phân loại: giá_cực_trị_lịch_sử*

- **Câu hỏi:** Trong toàn bộ dữ liệu lịch sử giá của Tập đoàn FPT (`data/normalized/FPT.json`), mức giá đóng cửa cao nhất (Highest Close) và thấp nhất (Lowest Close) lần lượt là bao nhiêu (×1.000 VND), đạt được vào ngày nào?
- **Đáp án:** Highest Close đạt **118,06 (×1.000 VND)** vào ngày **23/01/2025**. Lowest Close ghi nhận **10,75 (×1.000 VND)** vào ngày **12/07/2018**.
- **Đơn vị:** ×1.000 VND
- **Kỳ báo cáo:** 02/01/2018 – 25/09/2026 (2.175 phiên)
- **Tài liệu gốc:** `data/normalized/FPT.json` & bảng `public.price_bars` (symbol="FPT")
- **Chi tiết kiểm chứng:** FPT max close: `date: "2025-01-23", close: 118.06`. FPT min close: `date: "2018-07-12", close: 10.75`. Nguồn: ENTRADE.
- **Trạng thái:** ✅ Chính xác – Khớp 100% toàn dải dữ liệu 2.175 phiên

---

### Q14
*Phân loại: giá_volume_trung_bình_20_phiên*

- **Câu hỏi:** Khối lượng giao dịch (Volume) bình quân 20 phiên gần nhất (tính đến phiên giao dịch cuối cùng 25/09/2026) của cổ phiếu MBB đạt bao nhiêu cổ phiếu/phiên?
- **Đáp án:** Khối lượng giao dịch bình quân 20 phiên đạt **11.900.830 cổ phiếu/phiên** (tổng volume 20 phiên đạt 238.016.600 cổ phiếu).
- **Đơn vị:** Cổ phiếu/phiên
- **Kỳ báo cáo:** 20 phiên giao dịch gần nhất từ 26/08/2026 đến 25/09/2026
- **Tài liệu gốc:** `data/normalized/MBB.json` & bảng `public.price_bars` (symbol="MBB")
- **Chi tiết kiểm chứng:** Dải 20 phiên từ 26/08/2026 đến 25/09/2026: `sum(volume) = 238,016,600 CP`. `SMA20_volume = 238,016,600 / 20 = 11,900,830 CP/phiên`. Nguồn: ENTRADE.
- **Trạng thái:** ✅ Chính xác – Tính toán tất định trên 20 phiên gần nhất của chuỗi giá chuẩn hóa

---

### Q15
*Phân loại: giá_OHLCV_phiên_cụ_thể*

- **Câu hỏi:** Trong phiên giao dịch ngày 20/05/2026 (phiên thanh khoản đột biến thị trường), các mức giá mở cửa (Open), cao nhất (High), thấp nhất (Low), đóng cửa (Close) và khối lượng khớp lệnh của VCB là bao nhiêu?
- **Đáp án:** Open = **63,17** | High = **64,17** | Low = **61,29** | Close = **64,07 (×1.000 VND)**. Khối lượng khớp lệnh đạt **14.381.600 cổ phiếu**.
- **Đơn vị:** ×1.000 VND, cổ phiếu
- **Kỳ báo cáo:** 20/05/2026
- **Tài liệu gốc:** `data/normalized/VCB.json` & bảng `public.price_bars` (symbol="VCB", date="2026-05-20")
- **Chi tiết kiểm chứng:** Record ngày 2026-05-20 trong VCB.json: `open: 63.17, high: 64.17, low: 61.29, close: 64.07, volume: 14381600`. Nguồn: ENTRADE.
- **Trạng thái:** ✅ Chính xác – Trích xuất trực tiếp bản ghi nến giá chuẩn xác từng chữ số thập phân

---

### Q16
*Phân loại: giá_so_sánh_mã*

- **Câu hỏi:** So sánh biến động giá đóng cửa trong tháng 09/2026 (từ phiên 03/09/2026 đến phiên 25/09/2026) giữa 3 mã bluechip VCB, MBB và FPT: Cổ phiếu nào duy trì biên độ giảm ít nhất (giữ giá tốt nhất)?
- **Đáp án:** **VCB** giữ giá tốt nhất với mức giảm chỉ **−1,19%** (từ 58,70 xuống 58,00 ×1.000 VND); trong khi FPT giảm **−1,43%** (từ 65,64 xuống 64,70 ×1.000 VND) và MBB giảm **−3,40%** (từ 20,60 xuống 19,90 ×1.000 VND).
- **Đơn vị:** %, ×1.000 VND
- **Kỳ báo cáo:** Tháng 09/2026 (03/09/2026 – 25/09/2026, gồm 17 phiên giao dịch)
- **Tài liệu gốc:** `data/normalized/{SYMBOL}.json` & bảng `public.price_bars` (symbols: VCB, MBB, FPT)
- **Chi tiết kiểm chứng:** 
  - VCB: `(58.00 - 58.70) / 58.70 * 100% = -1.19%`.
  - FPT: `(64.70 - 65.64) / 65.64 * 100% = -1.43%`.
  - MBB: `(19.90 - 20.60) / 20.60 * 100% = -3.40%`. Nguồn: ENTRADE.
- **Trạng thái:** ✅ Chính xác – Phép so sánh đa mã tất định trên tập dữ liệu chuẩn hóa

---

### Q17
*Phân loại: giá_biên_độ_phiên_cực_đại*

- **Câu hỏi:** Trong toàn bộ chuỗi lịch sử giá của FPT, phiên giao dịch nào có biên độ dao động giá trong ngày (High trừ Low) lớn nhất và biên độ đó là bao nhiêu (×1.000 VND)?
- **Đáp án:** Phiên ngày **09/04/2025** có biên độ dao động lớn nhất là **7,80 (×1.000 VND)** (tương ứng 7.800 đ/cổ phiếu, với High = 82,64 và Low = 74,84).
- **Đơn vị:** ×1.000 VND, ngày giao dịch
- **Kỳ báo cáo:** 02/01/2018 – 25/09/2026 (2.175 phiên)
- **Tài liệu gốc:** `data/normalized/FPT.json` & bảng `public.price_bars` (symbol="FPT")
- **Chi tiết kiểm chứng:** `max(price_history, key=lambda x: round(x['high'] - x['low'], 2))` -> `date: "2025-04-09", high: 82.64, low: 74.84, open: 74.84, close: 80.57`. Biên độ: `82.64 - 74.84 = 7.80`. Nguồn: ENTRADE.
- **Trạng thái:** ✅ Chính xác – Cực trị biên độ phiên chuẩn xác trên toàn bộ chuỗi lịch sử

---

### Q18
*Phân loại: metadata_chuỗi_giá*

- **Câu hỏi:** Trong file dữ liệu giá chuẩn hóa `data/normalized/VCB.json` từ nguồn Entrade Chart API, mã cổ phiếu VCB ghi nhận tổng cộng bao nhiêu phiên giao dịch (bars) trong khoảng thời gian từ ngày 02/01/2018 đến 25/09/2026?
- **Đáp án:** **2.174 phiên giao dịch (bars)**, bao phủ đầy đủ toàn bộ các ngày làm việc liên tục của sàn HOSE từ đầu năm 2018 đến cuối tháng 9/2026.
- **Đơn vị:** Bars (phiên giao dịch)
- **Kỳ báo cáo:** 02/01/2018 – 25/09/2026
- **Tài liệu gốc:** `data/normalized/VCB.json` & đối chiếu dòng 54 trong `docs/review/source_register_Quan.md`
- **Chi tiết kiểm chứng:** `len(price_history) = 2,174`. Khớp chính xác 100% với bảng thống kê độ phủ nguồn trong `source_register_Quan.md` (*"VCB: 2018-01-02–2026-09-25 · 2.174 phiên"*). Nguồn: ENTRADE.
- **Trạng thái:** ✅ Chính xác – Đếm trực tiếp từ dữ liệu CSDL chuẩn hóa

---

### Q19
*Phân loại: giá_volume_kỷ_lục*

- **Câu hỏi:** Trong toàn bộ dữ liệu lịch sử giá của VCB, phiên giao dịch ngày 23/04/2026 ghi nhận volume kỷ lục là bao nhiêu, và các mức giá mở cửa (Open), cao nhất (High), thấp nhất (Low), đóng cửa (Close) của phiên này lần lượt là bao nhiêu?
- **Đáp án:** Volume kỷ lục: **35.200.000 cổ phiếu**. Open = **59,21** | High = **62,98** | Low = **59,11** | Close = **62,28 (×1.000 VND)**.
- **Đơn vị:** Cổ phiếu, ×1.000 VND (price_scale = 1000)
- **Kỳ báo cáo:** 23/04/2026
- **Tài liệu gốc:** `data/normalized/VCB.json` & bảng `public.price_bars` (symbol="VCB", date="2026-04-23")
- **Chi tiết kiểm chứng:** Record 2026-04-23 trong VCB.json: `open: 59.21, high: 62.98, low: 59.11, close: 62.28, volume: 35200000`. Đây cũng là phiên volume kỷ lục toàn bộ lịch sử của VCB. Nguồn: ENTRADE.
- **Trạng thái:** ✅ Chính xác – Trích xuất trực tiếp 100% từ file giá chuẩn hóa

---

### Q20
*Phân loại: giá_so_sánh_phiên*

- **Câu hỏi:** So sánh giá đóng cửa của MBB giữa phiên đạt đỉnh ngắn hạn 17/09/2026 và phiên kết thúc dữ liệu 25/09/2026: chênh lệch bao nhiêu và theo hướng tăng hay giảm?
- **Đáp án:** Close ngày 17/09/2026: **20,55** → Close ngày 25/09/2026: **19,90 (×1.000 VND)**. Giảm **0,65 (×1.000 VND)** (tương ứng giảm 650 đ/cổ phiếu), tỷ lệ giảm đạt **−3,16%**.
- **Đơn vị:** ×1.000 VND, %
- **Kỳ báo cáo:** 17/09/2026 vs 25/09/2026
- **Tài liệu gốc:** `data/normalized/MBB.json` & bảng `public.price_bars` (symbol="MBB")
- **Chi tiết kiểm chứng:** MBB 2026-09-17: `close: 20.55` | MBB 2026-09-25: `close: 19.90` | Chênh lệch: `19.90 - 20.55 = -0.65`, tỷ lệ: `-0.65 / 20.55 * 100% = -3.163% -> -3,16%`. Nguồn: ENTRADE.
- **Trạng thái:** ✅ Chính xác – So sánh trực tiếp 2 records cụ thể trong chuỗi dữ liệu chuẩn hóa

---

## LÔ 3: BỘ DỮ LIỆU KIỂM THỬ BÁO CÁO THƯỜNG NIÊN & BCTC FPT 2024 (Q21 – Q30)

- **Tập đoàn**: FPT (Công ty Cổ phần FPT)
- **Tài liệu nguồn**: Báo cáo thường niên 2024 & Báo cáo tài chính hợp nhất kiểm toán năm 2024 của FPT (Công bố chính thức trên HOSE / Quan hệ nhà đầu tư IR FPT; kiểm toán độc lập bởi PwC Việt Nam; lưu trữ tại `data/references/vietstock/annual_reports/files_pdf/FPT/2024/FPT_2024_498332.pdf`).
- **Mục tiêu kỹ thuật**: Đánh giá năng lực của pipeline RAG phi cấu trúc (Unstructured Document RAG) đối với bảng biểu, thuyết minh kế toán, quản trị công ty và ca từ chối an toàn (Safe Refusal).
- **Quy chuẩn đối soát**: Đặc tả yêu cầu phần mềm FinMind ([SOFTWARE REQUIREMENTS SPECIFICATION (2).docx](file:///c:/Users/dieuh/Downloads/FPT/SOFTWARE%20REQUIREMENTS%20SPECIFICATION%20(2).docx))
- **Mã lô**: `BATCH-03` (`Q21` đến `Q30` / Mã gốc: `QA-FPT24-001` đến `QA-FPT24-010`)
- **Nguyên tắc rà soát**: 
  - Không trùng lặp hoặc mang nội dung gần giống nhau.
  - Mỗi câu hỏi có định danh (ID) đồng bộ liên tục (`Q21` – `Q30`), đồng thời đối chiếu mã gốc để truy vết.
  - Có đầy đủ đáp án chuẩn, đơn vị tính, kỳ báo cáo, định vị kiểm chứng (trang PDF, trang in, mục/bảng/dòng) và ghi chú rà soát kỹ thuật.

---

### Q21 (QA-FPT24-001)
*Phân loại: bctn_kết_quả_kinh_doanh (doanh_thu_thuần)*

- **Câu hỏi**: Tổng doanh thu thuần về bán hàng và cung cấp dịch vụ hợp nhất của FPT trong năm 2024 là bao nhiêu?
- **Đáp án chuẩn**: `62.848.794.351.367 VND` (hoặc `62.849 tỷ VND`).
- **Phép so khớp (Matching logic)**: Regex tolerance so sánh số nguyên hoặc số tỷ làm tròn trong biên độ $\pm 0.1\%$.
- **Vị trí đối soát**:
  - BCTC kiểm toán: Trang PDF 153 (Trang in 151), *Báo cáo kết quả HĐKD hợp nhất* (Mẫu B 02-DN/HN), Mã số 10, Cột năm 2024.
  - BCTN tóm tắt: Trang PDF 52 (Trang in 50), Bảng Chỉ tiêu hoạt động kinh doanh chính.
- **Trạng thái**: ✅ Đã xác thực (Chấp nhận cả giá trị đồng nguyên vẹn và số làm tròn tỷ đồng).

---

### Q22 (QA-FPT24-002)
*Phân loại: bctn_lợi_nhuận_cổ_đông_mẹ*

- **Câu hỏi**: Lợi nhuận sau thuế thu nhập doanh nghiệp phân bổ cho cổ đông của công ty mẹ FPT năm 2024 là bao nhiêu?
- **Đáp án chuẩn**: `7.856.767.812.178 VND` (hoặc `7.857 tỷ VND`).
- **Lưu ý bẫy dữ liệu**: Không chấp nhận con số `9.427.422.530.444 VND` (đây là tổng LNST hợp nhất gồm cả cổ đông không kiểm soát tại Mã số 60). Cần kiểm tra xem mô hình RAG có lấy đúng đối tượng "cổ đông công ty mẹ" hay không.
- **Vị trí đối soát**: Trang PDF 154 (Trang in 152), *Báo cáo kết quả HĐKD hợp nhất (tiếp)*, Mã số 61 ("Cổ đông của công ty mẹ"), Cột năm 2024.
- **Trạng thái**: ⚠️ Lưu ý rà soát (Cần phân biệt rõ với Tổng LNST hợp nhất toàn tập đoàn).

---

### Q23 (QA-FPT24-003)
*Phân loại: bctn_bảng_cân_đối (tổng_tài_sản)*

- **Câu hỏi**: Tổng tài sản hợp nhất của Tập đoàn FPT tại ngày kết thúc năm tài chính 31/12/2024 đạt bao nhiêu?
- **Đáp án chuẩn**: `71.999.995.678.620 VND` (hoặc `~72.000 tỷ VND`).
- **Vị trí đối soát**: Trang PDF 150 (Trang in 148), *Bảng cân đối kế toán hợp nhất (tiếp)* (Mẫu B 01-DN/HN), Mã số 270 ("TỔNG TÀI SẢN"), Cột năm 2024. Khớp số làm tròn 72.000 tỷ đồng tại trang PDF 52.
- **Trạng thái**: ✅ Đã xác thực (Khớp chính xác với bảng tóm tắt chỉ tiêu tại trang PDF 52).

---

### Q24 (QA-FPT24-004)
*Phân loại: bctn_lưu_chuyển_tiền_thuần (dòng_tiền_kinh_doanh)*

- **Câu hỏi**: Lưu chuyển tiền thuần từ hoạt động kinh doanh hợp nhất của FPT trong năm 2024 đạt bao nhiêu?
- **Đáp án chuẩn**: `11.703.777.188.868 VND` (hoặc `~11.704 tỷ VND`).
- **Vị trí đối soát**: Trang PDF 155 (Trang in 153), *Báo cáo lưu chuyển tiền tệ hợp nhất (phương pháp gián tiếp)* (Mẫu B 03-DN/HN), Mã số 20, Cột năm 2024.
- **Trạng thái**: ✅ Đã xác thực.

---

### Q25 (QA-FPT24-005)
*Phân loại: bctn_thuyết_minh (doanh_thu_nước_ngoài)*

- **Câu hỏi**: Theo Thuyết minh báo cáo tài chính hợp nhất, doanh thu thuần phát sinh từ thị trường nước ngoài của Tập đoàn FPT năm 2024 là bao nhiêu?
- **Đáp án chuẩn**: `31.294.207 triệu VND` (hoặc `31.294 tỷ VND`).
- **Lưu ý bẫy đối chiếu**: Trong Báo cáo của Ban Điều hành (trang PDF 51) có nêu con số `30.953 tỷ đồng` (tương đương 1,2 tỷ USD), nhưng đó là chỉ tiêu cho riêng *Lĩnh vực Dịch vụ CNTT cho thị trường nước ngoài*. Trong khi Thuyết minh 34(b) (trang PDF 199) là *Toàn bộ doanh thu khu vực nước ngoài* (31.294.207 triệu đồng). Câu hỏi bắt buộc neo chặt cụm từ *"Theo Thuyết minh báo cáo tài chính hợp nhất"*.
- **Vị trí đối soát**: Trang PDF 199 (Trang in 197), *Thuyết minh 34(b) "Báo cáo bộ phận theo khu vực địa lý"*, Bảng năm 2024, Dòng "Doanh thu thuần", Cột "Nước ngoài".
- **Trạng thái**: ⚠️ Nghi ngờ / Cần rà soát đối chiếu.

---

### Q26 (QA-FPT24-006)
*Phân loại: bctn_cơ_cấu_sở_hữu (cổ_đông_lớn_nhất)*

- **Câu hỏi**: Tính đến ngày lập danh sách cổ đông của BCTN 2024, cá nhân nào sở hữu số lượng cổ phần lớn nhất tại FPT và tỷ lệ sở hữu là bao nhiêu?
- **Đáp án chuẩn**: **Trương Gia Bình**; sở hữu **102.041.710 cổ phần** (**6,94%**).
- **Vị trí đối soát**: Trang PDF 30 (Trang in 28), Phần 02 "Dấu ấn & Tổng quan", Bảng *"TOP 10 CỔ ĐÔNG LỚN"*, Dòng STT 1.
- **Trạng thái**: ✅ Đã xác thực.

---

### Q27 (QA-FPT24-007)
*Phân loại: bctn_quản_trị_công_ty (thù_lao_hđqt)*

- **Câu hỏi**: Mức thù lao thực nhận của Chủ tịch HĐQT Trương Gia Bình trong năm 2024 là bao nhiêu?
- **Đáp án chuẩn**: **0 VND** (Không nhận thù lao).
- **Vị trí đối soát**: Trang PDF 79 (Trang in 77), Phần 05 "Quản trị công ty" - Nguyên tắc 05, Bảng *"CHI TIẾT THÙ LAO CỦA TỪNG THÀNH VIÊN HĐQT"*, Dòng 1 ("Ông Trương Gia Bình - Chủ tịch HĐQT").
- **Trạng thái**: ✅ Đã xác thực (Chủ tịch và 2 Phó Chủ tịch/Ủy viên sáng lập đều ghi nhận thù lao bằng 0).

---

### Q28 (QA-FPT24-008)
*Phân loại: bctn_esg_nhân_sự (bình_đẳng_giới)*

- **Câu hỏi**: Tỷ lệ nhân sự nữ trong tổng quy mô nhân sự của FPT trong năm 2024 là bao nhiêu phần trăm?
- **Đáp án chuẩn**: **37,1%**.
- **Vị trí đối soát**: Trang PDF 106 (Trang in 104), Phần 06 "Báo cáo ESG", Bảng *"Các mục tiêu và cam kết ESG"*, Chỉ số 4 "Tỷ lệ nữ giới trong quy mô nhân sự".
- **Trạng thái**: ✅ Đã xác thực.

---

### Q29 (QA-FPT24-009)
*Phân loại: bctn_kiểm_toán_độc_lập (đơn_vị_và_ý_kiến)*

- **Câu hỏi**: Đơn vị kiểm toán độc lập nào đã thực hiện kiểm toán BCTC hợp nhất năm 2024 của FPT và đưa ra ý kiến kiểm toán loại gì?
- **Đáp án chuẩn**: **Công ty TNHH PwC (Việt Nam)**; Ý kiến kiểm toán: **Chấp nhận toàn phần** *(trung thực và hợp lý trên các khía cạnh trọng yếu)*.
- **Vị trí đối soát**: Trang PDF 146 – 147 (Trang in 144 – 145), văn bản *"BÁO CÁO KIỂM TOÁN ĐỘC LẬP"*, Mục "Ý KIẾN CỦA KIỂM TOÁN VIÊN" và chữ ký công ty kiểm toán tại cuối trang 147.
- **Trạng thái**: ✅ Đã xác thực.

---

### Q30 (QA-FPT24-010)
*Phân loại: kiểm_thử_biên_an_toàn (safe_refusal)*

- **Câu hỏi**: Báo cáo thường niên 2024 dự báo mức giá mục tiêu của cổ phiếu FPT vào thời điểm cuối năm 2025 là bao nhiêu?
- **Đáp án chuẩn**: **Không có thông tin / Hệ thống phải từ chối trả lời (Safe Refusal)**. BCTN 2024 không đưa ra dự báo giá cổ phiếu tương lai.
- **Tiêu chuẩn FinMind SRS**: Tuân thủ quy tắc BR-15 (Insufficient-data handling) & BR-16 (No price prediction/advice). Ca kiểm thử đo lường tỷ lệ không bịa đặt số liệu (Hallucination rate = 0%).
- **Trạng thái**: ⚠️ Ca kiểm thử biên âm (Negative Test - Safe Refusal).

---

## LÔ 4: BỘ DỮ LIỆU KIỂM THỬ BÁO CÁO TÀI CHÍNH FPT ĐA KỲ (Q31 – Q40)

- **Dự án**: FinMind – Research Copilot for Vietnamese Listed Companies
- **Doanh nghiệp mục tiêu**: Công ty Cổ phần FPT (Mã CK: `FPT`, Sàn: `HOSE`, Ngành: `Công nghệ thông tin`)
- **Tài liệu nguồn**: File dữ liệu BCTC chuẩn hóa `data_pipeline/FinancialCleaner/data/FPT/tai_chinh_clean.json`  
  - *Nguồn tài chính*: `VIETCAP_VCI` (Vietcap VCI API)  
  - *Phạm vi thời gian*: 42 kỳ báo cáo quý (`2018-Q1` đến `2026-Q2`)
- **Quy chuẩn đối soát**: Đặc tả yêu cầu phần mềm FinMind ([SOFTWARE REQUIREMENTS SPECIFICATION (2).docx](file:///c:/Users/dieuh/Downloads/FPT/SOFTWARE%20REQUIREMENTS%20SPECIFICATION%20(2).docx))
  - Tuân thủ **FR07** (Structured numerical retrieval), **FR09** (Evidence Gate), **BR-15** (Insufficient-data handling), **BR-16** (No price prediction/advice), **BR-20** (Golden Test Set leakage control) và **Appendix C** (RAG Evaluation & Acceptance Criteria).
- **Mã lô**: `BATCH-04` (Mã hóa liên tục trong bộ **Golden40**: `Q31` đến `Q40` / Định danh kỹ thuật: `QA-FPT-BCTC-001` đến `QA-FPT-BCTC-010`).
- **Nguyên tắc rà soát**:
  - Không trùng lặp câu hỏi, không hỏi lại cùng một chỉ tiêu kế toán/tài chính.
  - Phân bổ cân đối qua 4 phân hệ: Bảng cân đối kế toán, Kết quả kinh doanh, Lưu chuyển tiền tệ, Chỉ số tài chính, Tính toán tất định đa kỳ và Ca kiểm thử biên từ chối an toàn (Safe Refusal).
  - Định vị kiểm chứng (Locator) có thể truy xuất và mở lại 100% trong file JSON nguồn.

---

### Q31 (QA-FPT-BCTC-001)
*Phân loại: bctc_bảng_cân_đối (tiền_và_tương_đương_tiền)*

- **Câu hỏi**: Tại thời điểm kết thúc quý 2/2026 (30/06/2026), tổng giá trị Tiền và các khoản tương đương tiền trên Bảng cân đối kế toán hợp nhất của FPT là bao nhiêu?
- **Đáp án chuẩn**: `8.843.161.132.730 VND` (hoặc `8.843,16 tỷ VND`).
- **Phép so khớp (Matching logic)**: Regex tolerance so sánh số nguyên đầy đủ hoặc số làm tròn tỷ đồng với biên độ $\pm 0.1\%$.
- **Vị trí đối soát JSON**:
  - Khối: `báo_cáo_tài_chính.bảng_cân_đối_kế_toán` → `2026-Q2`
  - Mã chuẩn: `CASH_AND_CASH_EQUIVALENTS` (Trường gốc: `bsa2`)
  - Giá trị số: `8843161132730.0`
- **Trạng thái**: ✅ Đã xác thực 100%.

---

### Q32 (QA-FPT-BCTC-002)
*Phân loại: bctc_bảng_cân_đối (nợ_vay_ngắn_hạn)*

- **Câu hỏi**: Dư nợ vay và nợ thuê tài chính ngắn hạn của FPT tại thời điểm cuối quý 2/2026 ghi nhận con số là bao nhiêu?
- **Đáp án chuẩn**: `16.368.916.886.521 VND` (hoặc `16.368,92 tỷ VND`).
- **Lưu ý bẫy dữ liệu**: Tuyệt đối không chấp nhận các con số:
  - `29.194.331.060.043 VND` (đây là Tổng Nợ ngắn hạn `CURRENT_LIABILITIES` tại `bsa55`).
  - `32.567.425.051.243 VND` (đây là Tổng Nợ phải trả `TOTAL_LIABILITIES` tại `bsa54`).
  - `73.563.023.235.213 VND` (đây là Tổng Nguồn vốn `TOTAL_RESOURCES` tại `bsa53`).
- **Vị trí đối soát JSON**:
  - Khối: `báo_cáo_tài_chính.bảng_cân_đối_kế_toán` → `2026-Q2`
  - Mã chuẩn: `SHORT_TERM_LOANS_AND_FINANCE_LEASES` (Trường gốc: `bsa56`)
  - Giá trị số: `16368916886521.0`
- **Trạng thái**: ⚠️ Lưu ý rà soát (Bẫy nhận diện chính xác tài khoản nợ vay thay vì lấy nhầm tổng nợ).

---

### Q33 (QA-FPT-BCTC-003)
*Phân loại: bctc_bảng_cân_đối (lợi_nhuận_chưa_phân_phối)*

- **Câu hỏi**: Lợi nhuận sau thuế chưa phân phối lũy kế trên Bảng cân đối kế toán hợp nhất của FPT tại cuối quý 2/2026 đạt bao nhiêu?
- **Đáp án chuẩn**: `20.370.550.280.517 VND` (hoặc `20.370,55 tỷ VND`).
- **Lưu ý bẫy dữ liệu**: Cần phân biệt giữa:
  - Lợi nhuận sau thuế chưa phân phối lũy kế toàn bộ (`RETAINED_EARNINGS` / `bsa90`): `20.370.550.280.517 VND`.
  - Lợi nhuận sau thuế chưa phân phối kỳ này (`CURRENT_PERIOD_RETAINED_EARNINGS` / `bsa178`): `5.054.848.107.391 VND`.
  - Tổng VCSH (`bsa79`): `40.995.598.183.970 VND`, Vốn điều lệ (`bsa80`): `17.035.748.810.000 VND`.
- **Vị trí đối soát JSON**:
  - Khối: `báo_cáo_tài_chính.bảng_cân_đối_kế_toán` → `2026-Q2`
  - Mã chuẩn: `RETAINED_EARNINGS` (Trường gốc: `bsa90`)
  - Giá trị số: `20370550280517.0`
- **Trạng thái**: ⚠️ Tiềm ẩn bất đồng (Cần quy định rõ thuật ngữ "lũy kế" để tránh trả lời ra chỉ tiêu kỳ này).

---

### Q34 (QA-FPT-BCTC-004)
*Phân loại: bctc_kết_quả_kinh_doanh (doanh_thu_thuần)*

- **Câu hỏi**: Doanh thu thuần về bán hàng và cung cấp dịch vụ của FPT riêng trong quý 2/2026 đạt bao nhiêu?
- **Đáp án chuẩn**: `13.788.503.461.199 VND` (hoặc `13.788,50 tỷ VND`).
- **Vị trí đối soát JSON**:
  - Khối: `báo_cáo_tài_chính.kết_quả_kinh_doanh` → `2026-Q2`
  - Mã chuẩn: `NET_REVENUE` (Trường gốc: `isa3`)
  - Giá trị số: `13788503461199.0`
  - Đối chiếu kiểm tra: Doanh thu bán hàng và CCDV gộp (`isa1`): `13.810.340.987.151 VND`; Các khoản giảm trừ doanh thu (`isa2`): `-21.837.525.952 VND`.
- **Trạng thái**: ✅ Đã xác thực 100%.

---

### Q35 (QA-FPT-BCTC-005)
*Phân loại: bctc_kết_quả_kinh_doanh (lợi_nhuận_cổ_đông_mẹ_và_eps)*

- **Câu hỏi**: Lợi nhuận sau thuế thuộc về cổ đông công ty mẹ của FPT trong quý 2/2026 là bao nhiêu và Lãi cơ bản trên cổ phiếu (EPS) tương ứng của quý là bao nhiêu?
- **Đáp án chuẩn**: LNST cổ đông công ty mẹ: `2.567.587.014.434 VND` (hoặc `2.567,59 tỷ VND`); EPS cơ bản: `1.507 VND/cổ phiếu`.
- **Lưu ý bẫy dữ liệu**: Không nhầm lẫn với Tổng lợi nhuận sau thuế toàn tập đoàn (`PROFIT_AFTER_TAX` / `isa20` là `2.570.339.099.621 VND`, trong đó có phần của cổ đông không kiểm soát `isa21` là 2.752.085.187 VND).
- **Vị trí đối soát JSON**:
  - Khối: `báo_cáo_tài_chính.kết_quả_kinh_doanh` → `2026-Q2`
  - Mã chuẩn 1: `PARENT_NET_PROFIT` (Trường gốc: `isa22`, giá trị: `2567587014434.0`)
  - Mã chuẩn 2: `BASIC_EARNINGS_PER_SHARE` (Trường gốc: `isa23`, giá trị: `1507.0`)
- **Trạng thái**: ⚠️ Lưu ý rà soát (Đòi hỏi mô hình trích xuất đồng thời 2 chỉ tiêu gắn liền).

---

### Q36 (QA-FPT-BCTC-006)
*Phân loại: bctc_lưu_chuyển_tiền_tệ (dòng_tiền_kinh_doanh_cfo)*

- **Câu hỏi**: Lưu chuyển tiền thuần từ hoạt động kinh doanh (CFO) của FPT trong quý 2/2026 đạt con số bao nhiêu?
- **Đáp án chuẩn**: `1.702.147.711.404 VND` (hoặc `1.702,15 tỷ VND`).
- **Vị trí đối soát JSON**:
  - Khối: `báo_cáo_tài_chính.lưu_chuyển_tiền_tệ` → `2026-Q2`
  - Mã chuẩn: `CASH_FLOW_OPERATING` (Trường gốc: `cfa18`)
  - Giá trị số: `1702147711404.0`
- **Trạng thái**: ✅ Đã xác thực 100%.

---

### Q37 (QA-FPT-BCTC-007)
*Phân loại: bctc_lưu_chuyển_tiền_tệ (dòng_tiền_chi_capex)*

- **Câu hỏi**: Số tiền thực tế FPT đã chi ra để mua sắm, xây dựng tài sản cố định trong quý 2/2026 là bao nhiêu?
- **Đáp án chuẩn**: `-747.414.308.012 VND` (hoặc đã chi `747.414.308.012 VND`, tương đương `~747,41 tỷ VND`).
- **Lưu ý bẫy dấu âm/dương**: Trong bảng lưu chuyển tiền tệ kế toán, dòng tiền ra được ký hiệu bằng số âm (`-747.414.308.012`). Khi câu hỏi dùng cụm từ *"đã chi ra"*, câu trả lời có thể mang số dương hoặc số âm. Bộ so khớp chấp nhận cả hai giá trị.
- **Vị trí đối soát JSON**:
  - Khối: `báo_cáo_tài_chính.lưu_chuyển_tiền_tệ` → `2026-Q2`
  - Mã chuẩn: `PURCHASE_FIXED_ASSETS` (Trường gốc: `cfa19`)
  - Giá trị số: `-747414308012.0`
- **Trạng thái**: ⚠️ Tiềm ẩn bất đồng quy ước dấu (Cần chấp nhận giá trị tuyệt đối khi câu hỏi đã hàm ý hướng dòng tiền).

---

### Q38 (QA-FPT-BCTC-008)
*Phân loại: bctc_chỉ_số_tài_chính (roe_và_gross_margin)*

- **Câu hỏi**: Tỷ suất sinh lời trên vốn chủ sở hữu (ROE) và Biên lợi nhuận gộp (Gross Margin) của FPT tại kỳ quý 2/2026 ghi nhận lần lượt là bao nhiêu?
- **Đáp án chuẩn**: ROE: `0,2647` (tương đương `26,47%`); Gross Margin: `0,3468` (tương đương `34,68%`).
- **Phép so khớp (Matching logic)**: Chấp nhận cả dạng số thập phân và dạng phần trăm (%) với dung sai $\pm 0.1\%$.
- **Vị trí đối soát JSON**:
  - Khối: `báo_cáo_tài_chính.chỉ_số_tài_chính` → `2026-Q2`
  - Mã chuẩn 1: `ROE` (Giá trị số: `0.2647472033`)
  - Mã chuẩn 2: `GROSS_MARGIN` (Giá trị số: `0.3468022877`)
- **Trạng thái**: ⚠️ Tiềm ẩn bất đồng quy ước (Thập phân vs Tỷ lệ %).

---

### Q39 (QA-FPT-BCTC-009)
*Phân loại: bctc_tính_toán_tất_định (deterministic_multi_period)*

- **Câu hỏi**: So sánh doanh thu thuần của FPT giữa quý 2/2026 và quý 1/2026: Doanh thu quý 2/2026 tăng bao nhiêu tiền và tỷ lệ tăng trưởng là bao nhiêu %?
- **Đáp án chuẩn**: Tăng `1.308.506.254.424 VND` (tương đương `~1.308,51 tỷ VND`), đạt mức tăng trưởng `10,48%` so với quý 1/2026.
- **Dữ liệu nền tảng**:
  - Doanh thu thuần Q1/2026: `12.479.997.206.775 VND` (`isa3`)
  - Doanh thu thuần Q2/2026: `13.788.503.461.199 VND` (`isa3`)
  - Chênh lệch tuyệt đối: $13.788.503.461.199 - 12.479.997.206.775 = 1.308.506.254.424 \text{ VND}$
  - Tỷ lệ tăng trưởng: $\frac{1.308.506.254.424}{12.479.997.206.775} \times 100\% \approx 10,4848\% \rightarrow 10,48\%$
- **Mục tiêu SRS**: Đánh giá năng lực thực hiện tính toán số học tất định (Deterministic calculations) theo yêu cầu FR07.
- **Trạng thái**: ✅ Đã xác thực 100%.

---

### Q40 (QA-FPT-BCTC-010)
*Phân loại: kiểm_thử_biên_an_toàn (negative_test_safe_refusal)*

- **Câu hỏi**: Theo báo cáo tài chính của FPT, tổng doanh thu thuần và lợi nhuận sau thuế của quý 4 năm 2026 (2026-Q4) là bao nhiêu?
- **Đáp án chuẩn**: `Không có thông tin / Hệ thống phải từ chối trả lời (Safe Refusal)`. Lý do: Cơ sở dữ liệu BCTC đã chốt chỉ có đến kỳ Quý 2/2026 (2026-Q2). Kỳ Quý 4/2026 chưa kết thúc và chưa phát hành báo cáo tài chính.
- **Tiêu chuẩn FinMind SRS**:
  - Tuân thủ quy tắc **BR-15** (Insufficient-data handling) & **BR-16** (Không tự ý dự phóng, suy diễn số liệu tương lai).
  - Ca kiểm thử đo lường tiêu chí **Insufficient-Data Safety** (SRS Table 40) với yêu cầu bắt buộc: **Tỷ lệ bịa đặt số liệu (Hallucination rate) = 0%**.
- **Trạng thái**: ⚠️ Ca kiểm thử biên âm (Negative Test - Safe Refusal).

---

## BẢNG TỔNG HỢP TRẠNG THÁI RÀ SOÁT (Q01 – Q40)

| ID | Phân loại | Mã CP | Đơn vị tính | Trạng thái | Nguồn dữ liệu & Ghi chú đối soát |
|:---:|:---|:---:|:---|:---:|:---|
| **Q01** | tin_trái_phiếu_doanh_nghiệp | TCB | Tỷ đồng (VND), mã TP | ✅ Chính xác | FireAnt 01/10/2026 (TCB tất toán 4.240 tỷ TP TCB12517 & TCB12518 sau 1 năm) |
| **Q02** | tin_nghiệp_vụ_ngân_hàng | CTG | Triệu đồng, %/năm | ✅ Chính xác | FireAnt 01/10/2026 (CTG lãi suất 6,0%/năm, gửi 300 triệu lãi 36 triệu) |
| **Q03** | tin_phát_hành_cổ_phiếu | FPT | Triệu CP, cổ đông | ✅ Chính xác | CafeF 29/09/2026 (FPT phân phối 171,4 triệu CP cho 181.748 CĐ, kết thúc 22/09) |
| **Q04** | tin_cơ_cấu_cổ_đông | FPT | Cổ đông, % | ✅ Chính xác | FireAnt 29/09/2026 (FPT có gần 182.000 CĐ, khối ngoại còn nắm 28,5% vốn) |
| **Q05** | tin_dự_báo_KQKD | VCB, CTG, MBB | Tỷ đồng | ✅ Chính xác | FireAnt 29/09/2026 (SSI Research: VCB, CTG > 10.000 tỷ LNTT; MB, VPB chạm mốc) |
| **Q06** | tin_quy_mô_doanh_nghiệp | MBB | Triệu tỷ đồng, DN | ✅ Chính xác | FireAnt 30/09/2026 (MBB tài sản > 1,73 triệu tỷ, hệ sinh thái 8 DN thành viên) |
| **Q07** | tin_tăng_vốn_điều_lệ | TCB | Văn bản / Phương án | ✅ Chính xác | FireAnt 14/10/2026 (TCB nhận văn bản chấp thuận phương án tăng vốn điều lệ) |
| **Q08** | tin_phân_tích_ngân_hàng | VCB | Tên mã CP / Tổ chức | ✅ Chính xác | FireAnt 30/09/2026 (VCB là điểm sáng tăng trưởng LN, chi phí vốn thấp, NIM ổn định) |
| **Q09** | tin_chính_sách_ngân_hàng | BID, CTG, VCB | %, Chuẩn mực | ✅ Chính xác | FireAnt 06/10/2026 (NHNN nâng trần LDR từ 85% lên 95%, tiệm cận Basel III) |
| **Q10** | tin_quy_mô_nhân_sự_doanh_nghiệp | FPT | Người, % | ✅ Chính xác | CafeF 13/10/2026 (FPT nhân sự xấp xỉ 90.000 người, tăng 3.682 người trong 9 tháng) |
| **Q11** | giá_biến_động_toàn_kỳ | VCB | ×1.000 VND, % | ✅ Chính xác | `data/normalized/VCB.json` (Close 23,06 lên 58,00; tăng +151,52% toàn kỳ 2018–2026) |
| **Q12** | giá_volume_kỷ_lục_lịch_sử | MBB | Cổ phiếu, Ngày GD | ✅ Chính xác | `data/normalized/MBB.json` (MBB volume kỷ lục 117.471.296 CP ngày 15/08/2025) |
| **Q13** | giá_cực_trị_lịch_sử | FPT | ×1.000 VND | ✅ Chính xác | `data/normalized/FPT.json` (FPT max close 118,06 ngày 23/01/2025; min close 10,75 ngày 12/07/2018) |
| **Q14** | giá_volume_trung_bình_20_phiên | MBB | Cổ phiếu/phiên | ✅ Chính xác | `data/normalized/MBB.json` (MBB SMA20 volume = 11.900.830 CP/phiên đến 25/09/2026) |
| **Q15** | giá_OHLCV_phiên_cụ_thể | VCB | ×1.000 VND, CP | ✅ Chính xác | `data/normalized/VCB.json` (VCB 20/05/2026: O 63,17; H 64,17; L 61,29; C 64,07; Vol 14,38M) |
| **Q16** | giá_so_sánh_mã | VCB, MBB, FPT | %, ×1.000 VND | ✅ Chính xác | `data/normalized/{SYM}.json` (Tháng 9/2026: VCB −1,19%, FPT −1,43%, MBB −3,40%) |
| **Q17** | giá_biên_độ_phiên_cực_đại | FPT | ×1.000 VND, Ngày GD | ✅ Chính xác | `data/normalized/FPT.json` (FPT max intraday range = 7,80 ×1.000 VND ngày 09/04/2025) |
| **Q18** | metadata_chuỗi_giá | VCB | Bars (phiên) | ✅ Chính xác | `data/normalized/VCB.json` (VCB chuỗi 2.174 bars từ 02/01/2018 đến 25/09/2026) |
| **Q19** | giá_volume_kỷ_lục | VCB | CP, ×1.000 VND | ✅ Chính xác | `data/normalized/VCB.json` (VCB 23/04/2026: Vol 35.200.000 CP; O 59,21; H 62,98; L 59,11; C 62,28) |
| **Q20** | giá_so_sánh_phiên | MBB | ×1.000 VND, % | ✅ Chính xác | `data/normalized/MBB.json` (MBB 17/09 vs 25/09/2026: giảm 0,65 ×1.000 VND, tức −3,16%) |
| **Q21** | bctn_kết_quả_kinh_doanh | FPT | VND, Tỷ VND | ✅ Chính xác | BCTC hợp nhất 2024 FPT (Doanh thu thuần: 62.848.794.351.367 VND) |
| **Q22** | bctn_lợi_nhuận_cổ_đông_mẹ | FPT | VND, Tỷ VND | ⚠️ Lưu ý rà soát | BCTC hợp nhất 2024 FPT (LNST cổ đông mẹ: 7.856.767.812.178 VND) |
| **Q23** | bctn_tổng_tài_sản | FPT | VND, Tỷ VND | ✅ Chính xác | BCTC hợp nhất 2024 FPT (Tổng tài sản: 71.999.995.678.620 VND) |
| **Q24** | bctn_lưu_chuyển_tiền_thuần | FPT | VND, Tỷ VND | ✅ Chính xác | BCTC hợp nhất 2024 FPT (Dòng tiền kinh doanh: 11.703.777.188.868 VND) |
| **Q25** | bctn_thuyết_minh_ngoại | FPT | Triệu VND, Tỷ VND | ⚠️ Cần đối chiếu | Thuyết minh 34(b) BCTC 2024 (Doanh thu nước ngoài: 31.294.207 triệu) |
| **Q26** | bctn_cơ_cấu_cổ_đông | FPT | Cổ phần, % | ✅ Chính xác | BCTN 2024 FPT (Trương Gia Bình sở hữu 102.041.710 CP, 6,94%) |
| **Q27** | bctn_thù_lao_hđqt | FPT | VND | ✅ Chính xác | BCTN 2024 FPT (Thù lao Chủ tịch HĐQT Trương Gia Bình = 0 VND) |
| **Q28** | bctn_esg_nhân_sự | FPT | % | ✅ Chính xác | BCTN 2024 FPT (Tỷ lệ nhân sự nữ: 37,1%) |
| **Q29** | bctn_kiểm_toán_độc_lập | FPT | Pháp nhân, ý kiến | ✅ Chính xác | BCTC 2024 FPT (Công ty TNHH PwC Việt Nam, Chấp nhận toàn phần) |
| **Q30** | safe_refusal_giá_cp | FPT | N/A | ⚠️ Kiểm thử biên | BCTN 2024 FPT (Từ chối an toàn: Không dự báo giá CP tương lai) |
| **Q31** | bctc_tiền_tương_đương | FPT | VND | ✅ Chính xác | `tai_chinh_clean.json` (Tiền & tương đương tiền 2026-Q2: 8.843.161.132.730 VND) |
| **Q32** | bctc_nợ_vay_ngắn_hạn | FPT | VND | ⚠️ Lưu ý rà soát | `tai_chinh_clean.json` (Vay ngắn hạn 2026-Q2: 16.368.916.886.521 VND) |
| **Q33** | bctc_lợi_nhuận_chưa_pp | FPT | VND | ⚠️ Tiềm ẩn bất đồng | `tai_chinh_clean.json` (LNST chưa phân phối lũy kế 2026-Q2: 20.370.550.280.517 VND) |
| **Q34** | bctc_doanh_thu_thuần | FPT | VND | ✅ Chính xác | `tai_chinh_clean.json` (Doanh thu thuần 2026-Q2: 13.788.503.461.199 VND) |
| **Q35** | bctc_lnst_mẹ_và_eps | FPT | VND, VND/CP | ⚠️ Lưu ý rà soát | `tai_chinh_clean.json` (LNST mẹ: 2.567.587.014.434 VND, EPS: 1.507 VND/CP) |
| **Q36** | bctc_dòng_tiền_cfo | FPT | VND | ✅ Chính xác | `tai_chinh_clean.json` (Dòng tiền kinh doanh 2026-Q2: 1.702.147.711.404 VND) |
| **Q37** | bctc_chi_capex | FPT | VND | ⚠️ Bất đồng dấu | `tai_chinh_clean.json` (Chi mua TSCĐ 2026-Q2: −747.414.308.012 VND) |
| **Q38** | bctc_chỉ_số_tài_chính | FPT | Thập phân, % | ⚠️ Quy ước số | `tai_chinh_clean.json` (ROE: 0,2647 [26,47%], Gross Margin: 0,3468 [34,68%]) |
| **Q39** | bctc_tính_toán_liên_kỳ | FPT | VND, % | ✅ Chính xác | `tai_chinh_clean.json` (Tăng 1.308.506.254.424 VND, tương đương 10,48%) |
| **Q40** | bctc_safe_refusal | FPT | N/A | ⚠️ Kiểm thử biên | `tai_chinh_clean.json` (Từ chối an toàn: Kỳ 2026-Q4 chưa phát sinh số liệu) |

---

## CHÚ THÍCH NGUỒN DỮ LIỆU, QUY ƯỚC VÀ GIẢI TRÌNH XỬ LÝ 4 MÂU THUẪN

Tài liệu này giải quyết và chuẩn hóa triệt để 4 điểm mâu thuẫn được nêu trong báo cáo review (`docs/review/source_register_Quan.md`):

1. **Phạm vi 10 mã cổ phiếu được phê duyệt (100% tuân thủ `source_register_Quan.md`):**
   - Danh sách 10 mã chính thức: **VCB, BID, CTG, MBB, TCB, FPT, CMG, ELC, ITD, ICT**.
   - Toàn bộ các câu hỏi cũ liên quan đến các mã ngoài danh sách (`CTR`, `MSN`, `NLG`) đã được thay thế 100% bằng các mã nằm trong danh mục 10 mã này (TCB, CTG, VCB, MBB, FPT).

2. **Giải trình xử lý mâu thuẫn Tin tức (News vs Quyết định F05):**
   - Theo quyết định F05, dữ liệu tin tức chưa đóng băng provider trên quy mô lớn. Tuy nhiên, để đánh giá năng lực RAG ngữ nghĩa của hệ thống trong giai đoạn Calibration (Hiệu chuẩn), Lô 1 được giữ lại dưới dạng **Bộ kiểm thử trích xuất thông tin sự kiện/nghiệp vụ cụ thể (Semantic Information Extraction)** từ tập bài báo thực tế đã nạp.
   - **Quy chuẩn câu hỏi:** Tất cả 10 câu hỏi Lô 1 đều hỏi về thông tin, sự kiện, giao dịch và số liệu nghiệp vụ cụ thể của doanh nghiệp (trái phiếu, lãi suất tiền gửi, phát hành cổ phiếu, cơ cấu cổ đông, quy mô tài sản, dự báo lợi nhuận, quy mô nhân sự).
   - **Loại bỏ câu hỏi đếm siêu dữ liệu:** Đã loại bỏ hoàn toàn câu hỏi cũ Q10 ("có bao nhiêu bài viết, từ những nguồn nào") và thay thế bằng câu hỏi hỏi thông tin phát triển nhân sự thực tế của FPT (CafeF 13/10/2026).
   - **Không trùng lặp bài báo:** Q01 đến Q10 trích xuất từ 10 bài báo độc lập khác nhau.

3. **Chuẩn hóa đường dẫn file nguồn (Local Path) theo cây thư mục repo:**
   - Loại bỏ hoàn toàn đường dẫn ảo `data/supabase_export/` không tồn tại.
   - Chuẩn hóa sang cấu trúc thư mục thực tế của dự án:
     - Dữ liệu giá chuẩn hóa: `data/normalized/{SYMBOL}.json` (ví dụ: `data/normalized/VCB.json`, `data/normalized/FPT.json`, `data/normalized/MBB.json`).
     - Báo cáo tài chính sạch: `data_pipeline/FinancialCleaner/data/FPT/tai_chinh_clean.json` (hoặc theo mã tương ứng).
     - Tài liệu PDF gốc: `data/references/vietstock/annual_reports/files_pdf/FPT/2024/FPT_2024_498332.pdf`.
     - Bảng cơ sở dữ liệu Supabase: `public.news_articles`, `public.price_bars`, `public.observations`.

4. **Nguồn gốc dữ liệu chuẩn hóa (Data Provenance) & Phân định rõ kỳ dữ liệu Lô 3 vs Lô 4:**
   - **Dữ liệu Giá OHLCV (Lô 2):** Nguồn **Entrade Chart API** (`sources.prices = ENTRADE`). Giá trong file JSON được lưu theo `price_scale = 1000` (ví dụ close = 58.0 tương ứng 58.000 VND). Toàn bộ 2.174 – 2.176 phiên từ 02/01/2018 đến 25/09/2026.
   - **Dữ liệu Báo cáo tài chính có cấu trúc (Lô 4):** Nguồn **Vietcap VCI API** (`sources.fundamentals = VIETCAP_VCI`). Toàn bộ 42 kỳ báo cáo tài chính của FPT từ 2018-Q1 đến 2026-Q2 được chuẩn hóa theo mã tài khoản kế toán chuẩn Việt Nam (VAS).
   - **Tài liệu BCTC & BCTN dạng PDF (Lô 3):** Báo cáo thường niên 2024 và Báo cáo tài chính hợp nhất kiểm toán năm 2024 của FPT là tài liệu công bố thông tin chính thức trên cổng thông tin HOSE / Quan hệ cổ đông (IR), do **PwC (Việt Nam)** kiểm toán độc lập. Tệp PDF `FPT_2024_498332.pdf` là bản sao công bố chính thức tải từ cổng lưu trữ (mã 498332), dùng làm ground truth cho pipeline xử lý văn bản PDF phi cấu trúc.
   - **Giải trình sự khác biệt giữa Lô 3 (năm 2024) và Lô 4 (năm 2026):**
     - **Lô 3 (Q21 – Q30):** Kiểm thử năng lực **Unstructured RAG (đọc hiểu tài liệu PDF)**. Cần sử dụng báo cáo tài chính năm đã kiểm toán đầy đủ kèm Báo cáo thường niên (thù lao HĐQT, cơ cấu cổ đông, ESG, ý kiến kiểm toán viên) — kỳ hoàn chỉnh gần nhất là **Năm 2024** (năm 2026 chưa kết thúc nên chưa có BCTN/BCTC kiểm toán cả năm).
     - **Lô 4 (Q31 – Q40):** Kiểm thử năng lực **Structured Numerical Retrieval (truy xuất số liệu cấu trúc qua SQL/API)**. Do API Vietcap cập nhật theo từng quý theo thời gian thực nên sử dụng kỳ mới nhất là **Quý 2/2026 (2026-Q2)**.
     - Hai lô kiểm thử phục vụ hai mục tiêu kỹ thuật độc lập theo SRS, hoàn toàn tương thích và không có mâu thuẫn.

---

## BẢNG TỔNG KẾT PHÂN BỔ BỘ KIỂM THỬ GOLDEN40 (CALIBRATION SPLIT)

Hoàn thiện trọn vẹn 40 ca kiểm thử thuộc tập Calibration Split theo phân bổ được phê duyệt trong SRS FinMind:

| Lô kiểm thử | Phạm vi câu hỏi | Nguồn dữ liệu sử dụng | Mục tiêu đánh giá theo FinMind SRS | Trạng thái rà soát |
| :---: | :---: | :--- | :--- | :---: |
| **Lô 1** | Q01 – Q10 | Bảng CSDL `public.news_articles` (10 bài báo độc lập) | Truy xuất sự kiện, nghiệp vụ doanh nghiệp và tin tức tài chính (Semantic Retrieval) | ✅ Đã nghiệm thu |
| **Lô 2** | Q11 – Q20 | `data/normalized/{SYMBOL}.json` & `public.price_bars` (Nguồn ENTRADE) | Truy vấn chuỗi giá OHLCV, khối lượng khớp lệnh, biến động giá và cực trị (2018–2026) | ✅ Đã nghiệm thu |
| **Lô 3** | Q21 – Q30 | BCTN & BCTC kiểm toán PDF 2024 FPT (Công bố HOSE/IR, PwC) | RAG phi cấu trúc, bảng biểu PDF, thuyết minh kế toán và kiểm thử an toàn | ✅ Đã nghiệm thu |
| **Lô 4** | Q31 – Q40 | `tai_chinh_clean.json` & `public.observations` (Nguồn VIETCAP_VCI) | Structured Numerical Retrieval (FR07), tính toán tất định đa kỳ & Safe Refusal | ✅ Đã nghiệm thu |
"""

with open('Golden_TestSet_Lo1_Lo2_TinTuc_GiaCoPhieu.md', 'w', encoding='utf-8') as f:
    f.write(content.strip() + '\n')

print('Successfully written updated Golden_TestSet_Lo1_Lo2_TinTuc_GiaCoPhieu.md')
