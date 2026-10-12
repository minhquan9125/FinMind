# Review: POC Python OCR router và Document IR (FinMind)

- **Đối tượng:** repo `FindMind/FinMind`, nhánh `feature/ocr-pipeline`, commit `b75d880` (09/10/2026). Gồm khoảng 3.300 dòng Python trong `src/`, 3 file test và output mẫu trong `ocr_router_out/`.  
- **Đối chiếu:**  
  - `KNOWHOW_ChuanHoa_BCTC_OCR_20261002.md`: PA C, mục 7–8.  
  - `poc/ocr-router/README.md`: kế hoạch A–E, mốc S2.  
  - `REVIEW_Pipeline_OCR_HanhChinh_v6_20261005.md`.  
- **Ngày review:** 09/10/2026. Hạn Sprint 2 là 11/10/2026.  
- **Cách review:**  
  - Đọc toàn bộ `src/`, chạy test, chạy lại builder.  
  - Làm 7 thí nghiệm (E1–E7) trên hai PDF mẫu và trên output Gemini của POC TypeScript. Lệnh tái lập ở [phụ lục](#phụ-lục-lệnh-tái-lập-thí-nghiệm).  
  - Các giải pháp có kèm code đều đã chạy thử trên bản sao của repo, trừ những chỗ ghi "chưa kiểm".  
  - Không gọi Gemini hay OpenRouter vì không có key.  
- **Cách đọc:**  
  - Mục 3 tóm tắt 11 vấn đề.  
  - Mục 4 trình bày từng vấn đề theo bốn phần: **Vấn đề**, **Bằng chứng**, **Giải pháp**, **Xong khi**.  
- **Mức độ:**  
  - 🔴 chặn, phải sửa trước khi dùng kết quả;  
  - 🟡 cần sửa trong Sprint 3;  
  - 🟢 dọn dẹp.

---

## 1\. Kết luận

**Chưa nên dùng làm nền cho Sprint 3 ở trạng thái hiện tại.** Phần lõi tốt hơn những gì output cho thấy. Nhưng các con số trong README chưa chứng minh được điều README nói.

**Tin tốt:** parser bảng tổng quát `_coded_statement_table` tái tạo đúng 278/278 ô của bảng FPT 2024 đã rà soát. Bộ phân loại tổng quát cũng nhận đúng 9/9 trang báo cáo chính. Nghĩa là có thể bỏ ngay nhánh gắn cứng cho FPT 2024 mà không mất gì.

**Năm vấn đề chặn:**

1. **Không chạy lại được.** Builder cần `templates/financial-template-lines.json`, nhưng file này không có trong repo và cũng không có ở đâu trong workspace.  
2. **Kết quả FPT 2024 không do pipeline tạo ra.** Phân loại trang, 15 bảng thường niên, 30 KPI và bảng BCTC đều lấy từ dữ liệu nhập tay, được chọn theo SHA-256 của file PDF.  
3. **Phép đo "278/278 ô khớp Poppler" không phát hiện được ô nằm sai dòng hay sai cột.** Đảo cột và tráo giá trị giữa hai dòng, phép đo vẫn ra 278/278.  
4. **Chưa có đường xử lý cho bài toán chính của KNOWHOW:** BCTC scan, mẫu TT99, BCTC phát hành riêng và mẫu ngân hàng. Với output Gemini của BCTC scan TT99, cả 3 trang báo cáo chính bị bỏ qua.  
5. **Đẳng thức chỉ kiểm 18 dòng tổng.** Ít nhất 60/83 dòng CĐKT không thuộc luật nào. Ngoài ra, parser số nhận cả chuỗi lỗi OCR thật mà không báo.

**Ghi nhận:** README và WorkLog đã tự ghi rõ rằng 278/278 chỉ là đồng thuận giữa hai bộ đọc, gold set chưa có và S2 chưa xong. Review này bổ sung những điểm README chưa thấy.

---

## 2\. Kết quả chạy thử

| \# | Thí nghiệm | Kết quả |
| :---- | :---- | :---- |
| E1 | `python3 -m unittest discover -s tests` | 11 test: 8 đạt, 1 lỗi, 2 bỏ qua. Cả 3 test của router (`test_main.py`) đều lỗi hoặc bị bỏ qua |
| E2 | Chạy `buildDocumentIr.py BCTN_2025.pdf` trên `pages.jsonl` đã commit | Chạy 37 giây rồi dừng với lỗi `Thiếu templates/financial-template-lines.json trong cây workspace` |
| E3 | Chạy `_coded_statement_table` (nhánh dành cho PDF không phải FPT 2024\) trên FPT 2024, trang 148–156, rồi so với fixture đã rà soát | 278/278 ô giống hệt. `financial_page_class` (nhánh không dùng SHA-256) phân loại đúng 9/9 trang |
| E4 | Trên bản sao IR FPT 2024 trang 148: đảo cột 2024↔2023 ở dòng 110, tráo giá trị cột 2024 giữa dòng 110 và 111\. Sau đó chạy `evaluateDocumentIr.py` | Vẫn ra `cells_matched: 278`, `exact_agreement: 1.0` |
| E5 | Đưa text Gemini của `bctc_fpt_2026.pdf`, trang 7–9 (TT99, scan) qua `financial_page_class` và `_text_blocks` | Cả 3 trang bị phân loại `None`. Parser Markdown dựng đúng bảng 31, 22 và 19 dòng có mã. Nhưng tiêu đề cột "Số cuối kỳ VND" và "Kỳ này VND" không có năm, nên ô không vào được đẳng thức |
| E6 | Đưa vào `_parse_accounting_number` các chuỗi lỗi OCR thật ở KNOWHOW mục 5.3 | `"3,405.535.984"` ra ≈ 3,4 (đúng là 3.405.535.984). `"3.451.002.5587"` ra 34.510.025.587 (đúng là 3.451.002.557). `"2.773,180.700"` ra 2.773,18 (đúng là 2.773.160.700). Không chuỗi nào bị từ chối |
| E7 | So các ô năm 2024 giữa hai PDF: năm hiện tại của bản 2024 và năm so sánh của bản 2025 | 136/139 ô khớp. Ô KQKD 52 thiếu ngoặc trong bản 2025, đã được pipeline gắn cờ. EPS (dòng 70, 71\) lệch: 4.944 so với 4.292, tỉ lệ ≈ 1,15, nhiều khả năng do EPS được trình bày lại sau đợt phát hành cổ phiếu thưởng (cần xem thuyết minh). Không có cờ nào cho chỗ lệch EPS |

&nbsp;

---

## 3\. Bảng tổng hợp

| \# | Vấn đề | Mức | Giải pháp ngắn | Hạn đề xuất |
| :---- | :---- | :---- | :---- | :---- |
| R1 | Không chạy lại được vì thiếu file template | 🔴 | Commit template vào repo, dùng đường dẫn cố định, thêm smoke test | 11/10 |
| R2 | Kết quả FPT 2024 lấy từ dữ liệu nhập tay, chọn theo SHA-256 | 🔴 | Bỏ nhánh SHA-256, chuyển dữ liệu nhập tay thành test | 11/10 |
| R3 | Phép đo ô không bắt được lỗi sai dòng hay sai cột | 🔴 | Gold set chép tay, khoá theo (báo cáo, mã, kỳ); so chéo hai bản | 11/10 |
| R4 | Chưa xử lý được BCTC scan, TT99, BCTC phát hành riêng, ngân hàng | 🔴 | Phân loại theo tiêu đề, gán kỳ cho cột, chọn template theo thông tư | Sprint 3 |
| R5 | Đẳng thức chỉ kiểm dòng tổng | 🟡 | Cây luật cha–con đầy đủ, đo độ phủ | Sprint 3 |
| R6 | Parser số nhận chuỗi sai định dạng | 🟡 | Kiểm nhóm 3 chữ số, gắn `BAD_NUMBER_FORMAT` | Sprint 3 |
| R7 | Test router hỏng; phần dựng IR không có test | 🟡 | Sửa 3 test, thêm test hồi quy | 11/10 |
| R8 | OpenRouter dự phòng chưa từng chạy | 🟡 | Nhóm và mentor quyết định; nếu giữ thì sửa schema và chạy thử | Sprint 3 |
| R9 | README ghi "xong" ở nhiều mục chưa xong | 🟡 | Cập nhật trạng thái theo bằng chứng | 11/10 |
| R10 | Công sức lệch khỏi DoD Sprint 2 | 🟡 | Tạm dừng phần báo cáo thường niên, dồn sức cho gold set và ngân hàng | 11/10 |
| R11 | Code và repo cần dọn | 🟢 | Bỏ code chết, gộp hàm lặp, sửa cache, giảm dung lượng repo | Sprint 3 |

&nbsp;

---

## 4\. Chi tiết từng vấn đề

### R1. Không chạy lại được vì thiếu file template 🔴

**Vấn đề**

- **File template không có trong repo.** Hàm `financialContent._accounting_template_path()` (dòng 389–394) tìm `templates/financial-template-lines.json` bằng cách dò ngược qua mọi thư mục cha của `src/`, tới gốc ổ đĩa. Vì vậy builder (`--build-document-ir`, `buildDocumentIr.py`) và `auditDocumentIr.py` không chạy được trên máy khác. Cũng không ai kiểm lại được output trong `ocr_router_out/`, kể cả kết quả 43/43 và 42/42.  
- **Kết quả phụ thuộc vào nơi đặt repo.** Vì code dò tới tận gốc ổ đĩa, nếu thư mục cha nào đó có file cùng tên, code sẽ dùng file đó mà không báo.  
- **Không truy được phiên bản template.** Output chỉ ghi `arithmetic_template_id`, không ghi phiên bản hay sha256 của template.

**Bằng chứng**

- E2: builder dừng vì thiếu file.  
- Đã `find` trên toàn bộ workspace `KDN_DTU/` và không thấy file này.

**Giải pháp**

1. Lấy file template từ máy tác giả, commit vào `templates/financial-template-lines.json` trong repo.  
2. Dùng đường dẫn cố định, tương đối với gốc repo. Cho phép đổi template qua tham số `--template`.

```py
TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "financial-template-lines.json"
```

3. Ghi `template_sha256` vào `table/index.json`, cạnh `arithmetic_template_id`.  
4. Thêm smoke test: chạy builder trên `pages.jsonl` đã commit, ghi ra thư mục tạm, rồi so với output đã commit.

**Xong khi:** clone sạch repo, chạy builder cho cả hai PDF mẫu, output trùng với bản đã commit (chỉ khác đường dẫn tuyệt đối).

---

### R2. Kết quả FPT 2024 lấy từ dữ liệu nhập tay, chọn theo SHA-256 🔴

**Vấn đề**

Code rẽ nhánh theo SHA-256 của hai PDF mẫu ở 8 chỗ. Ở các chỗ đó, kết quả lấy từ dữ liệu nhập tay thay vì do pipeline tạo ra:

| Vị trí | Dữ liệu nhập tay | Số liệu README bị ảnh hưởng |
| :---- | :---- | :---- |
| `financialContent.py:37–54` | Loại trang BCTC 2024, tra theo số trang (143 là mục lục, 148–152 là CĐKT…) | "A7 ✅ phân loại chuẩn xác toàn bộ" |
| `financialContent.py:96, 228` | Bảng BCTC 2024, đọc thẳng từ `Document IR/fpt-2024-reviewed-financial-tables.json` | 9 trang có bảng cấu trúc, 278 ô, 43/43 |
| `reportContent.py:228` | Khoảng trang của từng chủ đề thường niên 2024 | 119 trang, 6 chủ đề |
| `reportContent.py:165–224, 277, 363` | Toạ độ của 15 bảng thường niên 2024 (`box`, `cuts`, số dòng) | "15 bảng cấu trúc" |
| `reportContent.py:402–437, 443` | Nhãn KPI: 30 nhãn cho bản 2024, 2 nhãn cho bản 2025 | "30 KPI verified" |
| `buildDocumentIr.py:413` | Thứ tự đọc của trang 45, 98, 133 | — |

&nbsp;

**Các heuristic còn lại cũng chỉ hợp với bố cục FPT:**

- nhận mục lục bên theo màu xanh (`_is_active_blue`);  
- tìm các cụm "dau an 2024/2025", "tong quan ve fpt";  
- nhận menu đánh số theo `^0[1-7]`;  
- coi 22% chiều rộng bên trái trang là lề.

Với báo cáo thường niên của công ty khác, `annual_topics` trả rỗng cho mọi trang.

**Fixture bảng BCTC không độc lập với pipeline.** `source.tool` của fixture là `pdfplumber 0.11.9`, tức chính công cụ mà pipeline dùng.

**Bằng chứng&nbsp;**

E3: khi bỏ nhánh SHA-256, parser tổng quát vẫn cho đúng 278/278 ô và phân loại đúng 9/9 trang. Nhánh nhập tay cho BCTC vì vậy là thừa.

**Giải pháp**

1. **BCTC 2024:** xoá `if digest == FPT_2024_SHA256` trong `financial_page_class` và `statement_tables`, để mọi PDF đi cùng một đường.  
2. **Fixture BCTC:** chuyển `Document IR/fpt-2024-reviewed-financial-tables.json` sang `tests/fixtures/`. Thêm test kiểm `_coded_statement_table` ra đúng 278 ô của fixture (đoạn E3 ở phụ lục).  
3. **Bảng thường niên, KPI và thứ tự đọc 2024:** đưa ra khỏi đường chạy chính.  
   - Nếu còn cần cho demo, tách thành file override riêng, ví dụ `overrides/fpt_2024.json`.  
   - Chỉ nạp file này khi có cờ `--overrides`.  
   - Ghi các override đã áp dụng vào `annual_ir/index.json`, ví dụ `"overrides_applied": [...]`.  
4. **Heuristic riêng của FPT** (màu sidebar, menu `0[1-7]`, lề 22%): gom vào một "layout profile" có bước tự nhận diện. Mặc định là bố cục không có sidebar.  
5. **README:** tách số liệu do pipeline tạo ra khỏi số liệu lấy từ override.

**Xong khi:**

- `grep -n "FPT_20.._SHA256" src/` không còn kết quả;  
- test 278 ô đạt;  
- README ghi riêng hai loại số liệu.

---

### R3. Phép đo ô không bắt được lỗi sai dòng hay sai cột 🔴

**Vấn đề**

- **Phép so Poppler gần như luôn khớp.**  
  - `evaluateDocumentIr.py` lấy các từ Poppler nằm trong `bbox` của ô, rồi so với `raw`.  
  - Nhưng `bbox` được dựng từ chính các từ của ô (`_word_box(first)`, `financialContent.py:198`).  
  - Poppler và pdfplumber lại cùng đọc một lớp text.  
- **Phép so chỉ kiểm được việc tách từ và giải mã ký tự.** Nó không kiểm được ô có nằm đúng mã dòng và đúng kỳ hay không, trong khi đây là lỗi hay gặp nhất khi tách bảng.  
- **`gold_candidates.json` có cùng điểm yếu.**  
  - `gold_raw` được điền sẵn bằng kết quả Poppler, nên người duyệt dễ duyệt cả ô bị gán sai dòng.  
  - File khoá theo `(page, table_id, row_id, column)` của IR. Khi IR đổi thứ tự dòng, mọi nhãn đã duyệt mất hiệu lực (`evaluateDocumentIr.py:97–98`).

**Bằng chứng**

- **E4:** sau khi đảo cột và tráo dòng, phép đo vẫn ra 278/278.  
- **E7:** so cột năm 2024 giữa hai bản thì 136/139 ô khớp. Phép so này bắt được một ô thiếu ngoặc và EPS bị lệch, hai thứ mà phép so Poppler bỏ qua.

**Giải pháp**

1. **Gold set chép tay từ ảnh trang, không điền sẵn.**  
   - Hai người chép độc lập rồi đối chiếu chỗ khác nhau.  
   - Khoá theo nghiệp vụ, không theo vị trí trong IR:

```
document_sha256,statement,code,period_end,period_type,value_raw,pdf_page,transcriber,checker
fc9f2c52…,balance_sheet,131,2024-12-31,instant,10.537.019.113.380,148,<người chép>,<người kiểm>
```

2. **Viết lại phần đo.**  
   - Ghép ô IR với gold theo `(statement, code, period_end)`. Kỳ của ô lấy từ tiêu đề cột (R4, bước 2).  
   - Báo bốn số: ô đúng, ô sai giá trị, ô thiếu, ô thừa.  
   - `gold_accuracy` \= số ô đúng / số ô gold.  
3. **Thêm phép so chéo kỳ giữa hai bản thành kiểm tra tự động** (KNOWHOW 7.4, mục 7).  
   - Cột năm trước của bản N phải bằng cột năm nay của bản N−1.  
   - Nếu lệch, gắn `CROSS_PERIOD_MISMATCH` để người duyệt xác định đó là lỗi đọc hay báo cáo được trình bày lại (UC18 A1).  
4. **Đổi tên phép so Poppler thành `tokenization_agreement`.** Không dùng nó làm số đo độ chính xác.

**Xong khi:**

- Có gold set chép tay cho FPT 2024 và 2025, đã đối chiếu giữa hai người.  
- Có `gold_accuracy` cho từng bản.  
- Chạy lại E4 thì phần đo mới **báo lỗi**.

---

### R4. Chưa xử lý được BCTC scan, TT99, BCTC phát hành riêng và ngân hàng 🔴

**Vấn đề**

Theo F01 và KNOWHOW, nguồn số liệu chính là file BCTC của 10 mã, trải TT200, TT99 và mẫu ngân hàng TT49. Hai PDF mẫu đều là báo cáo thường niên FPT có lớp text. Với các trường hợp còn lại, đường xử lý bị chặn ở nhiều chỗ:

| Chỗ chặn | Vị trí | Hệ quả |
| :---- | :---- | :---- |
| Phân loại trang chỉ xét **dòng đầu** | `financialContent.py:58–59` | Trang BCTC thường mở đầu bằng tên công ty và mã mẫu, nên không được nhận |
| Không có tiêu đề TT99 "Báo cáo tình hình tài chính" | `financialContent.py:60–77` | BCTC năm 2026 vẫn không được nhận dù đã sửa luật dòng đầu |
| Bảng BCTC chỉ được dựng cho trang có lớp text | `buildDocumentIr.py:617–618` | Trang scan chỉ còn bảng Markdown của Gemini, và chỉ khi trang đã được phân loại |
| Cột kỳ phải có năm dạng 20xx | `_accounting_period_year`; `_coded_statement_table`, dòng 134 | "Số cuối kỳ", "Kỳ này", "31.12.2025" bị bỏ qua |
| Template TT200 áp cho mọi file | `evaluate_accounting` | Ở TT99, mã 270 là "Tài sản dài hạn khác", nên luật `270 = 100 + 200` báo sai |
| Bắt buộc có mã dòng và mỗi ô số đúng 1 từ | `_coded_statement_table`, dòng 144, 168 | Mẫu ngân hàng không có cột Mã số nên không đọc được |
| Trang không thuộc chủ đề FPT nào và không phải BCTC thì bị bỏ | `buildDocumentIr.py:628–633` | PDF của công ty khác có thể không sinh ra IR nào |

&nbsp;

**Bằng chứng**

E5: cả 3 trang báo cáo chính của bản scan TT99 bị phân loại `None`. Phần đọc bảng Markdown vẫn dựng đúng 31, 22 và 19 dòng. Phần còn thiếu chủ yếu là phân loại trang, gán kỳ cho cột và chọn template.

**Giải pháp**

1. **Phân loại trang theo tiêu đề trong 10 dòng đầu.** Đoạn dưới đã chạy thử:  
   - Trên 145 trang BCTC của hai báo cáo thường niên, kết quả không đổi so với bộ phân loại hiện tại, nên không có trang nào bị phân loại sai thêm.  
   - Trên bản scan TT99, nhận đúng trang 7–8 là CĐKT và trang 9 là KQKD.

TITLES \= \[

&nbsp;&nbsp;&nbsp;&nbsp;(r"^bao cao (kiem toan|(ket qua cong tac )?soat xet)", "auditor\_report"),

&nbsp;&nbsp;&nbsp;&nbsp;(r"^(bang can doi ke toan|bao cao tinh hinh tai chinh)\\b", "balance\_sheet"),

&nbsp;&nbsp;&nbsp;&nbsp;(r"^bao cao ket qua (hoat dong )?kinh doanh\\b", "income\_statement"),

&nbsp;&nbsp;&nbsp;&nbsp;(r"^bao cao luu chuyen tien te\\b", "cash\_flow"),

&nbsp;&nbsp;&nbsp;&nbsp;(r"^thuyet minh bao cao tai chinh\\b", "notes"),

&nbsp;&nbsp;&nbsp;&nbsp;(r"^thong tin ve doanh nghiep\\b", "company\_information"),

&nbsp;&nbsp;&nbsp;&nbsp;(r"^bao cao cua ban (tong )?giam doc\\b", "other"),

\]

&nbsp;

def classify(text: str, max\_lines: int \= 10\) \-\> str | None:

&nbsp;&nbsp;&nbsp;&nbsp;lines \= \[\_plain(l.strip()).lstrip("\#\*| ") for l in text.splitlines() if l.strip()\]\[:max\_lines\]

&nbsp;&nbsp;&nbsp;&nbsp;for line in lines:

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;for pattern, page\_class in TITLES:

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if re.search(pattern, line):

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return page\_class

&nbsp;&nbsp;&nbsp;&nbsp;return None

- Mẫu "soát xét" (BCTC giữa niên độ) chưa kiểm trên file thật.  
  - Trang tiếp nối không có tiêu đề thì thừa hưởng loại của trang liền trước, nếu cả hai nằm trong phần BCTC. Ví dụ: trang 6 của bản scan, "Kết luận của Kiểm toán viên".  
  - Chỉ cắt 22% lề trái khi đã nhận diện được sidebar (R2, bước 4).  
2. **Gán kỳ cho từng cột** dựa vào tiêu đề cột và dòng ngày dưới tiêu đề báo cáo (KNOWHOW 8.4):

| Tiêu đề cột | `period_end` | `period_type` | Vai trò |
| :---- | :---- | :---- | :---- |
| "2024" (CĐKT) | 31/12/2024 | instant | theo năm trong tiêu đề |
| "Số cuối kỳ" | ngày trong dòng "TẠI NGÀY 30 THÁNG 6 NĂM 2026" | instant | kỳ hiện tại |
| "Số đầu kỳ" | ngày đầu năm tài chính | instant | kỳ so sánh |
| "Kỳ này", "Kỳ trước" | lấy từ dòng "KỲ KẾ TOÁN 6 THÁNG KẾT THÚC NGÀY…" | duration | kỳ hiện tại / kỳ so sánh |
| "31.12.2025" (ngân hàng) | 31/12/2025 | instant | theo ngày |

Thay `_accounting_period_year` bằng hàm trả về bộ ba (`period_end`, `period_type`, vai trò). Dùng bộ ba này làm khoá trong `evaluate_accounting`.

3. **Nhận diện thông tư (việc B1) trước khi kiểm đẳng thức.**  
   - Dùng các tín hiệu ở KNOWHOW 8.7: tên báo cáo, mã mẫu, mã Tổng tài sản (270 hay 280), năm tài chính.  
   - Chọn template theo cặp (thông tư, mẫu).  
   - Không xác định được thì gắn `TEMPLATE_UNKNOWN` và không chạy đẳng thức.  
4. **Cho bảng Markdown của Gemini vào cùng nhánh kiểm tra,** với `bbox = null` và có ghi nguồn. Về sau đổi schema Gemini để trả về `rows` có cấu trúc (việc A4).  
5. **Ngân hàng** (kế hoạch gốc xếp vào Sprint 4):  
   - Trong Sprint 3, chạy ít nhất 1 BCTC của VCB hoặc BID qua bộ phân loại và parser.  
   - Ghi lại các chỗ hỏng, để ước lượng công sức cho việc khoá dòng theo đường dẫn kiểu A›III›1.

**Xong khi:** cả ba file mẫu dưới đây đều được phân loại đúng, có bảng và chạy đẳng thức với đúng template:

- 1 BCTC phát hành riêng theo TT200, có lớp text;  
- `bctc/bctc_fpt_2026.pdf` (TT99, scan);  
- 1 BCTC ngân hàng. Với file này, tối thiểu phải phân loại đúng và có danh sách chỗ hỏng.

---

### R5. Đẳng thức chỉ kiểm dòng tổng 🟡

**Vấn đề**

- **Luật chỉ có ở dòng tổng.** Theo `table/index.json`, template `vn_nonbank_b01_b02_b03_v1` có luật cho 18 dòng cha, cộng 7 luật chéo báo cáo:  
  - CĐKT: 100, 200, 270, 300, 400, 440;  
  - KQKD: 10–60;  
  - LCTT: 08, 20, 30, 40, 50, 70\.  
- **Dòng chi tiết không được kiểm.** Các dòng tổng trung gian như 110, 130, 140, 220, 410 chỉ xuất hiện trong luật với vai trò dòng con. Vì vậy các dòng chi tiết bên dưới chúng không thuộc luật nào:  
  - ít nhất 60/83 dòng CĐKT mỗi bản;  
  - trong đó có 131 (phải thu khách hàng), 141 (hàng tồn kho), 421a/421b (LNST chưa phân phối), là những dòng hay được map sang chỉ tiêu.  
- **KQKD thiếu luật `60 = 61 + 62`.**  
  - Dòng 61 (LNST của cổ đông công ty mẹ), cơ sở để tính EPS và ROE, không được kiểm.  
  - EPS (dòng 70, 71\) cũng không được kiểm.  
- **So với POC trong KNOWHOW:** POC ở mục 5 đã dùng 14 luật chỉ cho phần tài sản của một trang. Vì vậy kết quả "43/43 đạt" phải đọc cùng độ phủ.

**Bằng chứng**

- Danh sách luật lấy từ `table/index.json` của cả hai bản.  
- E7: EPS 2024 lệch giữa hai bản mà không có cờ nào.

**Giải pháp**

1. **Thêm luật cho mọi dòng tổng có dòng con,** theo phụ lục mẫu biểu TT200/TT202. Ví dụ với CĐKT hợp nhất TT202:

   - `110 = 111 + 112`  
   - `120 = 121 + 122 + 123`  
   - `130 = 131 + 132 + … + 137 + 139`  
   - `140 = 141 + 149`  
   - `220 = 221 + 224 + 227`, `221 = 222 + 223`  
   - `410 = 411 + … + 421 + 422 + 429`, `421 = 421a + 421b`  
   - KQKD: `60 = 61 + 62`

   Đánh dấu `is_memo` cho các dòng "trong đó", ví dụ 411a và 23\.

2. **Kiểm luật mới trên cả hai bản FPT.** Mọi luật phải đạt. Luật nào không đạt nghĩa là template sai hoặc dữ liệu sai.

3. **Thêm kiểm tra mềm:**

   - EPS ≈ LNST của cổ đông công ty mẹ / số cổ phiếu bình quân (KNOWHOW 7.4, mục 9);  
   - phép so chéo hai bản ở R3.  
4. **Ghi độ phủ vào `table/index.json`:** `cells_protected` (số ô thuộc ít nhất một luật) và `cells_total`, đặt cạnh số luật đạt.

**Xong khi:**

- ít nhất 95% ô có mã được ít nhất một luật bảo vệ;  
- có luật `60 = 61 + 62`;  
- cả hai bản FPT đạt toàn bộ luật.

---

### R6. Parser số nhận chuỗi sai định dạng 🟡

**Vấn đề**

- **`_parse_accounting_number` không kiểm nhóm 3 chữ số.** Hàm bỏ mọi dấu `.` rồi đổi `,` thành dấu thập phân.  
- **Regex chọn ô ở `_coded_statement_table` dòng 170 cũng quá rộng.** Mẫu `\(?[\d.]+\)?` nhận mọi chuỗi gồm chữ số và dấu chấm.  
- **Lỗi chưa lộ, nhưng sẽ lộ khi có bảng OCR.** Hai PDF mẫu có lớp text sạch nên chưa gặp lỗi này. Khi bảng từ Gemini hoặc Tesseract đi vào nhánh này (R4), giá trị sai ở dòng chi tiết sẽ lọt qua, vì không có luật nào kiểm dòng đó (R5).  
- **Đây là kiểm tra cứng số 1 trong KNOWHOW 7.4** (`BAD_NUMBER_FORMAT`).

**Bằng chứng**

E6: cả ba chuỗi lỗi OCR thật trong KNOWHOW 5.3 đều được nhận thành số sai.

**Giải pháp**

Thay bằng hàm dưới đây. Hàm đã chạy thử với các chuỗi trong KNOWHOW 5.3 và E7:

```py
MONEY = re.compile(r"\(?-?\d{1,3}(?:[.,]\d{3})*\)?")

def parse_money(raw: str) -> tuple[Decimal | None, str | None]:
    """Ô tiền trong bảng BCTC: số nguyên, '.' hoặc ',' ngăn nghìn, '(x)' là âm."""
    text = raw.strip().replace(" ", "")
    if text in ("-", "–", "—"):
        return Decimal(0), "PRINTED_DASH"
    if not MONEY.fullmatch(text) or text.startswith("(") != text.endswith(")"):
        return None, "BAD_NUMBER_FORMAT"
    value = Decimal(re.sub(r"\D", "", text))
    return (-value if text.startswith(("(", "-")) else value), None
```

&nbsp;

| Chuỗi | Kết quả |
| :---- | :---- |
| `(16.932.187.108)` | −16.932.187.108 |
| `3,405.535.984` | 3.405.535.984 (tự sửa dấu phân cách lẫn lộn) |
| `3.451.002.5587` | `BAD_NUMBER_FORMAT` |
| `(280.683.727.283` | `BAD_NUMBER_FORMAT` |
| `4.944` (EPS) | 4.944 đồng |

&nbsp;

**Lưu ý khi áp dụng:**

- **Kiểm định dạng không bắt được lỗi sai một chữ số.** Ví dụ `2.773,180.700` (đúng là 2.773.160.700) vẫn qua. Loại lỗi này chỉ đẳng thức bắt được, nên R5 càng quan trọng.  
- **Dùng chung regex cho bước chọn ô** trong `_coded_statement_table`. Ô sai định dạng thì gắn cờ cho ô và đưa vào `needs_review`, không `raise` làm hỏng cả trang.  
- **Tỉ lệ, phần trăm và số thập phân cần parser riêng** (KNOWHOW 8.2).

**Xong khi:** có unit test cho các chuỗi trong bảng trên và mọi test đều đạt.

---

### R7. Test router hỏng; phần dựng IR không có test 🟡

**Vấn đề**

- **`test_main.test_routes_and_output_shape` lỗi vì ba lý do:**  
  - Cache Tesseract giả thiếu `wordItems`, nên `main.py:88–89` bỏ cache và gọi Tesseract thật trên một file PNG giả.  
  - `argparse.Namespace` trong test dùng `agy_concurrency`, `agy_timeout`, trong khi code đọc `gemini_concurrency`, `gemini_timeout`.  
  - Test kỳ vọng `summary["cache"]` có 2 khoá, nhưng code nay ghi 3\.  
- **Hai test router còn lại bị bỏ qua,** vì trỏ tới `parents[5] / "bctc_fpt_2026"`, đường dẫn của bản TypeScript cũ.  
- **Khoảng 2.000 dòng không có test nào:** `buildDocumentIr.py`, `financialContent.py`, `reportContent.py`, `evaluateDocumentIr.py`, `auditDocumentIr.py`. 8 test đang đạt đều thuộc phần schema và phần đọc TSV của Tesseract.

**Bằng chứng**

E1: 11 test, trong đó 8 đạt, 1 lỗi, 2 bỏ qua.

**Giải pháp**

1. **Sửa `test_main.py`.** Đã chạy thử trên bản sao: 3 test, 1 đạt, 2 bỏ qua.

```py
cfg = argparse.Namespace(..., gemini_concurrency=2, gemini_timeout=300,
                         openrouter_model="x", ...)                 # thay agy_*
tess = {..., "words": 6, "wordItems": [], "meanConf": 95, ...}     # thêm wordItems
with ..., patch.dict(os.environ, {"GEMINI_API_KEY": "test"}):
    os.environ.pop("OPENROUTER_API_KEY", None)
    main.process_pdf(pdf, cfg, {})
self.assertEqual(summary["cache"], {"tesseractHits": 1, "geminiHits": 1, "openrouterHits": 0})
```

2. **Sửa hai test bị bỏ qua:** chép `pages.jsonl` và `text/` của `bctc_fpt_2026` (lấy từ `G2/ocr_router_out/`) vào `tests/fixtures/bctc_fpt_2026/`, rồi trỏ test vào đó.

3. **Thêm test hồi quy:**

   - parser so với fixture 2024 (E3, R2);  
   - phân loại trang trên text Gemini của bản scan TT99 (E5, R4);  
   - `parse_money` (R6);  
   - `evaluate_accounting` với một template nhỏ 3–4 luật;  
   - phép so chéo hai bản (E7);  
   - dùng E4 làm test âm cho phần đo gold mới (R3): đảo cột thì độ chính xác phải giảm.

   Code mẫu cho E3–E7 có ở phụ lục.

**Xong khi:** `python -m unittest discover -s tests` chạy hết, không lỗi, không test nào bị bỏ qua.

---

### R8. OpenRouter dự phòng chưa từng chạy 🟡

**Vấn đề**

- **Nhánh này chưa từng chạy.** `summary.json` của cả hai bản ghi `openrouterApi.calls = 0`, và không có thư mục `.cache/openrouter`.  
- **README mô tả một nhánh không có trong code.** README mục 5 viết rằng model `:free` "dùng JSON mode rồi kiểm tra cấu trúc trong Python". Thực tế code luôn gửi `json_schema` với `strict: True` (`model.py:197–198`).  
- **Lời gọi có thể bị từ chối.** Chế độ strict của OpenAI yêu cầu `additionalProperties: false` ở mọi object, mà `GEMINI_SCHEMA` không có. Vì vậy model mặc định `openai/gpt-4o-mini` có thể từ chối. **Chưa kiểm** vì không có key.  
- **Khó biết vì sao bị từ chối.** Lỗi HTTP chỉ giữ mã và lý do, phần body bị bỏ.  
- **Nằm ngoài stack đã duyệt.** Model mặc định không phải Gemini, trong khi Proposal Table 18 chỉ duyệt Gemini.  
- **Trang đọc bằng model dự phòng không có cờ riêng.** Trang này đi qua cùng phép so chéo như trang Gemini.

**Giải pháp**

1. **Nhóm và mentor quyết định có giữ nhánh dự phòng hay không,** vì nó nằm ngoài stack đã duyệt và gửi ảnh trang cho một nhà cung cấp khác.  
2. **Nếu giữ:**  
   - Dùng schema riêng cho OpenRouter:

```py
OPENROUTER_SCHEMA = copy.deepcopy(GEMINI_SCHEMA)
OPENROUTER_SCHEMA["additionalProperties"] = False
OPENROUTER_SCHEMA["properties"]["pages"]["items"]["additionalProperties"] = False
```

   - Ghi body lỗi HTTP:

```py
message = f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:500]}"
```

   - Thêm cờ `FALLBACK_MODEL` và cho cờ này đẩy trang sang REVIEW.  
   - Với model `:free`: viết nhánh `response_format = {"type": "json_object"}`; đoạn kiểm cấu trúc đã có sẵn trong `_call_openrouter`. Nếu không viết nhánh này thì xoá đoạn mô tả khỏi README.  
3. **Nếu bỏ:** xoá `_call_openrouter`, `openrouter_transcribe`, engine `OPENROUTER` trong schema và phần README liên quan.

**Xong khi:**

- Nếu bỏ: code, schema và README không còn nhánh OpenRouter.  
- Nếu giữ: có ít nhất một lần gọi thật thành công, có file trong `.cache/openrouter`, và trang dự phòng mang cờ `FALLBACK_MODEL`.

---

### R9. README ghi "xong" ở nhiều mục chưa xong 🟡

**Vấn đề và cách sửa**

| Mục | README đang ghi | Thực tế | Sửa thành |
| :---- | :---- | :---- | :---- |
| G3, A7 | "Phân loại chuẩn xác toàn bộ các trang" | Bản 2024 phân loại bằng bảng số trang (R2). TT99 và BCTC phát hành riêng không được nhận (R4) | 🟡 Đúng trên 2 PDF FPT |
| A2, C1 | ✅ | Chỉ có trên 2 PDF FPT có lớp text. Đẳng thức chỉ phủ dòng tổng (R5) | 🟡 |
| E2 | "Chặn trùng theo SHA-256 ✅" | Mới có cache ảnh trang. Kế hoạch E2 là chặn trùng file trước OCR, retry, giới hạn đồng thời, gắn `ingestion_jobs` | ⏳ |
| E3 | "Đưa cấu hình vào hệ thống ✅" | Cấu hình đang ở `.env` và CLI. Kế hoạch E3 là `system_configs`/`config_versions` | ⏳ |
| Q4, Q5 | "ĐÃ CHỐT XONG" | Theo README gốc mục 3.3, hai câu này cần nhóm và mentor chốt. Q5 hỏi nơi lưu sự kiện CBTT; việc bỏ khỏi phạm vi báo cáo thường niên không trả lời câu hỏi đó | "Đề xuất, chờ nhóm và mentor chốt" |
| Mục 3 | "Chạy mượt mà trên Windows/Linux" | Không chạy được ở đâu (R1). Trên Windows, nếu thiếu ImageMagick thì trang xoay không được xoay lại, chỉ in cảnh báo | Ghi rõ các phụ thuộc: poppler, Tesseract `vie`, template; xoay ảnh bằng Pillow (R11) |
| Mục 3 | "Đột phá 2025: tự động định vị trang theo nội dung" | Dựa vào màu xanh và cụm từ của mục lục bên FPT | "Định vị theo mục lục bên của FPT; chưa kiểm trên công ty khác" |
| Đầu README | `README_M.md` là "kế hoạch gốc ngày 06/10" | 4 dòng đã bị sửa so với bản gốc (A1, A2, mốc S2, ví dụ IR). Ví dụ A2 nay ghi "chốt dùng pdfplumber" | Khôi phục đúng bản gốc (`03_Design/Data_Pipeline/poc/ocr-router/README.md`) hoặc thay bằng link |

&nbsp;

**Nguyên tắc:** chỉ ghi ✅ khi có lệnh chạy được và output kiểm được. Số liệu lấy từ override ghi riêng (R2).

**Xong khi:** mọi mục ✅ trong README đều kèm lệnh chạy và đường dẫn tới output.

---

### R10. Công sức lệch khỏi DoD Sprint 2 🟡

**Vấn đề**

- **DoD Sprint 2** (F01; README gốc mục 3.4): đo độ chính xác trích xuất bảng BCTC trên gold set, mỗi ngành 1 công ty × 2 kỳ. Hai ngành là công nghệ và ngân hàng.  
- **Phần lớn công sức sprint lại dồn vào nội dung báo cáo thường niên:** 6 chủ đề, 15 bảng thường niên, KPI, lọc mục lục bên.  
  - `reportContent.py` dài 453 dòng, phần lớn là hằng số riêng cho FPT.  
  - Các phần này có ích cho nhánh RAG, nhưng không nằm trên đường tới DoD.  
- **Trong khi đó, ba việc trên đường tới DoD chưa bắt đầu:**  
  - gold set: 0 ô được duyệt;  
  - ngân hàng: chưa có mẫu nào;  
  - BCTC scan (R4).

**Giải pháp**

1. Tạm dừng phần mở rộng nội dung báo cáo thường niên (`reportContent.py`) cho đến khi đạt DoD.  
2. Trước 11/10, dồn người vào gold set FPT (R3).  
3. Báo mentor đúng hiện trạng:  
   - phần công nghệ: 1 công ty × 2 kỳ, có số đo nếu xong R3;  
   - phần ngân hàng: dời sang Sprint 3, theo kế hoạch ở R4 bước 5\.  
4. Lấy ngay 1 BCTC ngân hàng trong phạm vi (VCB hoặc BID) để bắt đầu khảo sát.

**Xong khi:**

- mentor đã duyệt phạm vi DoD S2 và lịch cho phần ngân hàng;  
- có ít nhất 1 file BCTC ngân hàng trong kho dữ liệu.

---

### R11. Code và repo cần dọn 🟢

| Vấn đề | Vị trí | Giải pháp |
| :---- | :---- | :---- |
| Cờ `--build-ir` import module đã chuyển vào `_archive/`, nên luôn lỗi | `main.py:257–258, 269–289` | Xoá cờ và phần xử lý của nó |
| Alias camelCase còn sót từ bản TypeScript | `util.py:106–120`, `textLayer.py:42–43`, `render.py:46`, `crossCheck.py:58–60` | Xoá |
| Hàm bị lặp: `_plain` ở 3 module; `_word_box` và `_printed_lines` mỗi hàm ở 2 module | `buildDocumentIr`, `reportContent`, `financialContent` | Gộp vào `src/text_utils.py` |
| Batch Gemini lỗi (sai key, hết quota) bị thử lại từng trang, thành 1 \+ N lần gọi đều lỗi | `model.py:157–159` | Không tách batch khi lỗi là `google.genai.errors.ClientError` (4xx). Chỉ tách khi lần gọi thành công nhưng thiếu trang, hoặc JSON trả về bị hỏng |
| Khoá cache Gemini không gồm nội dung prompt, nên sửa prompt mà quên tăng version thì vẫn dùng kết quả cũ | `model.py:132` | Thêm 8 ký tự đầu của `sha256(SYSTEM_INSTRUCTION + json.dumps(GEMINI_SCHEMA))` vào tên file cache |
| Ảnh render được dùng lại dù đã đổi `--long-side` | `render.py:20–21` | Đưa `long_side` vào tên file, ví dụ `p-001.3508.png` |
| Xoay ảnh cần `sips` (chỉ có trên macOS) hoặc ImageMagick | `render.py:36–42` | Dùng Pillow (đã có sẵn vì pdfplumber phụ thuộc vào nó): `Image.open(raw).rotate(-rotation, expand=True).save(upright)`. Dấu âm để xoay theo chiều kim đồng hồ giống `sips`. **Chưa kiểm:** cần thử trên file xoay 90° (`bctc/20260925 - FPT - Bao cao ket qua phat hanh…pdf`), vì POC mới thử trang xoay 180° |
| Repo commit 2 PDF (23 MB), 891 file output và thư mục `tmp/pdfs/`, tổng khoảng 50 MB | gốc repo | Đưa PDF vào Git LFS hoặc release asset. Thêm `ocr_router_out/*/work/` và `tmp/` vào `.gitignore`. Chỉ giữ một bộ output tham chiếu nhỏ trong `tests/fixtures/`. Không viết lại lịch sử git nếu nhóm chưa thống nhất |

&nbsp;

**Xong khi:** các mục trong bảng đã sửa, và test ở R7 vẫn đạt.

---

## 5\. Kế hoạch thực hiện

Ước tính là của reviewer. Cột "Người làm" để nhóm điền.

| Thứ tự | Việc | Vấn đề | Ước tính | Hạn | Người làm |
| :---- | :---- | :---- | :---- | :---- | :---- |
| 1 | Commit template, sửa đường dẫn, thêm smoke test | R1 | 2 giờ | 10/10 |  |
| 2 | Sửa 3 test router; thêm test parser so với fixture | R7, R2 | 2 giờ | 10/10 |  |
| 3 | Bỏ nhánh SHA-256 cho BCTC 2024 | R2 | 2 giờ | 10/10 |  |
| 4 | Gold set FPT 2024 và 2025: hai người chép tay; viết lại phần đo; thêm so chéo hai bản | R3 | 1 ngày × 2 người | 11/10 |  |
| 5 | Cập nhật README và WorkLog; báo mentor hiện trạng DoD | R9, R10 | 2 giờ | 11/10 |  |
| 6 | Phân loại trang theo tiêu đề, gán kỳ cho cột, nhận diện thông tư | R4 | 2–3 ngày | Sprint 3, tuần 1 |  |
| 7 | Thay parser số bằng `parse_money`; cây luật đầy đủ; đo độ phủ | R5, R6 | 1–2 ngày | Sprint 3, tuần 1 |  |
| 8 | Chạy thử 1 BCTC ngân hàng, liệt kê chỗ hỏng | R4, R10 | 0,5 ngày | Sprint 3, tuần 1 |  |
| 9 | Quyết định về OpenRouter, sửa theo quyết định | R8 | 0,5 ngày | Sprint 3 |  |
| 10 | Dọn code và repo | R11 | 1 ngày | Sprint 3 |  |

&nbsp;

Nếu việc 4 không kịp trước 11/10, báo mentor rằng S2 mới đạt phần công nghệ, còn phần ngân hàng dời sang S3.

---

## 6\. Những phần nên giữ nguyên khi sửa

- **Lớp text trước, OCR sau.** 211/215 trang (bản 2024\) và 230/232 trang (bản 2025\) được đọc thẳng, không tốn lượt gọi API. Tesseract chạy trước; Gemini chỉ được gọi khi cần.  
- **Parser `_coded_statement_table`.** Chạy đúng trên cả hai bản FPT (E3), có `bbox` cho từng ô và mã dòng, đủ cho locator FR11 với PDF có lớp text. Nên mở rộng parser này, không viết lại.  
- **Hợp đồng IR chặt.**  
  - Schema đóng; validator kiểm quan hệ giữa các trường: trùng id, ô không có cột tương ứng, bbox ngược chiều.  
  - Đã áp dụng các góp ý chính của review schema ngày 06/10 (`raw: null`; `source` và `page_size` bắt buộc; `votes`). 8 test đang đạt.  
- **Truy vết đầy đủ.** Có `document_sha256`, `image_sha256`, `prompt_version`; `printed_page` được tách riêng khỏi số trang PDF.  
- **Không giấu dữ liệu thiếu.** Luật thiếu dòng được ghi vào `arithmetic_checks_skipped`. Ô lỗi được ghi vào `needs_review` thay vì bị bỏ, như ô KQKD 52 ở E7.  
- **Gemini đúng tinh thần PA C.** Prompt yêu cầu chép nguyên văn, không tính toán; `temperature` bằng 0; cache theo ảnh và version.  
- **An toàn khoá API.** `.env` nằm trong `.gitignore`; thông báo lỗi che khoá. Đã quét lịch sử commit, không thấy khoá nào.  
- **Tự đánh giá trung thực.** README và WorkLog ghi rõ 278/278 là đồng thuận giữa hai bộ đọc, `gold_accuracy` đang là `null`, S2 chưa xong.

---

## Phụ lục: lệnh tái lập thí nghiệm

Chạy từ thư mục `FindMind/FinMind/`. Các lệnh không ghi gì vào repo.

**E3.** Parser tổng quát so với fixture FPT 2024:

```sh
python3 - <<'EOF'
import sys; sys.path.insert(0, "src")
import pdfplumber
from financialContent import _coded_statement_table, reviewed_statement_tables
from reportContent import FPT_2024_SHA256
kinds = {**{p: "balance_sheet" for p in range(148, 153)}, 153: "income_statement",
         154: "income_statement", 155: "cash_flow", 156: "cash_flow"}
cells = lambda t: {(r["code"], c): v["raw"] for r in t["rows"] if r["code"]
                   for c, v in r["cells"].items()}
pdf = pdfplumber.open("FPT_2024_498332 (1).pdf")
total = same = 0
for p, kind in kinds.items():
    fixture = cells(reviewed_statement_tables(p, FPT_2024_SHA256)[0])
    parsed = cells(_coded_statement_table(pdf.pages[p - 1], kind)[0])
    total += len(fixture); same += sum(parsed.get(k) == v for k, v in fixture.items())
print(same, "/", total)   # 278 / 278
EOF
```

&nbsp;

**E4.** Đảo cột và tráo dòng, rồi chạy phép đo ô:

```sh
T=$(mktemp -d); cp -R "ocr_router_out/FPT_2024_498332 (1)/annual_ir" "$T/ir"
rm -f "$T"/ir/gold_candidates.json "$T"/ir/cell_evaluation.json
python3 - "$T/ir/table/p-148.ir.json" <<'EOF'
import json, sys
path = sys.argv[1]; page = json.load(open(path))
rows = next(b for b in page["blocks"] if b["type"] == "table")["rows"]
r110, r111 = rows[1], rows[2]
r110["cells"]["c1"], r110["cells"]["c2"] = r110["cells"]["c2"], r110["cells"]["c1"]   # đảo cột
r110["cells"]["c1"], r111["cells"]["c1"] = r111["cells"]["c1"], r110["cells"]["c1"]   # tráo dòng
json.dump(page, open(path, "w"), ensure_ascii=False)
EOF
(cd src && python3 evaluateDocumentIr.py "../FPT_2024_498332 (1).pdf" --ir-dir "$T/ir" | head -8)
```

&nbsp;

**E5.** Text Gemini của BCTC scan TT99 qua bộ phân loại và parser bảng:

```sh
python3 - <<'EOF'
import sys; sys.path.insert(0, "src")
from financialContent import financial_page_class
from buildDocumentIr import _text_blocks
for p in (7, 8, 9):
    text = open(f"../../ocr_router_out/bctc_fpt_2026/text/p-{p:03d}.txt", encoding="utf-8").read()
    tables = [b for b in _text_blocks(text, p) if b["type"] == "table"]
    print(p, financial_page_class(p, None, "other-pdf", text), [len(t["rows"]) for t in tables])
EOF
```

&nbsp;

**E6.** Parser số với chuỗi lỗi OCR thật:

```sh
python3 -c 'import sys; sys.path.insert(0, "src")
from financialContent import _parse_accounting_number as parse
for s in ("3,405.535.984", "3.451.002.5587", "2.773,180.700"): print(s, "->", parse(s))'
```

&nbsp;

**E7.** So các ô năm 2024 giữa hai bản:

```sh
python3 - <<'EOF'
import glob, json
def cells(doc):
    out = {}
    for f in glob.glob(f"ocr_router_out/{doc}/annual_ir/table/p-*.ir.json"):
        page = json.load(open(f))
        for b in page["blocks"]:
            if b["type"] != "table" or page["page_class"] not in ("balance_sheet", "income_statement", "cash_flow"):
                continue
            year = {c["key"]: [t for t in " ".join(c["header_lines"]).split() if t.startswith("20")][-1]
                    for c in b["columns"]}
            for r in b["rows"]:
                for k, v in r["cells"].items():
                    if r["code"]: out[page["page_class"], r["code"], year[k]] = v["raw"]
    return out
a, b = cells("FPT_2024_498332 (1)"), cells("BCTN_2025")
common = [k for k in a if k[2] == "2024" and k in b]
print(len(common), [(k, a[k], b[k]) for k in common if a[k] != b[k]])
EOF
```

&nbsp;