# OCR router POC

Đọc báo cáo PDF để tạo `pages.jsonl` và Document IR. Trang có lớp chữ được đọc trực tiếp; trang scan đi qua Tesseract và, khi bật, Gemini hoặc OpenRouter. Phần BCTC trong báo cáo thường niên được dựng thành bảng để định vị ô và kiểm đẳng thức. Luồng này dành cho **PDF**; dữ liệu BCTC quý lấy từ API Vietcap trong FinMind là một nguồn khác.

## Chuẩn bị

- Python và các gói trong `requirements.txt`.
- Poppler có `pdfinfo`, `pdftotext`, `pdftoppm` trong `PATH`.
- Tesseract có dữ liệu ngôn ngữ `vie` trong `PATH`.
- Nếu dùng `--gemini auto` hoặc `always`, cấu hình `GEMINI_API_KEY` trong `.env` của thư mục này. Có thể dùng `OPENROUTER_API_KEY` cho tuyến dự phòng. `.env` đã được Git bỏ qua.

```powershell
python -m pip install -r requirements.txt
```

## Chạy OCR và dựng IR

Chạy hoàn toàn cục bộ bằng Tesseract:

```powershell
python src/main.py "report.pdf" --gemini never --build-document-ir --out tmp/run
```

Chạy với tuyến AI khi trang OCR cần kiểm thêm:

```powershell
python src/main.py "report.pdf" --gemini auto --build-document-ir --out tmp/run
```

Kết quả nằm ở `tmp/run/report/`: `pages.jsonl` là bản ghi từng trang; `annual_ir/content/` là nội dung thường niên; `annual_ir/table/` là BCTC; `annual_ir/ocr_cell_review.json` liệt kê ô OCR cần rà soát. Ô có `needs_review` không được đưa vào đẳng thức như số đã xác nhận. Mẫu biểu chưa hỗ trợ được ghi `TEMPLATE_UNKNOWN` thay vì áp sai template.

Nếu đã có `pages.jsonl` và ảnh OCR trong thư mục `work/`, có thể chỉ dựng lại IR:

```powershell
python src/buildDocumentIr.py "FPT_2024_498332 (1).pdf" --pages-jsonl "ocr_router_out/FPT_2024_498332 (1)/pages.jsonl" --out tmp/fpt_2024_default
```

## Kết quả mặc định và dữ liệu override

Builder **không tự nạp** dữ liệu trong `overrides/` theo tên file, số trang hay SHA-256. SHA-256 chỉ dùng để kiểm rằng một override được chọn tường minh thuộc đúng PDF. Với bản FPT 2024 đã kiểm:

| Cách chạy | Nội dung thường niên | BCTC | KPI và bảng thường niên |
| --- | ---: | ---: | --- |
| Mặc định, không có `--overrides` | 138 trang IR | 67 trang, 9 trang bảng cấu trúc | 0 KPI `verified` |
| Truyền `--overrides overrides/fpt_2024.json` | 119 trang IR | 67 trang, 9 trang bảng cấu trúc | 30 KPI `verified`, 15 bảng thường niên từ dữ liệu rà soát |

Lệnh chạy override:

```powershell
python src/buildDocumentIr.py "FPT_2024_498332 (1).pdf" --pages-jsonl "ocr_router_out/FPT_2024_498332 (1)/pages.jsonl" --out tmp/fpt_2024_override --overrides overrides/fpt_2024.json
```

`annual_ir/index.json` ghi `overrides_applied: []` cho lần chạy mặc định; khi dùng lệnh trên, nó ghi `fpt_2024_reviewed`. Những con số 15 bảng và 30 KPI thuộc **lần chạy có override**, không phải kết quả tự động. Parser BCTC tổng quát khớp 278/278 ô của fixture 2024, nhưng fixture đó được tạo bằng pdfplumber và chỉ là kiểm thử hồi quy, không phải gold độc lập.

Profile `fpt_sidebar` chỉ được chọn khi trang có nhãn sidebar xanh phù hợp. Trang khác dùng `no_sidebar`; builder không cắt cố định 22% lề trái của chúng để phân loại BCTC.

## Kiểm chứng

```powershell
python tests/smoke_rebuild_committed.py
python -m unittest discover -s tests
python -m pytest -q
```

Smoke test dựng lại hai PDF FPT từ đầu vào đã commit, rồi so checksum JSON với `tests/fixtures/document_ir_snapshot.json` và SHA-256 template. Sau thay đổi R2 ngày 11/10/2026, smoke test đạt và hai lệnh test đều đạt 38/38.

Gold keyed theo báo cáo, mã và kỳ khớp 278/278 ô ở mỗi bản FPT theo phần **người làm tự kiểm**. `agreement_rate` thể hiện mức khớp đó; `gold_accuracy` chỉ có giá trị khi có kiểm độc lập. Xem `Gold_Set/R3_EVALUATION.md` và `R1_R7_VERIFICATION_20261011.md` để biết các cờ cần rà soát và giới hạn của BCTC scan/ngân hàng.
