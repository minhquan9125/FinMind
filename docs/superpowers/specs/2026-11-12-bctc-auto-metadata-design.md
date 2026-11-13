# Thiết kế: hệ thống tự lấy và xác minh metadata BCTC, lưu trong DB kèm link nguồn

Ngày 12/11/2026. Trạng thái: chờ user duyệt.

## Mục đích

Bộ tính sức khỏe tài chính (`backend/src/financial/health.py`, `peers.py`) hiện trả `insufficient_data` cho mọi chỉ tiêu của 10 mã. Lý do: số Vietcap trong DB thiếu 5 loại metadata đã được xác minh:
- đơn vị;
- phạm vi hợp nhất hay riêng;
- kỳ quý riêng hay lũy kế, và năm tài chính;
- trạng thái kiểm toán;
- cơ sở so sánh.

User muốn:
1. Hệ thống **tự** lấy dữ liệu từ nguồn trên mạng, không dựa vào file có sẵn trên máy.
2. Bộ tính **chỉ đọc dữ liệu trong DB**.
3. Lưu **link tài liệu gốc** cho từng kỳ, để sau này hiện dưới mỗi câu trả lời của chatbot.
4. **Giữ lịch sử**: chỉ ghi thêm, không ghi đè.
5. Thêm đúng 1 bảng mới cho kết quả xác minh (phương án A). Mọi thứ khác dùng lại bảng có sẵn.

Khi xong, BCTC kết hợp được với xu hướng giá (đã có) để trả lời "công ty mạnh hay yếu, giá đang xu hướng gì".

## Nguồn (user đã cho phép dùng ngày 12/11)

- **VIETCAP_VCI** (đang dùng): số liệu BCTC theo quý và năm. Mỗi kỳ có `yearReport`, `lengthReport` (1–4 là quý, 5 là năm), `publicDate`, `updateDate`. Giá trị là VND tuyệt đối.
- **Vietstock Finance** (mới), cùng giao diện website với `data_pipeline/annual_reports/vietstock_download_annual.py`:
  - `/data/getrptdoctype`: loại 1 là "Báo cáo tài chính".
  - `/data/getrptterm`: các kỳ Năm=1, Q1=2, Q2=3, Q3=4, Q4=5, 6T=9, 9T=12.
  - `/data/getrptfile`: mỗi kỳ trả file "BCTC Hợp nhất …" và "BCTC Công ty mẹ …", tên có "Kiểm toán" hoặc "Soát xét", kèm `Url` (static2.vietstock.vn), `FileInfoID`, `LastUpdate`.
  - Đã probe danh mục FPT 2025 ngày 12/11, chưa tải file.
- Đây là giao diện website, không phải API có tài liệu. Giữ nhịp gọi chậm, không vượt đăng nhập hay CAPTCHA, chỉ theo link thuộc vietstock.

**Trên web không cần ghi tên Vietstock hay Vietcap** (yêu cầu của user). Dưới câu trả lời chỉ hiện tên tài liệu, ví dụ "BCTC hợp nhất quý 3/2025 – FPT", kèm link. User đồng ý ngày 12/11: link được trỏ tới static2.vietstock.vn. Trên web, link hiện dạng hyperlink có chữ là tên tài liệu; không in URL hay tên miền ra màn hình. Người dùng chỉ thấy tên miền khi bấm vào hoặc rê chuột lên link.

## Mục tiêu

1. Tự động thu danh mục BCTC (Vietstock) và số liệu (Vietcap) cho danh sách mã cấu hình, mặc định 10 mã: VCB, BID, CTG, MBB, TCB, FPT, CMG, ELC, ITD, ICT.
2. Với mỗi mã và kỳ, xác minh rồi ghi vào DB:
   - phạm vi;
   - kiểm toán/soát xét;
   - đơn vị;
   - kỳ quý riêng/lũy kế;
   - ngày kết thúc năm tài chính.
   Mỗi kết luận có bằng chứng: link, mã băm file, số trang, đoạn chữ trích, kết quả phép kiểm.
3. Ghi số kỳ mới (ví dụ 2026-Q3) vào DB theo kiểu chỉ thêm. Số của một kỳ đã có mà nguồn sửa lại thì thành phiên bản mới, giữ bản cũ.
4. `health_store.py` đọc metadata đã xác minh từ bảng mới. Kỳ nào đủ điều kiện thì bộ tính cho kết quả thật.
5. Có hàm trả link trích dẫn (tên tài liệu, url, trang) cho một số liệu, để chatbot dùng sau.
6. **Truy xuất vector, cách 1 (user chọn ngày 12/11).** [db_chunking.py](../../../backend/src/documents/db_chunking.py) cùng câu SQL cấp dữ liệu (`db_source.py`) đọc thêm bản xác minh hiện hành và `documents.source_url`.
   - Đầu đoạn ghi phạm vi, đơn vị, kỳ đã xác minh.
   - Phần trỏ nguồn (`locator`) thêm `source_url`, `title`, `page` để chatbot hiện link.
   - Kỳ chưa xác minh thì giữ như hiện nay và ghi rõ "chưa xác minh".
   - `chunk_id` sinh theo nội dung, nên đoạn mới tự có id mới; đoạn cũ giữ nguyên.
   - Không đưa chữ PDF vào vector trong đợt này.
7. **Phạm vi lấy dữ liệu cũ:** 10 mã, kỳ năm 2024–2025 và các quý từ 2025-Q1 đến 2026-Q3, khoảng 180 PDF. Đủ để so cùng kỳ năm trước. Kỳ cũ hơn để sau. (Đề xuất của Claude; user chưa phản đối.)
8. Chạy theo lịch:
   - hằng ngày lúc 18:00 trong mùa nộp BCTC: 15/01–15/02, 15/04–15/05, 15/07–20/08, 15/10–15/11;
   - ngoài mùa: thứ Hai hằng tuần lúc 18:00.

## Không làm trong đợt này

- Không sửa luồng chatbot hay giao diện. Chỉ chuẩn bị dữ liệu và hàm lấy link.
- Không xác minh định nghĩa tỷ số do nguồn tính sẵn (`SOURCE_NATIVE`). Bộ tính tự tính ROE/ROA từ số gốc đã xác minh nếu cần; tỷ số của nguồn vẫn coi là chưa xác minh.
- Không mở rộng sang 24 mã còn lại của rổ giá. Danh sách mã là cấu hình, thêm sau.
- Không bóc bảng số từ PDF thành dữ liệu. PDF chỉ dùng làm bằng chứng đối chiếu.
- Không đưa chữ của PDF BCTC (thuyết minh, giải trình) vào vector, tức cách 2. Đợt sau dùng lại chính các PDF và dòng `documents` này.

## Điều tuyệt đối tránh

- Ghi đè hoặc xóa số liệu, metadata đã lưu.
- Đánh dấu "đã xác minh" khi phép kiểm chưa đạt. Không chắc thì để `UNKNOWN` và ghi vào `quarantine_records`, không đoán.
- Dùng importer cũ (`import_clean_financials.py --apply`, kiểu upsert ghi đè).
- Lưu hay in mật khẩu, khóa.

## Dùng lại bảng có sẵn

| Bảng | Dùng cho |
|---|---|
| `sources` | Thêm dòng nguồn Vietstock BCTC. Cập nhật `approval_status` của VIETCAP_VCI và Vietstock theo cho phép của user ngày 12/11, ghi lý do vào `scope_note`. |
| `ingestion_jobs` | Mỗi lần chạy một dòng: trạng thái, số bản ghi đạt và bị cách ly. |
| `raw_payloads` | Lưu nguyên JSON phản hồi danh mục Vietstock và số liệu Vietcap, kèm `sha256` và `source_uri`. |
| `documents` | Mỗi file PDF BCTC một dòng: `doc_type='FINANCIAL_STATEMENT'`, `file_type='PDF'`, `title` lấy theo tên của nguồn, `source_url` là link hiện cho người dùng, `external_id` là `FileInfoID`, `published_at` là `LastUpdate`, `sha256` (đã có unique index), `page_count`, `company_id`, `period_id`. Nguồn thay file thì mã băm khác, thành dòng mới; dòng cũ giữ nguyên. Các dòng FINANCIAL_STATEMENT cũ (`file_type='DB'`) không bị đụng. |
| `reporting_periods` | Dùng `period_code` có sẵn. Thiếu kỳ thì thêm. |
| `financial_reports` | Kỳ mới thì thêm dòng. Số của một kỳ đã có mà nguồn sửa lại thì thêm dòng với `report_version` + 1 và `restated_from_id` trỏ về bản trước. Cột `statement_scope` cũ chứa tên bảng (INCOME_STATEMENT…), giữ nguyên ý nghĩa đó. |
| `observations` | Số liệu của dòng `financial_reports` mới. Dòng cũ không sửa. |
| `quarantine_records` | Kỳ xác minh lệch hoặc không đọc được, kèm `reason_code`. |

Link trích dẫn đi theo mẫu đang có ở `graph_viewer.py` và `wbs03_repository.py`: `documents.source_url` cộng số trang.

## Bảng mới duy nhất: `financial_report_verifications` (chỉ ghi thêm)

| Cột | Ý nghĩa |
|---|---|
| `verification_id` uuid PK | |
| `report_id` uuid | Trỏ `financial_reports`: kỳ số Vietcap được xác minh. |
| `document_id` uuid | Trỏ `documents`: PDF dùng làm bằng chứng. |
| `job_id` uuid | Trỏ `ingestion_jobs`. |
| `statement_scope` | `CONSOLIDATED` / `SEPARATE` / `UNKNOWN`. |
| `audit_status` | `AUDITED` / `REVIEWED` / `NOT_STATED` / `UNKNOWN`. |
| `unit`, `unit_status` | Ví dụ `VND` và `VERIFIED` / `UNKNOWN`. |
| `period_basis` | `ANNUAL` / `STANDALONE_QUARTER` / `YEAR_TO_DATE` / `UNKNOWN`. |
| `period_start`, `period_end`, `fiscal_year_end` | Ngày. |
| `checks` jsonb | Kết quả từng phép kiểm, kèm số liệu đầu vào. |
| `evidence` jsonb | Danh sách {trang, đoạn trích, giá trị tìm thấy}. |
| `status` | `VERIFIED` / `PARTIAL` / `MISMATCH`. |
| `verified_at` | Thời điểm ghi. |
| `supersedes_id` uuid | Trỏ lần xác minh trước của cùng `report_id`. |

Bản ghi hiện hành của một kỳ là dòng mới nhất theo `verified_at`. Không có UPDATE hay DELETE.

## Cách xác minh mỗi kỳ

1. **Phạm vi và kiểm toán** lấy từ tên file trong danh mục:
   - "Hợp nhất" là `CONSOLIDATED`;
   - "Công ty mẹ" hoặc "Riêng"/"Riêng lẻ" là `SEPARATE`;
   - "Kiểm toán" là `AUDITED`, "Soát xét" là `REVIEWED`, không ghi gì là `NOT_STATED`.
2. **Số Vietcap thuộc phạm vi nào:** tải PDF hợp nhất (và PDF riêng nếu cần), đọc chữ bằng `pypdf`, tìm 3 giá trị chính trong chữ PDF:
   - doanh thu thuần, hoặc tổng thu nhập hoạt động với ngân hàng;
   - lợi nhuận sau thuế;
   - tổng tài sản.
   Giá trị tìm theo các cách viết số kiểu Việt Nam (dấu chấm phân cách nghìn), ở đơn vị đồng và triệu đồng. File nào tìm thấy đủ 3 thì số Vietcap thuộc phạm vi của file đó. Ghi lại trang và đoạn trích.
3. **Đơn vị:** dòng "Đơn vị tính: …" ở trang có số. Số tìm thấy ở cách viết đồng hay triệu phải khớp đơn vị ghi trên trang. Số Vietcap lưu theo đồng.
4. **Kỳ:**
   - Kỳ năm: `ANNUAL`.
   - Kỳ quý: `STANDALONE_QUARTER` khi tổng 4 quý của năm lệch số năm trong ngưỡng 3% ở 3 chỉ tiêu trên. Đã thử: FPT ≤0,3%, BID ≤2,8% cho 2018–2025; phần lệch là điều chỉnh sau kiểm toán.
   - Năm chưa đủ 4 quý: `STANDALONE_QUARTER` khi giá trị quý tìm thấy trong PDF quý ở cột của quý, không phải cột lũy kế. Không tìm thấy thì `UNKNOWN`.
5. **Năm tài chính:** đọc "cho năm tài chính kết thúc ngày …" hoặc "cho kỳ … kết thúc ngày …" trong vài trang đầu (ví dụ CMG kết thúc 31/03). Không có thì `UNKNOWN`.
6. **Đánh giá:**
   - Đủ 1–5 thì `VERIFIED`.
   - Có cái đạt, có cái `UNKNOWN` thì `PARTIAL`.
   - Có số lệch thì `MISMATCH`, đồng thời ghi `quarantine_records`.
7. PDF scan không có lớp chữ: dùng OCR sẵn có (`OCR_annuals.py`, Tesseract) nếu máy có cài; không có thì `PARTIAL` với lý do `NO_TEXT_LAYER`.

## File PDF lưu ở đâu

Cache cục bộ trong thư mục gitignore `data/references/vietstock/financial_statements/files/<MÃ>/<KỲ>/`. DB giữ link, mã băm và số trang, là nguồn sự thật. Mất cache thì job tự tải lại theo link và kiểm lại mã băm. (Quyết định của Claude.)

## Lịch chạy

Gắn vào scheduler sẵn có của backend (`backend/src/market_data/app.py`, nơi đang chạy refresh giá 15:35), theo lịch ở mục tiêu 8. Có lệnh chạy tay `--apply` và chế độ chạy thử không ghi. Báo cáo mỗi lần chạy lưu ở `outputs/financial-refresh/<thời điểm>/`, giống phần giá. Trạng thái lần chạy gần nhất hiện trong `/live/status`.

## Phương án đã cân nhắc

- **A, được chọn:** một bảng xác minh mới chỉ ghi thêm; số liệu cũ không đụng; dùng lại các bảng khác.
- **B:** dùng `report_version` để chép lại toàn bộ số mỗi lần xác minh. Không cần migration, nhưng nhân đôi khoảng 308 nghìn dòng mỗi lần, và cột `statement_scope` cũ dễ lẫn nghĩa.
- **C:** dùng bảng `evidence`. Không cần migration, nhưng trộn vào luồng trích dẫn của chatbot.

User chọn A, kèm yêu cầu dùng lại bảng có sẵn tối đa.

## Quyết định của Claude sau lượt review (user kiểm khi đọc)

1. **`comparison_basis`**: thêm cột `comparison_basis` vào bảng mới.
   - Ghi `AS_REPORTED` khi số kỳ trước trong DB tìm thấy ở cột so sánh của PDF kỳ này.
   - Tìm thấy nhưng khác thì ghi `RESTATED`; bộ tính không so cặp kỳ đó (trường hợp FPT 2026).
   - Không có PDF kỳ này thì ghi `UNKNOWN`.
2. **Năm tài chính lệch lịch (CMG):**
   - Thêm cột `fiscal_label_convention` (`CALENDAR` / `START_YEAR` / `END_YEAR`). Suy từ PDF: năm của ngày kết thúc trùng `yearReport` thì là `END_YEAR`, nhỏ hơn 1 thì là `START_YEAR`. Không chắc thì để `UNKNOWN`.
   - `fiscal_year_end` lưu dạng `MM-DD` như bộ tính đang dùng.
3. **Dùng bản `PARTIAL`**: `health_store` dùng từng trường riêng. Trường nào có phép kiểm riêng đạt thì dùng; trường `UNKNOWN` thì bộ tính tự loại kỳ đó như hiện nay.
4. **Không tìm thấy giá trị trong PDF thì là `UNKNOWN`, không phải `MISMATCH`.** Chỉ ghi `MISMATCH` khi tìm thấy giá trị cùng chỉ tiêu nhưng khác số.
   - Ngân hàng không có dòng "tổng thu nhập hoạt động" trong PDF thì dùng lợi nhuận sau thuế, tổng tài sản và vốn chủ để xác định phạm vi.
5. **Khi nào coi là nguồn sửa số**: một giá trị của cùng mã, kỳ, chỉ tiêu khác bản đang lưu. Chỉ đổi `updateDate` mà số không đổi thì không tạo phiên bản. Phiên bản mới phải xác minh lại, không kế thừa xác minh cũ.
6. **Ánh xạ sang bộ tính**: `ANNUAL` thành `YEAR`, `STANDALONE_QUARTER` thành `QUARTER`. Chỉ tiêu bảng cân đối kế toán thành `INSTANT`.
7. Một PDF dùng cho nhiều kỳ (unique index theo `sha256`) thì dùng chung một dòng `documents`. Nhiều dòng xác minh cùng trỏ vào nó.

## Kết quả kiểm schema thật trên VPS (12/11, chỉ đọc)

- Các bảng dùng lại có trên VPS, cột khớp `docker/postgres/init/010_schema.sql`. Riêng `quarantine_records` có thêm `reasons` jsonb, `candidate_payload`, `evaluation_payload`, `review_id`; ghi lý do lệch vào `reasons`.
- Số liệu cũ **có nguồn đầy đủ, không cần thu lại**:
  - 1.638/1.638 `financial_reports` có `payload_id` và `job_id`. Chúng trỏ tới 10 `raw_payloads` (mỗi mã một payload), nhập ngày 29/10/2026, đều có `sha256` và nội dung.
  - Payload còn `publicDate` và `updateDate`.
  - Bản xác minh trỏ thẳng vào `report_id` cũ.
- **Đối chiếu từng số (12/11, chỉ đọc):**
  - **DB so với gói thô:** cả 308.546 dòng `observations` đều tìm được giá trị gốc trong `raw_payloads`, và không có số nào trong gói thô thiếu trong DB. 298.654 dòng khớp tuyệt đối. 9.892 dòng lệch, toàn bộ là nhiễu do importer cũ đổi qua float: 9.886 dòng tỷ số `SOURCE_NATIVE` và 6 dòng EPS `VND_PER_SHARE`. Mọi số tiền VND khớp tuyệt đối.
  - Builder: phép so số với PDF phải dùng giá trị trong gói thô, hoặc làm tròn về số chữ số của gói thô, không dùng giá trị float trong `observations`.
  - **Gói thô so với API gọi lại sáng 12/11:** đã so FPT ở 3 bảng và BID bảng kết quả kinh doanh. Cả 42 kỳ đã có đều giống hệt, chỉ có thêm 1 kỳ mới (2026-Q3). Chưa so 8 mã còn lại.
- `financial_reports`:
  - `document_id` trống ở mọi dòng; liên kết PDF đi qua bảng mới.
  - `report_version`=1 ở mọi dòng, chưa có `restated_from_id`.
  - `audit_status`=`UNKNOWN` ở mọi dòng.
  - Không có ràng buộc unique theo (công ty, kỳ, bảng, phiên bản), nên code ghi phải tự chặn trùng.
- `reporting_periods` dùng chung cho mọi công ty, ngày theo năm dương lịch (ví dụ `2025-YEAR` = 01/01–31/12). Vì vậy ngày thực của kỳ CMG phải lấy từ `period_start`/`period_end` trong bảng xác minh, không lấy từ bảng kỳ.
- `observations.locator_json` chỉ có `dataset_version`, `ratio_type`, `source_field`, `source_section`; chưa có metadata nào.
- `text_chunks` đã có `superseded_at` và `superseded_by_chunk_id`. Đoạn vector mới (mục tiêu 6) thay đoạn cũ bằng cột này, không xóa.
- `documents.sha256` có unique index. Không có dòng `FINANCIAL_STATEMENT` nào dạng PDF (3.695 dòng đều `file_type='DB'`).
- `sources`:
  - Chưa có nguồn Vietstock BCTC.
  - VIETCAP_VCI là `PENDING`, `is_enabled=false`.
  - Có thêm dòng "VIETCAP_VCI publicDate metadata" (`UNREVIEWED`, enabled).
  - Không code runtime nào đọc `is_enabled`. Chỉ `approval_status` có tác dụng: `health.py:151` trả `complete` khi mọi số có nguồn `APPROVED`, ngược lại trả `provisional`.
  - Đổi VIETCAP_VCI sang `APPROVED` theo cho phép của user. Nguồn giá ENTRADE và vnstock_kbs giữ nguyên `PENDING`, vì user chưa nói tới.
- Schema `public` không có công cụ migration. Chỉ `research_chat` có `schema_migrations`. Bảng mới viết thành file SQL trong `supabase/migrations/`, đồng thời cập nhật `docker/postgres/init/010_schema.sql`; áp lên VPS một lần sau khi user duyệt.

## Để builder tự quyết

- Kiểm schema thật trên VPS trước khi viết migration. Bản `docker/postgres/init/010_schema.sql` có thể khác VPS về tên bảng, cột hoặc index.
- Mã định danh nguồn ICT trên Vietcap là `CTIN`; dùng alias đã có trong `financial_capture.py`.
- Nhịp gọi Vietstock: tối thiểu 1 giây mỗi request.
- Ngưỡng lệch tổng quý: 3%, kèm test.
