# BỘ CÂU HỎI KIỂM THỬ GOLDEN TEST SET
## LÔ 1 & LÔ 2: TIN TỨC VÀ GIÁ CỔ PHIẾU (100% CHÍNH XÁC)

*Dự án: FinMind – Research Copilot for Vietnamese Listed Companies*  
*Ngày cập nhật: 14/10/2026*  
*Phiên bản: v2.0 – Đã loại bỏ tất cả câu nghi ngờ (20/20 câu chính xác 100%)*  
*Phạm vi corpus: VCB, MBB, FPT, CTR, MSN, NLG*  
*Nguồn dữ liệu: news_articles.json (224 bài), price_bars_all.json (737 bars)*  
*Kỳ dữ liệu: 29/07/2026 – 07/10/2026 (tin tức), 09/04/2026 – 07/10/2026 (giá)*

---

## MỤC LỤC
1. [Lô 1: Câu hỏi về TIN TỨC (Q01 – Q10)](#lô-1-câu-hỏi-về-tin-tức-q01--q10)
2. [Lô 2: Câu hỏi về GIÁ CỔ PHIẾU (Q11 – Q20)](#lô-2-câu-hỏi-về-giá-cổ-phiếu-q11--q20)
3. [Bảng tổng hợp trạng thái rà soát (100% Đạt chuẩn)](#bảng-tổng-hợp-trạng-thái-rà-soát-100-đạt-chuẩn)
4. [Chú thích nguồn dữ liệu và quy ước](#chú-thích-nguồn-dữ-liệu-và-quy-ước)

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

---

## CHÚ THÍCH NGUỒN DỮ LIỆU VÀ QUY ƯỚC

- **Nguồn dữ liệu tin tức:** File: `data/supabase_export/news_articles.json`. Bảng DB: `news_articles` (lưu trữ metadata và nội dung bài viết). Gồm 224 bài viết từ CafeF (114) và FireAnt (110). Kỳ dữ liệu: 29/07/2026 – 06/10/2026.
- **Nguồn dữ liệu giá:** File: `data/supabase_export/price_bars_all.json`. Bảng DB: `price_bars`. Schema: `price_id`, `company_id`, `trade_date`, `open`, `high`, `low`, `close`, `volume`, `symbol`, `sma20`, `sma50`, `rsi14`. Thuộc tính `price_scale = 1000`.
- **Đơn vị giá:** Giá trong dữ liệu đã chia cho `price_scale = 1000`. Ví dụ: `close = 57.3` tương ứng giá thực tế là **57.300 VND**.
- **Mã cổ phiếu trong scope:** VCB (Vietcombank), MBB (MB Bank), FPT (FPT Corp), CTR (Viettel Construction), MSN (Masan Group), NLG (Nam Long Group). Phù hợp hoàn toàn với dữ liệu thực tế trong Supabase.
- **Tiêu chuẩn chất lượng:** Đã loại bỏ 100% các câu hỏi nghi ngờ hoặc thông tin không rõ ràng. 20/20 câu hỏi đều có đáp án xác thực đối chiếu trực tiếp từ file dữ liệu gốc.
- **Quy ước ID câu hỏi:** Q01–Q10: Lô 1 (Tin tức). Q11–Q20: Lô 2 (Giá cổ phiếu). Không có câu hỏi trùng lặp hoặc gần trùng nội dung.
- **Tham chiếu SRS:** [FinMind_SRS.md](file:///c:/Users/dieuh/Downloads/FinMind_SRS.md) v2.0 draft. FR14 (Research Dashboard), FR07 (Structured Numerical Retrieval). UC11 (View Research Dashboard). Table `price_bars` (lines 212-225 in reset_and_rebuild.sql). Appendix C (Golden Test Set Protocol – 120 questions total).
