# OCR Router — Báo cáo thường niên & BCTC Document IR

- **Cập nhật:** 08/10/2026
- **Ngôn ngữ triển khai:** Python 3.10+ thuần (thay thế hoàn toàn bản TypeScript cũ)
- **Môi trường:** Windows / Linux
- **Git Branch:** [`feature/ocr-pipeline`](https://github.com/minhquan9125/FinMind/tree/feature/ocr-pipeline) | Remote: `https://github.com/minhquan9125/FinMind.git`
- **Tài liệu đối chiếu gốc:** [`README_M.md`](README_M.md) (bản kế hoạch và thiết kế kiến trúc POC lập ngày 06/10/2026).

Tài liệu này đối chiếu **toàn diện và chi tiết từng mục** giữa kế hoạch ban đầu trong `README_M.md` với **mã nguồn và dữ liệu thực tế đang chạy** trong hệ thống.

---

## 1. Kết quả thực tế đã đạt được (FPT 2024 & FPT 2025)

Hệ thống đã chạy thành công và được kiểm toán tự động trên 2 ấn bản PDF:

| Tiêu chí | FPT 2024 (`FPT_2024_498332 (1).pdf`) | FPT 2025 (`BCTN_2025.pdf`) | Ghi chú kỹ thuật |
| :--- | :---: | :---: | :--- |
| **Tổng số trang PDF** | 215 trang | 232 trang | 2024: 211 trang lớp chữ, 4 trang Tesseract; 2025: 230 trang lớp chữ, 2 trang Tesseract |
| **Trang IR Thường niên (`content/`)** | **119 trang** (Trang 20–141) | **156 trang** (Trang 3–158) | Tự động phân loại 6 chủ đề, loại bỏ trang bìa và BCTC |
| **Khối nội dung thường niên** | 313 heading, 2.345 paragraph | 226 heading, 3.436 paragraph | Audit không thấy thiếu từ trong vùng trang PDF nhìn thấy của các trang lớp chữ; khối lớp chữ có `bbox` |
| **Khối rác giao diện (`furniture`)** | 1.601 khối | 1.799 khối | Cô lập menu dọc lề trái, header, số trang để giữ sạch text cho RAG |
| **Bảng thường niên (`content/`)** | 15 bảng cấu trúc (`structured`) | 9 bảng mục tiêu (`text_only`) | Tự động định vị trang theo nội dung (Cổ đông trang 32–33, HĐQT trang 86, Thù lao trang 90, 108) |
| **Chỉ số KPI phi tài chính** | 30 KPI verified | 2 KPI verified | Gắn `block_id` trỏ thẳng tới khối IR tương ứng |
| **Trang IR phần BCTC (`table/`)** | **67 trang** (Trang 143–209) | **67 trang** (Trang 160–226) | Tự động nhận diện khoảng trang BCTC kiểm toán |
| **Bảng BCTC chính có cấu trúc** | **9 trang** (CĐKT, KQKD, LCTT) | **8 trang** (CĐKT, KQKD, LCTT) | Bóc tách thành `columns`, `rows`, `cells` có `bbox` |
| **Kết quả kiểm toán (`audit`)** | **0 lỗi (`errors: []`)** | **0 lỗi (`errors: []`)** | Kiểm tra schema, liên kết file và bảo toàn từ trong vùng trang nhìn thấy; chưa đo độ chính xác của từng ô |

---

## 1.1 Luồng bóc tách và nơi xem kết quả

```text
PDF → main.py → pages.jsonl (chữ từng trang, tuyến text_layer/Tesseract/Gemini)
                 → buildDocumentIr.py → annual_ir/index.json
                                      ├─ content/ : nội dung thường niên
                                      └─ table/   : toàn bộ phần BCTC kiểm toán
```

1. `main.py` dùng lớp chữ PDF khi có; trang không đủ chữ được render rồi đưa qua Tesseract, và có thể gọi Gemini theo tùy chọn CLI. `pages.jsonl` là kết quả OCR theo trang, **chưa phải bảng IR**.
2. `buildDocumentIr.py` dùng **`pdfplumber` làm adapter A2 đã chốt**: đọc chữ, tọa độ, cỡ chữ và màu ký tự để nhận tiêu đề, menu bên lề, các khối `heading`, `paragraph`, `furniture`, `kpi` và trang BCTC. Dữ liệu được xử lý trực tiếp trong Python. Mỗi trang được ghi thành `p-NNN.ir.json`, với `NNN` là **số trang PDF**. `pdftotext -layout` vẫn dùng trước đó để lấy chữ và quyết định trang cần OCR; không dùng `pdftotext -bbox-layout` để dựng IR.
3. Bảng FPT 2024 đã rà soát được dựng theo cấu hình riêng cho đúng mã SHA-256 của PDF mẫu. Với ba báo cáo chính trong FPT 2025, chương trình tìm hàng tiêu đề `Mã số` / `Thuyết minh` / hai năm, dùng vị trí các cột và mã dòng để tạo `table`. Trang không tách chắc chắn giữ chữ; trang báo cáo chính chưa có bảng được ghi vào `table/index.json` → `needs_review`.
4. Mỗi file IR được kiểm tra với `Document IR/ir-v1.schema.json` trước khi ghi. `auditDocumentIr.py` kiểm tra lại cấu trúc, chỉ mục và từ trong vùng trang PDF nhìn thấy. Các kiểm tra này **không chứng minh mọi ô đã được nhận đúng**.

`annual_ir/content/` chứa các trang thường niên; **bảng thường niên đã tách cũng nằm trong file trang ở đây**. `annual_ir/table/` chứa *toàn bộ* phần BCTC kiểm toán, gồm ý kiến kiểm toán, ba báo cáo chính và thuyết minh; không phải file nào trong thư mục này cũng có khối `table`.

| Cần tìm | Mở file |
| :--- | :--- |
| Danh mục hai nhánh | `annual_ir/index.json` |
| Chủ đề, trang và bảng thường niên mục tiêu | `annual_ir/content/sections.json` → `topics`, `table_targets` |
| Một trang thường niên | `annual_ir/content/p-NNN.ir.json` → `blocks` |
| Loại trang BCTC và trang có bảng | `annual_ir/table/index.json` → `page_index`, `structured_table_ranges` |
| Bảng BCTC cụ thể | `annual_ir/table/p-NNN.ir.json` → khối `type: "table"` |
| KPI đã đối chiếu | `annual_ir/content/kpi_review.json` |

## 1.2 Một bảng IR gồm những gì?

Trong `p-148.ir.json` của FPT 2024, bảng cân đối có khối `type: "table"`. Ví dụ rút gọn theo **đúng tên trường của schema**:

```json
{
  "id": "p148-t1",
  "type": "table",
  "title": "BẢNG CÂN ĐỐI KẾ TOÁN HỢP NHẤT",
  "bbox": [428.22, 122.33, 1860.43, 873.22],
  "unit_text": null,
  "columns": [
    {"key": "c1", "header_lines": ["Tại ngày 31 tháng 12 năm", "2024", "VND"], "bbox": [1535.42, 122.33, 1678.76, 198.46]},
    {"key": "c2", "header_lines": ["Tại ngày 31 tháng 12 năm", "2023", "VND"], "bbox": [1683.16, 122.33, 1860.43, 198.46]}
  ],
  "rows": [
    {
      "id": "r1", "code": "100", "label_raw": "TÀI SẢN NGẮN HẠN",
      "note": null, "bbox": [428.22, 214.66, 1859.4, 232.66],
      "cells": {
        "c1": {"raw": "45.535.942.846.453", "bbox": [1410.84, 214.66, 1575.94, 232.66]},
        "c2": {"raw": "36.705.751.751.876", "bbox": [1694.3, 214.66, 1859.4, 232.66]}
      }
    }
  ]
}
```

`columns[]` mô tả các cột giá trị; khóa `c1`, `c2` nối sang `rows[].cells`. Mỗi phần tử `rows[]` là một dòng in trên PDF: `code` là mã số nếu có, `label_raw` là tên dòng, `note` là số thuyết minh nếu có. `cells.c1.raw` là **chuỗi gốc**, chưa chuẩn hóa thành số hay `metric_id`. `bbox = [x0, y0, x1, y1]` là vị trí trên trang để dò ngược PDF; trang lớp chữ dùng đơn vị point (`page_size.unit: "pt"`). Ví dụ chỉ minh họa một dòng, không phải toàn bộ file.

Ở bản 2025, xem cùng kiểu dữ liệu trong `annual_ir/table/p-165.ir.json`: mã dòng `100` có nhãn `TÀI SẢN NGẮN HẠN`, hai ô giá trị nằm ở `cells.c1` (2025) và `cells.c2` (2024). Tên cột phải đọc từ `columns[]`, không suy ra cố định rằng `c1` luôn là năm hiện tại trên mọi PDF.

**`text_only` vẫn có dữ liệu.** Đây là trạng thái của bảng mục tiêu trong `content/sections.json`: đã tìm được tiêu đề và trang, nội dung vẫn nằm trong các khối `heading`/`paragraph`, nhưng chưa tách thành `rows` và `cells`. Nó **không** phải một giá trị của `block.type`. FPT 2025 hiện có 9 bảng thường niên ở trạng thái này; 2024 có 15 bảng thường niên đã thành khối `table`.

**Giới hạn kiểm chứng:** `table/index.json` có `arithmetic_checks` cho một số phép cộng/trừ BCTC và `needs_review` cho trang báo cáo chính chưa tách chắc chắn hoặc sai phép kiểm tra. Đây là kiểm tra bổ sung, chưa phải bộ luật sinh từ `template_lines`, chưa có gold set để đo độ đúng của từng ô.

## 1.3 Mốc S2 trong kế hoạch (đến 11/10/2026)

Tiêu chí ở `README_M.md`: **A1, A2, A6, C1 trên PDF có lớp text; gold set đầu tiên (E5). FPT 2024 trang PDF 148–156 ra IR, qua đẳng thức và có số đo trên gold set.** Hiện mốc này **chưa hoàn tất**:

| Tiêu chí S2 | Bằng chứng hiện có | Còn thiếu |
| :--- | :--- | :--- |
| A1 — schema IR v1 | Có JSON Schema, validation từng trang và `src/ir_types.py` khai báo type cho trang, nguồn, 8 loại khối chữ, bảng, cột, dòng, ô và phiếu đọc | Đã có đủ type theo cấu trúc schema; quy tắc giá trị và liên trường tiếp tục được kiểm tra khi chạy |
| A2 — lớp text → IR | Đã chốt `pdfplumber`; cả **9 trang 148–156** có bảng IR, tổng **139 dòng** với mã, nhãn, ô và `bbox`; audit schema không lỗi | Cần đo độ đúng từng ô trên gold set và mở rộng khả năng tách cho mẫu PDF khác; không còn yêu cầu chuyển sang `pdftotext -bbox-layout` |
| A6 — lọc `furniture` | Có khối `furniture` cho nhiều menu, header, footer | Kiểm tra lặp cùng vị trí trên ≥50% trang và đánh giá trang ngoại lệ |
| C1 — đẳng thức | Tính trên IR hiện có: **8/8 lượt kiểm tra cơ bản** khớp (4 luật × 2 kỳ) | Sinh luật từ `template_lines`, thêm luật chéo báo cáo và trọng tài theo ô |
| E5 — gold set | Chưa có bộ nhãn chuẩn độc lập và báo cáo số đo | Chép tay dữ liệu chuẩn, đối chiếu ô IR và tính chỉ số độ chính xác |

`auditDocumentIr.py` trả `errors: []` cho FPT 2024, nhưng kết quả đó đo **tính hợp lệ cấu trúc và độ phủ chữ**, không phải độ chính xác theo gold set. Vì thiếu E5 và các phần tổng quát của A6/C1, không đánh dấu S2 là hoàn thành.

---

## 2. Đối chiếu toàn diện với `README_M.md`

Dưới đây là bảng đối chiếu chi tiết từng hạng mục được đặt ra trong `README_M.md` với hiện trạng mã nguồn thực tế:

### 2.1 Đối chiếu 8 khoảng trống gốc (G1 – G8)

| Mã | Vấn đề nêu trong `README_M.md` | Hiện trạng thực tế trong code | Trạng thái |
| :---: | :--- | :--- | :---: |
| **G1** | Output là text phẳng, không có khối, bảng, dòng, ô | **ĐÃ GIẢI QUYẾT:** Đã có Document IR v1 theo `ir-v1.schema.json`. Mỗi trang có `blocks` (`heading`, `paragraph`, `kpi`, `furniture`, `table`). Các bảng chính có `columns`, `rows`, `cells` kèm tọa độ `bbox`. | ✅ Xong |
| **G2** | Không loại bỏ menu bên lề, header, footer lặp lại | Đã cô lập nhiều khối thành `furniture` bằng vị trí/bố cục; chưa có bước xác nhận khối lặp ở cùng vị trí trên ≥50% trang như kế hoạch A6. | 🟡 Một phần |
| **G3** | Không phân loại trang (CĐKT, KQKD, LCTT, thuyết minh, văn xuôi) | **ĐÃ GIẢI QUYẾT:** Tự động gán `page_class` cho từng trang: `balance_sheet`, `income_statement`, `cash_flow`, `notes`, `narrative`, `kpi`. Tách riêng 2 nhánh `content/` và `table/`. | ✅ Xong |
| **G4** | Không có trọng tài đẳng thức kế toán | Có 4 loại đối chiếu cơ bản cho hai kỳ, ghi vào `table/index.json` → `arithmetic_checks`; chưa sinh luật từ template hoặc làm trọng tài theo từng ô. | 🟡 Một phần |
| **G5** | Không chuẩn hoá số, đơn vị, kỳ, công ty, thông tư | **CHƯA TRIỂN KHAI:** Các con số trong bảng và KPI hiện vẫn lưu dạng chuỗi văn bản gốc (ví dụ `"62.849"`, `"(15.000)"`). Chưa parse sang `decimal`. | ⏳ Chưa làm |
| **G6** | Không map dòng sang chỉ số của template | **CHƯA TRIỂN KHAI:** Chưa nối mã dòng BCTC vào danh mục `metric_id` trong `templates/` để sinh `observations`. | ⏳ Chưa làm |
| **G7** | Gọi Gemini qua `agy` (CLI tương tác, tốn quota) | **ĐÃ GIẢI QUYẾT:** Đã loại bỏ hoàn toàn `agy`; chuyển sang gọi trực tiếp **Gemini API** qua `model.py` dùng SDK `google-genai`, gộp 4 trang/lần và cache ảnh SHA-256. | ✅ Xong |
| **G8** | Ghi file JSON cục bộ, chưa ghi Database; chưa có gold set | **GIỮ GHI FILE:** Hiện tại xuất file JSON theo chuẩn L2; chưa kết nối CSDL PostgreSQL (ERD v2); chưa xây dựng gold set đo độ chính xác. | ⏳ Chưa làm |

---

### 2.2 Đối chiếu 5 nhóm công việc kỹ thuật (Nhóm A $\rightarrow$ E)

#### Nhóm A: Document IR và tách cấu trúc (Giải quyết G1–G3)
* **A1 — Chốt Schema IR v1 (JSON Schema + Python type):** ✅ **HOÀN THÀNH PHẦN CẤU TRÚC**. `Document IR/ir-v1.schema.json` quy định JSON; `src/ir_types.py` khai báo `TypedDict` cho mọi loại khối, dòng/ô và nguồn; `src/validate_ir.py` kiểm tra schema và quy tắc liên trường khi chạy. Type giúp trình soạn thảo kiểm tra cấu trúc nhưng không thay thế validator runtime.
* **A2 — Adapter lớp chữ PDF $\rightarrow$ IR:** ✅ **HOÀN THÀNH TRÊN MẪU**. Đã chốt `pdfplumber` để đọc chữ, tọa độ, cỡ chữ và màu; chuyển đổi các bảng BCTC và bảng thường niên đã rà soát sang cấu trúc `table`. Chất lượng trên tài liệu mới cần gold set để đánh giá.
* **A3 — Adapter Tesseract TSV $\rightarrow$ IR:** 🟡 **TIẾN TRIỂN TỐT**. Đã phân tích chi tiết dữ liệu TSV (12 cột `level, page_num, block_num, par_num, line_num, word_num, left, top, width, height, conf, text`) thành danh sách từ (`wordItems`) kèm tọa độ hộp bao `[left, top, right, bottom]` và độ tin cậy (`conf`). Đã tích hợp vào `buildDocumentIr.py` để gán tọa độ khối có đơn vị pixel (`page_size.unit: "px"`) cho các trang scan OCR thay vì để `bbox: null`. Phần còn lại: nhóm dòng/cột để dựng bảng dạng cấu trúc từ trang scan thuần.
* **A4 — Đổi schema Gemini sang `blocks/rows`:** ❌ **CHƯA LÀM**. Gemini API hiện mới dùng để OCR text so chéo ở tầng L1, chưa ép Structured Output trả về thẳng IR dạng bảng theo schema.
* **A5 — Hợp nhất phiếu từng ô (`MERGED`):** ❌ **CHƯA LÀM**. Chưa có cơ chế bỏ phiếu giữa các engine OCR theo từng ô riêng lẻ.
* **A6 — Lọc bỏ rác giao diện (`furniture`):** 🟡 **MỘT PHẦN**. Có tách theo vị trí và bố cục; chưa kiểm chứng lặp trên ≥50% trang, nên không khẳng định đã loại hết menu/header khỏi `paragraph`.
* **A7 — Phân loại trang (`page_class`):** ✅ **HOÀN THÀNH**. Phân loại chuẩn xác toàn bộ các trang thường niên và BCTC trên cả 2 bản 2024 và 2025.

#### Nhóm B: Chuẩn hoá và Ánh xạ Template (G5, G6)
* **B1 — Nhận diện thông tư, mẫu biểu, kỳ, đơn vị, công ty:** ❌ **CHƯA LÀM**.
* **B2 — Parse số học (`.` ngăn nghìn, `,` thập phân, `(x)` số âm, `-` bằng 0):** ❌ **CHƯA LÀM**. Số liệu vẫn ở dạng chuỗi nguyên gốc.
* **B3 — Nạp `template_lines` map sang `metric_id`:** ❌ **CHƯA LÀM**.
* **B4 $\rightarrow$ B6 — Xử lý biểu mẫu ngân hàng TT49, nhãn alias:** ❌ **CHƯA LÀM**.

#### Nhóm C: Trọng tài & Kiểm duyệt (G4)
* **C1 — Sinh luật đẳng thức kế toán (cha = tổng con, chéo báo cáo):** 🟡 **MỘT PHẦN**. Có 4 loại kiểm tra cơ bản trên bảng BCTC, gồm tổng tài sản, nguồn vốn và doanh thu thuần; chưa sinh luật từ `template_lines` hoặc bao phủ đầy đủ luật chéo báo cáo.
* **C2 — Quyết định theo ô (Auto-derivation):** ❌ **CHƯA LÀM**.
* **C3 — Chuẩn hóa mã lý do (`reason_code`):** ❌ **CHƯA LÀM**.
* **C4 — Giao diện kiểm duyệt con người (UI UC17):** ❌ **CHƯA LÀM**. Hệ thống hiện vận hành 100% qua CLI.

#### Nhóm D: Cơ sở dữ liệu (G8)
* **D1 — Bảng `document_pages`, `page_extractions` (lưu IR jsonb):** ❌ **CHƯA LÀM** (hiện lưu file `.ir.json`).
* **D2 $\rightarrow$ D6 — Bảng `metrics`, `observations`, `quarantine_records`:** ❌ **CHƯA LÀM**.
* **D7 — Cắt đoạn văn bản (`text_chunks`) phục vụ RAG:** 🟡 **TIỀM NĂNG SẴN SÀNG**. Đã có sẵn 2.345 đoạn (2024) và 3.436 đoạn (2025) `paragraph` sạch; chỉ cần viết thêm script cắt chunk.

#### Nhóm E: Vận hành & Môi trường
* **E1 — Thay `agy` bằng Gemini API trực tiếp:** ✅ **HOÀN THÀNH**. Chạy qua `model.py` với SDK chính thức `google-genai`.
* **E2 — Chặn trùng theo mã SHA-256:** ✅ **HOÀN THÀNH**. Đã có cơ chế cache ảnh theo SHA-256 trong `model.py`.
* **E3 — Đưa cấu hình vào hệ thống:** ✅ **HOÀN THÀNH**. Cấu hình qua file `.env` và tham số CLI.
* **E4 — Đóng gói Docker:** ⏳ **CHƯA LÀM**. Hiện chạy trực tiếp trên môi trường Windows/Python cục bộ.
* **E5 — Gold Set đối chuẩn chất lượng:** ⏳ **CHƯA LÀM**.

---

### 2.3 Đối chiếu 5 quyết định kiến trúc (Q1 – Q5)

| # | Câu hỏi | Lựa chọn ban đầu | Hiện trạng thực tế trong dự án |
| :---: | :--- | :--- | :--- |
| **Q1** | Ngôn ngữ worker sản phẩm? | Đề xuất Python, bỏ TypeScript | **ĐÃ CHỐT XONG 100%:** Toàn bộ pipeline chạy trên Python 3.10+ thuần. TypeScript đã loại bỏ hoàn toàn. |
| **Q2** | Gọi Gemini qua đâu? | Đề xuất Gemini API, bỏ `agy` | **ĐÃ CHỐT XONG 100%:** Dùng `GEMINI_API_KEY` trực tiếp qua Google GenAI SDK; `gemini.py` (cũ) đã cất vào `_archive/`. |
| **Q3** | Tự động duyệt hay duyệt tay? | Đề xuất tự duyệt khi qua kiểm tra cứng | `structured` nghĩa là đã có dòng/ô trong IR; `verified` áp dụng cho KPI đối chiếu theo caption đã rà soát. Chưa có quyết định duyệt nghiệp vụ tự động theo từng ô. |
| **Q4** | `observations` có chiều và text? | Đề xuất giữ số phẳng trước | **ĐÃ CHỐT XONG:** Giữ dữ liệu phẳng ở tầng Document IR; chưa ép chiều dữ liệu phức tạp. |
| **Q5** | Sự kiện doanh nghiệp (CBTT)? | Đề xuất tách riêng | **ĐÃ CHỐT XONG:** Đã loại bỏ hoàn toàn khỏi phạm vi Báo cáo thường niên. |

---

### 2.4 Đối chiếu 4 tầng dữ liệu kiến trúc (L0 – L3)

```text
L0: File PDF gốc (SHA-256)        ──► [ĐÃ CÓ: FPT 2024 & FPT 2025]
L1: Raw OCR Payload (TSV / Text)  ──► [ĐÃ CÓ: pages.jsonl, cache SHA-256]
L2: Document IR (Blocks/Tables)   ──► [ĐÃ CÓ TRÊN 2 PDF MẪU: annual_ir/ (audit 0 lỗi); còn bảng text_only]
──────────────────────────────────────────────────────────────────────────────
L3: Dữ liệu nghiệp vụ (DB / RAG)  ──► [CHƯA LÀM: observations, text_chunks]
```

---

## 3. Tổng kết súc tích: Đã làm được gì & Chưa làm được gì

### ✅ NHỮNG GÌ ĐÃ LÀM ĐƯỢC (Thành tựu cốt lõi):
1. **Chuyển đổi hoàn chỉnh sang Python thuần:** Pipeline chạy mượt mà trên Windows/Linux, không phụ thuộc NodeJS hay macOS.
2. **Bộ định tuyến OCR siêu tiết kiệm:** Đọc text layer sạch cho 98% số trang, chỉ gọi Gemini API khi gặp trang scan khó (có cache ảnh SHA-256).
3. **Hoàn thiện tầng Document IR (L2):** 
   * Tách bạch 2 nhánh: Báo cáo thường niên (`content/`) và BCTC kiểm toán (`table/`).
   * Phân loại các chương thường niên và các báo cáo tài chính chính trên 2 PDF mẫu.
   * Tách nhiều menu lề/header thành `furniture`; cần đánh giá thêm các trang ngoại lệ.
   * Bóc tách thành công 15 bảng cấu trúc và 30 KPI trên bản 2024.
   * **Đột phá trên bản 2025:** Tự động định vị trang động theo nội dung (Cổ đông dời sang trang 32–33, HĐQT dời sang trang 86, Thù lao dời sang trang 90, 108; BCTC từ trang 160–226 có 8 trang bảng cấu trúc).
4. **Kiểm toán cấu trúc trên hai PDF mẫu:** `auditDocumentIr.py` trả **0 lỗi schema và liên kết**, không thiếu từ trong vùng trang nhìn thấy. Chưa có phép đo độ chính xác từng ô trên gold set.

### ⏳ NHỮNG GÌ CHƯA LÀM ĐƯỢC (Tồn đọng để lên Production):
1. **Chưa chuẩn hóa giá trị số (Number Parser - Nhóm B):** Chưa chuyển chuỗi `"62.849"`, `"(15.000)"` thành số thực `decimal` để tính toán.
2. **Chưa có trọng tài đẳng thức đầy đủ (Nhóm C):** Mới có vài kiểm tra cơ bản; chưa sinh luật từ template và chưa quyết định theo từng ô.
3. **Chưa lưu trữ Cơ sở dữ liệu (Database - Nhóm D):** Dữ liệu mới dừng ở file JSON cục bộ, chưa nạp vào PostgreSQL (ERD v2).
4. **Chưa tích hợp Chatbot AI / RAG:** Đã có văn bản sạch nhưng chưa cắt thành `text_chunks` nạp vào Vector DB.
5. **Chưa đóng gói Docker & Giao diện Web (UI):** Toàn bộ vận hành qua dòng lệnh CLI.

---

## 4. Cấu trúc thư mục hiện tại

```text
ocr-router/
├── .env                                # Chứa GEMINI_API_KEY
├── requirements.txt                    # Thư viện phụ thuộc
├── FPT_2024_498332 (1).pdf             # PDF mẫu 2024 (215 trang)
├── BCTN_2025.pdf                       # PDF mẫu 2025 (232 trang)
├── README_BAO_CAO_THUONG_NIEN.md       # Tài liệu hiện trạng dự án (Bản này)
├── README_M.md                         # Tài liệu kế hoạch gốc ngày 06/10/2026
│
├── _archive/                           # Thư mục cất các file thử nghiệm cũ & code BCTC cũ
│   ├── applyPdfReview.py
│   ├── buildSelectedTablesIr.py
│   ├── extractP148Rows.py
│   ├── gemini.py                       # Code agy cũ
│   └── *.json                          # Các file JSON override cũ
│
├── Document IR/
│   └── ir-v1.schema.json               # Schema chuẩn cho Document IR v1
│
├── src/                                # Mã nguồn chính (100% Python)
│   ├── main.py                         # CLI điều khiển chính
│   ├── buildDocumentIr.py              # Bộ dựng Document IR cho cả 2 nhánh
│   ├── reportContent.py                # Bóc tách 6 chủ đề thường niên, bảng và KPI
│   ├── financialContent.py             # Phân loại và định vị trang BCTC kiểm toán
│   ├── ir_types.py                     # Python TypedDict tương ứng Document IR v1
│   ├── validate_ir.py                  # Validator kiểm tra schema
│   ├── auditDocumentIr.py              # Bộ kiểm toán đối soát không mất từ với PDF gốc
│   ├── textLayer.py                    # Đọc lớp text PDF
│   ├── render.py                       # Render ảnh và tự động xoay trang
│   ├── tesseract.py                    # OCR Tesseract tiếng Việt
│   ├── model.py                        # Gọi Gemini API trực tiếp
│   ├── crossCheck.py                   # So chéo kết quả giữa các engine
│   └── util.py                         # Tiện ích dùng chung
│
└── ocr_router_out/
    ├── FPT_2024_498332 (1)/annual_ir/  # Kết quả Document IR FPT 2024 (119 + 67 trang)
    └── BCTN_2025/annual_ir/            # Kết quả Document IR FPT 2025 (156 + 67 trang)
        ├── index.json                  # Chỉ mục gốc liên kết 2 nhánh
        ├── content/                    # Nhánh Thường niên (Tổng quan, Cổ đông, Quản trị, ESG)
        └── table/                      # Nhánh Tài chính (BCTC kiểm toán)
```

---

## 5. Hướng dẫn chạy và kiểm toán trên Windows

```powershell
# Cài đặt thư viện
python -m pip install -r requirements.txt

# --- CHẠY BẢN FPT 2024 ---
python src\main.py "FPT_2024_498332 (1).pdf" --gemini never --build-document-ir
python src\auditDocumentIr.py "FPT_2024_498332 (1).pdf" --ir-dir "ocr_router_out\FPT_2024_498332 (1)\annual_ir"

# --- CHẠY BẢN FPT 2025 ---
python src\main.py "BCTN_2025.pdf" --gemini never --build-document-ir
python src\auditDocumentIr.py "BCTN_2025.pdf" --ir-dir "ocr_router_out\BCTN_2025\annual_ir"
```
