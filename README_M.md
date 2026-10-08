# POC: OCR router cho BCTC và báo cáo thường niên

- **Cập nhật:** 06/10/2026
- **Trạng thái:** POC chạy được trên 2 file mẫu. Chưa phải thiết kế đã chốt.
- **Tài liệu liên quan:**
  - `../../KNOWHOW_ChuanHoa_BCTC_OCR_20261002.md`: chuẩn hoá, trọng tài, đề xuất ERD (mục 7, 8, 12)
  - `../../REVIEW_Pipeline_OCR_HanhChinh_v6_20261005.md`: pipeline văn bản hành chính, trích xuất sự kiện (mục 8)
  - `../../../template/`: template chỉ số v1.2.0 và review ngày 06/10/2026
  - `../../../Database/ERD_v2.dbml`

README có ba phần:

1. [Chạy demo](#1-chạy-demo)
2. [POC có gì](#2-poc-có-gì)
3. [Từ POC thành sản phẩm](#3-từ-poc-thành-sản-phẩm)

---

## 1. Chạy demo

### 1.1 Cài đặt (macOS)

| Thành phần | Lệnh / ghi chú |
| --- | --- |
| Node ≥ 23.6 | Chạy `.ts` trực tiếp, không cần build. Máy dev đang dùng Node 25.9 |
| poppler | `brew install poppler` (`pdfinfo`, `pdftotext`, `pdftoppm`) |
| Tesseract + model tiếng Việt | `brew install tesseract`, rồi tải `vie` bản best vào `G2/tessdata_best/` (lệnh ở dưới) |
| Antigravity CLI | `agy` đã đăng nhập. Kiểm tra bằng `agy models`. Chỉ cần khi gọi Gemini |

```bash
cd G2
mkdir -p tessdata_best
curl -L -o tessdata_best/vie.traineddata https://github.com/tesseract-ocr/tessdata_best/raw/main/vie.traineddata
cp /opt/homebrew/share/tessdata/{osd,eng}.traineddata tessdata_best/
```

POC tự chọn thư mục tessdata đầu tiên thật sự có `vie.traineddata`, theo thứ tự `--tessdata`, `$TESSDATA_PREFIX`, `./tessdata_best`. `npm install` chỉ cần nếu muốn chạy `npm run typecheck`.

### 1.2 Ba kịch bản demo

Chạy từ thư mục `G2/`:

```bash
P=03_Design/Data_Pipeline/poc/ocr-router/src/main.ts

# A. PDF có lớp text (báo cáo thường niên FPT 2024, 215 trang): ~7 giây, không gọi Gemini
node $P bctc/FPT_2024_498332.pdf

# B. BCTC scan (FPT Online 2026), trang 6–9: đi đủ 3 tầng
#    ocr_router_out/.cache đã có kết quả của 4 trang này, nên chạy lại mất ~1 giây và không tốn quota
node $P bctc/bctc_fpt_2026.pdf --pages 6-9

# C. Chỉ lớp text + Tesseract, không tốn quota
node $P bctc/bctc_fpt_2026.pdf --gemini never

node $P --help
```

**Muốn gọi Gemini thật:** chọn trang chưa có trong cache (ví dụ `--pages 10-13`), hoặc xoá `ocr_router_out/.cache/gemini/`. Mỗi lần gọi `agy` gộp 4 trang, mất khoảng 80 giây.

### 1.3 Đọc output

Output ở `ocr_router_out/<tên file>/`:

| File | Nội dung |
| --- | --- |
| `summary.json` | Số trang theo tuyến và trạng thái, cờ, thời gian từng bước, số lần gọi và token của `agy`, cache hit |
| `pages.jsonl` | Mỗi trang một dòng: `route`, `status`, `flags`, `text`, chỉ số Tesseract, thông tin Gemini, `crossCheck` |
| `text/p-NNN.txt` | Text cuối của trang: bản Gemini nếu có, không thì bản Tesseract hoặc lớp text |
| `text/p-NNN.tess.txt` | Bản Tesseract của trang đã qua Gemini, để so |
| `work/` | Ảnh trang đã render |

**Nên xem trước:**

- `bctc_fpt_2026/text/p-007.txt`: bảng CĐKT do Gemini đọc. Mở cạnh `p-007.tess.txt` để thấy chỗ Tesseract sai.
- `bctc_fpt_2026/pages.jsonl`: trường `crossCheck.unverifiedNumbers`, và trang 6 có mã số con dấu bị gắn cờ.
- `FPT_2024_498332/text/p-148.txt`: trang CĐKT hợp nhất đọc thẳng từ lớp text.

---

## 2. POC có gì

### 2.1 Luồng xử lý

```
PDF ─► 1. Lớp text (pdftotext) ── đủ chữ, không ký tự lạ ──► xong, 0 đồng
          │ không có / lỗi
          ▼
       2. Render + tự xoay (OSD) + Tesseract vie (TSV, có độ tin cậy từng từ)
          │ trang bảng/nhiều số tiền, hoặc conf < 90, hoặc > 10% từ kém tin cậy
          ▼
       3. Gemini qua Antigravity CLI (agy), gộp 4 trang/lần gọi
          ▼
       4. So chéo Gemini với Tesseract: số khớp, độ giống chữ → OK | REVIEW
```

| File | Việc |
| --- | --- |
| `src/main.ts` | CLI, chọn tuyến cho từng trang, ghép kết quả, ghi output |
| `src/textLayer.ts` | Đọc lớp text một lần cho cả khoảng trang; kiểm tra ký tự lạ và lỗi mã hoá |
| `src/render.ts` | `pdftoppm` (cạnh dài 3508 px ≈ A4 300 DPI), Tesseract OSD, xoay bằng `sips`/`magick` |
| `src/tesseract.ts` | Tesseract `vie` xuất TSV, dựng lại text theo block/dòng, tính conf |
| `src/gemini.ts` | Gọi `agy -p --json-schema`, gộp trang, cache theo sha256 ảnh, gọi lại riêng trang bị thiếu |
| `src/crossCheck.ts` | So số (bỏ dấu phân cách) và độ giống chữ (bigram Dice, bỏ dấu tiếng Việt) |

### 2.2 Cơ chế giảm chi phí

| Cơ chế | Tác dụng |
| --- | --- |
| Đọc lớp text trước | PDF xuất từ phần mềm không cần OCR. FPT 2024: 211/215 trang đọc thẳng, cả file 7 giây |
| Tesseract trước Gemini | Miễn phí, 1–3 giây/trang. Trang chữ thường đọc tốt thì dừng ở đây |
| Chỉ gọi Gemini khi cần | Trang bảng hoặc nhiều số tiền luôn cần hai phiếu; trang chữ chỉ gọi khi Tesseract kém |
| Gộp 4 trang/lần gọi `agy` | Mỗi lần gọi có ~40k token system prompt của agent. Đo 05/10/2026: 1 trang/lần ≈ 43k token vào; 4 trang/lần ≈ 54k (≈ 13,6k/trang) |
| Cache theo sha256 ảnh | Chạy lại không tốn quota. Đổi prompt thì tăng `PROMPT_VERSION` trong `src/gemini.ts` |
| `--escalate-model` (tuỳ chọn) | Trang bảng có > 10% số lệch được gọi lại bằng model mạnh hơn |

### 2.3 Kết quả đo (05/10/2026)

| File | Trang | Tuyến | Thời gian | `agy` |
| --- | --- | --- | --- | --- |
| `FPT_2024_498332.pdf` (InDesign) | 215 | 211 lớp text, 4 Tesseract | 7,2 s | 0 lần gọi |
| `bctc_fpt_2026.pdf` (scan 100 DPI), trang 6–9 | 4 | 4 Tesseract + Gemini | 86 s (agy 79 s) | 1 lần gọi, 54k token vào, 5k ra |

Kiểm tay bằng đẳng thức kế toán trên bản Gemini (script chạy riêng, **chưa có trong POC**):

- Trang 7 (CĐKT): khớp **26/26** đẳng thức. Hai số lệch giữa hai engine đều do Tesseract đọc sai, đúng như gold set ở KNOWHOW mục 5.3.
- Trang 9 (KQKD): khớp **12/12**. Số lệch `51.665.149.452` (Tesseract đọc `51.865…`) và EPS `4.275` dưới con dấu đều do Tesseract sai.
- Trang 6 (kết luận kiểm toán): mã số trên con dấu chỉ Gemini đọc ra, và hai lần chạy cho hai giá trị khác nhau. Cờ `NUMBERS_UNVERIFIED` bắt đúng kiểu đoán số này.

### 2.4 Cờ

| Cờ | Ý nghĩa | Đẩy vào REVIEW |
| --- | --- | --- |
| `NUMBERS_UNVERIFIED` | Trang bảng: < 95% số của Gemini có trong bản Tesseract | có |
| `ENGINES_DISAGREE` | Độ giống chữ giữa hai engine < 0,6 | có |
| `GEMINI_UNREADABLE` | Gemini tự khai có chỗ không đọc được | có |
| `GEMINI_FAILED` | Gọi `agy` lỗi, đang dùng bản Tesseract | có |
| `LOW_CONF` | Chạy `--gemini never` và Tesseract kém | có |
| `TEXT_LAYER_BROKEN` | Có lớp text nhưng chứa ký tự lạ, nên phải OCR | không |
| `NEAR_EMPTY` | Trang gần như không có chữ (bìa, ảnh) | không |
| `ESCALATED` | Đã dùng bản của `--escalate-model` | không |

### 2.5 POC chưa làm được gì

| # | Thiếu | Hệ quả thấy được |
| --- | --- | --- |
| G1 | Output là text phẳng (Markdown hoặc plain), không có khối, bảng, dòng, ô | Không đưa thẳng vào DB được. Bảng của Gemini là Markdown, bảng của lớp text là text căn cột |
| G2 | Không loại header, footer, menu bên | Menu trái của báo cáo thường niên lẫn vào text ở **211/211** trang |
| G3 | Không phân loại trang (CĐKT, KQKD, LCTT, thuyết minh, văn xuôi, thư) | Không biết trang nào đi nhánh số liệu, trang nào đi nhánh RAG |
| G4 | Không có trọng tài đẳng thức | Cờ REVIEW đang báo quá tay: trên 4 trang thử, mọi số lệch trên trang bảng đều do Tesseract sai |
| G5 | Không chuẩn hoá số, đơn vị, kỳ, công ty, thông tư | Chưa ra được giá trị số, chưa gắn kỳ hay phạm vi |
| G6 | Không map dòng sang chỉ số của template | Chưa ra được `observations` |
| G7 | Gọi Gemini qua `agy` (CLI tương tác, quota tài khoản cá nhân) | Mỗi lần gọi tốn ~40k token system prompt, mất 12–80 giây, không có SLA |
| G8 | Ghi file, không ghi DB; ngưỡng chọn theo vài trang | Chưa có gold set để hiệu chỉnh |

---

## 3. Từ POC thành sản phẩm

### 3.1 Bức tranh dữ liệu

Dữ liệu chia làm bốn tầng. POC hiện mới tới giữa L1 và L2.

| Tầng | Chứa gì | Lưu ở đâu | Tình trạng |
| --- | --- | --- | --- |
| L0 File | PDF gốc, `sha256` | `documents` (ERD v2) | đã có trong ERD |
| L1 Raw | output gốc của từng engine (JSON Gemini, TSV Tesseract) | `raw_payloads` hoặc object storage | POC có cache, chưa có DB |
| **L2 Document IR** | khối, bảng, dòng, ô theo **một schema chung cho mọi engine** | **mới:** `page_extractions.ir` (jsonb) | **chưa có (G1)** |
| L3 Dữ liệu nghiệp vụ | số liệu, đoạn văn RAG, sự kiện | `observations`, `text_chunks`, `graph_extractions` | chưa có |

Ba nguồn định nghĩa cần khớp với nhau:

| Nguồn | Định nghĩa gì | Không định nghĩa gì |
| --- | --- | --- |
| **Template chỉ số** (`03_Design/template/`, v1.2.0, 226 chỉ số) | chỉ số là gì: `metric_id` (`common.total_assets`…), kiểu, đơn vị, `instant`/`duration`, chiều, chính sách thiếu dữ liệu. `db_storage` liệt kê ngữ cảnh bắt buộc của một fact | lấy số ở dòng nào của mẫu biểu nào; quan hệ cha–con giữa các dòng |
| **Mẫu biểu theo thông tư** (KNOWHOW mục 12.1: `statement_templates`, `template_lines`) | mã dòng của từng mẫu, dòng cha, dấu, thứ tự → map sang `metric_id` và sinh luật đẳng thức | định nghĩa chỉ số |
| **ERD v2** | bảng lưu: `metrics`, `financial_reports`, `observations`, `evidence`, `quarantine_records`… | các cột template yêu cầu (xem 3.4) |

Ví dụ một mã có hai nghĩa: Tổng tài sản là mã **270** trong FPT 2024 (TT202, `B 01 – DN/HN`) nhưng là mã **280** trong FPT Online 2026 (TT99). Cả hai đều phải map về `common.total_assets`. Vì vậy khóa map phải là (thông tư, mẫu, mã), không phải mã đơn thuần.

### 3.2 Việc cần làm theo luồng

Ưu tiên: 🔴 cần cho DoD Sprint 2/3 · 🟡 cần trước khi demo sản phẩm · 🟢 sau.

**A. Document IR và tách cấu trúc (giải quyết G1–G3)**

| # | Việc | Ưu tiên | Ghi chú |
| --- | --- | --- | --- |
| A1 | Chốt schema **IR v1** (JSON Schema + type): `blocks[]` gồm `heading`, `paragraph`, `table`, `kpi`, `stamp`, `signature`, `form_code`, `toc`, `furniture`; bảng có `columns[]`, `rows[]` (`code`, `label_raw`, `note`, `cells{raw, bbox, votes}`) | 🔴 | Đã có `Document IR/ir-v1.schema.json` và Python `TypedDict` ở `src/ir_types.py`; quy tắc giá trị/liên trường kiểm tra bằng `src/validate_ir.py`. Hợp đồng Gemini theo KNOWHOW mục 7.2 vẫn là việc riêng. |
| A2 | Adapter lớp text → IR: **chốt dùng `pdfplumber`** để đọc chữ, `bbox`, cỡ chữ và màu ký tự; dựng dòng bảng theo cột Mã số | 🔴 | Bản thử cũ dùng `pdftotext -bbox-layout` ở trang 148; code Python hiện dùng `pdfplumber` cho IR trang 148–156. `pdftotext -layout` vẫn dùng ở bước lấy chữ/OCR routing. Chất lượng ô cần đo trên gold set. |
| A3 | Adapter Tesseract TSV → IR (đã có block/dòng/bbox) | 🟡 | Dùng làm phiếu phụ cho từng ô |
| A4 | Đổi schema Gemini sang `blocks` + `rows` (thay cho `text`) | 🔴 | Tăng `PROMPT_VERSION` |
| A5 | Hợp nhất phiếu từng ô → bản `MERGED` | 🔴 | |
| A6 | Lọc `furniture`: khối lặp lại ở cùng vị trí trên ≥ 50% số trang, cùng số trang, chữ ký số | 🔴 | Giải quyết menu bên ở 211/211 trang |
| A7 | Phân loại trang (`page_class`) theo tiêu đề và mã mẫu: `BS`, `IS`, `CF`, `NOTES`, `NARRATIVE`, `KPI`, `LETTER`, `COVER` | 🔴 | Báo cáo thường niên FPT 2024: phần BCTC nằm ở trang 143–207 |

**B. Chuẩn hoá và map sang template chỉ số (G5, G6)**

| # | Việc | Ưu tiên | Ghi chú |
| --- | --- | --- | --- |
| B1 | Nhận diện thông tư, mẫu, phạm vi, kỳ, đơn vị, công ty | 🔴 | KNOWHOW mục 8.3–8.7 |
| B2 | Parse số: `.` ngăn nghìn, `(x)` là âm, `-` là không phát sinh; giữ chuỗi gốc | 🔴 | KNOWHOW mục 8.2 |
| B3 | Nạp `template_lines` cho TT200/TT202 và TT99 (trước hết các dòng của 15–25 chỉ số mỗi ngành), mỗi dòng trỏ tới `metric_id` của template | 🔴 | Cần chốt danh sách chỉ số với nhóm template |
| B4 | **Chặn từ phía template**, cần sửa trước khi map: phạm vi chỉ số chưa rõ (review template vấn đề 2: `trade_receivables` là 131, 211 hay tổng?); thiếu dòng tổng cần cho đẳng thức (vấn đề 3); thiếu `sign_convention` (vấn đề 8); thiếu `statement`/`section` (vấn đề 10); ngân hàng kế thừa chỉ số không áp dụng (vấn đề 4) | 🔴 | `03_Design/template/REVIEW_Template_JSON_v1.2.0_20261006.md` |
| B5 | Map nhãn khi không có mã (ngân hàng, mã OCR sai): T0' → T1 → T2 theo KNOWHOW mục 7.3; alias của template chỉ dùng làm ứng viên, không phải bằng chứng | 🟡 | Template ghi rõ: khớp nhãn chưa đủ để thành fact |
| B6 | Mẫu ngân hàng TT49 (không có cột Mã số, đơn vị Triệu VND) | 🟡 | Kiểm trên BCTC của 5 ngân hàng trong phạm vi |

**C. Trọng tài và quarantine (G4)**

| # | Việc | Ưu tiên | Ghi chú |
| --- | --- | --- | --- |
| C1 | Sinh luật từ `template_lines`: cha = Σ sign × con (bỏ dòng `is_memo`), chéo báo cáo (280 = 440, LCTT 70 = CĐKT 110) | 🔴 | KNOWHOW mục 7.4 |
| C2 | Quyết định cuối theo **ô**, không theo trang: bảng qua đủ đẳng thức thì OK dù Tesseract lệch; một đẳng thức chỉ lệch 1 ô thì sửa ô đó có kiểm soát và gắn `derived` | 🔴 | Thay cờ REVIEW cấp trang của POC |
| C3 | Đổi cờ POC sang `reason_code`: `NUMBERS_UNVERIFIED` → `EXTRACTOR_DISAGREE`, `GEMINI_UNREADABLE` → `UNREADABLE_CELL`, kèm `SUM_MISMATCH`, `TEMPLATE_UNKNOWN`… | 🔴 | KNOWHOW mục 12.3 |
| C4 | Màn hình UC17: xem ô bị quarantine cạnh ảnh trang (bbox), sửa, chạy lại kiểm tra | 🟡 | `quarantine_records.detail_json` |

**D. Database (G8)**

| # | Việc | Ưu tiên | Ghi chú |
| --- | --- | --- | --- |
| D1 | Thêm `document_pages` (`document_id`, `page_no`, `route`, `page_class`, `section_path`, `image_sha256`) và `page_extractions` (`engine`, `engine_version`, `prompt_version`, `ir_version`, `ir` jsonb, `quality` jsonb, `is_current`) | 🔴 | Thay cho `ocr_runs`/`pages`/`page_texts` ở REVIEW v6 mục 4.2, để không có hai thiết kế song song |
| D2 | Thêm `statement_templates`, `template_lines`; `financial_reports.template_id` | 🔴 | KNOWHOW mục 12.1 |
| D3 | `metrics` nạp từ template: `code` ← `metric_id`, `canonical_name` ← `label_vi`, `industry_scope` ← `sector_id`; **thêm** `data_type`, `period_type`, `unit_dimension`, `metric_version`; `section` cần template bổ sung (vấn đề 10) | 🔴 | ERD hiện chưa có `period_type`, `data_type` |
| D4 | `observations` đáp ứng ngữ cảnh bắt buộc của template (`db_storage.mandatory_context`): thêm `comparison_role` (cột kỳ này/kỳ so sánh), `dimensions` jsonb, `value_text` cho chỉ số `text`, `missing_reason`, `metric_version`, `raw_text`, `extraction_method`, `confidence`, `checks_json`, người/cách duyệt. **Đổi UNIQUE** `(report_id, metric_id)` thành `(report_id, metric_id, comparison_role, dimensions_hash)` | 🔴 | Khóa hiện tại không chứa được segment hay cột so sánh |
| D5 | Chuẩn hoá `locator_json`: `{extraction_id, page, form_code, row_key, column, bbox, extractor}` | 🔴 | FR11 |
| D6 | `quarantine_records.detail_json`; bổ sung `reason_codes` | 🟡 | |
| D7 | `text_chunks` sinh từ IR: bỏ `furniture`, `section_label` lấy từ mục lục, offset tính trên text của bản `MERGED` | 🟡 | Nhánh RAG cho báo cáo thường niên |
| D8 | Ghi mỗi lần gọi LLM vào `usage_events` (token, chi phí) | 🟡 | ERD đã có bảng này |
| D9 | Các file template trỏ tới nhưng **không có trong repo**: `contracts/candidate.schema.json`, `contracts/approved_fact.schema.json`, `DB_GUIDE.md`, `schema.sql` | 🔴 | Cần nhóm template bổ sung hoặc bỏ tham chiếu |

**E. Vận hành**

| # | Việc | Ưu tiên | Ghi chú |
| --- | --- | --- | --- |
| E1 | Thay `agy` bằng **Gemini API** (structured output, Batch API giảm 50%) | 🔴 | Gọi API chỉ tốn ~1,6k token vào mỗi trang thay vì ~13,6k. Giá 06/10/2026: 3.1 Flash-Lite ≈ $3,4 và 3.8 Flash ≈ $8,7 cho 1.000 trang (giả định ~1,6k vào / ~2k ra mỗi trang). Giá 3.8 Flash tăng gấp đôi từ 01/01/2027 |
| E2 | Gắn với `ingestion_jobs`: chặn trùng theo `sha256` trước khi OCR, chạy lại an toàn, retry, giới hạn đồng thời | 🔴 | |
| E3 | Ngưỡng (`min-chars`, `min-conf`, số khớp 95%) đưa vào `system_configs`/`config_versions` | 🟡 | ERD đã có |
| E4 | Docker image: poppler, tesseract + `tessdata_best` (`vie`, `osd`, `eng`); xoay ảnh bằng ImageMagick hoặc Pillow thay cho `sips` | 🟡 | `sips` chỉ có trên macOS |
| E5 | Gold set: mỗi ngành 1 công ty × 2 kỳ, chép tay (theo F01 của mentor), dùng để đo và hiệu chỉnh ngưỡng; test hồi quy trên 2 file mẫu | 🔴 | Đây là DoD Sprint 2 |
| E6 | Lưu ảnh trang ở object storage hoặc render lại khi cần (UC17 cần xem ảnh) | 🟢 | |

### 3.3 Quyết định cần chốt

| # | Câu hỏi | Lựa chọn | Đề xuất |
| --- | --- | --- | --- |
| Q1 | Viết worker sản phẩm bằng ngôn ngữ nào? | (a) Python, đúng stack đã duyệt (Python 3.13/FastAPI) và bộ đọc template (`TemplateRegistry`, `inheritance.py`); (b) giữ TypeScript làm worker riêng | (a). POC TS làm bản tham chiếu, chuyển logic sang Python. Các công cụ CLI (poppler, tesseract) dùng như nhau |
| Q2 | Gọi Gemini qua đâu? | (a) Gemini API có key dịch vụ; (b) `agy` | (a), xem E1. `agy` chỉ dùng cho thử nghiệm |
| Q3 | Tự động promote hay luôn duyệt tay? | Template ghi `approval: never auto-approve`; KNOWHOW PA C promote khi qua mọi kiểm tra cứng | Cần nhóm và mentor chốt. Đề xuất: cho tự promote ô bảng BCTC qua đủ đẳng thức, ghi `approval_method = AUTO_CHECKS`; các ô còn lại duyệt tay |
| Q4 | `observations` chứa chỉ số có chiều (segment) và chỉ số `text` không? | (a) mở rộng như D4; (b) giai đoạn đầu chỉ lưu chỉ số số, không chiều | (b) cho Sprint 3, (a) khi có nhu cầu thật |
| Q5 | Sự kiện doanh nghiệp (CBTT) lưu ở đâu? | bảng sự kiện riêng hay chỉ graph | Đã nêu ở REVIEW v6 mục 8.4 (#12), chưa chốt |

### 3.4 Lộ trình đề xuất

Theo lịch 6 sprint, mỗi sprint 2 tuần, đến 06/12/2026.

| Sprint | Nội dung | Đầu ra kiểm được |
| --- | --- | --- |
| S2 (đến 11/10) | A1, A2 (**pdfplumber**), A6, C1 trên PDF có lớp text; gold set đầu tiên (E5) | FPT 2024 trang 148–156 ra IR, qua đẳng thức, có số đo trên gold set |
| S3 (12/10–25/10) | A4, A5, A7, B1–B3, C2–C3, D1–D5, E1, E2; chốt Q1–Q4 | BCTC (lớp text và scan) → `observations` hoặc `quarantine_records` trong Postgres |
| S4 (26/10–08/11) | B5, B6 (ngân hàng), C4 (UC17 tối thiểu), D6–D8 | 10 mã trong phạm vi chạy hết, có tỉ lệ tự promote |
| S5–S6 | Nhánh RAG từ IR, sự kiện (Q5), tối ưu ngưỡng, test hồi quy | Đóng băng corpus |

Lịch trên là đề xuất. Nó phụ thuộc vào việc nhóm template xử lý B4 và D9 kịp trong S3.

### 3.5 Nháp Document IR v1

Mỗi trang một object, engine nào cũng xuất cùng dạng này. Ví dụ rút gọn trang 148 của FPT 2024 (dữ liệu thật, bbox lược bớt):

```json
{
  "ir_version": "1",
  "page": 148,
  "size": [1920, 1080],
  "source": { "engine": "TEXT_LAYER", "tool": "pdfplumber 0.11.9" },
  "blocks": [
    { "id": "b1", "type": "furniture", "text": "BÁO CÁO THƯỜNG NIÊN 2024", "bbox": [42, 109, …] },
    { "id": "b2", "type": "heading",   "text": "BẢNG CÂN ĐỐI KẾ TOÁN HỢP NHẤT", "bbox": [429, 55, …] },
    { "id": "b3", "type": "form_code", "text": "MẪU SỐ B 01 – DN/HN" },
    { "id": "t1", "type": "table", "unit_text": "VND",
      "columns": [ { "key": "c1", "header": "2024" }, { "key": "c2", "header": "2023" } ],
      "rows": [
        { "code": "131", "label_raw": "Phải thu ngắn hạn của khách hàng", "note": "6",
          "cells": { "c1": { "raw": "10.537.019.113.380" }, "c2": { "raw": "9.057.647.206.985" } } }
      ] }
  ]
}
```

- Ô chỉ lưu chuỗi in gốc (`raw`). Parse số, đơn vị và kỳ làm ở bước B.
- Trang OCR có thêm phiếu của từng engine cho mỗi ô, ví dụ `"votes": {"gemini": "2.773.160.700", "tesseract": "2.773,180.700"}`.
- Từ ô này, bước B3 tra (TT202, B01-DN/HN, 131) trong `template_lines` để ra `metric_id`. Hiện chưa map được, vì template chưa chốt `common.trade_receivables` là dòng 131, dòng 211 hay tổng hai dòng (B4).
