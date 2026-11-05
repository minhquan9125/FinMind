# WBS03 – rule bảng công ty con/liên kết và registry r2 (04/11/2026)

## Vấn đề

Extractor cũ chỉ nhận **câu văn** và **danh sách dòng**. Quan hệ của FPT, CMG, CTG nằm trong
**bảng nhiều cột** (thuyết minh BCTC hợp nhất, bảng BCTN). Trong text chunk, một hàng bảng thành
nhiều dòng; tên pháp lý bị xen với cột địa chỉ/giấy phép/ngành nghề ("Công ty Cho" / "thuê tài
chính" / "TNHH MTV" / …), có menu trang chèn giữa, và nhãn loại ở tiêu đề mục chứ không ở từng hàng.
Đối chiếu nguồn chi tiết: `docs/sprint4/WBS03-FPT-CMG-CTG-source-review-20261104.md`.

## Đã sửa

| File | Thay đổi |
|---|---|
| `backend/src/sprint4_runtime/ownership_tables.py` | Rule mới cho bảng sở hữu (mô tả dưới) |
| `backend/src/sprint4_runtime/relation_extractor.py` | Gọi rule bảng; `extract_candidates(..., diagnostics=list)`; issuer theo mã CK khi tên DB không khớp alias |
| `backend/src/sprint4_runtime/company.registry.20261104.r2.json` | Registry r2 = r1 + `…r2.changes.json` |
| `backend/src/sprint4_runtime/company.registry.20261104.r2.changes.json` | Danh sách thay đổi có nguồn từng dòng |
| `backend/scripts/build_registry_revision.py` | Dựng r2 từ r1 + danh sách thay đổi; chặn alias trùng |
| `backend/scripts/extract_bctn_from_db.py`, `extract_bctn_relations.py` | Mặc định r2; ghi `<doc>.candidates.diagnostics.json` |
| `backend/tests/test_wbs03_ownership_tables.py` | 8 test (FPT/CTG/CMG layout, ca âm, cặp trùng, registry r2 tái lập) |

### Rule bảng (`ownership_tables.py`)

1. **Loại quan hệ chỉ từ tiêu đề mục** (cả dòng, hoặc sau ký hiệu "(ii)", "b."): "Công ty con",
   "(i) Công ty con trực tiếp", "(ii) Công ty liên kết trực tiếp", "Công ty liên doanh"
   (→ `HAS_ASSOCIATE`, `relation_label: "công ty liên doanh"`), "Các công ty con của X bao gồm:"
   (mẹ trung gian X). Tiêu đề gộp "Các công ty con, công ty liên kết" **không** định loại → hàng
   vào diagnostics `SECTION_KIND_AMBIGUOUS`. Tên cột "Công ty con" trong bảng liên kết không phải tiêu đề.
2. **Hàng** = dòng có tên pháp lý và kết thúc bằng tỷ lệ ("100% 100%", "45,66% (*)",
   "X% X% X% X%") hoặc "<Chủ sở hữu> sở hữu N% vốn góp". Tỷ lệ lấy cột đầu (kỳ hiện tại, sở hữu).
3. **Tên** = ghép phần đầu các dòng của hàng, phải **trùng đúng một alias verified** trong registry
   (dài nhất thắng; trùng hai thực thể → `CHILD_AMBIGUOUS`). Được bỏ tối đa 2 dòng liên tiếp
   thuộc cột khác, nhưng không bỏ dòng ngay sau dòng đầu. Không đoán ranh giới cột, không tạo ID.
   Tên chỉ gồm hình thức pháp lý + ngành ("Công ty Cổ phần Chứng khoán") bị bỏ qua. So khớp bỏ dấu
   gạch đứng riêng và mở rộng TMCP/CTCP.
4. **Ngày** = dòng tiêu đề bảng "Tại ngày 31/12/2025 [và 31/12/2024]" (cả dòng hoặc cuối dòng tên
   cột) hoặc hai kỳ "31.12.2025 31.12.2024". Ngày lẻ trong cột giấy phép không tính. Bảng không có
   ngày → `as_of: null` (không lấy năm báo cáo).
5. Mục còn mở được mang sang **trang kế tiếp** (bảng CTG trang 142→143); tiêu đề thuyết minh đánh số
   ("2.4. …") đóng mục. Menu trang ("06 QUẢN TRỊ CÔNG TY") bị bỏ.
6. Cặp đã có ứng viên từ rule khác trong cùng báo cáo → chỉ **thêm bằng chứng**, không tạo bản thứ
   hai (tránh xung đột giả ở WBS09 và giữ `relation_id` cũ).
7. Quote là đoạn đúng của chunk: dòng tiêu đề, dòng ngày, và các dòng của hàng tới dòng cuối tạo nên tên.

### Registry r2

- Gỡ alias "VietinBank Leasing" khỏi CTG (`CMP-c8ff5c1af9a79b27bdfb`), chuyển sang công ty con cho thuê tài chính.
- Thêm alias "Tập đoàn Công nghệ CMC" cho CMG (`CMP-bda9e53cfba37e417ef8`); tên cũ VBSE cho `CMP-1e129dd1c23200f469a7`.
- Thêm 36 công ty con/liên kết của FPT, CTG, CMG với tên pháp lý theo nguồn. ID mới theo quy tắc
  ghi trong `…r2.changes.json`.
- r1 giữ nguyên (gate WBS06 và 13 bản duyệt V4 vẫn dùng r1).

## Kết quả chạy lại (corpus `b2550a0b…`, chỉ đọc DB)

`backend/.tmp/wbs03-candidates-20261104-tables/` (Git ignore): **69 ứng viên PENDING** (trước: 23).

- 23 ứng viên cũ: giữ nguyên `relation_id` và nội dung; hai ứng viên TCB→TechAMC thêm bằng chứng từ bảng.
- 46 ứng viên mới, không có cặp trùng trong cùng báo cáo:

| BCTN | Mới | Ghi chú |
|---|---:|---|
| FPT 2025 | 10 | 8 con + 2 liên kết, `as_of` 2025-12-31, khớp bảng đối chiếu tay |
| FPT 2024 | 10 | 8 con + 2 liên kết, `as_of` 2024-12-31 |
| CTG 2025 | 9 | 8 con + Indovina (liên doanh) 50%, `as_of` 2025-12-31 |
| CTG 2024 | 8 | 8 con, `as_of` 2024-12-31 |
| CMG 2025 | 8 | Chỉ các hàng dưới "Các công ty con của X bao gồm:" (mẹ CMC Global/CMC Education/CMC Uni); `as_of` null |
| CMG 2024 | 1 | Rule cũ, đối tượng chưa resolve (tên 2024 "CMC AI Digital Infrastructure") |

Diagnostics (hàng bảng không thành ứng viên): CMG 2025 12 `SECTION_KIND_AMBIGUOUS`; MBB 2025 4
ambiguous + 4 `CHILD_UNRESOLVED`; VCB 2024/2025, TCB 2025 vài `CHILD_UNRESOLVED`; CMG 2024 1
`PARENT_UNRESOLVED`.

Kiểm thử: 78 test WBS03/WBS08/WBS09; 1.036 test router, WBS06, person-role đạt.

## Khi DB có dữ liệu mới

1. Chạy `extract_bctn_from_db.py` sang thư mục output mới.
2. Mở các file `*.diagnostics.json`:
   - `CHILD_UNRESOLVED` / `PARENT_UNRESOLVED`: tên chưa có trong registry → đối chiếu nguồn, thêm vào
     một `…rN.changes.json` mới, chạy `build_registry_revision.py`, đổi mặc định CLI. Không sửa r cũ.
   - `SECTION_KIND_AMBIGUOUS`: tài liệu không phân loại ở bảng đó → tìm bảng thuyết minh phân loại
     rõ, hoặc để WBS06 quyết. Không thêm rule gán loại theo tỷ lệ %.
   - `CHILD_IS_PARENT`, `CHILD_AMBIGUOUS`: kiểm alias registry bị đặt nhầm/trùng.
3. Mọi ứng viên vẫn `PENDING`; WBS06 duyệt trước khi WBS09 nạp graph.

## Còn mở

- CMG: thuyết minh trang 88–90, 109 trong snapshot là OCR lỗi dấu, nên các hàng trực tiếp của CMG
  (CMC TS, CMC Telecom, NetNam…) chưa có nguồn phân loại đọc được. Cần WBS01 re-snapshot OCR sạch.
- CMG: bảng BCTN không có ngày; năm tài chính kết thúc 31/03/2026.
- CMC Malay: BCTN ghi mẹ CMC Global, thuyết minh ghi CMC-APAC → WBS06 quyết.
- Registry có hai ID cho FTEL (`CMP-7097a7e10282f47ca683`, `CMP-7159a1a0f4ea52a1ffd3`); chưa gộp.
- Rule bảng neo vào registry: công ty con mới chưa có trong registry sẽ nằm ở diagnostics, không tự xuất.

## Bổ sung kiểm tra dòng bảng sau review ngày 04/11

Ba ca thử bổ sung cho thấy rule bảng trước đây còn nhận câu phủ định/dự kiến,
lấy phần trăm đầu tiên khi cột biểu quyết đứng trước sở hữu, và khớp tên dài
vào prefix của một tên registry ngắn hơn. Đây là lỗi tái hiện trên ca thử;
không phải kết luận 69 ứng viên của lượt Hưng đều sai.

Đã bổ sung trong `ownership_tables.py`:

- Dòng chứa phát biểu phủ định, dự kiến, điều kiện hoặc quan hệ đã chấm dứt
  được đưa vào diagnostics `RELATION_NOT_CURRENT_OR_ASSERTED`. Chỉ kiểm phần
  dòng thuộc quan hệ và dòng trạng thái nối ngay sau đó; từ “không dây” trong
  ngành nghề và “trước đây là Công ty…” trong giấy phép không tự chặn quan hệ.
- Lấy tỷ lệ theo nhãn cột sở hữu/biểu quyết, kể cả tiêu đề xuống dòng hoặc
  xếp nhiều tầng. Thêm quote của tiêu đề cột vào evidence. Câu “X sở hữu N%”
  tự xác định đại lượng. Nếu không xác định được cột sở hữu, vẫn giữ quan hệ
  được nêu rõ nhưng bỏ `ownership_percent` và ghi `OWNERSHIP_COLUMN_UNRESOLVED`
  với `candidate_emitted: true`; đây là cảnh báo, không phải dòng bị loại.
- Kiểm tra phần chữ ngay sau tên registry. Hậu tố chưa xác minh như “Miền Nam”
  hoặc “Beta” không được gán vào ID của tên ngắn. Tên dài đã có registry thì
  ưu tiên khớp tên dài. Giữ các ranh giới cột rõ như giấy phép, hoạt động,
  địa chỉ có nhãn và tên viết tắt được tách cột; trường hợp chưa rõ ghi
  `CHILD_NAME_BOUNDARY_UNCLEAR`. Đây vẫn là rule theo text, không phải bộ đọc
  bố cục tổng quát cho mọi PDF.

`extract_bctn_from_db.py` phân biệt `unresolved_table_rows` (dòng bị bỏ)
với `table_warnings` (ứng viên giữ lại nhưng thiếu tỷ lệ). JSON contract,
registry r2 và quyết định WBS06 không đổi.

Kiểm chứng tại máy Nhân:

- 243 test WBS03/graph/router liên quan đạt, trong đó file test bảng có 18 test.
- Chạy lại offline trên 20 JSON của
  `backend/.tmp/wbs03-candidates-20261103-gapcheck/` chứa 17.664 chunk thật
  đã được reader xác minh ở lượt trước, đối chiếu với bản Hưng chạy cùng đầu
  vào và registry r2: **69 → 69**, không thêm/mất ID hoặc thay đổi thuộc tính
  quan hệ. Evidence được bổ sung tiêu đề cột; diagnostics có thể đổi lý do.
- Báo cáo local: `backend/.tmp/wbs03-ownership-guards-replay.json` (Git ignore).
  Đây là chạy lại trên bản lưu; không phải một lượt xác minh DB live mới,
  không ghi PostgreSQL/Neo4j và không phê duyệt 69 ứng viên.
