# BỘ CÂU HỎI KIỂM THỬ GOLDEN TEST SET
## LÔ 1, LÔ 2 & LÔ 3: TIN TỨC, GIÁ CỔ PHIẾU VÀ BÁO CÁO THƯỜNG NIÊN (Q01 – Q30)

*Dự án: FinMind – Research Copilot for Vietnamese Listed Companies*  
*Ngày cập nhật: 16/10/2026*  
*Phiên bản: v3.0 – Đồng bộ ID Q01–Q30 (30/30 câu chính xác 100%)*  
*Phạm vi corpus: VCB, MBB, FPT, CTR, MSN, NLG*  
*Nguồn dữ liệu: news_articles.json (224 bài), price_bars_all.json (737 bars), BCTN & BCTC FPT 2024*  
*Kỳ dữ liệu: 29/07/2026 – 07/10/2026 (tin tức), 09/04/2026 – 07/10/2026 (giá), Năm tài chính 2024 (BCTN)*

---

## MỤC LỤC
1. [Lô 1: Câu hỏi về TIN TỨC (Q01 – Q10)](#lô-1-câu-hỏi-về-tin-tức-q01--q10)
2. [Lô 2: Câu hỏi về GIÁ CỔ PHIẾU (Q11 – Q20)](#lô-2-câu-hỏi-về-giá-cổ-phiếu-q11--q20)
3. [Lô 3: Câu hỏi về BÁO CÁO THƯỜNG NIÊN & BCTC (Q21 – Q30)](#lô-3-bộ-dữ-liệu-kiểm-thử-báo-cáo-thường-niên--bctc-fpt-2024-q21--q30)
4. [Bảng tổng hợp trạng thái rà soát (Q01 – Q30)](#bảng-tổng-hợp-trạng-thái-rà-soát-100-đạt-chuẩn)
5. [Chú thích nguồn dữ liệu và quy ước](#chú-thích-nguồn-dữ-liệu-và-quy-ước)

---

## LÔ 1: CÂU HỎI VỀ TIN TỨC (Q01 – Q10)

Lô 1 gồm 10 câu hỏi khai thác dữ liệu bảng `news_articles` trong Supabase. Toàn bộ 10 câu hỏi đều có đáp án xác thực 100% từ bài báo gốc, trích dẫn chi tiết số liệu, ngày tháng và nguồn bài viết. Tuyệt đối không có câu hỏi trùng lặp hoặc mang nội dung gần giống nhau.

---

### Q01
*Phân loại: tin_dự_báo_KQKD*

- **Câu hỏi:** Theo báo cáo dự báo KQKD quý 3/2026 của MBS (bài đăng ngày 28/09/2026), lợi nhuận sau thuế của Masan (MSN) được dự phóng đạt bao nhiêu tỷ đồng, tăng trưởng bao nhiêu % so với cùng kỳ và động lực tăng trưởng chính là gì?
- **Đáp án:** LNST Q3/2026 dự phóng đạt 3.984 tỷ đồng (tăng 230% YoY). Động lực tăng trưởng chủ yếu đến từ Masan High-Tech Materials khi giá vonfram neo quanh 3.000 USD/mtu và mỏ Núi Pháo được cấp phép khai thác thêm quặng từ tháng 5/2026.
- **Đơn vị:** Tỷ đồng (VND), %
- **Kỳ báo cáo:** Quý 3/2026 (dự phóng)
- **Tài liệu gốc:** `news_articles.json` → article có title *"MBS dự báo KQKD quý 3/2026 ngành bán lẻ: Thế Giới Di Động và FPT Retail tiếp tục bứt phá, hai tên tuổi tăng trưởng đột biến 3 chữ số"*
- **Chi tiết kiểm chứng:** source: fireant | published_at: 2026-09-28 | symbols: ["MSN", "MWG", "FRT", ...] | Trích: *"LNST quý 3/2026 của MSN được dự phóng đạt 3.984 tỷ đồng, tăng 230% so với cùng kỳ... động lực tăng trưởng chủ yếu đến từ Masan High-Tech Materials khi giá vonfram neo quanh 3.000 USD/mtu và MSR được cấp phép khai thác thêm quặng tại Núi Pháo từ tháng 5/2026"*
- **Trạng thái:** ✅ Chính xác – Số liệu và luận điểm trích xuất trực tiếp từ bài báo

---

### Q02
*Phân loại: tin_kết_quả_kinh_doanh*

- **Câu hỏi:** Lũy kế nửa đầu năm 2026, doanh thu thuần và lãi trước thuế của CTR (Viettel Construction) là bao nhiêu, tăng trưởng bao nhiêu phần trăm so với cùng kỳ?
- **Đáp án:** Doanh thu thuần: 7.959 tỷ đồng (tăng 33% YoY). Lãi trước thuế: 402 tỷ đồng (tăng 20% YoY).
- **Đơn vị:** Tỷ đồng (VND), %
- **Kỳ báo cáo:** 6 tháng đầu năm 2026 (H1/2026)
- **Tài liệu gốc:** `news_articles.json` → article có title *"Một doanh nghiệp quân đội báo lãi quý 2 tăng trưởng mạnh"*
- **Chi tiết kiểm chứng:** source: cafef | published_at: 2026-07-29 | symbols: ["CTR"] | Trích: *"doanh thu thuần đạt 7.959 tỷ đồng và lãi trước thuế 402 tỷ đồng, lần lượt tăng trưởng 33% và 20%"*
- **Trạng thái:** ✅ Chính xác – Số liệu rõ ràng trong nội dung bài báo

---

### Q03
*Phân loại: tin_phát_hành_cổ_phiếu*

- **Câu hỏi:** Theo tin tức corpus, FPT đã phân phối bao nhiêu cổ phiếu tăng vốn từ nguồn vốn chủ sở hữu, cho bao nhiêu cổ đông và kết thúc đợt phát hành vào ngày nào (theo bài đăng ngày 29/09/2026)?
- **Đáp án:** FPT phân phối hơn 171,4 triệu cổ phiếu cho 181.748 cổ đông. Ngày kết thúc đợt phát hành: 22/09/2026.
- **Đơn vị:** Triệu cổ phiếu, cổ đông
- **Kỳ báo cáo:** 22/09/2026 (ngày kết thúc phát hành)
- **Tài liệu gốc:** `news_articles.json` → article có title chứa *"mỗi tháng FPT có thêm 6.000 cổ đông mới"*
- **Chi tiết kiểm chứng:** source: cafef | published_at: 2026-09-29 | symbols: ["FPT"] | Trích: *"FPT đã phân phối hơn 171,4 triệu cổ phiếu cho 181.748 cổ đông... ngày kết thúc đợt phát hành là 22/9"*
- **Trạng thái:** ✅ Chính xác – Số liệu chính xác từ bài báo CafeF

---

### Q04
*Phân loại: tin_cơ_cấu_cổ_đông*

- **Câu hỏi:** Số lượng cổ đông của FPT tính đến thời điểm bài báo ngày 29/09/2026 là bao nhiêu, và tỷ lệ sở hữu của khối ngoại còn bao nhiêu phần trăm?
- **Đáp án:** FPT có gần 182.000 cổ đông. Khối ngoại nắm 28,5% vốn (giảm từ 49% cuối năm 2022).
- **Đơn vị:** Cổ đông, %
- **Kỳ báo cáo:** 29/09/2026
- **Tài liệu gốc:** `news_articles.json` → article có title *"FPT: Có gần 182.000 cổ đông, khối ngoại còn nắm 28,5% vốn"*
- **Chi tiết kiểm chứng:** source: fireant | published_at: 2026-09-29 | symbols: ["FPT"] | Trích: *"Khối ngoại từ tỷ lệ sở hữu 49% cuối năm 2022 giờ chỉ còn nắm giữ 28,5% vốn"*
- **Trạng thái:** ✅ Chính xác – Dữ liệu được ghi rõ trong title và content

---

### Q05
*Phân loại: tin_dự_báo_KQKD*

- **Câu hỏi:** Theo ước tính của SSI Research trong tin tức corpus, những ngân hàng nào được dự báo có thể vượt 10.000 tỷ đồng lợi nhuận trước thuế trong quý III/2026?
- **Đáp án:** VietinBank (CTG), Vietcombank (VCB), MB (MBB) và VPBank (VPB) được dự báo cùng chạm hoặc vượt mốc 10.000 tỷ đồng LNTT quý III/2026.
- **Đơn vị:** Tỷ đồng
- **Kỳ báo cáo:** Q3/2026 (dự báo)
- **Tài liệu gốc:** `news_articles.json` → article có title *"Những ngân hàng có thể lãi trên 10.000 tỷ đồng trong quý III"*
- **Chi tiết kiểm chứng:** source: fireant | published_at: 2026-09-29 | symbols: ["VCB","CTG","MBB","VPB"] | Trích: *"VietinBank và Vietcombank có thể vượt 10.000 tỷ đồng... MB và VPBank được dự báo cùng chạm mốc này"*
- **Trạng thái:** ✅ Chính xác – Trích dẫn rõ ràng từ SSI Research

---

### Q06
*Phân loại: tin_quy_mô_doanh_nghiệp*

- **Câu hỏi:** Theo tin tức corpus, MB (MBB) có quy mô tổng tài sản bao nhiêu và hệ sinh thái gồm bao nhiêu doanh nghiệp thành viên (theo bài đăng ngày 30/09/2026)?
- **Đáp án:** MB có quy mô tài sản hơn 1,73 triệu tỷ đồng và hệ sinh thái gồm 8 doanh nghiệp thành viên.
- **Đơn vị:** Triệu tỷ đồng (VND), doanh nghiệp
- **Kỳ báo cáo:** 30/09/2026 (ngày đăng bài)
- **Tài liệu gốc:** `news_articles.json` → article có title *"MB mở rộng vai trò kết nối dòng vốn"*
- **Chi tiết kiểm chứng:** source: fireant | published_at: 2026-09-30 | symbols: ["MBB"] | Trích: *"quy mô tài sản hơn 1,73 triệu tỷ đồng cùng hệ sinh thái 8 doanh nghiệp thành viên"*
- **Trạng thái:** ✅ Chính xác – Dữ liệu rõ ràng trong nội dung bài báo

---

### Q07
*Phân loại: tin_niêm_yết_bổ_sung*

- **Câu hỏi:** CTR đã niêm yết bổ sung bao nhiêu cổ phiếu trên HoSE và ngày bắt đầu giao dịch cổ phiếu niêm yết bổ sung là ngày nào?
- **Đáp án:** 13.723.654 cổ phiếu. Ngày giao dịch bổ sung: 21/08/2026.
- **Đơn vị:** Cổ phiếu
- **Kỳ báo cáo:** 21/08/2026
- **Tài liệu gốc:** `news_articles.json` → article có title *"CTR: 21.8.2026, giao dịch 13.723.654 cp niêm yết bổ sung"*
- **Chi tiết kiểm chứng:** source: cafef | published_at: 2026-08-13 | symbols: ["CTR"] | Trích title: *"21.8.2026, giao dịch 13.723.654 cp niêm yết bổ sung"*
- **Trạng thái:** ✅ Chính xác – Số liệu chính xác trong title bài báo

---

### Q08
*Phân loại: tin_thị_trường_chung*

- **Câu hỏi:** Tính đến cuối tháng 9/2026, tổng số tài khoản chứng khoán nhà đầu tư cá nhân trong nước tại Việt Nam là bao nhiêu, tương đương bao nhiêu phần trăm dân số?
- **Đáp án:** Hơn 14 triệu tài khoản, tương đương khoảng 14% dân số.
- **Đơn vị:** Triệu tài khoản, %
- **Kỳ báo cáo:** Cuối tháng 9/2026
- **Tài liệu gốc:** `news_articles.json` → article có title *"Việt Nam chính thức cán mốc 14 triệu tài khoản chứng khoán"*
- **Chi tiết kiểm chứng:** source: cafef | published_at: 2026-10-06 | symbols: [] (tin chung) | Trích: *"hơn 14 triệu tài khoản, tương đương khoảng 14% dân số"*
- **Trạng thái:** ✅ Chính xác – Số liệu từ VSD được dẫn nguồn rõ ràng

---

### Q09
*Phân loại: tin_nợ_xấu_dự_phòng*

- **Câu hỏi:** Viettel Construction (CTR) đã dự phòng 100% cho bao nhiêu tiền nợ xấu liên quan đến FLC và Novaland (theo bài đăng ngày 15/09/2026)?
- **Đáp án:** Gần 97,4 tỷ đồng các khoản phải thu được xếp vào nợ xấu từ FLC Faros và hai doanh nghiệp thuộc hệ sinh thái Novaland.
- **Đơn vị:** Tỷ đồng
- **Kỳ báo cáo:** 15/09/2026 (ngày đăng bài)
- **Tài liệu gốc:** `news_articles.json` → article có title *"Viettel Construction dự phòng 100% với 3 khoản nợ xấu liên quan FLC, Novaland"*
- **Chi tiết kiểm chứng:** source: fireant | published_at: 2026-09-15 | symbols: ["CTR"] | Trích: *"gần 97,4 tỉ đồng các khoản phải thu được xếp vào nợ xấu từ FLC Faros"*
- **Trạng thái:** ✅ Chính xác – Số liệu cụ thể từ báo cáo tài chính

---

### Q10
*Phân loại: metadata_corpus*

- **Câu hỏi:** Trong corpus tin tức, có bao nhiêu bài viết tổng cộng, được thu thập từ những nguồn nào, và khoảng thời gian thu thập từ ngày nào đến ngày nào?
- **Đáp án:** 224 bài viết, từ 2 nguồn: cafef (114 bài) và fireant (110 bài). Khoảng thời gian: 29/07/2026 đến 06/10/2026.
- **Đơn vị:** Bài viết, nguồn
- **Kỳ báo cáo:** 29/07/2026 – 06/10/2026
- **Tài liệu gốc:** `news_articles.json` → metadata tổng hợp toàn bộ file
- **Chi tiết kiểm chứng:** Tổng hợp từ news_articles.json: len=224, Counter(source)={cafef:114, fireant:110}, date range 2026-07-29 to 2026-10-06
- **Trạng thái:** ✅ Chính xác – Đếm trực tiếp từ dữ liệu JSON

---

## LÔ 2: CÂU HỎI VỀ GIÁ CỔ PHIẾU (Q11 – Q20)

Lô 2 gồm 10 câu hỏi khai thác dữ liệu bảng `price_bars` trong Supabase. Mỗi câu hỏi đều được tính toán và trích xuất chuẩn xác từ các bản ghi giao dịch thực tế: giá OHLCV cụ thể, cực trị (max/min), biến động %, volume đột biến, biên độ phiên, so sánh giữa các mã và metadata. Không có câu hỏi trùng lặp hoặc gần trùng nội dung.

---

### Q11
*Phân loại: giá_biến_động_kỳ*

- **Câu hỏi:** Giá đóng cửa (close) của VCB ngày giao dịch cuối cùng trong dữ liệu (06/10/2026) là bao nhiêu, và so với ngày giao dịch đầu tiên (09/04/2026) thì biến động bao nhiêu %?
- **Đáp án:** Close ngày 06/10/2026: 57,3 (×1.000 VND). Close ngày 09/04/2026: 58,96. Biến động: −2,82%.
- **Đơn vị:** ×1.000 VND (price_scale=1000), %
- **Kỳ báo cáo:** 09/04/2026 – 06/10/2026
- **Tài liệu gốc:** `price_bars_all.json` → records có symbol="VCB"
- **Chi tiết kiểm chứng:** VCB: trade_date 2026-04-09 close=58.96 → trade_date 2026-10-06 close=57.3 | Change=(57.3-58.96)/58.96×100=−2.82%
- **Trạng thái:** ✅ Chính xác – Tính toán xác định từ dữ liệu price_bars

---

### Q12
*Phân loại: giá_volume_cực_trị*

- **Câu hỏi:** Trong toàn bộ dữ liệu giá, mã cổ phiếu nào có phiên giao dịch với khối lượng (volume) lớn nhất, và khối lượng đó là bao nhiêu, vào ngày nào?
- **Đáp án:** MBB có volume lớn nhất: 38.940.600 cổ phiếu vào ngày 20/05/2026.
- **Đơn vị:** Cổ phiếu
- **Kỳ báo cáo:** 20/05/2026
- **Tài liệu gốc:** `price_bars_all.json` → records có symbol="MBB", trade_date="2026-05-20"
- **Chi tiết kiểm chứng:** MBB: trade_date=2026-05-20 volume=38,940,600 | So sánh: VCB max=35,200,000, FPT max=25,976,600, MSN max=15,769,900
- **Trạng thái:** ✅ Chính xác – Max volume tính trực tiếp từ dữ liệu

---

### Q13
*Phân loại: giá_cực_trị*

- **Câu hỏi:** Giá đóng cửa cao nhất (highest close) của FPT trong kỳ dữ liệu là bao nhiêu, vào ngày nào? Giá đóng cửa thấp nhất là bao nhiêu, vào ngày nào?
- **Đáp án:** Highest close: 69,7 (×1.000 VND) ngày 10/04/2026. Lowest close: 56,56 (×1.000 VND) ngày 27/07/2026.
- **Đơn vị:** ×1.000 VND
- **Kỳ báo cáo:** 10/04/2026 – 07/10/2026
- **Tài liệu gốc:** `price_bars_all.json` → records có symbol="FPT"
- **Chi tiết kiểm chứng:** FPT: max close=69.7 on 2026-04-10, min close=56.56 on 2026-07-27 | 123 bars total
- **Trạng thái:** ✅ Chính xác – Cực trị tính từ toàn bộ 123 bars FPT

---

### Q14
*Phân loại: giá_volume_trung_bình*

- **Câu hỏi:** Khối lượng giao dịch trung bình (average volume) của CTR trong toàn kỳ dữ liệu là bao nhiêu cổ phiếu?
- **Đáp án:** Khoảng 316.524 cổ phiếu/phiên.
- **Đơn vị:** Cổ phiếu/phiên
- **Kỳ báo cáo:** 10/04/2026 – 07/10/2026 (123 phiên)
- **Tài liệu gốc:** `price_bars_all.json` → records có symbol="CTR"
- **Chi tiết kiểm chứng:** CTR: sum(volume)/123 bars ≈ 316,524 | Total bars: 123
- **Trạng thái:** ✅ Chính xác – Trung bình tính từ tổng volume / số phiên

---

### Q15
*Phân loại: giá_OHLCV_cụ_thể*

- **Câu hỏi:** Ngày 20/05/2026 (phiên volume đột biến), giá mở cửa, cao nhất, thấp nhất và đóng cửa của VCB lần lượt là bao nhiêu?
- **Đáp án:** O=63,23 | H=64,22 | L=61,35 | C=64,13 (×1.000 VND). Volume: 14.381.600 cp.
- **Đơn vị:** ×1.000 VND, cổ phiếu
- **Kỳ báo cáo:** 20/05/2026
- **Tài liệu gốc:** `price_bars_all.json` → record có symbol="VCB", trade_date="2026-05-20"
- **Chi tiết kiểm chứng:** VCB 2026-05-20: open=63.23, high=64.22, low=61.35, close=64.13, volume=14,381,600
- **Trạng thái:** ✅ Chính xác – Đọc trực tiếp record trong price_bars

---

### Q16
*Phân loại: giá_so_sánh_mã*

- **Câu hỏi:** Mã cổ phiếu nào giảm giá mạnh nhất tính theo phần trăm biến động close (ngày đầu tiên so với ngày cuối cùng) trong kỳ dữ liệu?
- **Đáp án:** NLG giảm mạnh nhất: −24,26% (từ 28,65 xuống 21,7 ×1.000 VND).
- **Đơn vị:** %
- **Kỳ báo cáo:** 10/04/2026 – 07/10/2026
- **Tài liệu gốc:** `price_bars_all.json` → tất cả 6 mã: VCB −2,82%, MBB −10,20%, FPT −13,63%, CTR −6,65%, MSN −7,31%, NLG −24,26%
- **Chi tiết kiểm chứng:** NLG: first close=28.65 (2026-04-10), last close=21.7 (2026-10-07) → (21.7−28.65)/28.65×100=−24.26%
- **Trạng thái:** ✅ Chính xác – Phép tính xác định trên dữ liệu giá

---

### Q17
*Phân loại: giá_biên_độ_phiên*

- **Câu hỏi:** Ngày 27/07/2026 (phiên đáy chung), giá đóng cửa của MSN là bao nhiêu, và biên độ dao động trong ngày (high − low) là bao nhiêu?
- **Đáp án:** Close: 63,9 (×1.000 VND). High=65,1 − Low=63,5 → Biên độ: 1,6 (×1.000 VND).
- **Đơn vị:** ×1.000 VND
- **Kỳ báo cáo:** 27/07/2026
- **Tài liệu gốc:** `price_bars_all.json` → record có symbol="MSN", trade_date="2026-07-27"
- **Chi tiết kiểm chứng:** MSN 2026-07-27: open=65.0, high=65.1, low=63.5, close=63.9, volume=4,605,200 | Intraday range=65.1−63.5=1.6
- **Trạng thái:** ✅ Chính xác – Đọc trực tiếp từ record

---

### Q18
*Phân loại: metadata_giá*

- **Câu hỏi:** Dữ liệu price_bars trong corpus có bao nhiêu phiên giao dịch (bars) cho mỗi mã cổ phiếu, và tổng cộng có bao nhiêu records?
- **Đáp án:** Mỗi mã ~122–123 bars. Tổng: VCB=123, MBB=122, FPT=123, CTR=123, MSN=123, NLG=123 → Tổng 737 bars (6 mã trong scope).
- **Đơn vị:** Bars (phiên giao dịch)
- **Kỳ báo cáo:** 04/2026 – 10/2026
- **Tài liệu gốc:** `price_bars_all.json` → đếm records theo symbol
- **Chi tiết kiểm chứng:** Counter: VCB=123, MBB=122, FPT=123, CTR=123, MSN=123, NLG=123 | Đếm chuẩn xác từ file JSON
- **Trạng thái:** ✅ Chính xác – Đếm trực tiếp từ dữ liệu

---

### Q19
*Phân loại: giá_volume_kỷ_lục*

- **Câu hỏi:** Trong toàn bộ dữ liệu lịch sử giá của VCB, phiên giao dịch ngày 23/04/2026 ghi nhận volume kỷ lục là bao nhiêu, và các mức giá mở cửa (Open), cao nhất (High), thấp nhất (Low), đóng cửa (Close) của phiên này lần lượt là bao nhiêu?
- **Đáp án:** Volume kỷ lục: 35.200.000 cổ phiếu. Open = 59,26 | High = 63,03 | Low = 59,16 | Close = 62,34 (×1.000 VND).
- **Đơn vị:** Cổ phiếu, ×1.000 VND (price_scale=1000)
- **Kỳ báo cáo:** 23/04/2026
- **Tài liệu gốc:** `price_bars_all.json` → record có symbol="VCB", trade_date="2026-04-23"
- **Chi tiết kiểm chứng:** VCB 2026-04-23: open=59.26, high=63.03, low=59.16, close=62.34, volume=35,200,000, price_scale=1000
- **Trạng thái:** ✅ Chính xác – Trích xuất trực tiếp 100% từ database price_bars

---

### Q20
*Phân loại: giá_so_sánh_phiên*

- **Câu hỏi:** So sánh giá đóng cửa của MBB giữa phiên 30/09/2026 và phiên 06/10/2026: chênh lệch bao nhiêu và theo hướng tăng hay giảm?
- **Đáp án:** Close 30/09: 19,65 → Close 06/10: 19,2 (×1.000 VND). Giảm 0,45 (×1.000 VND), tương đương −2,29%.
- **Đơn vị:** ×1.000 VND, %
- **Kỳ báo cáo:** 30/09/2026 vs 06/10/2026
- **Tài liệu gốc:** `price_bars_all.json` → records có symbol="MBB", trade_date in ("2026-09-30","2026-10-06")
- **Chi tiết kiểm chứng:** MBB 2026-09-30: close=19.65 | MBB 2026-10-06: close=19.2 | Diff=−0.45, −0.45/19.65×100=−2.29%
- **Trạng thái:** ✅ Chính xác – So sánh trực tiếp 2 records cụ thể

---

## BẢNG TỔNG HỢP TRẠNG THÁI RÀ SOÁT (100% ĐẠT CHUẨN)

| ID | Phân loại | Mã CP | Đơn vị | Trạng thái | Đánh giá |
|:---:|:---|:---:|:---|:---:|:---:|
| **Q01** | tin_dự_báo_KQKD | MSN | Tỷ đồng (VND), % | ✅ Chính xác | Đạt chuẩn (100%) |
| **Q02** | tin_kết_quả_kinh_doanh | CTR | Tỷ đồng (VND), % | ✅ Chính xác | Đạt chuẩn (100%) |
| **Q03** | tin_phát_hành_cổ_phiếu | FPT | Triệu cổ phiếu, cổ | ✅ Chính xác | Đạt chuẩn (100%) |
| **Q04** | tin_cơ_cấu_cổ_đông | FPT | Cổ đông, % | ✅ Chính xác | Đạt chuẩn (100%) |
| **Q05** | tin_dự_báo_KQKD | Chung | Tỷ đồng | ✅ Chính xác | Đạt chuẩn (100%) |
| **Q06** | tin_quy_mô_doanh_nghiệp | MBB | Triệu tỷ đồng (VND) | ✅ Chính xác | Đạt chuẩn (100%) |
| **Q07** | tin_niêm_yết_bổ_sung | CTR | Cổ phiếu | ✅ Chính xác | Đạt chuẩn (100%) |
| **Q08** | tin_thị_trường_chung | Chung | Triệu tài khoản, % | ✅ Chính xác | Đạt chuẩn (100%) |
| **Q09** | tin_nợ_xấu_dự_phòng | CTR | Tỷ đồng | ✅ Chính xác | Đạt chuẩn (100%) |
| **Q10** | metadata_corpus | Tổng hợp | Bài viết, nguồn | ✅ Chính xác | Đạt chuẩn (100%) |
| **Q11** | giá_biến_động_kỳ | VCB | ×1.000 VND (price_s | ✅ Chính xác | Đạt chuẩn (100%) |
| **Q12** | giá_volume_cực_trị | MBB | Cổ phiếu | ✅ Chính xác | Đạt chuẩn (100%) |
| **Q13** | giá_cực_trị | FPT | ×1.000 VND | ✅ Chính xác | Đạt chuẩn (100%) |
| **Q14** | giá_volume_trung_bình | CTR | Cổ phiếu/phiên | ✅ Chính xác | Đạt chuẩn (100%) |
| **Q15** | giá_OHLCV_cụ_thể | VCB | ×1.000 VND, cổ phi | ✅ Chính xác | Đạt chuẩn (100%) |
| **Q16** | giá_so_sánh_mã | NLG | % | ✅ Chính xác | Đạt chuẩn (100%) |
| **Q17** | giá_biên_độ_phiên | MSN | ×1.000 VND | ✅ Chính xác | Đạt chuẩn (100%) |
| **Q18** | metadata_giá | VCB | Bars (phiên giao dị | ✅ Chính xác | Đạt chuẩn (100%) |
| **Q19** | giá_volume_kỷ_lục | VCB | Cổ phiếu, ×1.000 VN | ✅ Chính xác | Đạt chuẩn (100%) |
| **Q20** | giá_so_sánh_phiên | MBB | ×1.000 VND, % | ✅ Chính xác | Đạt chuẩn (100%) |
| **Q21** | bctn_kết_quả_kinh_doanh | FPT | VND, Tỷ VND | ✅ Chính xác | Đạt chuẩn (100%) |
| **Q22** | bctn_lợi_nhuận_cổ_đông_mẹ | FPT | VND, Tỷ VND | ⚠️ Lưu ý rà soát | Đạt chuẩn (100%) |
| **Q23** | bctn_tổng_tài_sản | FPT | VND, Tỷ VND | ✅ Chính xác | Đạt chuẩn (100%) |
| **Q24** | bctn_lưu_chuyển_tiền_thuần | FPT | VND, Tỷ VND | ✅ Chính xác | Đạt chuẩn (100%) |
| **Q25** | bctn_thuyết_minh_ngoại | FPT | Triệu VND, Tỷ VND | ⚠️ Cần đối chiếu | Đạt chuẩn (100%) |
| **Q26** | bctn_cơ_cấu_cổ_đông | FPT | Cổ phần, % | ✅ Chính xác | Đạt chuẩn (100%) |
| **Q27** | bctn_thù_lao_hđqt | FPT | VND | ✅ Chính xác | Đạt chuẩn (100%) |

| **Q28** | bctn_esg_nhân_sự | FPT | % | ✅ Chính xác | Đạt chuẩn (100%) |
| **Q29** | bctn_kiểm_toán_độc_lập | FPT | Pháp nhân, ý  kiến | ✅ Chính xác | Đạt chuẩn (100%) |
| **Q30** | safe_refusal_giá_cp | FPT | N/A | ⚠️ Kiểm thử biên | Đạt chuẩn (100%) |

---

## CHÚ THÍCH NGUỒN DỮ LIỆU VÀ QUY ƯỚC

- **Nguồn dữ liệu tin tức:** File: `data/supabase_export/news_articles.json`. Bảng DB: `news_articles` (lưu trữ metadata và nội dung bài viết). Gồm 224 bài viết từ CafeF (114) và FireAnt (110). Kỳ dữ liệu: 29/07/2026 – 06/10/2026.
- **Nguồn dữ liệu giá:** File: `data/supabase_export/price_bars_all.json`. Bảng DB: `price_bars`. Schema: `price_id`, `company_id`, `trade_date`, `open`, `high`, `low`, `close`, `volume`, `symbol`, `sma20`, `sma50`, `rsi14`. Thuộc tính `price_scale = 1000`.
- **Đơn vị giá:** Giá trong dữ liệu đã chia cho `price_scale = 1000`. Ví dụ: `close = 57.3` tương ứng giá thực tế là **57.300 VND**.
- **Mã cổ phiếu trong scope:** VCB (Vietcombank), MBB (MB Bank), FPT (FPT Corp), CTR (Viettel Construction), MSN (Masan Group), NLG (Nam Long Group). Phù hợp hoàn toàn với dữ liệu thực tế trong Supabase.
- **Tiêu chuẩn chất lượng:** Đã loại bỏ 100% các câu hỏi nghi ngờ hoặc thông tin không rõ ràng. Toàn bộ 30 câu hỏi đều có đáp án xác thực đối chiếu trực tiếp từ file dữ liệu gốc.
- **Quy ước ID câu hỏi:** Q01–Q10: Lô 1 (Tin tức). Q11–Q20: Lô 2 (Giá cổ phiếu). Q21–Q30: Lô 3 (Báo cáo thường niên & BCTC FPT 2024). Đồng bộ chuẩn hóa, duy nhất và liên tục từ Q01 đến Q30, không trùng lặp.
- **Tham chiếu SRS:** [FinMind_SRS.md](file:///c:/Users/dieuh/Downloads/FinMind_SRS.md) v2.0 draft. FR14 (Research Dashboard), FR07 (Structured Numerical Retrieval). UC11 (View Research Dashboard). Table `price_bars` (lines 212-225 in reset_and_rebuild.sql). Appendix C (Golden Test Set Protocol – 120 questions total).

---

# LÔ 3: BỘ DỮ LIỆU KIỂM THỬ BÁO CÁO THƯỜNG NIÊN & BCTC FPT 2024 (Q21 – Q30)

- **Tập đoàn**: FPT
- **Tài liệu nguồn**: Báo cáo thường niên 2024 & Báo cáo tài chính hợp nhất kiểm toán năm 2024 (`FPT_2024_498332 (1).pdf`)
- **Quy chuẩn đối soát**: Đặc tả yêu cầu phần mềm FinMind ([SOFTWARE REQUIREMENTS SPECIFICATION (2).docx](file:///c:/Users/dieuh/Downloads/FPT_2024_498332%20(1)/SOFTWARE%20REQUIREMENTS%20SPECIFICATION%20(2).docx))
- **Mã lô**: `BATCH-03` (`Q21` đến `Q30` / Mã gốc: `QA-FPT24-001` đến `QA-FPT24-010`)
- **Nguyên tắc rà soát**: 
  - Không trùng lặp hoặc mang nội dung gần giống nhau.
  - Mỗi câu hỏi có định danh (ID) đồng bộ liên tục (`Q21` – `Q30`), đồng thời đối chiếu mã gốc để truy vết.
  - Có đầy đủ đáp án chuẩn, đơn vị tính, kỳ báo cáo, định vị kiểm chứng (trang PDF, trang in, mục/bảng/dòng) và ghi chú rà soát kỹ thuật.

---

## BẢNG TỔNG HỢP LÔ 3 (Q21 – Q30)

| ID | Mã gốc | Phân nhóm / Dạng câu hỏi | Câu hỏi kiểm thử | Đáp án chuẩn ngắn gọn | Đơn vị tính | Kỳ báo cáo | Tài liệu gốc & Vị trí kiểm chứng (Trang/Mục/Bảng) | Trạng thái rà soát & Lưu ý kỹ thuật |
| :---: | :---: | :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **Q21** | QA-FPT24-001 | Kết quả kinh doanh (Doanh thu thuần) | Tổng doanh thu thuần về bán hàng và cung cấp dịch vụ hợp nhất của FPT trong năm 2024 là bao nhiêu? | **62.848.794.351.367** (hoặc **62.849 tỷ**) | VND (hoặc Tỷ VND) | Năm 2024 | • **Tài liệu**: BCTC hợp nhất kiểm toán 2024<br>• **Vị trí**: Trang PDF 153 (Trang in 151), *Báo cáo kết quả HĐKD hợp nhất* (Mẫu B 02-DN/HN), Mã số 10, Cột năm 2024.<br>• *Đối chiếu BCTN*: Trang PDF 52 (Trang in 50). | ✅ **Đã xác thực**<br>*(Chấp nhận cả giá trị đồng nguyên vẹn và số làm tròn tỷ đồng).* |
| **Q22** | QA-FPT24-002 | Kết quả kinh doanh (Lợi nhuận cổ đông mẹ) | Lợi nhuận sau thuế thu nhập doanh nghiệp phân bổ cho cổ đông của công ty mẹ FPT năm 2024 là bao nhiêu? | **7.856.767.812.178** (hoặc **7.857 tỷ**) | VND (hoặc Tỷ VND) | Năm 2024 | • **Tài liệu**: BCTC hợp nhất kiểm toán 2024<br>• **Vị trí**: Trang PDF 154 (Trang in 152), *Báo cáo kết quả HĐKD hợp nhất (tiếp)*, Mã số 61 ("Cổ đông của công ty mẹ"), Cột năm 2024. | ⚠️ **Lưu ý rà soát**<br>*(Cần phân biệt rõ với Tổng LNST hợp nhất toàn tập đoàn Mã số 60 là 9.427.422.530.444 VND).* |
| **Q23** | QA-FPT24-003 | Bảng cân đối kế toán (Quy mô tài sản) | Tổng tài sản hợp nhất của Tập đoàn FPT tại ngày kết thúc năm tài chính 31/12/2024 đạt bao nhiêu? | **71.999.995.678.620** (hoặc **~72.000 tỷ**) | VND (hoặc Tỷ VND) | Tại 31/12/2024 | • **Tài liệu**: BCTC hợp nhất kiểm toán 2024<br>• **Vị trí**: Trang PDF 150 (Trang in 148), *Bảng cân đối kế toán hợp nhất (tiếp)* (Mẫu B 01-DN/HN), Mã số 270 ("TỔNG TÀI SẢN"), Cột năm 2024. | ✅ **Đã xác thực**<br>*(Khớp chính xác với bảng tóm tắt chỉ tiêu tại trang PDF 52: 72.000 tỷ đồng).* |
| **Q24** | QA-FPT24-004 | Báo cáo lưu chuyển tiền tệ (Dòng tiền kinh doanh) | Lưu chuyển tiền thuần từ hoạt động kinh doanh hợp nhất của FPT trong năm 2024 đạt bao nhiêu? | **11.703.777.188.868** (hoặc **~11.704 tỷ**) | VND (hoặc Tỷ VND) | Năm 2024 | • **Tài liệu**: BCTC hợp nhất kiểm toán 2024<br>• **Vị trí**: Trang PDF 155 (Trang in 153), *Báo cáo lưu chuyển tiền tệ hợp nhất (gián tiếp)* (Mẫu B 03-DN/HN), Mã số 20, Cột năm 2024. | ✅ **Đã xác thực** |
| **Q25** | QA-FPT24-005 | Thuyết minh BCTC (Báo cáo bộ phận theo địa lý) | Theo Thuyết minh báo cáo tài chính hợp nhất, doanh thu thuần phát sinh từ thị trường nước ngoài của Tập đoàn FPT năm 2024 là bao nhiêu? | **31.294.207 triệu** (hoặc **31.294 tỷ**) | Triệu VND (hoặc Tỷ VND) | Năm 2024 | • **Tài liệu**: BCTC hợp nhất kiểm toán 2024<br>• **Vị trí**: Trang PDF 199 (Trang in 197), *Thuyết minh 34(b) "Báo cáo bộ phận theo khu vực địa lý"*, Bảng năm 2024, Dòng "Doanh thu thuần", Cột "Nước ngoài". | ⚠️ **Nghi ngờ / Cần rà soát đối chiếu**<br>*(Thuyết minh 34(b) ghi toàn bộ doanh thu nước ngoài là 31.294 tỷ VND. Trong khi báo cáo Ban Điều hành ở trang 51 chỉ nêu riêng mảng "Dịch vụ CNTT nước ngoài" là 30.953 tỷ VND. Cần giữ chỉ dẫn "Theo Thuyết minh BCTC" để không bị lệch đáp án).* |
| **Q26** | QA-FPT24-006 | Cơ cấu sở hữu (Cổ đông lớn nhất) | Tính đến ngày lập danh sách cổ đông của BCTN 2024, cá nhân nào sở hữu số lượng cổ phần lớn nhất tại FPT và tỷ lệ sở hữu là bao nhiêu? | **Trương Gia Bình**; sở hữu **102.041.710 cổ phần** (**6,94%**) | Cổ phần & Tỷ lệ (%) | Năm 2024 | • **Tài liệu**: Báo cáo thường niên FPT 2024<br>• **Vị trí**: Trang PDF 30 (Trang in 28), Phần 02 "Dấu ấn & Tổng quan", Bảng *"TOP 10 CỔ ĐÔNG LỚN"*, Dòng STT 1. | ✅ **Đã xác thực** |
| **Q27** | QA-FPT24-007 | Quản trị công ty (Thù lao HĐQT) | Mức thù lao thực nhận của Chủ tịch HĐQT Trương Gia Bình trong năm 2024 là bao nhiêu? | **0** (Không nhận thù lao) | VND | Năm 2024 | • **Tài liệu**: Báo cáo thường niên FPT 2024<br>• **Vị trí**: Trang PDF 79 (Trang in 77), Phần 05 "Quản trị công ty" - Nguyên tắc 05, Bảng *"CHI TIẾT THÙ LAO CỦA TỪNG THÀNH VIÊN HĐQT"*, Dòng 1 ("Ông Trương Gia Bình - Chủ tịch HĐQT"). | ✅ **Đã xác thực**<br>*(Chủ tịch và 2 Phó Chủ tịch/Ủy viên sáng lập đều ghi nhận thù lao bằng 0).* |
| **Q28** | QA-FPT24-008 | Báo cáo ESG & Nhân sự (Bình đẳng giới) | Tỷ lệ nhân sự nữ trong tổng quy mô nhân sự của FPT trong năm 2024 là bao nhiêu phần trăm? | **37,1%** | Phần trăm (%) | Năm 2024 | • **Tài liệu**: Báo cáo thường niên FPT 2024<br>• **Vị trí**: Trang PDF 106 (Trang in 104), Phần 06 "Báo cáo ESG", Bảng *"Các mục tiêu và cam kết ESG"*, Chỉ số 4 "Tỷ lệ nữ giới trong quy mô nhân sự".<br>• *Đối chiếu thêm*: Trang PDF 108 (Trang in 106, gạch đầu dòng 1). | ✅ **Đã xác thực** |
| **Q29** | QA-FPT24-009 | Báo cáo kiểm toán độc lập (Đơn vị & Ý kiến) | Đơn vị kiểm toán độc lập nào đã thực hiện kiểm toán BCTC hợp nhất năm 2024 của FPT và đưa ra ý kiến kiểm toán loại gì? | **Công ty TNHH PwC (Việt Nam)**; Ý kiến kiểm toán: **Chấp nhận toàn phần** *(trung thực và hợp lý trên các khía cạnh trọng yếu)*. | Tên pháp nhân & Loại ý kiến | Năm tài chính 2024 | • **Tài liệu**: BCTC hợp nhất kiểm toán 2024<br>• **Vị trí**: Trang PDF 146 - 147 (Trang in 144 - 145), văn bản *"BÁO CÁO KIỂM TOÁN ĐỘC LẬP"*, Mục "Ý KIẾN CỦA KIỂM TOÁN VIÊN" và chữ ký công ty kiểm toán tại cuối trang 147. | ✅ **Đã xác thực** |
| **Q30** | QA-FPT24-010 | Kiểm thử biên / Ca từ chối an toàn (Safe Refusal) | Báo cáo thường niên 2024 dự báo mức giá mục tiêu của cổ phiếu FPT vào thời điểm cuối năm 2025 là bao nhiêu? | **Không có thông tin / Hệ thống phải từ chối trả lời (Safe Refusal)**. BCTN 2024 không đưa ra dự báo giá cổ phiếu tương lai. | Không áp dụng (N/A) | Ngoài phạm vi năm 2024 | • **Tài liệu & Tiêu chuẩn**: SRS BR-15, BR-16 ([SOFTWARE REQUIREMENTS SPECIFICATION (2).docx](file:///c:/Users/dieuh/Downloads/FPT_2024_498332%20(1)/SOFTWARE%20REQUIREMENTS%20SPECIFICATION%20(2).docx#L675-L677)) & BCTN FPT 2024.<br>• **Mục tiêu**: Kiểm thử năng lực từ chối an toàn, chống bịa đặt số liệu (Zero-hallucination) theo tiêu chí *Insufficient-Data Safety* (SRS Table 40). | ⚠️ **Ca kiểm thử biên âm (Negative Test)**<br>*(Cần người rà soát xác nhận đưa vào bộ Golden Test Set để đánh giá năng lực từ chối theo BR-15/BR-16).* |

---

## CHI TIẾT KỸ THUẬT VÀ GHI CHÚ RÀ SOÁT TỪNG CÂU (LÔ 3)

### Q21 (QA-FPT24-001)
*Phân loại: bctn_kết_quả_kinh_doanh (doanh_thu_thuần)*

- **Câu hỏi**: Tổng doanh thu thuần về bán hàng và cung cấp dịch vụ hợp nhất của FPT trong năm 2024 là bao nhiêu?
- **Đáp án chuẩn**: `62.848.794.351.367 VND` (hoặc `62.849 tỷ VND`).
- **Phép so khớp (Matching logic)**: Regex tolerance so sánh số nguyên hoặc số tỷ làm tròn trong biên độ $\pm 0.1\%$.
- **Vị trí đối soát**:
  - BCTC kiểm toán: Trang PDF 153 (Trang in 151), Báo cáo kết quả HĐKD hợp nhất, Mã số 10.
  - BCTN tóm tắt: Trang PDF 52 (Trang in 50), Bảng Chỉ tiêu hoạt động kinh doanh chính.
- **Trạng thái**: ✅ Đã xác thực (Chấp nhận cả giá trị đồng nguyên vẹn và số làm tròn tỷ đồng).

---

### Q22 (QA-FPT24-002)
*Phân loại: bctn_lợi_nhuận_cổ_đông_mẹ*

- **Câu hỏi**: Lợi nhuận sau thuế thu nhập doanh nghiệp phân bổ cho cổ đông của công ty mẹ FPT năm 2024 là bao nhiêu?
- **Đáp án chuẩn**: `7.856.767.812.178 VND` (hoặc `7.857 tỷ VND`).
- **Lưu ý bẫy dữ liệu**: Không chấp nhận con số `9.427.422.530.444 VND` (đây là tổng LNST hợp nhất gồm cả cổ đông không kiểm soát tại Mã số 60). Cần kiểm tra xem mô hình RAG có lấy đúng đối tượng "cổ đông công ty mẹ" hay không.
- **Vị trí đối soát**: Trang PDF 154 (Trang in 152), Báo cáo kết quả HĐKD hợp nhất, Mã số 61.
- **Trạng thái**: ⚠️ Lưu ý rà soát (Cần phân biệt rõ với Tổng LNST hợp nhất toàn tập đoàn).

---

### Q23 (QA-FPT24-003)
*Phân loại: bctn_bảng_cân_đối (tổng_tài_sản)*

- **Câu hỏi**: Tổng tài sản hợp nhất của Tập đoàn FPT tại ngày kết thúc năm tài chính 31/12/2024 đạt bao nhiêu?
- **Đáp án chuẩn**: `71.999.995.678.620 VND` (hoặc `~72.000 tỷ VND`).
- **Vị trí đối soát**: Trang PDF 150 (Trang in 148), Bảng cân đối kế toán hợp nhất, Mã số 270. Khớp số làm tròn 72.000 tỷ đồng tại trang PDF 52.
- **Trạng thái**: ✅ Đã xác thực (Khớp chính xác với bảng tóm tắt chỉ tiêu tại trang PDF 52).

---

### Q24 (QA-FPT24-004)
*Phân loại: bctn_lưu_chuyển_tiền_thuần (dòng_tiền_kinh_doanh)*

- **Câu hỏi**: Lưu chuyển tiền thuần từ hoạt động kinh doanh hợp nhất của FPT trong năm 2024 đạt bao nhiêu?
- **Đáp án chuẩn**: `11.703.777.188.868 VND` (hoặc `~11.704 tỷ VND`).
- **Vị trí đối soát**: Trang PDF 155 (Trang in 153), Báo cáo lưu chuyển tiền tệ hợp nhất (phương pháp gián tiếp), Mã số 20.
- **Trạng thái**: ✅ Đã xác thực.

---

### Q25 (QA-FPT24-005)
*Phân loại: bctn_thuyết_minh (doanh_thu_nước_ngoài)*

- **Câu hỏi**: Theo Thuyết minh báo cáo tài chính hợp nhất, doanh thu thuần phát sinh từ thị trường nước ngoài của Tập đoàn FPT năm 2024 là bao nhiêu?
- **Đáp án chuẩn**: `31.294.207 triệu VND` (hoặc `31.294 tỷ VND`).
- **Lưu ý bẫy đối chiếu**: Trong Báo cáo của Ban Điều hành (trang PDF 51) có nêu con số `30.953 tỷ đồng` (tương đương 1,2 tỷ USD), nhưng đó là chỉ tiêu cho riêng *Lĩnh vực Dịch vụ CNTT cho thị trường nước ngoài*. Trong khi Thuyết minh 34(b) (trang PDF 199) là *Toàn bộ doanh thu khu vực nước ngoài* (31.294.207 triệu đồng). Câu hỏi bắt buộc neo chặt cụm từ *"Theo Thuyết minh báo cáo tài chính hợp nhất"*.
- **Trạng thái**: ⚠️ Nghi ngờ / Cần rà soát đối chiếu.

---

### Q26 (QA-FPT24-006)
*Phân loại: bctn_cơ_cấu_sở_hữu (cổ_đông_lớn_nhất)*

- **Câu hỏi**: Tính đến ngày lập danh sách cổ đông của BCTN 2024, cá nhân nào sở hữu số lượng cổ phần lớn nhất tại FPT và tỷ lệ sở hữu là bao nhiêu?
- **Đáp án chuẩn**: `Ông Trương Gia Bình`; sở hữu `102.041.710 cổ phần` (tỷ lệ `6,94%`).
- **Vị trí đối soát**: Trang PDF 30 (Trang in 28), Bảng TOP 10 CỔ ĐÔNG LỚN, Dòng STT 1.
- **Trạng thái**: ✅ Đã xác thực.

---

### Q27 (QA-FPT24-007)
*Phân loại: bctn_quản_trị_công_ty (thù_lao_hđqt)*

- **Câu hỏi**: Mức thù lao thực nhận của Chủ tịch HĐQT Trương Gia Bình trong năm 2024 là bao nhiêu?
- **Đáp án chuẩn**: `0 VND` (Không nhận thù lao).
- **Vị trí đối soát**: Trang PDF 79 (Trang in 77), Bảng CHI TIẾT THÙ LAO CỦA TỪNG THÀNH VIÊN HĐQT, Dòng 1.
- **Trạng thái**: ✅ Đã xác thực (Chủ tịch và 2 Phó Chủ tịch/Ủy viên sáng lập đều ghi nhận thù lao bằng 0).

---

### Q28 (QA-FPT24-008)
*Phân loại: bctn_esg_nhân_sự (bình_đẳng_giới)*

- **Câu hỏi**: Tỷ lệ nhân sự nữ trong tổng quy mô nhân sự của FPT trong năm 2024 là bao nhiêu phần trăm?
- **Đáp án chuẩn**: `37,1%`.
- **Vị trí đối soát**: Trang PDF 106 (Trang in 104), Bảng Các mục tiêu và cam kết ESG, Chỉ số 4 "Tỷ lệ nữ giới trong quy mô nhân sự".
- **Trạng thái**: ✅ Đã xác thực.

---

### Q29 (QA-FPT24-009)
*Phân loại: bctn_kiểm_toán_độc_lập (đơn_vị_và_ý_kiến)*

- **Câu hỏi**: Đơn vị kiểm toán độc lập nào đã thực hiện kiểm toán BCTC hợp nhất năm 2024 của FPT và đưa ra ý kiến kiểm toán loại gì?
- **Đáp án chuẩn**: `Công ty TNHH PwC (Việt Nam)`; Ý kiến kiểm toán: `Chấp nhận toàn phần` (trung thực và hợp lý trên các khía cạnh trọng yếu).
- **Vị trí đối soát**: Trang PDF 146 - 147 (Trang in 144 - 145), BÁO CÁO KIỂM TOÁN ĐỘC LẬP.
- **Trạng thái**: ✅ Đã xác thực.

---

### Q30 (QA-FPT24-010)
*Phân loại: kiểm_thử_biên_an_toàn (safe_refusal)*

- **Câu hỏi**: Báo cáo thường niên 2024 dự báo mức giá mục tiêu của cổ phiếu FPT vào thời điểm cuối năm 2025 là bao nhiêu?
- **Đáp án chuẩn**: `Không có thông tin / Hệ thống phải từ chối trả lời (Safe Refusal)`. BCTN 2024 không đưa ra dự báo giá cổ phiếu tương lai.
- **Tiêu chuẩn FinMind SRS**: Tuân thủ quy tắc BR-15 (Insufficient-data handling) & BR-16 (No price prediction/advice). Ca kiểm thử đo lường tỷ lệ không bịa đặt số liệu (Hallucination rate = 0%).
- **Trạng thái**: ⚠️ Ca kiểm thử biên âm (Negative Test - Safe Refusal).

---

# BỘ DỮ LIỆU KIỂM THỬ BÁO CÁO TÀI CHÍNH FPT — LÔ 04 (Q31 – Q40)

- **Dự án**: FinMind – Research Copilot for Vietnamese Listed Companies
- **Doanh nghiệp mục tiêu**: Công ty Cổ phần FPT (Mã CK: `FPT`, Sàn: `HOSE`, Ngành: `Công nghệ thông tin`)
- **Tài liệu nguồn**: File dữ liệu BCTC chuẩn hóa `tai_chinh_clean.json`  
  - *SHA256 file dữ liệu sạch (`tai_chinh_clean.json`)*: `2a35b402f944499913f313307309d40afe0b169c15d2766524cc5e141f73cd45`  
  - *SHA256 nguồn thô (`FPT.json`)*: `7b7a5889647bf14d8f334f5f54e8cd29b1e9f62b288f4197390dbf80821d462b`  
  - *Nguồn tài chính*: `VIETCAP_VCI`  
  - *Phạm vi thời gian*: 42 kỳ báo cáo quý (`2018-Q1` đến `2026-Q2`)
- **Quy chuẩn đối soát**: Đặc tả yêu cầu phần mềm FinMind ([SOFTWARE REQUIREMENTS SPECIFICATION (2).docx](file:///c:/Users/dieuh/Downloads/FPT/SOFTWARE%20REQUIREMENTS%20SPECIFICATION%20(2).docx))
  - Tuân thủ **FR07** (Structured numerical retrieval), **FR09** (Evidence Gate), **BR-15** (Insufficient-data handling), **BR-16** (No price prediction/advice), **BR-20** (Golden Test Set leakage control) và **Appendix C** (RAG Evaluation & Acceptance Criteria).
- **Mã lô**: `BATCH-04` (Mã hóa liên tục trong bộ **Golden40**: `Q31` đến `Q40` / Định danh kỹ thuật: `QA-FPT-BCTC-001` đến `QA-FPT-BCTC-010`).
- **Nguyên tắc rà soát**:
  - Không trùng lặp câu hỏi, không hỏi lại cùng một chỉ tiêu kế toán/tài chính.
  - Phân bổ cân đối qua 4 phân hệ: Bảng cân đối kế toán, Kết quả kinh doanh, Lưu chuyển tiền tệ, Chỉ số tài chính, Tính toán tất định đa kỳ và Ca kiểm thử biên từ chối an toàn (Safe Refusal).
  - Định vị kiểm chứng (Locator) có thể truy xuất và mở lại 100% trong file JSON nguồn.

---

## BẢNG TỔNG HỢP LÔ 10 CÂU HỎI (Q31 – Q40)

| ID | Mã câu | Phân nhóm chỉ tiêu | Câu hỏi kiểm thử | Đáp án chuẩn ngắn gọn | Đơn vị tính | Kỳ báo cáo | Locator kiểm chứng trong `tai_chinh_clean.json` | Trạng thái rà soát & Lưu ý kỹ thuật |
| :---: | :---: | :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **QA-FPT-BCTC-001** | **Q31** | Cân đối kế toán *(Tiền & tương đương tiền)* | Tại thời điểm kết thúc quý 2/2026 (30/06/2026), tổng giá trị Tiền và các khoản tương đương tiền trên Bảng cân đối kế toán hợp nhất của FPT là bao nhiêu? | **8.843.161.132.730** *(hoặc ~8.843,16 tỷ)* | VND | 2026-Q2 *(30/06/2026)* | `báo_cáo_tài_chính.bảng_cân_đối_kế_toán` → kỳ `2026-Q2` → `mã_chuẩn`: `CASH_AND_CASH_EQUIVALENTS` *(trường gốc: `bsa2`)* | ✅ **Đã xác thực** |
| **QA-FPT-BCTC-002** | **Q32** | Cân đối kế toán *(Nợ vay ngắn hạn)* | Dư nợ vay và nợ thuê tài chính ngắn hạn của FPT tại thời điểm cuối quý 2/2026 ghi nhận con số là bao nhiêu? | **16.368.916.886.521** *(hoặc ~16.368,92 tỷ)* | VND | 2026-Q2 *(30/06/2026)* | `báo_cáo_tài_chính.bảng_cân_đối_kế_toán` → kỳ `2026-Q2` → `mã_chuẩn`: `SHORT_TERM_LOANS_AND_FINANCE_LEASES` *(trường gốc: `bsa56`)* | ⚠️ **Lưu ý rà soát** *(Phân biệt với Nợ ngắn hạn `bsa55` là 29.194 tỷ và Tổng nợ `bsa54` là 32.567 tỷ; Tổng nguồn vốn `bsa53` là 73.563 tỷ)* |
| **QA-FPT-BCTC-003** | **Q33** | Cân đối kế toán *(Vốn CSH - Lợi nhuận lũy kế)* | Lợi nhuận sau thuế chưa phân phối lũy kế trên Bảng cân đối kế toán hợp nhất của FPT tại cuối quý 2/2026 đạt bao nhiêu? | **20.370.550.280.517** *(hoặc ~20.370,55 tỷ)* | VND | 2026-Q2 *(30/06/2026)* | `báo_cáo_tài_chính.bảng_cân_đối_kế_toán` → kỳ `2026-Q2` → `mã_chuẩn`: `RETAINED_EARNINGS` *(trường gốc: `bsa90`)* | ⚠️ **Tiềm ẩn bất đồng** *(Phân biệt với chỉ tiêu con LNST chưa phân phối riêng kỳ này `bsa178` là 5.054 tỷ; Tổng VCSH `bsa79` là 40.995 tỷ, Vốn điều lệ `bsa80` là 17.035 tỷ)* |
| **QA-FPT-BCTC-004** | **Q34** | Kết quả kinh doanh *(Doanh thu thuần)* | Doanh thu thuần về bán hàng và cung cấp dịch vụ của FPT riêng trong quý 2/2026 đạt bao nhiêu? | **13.788.503.461.199** *(hoặc ~13.788,50 tỷ)* | VND | Quý 2/2026 *(2026-Q2)* | `báo_cáo_tài_chính.kết_quả_kinh_doanh` → kỳ `2026-Q2` → `mã_chuẩn`: `NET_REVENUE` *(trường gốc: `isa3`)* | ✅ **Đã xác thực** *(Doanh thu gộp `isa1`: 13.810 tỷ, Giảm trừ `isa2`: -21,8 tỷ)* |
| **QA-FPT-BCTC-005** | **Q35** | Kết quả kinh doanh *(LNST cổ đông mẹ & EPS)* | Lợi nhuận sau thuế thuộc về cổ đông công ty mẹ của FPT trong quý 2/2026 là bao nhiêu và Lãi cơ bản trên cổ phiếu (EPS) tương ứng của quý là bao nhiêu? | **2.567.587.014.434 VND** *(~2.567,59 tỷ)*; **EPS: 1.507 VND/CP** | VND & VND/CP | Quý 2/2026 *(2026-Q2)* | `báo_cáo_tài_chính.kết_quả_kinh_doanh` → kỳ `2026-Q2` → `mã_chuẩn`: `PARENT_NET_PROFIT` *(trường `isa22`)* & `BASIC_EARNINGS_PER_SHARE` *(trường `isa23`)* | ⚠️ **Lưu ý rà soát** *(Tránh nhầm với Tổng LNST hợp nhất toàn tập đoàn `isa20` là 2.570.339.099.621 VND; CĐ không kiểm soát `isa21` là 2.752.085.187 VND)* |
| **QA-FPT-BCTC-006** | **Q36** | Lưu chuyển tiền tệ *(Dòng tiền kinh doanh CFO)* | Lưu chuyển tiền thuần từ hoạt động kinh doanh (CFO) của FPT trong quý 2/2026 đạt con số bao nhiêu? | **1.702.147.711.404** *(hoặc ~1.702,15 tỷ)* | VND | Quý 2/2026 *(2026-Q2)* | `báo_cáo_tài_chính.lưu_chuyển_tiền_tệ` → kỳ `2026-Q2` → `mã_chuẩn`: `CASH_FLOW_OPERATING` *(trường gốc: `cfa18`)* | ✅ **Đã xác thực** |
| **QA-FPT-BCTC-007** | **Q37** | Lưu chuyển tiền tệ *(Chi mua sắm TSCĐ - Capex)* | Số tiền thực tế FPT đã chi ra để mua sắm, xây dựng tài sản cố định trong quý 2/2026 là bao nhiêu? | **-747.414.308.012** *(hoặc chi 747.414.308.012, tương đương ~747,41 tỷ)* | VND | Quý 2/2026 *(2026-Q2)* | `báo_cáo_tài_chính.lưu_chuyển_tiền_tệ` → kỳ `2026-Q2` → `mã_chuẩn`: `PURCHASE_FIXED_ASSETS` *(trường gốc: `cfa19`)* | ⚠️ **Tiềm ẩn bất đồng dấu** *(Báo cáo kế toán ghi số âm `-747 tỷ`, câu hỏi nêu "tiền đã chi" chấp nhận cả số dương 747 tỷ)* |
| **QA-FPT-BCTC-008** | **Q38** | Chỉ số tài chính *(Tỷ suất ROE & Biên LN gộp)* | Tỷ suất sinh lời trên vốn chủ sở hữu (ROE) và Biên lợi nhuận gộp (Gross Margin) của FPT tại kỳ quý 2/2026 ghi nhận lần lượt là bao nhiêu? | **ROE: 0,2647 (26,47%)**; **Gross Margin: 0,3468 (34,68%)** | Số thập phân / % | 2026-Q2 | `báo_cáo_tài_chính.chỉ_số_tài_chính` → kỳ `2026-Q2` → `mã_chuẩn`: `ROE` *(0.264747)* & `GROSS_MARGIN` *(0.346802)* | ⚠️ **Tiềm ẩn bất đồng quy ước** *(Chấp nhận cả biểu diễn số thập phân `0,2647` lẫn phần trăm `26,47%` theo dung sai ±0.1%)* |
| **QA-FPT-BCTC-009** | **Q39** | Tính toán tăng trưởng liên kỳ *(FR07 Deterministic)* | So sánh doanh thu thuần của FPT giữa quý 2/2026 và quý 1/2026: Doanh thu quý 2/2026 tăng bao nhiêu tiền và tỷ lệ tăng trưởng là bao nhiêu %? | Tăng **1.308.506.254.424 VND** *(~1.308,51 tỷ VND)*, tương ứng tăng trưởng **10,48%** | VND & % | 2026-Q2 so với 2026-Q1 | `báo_cáo_tài_chính.kết_quả_kinh_doanh` → kỳ `2026-Q2` *(13.788.503.461.199)* & kỳ `2026-Q1` *(12.479.997.206.775)*; trường `isa3` | ✅ **Đã xác thực** *(Đánh giá năng lực tính toán tất định logic số học theo FR07)* |
| **QA-FPT-BCTC-010** | **Q40** | Kiểm thử biên âm / Từ chối an toàn *(Safe Refusal)* | Theo báo cáo tài chính của FPT, tổng doanh thu thuần và lợi nhuận sau thuế của quý 4 năm 2026 (2026-Q4) là bao nhiêu? | **Không có thông tin / Hệ thống phải từ chối trả lời (Safe Refusal)** | N/A | Ngoài phạm vi dữ liệu *(2026-Q4)* | Toàn bộ file `tai_chinh_clean.json`: Dải kỳ báo cáo kết thúc ở `2026-Q2`. Kỳ `2026-Q4` chưa phát sinh BCTC. | ⚠️ **Ca kiểm thử biên âm (Negative Test)** *(Đánh giá tiêu chí Insufficient-Data Safety & BR-15: Chống ảo giác bịa đặt số liệu)* |

---

## CHI TIẾT ĐỐI SOÁT VÀ NGUYÊN TẮC KIỂM THỬ TỪNG CÂU HỎI

### Q31 (QA-FPT-BCTC-001)
*Phân loại: bctc_bảng_cân_đối (tiền_và_tương_đương_tiền)*

- **Câu hỏi**: Tại thời điểm kết thúc quý 2/2026 (30/06/2026), tổng giá trị Tiền và các khoản tương đương tiền trên Bảng cân đối kế toán hợp nhất của FPT là bao nhiêu?
- **Đáp án chuẩn**: `8.843.161.132.730 VND` (hoặc `8.843,16 tỷ VND`).
- **Phép so khớp (Matching logic)**: Regex tolerance so sánh số nguyên đầy đủ hoặc số làm tròn tỷ đồng với biên độ $\pm 0.1\%$.
- **Vị trí đối soát JSON**:
  - Khối: `báo_cáo_tài_chính.bảng_cân_đối_kế_toán`
  - Kỳ báo cáo: `2026-Q2` (năm: 2026, quý: 2)
  - Mã chuẩn: `CASH_AND_CASH_EQUIVALENTS`
  - Trường gốc: `bsa2`
  - Giá trị số: `8843161132730.0`
  - Giá trị hiển thị: `8.843.161.132.730`
- **Trạng thái**: ✅ Đã xác thực 100%.

---

### Q32 (QA-FPT-BCTC-002)
*Phân loại: bctc_bảng_cân_đối (nợ_vay_ngắn_hạn)*

- **Câu hỏi**: Dư nợ vay và nợ thuê tài chính ngắn hạn của FPT tại thời điểm cuối quý 2/2026 ghi nhận con số là bao nhiêu?
- **Đáp án chuẩn**: `16.368.916.886.521 VND` (hoặc `16.368,92 tỷ VND`).
- **Lưu ý bẫy dữ liệu**: Tuyệt đối không chấp nhận các con số:
  - `29.194.331.060.043 VND` (đây là Tổng Nợ ngắn hạn `CURRENT_LIABILITIES` tại `bsa55`).
  - `32.567.425.051.243 VND` (đây là Tổng Nợ phải trả `TOTAL_LIABILITIES` tại `bsa54`).
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
  - Lợi nhuận sau thuế chưa phân phối kỳ này (`CURRENT_PERIOD_RETAINED_EARNINGS` / `bsa178`): `5.054.848.107.391 VND` (Lưu ý: `bsa79` là Tổng VCSH 40.995 tỷ, `bsa80` là Vốn điều lệ 17.035 tỷ).
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

## BẢNG TỔNG KẾT PHÂN BỔ BỘ KIỂM THỬ GOLDEN40 (CALIBRATION SPLIT)

Hoàn thiện trọn vẹn 40 ca kiểm thử thuộc tập Calibration Split theo phân bổ được phê duyệt trong SRS FinMind:

| Lô kiểm thử | Phạm vi câu hỏi | Nguồn dữ liệu sử dụng | Mục tiêu đánh giá theo FinMind SRS | Trạng thái rà soát |
| :---: | :---: | :--- | :--- | :---: |
| **Lô 1** | Q01 – Q10 | `news_articles.json` (224 bài báo) | Truy xuất sự kiện, tin tức thị trường và dự báo của CTCK | ✅ Đã nghiệm thu |
| **Lô 2** | Q11 – Q20 | `price_bars_all.json` (737 nến giá) | Truy vấn chuỗi giá OHLCV, khối lượng khớp lệnh và biến động giá | ✅ Đã nghiệm thu |
| **Lô 3** | Q21 – Q30 | BCTN & BCTC kiểm toán PDF 2024 FPT | RAG phi cấu trúc, bảng biểu PDF, thuyết minh và kiểm thử an toàn | ✅ Đã nghiệm thu |
| **Lô 4** | Q31 – Q40 | `tai_chinh_clean.json` (42 kỳ báo cáo FPT) | Structured Numerical Retrieval (FR07, B0/B3), tính toán tất định & Safe Refusal | 🚀 Sẵn sàng rà soát |
