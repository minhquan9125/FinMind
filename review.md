# Review: JSON Schema Document IR v1 (bản nháp)

- **Đối tượng review:** `03_Design/template/Schema.txt`, JSON Schema Draft 2020-12 cho Document IR v1, mô tả một trang gồm khối, bảng, dòng và ô
- **Ngày review:** 06/10/2026
- **File đề xuất sửa:** `Schema_suggested_20261006.json`, cùng thư mục. Mỗi chỗ sửa có `$comment` ghi mã vấn đề (A1, B3…) của review này. Cuối file có một ví dụ hợp lệ lấy từ trang 148.
- **Cách review:**
    - Kiểm tra cả hai schema bằng `jsonschema` 4.26 (Python), chế độ Draft 2020-12.
    - Validate 16 tài liệu mẫu, mỗi mẫu nhắm vào một quy tắc, và 4 trang hợp lệ thuộc các loại khác nhau.
    - Lấy số liệu và tọa độ thật từ `bctc/FPT_2024_498332.pdf` trang 148 bằng `pdftotext 26.04 -bbox-layout`.
- **Tài liệu đối chiếu:**
    - `03_Design/Data_Pipeline/poc/ocr-router/README.md`: mục 3.1 (các tầng dữ liệu), 3.2 (việc A1, A5, A7, D1), 3.5 (nháp IR v1).
    - `03_Design/Data_Pipeline/KNOWHOW_ChuanHoa_BCTC_OCR_20261002.md`: mục 7.2 (hợp đồng Gemini), 7.3 (thứ tự map), 8.2 (số), 12.2 (`match_method`).
    - `CẤU TRÚC TEMPLATE.md`: mục 3 (`statement`), 6 (alias), 8 (`schema_version` và `metric_version`).

## Kết luận

**Chưa dùng được.** Schema bản thân hợp lệ, nhưng có một lỗi khiến mọi bảng có ít nhất một dòng đều bị từ chối (A1), kể cả mẫu JSON nhóm gửi kèm. Ngoài ra còn 3 vấn đề mức Cao về nội dung IR (A2–A4).

**Điểm tốt nên giữ:**

- Schema đóng: `additionalProperties: false` ở mọi cấp, nên trường gõ sai bị bắt ngay.
- Tọa độ có quy ước rõ: `[x0, y0, x1, y1]`, gốc ở góc trên bên trái, cho phép `null` khi chưa đo.
- Enum engine có cả `MERGED`; ô đã có chỗ cho `votes`.
- Có `logical_table_id` cho bảng nối trang, và tách số trang vật lý với số trang in, đúng như REVIEW v6 H5 yêu cầu.
- Có đủ các loại khối README A1 đề xuất (`heading`, `furniture`, `form_code`…).

**Kết quả kiểm tra.** `Schema.txt` được vá tạm lỗi A1 trước khi chạy, để các lỗi khác lộ ra. Cột "Mong muốn" là hành vi đúng.

| Trường hợp | Schema.txt (vá tạm A1) | Schema đề xuất | Mong muốn |
|---|---|---|---|
| Bảng có ≥ 1 dòng, dùng `ma_so` như mẫu gửi kèm (schema gốc, chưa vá) | FAIL | — | PASS |
| Ô không đọc được: `raw: null` | FAIL | PASS | PASS |
| Phiếu Tesseract đọc ra null, có độ tin cậy | FAIL | PASS | PASS |
| Ô `raw: ""` (ô trống phải bỏ khóa) | PASS | FAIL | FAIL |
| Thiếu `source` | PASS | FAIL | FAIL |
| Thiếu `page_size` | PASS | FAIL | FAIL |
| `unit: px` nhưng không có thông tin render | PASS | FAIL | FAIL |
| Engine GEMINI không có `prompt_version` | PASS | FAIL | FAIL |
| `votes` có engine lạ `foo` | PASS | FAIL | FAIL |
| Khóa ô là `2024` thay vì `c1` | PASS | FAIL | FAIL |
| Trang thuyết minh (`notes`) | FAIL | PASS | PASS |
| Số trang in là `"iv"` | FAIL | PASS | PASS |
| Dòng có `metric_match` | PASS | FAIL | FAIL |
| Hai block trùng `id` | PASS | PASS | FAIL (\*) |
| Ô `c9` không có trong `columns` | PASS | PASS | FAIL (\*) |
| bbox `x1 < x0` | PASS | PASS | FAIL (\*) |

(\*) JSON Schema không diễn đạt được ba luật này. Cần một hàm kiểm tra bằng code (C2). Hàm mẫu ở C2 đã chạy thử và bắt được cả ba.

Thêm 4 trang hợp lệ, đều PASS với schema đề xuất:
- trang scan Tesseract dùng `px`, có `render`;
- trang `MERGED` có `votes`;
- bảng ngân hàng có `code: null`, nối trang và không lặp lại tiêu đề cột;
- dòng tiêu đề nhóm không có số (`cells: {}`).

---

## Tổng hợp vấn đề

| # | Vấn đề | Mức |
|---|---|---|
| A1 | `code` bắt buộc nhưng chỉ khai báo `ma_so`: mọi bảng có dòng đều không hợp lệ | Cao |
| A2 | Ô không ghi được trạng thái "không đọc được"; phiếu không có null và độ tin cậy | Cao |
| A3 | `source` và `page_size` không bắt buộc: không biết engine nào đọc, bbox không có đơn vị | Cao |
| A4 | IR chứa kết quả mapping và template (`metric_match`, `template_context`, `cell.label`) | Cao |
| B1 | `oneOf` ở `blocks` che lỗi thật | Trung bình |
| B2 | Tiêu đề cột chỉ một chuỗi: mất "Tại ngày 31 tháng 12 năm", tức mất kỳ | Trung bình |
| B3 | Dòng thiếu `id`, độ thụt lề và chữ đậm | Trung bình |
| B4 | Phân loại nằm hai chỗ, enum lệch template, thiếu `notes`, trường trùng nhau | Trung bình |
| C1 | `source` có trường trùng hoặc đặt sai chỗ | Thấp |
| C2 | Chưa có kiểm tra bằng code cho các luật JSON Schema không diễn đạt được | Thấp |
| C3 | Chưa có ví dụ hợp lệ đi kèm; README 3.5 dùng tên trường khác schema | Thấp |

Bảng đổi tên trường, để sửa code sinh IR, ở [Phụ lục](#phụ-lục-đổi-trường-từ-schematxt-sang-bản-đề-xuất).

---

## A1. `code` bắt buộc nhưng chỉ khai báo `ma_so`

- **Vấn đề:** dòng của bảng có `required` gồm `code`, nhưng `properties` chỉ khai báo `ma_so`. Cộng với `additionalProperties: false`, không có cách viết nào hợp lệ:
    - dùng `ma_so` thì thiếu `code`;
    - dùng `code` thì `code` là trường lạ.

  Chỉ bảng có `rows: []` mới qua được. Có lẽ khi đổi tên, nhóm sửa `required` mà quên sửa `properties`.
- **As-is:**
  ```
  rows.items.required   = ["code", "label_raw", "note", "bbox", "cells"]
  rows.items.properties = { "ma_so", "label_raw", "note", "bbox", "metric_match", "cells" }
  ```
  Kết quả validate:
  ```
  dùng ma_so → rows/0: 'code' is a required property
  dùng code  → rows/0: Additional properties are not allowed ('code' was unexpected)
  ```
- **To-be:** thống nhất tên `code`, cho phép `null`: BCTC ngân hàng không có cột Mã số, và dòng tiêu đề như "TÀI SẢN" cũng không in mã. Không đặt `pattern` cho `code`, vì IR lưu đúng chuỗi đã đọc, kể cả khi OCR đọc sai. Kiểm tra định dạng mã làm ở bước trọng tài.
  ```json
  "code": { "type": ["string", "null"] }
  ```
- **Căn cứ:** kết quả validate ở trên. README 3.5 và KNOWHOW 7.2 đều dùng `code`.

## A2. Ô không ghi được trạng thái "không đọc được"

- **Vấn đề:**
    - `cell.raw` bắt buộc là string, nên không ghi được ô có in số nhưng không đọc được. Hợp đồng với Gemini yêu cầu trả `null` cho ô này, và reason code tương ứng là `UNREADABLE_CELL`.
    - Ô trống cũng chưa có quy ước: ghi `""` hay bỏ khóa đều hợp lệ, nên cùng một ô có hai cách biểu diễn.
    - `votes` chỉ nhận string, nên không ghi được việc một engine không đọc được ô. Cũng không có chỗ cho độ tin cậy từng từ mà Tesseract trả về (POC đã dùng).
- **As-is:**
  ```json
  "raw":   { "type": "string" },
  "votes": { "type": "object", "additionalProperties": { "type": "string" } }
  ```
- **To-be:** ba trạng thái, mỗi trạng thái đúng một cách ghi:

  | Trên trang | Cách ghi |
  |---|---|
  | In số, đọc được | `"raw": "(619.531.925.859)"`, giữ nguyên chuỗi |
  | In "-" | `"raw": "-"`. Đổi sang 0 kèm cờ `printed_dash` ở bước chuẩn hóa |
  | In nhưng không đọc được | `"raw": null` |
  | Không in gì | bỏ khóa của cột đó trong `cells` |

  ```json
  "raw":   { "type": ["string", "null"], "minLength": 1 },
  "votes": {
    "type": "object", "minProperties": 1,
    "propertyNames": { "enum": ["TEXT_LAYER", "TESSERACT", "GEMINI"] },
    "additionalProperties": { "$ref": "#/$defs/vote" }
  },
  "vote": { "required": ["raw"], "properties": {
    "raw":  { "type": ["string", "null"], "minLength": 1 },
    "conf": { "type": ["number", "null"], "minimum": 0, "maximum": 100 } } }
  ```
  Với `MERGED`, `raw` là bản được chọn, còn `votes` giữ phiếu của từng engine.
- **Căn cứ:** KNOWHOW 7.2: "Ô không đọc được thì trả `null`". KNOWHOW 8.2: "-" và ô trống là hai trường hợp khác nhau. KNOWHOW 12.3: `UNREADABLE_CELL`, `EXTRACTOR_DISAGREE`. README 3.5: ví dụ `votes`.

## A3. `source` và `page_size` không bắt buộc

- **Vấn đề:**
    - **`source` không nằm trong `required`.** IR không có `source` thì không biết engine nào đọc, model hay prompt nào. Như vậy không truy vết được, trái nguyên tắc "LLM không được tạo bản ghi production không truy vết được".
    - **`page_size` được phép `null` trong khi bbox vẫn có số.** Mô tả của `bbox` nói đơn vị là `page_size.unit`, nên khi đó bbox không có đơn vị.
    - **Không có `dpi` và góc xoay.** Tesseract trả pixel trên ảnh đã render và đã xoay theo OSD; trang của `bctc_fpt_2026.pdf` bị lật 180°. Thiếu hai thông tin này thì không đổi được pixel về point để so phiếu với lớp text, và cũng không cắt đúng vùng ảnh cho UC17.
    - **Chưa quy định đổi tọa độ của Gemini.** Gemini trả `box_2d` theo thứ tự `[y0, x0, y1, x1]` trên thang 0–1000. Nếu ghi thẳng vào IR thì sai cả thứ tự lẫn đơn vị.
    - **Không có định danh tài liệu.** Chỉ có `document_name`, mà tên file có thể sai (xem C1).
- **To-be:**
    - `required` ở gốc thêm `page_size` và `source`; `page_size` không còn được `null`. Kích thước trang luôn biết trước, từ `pdfinfo` hoặc kích thước ảnh.
    - `source` bắt buộc có `document_sha256`. Thêm `image_sha256` (bắt buộc với TESSERACT và GEMINI; POC đã dùng làm khóa cache), `prompt_version` (bắt buộc với GEMINI) và `render: {dpi, rotation}` (bắt buộc khi `unit` là `px`). Ba điều kiện này viết bằng `allOf` và `if/then` ở gốc schema.
    - Mô tả của `page_size` ghi rõ: tọa độ của Gemini phải được đổi sang không gian của trang trước khi ghi vào IR.
- **Căn cứ:** KNOWHOW mục 2 (nguyên tắc LLM, locator FR11). KNOWHOW 3.2 (trang lật 180°, xoay 90°). README 2.1 và `src/render.ts` (render 3508 px rồi xoay). KNOWHOW 7.2 (lưu model id, phiên bản prompt, sha256 ảnh trang). README D1 (`page_extractions` có `engine_version`, `prompt_version`).

## A4. IR chứa kết quả mapping và template

- **Vấn đề:** schema đặt vào IR ba thứ không in trên trang:
    1. `rows[].metric_match`: kết quả map dòng sang `metric_id`.
    2. `template_context`: file template và ngành dùng để map.
    3. `cells.*.label`: diễn giải cột, ví dụ "Giá trị năm 2024".

  Theo README 3.1, IR là tầng L2: một schema chung cho mọi engine, lưu theo từng lần trích xuất (`page_extractions.ir`). Mapping thuộc tầng sau (bước B). Để chung gây ra bốn vấn đề:
    - **Phải sinh lại IR khi template đổi.** Mỗi khi template đổi `metric_version` hay alias, phải sinh lại IR, dù chữ trên trang không đổi.
    - **Không rõ IR nào giữ mapping.** Một trang có IR từ TEXT_LAYER, TESSERACT, GEMINI và MERGED; mapping nên nằm ở bản nào?
    - **IR phụ thuộc một ngành.** `template_context` chỉ có một `sector_id` và `template_file`, trong khi một doanh nghiệp có thể thuộc nhiều ngành (CẤU TRÚC TEMPLATE mục 4). Template cũng quy định nhận diện bằng nội dung, không dựa vào tên file.
    - **`label` "Giá trị năm 2024" sai nghĩa với CĐKT.** Số trên CĐKT là số dư tại ngày 31/12/2024 (`instant`), không phải giá trị của cả năm.

  Bản thân `metric_match` cũng có lỗi:
    - **Thiếu cách map theo mã dòng.** `match_method` không có giá trị nào cho mã dòng, trong khi KNOWHOW 7.3 đặt map theo (thông tư, mẫu, mã) ở tầng đầu tiên. Mẫu gửi kèm map dòng 100 bằng `exact_alias`. Ngay trang 148 đã có phản ví dụ: dòng 140 và 141 cùng nhãn "Hàng tồn kho". Trong template 2.3.0, nhãn này khớp cả `common.inventories` lẫn `common.inventories_gross`, và nằm trong `context_required_aliases`.
    - **Ghi sai loại phiên bản.** `template_schema_version` là phiên bản định dạng file. Fact cần `metric_version`, tức phiên bản định nghĩa chỉ số (CẤU TRÚC TEMPLATE mục 8).
    - **Trộn trạng thái với cách map.** `template_alias_missing` là một trạng thái nhưng nằm trong enum `match_method`.
    - **Không ràng buộc trạng thái với `metric_id`.** Validate cho qua `status: "no_match"` kèm `metric_id`, và cả `status: "candidate"` với `metric_id: null`.
- **To-be:**
    - Bỏ `metric_match`, `template_context` và `cell.label` khỏi IR.
    - Lưu mapping thành bản ghi riêng, trỏ về IR qua `(extraction_id, block_id, row_id)`:
      ```json
      {
        "extraction_id": "<page_extractions.id>",
        "block_id": "p148-t1",
        "row_id": "r1",
        "line_key": { "regime": "TT202_2014", "form_code": "B01-DN/HN", "code": "100" },
        "status": "candidate",
        "metric_id": "common.current_assets",
        "metric_version": "2.3.0",
        "match_method": "CODE",
        "candidate_ids": ["common.current_assets"],
        "evidence": "Mã 100 của B01-DN/HN; nhãn in 'TÀI SẢN NGẮN HẠN' khớp alias"
      }
      ```
    - `match_method` theo KNOWHOW 12.2: `CODE`, `PATH`, `ALIAS`, `FUZZY`, `EMBED`, `LLM`, `MANUAL`. Đổi giá trị cũ như sau:
        - `exact_alias` → `ALIAS`;
        - `pdf_hierarchy` → `PATH`;
        - `pdf_label_semantics` → `EMBED` hoặc `LLM`;
        - `pdf_reconciliation` là bằng chứng từ đẳng thức, nên ghi vào `evidence`;
        - `template_alias_missing` → `status: "no_match"` kèm lý do.
    - Schema của bản ghi mapping thêm ràng buộc:
        - `candidate` thì `metric_id` khác null;
        - `no_match` thì `metric_id` là null và `candidate_ids` rỗng;
        - `ambiguous` thì có ít nhất 2 ứng viên.
    - Nơi đặt hợp lý là `contracts/candidate.schema.json`. Template có nhắc tới file này nhưng repo chưa có (README D9).
    - Nếu demo cần một file duy nhất thì bọc ngoài: `{ "ir": { … }, "mappings": [ … ] }`, IR vẫn giữ nguyên schema.
- **Căn cứ:** README 3.1 (bảng tầng L0–L3), 3.5 ("Parse số, đơn vị và kỳ làm ở bước B"). KNOWHOW 7.3, 12.2. CẤU TRÚC TEMPLATE mục 4, 6, 8. Kết quả kiểm tra dòng "Dòng có `metric_match`".

## B1. `oneOf` ở `blocks` che lỗi thật

- **Vấn đề:** khi một bảng sai, `oneOf` báo lỗi cho cả khối, kèm toàn bộ nội dung khối, không chỉ ra trường nào sai. Đây là lý do lỗi A1 khó thấy.
- **As-is:** `blocks/0 -> {'id': 'p148-balance_sheet-table', 'type': 'table', 'classification': {…` (đã cắt bớt)
- **To-be:** phân nhánh theo `type` bằng `if/then`:
  ```json
  "items": {
    "type": "object", "required": ["type"],
    "if":   { "properties": { "type": { "const": "table" } } },
    "then": { "$ref": "#/$defs/table_block" },
    "else": { "$ref": "#/$defs/text_block" }
  }
  ```
  Lỗi khi đó trỏ đúng chỗ: `blocks/3/rows/0 -> 'code' is a required property` (đã chạy thử).
- **Căn cứ:** kết quả validate trước và sau khi đổi.

## B2. Tiêu đề cột chỉ một chuỗi

- **Vấn đề:** `columns[].header` là một chuỗi, nên mẫu chỉ còn `"2024"`. Dòng "Tại ngày 31 tháng 12 năm" phía trên cả hai cột bị mất. Bước B1 của pipeline cần chính dòng này để biết kỳ thời điểm (CĐKT) hay kỳ khoảng ("Năm 2024" ở KQKD, LCTT; "Kỳ này/Kỳ trước" ở BCTC giữa niên độ). Đơn vị "VND" in dưới từng cột cũng không có chỗ ghi.

  Ngoài ra, bbox bảng trong mẫu bắt đầu từ dòng 100 (y = 214,66), không bao vùng tiêu đề (y ≈ 113–198). UC17 cắt ảnh theo bbox này sẽ mất tiêu đề.
- **To-be:** `header_lines` ghi mọi dòng tiêu đề phía trên cột, theo thứ tự từ trên xuống, giữ nguyên văn, kể cả dòng trải nhiều cột. Bảng nối trang không lặp tiêu đề thì `[]`. Mô tả của `table.bbox` ghi rõ là gồm cả tiêu đề cột.
  ```json
  { "key": "c1", "header_lines": ["Tại ngày 31 tháng 12 năm", "2024", "VND"],
    "bbox": [1535.42, 147.55, 1576.06, 198.46] }
  ```
  `key` có `pattern` `^c[1-9][0-9]*$`. `cells` dùng cùng mẫu qua `propertyNames`, nên khóa ô như `"2024"` bị bắt.
- **Căn cứ:** lớp text trang 148. KNOWHOW 8.4: kỳ của CĐKT khác kỳ của KQKD và LCTT.

## B3. Dòng thiếu `id`, độ thụt lề và chữ đậm

- **Vấn đề:**
    - **Thiếu khóa dòng.** Không có trường nào làm khóa dòng cho locator. Mã số có thể null (ngân hàng), trùng, hoặc bị OCR đọc sai.
    - **Thiếu thông tin cấp dòng.** BCTC ngân hàng không có mã, nên muốn dựng đường dẫn kiểu A›III›1 (tầng T0' của KNOWHOW 7.3) chỉ còn dựa vào độ thụt lề và chữ đậm. Schema chưa có chỗ ghi hai thông tin này.
- **To-be:**
    - `id` bắt buộc, duy nhất trong bảng (`r1`, `r2`…).
    - `indent` là x0 của nhãn. Trên trang 148, nhãn cấp 1 bắt đầu ở x = 541,4 và nhãn cấp 2 ở x = 555,6, đủ để phân cấp.
    - `bold` nhận true, false hoặc null.
    - Cả `indent` và `bold` được phép null khi engine không đo được. Ví dụ, `pdftotext` không cho biết độ đậm, nên ví dụ trong file đề xuất ghi `bold: null`.
- **Căn cứ:** KNOWHOW 3.2 (ngân hàng không có cột Mã số), 7.3 (T0'). Tọa độ đo bằng `pdftotext -bbox-layout`.

## B4. Phân loại nằm hai chỗ và lệch template

- **Vấn đề:**
    - **Hai chỗ phân loại.** `document_context` ở cấp trang và `classification` ở cấp block dùng cùng một định nghĩa. Một trang có thể mang hai phân loại khác nhau mà không có luật nào chọn.
    - **Enum lệch template.** `report_type` dùng `cash_flow_statement`, còn `statement` của template dùng `cash_flow`. Danh sách giá trị `statement` đếm trên 7 file template: `balance_sheet`, `income_statement`, `cash_flow`, `notes`, `operating`, `text`.
    - **Thiếu giá trị cho phần lớn các trang.** Enum không có `notes` nên trang thuyết minh không phân loại được. Báo cáo thường niên còn có các trang thư, văn xuôi và KPI (README A7).
    - **Trường trùng nhau.** Mẫu gửi kèm có `group_label` = `canonical_title`, và `group_id` = `report_type`. `company_information` chưa có định nghĩa.
    - **Chưa phân vai.** `continuation` và `logical_table_id` cùng nói chuyện nối trang nhưng chưa ghi rõ trường nào làm gì.
- **To-be:**
    - Một trường `page_class` ở cấp trang, được phép null ngay sau khi trích xuất (bước A7 điền sau). Giá trị trùng tên với `statement` của template ở các loại báo cáo, cộng các loại trang của README A7: `cover`, `toc`, `letter`, `narrative`, `kpi`, `company_information`, `auditor_report`, `balance_sheet`, `income_statement`, `cash_flow`, `notes`, `other`.
    - Bảng chỉ giữ nguyên văn `title`. Mã mẫu đã có block `form_code`.
    - Hai trường nối trang có vai trò riêng:
        - `continued` là điều thấy trên chính trang đó, ví dụ chữ "(tiếp theo)";
        - `logical_table_id` được điền khi nối các trang, cùng giá trị cho mọi mảnh của một bảng.
- **Căn cứ:** CẤU TRÚC TEMPLATE mục 3. Danh sách `statement` đếm trên 7 file template. README A7. Trang 149 của FPT 2024 có tiêu đề "BẢNG CÂN ĐỐI KẾ TOÁN HỢP NHẤT (tiếp theo)".

## C1. `source` có trường trùng hoặc đặt sai chỗ

- **Vấn đề:**

  | Trường | Vấn đề |
  |---|---|
  | `source.physical_page` | Trùng với `page` ở gốc; validate cho qua `page: 148` cùng `physical_page: 150` |
  | `source.printed_page` (integer) | Số trang in là nội dung trang, không phải nguồn. Có báo cáo đánh số La Mã, nên kiểu integer làm mất dữ liệu |
  | `source.form_code` | Là nội dung trang, trùng với block `form_code` |
  | `source.document_name` | Tên file không đáng tin: `bctc_fpt_2026.pdf` thực ra là BCTC của FPT Online |

- **To-be:**
    - Bỏ `physical_page` và `form_code`.
    - Chuyển `printed_page` ra gốc, kiểu string và giữ nguyên văn.
    - Đổi `document_name` thành `file_name`, mô tả rõ là chỉ dùng để hiển thị. Định danh tài liệu là `document_sha256` (A3).
- **Căn cứ:** KNOWHOW 3.2 (tên file sai công ty), 8.5 (không dùng tên file). REVIEW v6 H5 (`page_no` là số thứ tự trong PDF).

## C2. Chưa có kiểm tra bằng code

- **Vấn đề:** JSON Schema không diễn đạt được bốn luật sau:
    - `id` của block và của dòng không được trùng;
    - khóa trong `cells` phải có trong `columns`;
    - bbox phải đúng chiều và nằm trong trang;
    - IR `MERGED` phải có `votes` ở mọi ô có in.

  Kết quả kiểm tra cho thấy cả schema cũ lẫn schema mới đều cho qua các lỗi này.
- **To-be:** chạy thêm hàm kiểm tra sau JSON Schema. Bản dưới đây đã chạy thử: ví dụ hợp lệ trả về rỗng; bản cố tình sai bị bắt cả bốn loại lỗi.
  ```python
  def check_ir_semantics(ir):
      errs = []
      w, h = ir["page_size"]["width"], ir["page_size"]["height"]
      merged = ir["source"]["engine"] == "MERGED"
      def check_bbox(path, bb):
          if bb is None: return
          x0, y0, x1, y1 = bb
          if x0 > x1 or y0 > y1: errs.append(f"{path}: bbox ngược chiều")
          if x1 > w or y1 > h: errs.append(f"{path}: bbox ra ngoài trang")
      seen = set()
      for b in ir["blocks"]:
          if b["id"] in seen: errs.append(f"{b['id']}: trùng id block")
          seen.add(b["id"]); check_bbox(b["id"], b["bbox"])
          if b["type"] != "table": continue
          keys = [c["key"] for c in b["columns"]]
          if len(set(keys)) != len(keys): errs.append(f"{b['id']}: trùng key cột")
          row_ids = set()
          for r in b["rows"]:
              p = f"{b['id']}/{r['id']}"
              if r["id"] in row_ids: errs.append(f"{p}: trùng id dòng")
              row_ids.add(r["id"]); check_bbox(p, r["bbox"])
              for k, c in r["cells"].items():
                  if k not in keys: errs.append(f"{p}/{k}: cột không có trong columns")
                  check_bbox(f"{p}/{k}", c["bbox"])
                  if merged and not c.get("votes"): errs.append(f"{p}/{k}: MERGED nhưng thiếu votes")
      return errs
  ```
- **Căn cứ:** kết quả kiểm tra, các dòng đánh dấu (\*).

## C3. Chưa có ví dụ đi kèm; README 3.5 lệch tên trường

- **Vấn đề:**
    - Schema không có ví dụ hợp lệ nào. Mẫu JSON nhóm gửi kèm lại không qua chính schema này (A1).
    - README 3.5 dùng `code`, `header` và `size: [w, h]`, còn schema dùng `ma_so` và `page_size: {width, height, unit}`. Như vậy đang có hai nguồn định nghĩa.
- **To-be:**
    - Nhúng ví dụ vào `examples` của schema. File đề xuất đã có ví dụ trang 148: 4 khối chữ và 1 bảng 3 dòng, số liệu và tọa độ lấy thật từ lớp text.
    - Sửa README 3.5 để trỏ tới schema, không giữ một ví dụ riêng.
    - Đưa bộ test validate (16 trường hợp ở phần Kết luận, cùng hàm C2) vào repo cạnh schema, để lỗi kiểu A1 không lặp lại.
- **Căn cứ:** kết quả validate; README 3.5.

---

## Ngoài phạm vi schema

| Mục | Ghi chú |
|---|---|
| Ảnh minh họa gửi kèm mẫu JSON | Ảnh có cột 2025/2024, tức BCTC năm 2025. Mẫu JSON lấy từ `FPT_2024_498332.pdf` trang 148, có cột 2024/2023. Lần sau chụp đúng trang của mẫu để người review đối chiếu được |
| Bản ghi mapping | Cần schema riêng (A4), nên đặt ở `contracts/candidate.schema.json`. Phụ thuộc việc chốt `template_lines` (KNOWHOW 12.1, README B3) |
| Nơi lưu IR | README D1: `page_extractions` có `engine`, `engine_version`, `prompt_version`, `ir_version`, `ir` jsonb, `is_current`. Các trường trong `source` của IR nên khớp với các cột này |
| Bước tiếp theo của A1 trong README | Sinh IR cho trang 148–156 theo schema mới, chạy đẳng thức ngay trên IR (đã cộng tay: 100 = 110 + 120 + 130 + 140 + 150 khớp ở cột 2024), và xuất một trang scan (`bctc_fpt_2026` trang 7, bản Gemini) theo cùng schema |

---

## Phụ lục: đổi trường từ `Schema.txt` sang bản đề xuất

| `Schema.txt` | Bản đề xuất | Mã |
|---|---|---|
| `rows[].ma_so` | `rows[].code` (string hoặc null) | A1 |
| — | `rows[].id` (bắt buộc), `rows[].indent`, `rows[].bold` | B3 |
| `columns[].header` (string) | `columns[].header_lines` (mảng string) | B2 |
| `columns[].key` (string tự do) | `columns[].key` theo mẫu `c1`, `c2`…; `cells` cùng mẫu | B2 |
| `cells.*.raw` (string) | string hoặc null, không rỗng; ô không in thì bỏ khóa | A2 |
| `cells.*.votes` (`{engine: string}`) | `{engine: {raw, conf}}`, engine trong enum | A2 |
| `cells.*.label` | bỏ | A4 |
| `rows[].metric_match` | bỏ, chuyển sang bản ghi mapping riêng | A4 |
| `template_context` | bỏ | A4 |
| `document_context`, `blocks[].classification` | `page_class` ở cấp trang | B4 |
| `classification.continuation` | `table.continued` | B4 |
| `table.title` | `table.title` (string hoặc null), giữ nguyên văn | B4 |
| `page_size` (được null, không bắt buộc) | bắt buộc, không null | A3 |
| `source` (không bắt buộc) | bắt buộc; thêm `document_sha256`, `image_sha256`, `prompt_version`, `render {dpi, rotation}` | A3 |
| `source.physical_page` | bỏ, dùng `page` | C1 |
| `source.printed_page` (integer) | `printed_page` ở gốc (string) | C1 |
| `source.form_code` | bỏ, dùng block `form_code` | C1 |
| `source.document_name` | `source.file_name`, chỉ để hiển thị | C1 |
| `text_block.classification` | bỏ, dùng `page_class` | B4 |
| `blocks.items` dùng `oneOf` | `if/then` theo `type` | B1 |
| — | `examples` có ví dụ trang 148 | C3 |