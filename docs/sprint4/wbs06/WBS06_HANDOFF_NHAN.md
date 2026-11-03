# Bàn giao Nhân V4 — 13 APPROVED, 10 REJECTED sau thẩm định nguồn

> **Người duyệt: Trần Diệu Huyền.**  
> **Thời điểm ghi nhận chốt duyệt: 02/11/2026, 17:13:40 (UTC+7).**  
> **Gửi riêng file Markdown này là đủ để bàn giao và đối chiếu.**

---

## 1. Kết luận tổng quan cho Nhân

| Tổng số quan hệ thẩm định | APPROVED (Chấp thuận) | REJECTED (Chưa đạt lần này) |
|:---:|:---:|:---:|
| **23 quan hệ** | **13** | **10** |

* **13 APPROVED:** WBS06 đã đọc thêm ngữ cảnh, bổ sung thuộc tính và mốc báo cáo có bằng chứng thực tế, kiểm lại nguồn và xuất envelope V4 hoàn chỉnh để bạn nghiệm thu. Không còn bác chỉ vì WBS03 xuất ứng viên chưa điền trường duyệt.
* **10 REJECTED:** Nguồn có nói đến quan hệ, nhưng chưa ghim đủ mốc thời điểm cho phát biểu; riêng 4 quan hệ sở hữu chưa chứng minh rõ trực tiếp/gián tiếp. Đây là điều kiện chưa đủ để nạp graph ở đợt này, không phải kết luận Nhân bịa hoặc trích sai cả 10 quan hệ.

---

## 2. Trạng thái lưu trữ DB và nạp Graph

| Hạng mục kiểm tra | Trạng thái hiện tại | Lưu ý kỹ thuật |
|---|:---:|---|
| **Chốt duyệt nội dung 13 ca** | **ĐÃ CHỐT** | Trần Diệu Huyền đã xác nhận chốt duyệt chính thức. |
| **Ghi vào Review Store DB** | **CHƯA** | Bảng `graph_review_results` / `graph_review_audit` chưa triển khai trên DB. |
| **Receipt / User ID ứng dụng** | **CHƯA CÓ** | Không tự tạo hoặc ký bằng tài khoản giả lập. |
| **Đã nạp vào Neo4j** | **CHƯA** | **Nhân tuyệt đối chưa tự ý nạp vào Neo4j.** |
| **`application_load_allowed`** | **`false`** | Backend chỉ cho phép nạp khi có bản ghi duyệt DB hợp lệ. |

> **Thông điệp gửi Nhân:**  
> “13 ca đã được Trần Diệu Huyền chốt duyệt cuối cùng ở WBS06 lúc 17:13:40 ngày 02/11/2026. Đã xuất gói V4 chuẩn hóa ghi đúng người duyệt, thời điểm và bảng ánh xạ ID gốc → ID đã duyệt. Quyết định chưa được ghi vào review store vì các bảng review chưa triển khai trên DB, nên `application_load_allowed` vẫn là `false`. **Nhân chưa nạp Neo4j**; sau khi WBS07 lưu và đọc lại đủ 13 quyết định trên DB, sẽ bàn giao tiếp cho WBS08 nạp và đối chiếu graph.”

---

## 3. Đánh giá chi tiết theo từng nhóm doanh nghiệp

| Nhóm | Số lượng | Kết luận | Bằng chứng và căn cứ xử lý |
|---|:---:|:---:|---|
| **TCB** (Techcombank) | 5 | **APPROVED** | Sơ đồ và tên pháp lý xác nhận công ty con; thuyết minh nêu rõ cơ sở hợp nhất. Mốc thời gian xác định là 31/12/2024 hoặc 31/12/2025 từ sơ đồ/thuyết minh có ngày cụ thể. |
| **ELC** (Elcom) | 8 | **APPROVED** | Danh sách và chính sách kế toán trong thuyết minh được liên kết với BCTC tại ngày 31/12/2024. Ghi rõ `as_of` của báo cáo. |
| **VCB** (Vietcombank) | 4 | **REJECTED** | Quan hệ công ty con có trong nguồn; nhưng chưa ghim được mốc thời gian (`as_of` / `valid_from`) đủ rõ ràng cho phát biểu đang duyệt. |
| **VCB** (Vietcombank) | 4 | **REJECTED** | Quan hệ sở hữu cổ phần: nguồn ghi sở hữu 100%, nhưng chưa chứng minh rõ tỷ lệ trực tiếp (direct) hay gián tiếp (indirect) và mốc thời điểm. Không suy luận direct từ 100%. |
| **BID → BIC** | 1 | **REJECTED** | Nguồn xác nhận công ty con nhưng chưa ghim mốc `as_of` / `valid_from` đủ rõ. Không lấy năm ở tiêu đề BCTN làm ngày hiệu lực. |
| **MB ↔ FPT** | 1 | **REJECTED** | Toàn chunk nói về việc hợp tác ứng dụng công nghệ xanh; phạm vi có căn cứ nhưng còn thiếu mốc thời gian rõ ràng cho phát biểu. |

*Lưu ý riêng về Smartek:* Phần giới thiệu ghi 74,4%, bảng thuyết minh ghi 88,35%. Do chưa chốt cùng cơ sở/thời điểm tính nên không duyệt tỷ lệ này. Hai cạnh quan hệ công ty con của Smartek vẫn được duyệt riêng do nguồn nhất quán về quan hệ.

---

## 4. Bảng tổng hợp chi tiết 23 quan hệ (Kèm ID ánh xạ)

| STT | ID ứng viên gốc | Loại quan hệ & Hai đầu thực thể | Kết luận | ID bản duyệt (Envelope V4) | Lý do thẩm định / Bằng chứng |
|:---:|---|---|:---:|---|---|
| 1 | `rel:16e385867ed1c8eefa0e59387714180e` | HAS_SUBSIDIARY<br>TCB → Chứng khoán Kỹ Thương (TCBS) | **APPROVED** | `review:bceddd14947a63a6afddeb22ec2cc385` | Thuyết minh tại 31/12/2025 và cơ sở hợp nhất; tên pháp lý khớp mục công ty con. `as_of=2025-12-31`. |
| 2 | `rel:9e97a35a4e008840693a5d46ba4feac4` | HAS_SUBSIDIARY<br>TCB → Quản lý nợ & Khai thác tài sản TCB | **APPROVED** | `review:db39ab775197b7fc3efb341333579d3e` | Thuyết minh tại 31/12/2025 và cơ sở hợp nhất; tên pháp lý khớp mục công ty con. `as_of=2025-12-31`. |
| 3 | `rel:62a5afb99dd07bcd82125889511cb6df` | HAS_SUBSIDIARY<br>TCB → Quản lý nợ & Khai thác tài sản TCB | **APPROVED** | `review:932ed27c8c6b464605938ba58730874b` | Sơ đồ ngày 31/12/2024 có liên kết tên pháp lý; thuyết minh hợp nhất toàn bộ. `as_of=2024-12-31`. |
| 4 | `rel:66a5737a3df9ffceaaa5bbf016c1e442` | HAS_SUBSIDIARY<br>TCB → Chứng khoán Kỹ Thương (TCBS) | **APPROVED** | `review:f1c3bf9fe82007beb07d6242fa64e4be` | Sơ đồ ngày 31/12/2024 có liên kết tên pháp lý; thuyết minh hợp nhất toàn bộ. `as_of=2024-12-31`. |
| 5 | `rel:c2867016259752857acb355f89f81cc1` | HAS_SUBSIDIARY<br>TCB → Quản lý Quỹ Kỹ Thương (Techcom Capital) | **APPROVED** | `review:d17408be45cf30dc8ca8da18b78b612a` | Sơ đồ ngày 31/12/2024 có liên kết tên pháp lý; thuyết minh hợp nhất toàn bộ. `as_of=2024-12-31`. |
| 6 | `rel:088f2d6504272e84004f05147c25f31c` | HAS_SUBSIDIARY<br>Datanova Việt Nam → Đầu tư Smartek | **APPROVED** | `review:258a2da88fb788931f38dd798cf6b397` | Báo cáo kiểm toán xác định BCTC tại 31/12/2024; thuyết minh 1.5 và quyền kiểm soát tại 3.1. `as_of=2024-12-31`. |
| 7 | `rel:1fb8958ce30f9da65baf366fd359a26f` | HAS_SUBSIDIARY<br>ELCOM → Datanova Việt Nam | **APPROVED** | `review:abe23a48351378e472c749d0a64a581e` | Báo cáo kiểm toán xác định BCTC tại 31/12/2024; thuyết minh 1.5 và quyền kiểm soát tại 3.1. `as_of=2024-12-31`. |
| 8 | `rel:4c99ccafaaa13f8bcc2c08851e807591` | HAS_SUBSIDIARY<br>ELCOM → Tập đoàn Thương mại Hà Nội | **APPROVED** | `review:b3a8d25c8ce6f2729ec1f0dfa2099314` | Báo cáo kiểm toán xác định BCTC tại 31/12/2024; thuyết minh 1.5 và quyền kiểm soát tại 3.1. `as_of=2024-12-31`. |
| 9 | `rel:6722a28cffaea98a9304ecc3affa0250` | HAS_SUBSIDIARY<br>ELCOM → Đầu tư Smartek | **APPROVED** | `review:dd9e935dffee9b09ada5bed3d3f75924` | Báo cáo kiểm toán xác định BCTC tại 31/12/2024; thuyết minh 1.5 và quyền kiểm soát tại 3.1. `as_of=2024-12-31`. |
| 10 | `rel:6a839b61aac7db4b668726835ac84645` | HAS_ASSOCIATE<br>ELCOM → Công nghệ VFT | **APPROVED** | `review:297f6f61dd1554d81ea2fbdacf33bdd6` | BCTC kiểm toán 31/12/2024, danh sách công ty liên kết mục thuyết minh 1.5. `as_of=2024-12-31`. |
| 11 | `rel:bfea0864087f9da2227fcfcf44d80dc6` | HAS_SUBSIDIARY<br>ELCOM → Giải pháp phần mềm ELCOM | **APPROVED** | `review:f3c4ed87b20853267f9bf19a6fd2d210` | BCTC kiểm toán 31/12/2024, thuyết minh 1.5 và quyền kiểm soát 3.1. `as_of=2024-12-31`. |
| 12 | `rel:c47542be243328ffc45f1c1b2cebbab3` | HAS_SUBSIDIARY<br>ELCOM → ElcomPrime | **APPROVED** | `review:6fb09f95bc932d9621f4f78096655b39` | BCTC kiểm toán 31/12/2024, thuyết minh 1.5 và quyền kiểm soát 3.1. `as_of=2024-12-31`. |
| 13 | `rel:f3ba537b3df1a1ffc8d18c69f64000dd` | HAS_ASSOCIATE<br>ELCOM → Công nghệ Vật liệu mới Bắc Kạn | **APPROVED** | `review:c7abba537d91b909a7c67388de7317db` | BCTC kiểm toán 31/12/2024, danh sách công ty liên kết mục thuyết minh 1.5. `as_of=2024-12-31`. |
| 14 | `rel:54a63c17919c89a13b9a364669a20138` | HAS_SUBSIDIARY<br>VCB → Cho thuê tài chính Vietcombank | **REJECTED** | *Chưa xuất bản duyệt* | Nguồn có nêu quan hệ nhưng chưa ghim mốc `as_of`/`valid_from` rõ ràng. Không lấy năm tiêu đề BCTN làm ngày hiệu lực. |
| 15 | `rel:c3d36770dd3753c0b5d30a0a291b4f50` | HAS_SUBSIDIARY<br>VCB → Cho thuê tài chính Vietcombank | **REJECTED** | *Chưa xuất bản duyệt* | Nguồn có nêu quan hệ nhưng chưa ghim mốc `as_of`/`valid_from` rõ ràng. Không lấy năm tiêu đề BCTN làm ngày hiệu lực. |
| 16 | `rel:f11468f41fb1cae28c0617bd7eec521f` | HAS_SUBSIDIARY<br>VCB → Kiều hối Vietcombank | **REJECTED** | *Chưa xuất bản duyệt* | Nguồn có nêu quan hệ nhưng chưa ghim mốc `as_of`/`valid_from` rõ ràng. Không lấy năm tiêu đề BCTN làm ngày hiệu lực. |
| 17 | `rel:a308917230b9e53c1db06a113af0f530` | HAS_SUBSIDIARY<br>VCB → Kiều hối Vietcombank | **REJECTED** | *Chưa xuất bản duyệt* | Nguồn có nêu quan hệ nhưng chưa ghim mốc `as_of`/`valid_from` rõ ràng. Không lấy năm tiêu đề BCTN làm ngày hiệu lực. |
| 18 | `rel:a6e698eb7ae99ff04d7e694ffe12eb87` | OWNS_SHARES<br>VCB → Cho thuê tài chính Vietcombank | **REJECTED** | *Chưa xuất bản duyệt* | Nêu tỷ lệ 100% nhưng chưa chứng minh rõ sở hữu trực tiếp hay gián tiếp và mốc ngày hiệu lực. |
| 19 | `rel:f25bca89fa66800b87257166d554bad9` | OWNS_SHARES<br>VCB → Cho thuê tài chính Vietcombank | **REJECTED** | *Chưa xuất bản duyệt* | Nêu tỷ lệ 100% nhưng chưa chứng minh rõ sở hữu trực tiếp hay gián tiếp và mốc ngày hiệu lực. |
| 20 | `rel:b619ed16494a3f38a14729f21f1b1910` | OWNS_SHARES<br>VCB → Chứng khoán Vietcombank (VCBS) | **REJECTED** | *Chưa xuất bản duyệt* | Nêu tỷ lệ 100% nhưng chưa chứng minh rõ sở hữu trực tiếp hay gián tiếp và mốc ngày hiệu lực. |
| 21 | `rel:deb37325f74612ded314754484380a9f` | OWNS_SHARES<br>VCB → Chứng khoán Vietcombank (VCBS) | **REJECTED** | *Chưa xuất bản duyệt* | Nêu tỷ lệ 100% nhưng chưa chứng minh rõ sở hữu trực tiếp hay gián tiếp và mốc ngày hiệu lực. |
| 22 | `rel:dd01697e444a009d219d8956a9b09077` | HAS_SUBSIDIARY<br>BIDV → Bảo hiểm BIDV (BIC) | **REJECTED** | *Chưa xuất bản duyệt* | Nguồn xác nhận công ty con nhưng thiếu mốc thời gian cụ thể gắn với phát biểu. |
| 23 | `rel:023629b35242df030f87b93a34d85b58` | COOPERATES_WITH<br>MBBank ↔ FPT | **REJECTED** | *Chưa xuất bản duyệt* | Hợp tác công nghệ xanh có căn cứ nhưng thiếu mốc thời gian rõ ràng cho phát biểu. |

---

## 5. Bằng chứng và yêu cầu bổ sung cho 10 ca REJECTED

Đã đối chiếu báo cáo thẩm định đã lưu: cả 10 ca thiếu mốc thời gian; 4 ca OWNS_SHARES thiếu thêm holding_basis. Lượt này chỉ kiểm tra tài liệu và mã nguồn, chưa truy vấn lại DB hoặc đọc toàn bộ PDF. Không kết luận toàn báo cáo không có bằng chứng bổ sung.

REJECTED là kết luận WBS06 cho bản ứng viên hiện tại. Mã ERR_REVIEW_* là lý do của báo cáo thẩm định; engine đánh dấu thiếu thời gian bằng WARN_TEMPORAL_BASIS_MISSING. Chưa có xác nhận lưu các quyết định reject vào DB.

### Ca 1 — `rel:54a63c17919c89a13b9a364669a20138`

**HAS_SUBSIDIARY: NGÂN HÀNG THƯƠNG MẠI CỔ PHẦN NGOẠI THƯƠNG VIỆT NAM → Công ty TNHH Một thành viên Cho thuê tài chính Vietcombank**

Document ID: `679baa3e-b39c-5b53-be43-3cd19d738dca`.

Trang theo locator: 18; chunk: `2ceea344-77ec-52e7-92e3-a5037a1eb64b`.

Trích nguyên văn:

```text
công ty con
VCBL
```

Lý do thẩm định: ERR_REVIEW_TEMPORAL_BASIS_NOT_GROUNDED.

**Cần bổ sung:** Nguồn xác nhận as_of hoặc valid_from cho đúng quan hệ, kèm document ID, chunk ID, trang và trích đoạn. Không tự lấy năm tiêu đề hoặc năm lợi nhuận làm ngày 31/12. Không bắt buộc tìm ngày bắt đầu nếu đã có mốc xác nhận phù hợp. Giữ nguyên ứng viên gốc, gửi bản bổ sung để thẩm định lại.

### Ca 2 — `rel:c3d36770dd3753c0b5d30a0a291b4f50`

**HAS_SUBSIDIARY: NGÂN HÀNG THƯƠNG MẠI CỔ PHẦN NGOẠI THƯƠNG VIỆT NAM → Công ty TNHH Một thành viên Cho thuê tài chính Vietcombank**

Document ID: `dd94d5da-f8b1-5776-8c5e-f211d18ae26b`.

Trang theo locator: 19; chunk: `f45912ed-4282-5edb-88ce-a43c11c3776b`.

Trích nguyên văn:

```text
công ty con
Công ty TNHH Một thành viên
Cho thuê tài chính Vietcombank
```

Lý do thẩm định: ERR_REVIEW_TEMPORAL_BASIS_NOT_GROUNDED.

**Cần bổ sung:** Nguồn xác nhận as_of hoặc valid_from cho đúng quan hệ, kèm document ID, chunk ID, trang và trích đoạn. Không tự lấy năm tiêu đề hoặc năm lợi nhuận làm ngày 31/12. Không bắt buộc tìm ngày bắt đầu nếu đã có mốc xác nhận phù hợp. Giữ nguyên ứng viên gốc, gửi bản bổ sung để thẩm định lại.

### Ca 3 — `rel:f11468f41fb1cae28c0617bd7eec521f`

**HAS_SUBSIDIARY: NGÂN HÀNG THƯƠNG MẠI CỔ PHẦN NGOẠI THƯƠNG VIỆT NAM → Công ty TNHH Một thành viên Kiều hối Vietcombank**

Document ID: `679baa3e-b39c-5b53-be43-3cd19d738dca`.

Trang theo locator: 18; chunk: `4eb699ea-63f8-58c3-a0e6-55f1bb62f66c`.

Trích nguyên văn:

```text
VCBR là công ty con do Vietcombank sở hữu 100%
```

Lý do thẩm định: ERR_REVIEW_TEMPORAL_BASIS_NOT_GROUNDED.

**Cần bổ sung:** Nguồn xác nhận as_of hoặc valid_from cho đúng quan hệ, kèm document ID, chunk ID, trang và trích đoạn. Không tự lấy năm tiêu đề hoặc năm lợi nhuận làm ngày 31/12. Không bắt buộc tìm ngày bắt đầu nếu đã có mốc xác nhận phù hợp. Giữ nguyên ứng viên gốc, gửi bản bổ sung để thẩm định lại.

### Ca 4 — `rel:a308917230b9e53c1db06a113af0f530`

**HAS_SUBSIDIARY: NGÂN HÀNG THƯƠNG MẠI CỔ PHẦN NGOẠI THƯƠNG VIỆT NAM → Công ty TNHH Một thành viên Kiều hối Vietcombank**

Document ID: `dd94d5da-f8b1-5776-8c5e-f211d18ae26b`.

Trang theo locator: 19; chunk: `4da429da-4ebd-5fef-9fad-4054093f8eb5`.

Trích nguyên văn:

```text
VCBR là công ty con do Vietcombank sở hữu 100%
```

Trang theo locator: 19; chunk: `4da429da-4ebd-5fef-9fad-4054093f8eb5`.

Trích nguyên văn:

```text
Công ty TNHH MTV Kiều hối
Vietcombank
VCBR
Lợi nhuận trước thuế năm 2024
31,49 TỶ ĐỒNG
VCBR là công ty con do Vietcombank sở hữu 100%
```

Lý do thẩm định: ERR_REVIEW_TEMPORAL_BASIS_NOT_GROUNDED.

**Cần bổ sung:** Nguồn xác nhận as_of hoặc valid_from cho đúng quan hệ, kèm document ID, chunk ID, trang và trích đoạn. Không tự lấy năm tiêu đề hoặc năm lợi nhuận làm ngày 31/12. Không bắt buộc tìm ngày bắt đầu nếu đã có mốc xác nhận phù hợp. Giữ nguyên ứng viên gốc, gửi bản bổ sung để thẩm định lại.

### Ca 5 — `rel:a6e698eb7ae99ff04d7e694ffe12eb87`

**OWNS_SHARES: NGÂN HÀNG THƯƠNG MẠI CỔ PHẦN NGOẠI THƯƠNG VIỆT NAM → Công ty TNHH Một thành viên Cho thuê tài chính Vietcombank**

Document ID: `679baa3e-b39c-5b53-be43-3cd19d738dca`.

Trang theo locator: 18; chunk: `2ceea344-77ec-52e7-92e3-a5037a1eb64b`.

Trích nguyên văn:

```text
VCBL là Công ty do Vietcombank sở hữu 100%
```

Lý do thẩm định: ERR_REVIEW_HOLDING_BASIS_NOT_GROUNDED, ERR_REVIEW_TEMPORAL_BASIS_NOT_GROUNDED.

**Cần bổ sung:** Nguồn xác nhận as_of hoặc valid_from cho đúng quan hệ, kèm document ID, chunk ID, trang và trích đoạn. Không tự lấy năm tiêu đề hoặc năm lợi nhuận làm ngày 31/12. Không bắt buộc tìm ngày bắt đầu nếu đã có mốc xác nhận phù hợp. Bổ sung căn cứ holding_basis=direct/indirect cho đúng tỷ lệ 100%; không suy direct từ 100%. Giữ nguyên ứng viên gốc, gửi bản bổ sung để thẩm định lại.

### Ca 6 — `rel:f25bca89fa66800b87257166d554bad9`

**OWNS_SHARES: NGÂN HÀNG THƯƠNG MẠI CỔ PHẦN NGOẠI THƯƠNG VIỆT NAM → Công ty TNHH Một thành viên Cho thuê tài chính Vietcombank**

Document ID: `dd94d5da-f8b1-5776-8c5e-f211d18ae26b`.

Trang theo locator: 19; chunk: `f45912ed-4282-5edb-88ce-a43c11c3776b`.

Trích nguyên văn:

```text
VCBL là Công ty do Vietcombank sở hữu 100%
```

Lý do thẩm định: ERR_REVIEW_HOLDING_BASIS_NOT_GROUNDED, ERR_REVIEW_TEMPORAL_BASIS_NOT_GROUNDED.

**Cần bổ sung:** Nguồn xác nhận as_of hoặc valid_from cho đúng quan hệ, kèm document ID, chunk ID, trang và trích đoạn. Không tự lấy năm tiêu đề hoặc năm lợi nhuận làm ngày 31/12. Không bắt buộc tìm ngày bắt đầu nếu đã có mốc xác nhận phù hợp. Bổ sung căn cứ holding_basis=direct/indirect cho đúng tỷ lệ 100%; không suy direct từ 100%. Giữ nguyên ứng viên gốc, gửi bản bổ sung để thẩm định lại.

### Ca 7 — `rel:b619ed16494a3f38a14729f21f1b1910`

**OWNS_SHARES: NGÂN HÀNG THƯƠNG MẠI CỔ PHẦN NGOẠI THƯƠNG VIỆT NAM → Công ty TNHH Chứng khoán Vietcombank**

Document ID: `679baa3e-b39c-5b53-be43-3cd19d738dca`.

Trang theo locator: 18; chunk: `8b2d615a-ce16-53ae-a636-ab227e4ad934`.

Trích nguyên văn:

```text
VCBS là công ty do Vietcombank sở hữu 100%
```

Lý do thẩm định: ERR_REVIEW_HOLDING_BASIS_NOT_GROUNDED, ERR_REVIEW_TEMPORAL_BASIS_NOT_GROUNDED.

**Cần bổ sung:** Nguồn xác nhận as_of hoặc valid_from cho đúng quan hệ, kèm document ID, chunk ID, trang và trích đoạn. Không tự lấy năm tiêu đề hoặc năm lợi nhuận làm ngày 31/12. Không bắt buộc tìm ngày bắt đầu nếu đã có mốc xác nhận phù hợp. Bổ sung căn cứ holding_basis=direct/indirect cho đúng tỷ lệ 100%; không suy direct từ 100%. Giữ nguyên ứng viên gốc, gửi bản bổ sung để thẩm định lại.

### Ca 8 — `rel:deb37325f74612ded314754484380a9f`

**OWNS_SHARES: NGÂN HÀNG THƯƠNG MẠI CỔ PHẦN NGOẠI THƯƠNG VIỆT NAM → Công ty TNHH Chứng khoán Vietcombank**

Document ID: `dd94d5da-f8b1-5776-8c5e-f211d18ae26b`.

Trang theo locator: 19; chunk: `1f233fca-f45b-5996-a9c3-31566c16a351`.

Trích nguyên văn:

```text
VCBS là công ty do Vietcombank sở hữu 100%
```

Lý do thẩm định: ERR_REVIEW_HOLDING_BASIS_NOT_GROUNDED, ERR_REVIEW_TEMPORAL_BASIS_NOT_GROUNDED.

**Cần bổ sung:** Nguồn xác nhận as_of hoặc valid_from cho đúng quan hệ, kèm document ID, chunk ID, trang và trích đoạn. Không tự lấy năm tiêu đề hoặc năm lợi nhuận làm ngày 31/12. Không bắt buộc tìm ngày bắt đầu nếu đã có mốc xác nhận phù hợp. Bổ sung căn cứ holding_basis=direct/indirect cho đúng tỷ lệ 100%; không suy direct từ 100%. Giữ nguyên ứng viên gốc, gửi bản bổ sung để thẩm định lại.

### Ca 9 — `rel:dd01697e444a009d219d8956a9b09077`

**HAS_SUBSIDIARY: NGÂN HÀNG THƯƠNG MẠI CỔ PHẦN ĐẦU TƯ VÀ PHÁT TRIỂN VIỆT NAM → Tổng Công ty Cổ phần Bảo hiểm BIDV**

Document ID: `c0a80084-f786-5abe-9f16-84b1f466c118`.

Trang theo locator: 63; chunk: `8e2d6222-9db8-506b-9b44-500f6b356682`.

Trích nguyên văn:

```text
BIC- Công ty con của BIDV
```

Lý do thẩm định: ERR_REVIEW_TEMPORAL_BASIS_NOT_GROUNDED.

**Cần bổ sung:** Nguồn xác nhận as_of hoặc valid_from cho đúng quan hệ, kèm document ID, chunk ID, trang và trích đoạn. Không tự lấy năm tiêu đề hoặc năm lợi nhuận làm ngày 31/12. Không bắt buộc tìm ngày bắt đầu nếu đã có mốc xác nhận phù hợp. Giữ nguyên ứng viên gốc, gửi bản bổ sung để thẩm định lại.

### Ca 10 — `rel:023629b35242df030f87b93a34d85b58`

**COOPERATES_WITH: Ngân hàng Thương mại Cổ phần Quân đội → Công ty Cổ phần FPT**

Document ID: `faf61b2a-9dba-57d4-91e4-d7eca3edb4c7`.

Trang theo locator: 77; chunk: `f4303a40-b295-5f6b-99b8-a2ddfdb6edc9`.

Trích nguyên văn:

```text
hợp tác giữa Ngân hàng TMCP Quân đội (MB) và Tập đoàn FPT
```

Lý do thẩm định: ERR_REVIEW_TEMPORAL_BASIS_NOT_GROUNDED.

**Cần bổ sung:** Nguồn xác nhận as_of hoặc valid_from cho đúng quan hệ, kèm document ID, chunk ID, trang và trích đoạn. Không tự lấy năm tiêu đề hoặc năm lợi nhuận làm ngày 31/12. Không bắt buộc tìm ngày bắt đầu nếu đã có mốc xác nhận phù hợp. Giữ nguyên ứng viên gốc, gửi bản bổ sung để thẩm định lại.

---

## 6. Hướng dẫn cụ thể cho Nhân

1. **Không sửa hash snapshot và không cần trích xuất lại** 23 ứng viên từ đầu.
2. **Với 13 ca APPROVED:** 
   - Sử dụng các thông tin và mã bản duyệt (`review:...`) trong bảng Mục 4 để đối chiếu. 
   - WBS06 đã bổ sung đầy đủ thuộc tính và mốc thời gian chuẩn từ BCTC.
3. **Với 10 ca REJECTED:** 
   - Tham khảo mục số 5 ở trên: tìm đúng trang bảng thuyết minh hoặc báo cáo kiểm toán có ghi mốc ngày cụ thể (`as_of` ví dụ `31/12/2024`).
   - Với quan hệ sở hữu (`OWNS_SHARES`): cần nguồn ghi rõ cơ sở trực tiếp hay gián tiếp, không tự suy diễn direct từ 100%.
4. **Quy trình triển khai tiếp theo:** 
   - Chờ WBS07 tạo bảng và ghi nhận kết quả duyệt vào Review Store trên DB.
   - Sau đó bàn giao cho WBS08 thực hiện nạp vào Neo4j và kiểm tra đối chiếu graph.

---

## 7. Lệnh tái lập kiểm tra nguồn (tùy chọn, cần DB)

Từ thư mục gốc `FinMind`, mở PowerShell:

```powershell
# 1. Tái lập chạy lại extractor với code và nguồn gốc
.\.venv\Scripts\python.exe -X utf8 backend/scripts/recheck_nhan_original.py --output backend/.tmp/nhan-original-recheck

# 2. Kiểm định danh hai đầu với registry r1
.\.venv\Scripts\python.exe -X utf8 backend/scripts/audit_wbs06.py --owner NHAN --registry backend/src/sprint4_runtime/company.registry.20261030.r1.json --handoff-ref 1f72ccdadc195bdd7539b91c7df7fe587f84bc09 --output backend/.tmp/nhan-original-recheck/automatic_r1_audit.json

# 3. Chạy lại kiểm tra bằng chứng thẩm định
.\.venv\Scripts\python.exe -X utf8 backend/scripts/review_nhan_evidence.py --input backend/.tmp/nhan-original-recheck --output backend/.tmp/nhan-reviewed
```
Các lệnh trên cần kết nối DB nguồn với quyền SELECT; chỉ đọc DB và ghi file kết quả cục bộ, không ghi DB hoặc nạp Neo4j. Kết quả script là báo cáo kiểm tra, không thay thế quyết định chốt duyệt V4.
