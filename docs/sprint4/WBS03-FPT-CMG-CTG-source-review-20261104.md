# WBS03 – đối chiếu nguồn quan hệ doanh nghiệp FPT, CMG, CTG (BCTN 2025)

Ngày 04/11/2026 · người đối chiếu: Hưng (WBS09) · đầu vào cho WBS03 sửa rule và chạy lại.
Chỉ đọc PDF, OCR trên máy và DB (transaction read-only qua tunnel VPS). **Không ghi DB, không
nạp Neo4j, không sửa registry.** Mọi quan hệ dưới đây vẫn là **ứng viên**, phải qua WBS06
(Huyền) duyệt trước khi vào graph.

## 1. Xác nhận nguồn: PDF ↔ OCR ↔ snapshot corpus `b2550a0b-c423-5c50-9b15-6fb6af12e2c6`

| Mã | PDF (sha256) | `source.json` OCR | `pdf_sha256` trên locator chunk DB | document_id trong corpus | Thuộc corpus |
|---|---|---|---|---|---|
| FPT | `5ea9b229656594f65e858ff7465ec600332fd623c501ce27d5b95de098275a35` | khớp | khớp | `c5eb8271-54db-5e8d-8790-cdcf3ad86757` | có |
| CMG | `4ed2a0ed75c3585adbf1925b0ce210d03d48142adc54f0a386553041c9c55f56` | khớp | khớp | `532597dc-7b79-5f00-99f9-d3394cba9038` | có |
| CTG | `bb4d98a8b3e7122f5cc8c73d9e9fdf7d34652d68e0094307bcad99e5792f5650` | khớp | khớp | `26c58a92-9b65-5ce3-a1c2-5f3b71717ddc` | có |

- `FPT/.../annual_ir/content/p-032.ir.json`: `source.document_sha256` = PDF FPT, `engine: TEXT_LAYER`,
  bbox theo pt của trang PDF (1058,27 × 595,28). Đã đối chiếu vị trí bằng text layer PDF (pypdf):
  từng số vốn/tỷ lệ nằm đúng cột như bbox IR.
- `CMG/.../work/p-008.png`: pipeline không ghi hash ảnh (`pages.jsonl`, `summary.json` không có
  trường này), nên **không kiểm được bằng hash**. Nội dung ảnh khớp `text/p-008.txt`, và text đó
  khớp 12/12 dòng của chunk DB `01b50d4b…` → khớp về nội dung.
- So tập từ giữa text OCR trên máy và text chunk DB dựng lại (`read_annual_chunk`) của từng trang
  bằng chứng:

| Trang | Khớp | Ghi chú |
|---|---|---|
| FPT 32, 175, 176; CMG 7, 8, 9, 88, 109 | 100% | Cùng từ, khác thứ tự dòng |
| CTG 8, 142, 143, 159 | ≥ 99,5% | Snapshot tách số "7"/"1" khỏi tiêu đề trang 8 |
| CTG 63 (86–92%), CTG 169 (96,7%) | lệch nhẹ | Text OCR trên máy lỗi font ("èồng", "ph p"); **snapshot DB sạch hơn** |
| **CMG 89 (≈40%)** | **lệch** | **Snapshot DB là OCR lỗi dấu** ("Cong ty Co phn…"); `text/p-089.txt` trên máy đã OCR lại sạch. Bằng chứng phải trích từ chunk DB, không từ file trên máy |

Kết luận: ba PDF và JSON/ảnh OCR là **cùng tài liệu** với snapshot corpus. Text OCR trên máy
**không phải** bản đã nạp vào corpus: cùng nguồn, nhưng khác lượt làm sạch/OCR ở vài trang
(CMG 89; CTG 63, 169). Rule WBS03 chạy trên text chunk DB.

## 2. Bảng quan hệ

Quy ước: **trang** là số trang PDF (số in trên trang ghi trong ngoặc). `chunk` là `chunk_id` trong
corpus `b2550a0b…` chứa đoạn trích. Mức chắc chắn: **Cao** = thuyết minh BCTC hợp nhất đã
kiểm toán ghi rõ, khớp BCTN; **TB** = một nguồn, hoặc thiếu ngày, hoặc lệch số; **Thấp** = các
nguồn mâu thuẫn.

### 2.1 FPT — Công ty Cổ phần FPT (`CMP-fbb705553b47c681f6ae`)

Nguồn chính: thuyết minh 1 BCTC hợp nhất, trang 175–176 (in 173–174), bảng "Tại ngày 31/12/2025
và 31/12/2024" (`p175-b34`, chunk `9863814b-16d3-5e90-aa59-2a27529870f6`). Đối chiếu: sơ đồ tổ
chức trang 32 (in 30), câu `p32-b4` *"tính đến thời điểm 31/12/2025, mô hình hoạt động của Tập
đoàn gồm 08 công ty con trực tiếp và 02 công ty liên kết chính"* (chunk `a43e3627-d8c0-57e9-bbbf-b0c57c3c5bb1`;
trong snapshot câu này bị xen dòng menu: "08 công / … / ty con").

| # | Loại | Công ty (tên pháp lý) | Registry r1 | Tỷ lệ sở hữu / biểu quyết | as_of | Bằng chứng (trang · block · chunk) | Chắc chắn |
|---|---|---|---|---|---|---|---|
| F1 | HAS_SUBSIDIARY | Công ty TNHH Phần mềm FPT | chưa có | 100% / 100% | 2025-12-31 | 175 · `p175-b7`, `p175-b37`, `p175-b36` · `c0648c1c-8b58-5d47-8962-6b61d0bbbaa0`; sơ đồ 32 `p32-b6` "FPT Software", 100% | Cao |
| F2 | HAS_SUBSIDIARY | Công ty Cổ phần Viễn thông FPT | `CMP-7097a7e10282f47ca683` | 45,66% / "(*)" | 2025-12-31 | 175 · `p175-b9`, `p175-b11`, `p175-b39`, `p175-b38` · `c0648c1c…`; chú thích 176 `p176-b7`, `p176-b8`, `p176-b19` · `6c2dd115-519b-5027-b8b3-22b855d3cf72` | Cao, kèm ghi chú (a) |
| F3 | HAS_SUBSIDIARY | Công ty TNHH FPT IS | chưa có | 100% / 100% | 2025-12-31 | 175 · `p175-b14`, `p175-b41`, `p175-b40` · `95cd3b85-de59-5fc1-bd94-c6a9bd844d5d` | Cao |
| F4 | HAS_SUBSIDIARY | Công ty TNHH Giáo dục FPT | chưa có | 100% / 100% | 2025-12-31 | 175 · `p175-b17`, `p175-b43`, `p175-b42` · `95cd3b85…` | Cao |
| F5 | HAS_SUBSIDIARY | Công ty Cổ phần Dịch vụ Trực tuyến FPT | chưa có | **49,52% / 80,15%** | 2025-12-31 | 175 · `p175-b19`, `p175-b45`, `p175-b44` · `95cd3b85…` | Cao (b) |
| F6 | HAS_SUBSIDIARY | Công ty TNHH Đầu tư FPT | chưa có | 100% / 100% | 2025-12-31 | 175 · `p175-b21`, `p175-b47`, `p175-b46` · `7f0c77bf-9185-5001-8553-ec76acb247f1` | Cao |
| F7 | HAS_SUBSIDIARY | Công ty TNHH FPT Smart Cloud | chưa có | 100% / 100% | 2025-12-31 | 175 · `p175-b22`, `p175-b49`, `p175-b48` · `7f0c77bf…` | Cao |
| F8 | HAS_SUBSIDIARY | Công ty TNHH FPT Digital | chưa có | 100% / 100% | 2025-12-31 | 175 · `p175-b24`, `p175-b51`, `p175-b50` · `7f0c77bf…` | Cao (c) |
| F9 | HAS_ASSOCIATE | Công ty Cổ phần Synnex FPT | chưa có | 48% / 48% | 2025-12-31 | 176 · tiêu đề `p176-b9` "(ii) Công ty liên kết trực tiếp" (chunk `6c2dd115…`), `p176-b11`, `p176-b25`, `p176-b26` · `b4686726-982d-5e7c-a818-99adb0dc257e` | Cao (d) |
| F10 | HAS_ASSOCIATE | Công ty Cổ phần Bán lẻ Kỹ thuật số FPT | `CMP-7356238c7b172d16f5d3` | 46,54% / 46,54% | 2025-12-31 | 176 · `p176-b12`, `p176-b28`, `p176-b29` · `b4686726…`; sơ đồ 32 "FPT Retail" 46,54% (`p32-b40`, chunk `4f57fdfa-0f83-5157-819d-872c5edf505f`) | Cao |

Cách tách sơ đồ trang 32 (cho rule, không dùng làm nguồn duy nhất):
- Hai cột tiêu đề: `p32-b26` "CÔNG TY CON" (x 642–709), `p32-b25` "CÔNG TY LIÊN KẾT" (x 758–843).
- Hàng y≈380: FPT Software (x 262–321), FPT IS (364–391), FPT Digital (438–485),
  FPT Smart Cloud (524–598) thuộc khối công ty con; Synnex FPT (772–822) thuộc cột liên kết.
- Block gộp `p32-b10` tách theo x của text layer: 7.750 tỷ (x 250) → Software; 1.500 tỷ (x 335)
  → IS; 60 tỷ (x 426) → Digital; 1.000 tỷ (x 520) → Smart Cloud. "Tỷ lệ sở hữu: 100%" ở x 261
  thuộc Software; `p32-b11`/`b12`/`b33` thuộc IS/Digital/Smart Cloud; `p32-b34` 48,00% thuộc Synnex.
- Hàng y≈453: FPT Online (`p32-b14`: 184,71 tỷ, 49,52%), FPT Telecom (`p32-b37`, `p32-b39`: 45,66%),
  FPT Retail (`p32-b38`, `p32-b40`: 46,54%, cột liên kết).
- Hàng y≈523: block gộp `p32-b73` → 1.000 tỷ + 100% thuộc FPT Investment (x 423–434), 4.500 tỷ thuộc
  FPT Education; `p32-b74` 100% thuộc Education.
- Kết quả 8 con + 2 liên kết, khớp `p32-b4` và trang 175–176.

Ghi chú FPT:
- (a) FTEL: sở hữu 45,66% nhưng có quyền kiểm soát nên hợp nhất là công ty con đến 31/12/2025.
  Từ 11/11/2025, phần vốn Nhà nước 50,16% chuyển sang Bộ Công an. Từ năm tài chính 2026 Tập
  đoàn **chuyển sang phương pháp vốn chủ sở hữu (liên doanh, liên kết)** (`p176-b20`, chunk
  `d772bc16-0492-5ac8-8a6e-f23a7ad7b86b`). Không tự đặt `valid_to`; WBS06 quyết định cách ghi.
- (b) FPT Online: tỷ lệ sở hữu 49,52% khác tỷ lệ quyền biểu quyết 80,15%. Ghi đúng cột, không suy
  ngược kiểm soát từ tỷ lệ sở hữu.
- (c) Alias "FPT Digital" là chuỗi con của alias "FPT DIGITAL RETAIL JOINT STOCK COMPANY" của FRT
  (`CMP-7356238c…`). Resolver không được khớp theo chuỗi con.
- (d) Bảng liên kết ở trang 176 vẫn ghi cột đầu là **"Công ty con"** (lỗi trong chính tài liệu).
  Rule phải phân loại theo tiêu đề mục "(ii) Công ty liên kết trực tiếp", không theo tên cột.

### 2.2 CMG — Công ty Cổ phần Tập đoàn Công nghệ CMC (`CMP-bda9e53cfba37e417ef8`)

**Năm tài chính CMG kết thúc 31/03/2026**, không phải 31/12 (thuyết minh trang 88: *"Tại ngày 31
tháng 3 năm 2026, Công ty có 17 công ty con"*, chunk `566b49b3-3952-57f7-943b-298e1585dc23`;
snapshot là OCR lỗi dấu). Bảng BCTN trang 7–9 ("b. Các công ty con, công ty liên kết", chunk
`fbcbfc6d-a32a-5b6b-bfd0-565c1109a9b3`) **không ghi ngày**. Ranh giới hàng trang 8 xác định bằng
ảnh `work/p-008.png`: hàng 3, hàng 4, một hàng gộp ô "Các công ty con của Công ty TNHH CMC Global
(CMC Global) bao gồm:", 6 hàng không số thứ tự (mẹ là CMC Global), rồi hàng 5.

| # | Loại | Công ty mẹ → công ty | Tỷ lệ (BCTN) | Thuyết minh 31/03/2026 | Bằng chứng BCTN (trang · chunk) | Chắc chắn |
|---|---|---|---|---|---|---|
| C1 | HAS_SUBSIDIARY | CMG → Công ty TNHH Tổng Công ty Công nghệ và Giải pháp CMC (CMC TS) | 100% | có, 100%/100% (tr. 88) | 7 · `22a1f150-2157-5700-abe0-bf6f49052b09` | Cao |
| C2 | HAS_SUBSIDIARY | CMG → Công ty TNHH CMC Consulting | 100% | có (tr. 88) | 7 · `22a1f150…` | Cao |
| C3 | HAS_SUBSIDIARY | CMG → Công ty TNHH An ninh an toàn Thông tin CMC (CMC CS) | 100% | có (tr. 89) | 8 · `01b50d4b-5505-5beb-8382-6cef9197fdf2` | Cao |
| C4 | HAS_SUBSIDIARY | CMG → Công ty TNHH CMC Global | 100% | có (tr. 88) | 8 · `01b50d4b…` | Cao |
| C5 | HAS_SUBSIDIARY | **CMC Global** → Công ty TNHH CMC Châu Á Thái Bình Dương (CMC-APAC) | "CMC Global sở hữu 100% vốn góp" | có, 100% (tr. 89) | 8 · `01b50d4b…` | Cao |
| C6 | HAS_SUBSIDIARY | **CMC Global** → Công ty Cổ phần CMC Japan | 100% vốn góp | có, 100% (tr. 89; text OCR ghi "400%", ảnh trang ghi 100%) | 8 · `bc9565f7-82cc-504c-af07-11b0abd83612` | Cao |
| C7 | HAS_SUBSIDIARY | **CMC Global** → Công ty TNHH CMC Korea | 100% vốn góp | có (tr. 89) | 8 · `bc9565f7…` | Cao |
| C8 | HAS_SUBSIDIARY | **? → Công ty TNHH CMC Malay** (thuyết minh: "Công ty TNHH CMC Global Malaysia SDN.BHD") | BCTN: CMC Global 100% | Thuyết minh, chú thích (iv) (đã đối chiếu ảnh `work/p-089.png`): **CMC-APAC thành lập ngày 13/6/2025**; 100%/100% | 8 · `bc9565f7…`; tr. 89 · `574a7540-2616-5e51-a81e-da00602013ad` | **Thấp — mâu thuẫn công ty mẹ, chuyển WBS06** |
| C9 | HAS_SUBSIDIARY | **CMC Global** → Công ty TNHH CMC North America | 100% vốn góp | **không có** trong 17 công ty con | 8 · `bc9565f7…` | TB |
| C10 | HAS_SUBSIDIARY | **CMC Global** → Công ty TNHH CMC Deutschland | 100% vốn góp | **không có** | 8 · `e99959c8-72c3-58f3-89b8-0fa81e2ccf82` | TB |
| C11 | HAS_SUBSIDIARY | CMG → Công ty Cổ phần Hạ tầng Viễn thông CMC (CMC Telecom) | 54,628% | 54,63%/54,63%, sở hữu trực tiếp sau giao dịch theo NQ 19/2025/NQ-HĐQT (tr. 88–89) | 8 · `e99959c8…`; tr. 88 · `c4c15e6e-0d1e-5081-bfa6-9f9d99aaf4c0` | Cao |
| C12 | **HAS_ASSOCIATE** | CMG → Công ty Cổ phần NetNam | 41,14% | Thuyết minh 13 "Đầu tư vào công ty liên kết": 41,14% vốn và quyền biểu quyết tại 31/03/2026 | 9 · `593d4624-5abe-5b54-925f-72fadcb587cc`; tr. 109 · `d1d71265-2040-58a4-b03b-2a9bed373c2c` | Cao |
| C13 | HAS_SUBSIDIARY | CMG → Viện Nghiên cứu và Ứng dụng Công nghệ CMC (CMC ATI) | 100% | có (tr. 88) | 9 · `593d4624…` | TB (e) |
| C14 | HAS_SUBSIDIARY | CMG → Công ty TNHH CMC Invesment (CMC Invest) | 100% | **không có** | 9 · `593d4624…` | TB |
| C15 | HAS_SUBSIDIARY | CMG → Công ty TNHH CMC Đà Nẵng | 100% | có (tr. 89) | 9 · `76162b24-7830-506d-b5fb-14b52edb88b1` | Cao |
| C16 | HAS_SUBSIDIARY | CMG → Công ty TNHH CMC Hòa Lạc | 100% | **không có** | 9 · `76162b24…` | TB |
| C17 | HAS_SUBSIDIARY | CMG → Công ty TNHH CMC Education | 100% | có (tr. 89) | 9 · `76162b24…` | Cao |
| C18 | HAS_SUBSIDIARY | **CMC Education** → Công ty Cổ phần Đầu tư Đại học CMC (CMC Uni) | 80,8% | 80,83%/80,83% | 9 · `ff629bb7-313f-52e8-a73b-503fe225cdae` | Cao |
| C19 | HAS_SUBSIDIARY | **CMC Uni** → Trường Đại học CMC | 92,1% | lợi ích 74,47%, quyền biểu quyết 92,13% | 9 · `ff629bb7…` | Cao (f) |
| C20 | HAS_SUBSIDIARY | CMG → Công ty TNHH Hạ tầng số CMC AI (CMC ADI) | 100% | có (tr. 89) | 9 · `ff629bb7…` | Cao |

Thuyết minh còn có hai đơn vị BCTN không liệt kê trong bảng: Công ty TNHH CMC Blue France
(100%, tạm dừng hoạt động) và Công ty Cổ phần CMC OpenAI (99%, do CMC ADI góp vốn, tr. 89–90,
chunk `5392db82-caef-5750-ac8e-d35616dd5fed`). Không đưa vào bảng vì snapshot của các trang này
là OCR lỗi dấu.

Ghi chú CMG:
- `as_of`: chỉ những hàng có trong thuyết minh mới có căn cứ ngày **2026-03-31**. Hàng TB "không
  có" (C9, C10, C14, C16) không có ngày trong nguồn → để `as_of: null`, sẽ không qua duyệt. Không
  lấy năm "2025" ở tiêu đề BCTN.
- Snapshot các trang thuyết minh 88–90, 109 là OCR lỗi dấu. Quote phải trích **đúng text chunk DB**
  (ví dụ "Tp doàn nàm giG' 41,14% phn vOn"), hoặc cần corpus mới với OCR sạch (bản `text/p-089.txt`
  trên máy). Đề nghị WBS01 cân nhắc re-snapshot các trang này.
- (e) CMC ATI là viện nghiên cứu, không phải công ty; WBS06 quyết định giữ `entity_type: Company` hay không.
- (f) Trường Đại học CMC: BCTN ghi 92,1% (sở hữu của CMC Uni); thuyết minh ghi lợi ích của Tập
  đoàn 74,47% (gián tiếp) và quyền biểu quyết 92,13%. Hai con số là hai đại lượng khác nhau, không
  phải mâu thuẫn; ghi `ownership_percent` theo nguồn đang dùng làm bằng chứng.
- **Canonical ID:** "Tập đoàn Công nghệ CMC" trong DB chưa khớp alias. Registry r1 đã có
  `CMP-bda9e53cfba37e417ef8` (tên "CÔNG TY CỔ PHẦN TẬP ĐOÀN CÔNG NGHỆ CMC", mã CMG). Đề nghị thêm
  alias "Tập đoàn Công nghệ CMC" ở bản registry kế tiếp, **không tạo ID mới**. "CMC TS" **không phải**
  `CMP-26aa0b2bbd2402e96589` (CMC TSSG – Sài Gòn); hiện CMC TS chưa có ID.

### 2.3 CTG — Ngân hàng TMCP Công thương Việt Nam (`CMP-c8ff5c1af9a79b27bdfb`)

Trang 8 (in 10): *"7 CÔNG TY CON VÀ 1 CÔNG TY LIÊN KẾT"* cùng 8 tên (chunk `33370e93-090e-565d-97c1-c8a82d162102`,
Indovina ở `33e95b18-a372-5fbc-8d98-dec646de366e`; snapshot tách số "7 1" khỏi tiêu đề ở
`ef87adef…`). Trang này **không chỉ rõ** đơn vị nào là liên kết; ngân hàng con tại Lào đếm riêng
("1 NGÂN HÀNG CON TẠI LÀO"). Phân loại lấy từ thuyết minh 1 BCTC hợp nhất, trang 142–143
(in 278–281): *"Quyền lợi của Ngân hàng trong tám (08) công ty con sở hữu trực tiếp và một (01)
công ty liên doanh"* (chunk `adc2fb03-f16c-5805-ab8c-a1d22802883c`; cột "31.12.2025 | 31.12.2024", mỗi
năm có tỷ lệ sở hữu và tỷ lệ quyền biểu quyết). 7 + 1 (Lào) = 8: hai trang khớp nhau.

| # | Loại | Công ty (tên pháp lý theo thuyết minh) | Tên ngắn (tr. 8) | Sở hữu / biểu quyết 31.12.2025 | Bằng chứng (trang · chunk) | Chắc chắn |
|---|---|---|---|---|---|---|
| T1 | HAS_SUBSIDIARY | Công ty Cho thuê tài chính TNHH MTV Ngân hàng TMCP Công thương Việt Nam | VietinBank Leasing | 100% / 100% | 142 · `bba6f920-3ad8-5a46-a683-ddf048669ce5` | Cao (g) |
| T2 | HAS_SUBSIDIARY | Công ty Cổ phần Chứng khoán VietinBank | VBSE | 75,64% / 75,64% | 142 · `f278a317-4ea8-5cc9-8b63-ff7270a3df53` | Cao — registry `CMP-1e129dd1c23200f469a7` |
| T3 | HAS_SUBSIDIARY | Công ty TNHH MTV Quản lý nợ và Khai thác Tài sản Ngân hàng TMCP Công thương Việt Nam | VietinBank AMC | 100% / 100% | 142 · `2053abcb-79eb-5c4d-97d7-2b1b55b6d2f0` | Cao |
| T4 | HAS_SUBSIDIARY | Tổng Công ty Cổ phần Bảo hiểm Ngân hàng TMCP Công thương Việt Nam | VBI | 73,37% / 73,37% | 142 · `1fd3a7ad-326f-567b-a47d-75f28824b24d` | Cao |
| T5 | HAS_SUBSIDIARY | Công ty TNHH MTV Vàng bạc Đá quý Ngân hàng TMCP Công thương Việt Nam | VietinBank Gold & Jewellery | 100% / 100% | 143 · `eba3d544-1147-54c5-9d00-d3ddacf46c2e` | Cao |
| T6 | HAS_SUBSIDIARY | Công ty TNHH MTV Quản lý Quỹ Ngân hàng TMCP Công thương Việt Nam | VietinBank FMC | 100% / 100% | 143 · `aec480be-d280-5c5b-8718-dd01703d10d5` | Cao |
| T7 | HAS_SUBSIDIARY | Công ty TNHH MTV Chuyển tiền Toàn cầu - Ngân hàng TMCP Công thương Việt Nam | VietinBank Global Money Transfer | 100% / 100% | 143 · `d1b961ee-1fe2-5e94-9315-0058d047d148` | Cao |
| T8 | HAS_SUBSIDIARY | Ngân hàng TNHH Công thương Việt Nam tại Lào | VietinBank Lào | 100% / 100% | 143 · `d1b961ee…` (hàng vắt sang `c9d669e7…`) | Cao |
| T9 | HAS_ASSOCIATE (h) | Ngân hàng TNHH Indovina | IVB | 50% / 50% | 143 · tiêu đề "Công ty liên doanh" · `c9d669e7-957c-58e2-819b-fb811d0efd02`; tr. 159 thuyết minh 10.2 "Vốn góp liên doanh … Tỷ phần nắm giữ 50%" · `df0cd184-38d4-5be1-88ac-a8a2a9409450`; tr. 169 "Công ty liên doanh" · `8166d57b-f478-52f8-b61e-5eb125fb5256` | Cao về số liệu; loại quan hệ do WBS06 chốt |

Ghi chú CTG:
- `as_of` = 2025-12-31 (cột "31.12.2025"). Tỷ lệ năm 2024 trùng năm 2025 cho cả 9 hàng.
- Trong snapshot, mỗi hàng của bảng trang 142–143 nằm trọn trong một chunk, gồm số thứ tự, đoạn
  đầu tên và dòng "X% X% X% X%". Riêng hàng 8 vắt sang chunk sau. Tên pháp lý bị ngắt thành nhiều
  dòng xen văn bản giấy phép, nên rule phải ráp tên theo hàng; tên ngắn ở trang 8 chỉ dùng để đối chiếu.
- (g) **Lỗi registry:** `CMP-c8ff5c1af9a79b27bdfb` (chính CTG) đang có alias **"VietinBank Leasing"**.
  Với alias này, resolver sẽ gán công ty con T1 thành CTG, tạo cạnh tự trỏ hoặc gán sai. Cần gỡ
  alias ở bản registry kế tiếp; T1 hiện chưa có ID riêng.
- (h) Indovina là **liên doanh** (đồng kiểm soát), hạch toán theo phương pháp vốn chủ sở hữu. Trang 8
  gọi là "công ty liên kết". Contract 2.1.0 không có loại liên doanh riêng, nên đề xuất
  `HAS_ASSOCIATE` với `accounting_basis: "phương pháp vốn chủ sở hữu (liên doanh)"`; WBS06 chốt.

## 3. Gợi ý sửa rule WBS03

1. Phân loại con/liên kết theo **tiêu đề mục** ("Công ty con", "(ii) Công ty liên kết trực tiếp",
   "Công ty liên doanh"), không theo tên cột (FPT 176) hay tiêu đề gộp (CTG 8).
2. Ưu tiên bảng thuyết minh BCTC hợp nhất (FPT 175–176, CTG 142–143, CMG 88–89/109) để lấy tỷ lệ
   và ngày. Sơ đồ/bảng BCTN (FPT 32, CTG 8, CMG 7–9) chỉ dùng đối chiếu.
3. Với bảng có hàng gộp ô dạng "Các công ty con của X bao gồm:" (CMG 8, 9), công ty mẹ của các
   hàng tiếp theo là X, cho đến hàng có số thứ tự kế tiếp.
4. Lấy ngày từ tiêu đề bảng hoặc thuyết minh ("Tại ngày 31/12/2025…", "Tại ngày 31 tháng 3 năm
   2026…"). CMG có năm tài chính kết thúc 31/03.
5. Không dùng sơ đồ FPT 32 trong snapshot làm nguồn duy nhất: text chunk bị xen menu và cột.
   Nếu cần, ghép theo bbox IR như mục 2.1.

## 4. Việc cần người khác chốt

| Việc | Ai |
|---|---|
| Thêm alias "Tập đoàn Công nghệ CMC" vào `CMP-bda9e53cfba37e417ef8`; gỡ alias "VietinBank Leasing" khỏi `CMP-c8ff5c1af9a79b27bdfb`; cấp ID cho các công ty còn "chưa có" | Hưng (registry) |
| C8 CMC Malay: công ty mẹ là CMC Global (BCTN) hay CMC-APAC (thuyết minh) | Huyền (WBS06) |
| Loại quan hệ cho Indovina (liên doanh); FTEL đổi phương pháp từ 2026; CMC ATI có phải Company không | Huyền (WBS06) |
| Re-snapshot OCR sạch cho CMG trang 88–90, 109 nếu muốn trích quote đọc được | WBS01 |
| Sửa rule và chạy lại WBS03; ứng viên mới vẫn PENDING | Người làm WBS03 |
