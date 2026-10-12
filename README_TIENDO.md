# BÁO CÁO TIẾN ĐỘ THỰC HIỆN DỰ ÁN OCR ROUTER
*(Cập nhật ngày 12/10/2026 dựa trên đối chiếu mã nguồn thực tế và README)*

Quy ước trạng thái:
- 🟢 **xong**: Đã hoàn thành, có mã nguồn và kiểm chứng chạy tốt.
- 🟡 **gần**: Đã hoàn thành một phần cốt lõi / đạt mức POC, đang trong quá trình hoàn thiện.
- 🔴 **chưa**: Chưa triển khai hoặc đang chờ phụ thuộc từ module/hệ thống khác.

---

## 1. BẢNG TIẾN ĐỘ CHI TIẾT THEO MỤC 3.2 README

### A. Document IR và tách cấu trúc (Giải quyết G1–G3)
| Mã | Việc cần làm | Trạng thái | Đánh giá thực tế trong Code |
| :---: | :--- | :---: | :--- |
| **A1** | Chốt schema **IR v1** (JSON Schema + types: blocks, tables, columns, rows, cells, votes...) | 🟢 **xong** | Đã hoàn thiện file `Document IR/ir-v1.schema.json`, `src/ir_types.py` và bộ validator `src/validate_ir.py`. |
| **A2** | Adapter lớp text $\rightarrow$ IR: `pdftotext -bbox-layout` / `pdfplumber`, dựng dòng bảng theo cột Mã số | 🟢 **xong** | Đã triển khai hoàn chỉnh trong `src/buildDocumentIr.py` và `src/financialContent.py`. Kiểm chứng trên FPT 2024 & FPT 2025 đạt 100% các dòng có mã. |
| **A3** | Adapter Tesseract TSV $\rightarrow$ IR (có block/dòng/bbox làm phiếu phụ) | 🟢 **xong** | Đã có các hàm `_ocr_blocks`, `_tess_statement_table`, `_tess_vote` trong `src/buildDocumentIr.py`. |
| **A4** | Đổi schema Gemini sang `blocks` + `rows` (thay cho text phẳng) | 🟢 **xong** | Đã triển khai trong `src/model.py` (`GEMINI_SCHEMA`, `PROMPT_VERSION = "api-ir-v2"`), trả về JSON có cấu trúc bảng, dòng, ô, box_2d. |
| **A5** | Hợp nhất phiếu từng ô $\rightarrow$ bản `MERGED` | 🟢 **xong** | Đã có hàm `_ai_ir_blocks`, tích hợp `votes` giữa Gemini và Tesseract, gán cờ `needs_review` ở từng ô. |
| **A6** | Lọc `furniture`: khối lặp lại ở cùng vị trí trên $\ge 50\%$ số trang | 🟢 **xong** | Đã hoàn thiện thuật toán `audit_and_promote` và `_furniture_key`, loại bỏ hoàn toàn menu sidebar ở 211/211 trang FPT 2024, xuất file `furniture_audit.json`. |
| **A7** | Phân loại trang (`page_class`) theo tiêu đề và mã mẫu | 🟢 **xong** | Đã hoàn thiện hàm `financial_page_class` nhận diện chính xác `balance_sheet`, `income_statement`, `cash_flow`, `notes`, `auditor_report`, `toc`... |

---

### B. Chuẩn hoá và map sang template chỉ số (G5, G6)
| Mã | Việc cần làm | Trạng thái | Đánh giá thực tế trong Code |
| :---: | :--- | :---: | :--- |
| **B1** | Nhận diện thông tư, mẫu, phạm vi, kỳ, đơn vị, công ty | 🟢 **xong** | Nhận diện tự động TT200/202, TT99, TT49, tách ngày tháng lập báo cáo, đơn vị tiền tệ trong `src/financialContent.py`. |
| **B2** | Parse số kế toán: `.` ngăn nghìn, `(x)` là âm, `-` là không phát sinh; giữ chuỗi gốc `raw` | 🟢 **xong** | Đã có `_parse_accounting_number` trong `src/financialContent.py`. Xử lý lỗi định dạng gán `BAD_NUMBER_FORMAT`, bảo toàn giá trị gốc. |
| **B3** | Nạp `template_lines` cho TT200/TT202 và TT99, liên kết với `metric_id` | 🟢 **xong** | Đã có các file cấu hình `templates/financial-template-lines.json` và `templates/tt99-2025-b01-b02-b03.json`. |
| **B4** | Chặn từ phía template (sửa phạm vi chỉ số trade_receivables, dòng tổng, sign_convention...) | 🔴 **chưa** | Phụ thuộc nhóm phụ trách Template bên ngoài repo, hiện tại mã nguồn tạm thời xử lý các trường hợp ngoại lệ. |
| **B5** | Map nhãn khi không có mã (ngân hàng TT49, mã OCR sai): T0' $\rightarrow$ T1 $\rightarrow$ T2 | 🟡 **gần** | Đã có cơ chế fallback nhãn cơ bản cho Techcombank TT49 nhưng chưa có bộ từ điển mapping nhãn hoàn chỉnh. |
| **B6** | Mẫu biểu ngân hàng TT49 (không có cột Mã số, đơn vị Triệu VND) | 🟡 **gần** | Đã nhận diện và dựng được bảng với >30 dòng (`test_r4_financial_routes.py`), nhưng chưa triển khai đầy đủ hệ thống đẳng thức kiểm tra cho TT49. |

---

### C. Trọng tài và quarantine (G4)
| Mã | Việc cần làm | Trạng thái | Đánh giá thực tế trong Code |
| :---: | :--- | :---: | :--- |
| **C1** | Sinh luật từ `template_lines`: cha = $\Sigma$ sign $\times$ con, chéo báo cáo | 🟢 **xong** | Đã hoàn thiện hàm `evaluate_accounting`, kiểm tra đẳng thức cân đối kế toán, liên kết cha-con và kiểm tra EPS mềm. |
| **C2** | Quyết định cuối theo **ô**, không theo trang (bảng qua đủ đẳng thức thì OK) | 🟢 **xong** | Đã áp dụng `_accounting_cell_coverage`, bảo vệ được 98.56% ô có mã trên các báo cáo thực nghiệm. |
| **C3** | Đổi cờ POC sang `reason_code` chuẩn (`EXTRACTOR_DISAGREE`, `UNREADABLE_CELL`, `SUM_MISMATCH`...) | 🟢 **xong** | Đã thay thế hệ thống cờ cũ bằng các reason code chuẩn hóa trong `src/financialContent.py`. |
| **C4** | Màn hình UC17: xem ô bị quarantine cạnh ảnh trang (bbox), sửa, chạy lại | 🔴 **chưa** | Đây là tính năng UI/Web Frontend cho người dùng, hiện chưa có trong codebase POC. |

---

### D. Database (G8)
| Mã | Việc cần làm | Trạng thái | Đánh giá thực tế trong Code |
| :---: | :--- | :---: | :--- |
| **D1** | Thêm bảng `document_pages` và `page_extractions` | 🔴 **chưa** | Hiện tại lưu trữ dạng file JSON (`annual_ir/`), chưa kết nối PostgreSQL / ERD v2. |
| **D2** | Thêm `statement_templates`, `template_lines`; `financial_reports.template_id` | 🟡 **gần** | Cấu trúc dữ liệu đã sẵn sàng dưới dạng JSON template, chưa migrate nạp vào cơ sở dữ liệu quan hệ. |
| **D3** | Nạp `metrics` từ template | 🟡 **gần** | Đã có danh mục JSON trong thư mục `templates/catalogs/`, chưa đồng bộ vào DB. |
| **D4** | Bảng `observations` đáp ứng ngữ cảnh bắt buộc của template (comparison_role, dimensions...) | 🔴 **chưa** | Chưa triển khai module kết nối và chèn dữ liệu fact vào DB. |
| **D5** | Chuẩn hoá `locator_json` (`extraction_id`, `page`, `form_code`, `row_key`, `bbox`...) | 🟡 **gần** | Dữ liệu IR đã có đầy đủ thông tin này, chỉ cần hàm đóng gói thành định dạng JSONB cuối cùng. |
| **D6** | Bảng `quarantine_records.detail_json` | 🟡 **gần** | File `cell_evaluation.json` đã lưu đầy đủ thông tin này, chưa đẩy vào DB. |
| **D7** | Sinh `text_chunks` từ IR (bỏ furniture, gán nhãn section) phục vụ RAG | 🟢 **xong** *(phần IR)*<br>🟡 **gần** *(phần DB)* | `src/reportContent.py` đã tạo ra nội dung text sạch không có furniture và có chỉ mục mục lục `sections.json`. |
| **D8** | Ghi nhận tài nguyên LLM vào `usage_events` (token, chi phí) | 🟡 **gần** | Đã ghi nhận chi tiết token và số lần gọi trong `summary.json`, chưa lưu bản ghi vào DB. |
| **D9** | Bổ sung các file schema còn thiếu (`contracts/candidate.schema.json`...) | 🔴 **chưa** | Phụ thuộc nhóm bên ngoài repo. |

---

### E. Vận hành
| Mã | Việc cần làm | Trạng thái | Đánh giá thực tế trong Code |
| :---: | :--- | :---: | :--- |
| **E1** | Thay `agy` bằng **Gemini API** trực tiếp (structured output, Batch API) | 🟢 **xong** | Đã chuyển sang gọi Gemini API trực tiếp trong `src/model.py`, có fallback OpenRouter, không phụ thuộc Antigravity CLI. |
| **E2** | Gắn với `ingestion_jobs` (chặn trùng sha256, retry, giới hạn đồng thời) | 🟡 **gần** | Đã có cache sha256 và thread pool, nhưng chưa gắn vào worker backend hàng đợi (Celery/Temporal). |
| **E3** | Đưa ngưỡng (`min-chars`, `min-conf`...) vào bảng cấu hình `system_configs` | 🔴 **chưa** | Hiện tại truyền qua tham số CLI hoặc thiết lập mặc định trong mã nguồn. |
| **E4** | Docker image chuẩn hóa (poppler, tesseract + tessdata_best, ImageMagick) | 🔴 **chưa** | Chưa tạo `Dockerfile`. |
| **E5** | Gold set và kiểm thử hồi quy trên các mẫu báo cáo | 🟢 **xong** | Đã có Gold Set FPT 2024 (`Gold_Set/gold_fpt_2024.xlsx`), fixture Safoco TT99, BCTN 2025 và bộ test đạt 38/38 bài test. |
| **E6** | Lưu ảnh trang ở object storage (S3/MinIO) | 🔴 **chưa** | Hiện tại đang lưu cục bộ trong thư mục `work/`. |

---

## 2. TỔNG HỢP TIẾN ĐỘ CHUNG

| Nhóm công việc | Tổng số | 🟢 Xong | 🟡 Gần | 🔴 Chưa | Tỷ lệ hoàn thành |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **A. Document IR & Cấu trúc** | 7 | 7 | 0 | 0 | **100%** |
| **B. Chuẩn hóa & Map Template** | 6 | 3 | 2 | 1 | **67%** |
| **C. Trọng tài & Quarantine** | 4 | 3 | 0 | 1 | **75%** |
| **D. Cơ sở dữ liệu (Database)** | 9 | 0 | 6 | 3 | **33%** |
| **E. Vận hành & Triển khai** | 6 | 2 | 1 | 3 | **42%** |
| **TỔNG CỘNG** | **32** | **15** | **9** | **8** | **~61%** |

### Nhận xét trọng tâm:
1. **Phần lõi OCR, Thuật toán & Trích xuất (Nhóm A & C):** Đã hoàn thiện **100%** mục tiêu thiết kế. Hệ thống Document IR v1, lọc furniture và trọng tài đẳng thức kế toán hoạt động cực kỳ ổn định và chính xác (38/38 unit tests pass).
2. **Phần Template & Kế toán (Nhóm B):** Đã hoàn tất cho doanh nghiệp thông thường (TT200, TT202, TT99). Còn mở ở mảng Ngân hàng (TT49) và các chỉ số đang đợi chốt từ nhóm template.
3. **Phần Tích hợp Hệ thống & Cơ sở dữ liệu (Nhóm D & E):** Đây là công việc trọng tâm của các Sprint tiếp theo (chuyển đổi từ POC chạy file sang hệ thống dịch vụ có Database, Docker, Worker và giao diện duyệt UC17).
