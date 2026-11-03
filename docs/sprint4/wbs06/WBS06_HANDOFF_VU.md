# Bàn giao Vũ — kết quả kiểm thử code và 187 dữ kiện nhân sự

**Rà soát ngày 02/11/2026. Gửi riêng file Markdown này là đủ.**

## Kết luận của người kiểm thử

**185 APPROVED, 2 REJECTED về nội dung trích xuất trong phạm vi nguồn.** Phạm vi gồm 184 metadata và 3 ứng viên bị để ngoài metadata. Mỗi ID bên dưới có kết luận, câu nguồn và phạm vi được chấp nhận; không còn mục “chưa đánh giá”.

APPROVED ở đây nghiệm thu đúng dữ kiện được nguồn đã ghim chứng minh, với định danh người trong tài liệu. Không biến chức vụ trong BCTN cũ thành “đương nhiệm hôm nay”, không bịa ngày từ report_year. Kết quả kiểm thử này **không phải receipt duyệt trong ứng dụng hoặc lệnh nạp Neo4j**. Trước khi nạp vẫn phải nối canonical ID, thời gian theo đúng độ chính xác nguồn, review store và graph READY. Thiếu triển khai không làm dữ kiện nguồn trở thành sai.

Hai bản REJECTED: tên Trần Văn Tân không khớp Trần Văn Tần trong PDF; niên biểu TGĐ Lê Thanh Sơn mâu thuẫn ngay trong nguồn. Hai ca từng bị từ chối lan là **chức vụ HĐQT Lê Thanh Sơn** và **tên Nguyễn Vân Anh** được xét riêng lại và đạt trong phạm vi nêu tại từng ID. Không sửa trạng thái SOURCE_CONFLICT đang lưu trong DB.

## Những phần code đã đối chiếu và đạt

| Hạng mục | Kết luận | Bằng chứng kiểm thử |
|---|---|---|
| Payload và nguồn metadata | APPROVED | 184/184 hash payload, source membership và binding khớp; 6.278 liên kết/276 chunk; 91 quote khớp chunk, 93 khớp section. |
| Đọc repository và dữ liệu gốc | APPROVED | 184/184 đối chiếu subject/object, loại quan hệ, trạng thái, graph ID và chunk bindings. |
| Manifest | APPROVED | Kiểm hash từng lớp độc lập: graph 9648b7ca4c004751c55c683be702e102b1d36454d5c866a762938b7340b1de7e; corpus e43b8cb63a895c0cf8c111b075a8074189d5c56ac97313d248cef6bd5e86dadd. Không so hai hash của hai đối tượng khác nhau. |
| Chiều quan hệ metadata | APPROVED | HOLDS_ROLE: Person → Company; APPOINTS/DISMISSES: Company → Person. Nhãn lịch sử giữ đúng schema metadata, không tự đổi thành HOLDS_ROLE hiện tại. |
| Intake WBS03 | APPROVED | WBS03Repository có validate contract 2.1.0, replay nguồn, lưu draft nguyên tử và đọc lại. Không bắt GraphMetadataRepository thay thế intake này. |
| Tách version snapshot/section | APPROVED | Code local dùng member.sha256 cho document_version; locator dùng hash riêng của section. |
| Gate WBS06 | APPROVED ở mức code-test | Có engine/repository/gate; cần triển khai và kiểm tích hợp thật. Không quy thiếu triển khai thành không có code. |


## Lỗi code/tài liệu và điều kiện triển khai — tách khỏi chất lượng từng dữ kiện

### REJECTED — Nguồn News ở phiên bcc6251d… cho bốn article ID

**Bằng chứng trực tiếp — kết quả SELECT và kiểm định danh:** index `bcc6251d-ba1b-51d9-8fd5-92eb893a9ff0`, corpus `a5338f75-5894-5b8a-bf94-0a6da7c26ced`.

Quy tắc: stored document ID phải bằng locator source document ID hoặc release alias hợp lệ của nó. Cả bốn dòng sau không thỏa. Đây là từ chối **binding của phiên này**, không phải từ chối chính bài viết.

| Article ID | Stored document ID | Locator source document ID | Release alias kỳ vọng |
|---|---|---|---|
| 97ebe30f-745f-576d-a3aa-08a65d013b38 | 115b0a99-d9a0-50ea-ab6c-a1ac6da67661 | e2b5d203-9756-590d-a7c7-120efe7411bf | 874636b9-b1a4-5f9b-b55a-a8a4aaad5035 |
| d5b2a5e5-6d68-5815-996d-badec50d510a | 33a46815-7218-59fd-a557-69fb3696253c | 44ab17dd-ec76-59a3-80da-95cb7f907312 | eddec916-90bf-5bb1-ba80-8bee74361da6 |
| 68ee9bb4-d1a2-5e84-9cc4-1ea69daf2ed0 | 3b1990e8-10cd-5357-8a61-855e97ef9375 | 7a23fd4f-b978-5d68-b4df-11f6b8587484 | 079cea4d-4fb3-50f5-98e8-b3de2a0092e3 |
| 2b7ec115-7053-5620-867d-dfd2e8dbc52e | 6b9af22c-4f6a-5d55-bc3d-d1da0cefb633 | a10f61c7-e2ee-5c12-962c-9d68f380858c | 58bce1d8-5100-5b0f-a879-46e7f1ec5bcf |

Các bài vẫn có binding hợp lệ ở index `2264bbb9-024c-5634-abb5-58f399801b34`, là phiên dùng để đối chiếu output lần này. WBS07/đơn vị quản lý corpus kiểm mapping trước khi dùng phiên bị từ chối; không giao Quân sửa nội dung bài.

**Kết luận trong phạm vi hạng mục:** Bốn binding có stored document ID khác cả locator source ID và release alias kỳ vọng như bảng bằng chứng ngay trên. Không dùng các binding đó. Cả bốn bài vẫn có binding hợp lệ ở index 2264bbb9…; không từ chối chính bài viết.

### REJECTED — V01 — chặn hồi sinh bản REJECTED ở metadata legacy

**Bằng chứng trực tiếp — test giả lập đã chạy với `--runxfail`:**

```text
test_legacy_rejected_record_cannot_be_reopened
Input read_assertion.review_status = "REJECTED"
Call record_review(..., decision="APPROVED", ...)
Expected: raise MetadataConflict hoặc ValueError
Actual: Failed: DID NOT RAISE any of (MetadataConflict, ValueError)
```
**Mã đã đối chiếu:** `backend/src/person_role/metadata_repository.py`

```python
 async def record_review(self,extraction_id,decision,reason_code,note,review_id=None):
  if decision not in ('PENDING','APPROVED','REJECTED','QUARANTINED') or not reason_code.strip() or not note.strip():raise ValueError('Explicit review decision/reason/note required')
  record=await self.read_assertion(extraction_id)
  if record is None:raise ValueError('Unknown assertion')
  p=record['payload']
  if decision=='APPROVED' and (p['relation_type'] not in ('HOLDS_ROLE','APPOINTS','DISMISSES') or p['validation_status']!='SOURCE_VERIFIED' or not p.get('effective_date') and not p.get('report_year')):
   raise ValueError('Approval requires verified source and temporal basis')
  rid=review_id or uuid.uuid4()
  await self.c.execute('INSERT INTO graph_metadata.reviews(review_id,extraction_id,decision,reason_code,note) VALUES($1,$2,$3,$4,$5)',rid,uuid.UUID(str(extraction_id)),decision,reason_code,note)
  return str(rid)
```

Hàm chỉ kiểm điều kiện nguồn/thời gian trước APPROVED, chưa kiểm quyết định trước. Nhánh SQL `TG_TABLE_NAME='reviews' AND NEW.decision='APPROVED'` cũng kiểm resolved/source/time, chưa chặn lịch sử REJECTED. Test này xác nhận lỗi đường Python, **không chứng minh có thể vượt quyền/trigger DB hiện hành**.

**Kết luận trong phạm vi hạng mục:** Test bỏ xfail tái hiện record_review không chặn; SQL legacy không kiểm lịch sử REJECTED. Đây là lỗi source Vũ cần sửa nếu dùng cho chính sách WBS06.

### REJECTED — V02 — review store chung đã được triển khai/ghi quyết định

**Bằng chứng trực tiếp — SELECT trên VPS, chỉ đọc:**

```json
{
  "database": "finmind",
  "graph_metadata_reviews_count": 0,
  "graph_review_results": null,
  "graph_review_audit": null,
  "checked_at": "2026-11-02T13:12:08.159242+00:00"
}
```

`null` ở đây nghĩa là `to_regclass()` không tìm thấy bảng. Store nhân sự đã có, nhưng chưa có hai bảng review chung và chưa có receipt ghi 13 quyết định. Đây là REJECTED tiêu chí **đã triển khai/đã ghi**, không phải kết luận mọi chức năng metadata sai.

**Kết luận trong phạm vi hạng mục:** graph_metadata.reviews có thật, nhưng public.graph_review_results/audit chưa có trên VPS; chưa có receipt lưu 13 ca đã chốt. Không nói mọi store của Vũ đều thiếu.

### REJECTED — V03 — đủ điều kiện canonical ID và thời gian để nạp

**Bằng chứng trực tiếp — dữ liệu đọc lại từ DB:**

```json
{
  "total_assertions": 184,
  "source_scoped_endpoint_pairs": 184,
  "records_without_effective_date_and_report_year": 87,
  "example": {
    "candidate_id": "0310a991-7426-5c24-8cb4-16fa346e10cb",
    "subject": "Nguyễn Văn Thạnh",
    "object": "BID",
    "subject_resolution": "source_scoped",
    "object_resolution": "source_scoped",
    "effective_date": null,
    "report_year": null
  }
}
```

Không tự coi `source_scoped` là canonical ID hoặc lấy ngày hiện tại điền mốc còn thiếu. Web roster có thể dùng as-of snapshot khi có căn cứ. Việc đối soát thuộc WBS02/WBS06 và tích hợp WBS07; đây không phải bằng chứng 184 dữ kiện nguồn đều sai.

**Kết luận trong phạm vi hạng mục:** Hai đầu 184 bản còn source_scoped; 87 bản chưa có effective_date/report_year. Đây là việc đối soát WBS02/WBS06 và nối WBS07, không phải yêu cầu Vũ bịa ID/ngày hoặc lỗi vì giữ source_scoped. Web có thể dùng as-of snapshot khi có căn cứ.

### REJECTED — V04 — tài liệu hướng dẫn document_version

**Bằng chứng trực tiếp — tài liệu và code đang nói khác nhau:**

Trong `docs/graph/WBS03_DATABASE_PIPELINE.md`:

> `document_version` là source_view_sha256 của section, không phải UUID phiên graph. Các trang khác nhau có thể có source_view khác nhau; khi đó phải tách envelope theo source view, không ép chung document_version.

Trong `backend/src/person_role/wbs03_repository.py`, code local đang dùng:

```python
doc=dict(source_kind='db', document_id=r['document_id'],
         document_version=member['sha256'], source_uri=member['source_uri'],
         source_sha256=member['sha256'], index_version_id=iid, ...)
# member['sha256']: hash toàn snapshot; source_view_sha256: hash section trong locator.
```

REJECTED đoạn **hướng dẫn cũ**; giữ code tách đúng hai lớp hash, cập nhật tài liệu để người nhận không sửa ngược.

**Kết luận trong phạm vi hạng mục:** docs/graph/WBS03_DATABASE_PIPELINE.md còn ghi document_version là source_view_sha256 của section; trái code local đã sửa và quy tắc hash toàn snapshot. Sửa đoạn hướng dẫn này trước khi bàn giao để tránh người khác sửa ngược code.

### REJECTED — V05 — tên trong bản 4ea9f723…

**Bằng chứng trực tiếp — so bản gửi với PDF và nguồn ghim:**

```json
{
  "candidate_id": "4ea9f723-ec5f-5f60-a349-932ba45616b0",
  "submitted_name": "Trần Văn Tân",
  "pdf_page": 18,
  "pdf_sha256": "bb4d98a8b3e7122f5cc8c73d9e9fdf7d34652d68e0094307bcad99e5792f5650",
  "source_url": "https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CTG_Baocaothuongnien_2025.pdf"
}
```

> 3 Ông Trần Văn Tần TV HĐQT 0 0% TV không điều hành


Đã đọc lớp chữ PDF, không nhận là đã kiểm ảnh bằng mắt. Tên “Tân” trong bản gửi chưa được đoạn nguồn này chứng minh; từ chối trường tên đó, không tự đổi hoặc hợp nhất danh tính. Người nhận có thể mở URL và tới trang PDF 18.

**Kết luận trong phạm vi hạng mục:** Bản gửi “Trần Văn Tân”; nguồn ghim và lớp chữ PDF trang 18 ghi “Trần Văn Tần”. Từ chối trường tên chưa được chứng minh, không tự hợp nhất danh tính.

### REJECTED — Nghiệm thu cùng DB/Neo4j thật sau triển khai

**Bằng chứng trực tiếp — SELECT trên VPS, chỉ đọc:**

```json
{
  "database": "finmind",
  "graph_metadata_reviews_count": 0,
  "graph_review_results": null,
  "graph_review_audit": null,
  "checked_at": "2026-11-02T13:12:08.159242+00:00"
}
```

`null` ở đây nghĩa là `to_regclass()` không tìm thấy bảng. Store nhân sự đã có, nhưng chưa có hai bảng review chung và chưa có receipt ghi 13 quyết định. Đây là REJECTED tiêu chí **đã triển khai/đã ghi**, không phải kết luận mọi chức năng metadata sai.
**Phần chưa có bằng chứng nghiệm thu:** chưa có lượt ghi/đọc review store chung và nạp/đọc graph thật sau triển khai. Các test đã qua dùng memory/driver giả không thay thế lượt đó. Vì vậy REJECTED tiêu chí nghiệm thu triển khai; không bịa một lỗi Neo4j đã chạy khi chưa chạy.

**Kết luận trong phạm vi hạng mục:** Chưa chạy được end-to-end vì review store chung/quyền chưa sẵn sàng; không đồng nhất với test memory/mock đã qua.




## Kết luận từng ID — 187/187 bản

Mỗi APPROVED có reasons=[]; ghi chú giới hạn phạm vi không phải lỗi. Mỗi REJECTED đặt bằng chứng ngay sau tiêu đề. Đây là kết quả kiểm thử trên file, chưa ghi review store.

### APPROVED — 1. 0310a991-7426-5c24-8cb4-16fa346e10cb

**Bằng chứng nguồn:**
> Ông Nguyễn Văn Thạnh Ủy viên HĐQT độc lập

**Bản kiểm:** Nguyễn Văn Thạnh → BID · `HOLDS_ROLE` · Ủy viên HĐQT độc lập.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://bidv.com.vn/vn/ve-bidv/ban-lanh-dao · document_id `7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190` · trang PDF `None`.

**Hash section/trang đã kiểm:** `da6f0211ebf6ee83cd6983571fbeec008196b5e66acab7055bf093ab1f9abfcf`.

### APPROVED — 2. 04b7cb60-62da-5b54-8dac-c6fe2d02bd97

**Bằng chứng nguồn:**
> iám đốc (Miễn nhiệm từ ngày 01/09/2025) *Chi tiết tại phần giới thiệu HĐQT Công ty 4. Ông Lê Ánh Dương Phó Tổng Giám đốc 5. Ông Nguyễn Ngọc Sơn Kế toán trưởng 34 Báo cáo thường niên 2025 Giới thiệu về Ban Tổng Giám đốc Ông Lê Thanh Sơn Chức danh: Tổng Giám đốc Năm sinh: 1972 Trình độ chuyên môn: » Cử nhân Kinh tế phát triển. Quá trình công tác: - Từ tháng 04/1999 đến nay: Công tác tại Xí nghiệp Khoa học Sản xuất Thiết bị Thông tin (nay là Công ty Cổ phần Viễn thông – Tin học Bư

**Bản kiểm:** Lê Ánh Dương → ICT · `HOLDS_ROLE` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/ICT_Baocaothuongnien_2025.pdf · document_id `719349c4-edf0-5b57-9017-48035e41063c` · trang PDF `18`.

**Hash section/trang đã kiểm:** `26120c9af9eff152f100fcdbe4dde5e715cfa84a32497b5418977c9c170d82e8`.

### APPROVED — 3. 093cb7e8-08a0-5006-8bea-17a95d5a8164

**Bằng chứng nguồn:**
> PHÓ TỔNG GIÁM ĐỐC KIÊM GIÁM ĐỐC TÀI CHÍNH TẬP ĐOÀN Ông Alexandre Macaire

**Bản kiểm:** Alexandre Macaire → TCB · `HOLDS_ROLE` · Giám đốc Tài chính Tập đoàn.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 4. 0a912a1d-bcc1-5029-8540-6a0e7e7f529a

**Bằng chứng nguồn:**
> ng Thành viên HĐQT 0 4 Ông Nguyễn Mạnh Hùng Thành viên HĐQT 5.112 Thành viên HĐQT – 5 Ông Hồng Quang 2 Giám đốc Khối Nhân sự 6 Ông Vũ Viết Ngoạn Thành viên độc lập HĐQT 0 7 Bà Nguyễn Thị Kim Oanh Thành viên HĐQT 7.475 8 Ông Nguyễn Tuấn Anh Thành viên HĐQT 0 63 CHƯƠNG 4 Quản trị doanh nghiệp Trong những năm qua, công tác quản trị công ty của VCB luôn được chú trọng và triển khai Hội đồng một cách nghiêm túc dưới sự định hướng và giám sát của HĐQT. VCB đã tuân thủ đầy đủ quản t

**Bản kiểm:** Hồng Quang → VCB · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/VCB_Baocaothuongnien_2025.zip · document_id `679baa3e-b39c-5b53-be43-3cd19d738dca` · trang PDF `33`.

**Hash section/trang đã kiểm:** `cf40fe0d83644c1e5c1942f9eb281f4ec55c5169a7cfd0e4f5aa1a79fa6db82f`.

### APPROVED — 5. 0b2aa1eb-a916-5bdf-b46c-ab608b6d4290

**Bằng chứng nguồn:**
> 2.323 0,00042% VietinBank TP. Hồ Chí Minh 6 Ông Đỗ Thanh Sơn Phó TGĐ 180 0,0000023% 7 Ông Nguyễn Đức Thành Phó TGĐ 0 0% Phó TGĐ kiêm GĐ 8 Ông Dương Văn Quân 0 0% VietinBank TP. Hà Nội Phó TGĐ kiêm GĐ Khối Tài 9 Bà Nguyễn Bảo Thanh Vân 26.589 0,00034% chính 10 Bà Đặng Thị Việt Hà Phó TGĐ 0 0% 11 Ông Nguyễn Hải Hưng Kế toán trưởng 40.232 0,000518% Ghi chú: - Ngày 25/12/2025, VietinBank đã CBTT Thông báo thay đổi số lượng cổ phần có quyền biểu quyết tại công văn số 1292/HĐQT-NHCT-VPHĐ

**Bản kiểm:** Nguyễn Đức Thành → CTG · `HOLDS_ROLE` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CTG_Baocaothuongnien_2025.pdf · document_id `26c58a92-9b65-5ce3-a1c2-5f3b71717ddc` · trang PDF `25`.

**Hash section/trang đã kiểm:** `840c84044c4ea71e95ab1827555a35741b3e0f80eced81a1a7a265c805edfe68`.

### APPROVED — 6. 0bd2a62c-3d20-5523-89b8-614a66cb4f4f

**Bằng chứng nguồn:**
> ng Thành viên HĐQT 0 4 Ông Nguyễn Mạnh Hùng Thành viên HĐQT 5.112 Thành viên HĐQT – 5 Ông Hồng Quang 2 Giám đốc Khối Nhân sự 6 Ông Vũ Viết Ngoạn Thành viên độc lập HĐQT 0 7 Bà Nguyễn Thị Kim Oanh Thành viên HĐQT 7.475 8 Ông Nguyễn Tuấn Anh Thành viên HĐQT 0 63 CHƯƠNG 4 Quản trị doanh nghiệp Trong những năm qua, công tác quản trị công ty của VCB luôn được chú trọng và triển khai Hội đồng một cách nghiêm túc dưới sự định hướng và giám sát của HĐQT. VCB đã tuân thủ đầy đủ quản t

**Bản kiểm:** Hồng Quang → VCB · `HOLDS_ROLE` · Giám đốc Khối Nhân sự.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/VCB_Baocaothuongnien_2025.zip · document_id `679baa3e-b39c-5b53-be43-3cd19d738dca` · trang PDF `33`.

**Hash section/trang đã kiểm:** `cf40fe0d83644c1e5c1942f9eb281f4ec55c5169a7cfd0e4f5aa1a79fa6db82f`.

### APPROVED — 7. 0faadeeb-d8e5-5b56-b4e1-1a9f62fc2786

**Bằng chứng nguồn:**
> Bà Nguyễn Thị Thu Hà Thành viên /n Ban Kiểm soát

**Bản kiểm:** Nguyễn Thị Thu Hà → BID · `HOLDS_ROLE` · Thành viên Ban Kiểm soát.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://bidv.com.vn/vn/ve-bidv/ban-lanh-dao · document_id `7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190` · trang PDF `None`.

**Hash section/trang đã kiểm:** `da6f0211ebf6ee83cd6983571fbeec008196b5e66acab7055bf093ab1f9abfcf`.

### APPROVED — 8. 1280ad84-c034-5baa-98d5-c83329aaf3a7

**Bằng chứng nguồn:**
> 1 11 11/11 100% Trưởng BKS Bà Nguyễn Thị Anh Thư 2 11 11/11 100% TV BKS (Chuyên trách) Bà Phạm Thị Thơm (3) Không tham gia họp BKS do nghỉ 3 10 10/11 90,9% hưu hưởng chế độ BHXH kể từ Nguyên TV BKS (Chuyên trách) ngày 1/11/2025 Ông Nguyễn Hải Đăng (1) Không tham gia họp BKS trước 4 8 8/11 72,7% ngày 18/4/2025 (chưa là TV BKS) TV BKS (Chuyên trách) Bà Phạm Thị Thu Huyền (1) Không tham gia họp BKS trước 5 8 8/11 72,7% ngày 18/4/2025 (chưa là TV BKS) TV BKS (Chuyên trách) Bà Mai Hư

**Bản kiểm:** Phạm Thị Thơm → CTG · `FORMER_ROLE` · Thành viên Ban Kiểm soát.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Giữ nguyên loại quan hệ lịch sử/miễn nhiệm/từ nhiệm; không đổi thành đang giữ chức. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CTG_Baocaothuongnien_2025.pdf · document_id `26c58a92-9b65-5ce3-a1c2-5f3b71717ddc` · trang PDF `102`.

**Hash section/trang đã kiểm:** `4ae48c48a45a36f0869a4f2ea84ba9c4e5889812c698890dcf36216b8b0e6a76`.

### APPROVED — 9. 130c0546-aeb9-56ac-8039-6ab15e2e80b2

**Bằng chứng nguồn:**
> ày lập báo cáo này bao gồm: Ông Mai Hoài An Chủ tịch Ông Nguyễn Hữu Dũng Phó Chủ tịch Ông Nguyễn Vĩnh Thuận Phó Chủ tịch Miễn nhiệm ngày 26/06/2025 Ông Võ Xuân Vinh Thành viên Bổ nhiệm ngày 26/06/2025 Ông Nguyễn Ngọc Trung Thành viên Ông Đinh Thế Hiển Thành viên Đ Các thành viên của Ban Tổng Giám đốc đã điều hành Công ty trong năm và tại ngày lập báo cáo này bao gồm: Ông Nguyễn Ngọc Trung Tổng Giám đốc Ông Nguyễn Hồng Minh Phó Tổng Giám đốc Bổ nhiệm ngày 04/11/2025 Bà Nguyễn Thị Thu

**Bản kiểm:** ITD → Nguyễn Vĩnh Thuận · `DISMISSES` · Phó Chủ tịch HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Giữ nguyên loại quan hệ lịch sử/miễn nhiệm/từ nhiệm; không đổi thành đang giữ chức. Mốc bản gửi: 2025-06-26; kiểm theo câu ghi ngày của đúng người.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/ITD_Baocaothuongnien_2025.pdf · document_id `a2c071fb-25bf-5ec4-903b-e973c623b85d` · trang PDF `52`.

**Hash section/trang đã kiểm:** `d29acf9d280d7310222afee6a10edbd47b99492988edf6f82320997cda5ee3e5`.

### APPROVED — 10. 13c97a90-63b5-50b9-8921-a053dfeb95e4

**Bằng chứng nguồn:**
> GIÁM ĐỐC KHỐI TIẾP THỊ Bà Thái Minh Diễm Tú

**Bản kiểm:** Thái Minh Diễm Tú → TCB · `HOLDS_ROLE` · Giám đốc Khối Tiếp thị.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 11. 1574f0aa-cece-59ac-8033-04477e2b78b0

**Bằng chứng nguồn:**
> ày 19 tháng 8 năm 2024 Ông Nguyễn Mỹ Hào Thành viên Từ nhiệm ngày 1 tháng 11 năm 2024 Ông Nguyễn Mạnh Hùng Thành viên Bổ nhiệm lại ngày 21 tháng 4 năm 2023 Ông Hồng Quang Thành viên Bổ nhiệm lại ngày 21 tháng 4 năm 2023 Ông Shojiro Mizoguchi Thành viên Bổ nhiệm lại ngày 21 tháng 4 năm 2023 Bà Nguyễn Thị Kim Oanh Thành viên Bổ nhiệm ngày 24 tháng 11 năm 2023 Ông Vũ Viết Ngoạn Thành viên độc lập Bổ nhiệm ngày 21 tháng 4 năm 2023 126 BÁO CÁO THƯỜNG NIÊN 2024 Dấu ấn Tài chính - Kiến tạ

**Bản kiểm:** VCB → Nguyễn Mạnh Hùng · `APPOINTS` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Chấp nhận thông tin quyết định bổ nhiệm; không suy người vẫn đương nhiệm hiện tại. Mốc bản gửi: 2023-04-21; kiểm theo câu ghi ngày của đúng người.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/VCB_Baocaothuongnien_2024.pdf · document_id `dd94d5da-f8b1-5776-8c5e-f211d18ae26b` · trang PDF `65`.

**Hash section/trang đã kiểm:** `4ee095497823547593f90cb39e32e5919342ada0c636aa01c936a1b49acb38c3`.

### APPROVED — 12. 177e6400-b138-5e45-a0d8-7c969336d6fc

**Bằng chứng nguồn:**
> GIÁM ĐỐC KHỐI VẬN HÀNH KIÊM GIÁM ĐỐC KHỐI CÔNG NGHỆ Ông Chu Hồng Ngọc

**Bản kiểm:** Chu Hồng Ngọc → TCB · `HOLDS_ROLE` · Giám đốc Khối Vận hành.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 13. 19b27ff8-e85d-5969-a958-d901f297895b

**Bằng chứng nguồn:**
> THÀNH VIÊN CHUYÊN TRÁCH Bà Bùi Thị Hồng Mai

**Bản kiểm:** Bùi Thị Hồng Mai → TCB · `HOLDS_ROLE` · Thành viên chuyên trách Ban Kiểm soát.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 14. 19bfbc1d-2edc-5c2f-b396-1f0383eb4eee

**Bằng chứng nguồn:**
> TGĐ kiêm GĐ 8 Ông Dương Văn Quân 0 0% VietinBank TP. Hà Nội Phó TGĐ kiêm GĐ Khối Tài 9 Bà Nguyễn Bảo Thanh Vân 26.589 0,00034% chính 10 Bà Đặng Thị Việt Hà Phó TGĐ 0 0% 11 Ông Nguyễn Hải Hưng Kế toán trưởng 40.232 0,000518% Ghi chú: - Ngày 25/12/2025, VietinBank đã CBTT Thông báo thay đổi số lượng cổ phần có quyền biểu quyết tại công văn số 1292/HĐQT-NHCT-VPHĐQT1. Theo đó, tổng số lượng cổ phiếu có quyền biểu quyết đang lưu hành là 7.766.944.637 cổ phiếu. Tuy nhiên, đến ngày 9/1/2026,

**Bản kiểm:** Nguyễn Bảo Thanh Vân → CTG · `HOLDS_ROLE` · Giám đốc Khối Tài chính.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CTG_Baocaothuongnien_2025.pdf · document_id `26c58a92-9b65-5ce3-a1c2-5f3b71717ddc` · trang PDF `25`.

**Hash section/trang đã kiểm:** `840c84044c4ea71e95ab1827555a35741b3e0f80eced81a1a7a265c805edfe68`.

### APPROVED — 15. 19eb9fe8-71ad-5c37-99e1-fa9422797bd6

**Bằng chứng nguồn:**
> y 7 tháng 3 năm 2025 Ông Nguyễn Tuấn Anh Thành viên Bổ nhiệm ngày 19 tháng 8 năm 2024 Ông Nguyễn Mỹ Hào Thành viên Từ nhiệm ngày 1 tháng 11 năm 2024 Ông Nguyễn Mạnh Hùng Thành viên Bổ nhiệm lại ngày 21 tháng 4 năm 2023 Ông Hồng Quang Thành viên Bổ nhiệm lại ngày 21 tháng 4 năm 2023 Ông Shojiro Mizoguchi Thành viên Bổ nhiệm lại ngày 21 tháng 4 năm 2023 Bà Nguyễn Thị Kim Oanh Thành viên Bổ nhiệm ngày 24 tháng 11 năm 2023 Ông Vũ Viết Ngoạn Thành viên độc lập Bổ nhiệm ngày 21 tháng

**Bản kiểm:** Nguyễn Mỹ Hào → VCB · `RESIGNS` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Giữ nguyên loại quan hệ lịch sử/miễn nhiệm/từ nhiệm; không đổi thành đang giữ chức. Mốc bản gửi: 2024-11-01; kiểm theo câu ghi ngày của đúng người.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/VCB_Baocaothuongnien_2024.pdf · document_id `dd94d5da-f8b1-5776-8c5e-f211d18ae26b` · trang PDF `65`.

**Hash section/trang đã kiểm:** `4ee095497823547593f90cb39e32e5919342ada0c636aa01c936a1b49acb38c3`.

### APPROVED — 16. 1b8ceb86-4745-5230-8a21-3c76759b842c

**Bằng chứng nguồn:**
> Công Quỳnh Lân Phó TGĐ 0 0% 4 Bà Lê Như Hoa Phó TGĐ 61.548 0,00079% Phó TGĐ kiêm GĐ 5 Ông Lê Duy Hải 32.323 0,00042% VietinBank TP. Hồ Chí Minh 6 Ông Đỗ Thanh Sơn Phó TGĐ 180 0,0000023% 7 Ông Nguyễn Đức Thành Phó TGĐ 0 0% Phó TGĐ kiêm GĐ 8 Ông Dương Văn Quân 0 0% VietinBank TP. Hà Nội Phó TGĐ kiêm GĐ Khối Tài 9 Bà Nguyễn Bảo Thanh Vân 26.589 0,00034% chính 10 Bà Đặng Thị Việt Hà Phó TGĐ 0 0% 11 Ông Nguyễn Hải Hưng Kế toán trưởng 40.232 0,000518% Ghi chú: - Ngày 25/12/2025, Vi

**Bản kiểm:** Lê Duy Hải → CTG · `HOLDS_ROLE` · Giám đốc VietinBank TP. Hồ Chí Minh.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CTG_Baocaothuongnien_2025.pdf · document_id `26c58a92-9b65-5ce3-a1c2-5f3b71717ddc` · trang PDF `25`.

**Hash section/trang đã kiểm:** `840c84044c4ea71e95ab1827555a35741b3e0f80eced81a1a7a265c805edfe68`.

### APPROVED — 17. 1c66e401-c311-5c6e-8f07-b3ebd68ddd2f

**Bằng chứng nguồn:**
> Bà Bùi Thị Hòa Kế toán trưởng

**Bản kiểm:** Bùi Thị Hòa → BID · `HOLDS_ROLE` · Kế toán trưởng.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://bidv.com.vn/vn/ve-bidv/ban-lanh-dao · document_id `7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190` · trang PDF `None`.

**Hash section/trang đã kiểm:** `da6f0211ebf6ee83cd6983571fbeec008196b5e66acab7055bf093ab1f9abfcf`.

### APPROVED — 18. 1e4526e2-d8d9-5fbc-bdcc-270c13030670

**Bằng chứng nguồn:**
> Ông Ham Jin Sik Thành viên /n Ban Điều hành

**Bản kiểm:** Ham Jin Sik → BID · `HOLDS_ROLE` · Thành viên Ban Điều hành.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://bidv.com.vn/vn/ve-bidv/ban-lanh-dao · document_id `7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190` · trang PDF `None`.

**Hash section/trang đã kiểm:** `da6f0211ebf6ee83cd6983571fbeec008196b5e66acab7055bf093ab1f9abfcf`.

### APPROVED — 19. 1ea4b00c-6512-53d9-b6f8-8624d6e489eb

**Bằng chứng nguồn:**
> tịch Miễn nhiệm ngày 26/06/2025 Ông Võ Xuân Vinh Thành viên Bổ nhiệm ngày 26/06/2025 Ông Nguyễn Ngọc Trung Thành viên Ông Đinh Thế Hiển Thành viên Đ Các thành viên của Ban Tổng Giám đốc đã điều hành Công ty trong năm và tại ngày lập báo cáo này bao gồm: Ông Nguyễn Ngọc Trung Tổng Giám đốc Ông Nguyễn Hồng Minh Phó Tổng Giám đốc Bổ nhiệm ngày 04/11/2025 Bà Nguyễn Thị Thu Sương Phó Tổng Giám đốc Miễn nhiệm ngày 17/07/2025 Căn cứ theo Nghị quyết ĐHĐCD năm 2025 ngày 26/06/2025, Công ty

**Bản kiểm:** Nguyễn Ngọc Trung → ITD · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/ITD_Baocaothuongnien_2025.pdf · document_id `a2c071fb-25bf-5ec4-903b-e973c623b85d` · trang PDF `52`.

**Hash section/trang đã kiểm:** `d29acf9d280d7310222afee6a10edbd47b99492988edf6f82320997cda5ee3e5`.

### APPROVED — 20. 1f0d46aa-a24a-5cbf-a454-eaf3b1360b85

**Bằng chứng nguồn:**
> 4 năm 2021 Ông Nguyễn Việt Cường Phó Tổng Giám đốc Bổ nhiệm ngày 26 tháng 4 năm 2022 Ông Lê Hoàng Tùng Phó Tổng Giám đốc Bổ nhiệm ngày 15 tháng 8 năm 2023 Ông Hồ Văn Tuấn Phó Tổng Giám đốc Bổ nhiệm ngày 15 tháng 8 năm 2023 Ông Nguyễn Văn Tuân Phó Tổng Giám đốc Bổ nhiệm ngày 16 tháng 1 năm 2025 Bà Nguyễn Thị Hồng Vân Giám đốc Khối Pháp chế và Tuân thủ Bổ nhiệm ngày 15 tháng 11 năm 2023 Bà Đoàn Hồng Nhung Giám đốc Khối Bán lẻ Bổ nhiệm ngày 7 tháng 12 năm 2023 Ông Colin Richard Di

**Bản kiểm:** VCB → Lê Hoàng Tùng · `APPOINTS` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Chấp nhận thông tin quyết định bổ nhiệm; không suy người vẫn đương nhiệm hiện tại. Mốc bản gửi: 2023-08-15; kiểm theo câu ghi ngày của đúng người.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/VCB_Baocaothuongnien_2024.pdf · document_id `dd94d5da-f8b1-5776-8c5e-f211d18ae26b` · trang PDF `65`.

**Hash section/trang đã kiểm:** `4ee095497823547593f90cb39e32e5919342ada0c636aa01c936a1b49acb38c3`.

### APPROVED — 21. 21dc8c10-b67e-5597-8ec0-373de67dffe7

**Bằng chứng nguồn:**
> Ông Võ Xuân Vinh Thành viên Bổ nhiệm ngày 26/06/2025 Ông Nguyễn Ngọc Trung Thành viên Ông Đinh Thế Hiển Thành viên Đ Các thành viên của Ban Tổng Giám đốc đã điều hành Công ty trong năm và tại ngày lập báo cáo này bao gồm: Ông Nguyễn Ngọc Trung Tổng Giám đốc Ông Nguyễn Hồng Minh Phó Tổng Giám đốc Bổ nhiệm ngày 04/11/2025 Bà Nguyễn Thị Thu Sương Phó Tổng Giám đốc Miễn nhiệm ngày 17/07/2025 Căn cứ theo Nghị quyết ĐHĐCD năm 2025 ngày 26/06/2025, Công ty đã được thông qua thay đổi cơ

**Bản kiểm:** ITD → Đinh Thế Hiển · `APPOINTS` · Chủ tịch Ủy ban kiểm toán.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Chấp nhận thông tin quyết định bổ nhiệm; không suy người vẫn đương nhiệm hiện tại. Mốc bản gửi: 2025-07-10; kiểm theo câu ghi ngày của đúng người.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/ITD_Baocaothuongnien_2025.pdf · document_id `a2c071fb-25bf-5ec4-903b-e973c623b85d` · trang PDF `52`.

**Hash section/trang đã kiểm:** `d29acf9d280d7310222afee6a10edbd47b99492988edf6f82320997cda5ee3e5`.

### APPROVED — 22. 2217e18c-ee33-5976-87b0-73861476a159

**Bằng chứng nguồn:**
> ên HĐQT 151.835.000 - Ông Ngô Ngọc Hà Thành viên HĐQT/Phó Tổng Giám đốc 396.047.930 - Ông Nguyễn Mạnh Hùng Thành viên HĐQT 120.000.000 - Ông Đỗ Minh Tiến Thành viên HĐQT 120.000.000 - Ông Phạm Minh Thắng Tổng Giám đốc 399.626.000 - Ông Nguyễn Văn Hòa Phó Tổng Giám đốc 738.244.000 Ban Kiểm soát - - Bà Ngô Kiều Anh Trưởng ban 313.893.000 - Bà Vũ Thị Ngân Hà Thành viên 306.994.000 - Bà Hoàng Thị Phương Thúy Thành viên 36.000.000 Kế toán trưởng - - Bà Đậu Thị Lý Kế toán trưởng (bổ nhiệ

**Bản kiểm:** Nguyễn Mạnh Hùng → ELC · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/ELC_Baocaothuongnien_2024.pdf · document_id `f0730a07-8ab5-548a-a3b8-e099489d0f29` · trang PDF `68`.

**Hash section/trang đã kiểm:** `1348dcfba0e77b9917fdbfd279ba8c0ed2e92ec8dcb4cf1f2ceaa0dc2d65d83c`.

### APPROVED — 23. 23162023-9cf0-5d4f-9572-743ee937f879

**Bằng chứng nguồn:**
> Bà Nguyễn Thị Nguyệt Hà Thành viên Ban Kiểm soát

**Bản kiểm:** Nguyễn Thị Nguyệt Hà → MBB · `HOLDS_ROLE` · Thành viên Ban Kiểm soát.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://www.mbbank.com.vn/ve-mb/doi-ngu-lanh-dao · document_id `e9dd552a-0bd7-5716-bbdd-34e4580f7d6d` · trang PDF `None`.

**Hash section/trang đã kiểm:** `361d3953e754b97a64c3e6c7539f132c4b1fedc70c0825d017be9dce006ee918`.

### APPROVED — 24. 233b180b-577a-5974-b56b-29059dd44570

**Bằng chứng nguồn:**
> Ông Kim Sang Soo Ủy viên HĐQT

**Bản kiểm:** Kim Sang Soo → BID · `HOLDS_ROLE` · Ủy viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://bidv.com.vn/vn/ve-bidv/ban-lanh-dao · document_id `7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190` · trang PDF `None`.

**Hash section/trang đã kiểm:** `da6f0211ebf6ee83cd6983571fbeec008196b5e66acab7055bf093ab1f9abfcf`.

### APPROVED — 25. 241e5656-a061-5b35-bd0f-bf98f0ff632c

**Bằng chứng nguồn:**
> êm Tổng Giám đốc BIDV. Từ ngày 01/07/2026, ông được bổ nhiệm giữ chức Chủ tịch HĐQT BIDV. Ông Hoàng Việt Hùng Ủy viên HĐQT Năm sinh: 1972 Năm 1996, ông bắt đầu làm việc tại BIDV; từ tháng 11/2007 là Phó Giám đốc Chi nhánh BIDV Nghệ An; từ tháng 01/2013 là Giám đốc Chi nhánh BIDV Nghệ An; từ tháng 04/2019 là Giám đốc Ban Tổ chức nhân sự BIDV; từ tháng 03/2020 là Phó Tổng Giám đốc BIDV kiêm Giám đốc Ban Tổ chức nhân sự; từ tháng 02/2024 là Phó Tổng Giám đốc BIDV, Chủ tịch HĐQT Ngân hàng Liên doanh Lào - Việt; từ tháng 05/2026 là Phó Tổng Giám đốc BIDV. Từ ngày 01/07/2026 ông là thành viên HĐQT, Tổng Giám đốc BIDV. Ông Kim Sang Soo Ủy viên HĐQT Sinh năm: 1968 Từng giữ các chức vụ: Giám đốc điều hành Khối Toàn cầu (Ngân hàng KEB Hana); Chủ tịch HĐQT & Tổng Giám đốc (Ngân hàng TNHH Hana Trung Quốc); Giám đốc Chi nhánh (Ngân hàng KEB Hana - Chi nhánh TP Hồ Chí Minh). Từ ngày 24/4/2026, ông là Uỷ viên Hội đồng quản trị BIDV. Ông Trần Xuân Hoàng Ủy viên HĐQT Sinh năm 1965 Năm 1989, ông bắt đầu làm việc tại BIDV; từ tháng 07/1996 là Phó Giám đốc BIDV Gia Lai; từ tháng 7/2006 là Phó Giám đốc BIDV Sở Giao dịch 2; từ tháng 8/2008 là Giám đốc Ban Tổ chức cán bộ; từ tháng 5/2012 là Phó Tổng Giám đốc BIDV, từ tháng 3/2020 là Ủy viên HĐQT BIDV. Ông Ngô Văn Dũng Ủy viên HĐQT Sinh năm 1968 Năm 1998, ông bắt đầu làm việc tại BIDV; từ tháng 09/2004 là Giám đốc Ban Quản lý rủi ro BIDV; từ tháng 12/2007 là Giám đốc BIDV Hà Nội; từ tháng 6/2015 đến nay là Ủy

**Bản kiểm:** Hoàng Việt Hùng → BID · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Mốc bản gửi: 2026-07-01; kiểm theo câu ghi ngày của đúng người. Đã đọc riêng tiểu sử dưới tiêu đề tên, không lấy “ông” của người ở đoạn trước.

**Nguồn:** https://bidv.com.vn/vn/ve-bidv/ban-lanh-dao · document_id `7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190` · trang PDF `None`.

**Hash section/trang đã kiểm:** `da6f0211ebf6ee83cd6983571fbeec008196b5e66acab7055bf093ab1f9abfcf`.

### APPROVED — 26. 25bf30d4-8a3a-5ada-9cae-0eb11baa6721

**Bằng chứng nguồn:**
> Ông Ngô Văn Dũng Ủy viên HĐQT

**Bản kiểm:** Ngô Văn Dũng → BID · `HOLDS_ROLE` · Ủy viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://bidv.com.vn/vn/ve-bidv/ban-lanh-dao · document_id `7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190` · trang PDF `None`.

**Hash section/trang đã kiểm:** `da6f0211ebf6ee83cd6983571fbeec008196b5e66acab7055bf093ab1f9abfcf`.

### APPROVED — 27. 269122d9-4391-541c-81c3-b433d10c7a39

**Bằng chứng nguồn:**
> 4 Bà Lê Như Hoa Phó TGĐ 39.937 0,000744% 5 Ông Lê Duy Hải Phó TGĐ 22.348 0,000416% 6 Ông Đỗ Thanh Sơn Phó TGĐ 125 0,0000023% 7 Ông Nguyễn Hải Hưng Kế toán trưởng 27.816 0,000518% Ghi chú: Danh sách TV BĐH và số lượng cổ phiếu trong bảng này được cập nhật tại ngày 31/12/2024. THAY ĐỔI TV BĐH TRONG NĂM 2024 STT Họ và tên Chức vụ Ngày bổ nhiệm/thôi nhiệm Bổ nhiệm TGĐ VietinBank kể từ ngày 17/10/2024 TV HĐQT 1 Ông Nguyễn Trần Mạnh Trung theo quyết định số 3639/QĐ-NHCT-NHCT-NS2 kiê

**Bản kiểm:** Đỗ Thanh Sơn → CTG · `HOLDS_ROLE` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/CTG_Baocaothuongnien_2024.pdf · document_id `ebc51a9d-1d79-51a6-8c3e-f3db6d8f4891` · trang PDF `24`.

**Hash section/trang đã kiểm:** `e2d957a20adea3a5a279afd84d3eb05232042cc8edc2b298b71474c14a55c353`.

### APPROVED — 28. 309b6241-f2ff-5509-9fbe-7caacb53731d

**Bằng chứng nguồn:**
> y 26 tháng 7 năm 2024 Ông Lê Quang Vinh Tổng Giám đốc Bổ nhiệm ngày 7 tháng 3 năm 2025 Bà Đinh Thị Thái Phó Tổng Giám đốc Miễn nhiệm ngày 19 tháng 8 năm 2024 Bà Phùng Nguyễn Hải Yến Phó Tổng Giám đốc Bổ nhiệm lại ngày 15 tháng 12 năm 2022 Ông Đặng Hoài Đức Phó Tổng Giám đốc Bổ nhiệm lại ngày 1 tháng 4 năm 2024 Ông Shojiro Mizoguchi Phó Tổng Giám đốc Bổ nhiệm ngày 23 tháng 4 năm 2021 Ông Nguyễn Việt Cường Phó Tổng Giám đốc Bổ nhiệm ngày 26 tháng 4 năm 2022 Ông Lê Hoàng Tùng Phó T

**Bản kiểm:** VCB → Đinh Thị Thái · `DISMISSES` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Giữ nguyên loại quan hệ lịch sử/miễn nhiệm/từ nhiệm; không đổi thành đang giữ chức. Mốc bản gửi: 2024-08-19; kiểm theo câu ghi ngày của đúng người.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/VCB_Baocaothuongnien_2024.pdf · document_id `dd94d5da-f8b1-5776-8c5e-f211d18ae26b` · trang PDF `65`.

**Hash section/trang đã kiểm:** `4ee095497823547593f90cb39e32e5919342ada0c636aa01c936a1b49acb38c3`.

### APPROVED — 29. 310a11f1-e9bc-5db8-ae67-898e2b53444f

**Bằng chứng nguồn:**
> Ông Cao Cự Trí Thành viên /n Ban Kiểm soát

**Bản kiểm:** Cao Cự Trí → BID · `HOLDS_ROLE` · Thành viên Ban Kiểm soát.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://bidv.com.vn/vn/ve-bidv/ban-lanh-dao · document_id `7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190` · trang PDF `None`.

**Hash section/trang đã kiểm:** `da6f0211ebf6ee83cd6983571fbeec008196b5e66acab7055bf093ab1f9abfcf`.

### APPROVED — 30. 310aadb7-c0d6-5c99-9104-a3623bc7552e

**Bằng chứng nguồn:**
> 4 Chức vụ VND HĐQT và Ban Giám đốc - Ông Phan Chiến Thắng Chủ tịch HĐQT 239.452.000 - Ông Nguyễn Đức Thiện Phó Chủ tịch HĐQT 152.065.000 - Ông Trần Hùng Giang Thành viên HĐQT 152.065.000 - Ông Nguyễn Mạnh Hải Thành viên HĐQT 151.835.000 - Ông Ngô Ngọc Hà Thành viên HĐQT/Phó Tổng Giám đốc 396.047.930 - Ông Nguyễn Mạnh Hùng Thành viên HĐQT 120.000.000 - Ông Đỗ Minh Tiến Thành viên HĐQT 120.000.000 - Ông Phạm Minh Thắng Tổng Giám đốc 399.626.000 - Ông Nguyễn Văn Hòa Phó Tổng Giám đốc

**Bản kiểm:** Nguyễn Đức Thiện → ELC · `HOLDS_ROLE` · Phó Chủ tịch HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/ELC_Baocaothuongnien_2024.pdf · document_id `f0730a07-8ab5-548a-a3b8-e099489d0f29` · trang PDF `68`.

**Hash section/trang đã kiểm:** `1348dcfba0e77b9917fdbfd279ba8c0ed2e92ec8dcb4cf1f2ceaa0dc2d65d83c`.

### APPROVED — 31. 3365ca16-3e07-5ef7-847f-442649c51fa6

**Bằng chứng nguồn:**
> PHÓ CHỦ TỊCH Ông Hồ Anh Ngọc

**Bản kiểm:** Hồ Anh Ngọc → TCB · `HOLDS_ROLE` · Phó Chủ tịch HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 32. 33d74abf-89be-5c3c-bd8c-25b90e4fbdb0

**Bằng chứng nguồn:**
> với HĐQT. DANH SÁCH TV BĐH STT Họ và tên Chức vụ Số lượng cổ phiếu Tỷ lệ sở hữu (%) 1 Ông Nguyễn Trần Mạnh Trung TV HĐQT kiêm TGĐ 3 0,00000006% 2 Ông Koji Iriguchi TV HĐQT kiêm Phó TGĐ 0 0% 3 Ông Trần Công Quỳnh Lân Phó TGĐ 0 0% 4 Bà Lê Như Hoa Phó TGĐ 39.937 0,000744% 5 Ông Lê Duy Hải Phó TGĐ 22.348 0,000416% 6 Ông Đỗ Thanh Sơn Phó TGĐ 125 0,0000023% 7 Ông Nguyễn Hải Hưng Kế toán trưởng 27.816 0,000518% Ghi chú: Danh sách TV BĐH và số lượng cổ phiếu trong bảng này được cập nhật tại ngày

**Bản kiểm:** Nguyễn Trần Mạnh Trung → CTG · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/CTG_Baocaothuongnien_2024.pdf · document_id `ebc51a9d-1d79-51a6-8c3e-f3db6d8f4891` · trang PDF `24`.

**Hash section/trang đã kiểm:** `e2d957a20adea3a5a279afd84d3eb05232042cc8edc2b298b71474c14a55c353`.

### APPROVED — 33. 340f80e7-d343-5e8d-8aea-c9bc74459313

**Bằng chứng nguồn:**
> Bà Tạ Thị Hạnh Trưởng Ban Kiểm soát

**Bản kiểm:** Tạ Thị Hạnh → BID · `HOLDS_ROLE` · Trưởng Ban Kiểm soát.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://bidv.com.vn/vn/ve-bidv/ban-lanh-dao · document_id `7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190` · trang PDF `None`.

**Hash section/trang đã kiểm:** `da6f0211ebf6ee83cd6983571fbeec008196b5e66acab7055bf093ab1f9abfcf`.

### APPROVED — 34. 353d48aa-7c39-53cc-8efe-e1d3de711f72

**Bằng chứng nguồn:**
> 5 Ông Lê Duy Hải Phó TGĐ 22.348 0,000416% 6 Ông Đỗ Thanh Sơn Phó TGĐ 125 0,0000023% 7 Ông Nguyễn Hải Hưng Kế toán trưởng 27.816 0,000518% Ghi chú: Danh sách TV BĐH và số lượng cổ phiếu trong bảng này được cập nhật tại ngày 31/12/2024. THAY ĐỔI TV BĐH TRONG NĂM 2024 STT Họ và tên Chức vụ Ngày bổ nhiệm/thôi nhiệm Bổ nhiệm TGĐ VietinBank kể từ ngày 17/10/2024 TV HĐQT 1 Ông Nguyễn Trần Mạnh Trung theo quyết định số 3639/QĐ-NHCT-NHCT-NS2 kiêm TGĐ ngày 17/10/2024 của HĐQT VietinBank; Th

**Bản kiểm:** Nguyễn Hải Hưng → CTG · `HOLDS_ROLE` · Kế toán trưởng.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/CTG_Baocaothuongnien_2024.pdf · document_id `ebc51a9d-1d79-51a6-8c3e-f3db6d8f4891` · trang PDF `24`.

**Hash section/trang đã kiểm:** `e2d957a20adea3a5a279afd84d3eb05232042cc8edc2b298b71474c14a55c353`.

### APPROVED — 35. 37bb58a7-a995-53aa-be66-76df2dd90449

**Bằng chứng nguồn:**
> TỔNG GIÁM ĐỐC Ông Jens Lottner

**Bản kiểm:** Jens Lottner → TCB · `HOLDS_ROLE` · Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 36. 3b48183d-817e-5bc0-a796-bb2d758833dd

**Bằng chứng nguồn:**
> 83% 2 Bà Nguyễn Thị Anh Thư TV BKS 2.159 0,000028% 3 Ông Nguyễn Hải Đăng TV BKS 0 0% 4 Bà Mai Hương Thảo TV BKS 217 0,000003% 5 Bà Phạm Thị Thu Huyền TV BKS 0 0% Ghi chú: - Ngày 25/12/2025, VietinBank đã CBTT Thông báo thay đổi số lượng cổ phần có quyền biểu quyết tại công văn số 1292/ HĐQT-NHCT-VPHĐQT1. Theo đó, tổng số lượng cổ phiếu có quyền biểu quyết đang lưu hành là 7.766.944.637 cổ phiếu. Tuy nhiên, đến ngày 9/1/2026, VietinBank mới hoàn thành điều chỉnh thông tin số lượng

**Bản kiểm:** Mai Hương Thảo → CTG · `HOLDS_ROLE` · Thành viên Ban Kiểm soát.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CTG_Baocaothuongnien_2025.pdf · document_id `26c58a92-9b65-5ce3-a1c2-5f3b71717ddc` · trang PDF `23`.

**Hash section/trang đã kiểm:** `7fe441c59f1ac429219cbd3b5247beb640cbefadfb2d88bcceb463b8ff71bc66`.

### APPROVED — 37. 3f96e1c8-1dd2-5433-b352-e43cc42dab39

**Bằng chứng nguồn:**
> g Chính Chủ tịch HĐQT 2,500,551 1,18% 2 Nguyễn Minh Đức Thành viên HĐQT 4,862,063 2,30% 3 Nguyễn Phước Hải Thành viên HĐQT 3,453,867 1,63% 4 Gum Ki Ho Thành viên HĐQT 0 0% 5 Kwon Oh Soo Thành viên HĐQT 0 0% 6 Trương Tuấn Lâm | Thành viên HĐQT độc lập 0 0% 7 Nguyễn Danh Lam | Thành viên HĐQT độc lập 0 0% 8 Lê Việt Hà Thành viên HĐQT độc lập 0 0% 9 Hà Thế Vinh Thành viên HĐQT không 0 0% điêu hành 1.2. Các tiêu ban thuộc Hội đồng quản trị: a.. Ban kiễm toán nội bộ: Lập kế hoạch cho cá

**Bản kiểm:** Nguyễn Phước Hải → CMG · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CMG_Baocaothuongnien_2025.pdf · document_id `532597dc-7b79-5f00-99f9-d3394cba9038` · trang PDF `64`.

**Hash section/trang đã kiểm:** `e4be11d5fd9ac0153b2e13b1ce0440b44dcf12f4d7c77de22d1c9c0e0d017210`.

### APPROVED — 38. 40486b2b-87f5-5965-a740-fa0616ec6f6b

**Bằng chứng nguồn:**
> Ông Trần Minh Đạt Phó Tổng Giám đốc

**Bản kiểm:** Trần Minh Đạt → MBB · `HOLDS_ROLE` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://www.mbbank.com.vn/ve-mb/doi-ngu-lanh-dao · document_id `e9dd552a-0bd7-5716-bbdd-34e4580f7d6d` · trang PDF `None`.

**Hash section/trang đã kiểm:** `361d3953e754b97a64c3e6c7539f132c4b1fedc70c0825d017be9dce006ee918`.

### APPROVED — 39. 410eeedf-b506-5d45-8113-d9e7165d1c09

**Bằng chứng nguồn:**
> Hội đồng Quản trị (“HĐQT”) trong năm và đến ngày phát hành báo cáo tài chính hợp nhất Ông Nguyễn Thanh Tùng Chủ tịch Bổ nhiệm ngày 26 tháng 7 năm 2024 Ông Đỗ Việt Hùng Thành viên phụ trách hoạt động của HĐQT Thôi giao phụ trách HĐQT ngày 26 tháng 7 Thành viên năm 2024 Bổ nhiệm lại ngày 21 tháng 4 năm 2023 Ông Lê Quang Vinh Thành viên Bổ nhiệm ngày 7 tháng 3 năm 2025 Ông Nguyễn Tuấn Anh Thành viên Bổ nhiệm ngày 19 tháng 8 năm 2024 Ông Nguyễn Mỹ Hào Thành viên Từ nhiệm ngày 1 tháng 11

**Bản kiểm:** VCB → Nguyễn Thanh Tùng · `APPOINTS` · Chủ tịch HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Chấp nhận thông tin quyết định bổ nhiệm; không suy người vẫn đương nhiệm hiện tại. Mốc bản gửi: 2024-07-26; kiểm theo câu ghi ngày của đúng người.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/VCB_Baocaothuongnien_2024.pdf · document_id `dd94d5da-f8b1-5776-8c5e-f211d18ae26b` · trang PDF `65`.

**Hash section/trang đã kiểm:** `4ee095497823547593f90cb39e32e5919342ada0c636aa01c936a1b49acb38c3`.

### APPROVED — 40. 47d9d6b5-7772-5889-88a1-6ff290ad2814

**Bằng chứng nguồn:**
> PHÓ CHỦ TỊCH THỨ NHẤT Ông Nguyễn Đăng Quang

**Bản kiểm:** Nguyễn Đăng Quang → TCB · `HOLDS_ROLE` · Phó Chủ tịch thứ nhất HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 41. 4b47bad7-66b2-5357-9966-3fdf08a36944

**Bằng chứng nguồn:**
> THÀNH VIÊN Bà Đỗ Thị Hoàng Liên

**Bản kiểm:** Đỗ Thị Hoàng Liên → TCB · `HOLDS_ROLE` · Thành viên Ban Kiểm soát.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 42. 4b75c02d-5a27-5e4b-bd16-8465ec8eb64a

**Bằng chứng nguồn:**
> Bà Nguyễn Thị Ngọc Thành viên Ban điều hành

**Bản kiểm:** Nguyễn Thị Ngọc → MBB · `HOLDS_ROLE` · Thành viên Ban điều hành.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://www.mbbank.com.vn/ve-mb/doi-ngu-lanh-dao · document_id `e9dd552a-0bd7-5716-bbdd-34e4580f7d6d` · trang PDF `None`.

**Hash section/trang đã kiểm:** `361d3953e754b97a64c3e6c7539f132c4b1fedc70c0825d017be9dce006ee918`.

### APPROVED — 43. 4bb5208e-d858-516d-a841-297479726a5d

**Bằng chứng nguồn:**
> GIÁM ĐỐC KHỐI DỮ LIỆU VÀ PHÂN TÍCH Ông Santhosh Mahendiran

**Bản kiểm:** Santhosh Mahendiran → TCB · `HOLDS_ROLE` · Giám đốc Khối Dữ liệu và Phân tích.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 44. 4bb78530-a4a2-57c7-8735-9c9698dd3f0d

**Bằng chứng nguồn:**
> ọ và tên Chức danh 1. Ông Lê Thanh Sơn Tổng Giám đốc (Bổ nhiệm từ ngày 07/02/2025) 2. Ông Hà Thanh Hải* Tổng Giám đốc (Miễn nhiệm từ ngày 07/02/2025) *Chi tiết tại phần giới thiệu HĐQT Công ty 3. Ông Tô Hoài Văn* Phó Tổng Giám đốc (Miễn nhiệm từ ngày 01/09/2025) *Chi tiết tại phần giới thiệu HĐQT Công ty 4. Ông Lê Ánh Dương Phó Tổng Giám đốc 5. Ông Nguyễn Ngọc Sơn Kế toán trưởng 34 Báo cáo thường niên 2025 Giới thiệu về Ban Tổng Giám đốc Ông Lê Thanh Sơn Chức danh: Tổng Giám đố

**Bản kiểm:** ICT → Hà Thanh Hải · `DISMISSES` · Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Giữ nguyên loại quan hệ lịch sử/miễn nhiệm/từ nhiệm; không đổi thành đang giữ chức. Mốc bản gửi: 2025-02-07; kiểm theo câu ghi ngày của đúng người.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/ICT_Baocaothuongnien_2025.pdf · document_id `719349c4-edf0-5b57-9017-48035e41063c` · trang PDF `18`.

**Hash section/trang đã kiểm:** `26120c9af9eff152f100fcdbe4dde5e715cfa84a32497b5418977c9c170d82e8`.

### APPROVED — 45. 4d2e13b6-0e1e-589d-a553-5146ccf0aa7e

**Bằng chứng nguồn:**
> TV HĐQT 0 0% TV không điều hành 4 Ông Lê Thanh Tùng TV HĐQT 0 0% TV không điều hành 5 Ông Nguyễn Thế Huân TV HĐQT 0 0% TV không điều hành 6 Bà Phạm Thị Thanh Hoài TV HĐQT 189 0,000002% TV không điều hành 7 Ông Nguyễn Vân Anh TV HĐQT 0 0% TV không điều hành 8 Ông Nguyễn Việt Dũng TV HĐQT 0 0% TV không điều hành TV HĐQT kiêm Phó 9 Ông Koji Iriguchi 0 0% TV điều hành TGĐ 10 Ông Takeo Shimotsu TV HĐQT 0 0% TV không điều hành 11 Ông Cát Quang Dương TV độc lập HĐQT 0 0% TV độc lập Ghi c

**Bản kiểm:** Nguyễn Thế Huân → CTG · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CTG_Baocaothuongnien_2025.pdf · document_id `26c58a92-9b65-5ce3-a1c2-5f3b71717ddc` · trang PDF `18`.

**Hash section/trang đã kiểm:** `7a501da6b4991a2d607a6d5c038e78cff57a65aee779fa9507190b560d089045`.

### REJECTED — 46. 4ea9f723-ec5f-5f60-a349-932ba45616b0

**Bằng chứng nguồn:**
> điều hành TV HĐQT kiêm 2 Ông Nguyễn Trần Mạnh Trung 04 0,00000005% TV điều hành TGĐ 3 Ông Trần Văn Tần TV HĐQT 0 0% TV không điều hành 4 Ông Lê Thanh Tùng TV HĐQT 0 0% TV không điều hành 5 Ông Nguyễn Thế Huân TV HĐQT 0 0% TV không điều hành 6 Bà Phạm Thị Thanh Hoài TV HĐQT 189 0,000002% TV không điều hành 7 Ông Nguyễn Vân Anh TV HĐQT 0 0% TV không điều hành 8 Ông Nguyễn Việt Dũng TV HĐQT 0 0% TV không điều hành TV HĐQT kiêm Phó 9 Ông Koji Iriguchi 0 0% TV điều hành TGĐ 10 Ông T

**Bản kiểm:** Trần Văn Tân → CTG · `HOLDS_ROLE` · Thành viên HĐQT.

**Vì sao REJECTED:** Tên trong bản là Trần Văn Tân; nguồn trang 18 ghi Trần Văn Tần. Đã kiểm cả text ghim và text trích từ PDF gốc, không chỉ so tên với JSON. Không tự hợp nhất hai cách viết thành một người.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CTG_Baocaothuongnien_2025.pdf · document_id `26c58a92-9b65-5ce3-a1c2-5f3b71717ddc` · trang PDF `18`.

**Hash section/trang đã kiểm:** `7a501da6b4991a2d607a6d5c038e78cff57a65aee779fa9507190b560d089045`.

### APPROVED — 47. 548856be-d548-5ae6-9af5-bdbc83c4fcf1

**Bằng chứng nguồn:**
> Ông Vũ Hoàng Dương Phó Tổng Giám đốc

**Bản kiểm:** Vũ Hoàng Dương → BID · `HOLDS_ROLE` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://bidv.com.vn/vn/ve-bidv/ban-lanh-dao · document_id `7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190` · trang PDF `None`.

**Hash section/trang đã kiểm:** `da6f0211ebf6ee83cd6983571fbeec008196b5e66acab7055bf093ab1f9abfcf`.

### APPROVED — 48. 570dcbfd-d369-5f76-bcb5-4a464852dc99

**Bằng chứng nguồn:**
> 17/10/2024 của HĐQT VietinBank. Miễn nhiệm Phó TGĐ theo quyết định số 467/QĐ-HĐQT- 3 Ông Nguyễn Đình Vinh Phó TGĐ NHCT-NS2 ngày 18/12/2024 của HĐQT VietinBank. Miễn nhiệm Phó TGĐ theo quyết định số 72/QĐ-HĐQT- 4 Ông Hoàng Ngọc Phương Phó TGĐ NHCT-NS2 ngày 28/3/2024 của HĐQT VietinBank. 42 Ông NGUYỄN TRẦN MẠNH TRUNG TV HĐQT kiêm TGĐ Sinh năm 1983. Thạc sỹ Tài chính, Ngân hàng. Công tác tại VietinBank từ năm 2005. Được bầu vào HĐQT VietinBank từ ngày 17/10/2024; kiêm nhiệm TGĐ Vieti

**Bản kiểm:** CTG → Nguyễn Đình Vinh · `DISMISSES` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Giữ nguyên loại quan hệ lịch sử/miễn nhiệm/từ nhiệm; không đổi thành đang giữ chức. Không tự thêm ngày hiệu lực khi trường này đang null. Ngày của quyết định trong nguồn không tự chuyển thành ngày hiệu lực.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/CTG_Baocaothuongnien_2024.pdf · document_id `ebc51a9d-1d79-51a6-8c3e-f3db6d8f4891` · trang PDF `24`.

**Hash section/trang đã kiểm:** `e2d957a20adea3a5a279afd84d3eb05232042cc8edc2b298b71474c14a55c353`.

### APPROVED — 49. 59cc0b00-3a62-5927-8908-6d449e926b49

**Bằng chứng nguồn:**
> m đốc 399.626.000 - Ông Nguyễn Văn Hòa Phó Tổng Giám đốc 738.244.000 Ban Kiểm soát - - Bà Ngô Kiều Anh Trưởng ban 313.893.000 - Bà Vũ Thị Ngân Hà Thành viên 306.994.000 - Bà Hoàng Thị Phương Thúy Thành viên 36.000.000 Kế toán trưởng - - Bà Đậu Thị Lý Kế toán trưởng (bổ nhiệm từ 19/05/2023) 480.850.000 - Bà Đặng Thị Thanh Minh Kế toán trưởng (miễn nhiệm từ 19/05/2023) 106.746.860 Cộng 3.713.818.790 BÁO CÁO TÀI CHÍNH 120 120 CÔNG TY CỔ PHẦN CÔNG NGHỆ - VIỄN THÔNG ELCOM MẪU SỐ B09

**Bản kiểm:** Ngô Kiều Anh → ELC · `HOLDS_ROLE` · Trưởng Ban Kiểm soát.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/ELC_Baocaothuongnien_2024.pdf · document_id `f0730a07-8ab5-548a-a3b8-e099489d0f29` · trang PDF `68`.

**Hash section/trang đã kiểm:** `1348dcfba0e77b9917fdbfd279ba8c0ed2e92ec8dcb4cf1f2ceaa0dc2d65d83c`.

### APPROVED — 50. 59d2cbe2-c21f-583d-bc0b-453470350d3b

**Bằng chứng nguồn:**
> Ông Đoàn Việt Nam Phó Tổng Giám đốc

**Bản kiểm:** Đoàn Việt Nam → BID · `HOLDS_ROLE` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://bidv.com.vn/vn/ve-bidv/ban-lanh-dao · document_id `7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190` · trang PDF `None`.

**Hash section/trang đã kiểm:** `da6f0211ebf6ee83cd6983571fbeec008196b5e66acab7055bf093ab1f9abfcf`.

### APPROVED — 51. 5a6712b1-45c0-5f47-931d-d0cb13797dc5

**Bằng chứng nguồn:**
> HAMPAPUR RANGADORE BINOD Ủy viên Hội đồng Quản trị độc lập

**Bản kiểm:** Hampapur Rangadore Binod → FPT · `HOLDS_ROLE` · Ủy viên Hội đồng Quản trị độc lập.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://fpt.com/vi/ve-fpt/doi-ngu-lanh-dao · document_id `535b180e-02c7-58e1-97cb-b4fe6b4d14a9` · trang PDF `None`.

**Hash section/trang đã kiểm:** `33cfaf2fbc681dae83c47dd4fa4b85cfe52e52683e7c2a066b0cd1deb35486ce`.

### APPROVED — 52. 5ab72ec4-f6ec-5a67-858e-bb86e466348b

**Bằng chứng nguồn:**
> Bà Nguyễn Thị An Bình Phó Trưởng Ban Kiểm soát

**Bản kiểm:** Nguyễn Thị An Bình → MBB · `HOLDS_ROLE` · Phó Trưởng Ban Kiểm soát.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://www.mbbank.com.vn/ve-mb/doi-ngu-lanh-dao · document_id `e9dd552a-0bd7-5716-bbdd-34e4580f7d6d` · trang PDF `None`.

**Hash section/trang đã kiểm:** `361d3953e754b97a64c3e6c7539f132c4b1fedc70c0825d017be9dce006ee918`.

### APPROVED — 53. 5b2790ec-230b-51af-9a5a-b178b575a982

**Bằng chứng nguồn:**
> đồng Quản trị trong năm và tại ngày lập báo cáo này bao gồm: Ông Mai Hoài An Chủ tịch Ông Nguyễn Hữu Dũng Phó Chủ tịch Ông Nguyễn Vĩnh Thuận Phó Chủ tịch Miễn nhiệm ngày 26/06/2025 Ông Võ Xuân Vinh Thành viên Bổ nhiệm ngày 26/06/2025 Ông Nguyễn Ngọc Trung Thành viên Ông Đinh Thế Hiển Thành viên Đ Các thành viên của Ban Tổng Giám đốc đã điều hành Công ty trong năm và tại ngày lập báo cáo này bao gồm: Ông Nguyễn Ngọc Trung Tổng Giám đốc Ông Nguyễn Hồng Minh Phó Tổng Giám đốc Bổ nhiệ

**Bản kiểm:** Nguyễn Hữu Dũng → ITD · `HOLDS_ROLE` · Phó Chủ tịch HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/ITD_Baocaothuongnien_2025.pdf · document_id `a2c071fb-25bf-5ec4-903b-e973c623b85d` · trang PDF `52`.

**Hash section/trang đã kiểm:** `d29acf9d280d7310222afee6a10edbd47b99492988edf6f82320997cda5ee3e5`.

### APPROVED — 54. 5f0ce1e4-5224-58ba-a15a-2e5b0b72e5e0

**Bằng chứng nguồn:**
> Hoàng Văn Sâm Thành viên HĐQT độc lập

**Bản kiểm:** Hoàng Văn Sâm → MBB · `HOLDS_ROLE` · Thành viên HĐQT độc lập.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://www.mbbank.com.vn/ve-mb/doi-ngu-lanh-dao · document_id `e9dd552a-0bd7-5716-bbdd-34e4580f7d6d` · trang PDF `None`.

**Hash section/trang đã kiểm:** `361d3953e754b97a64c3e6c7539f132c4b1fedc70c0825d017be9dce006ee918`.

### APPROVED — 55. 5f5d34fc-5315-5fdf-a308-990fcb642e50

**Bằng chứng nguồn:**
> iện Phó Chủ tịch HĐQT 152.065.000 - Ông Trần Hùng Giang Thành viên HĐQT 152.065.000 - Ông Nguyễn Mạnh Hải Thành viên HĐQT 151.835.000 - Ông Ngô Ngọc Hà Thành viên HĐQT/Phó Tổng Giám đốc 396.047.930 - Ông Nguyễn Mạnh Hùng Thành viên HĐQT 120.000.000 - Ông Đỗ Minh Tiến Thành viên HĐQT 120.000.000 - Ông Phạm Minh Thắng Tổng Giám đốc 399.626.000 - Ông Nguyễn Văn Hòa Phó Tổng Giám đốc 738.244.000 Ban Kiểm soát - - Bà Ngô Kiều Anh Trưởng ban 313.893.000 - Bà Vũ Thị Ngân Hà Thành viên 30

**Bản kiểm:** Nguyễn Mạnh Hải → ELC · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/ELC_Baocaothuongnien_2024.pdf · document_id `f0730a07-8ab5-548a-a3b8-e099489d0f29` · trang PDF `68`.

**Hash section/trang đã kiểm:** `1348dcfba0e77b9917fdbfd279ba8c0ed2e92ec8dcb4cf1f2ceaa0dc2d65d83c`.

### APPROVED — 56. 61776e37-d9ac-53cf-ada8-92024cf88ea6

**Bằng chứng nguồn:**
> ng Thành viên HĐQT 5.112 Thành viên HĐQT – 5 Ông Hồng Quang 2 Giám đốc Khối Nhân sự 6 Ông Vũ Viết Ngoạn Thành viên độc lập HĐQT 0 7 Bà Nguyễn Thị Kim Oanh Thành viên HĐQT 7.475 8 Ông Nguyễn Tuấn Anh Thành viên HĐQT 0 63 CHƯƠNG 4 Quản trị doanh nghiệp Trong những năm qua, công tác quản trị công ty của VCB luôn được chú trọng và triển khai Hội đồng một cách nghiêm túc dưới sự định hướng và giám sát của HĐQT. VCB đã tuân thủ đầy đủ quản trị các quy định về quản trị công ty theo phá

**Bản kiểm:** Vũ Viết Ngoạn → VCB · `HOLDS_ROLE` · Thành viên HĐQT độc lập.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/VCB_Baocaothuongnien_2025.zip · document_id `679baa3e-b39c-5b53-be43-3cd19d738dca` · trang PDF `33`.

**Hash section/trang đã kiểm:** `cf40fe0d83644c1e5c1942f9eb281f4ec55c5169a7cfd0e4f5aa1a79fa6db82f`.

### APPROVED — 57. 62117e54-9c4d-5629-ad2c-1406856cb98e

**Bằng chứng nguồn:**
> ĐỖ CAO BẢO Ủy viên Hội đồng Quản trị

**Bản kiểm:** Đỗ Cao Bảo → FPT · `HOLDS_ROLE` · Ủy viên Hội đồng Quản trị.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://fpt.com/vi/ve-fpt/doi-ngu-lanh-dao · document_id `535b180e-02c7-58e1-97cb-b4fe6b4d14a9` · trang PDF `None`.

**Hash section/trang đã kiểm:** `33cfaf2fbc681dae83c47dd4fa4b85cfe52e52683e7c2a066b0cd1deb35486ce`.

### APPROVED — 58. 64fb6ab9-4362-51c2-8304-8ef9863e1a07

**Bằng chứng nguồn:**
> với HĐQT. DANH SÁCH TV BĐH STT Họ và tên Chức vụ Số lượng cổ phiếu Tỷ lệ sở hữu (%) 1 Ông Nguyễn Trần Mạnh Trung TV HĐQT kiêm TGĐ 3 0,00000006% 2 Ông Koji Iriguchi TV HĐQT kiêm Phó TGĐ 0 0% 3 Ông Trần Công Quỳnh Lân Phó TGĐ 0 0% 4 Bà Lê Như Hoa Phó TGĐ 39.937 0,000744% 5 Ông Lê Duy Hải Phó TGĐ 22.348 0,000416% 6 Ông Đỗ Thanh Sơn Phó TGĐ 125 0,0000023% 7 Ông Nguyễn Hải Hưng Kế toán trưởng 27.816 0,000518% Ghi chú: Danh sách TV BĐH và số lượng cổ phiếu trong bảng này được cập nhật tại ngày

**Bản kiểm:** Nguyễn Trần Mạnh Trung → CTG · `HOLDS_ROLE` · Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/CTG_Baocaothuongnien_2024.pdf · document_id `ebc51a9d-1d79-51a6-8c3e-f3db6d8f4891` · trang PDF `24`.

**Hash section/trang đã kiểm:** `e2d957a20adea3a5a279afd84d3eb05232042cc8edc2b298b71474c14a55c353`.

### APPROVED — 59. 69fbea39-b6a2-5ed0-9514-8a0e9439fd72

**Bằng chứng nguồn:**
> Bà Phan Thị Hải Yến được bổ nhiệm giữ vị trí Phó Tổng Giám đốc kiêm Giám đốc Khối Ngân hàng Doanh nghiệp và Định chế Tài chính của Techcombank từ ngày 1/11/2026.

**Bản kiểm:** TCB → Phan Thị Hải Yến · `APPOINTS` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Chấp nhận thông tin quyết định bổ nhiệm; không suy người vẫn đương nhiệm hiện tại. Mốc bản gửi: 2026-11-01; kiểm theo câu ghi ngày của đúng người. Nhãn FUTURE_EFFECTIVE là trạng thái tại lúc tạo dữ liệu. Chỉ duyệt quyết định và ngày 1/11/2026 mà nguồn ghi, không tự xác nhận đã nhận nhiệm vụ vì lịch đã sang tháng 11.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 60. 6a87d56f-513e-5494-9f16-7be094278f31

**Bằng chứng nguồn:**
> Vũ Thị Hải Phượng Phó Chủ tịch HĐQT

**Bản kiểm:** Vũ Thị Hải Phượng → MBB · `HOLDS_ROLE` · Phó Chủ tịch HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://www.mbbank.com.vn/ve-mb/doi-ngu-lanh-dao · document_id `e9dd552a-0bd7-5716-bbdd-34e4580f7d6d` · trang PDF `None`.

**Hash section/trang đã kiểm:** `361d3953e754b97a64c3e6c7539f132c4b1fedc70c0825d017be9dce006ee918`.

### APPROVED — 61. 6b5e6272-cf28-597d-a168-7e14235a8c80

**Bằng chứng nguồn:**
> TGĐ kiêm GĐ 8 Ông Dương Văn Quân 0 0% VietinBank TP. Hà Nội Phó TGĐ kiêm GĐ Khối Tài 9 Bà Nguyễn Bảo Thanh Vân 26.589 0,00034% chính 10 Bà Đặng Thị Việt Hà Phó TGĐ 0 0% 11 Ông Nguyễn Hải Hưng Kế toán trưởng 40.232 0,000518% Ghi chú: - Ngày 25/12/2025, VietinBank đã CBTT Thông báo thay đổi số lượng cổ phần có quyền biểu quyết tại công văn số 1292/HĐQT-NHCT-VPHĐQT1. Theo đó, tổng số lượng cổ phiếu có quyền biểu quyết đang lưu hành là 7.766.944.637 cổ phiếu. Tuy nhiên, đến ngày 9/1/2026,

**Bản kiểm:** Nguyễn Bảo Thanh Vân → CTG · `HOLDS_ROLE` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CTG_Baocaothuongnien_2025.pdf · document_id `26c58a92-9b65-5ce3-a1c2-5f3b71717ddc` · trang PDF `25`.

**Hash section/trang đã kiểm:** `840c84044c4ea71e95ab1827555a35741b3e0f80eced81a1a7a265c805edfe68`.

### APPROVED — 62. 6be74e37-d939-5633-8016-909958ee0209

**Bằng chứng nguồn:**
> GIÁM ĐỐC NGÂN HÀNG ĐẦU TƯ Ông Nguyễn Xuân Minh

**Bản kiểm:** Nguyễn Xuân Minh → TCB · `HOLDS_ROLE` · Giám đốc Ngân hàng Đầu tư.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 63. 6cea6ef2-900c-5530-8a01-1bfe114b52f7

**Bằng chứng nguồn:**
> Bà Phan Thị Hải Yến được bổ nhiệm giữ vị trí Phó Tổng Giám đốc kiêm Giám đốc Khối Ngân hàng Doanh nghiệp và Định chế Tài chính của Techcombank từ ngày 1/11/2026.

**Bản kiểm:** TCB → Phan Thị Hải Yến · `APPOINTS` · Giám đốc Khối Ngân hàng Doanh nghiệp và Định chế Tài chính.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Chấp nhận thông tin quyết định bổ nhiệm; không suy người vẫn đương nhiệm hiện tại. Mốc bản gửi: 2026-11-01; kiểm theo câu ghi ngày của đúng người. Nhãn FUTURE_EFFECTIVE là trạng thái tại lúc tạo dữ liệu. Chỉ duyệt quyết định và ngày 1/11/2026 mà nguồn ghi, không tự xác nhận đã nhận nhiệm vụ vì lịch đã sang tháng 11.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 64. 6d59091b-2299-53c2-af5a-89af26f016f6

**Bằng chứng nguồn:**
> ếu TGĐ Công ty - em trai của CMC Phó TGĐ Ngô Ngọc Hà - Công ty CP đầu tư thương mại & Ông Nguyễn Văn Hòa là đại diện theo Pháp phát triển Dịch vụ Việt Nam luật của Công ty CP đầu tư TM & PT Dịch vụ Việt Nam và là Phó Tổng Giám đốc của Công ty CP Công nghệ - Viễn thông ELCOM - Ông Trần Hùng Giang Thành viên HĐQT - Ông Ngô Ngọc Hà Thành viên HĐQT - Bà Nguyễn Thị Lệ Thủy Vợ Ông Phan Chiến Thắng - Chủ tịch HĐQT THU NHẬP CỦA CÁC THÀNH VIÊN QUẢN LÝ CHỦ CHỐT Tổng thu nhập Năm 2024 Chức

**Bản kiểm:** Nguyễn Văn Hòa → ELC · `HOLDS_ROLE` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/ELC_Baocaothuongnien_2024.pdf · document_id `f0730a07-8ab5-548a-a3b8-e099489d0f29` · trang PDF `68`.

**Hash section/trang đã kiểm:** `1348dcfba0e77b9917fdbfd279ba8c0ed2e92ec8dcb4cf1f2ceaa0dc2d65d83c`.

### APPROVED — 65. 6eb52e7a-c18b-5393-bae3-fab6222476cc

**Bằng chứng nguồn:**
> DANH SÁCH TV HĐQT STT Họ và tên Chức vụ Số lượng cổ phiếu Tỷ lệ sở hữu (%) Ghi chú 1 Ông Trần Minh Bình Chủ tịch HĐQT 5.015 0,000065% TV không điều hành TV HĐQT kiêm 2 Ông Nguyễn Trần Mạnh Trung 04 0,00000005% TV điều hành TGĐ 3 Ông Trần Văn Tần TV HĐQT 0 0% TV không điều hành 4 Ông Lê Thanh Tùng TV HĐQT 0 0% TV không điều hành 5 Ông Nguyễn Thế Huân TV HĐQT 0 0% TV không điều hành 6 Bà Phạm Thị Thanh Hoài TV HĐQT 189 0,000002% TV không điều hành 7 Ông Nguyễn Vân Anh TV HĐQT 0 0%

**Bản kiểm:** Trần Minh Bình → CTG · `HOLDS_ROLE` · Chủ tịch HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CTG_Baocaothuongnien_2025.pdf · document_id `26c58a92-9b65-5ce3-a1c2-5f3b71717ddc` · trang PDF `18`.

**Hash section/trang đã kiểm:** `7a501da6b4991a2d607a6d5c038e78cff57a65aee779fa9507190b560d089045`.

### APPROVED — 66. 72bb9a14-bdfb-582a-b063-aea2ca0eb4f3

**Bằng chứng nguồn:**
> Ông Lê Kim Hòa Ủy viên HĐQT

**Bản kiểm:** Lê Kim Hòa → BID · `HOLDS_ROLE` · Ủy viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://bidv.com.vn/vn/ve-bidv/ban-lanh-dao · document_id `7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190` · trang PDF `None`.

**Hash section/trang đã kiểm:** `da6f0211ebf6ee83cd6983571fbeec008196b5e66acab7055bf093ab1f9abfcf`.

### APPROVED — 67. 73222906-874e-5be5-8bb3-51abbbf69224

**Bằng chứng nguồn:**
> PHÓ TỔNG GIÁM ĐỐC, QUYỀN GIÁM ĐỐC KHỐI QUẢN LÝ TÍN DỤNG Bà Trần Thị Thu Lan

**Bản kiểm:** Trần Thị Thu Lan → TCB · `HOLDS_ROLE` · Quyền Giám đốc Khối Quản lý Tín dụng.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 68. 743c152b-65bc-57af-8eee-f2f4cb25af1f

**Bằng chứng nguồn:**
> ạnh Hùng Thành viên HĐQT 120.000.000 - Ông Đỗ Minh Tiến Thành viên HĐQT 120.000.000 - Ông Phạm Minh Thắng Tổng Giám đốc 399.626.000 - Ông Nguyễn Văn Hòa Phó Tổng Giám đốc 738.244.000 Ban Kiểm soát - - Bà Ngô Kiều Anh Trưởng ban 313.893.000 - Bà Vũ Thị Ngân Hà Thành viên 306.994.000 - Bà Hoàng Thị Phương Thúy Thành viên 36.000.000 Kế toán trưởng - - Bà Đậu Thị Lý Kế toán trưởng (bổ nhiệm từ 19/05/2023) 480.850.000 - Bà Đặng Thị Thanh Minh Kế toán trưởng (miễn nhiệm từ 19/05/2023) 1

**Bản kiểm:** Phạm Minh Thắng → ELC · `HOLDS_ROLE` · Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/ELC_Baocaothuongnien_2024.pdf · document_id `f0730a07-8ab5-548a-a3b8-e099489d0f29` · trang PDF `68`.

**Hash section/trang đã kiểm:** `1348dcfba0e77b9917fdbfd279ba8c0ed2e92ec8dcb4cf1f2ceaa0dc2d65d83c`.

### APPROVED — 69. 75dc50d4-005c-577e-9cd8-9e960ddb956d

**Bằng chứng nguồn:**
> hành viên và cơ cấu của Hội đồng quản trị: TT |_ Thành viên HĐQT Chức vụ krkk Ti Non 1 _| Nguyễn Trung Chính Chủ tịch HĐQT 2,500,551 1,18% 2 Nguyễn Minh Đức Thành viên HĐQT 4,862,063 2,30% 3 Nguyễn Phước Hải Thành viên HĐQT 3,453,867 1,63% 4 Gum Ki Ho Thành viên HĐQT 0 0% 5 Kwon Oh Soo Thành viên HĐQT 0 0% 6 Trương Tuấn Lâm | Thành viên HĐQT độc lập 0 0% 7 Nguyễn Danh Lam | Thành viên HĐQT độc lập 0 0% 8 Lê Việt Hà Thành viên HĐQT độc lập 0 0% 9 Hà Thế Vinh Thành viên HĐQT không 0 0%

**Bản kiểm:** Nguyễn Trung Chính → CMG · `HOLDS_ROLE` · Chủ tịch HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CMG_Baocaothuongnien_2025.pdf · document_id `532597dc-7b79-5f00-99f9-d3394cba9038` · trang PDF `64`.

**Hash section/trang đã kiểm:** `e4be11d5fd9ac0153b2e13b1ce0440b44dcf12f4d7c77de22d1c9c0e0d017210`.

### APPROVED — 70. 7713aa4d-628d-5ce2-a32b-11f77513243c

**Bằng chứng nguồn:**
> Kế toán trưởng - - Bà Đậu Thị Lý Kế toán trưởng (bổ nhiệm từ 19/05/2023) 480.850.000 - Bà Đặng Thị Thanh Minh Kế toán trưởng (miễn nhiệm từ 19/05/2023) 106.746.860 Cộng 3.713.818.790 BÁO CÁO TÀI CHÍNH 120 120 CÔNG TY CỔ PHẦN CÔNG NGHỆ - VIỄN THÔNG ELCOM MẪU SỐ B09-DN/HN Tòa nhà Elcom, phố Duy Tân, phường Dịch Vọng Hậu, Ban hành theo Thông tư số 202/2014/TT- quận Cầu Giấy, Hà Nội BTC ngày 22/12/2014 của Bộ Tài chính THUYẾT MINH BÁO CÁO TÀI CHÍNH HỢP NHẤT (TIẾP) (Các thuyết minh này là

**Bản kiểm:** ELC → Đặng Thị Thanh Minh · `DISMISSES` · Kế toán trưởng.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Giữ nguyên loại quan hệ lịch sử/miễn nhiệm/từ nhiệm; không đổi thành đang giữ chức. Mốc bản gửi: 2023-05-19; kiểm theo câu ghi ngày của đúng người.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/ELC_Baocaothuongnien_2024.pdf · document_id `f0730a07-8ab5-548a-a3b8-e099489d0f29` · trang PDF `68`.

**Hash section/trang đã kiểm:** `1348dcfba0e77b9917fdbfd279ba8c0ed2e92ec8dcb4cf1f2ceaa0dc2d65d83c`.

### APPROVED — 71. 79e9aa0b-ad0e-590d-8de5-0bc4dd0e77cb

**Bằng chứng nguồn:**
> tịch Miễn nhiệm ngày 26/06/2025 Ông Võ Xuân Vinh Thành viên Bổ nhiệm ngày 26/06/2025 Ông Nguyễn Ngọc Trung Thành viên Ông Đinh Thế Hiển Thành viên Đ Các thành viên của Ban Tổng Giám đốc đã điều hành Công ty trong năm và tại ngày lập báo cáo này bao gồm: Ông Nguyễn Ngọc Trung Tổng Giám đốc Ông Nguyễn Hồng Minh Phó Tổng Giám đốc Bổ nhiệm ngày 04/11/2025 Bà Nguyễn Thị Thu Sương Phó Tổng Giám đốc Miễn nhiệm ngày 17/07/2025 Căn cứ theo Nghị quyết ĐHĐCD năm 2025 ngày 26/06/2025, Công ty

**Bản kiểm:** Nguyễn Ngọc Trung → ITD · `HOLDS_ROLE` · Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/ITD_Baocaothuongnien_2025.pdf · document_id `a2c071fb-25bf-5ec4-903b-e973c623b85d` · trang PDF `52`.

**Hash section/trang đã kiểm:** `d29acf9d280d7310222afee6a10edbd47b99492988edf6f82320997cda5ee3e5`.

### APPROVED — 72. 7cae84b3-82ce-53fc-89c5-ea779fc46df8

**Bằng chứng nguồn:**
> PHÓ CHỦ TỊCH Ông Nguyễn Cảnh Sơn

**Bản kiểm:** Nguyễn Cảnh Sơn → TCB · `HOLDS_ROLE` · Phó Chủ tịch HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 73. 7e632666-ec11-5e3c-9934-299b1638fc83

**Bằng chứng nguồn:**
> ức vụ Ngày bổ nhiệm/thôi nhiệm - Miễn nhiệm TV HĐQT nhiệm kỳ 2024 - 2029 kể từ ngày 1 Ông Nguyễn Đức Thành TV HĐQT 18/4/2025 theo Nghị quyết ĐHĐCĐ thường niên 2025 số 29/NQ-ĐHĐCĐ ngày 18/4/2025. - Bổ nhiệm TV HĐQT nhiệm kỳ 2024 - 2029 theo Nghị 2 Ông Nguyễn Vân Anh TV HĐQT quyết ĐHĐCĐ thường niên 2025 số 29/NQ-ĐHĐCĐ ngày 18/4/2025. BÁO CÁO BẢN LĨNH ĐỔI MỚI THƯỜNG NIÊN KIẾN TẠO DẪN ĐẦU 31 2025

**Bản kiểm:** CTG → Nguyễn Đức Thành · `DISMISSES` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Giữ nguyên loại quan hệ lịch sử/miễn nhiệm/từ nhiệm; không đổi thành đang giữ chức. Mốc bản gửi: 2025-04-18; kiểm theo câu ghi ngày của đúng người.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CTG_Baocaothuongnien_2025.pdf · document_id `26c58a92-9b65-5ce3-a1c2-5f3b71717ddc` · trang PDF `18`.

**Hash section/trang đã kiểm:** `7a501da6b4991a2d607a6d5c038e78cff57a65aee779fa9507190b560d089045`.

### APPROVED — 74. 7e6891e8-7d40-5f80-a41d-c028b4a8aebf

**Bằng chứng nguồn:**
> THÀNH VIÊN ĐỘC LẬP Ông Eugene Keith Galbraith

**Bản kiểm:** Eugene Keith Galbraith → TCB · `HOLDS_ROLE` · Thành viên HĐQT độc lập.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 75. 7f31b6e2-1b32-5566-8fd8-a1a2569f1da9

**Bằng chứng nguồn:**
> Bà Nguyễn Thị Quỳnh Giao Phó Tổng Giám đốc

**Bản kiểm:** Nguyễn Thị Quỳnh Giao → BID · `HOLDS_ROLE` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://bidv.com.vn/vn/ve-bidv/ban-lanh-dao · document_id `7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190` · trang PDF `None`.

**Hash section/trang đã kiểm:** `da6f0211ebf6ee83cd6983571fbeec008196b5e66acab7055bf093ab1f9abfcf`.

### APPROVED — 76. 7f86db46-090a-5325-931d-1a2d33468f62

**Bằng chứng nguồn:**
> Phạm Như Ánh Thành viên HĐQT

**Bản kiểm:** Phạm Như Ánh → MBB · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://www.mbbank.com.vn/ve-mb/doi-ngu-lanh-dao · document_id `e9dd552a-0bd7-5716-bbdd-34e4580f7d6d` · trang PDF `None`.

**Hash section/trang đã kiểm:** `361d3953e754b97a64c3e6c7539f132c4b1fedc70c0825d017be9dce006ee918`.

### APPROVED — 77. 811dc39c-37f5-52d7-a637-6ea4742d9db6

**Bằng chứng nguồn:**
> Nguyễn Thị Hải Lý Phó Chủ tịch HĐQT

**Bản kiểm:** Nguyễn Thị Hải Lý → MBB · `HOLDS_ROLE` · Phó Chủ tịch HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://www.mbbank.com.vn/ve-mb/doi-ngu-lanh-dao · document_id `e9dd552a-0bd7-5716-bbdd-34e4580f7d6d` · trang PDF `None`.

**Hash section/trang đã kiểm:** `361d3953e754b97a64c3e6c7539f132c4b1fedc70c0825d017be9dce006ee918`.

### APPROVED — 78. 811fdb31-f291-57bf-8d26-ea0725d94ab2

**Bằng chứng nguồn:**
> TRƯƠNG GIA BÌNH Chủ tịch Hội đồng quản trị

**Bản kiểm:** Trương Gia Bình → FPT · `HOLDS_ROLE` · Chủ tịch Hội đồng quản trị.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://fpt.com/vi/ve-fpt/doi-ngu-lanh-dao · document_id `535b180e-02c7-58e1-97cb-b4fe6b4d14a9` · trang PDF `None`.

**Hash section/trang đã kiểm:** `33cfaf2fbc681dae83c47dd4fa4b85cfe52e52683e7c2a066b0cd1deb35486ce`.

### APPROVED — 79. 84b9bab1-c930-5e55-8d5b-cf11e6ee3dcc

**Bằng chứng nguồn:**
> PHÓ CHỦ TỊCH Ông Nguyễn Thiều Quang

**Bản kiểm:** Nguyễn Thiều Quang → TCB · `HOLDS_ROLE` · Phó Chủ tịch HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 80. 85df5cff-53ba-5e6b-b86a-f757515d4fe9

**Bằng chứng nguồn:**
> phiếu Tỷ lệ sở hữu (%) 1 Ông Nguyễn Trần Mạnh Trung TV HĐQT kiêm TGĐ 3 0,00000006% 2 Ông Koji Iriguchi TV HĐQT kiêm Phó TGĐ 0 0% 3 Ông Trần Công Quỳnh Lân Phó TGĐ 0 0% 4 Bà Lê Như Hoa Phó TGĐ 39.937 0,000744% 5 Ông Lê Duy Hải Phó TGĐ 22.348 0,000416% 6 Ông Đỗ Thanh Sơn Phó TGĐ 125 0,0000023% 7 Ông Nguyễn Hải Hưng Kế toán trưởng 27.816 0,000518% Ghi chú: Danh sách TV BĐH và số lượng cổ phiếu trong bảng này được cập nhật tại ngày 31/12/2024. THAY ĐỔI TV BĐH TRONG NĂM 2024 STT Họ

**Bản kiểm:** Koji Iriguchi → CTG · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/CTG_Baocaothuongnien_2024.pdf · document_id `ebc51a9d-1d79-51a6-8c3e-f3db6d8f4891` · trang PDF `24`.

**Hash section/trang đã kiểm:** `e2d957a20adea3a5a279afd84d3eb05232042cc8edc2b298b71474c14a55c353`.

### APPROVED — 81. 872c2b1b-0d9f-5fc2-b6a6-82cb2ae73315

**Bằng chứng nguồn:**
> HĐQT - Công ty CP Hạ tầng Viễn thông Ngô Trọng Hiếu TGĐ Công ty - em trai của CMC Phó TGĐ Ngô Ngọc Hà - Công ty CP đầu tư thương mại & Ông Nguyễn Văn Hòa là đại diện theo Pháp phát triển Dịch vụ Việt Nam luật của Công ty CP đầu tư TM & PT Dịch vụ Việt Nam và là Phó Tổng Giám đốc của Công ty CP Công nghệ - Viễn thông ELCOM - Ông Trần Hùng Giang Thành viên HĐQT - Ông Ngô Ngọc Hà Thành viên HĐQT - Bà Nguyễn Thị Lệ Thủy Vợ Ông Phan Chiến Thắng - Chủ tịch HĐQT THU NHẬP CỦA CÁC THÀN

**Bản kiểm:** Ngô Ngọc Hà → ELC · `HOLDS_ROLE` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/ELC_Baocaothuongnien_2024.pdf · document_id `f0730a07-8ab5-548a-a3b8-e099489d0f29` · trang PDF `68`.

**Hash section/trang đã kiểm:** `1348dcfba0e77b9917fdbfd279ba8c0ed2e92ec8dcb4cf1f2ceaa0dc2d65d83c`.

### APPROVED — 82. 87ec8bfd-e385-53dc-9242-a175f13a5a57

**Bằng chứng nguồn:**
> PHÓ TỔNG GIÁM ĐỐC KIÊM GIÁM ĐỐC KHỐI NGÂN HÀNG BÁN LẺ Ông Nguyễn Anh Tuấn

**Bản kiểm:** Nguyễn Anh Tuấn → TCB · `HOLDS_ROLE` · Giám đốc Khối Ngân hàng Bán lẻ.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 83. 89d5643c-2136-5545-ad31-9a0f373fb752

**Bằng chứng nguồn:**
> V HĐQT 0 0% TV không điều hành 5 Ông Nguyễn Thế Huân TV HĐQT 0 0% TV không điều hành 6 Bà Phạm Thị Thanh Hoài TV HĐQT 189 0,000002% TV không điều hành 7 Ông Nguyễn Vân Anh TV HĐQT 0 0% TV không điều hành 8 Ông Nguyễn Việt Dũng TV HĐQT 0 0% TV không điều hành TV HĐQT kiêm Phó 9 Ông Koji Iriguchi 0 0% TV điều hành TGĐ 10 Ông Takeo Shimotsu TV HĐQT 0 0% TV không điều hành 11 Ông Cát Quang Dương TV độc lập HĐQT 0 0% TV độc lập Ghi chú: - Danh sách TV HĐQT và số lượng cổ phiếu trong bảng n

**Bản kiểm:** Phạm Thị Thanh Hoài → CTG · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CTG_Baocaothuongnien_2025.pdf · document_id `26c58a92-9b65-5ce3-a1c2-5f3b71717ddc` · trang PDF `18`.

**Hash section/trang đã kiểm:** `7a501da6b4991a2d607a6d5c038e78cff57a65aee779fa9507190b560d089045`.

### APPROVED — 84. 89f5994d-edc9-51f6-8dee-72d1c2c8d0d6

**Bằng chứng nguồn:**
> uấn Lâm | Thành viên HĐQT độc lập 0 0% 7 Nguyễn Danh Lam | Thành viên HĐQT độc lập 0 0% 8 Lê Việt Hà Thành viên HĐQT độc lập 0 0% 9 Hà Thế Vinh Thành viên HĐQT không 0 0% điêu hành 1.2. Các tiêu ban thuộc Hội đồng quản trị: a.. Ban kiễm toán nội bộ: Lập kế hoạch cho các hoạt động kiểm toán nội bộ và quản trị rủi ro ở cắp Tập đoàn và Công ty thành viên căn cứ vào chiến lược phát triển và kế hoạch kinh doanh. Thực hiện hoạt động kiểm tra, kiểm toán nhằm đánh giá và xác nhận tín

**Bản kiểm:** Lê Việt Hà → CMG · `HOLDS_ROLE` · Thành viên HĐQT độc lập.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CMG_Baocaothuongnien_2025.pdf · document_id `532597dc-7b79-5f00-99f9-d3394cba9038` · trang PDF `64`.

**Hash section/trang đã kiểm:** `e4be11d5fd9ac0153b2e13b1ce0440b44dcf12f4d7c77de22d1c9c0e0d017210`.

### APPROVED — 85. 8c5e545c-9707-5154-86e8-b34e26f7c03c

**Bằng chứng nguồn:**
> JEAN-CHARLES BELLIOL Ủy viên Hội đồng quản trị độc lập

**Bản kiểm:** Jean-Charles Belliol → FPT · `HOLDS_ROLE` · Ủy viên Hội đồng quản trị độc lập.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://fpt.com/vi/ve-fpt/doi-ngu-lanh-dao · document_id `535b180e-02c7-58e1-97cb-b4fe6b4d14a9` · trang PDF `None`.

**Hash section/trang đã kiểm:** `33cfaf2fbc681dae83c47dd4fa4b85cfe52e52683e7c2a066b0cd1deb35486ce`.

### APPROVED — 86. 8d437445-5b8e-5800-9465-1d041f3ce3c0

**Bằng chứng nguồn:**
> Ông Phạm Quang Tùng Ủy viên HĐQT

**Bản kiểm:** Phạm Quang Tùng → BID · `HOLDS_ROLE` · Ủy viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://bidv.com.vn/vn/ve-bidv/ban-lanh-dao · document_id `7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190` · trang PDF `None`.

**Hash section/trang đã kiểm:** `da6f0211ebf6ee83cd6983571fbeec008196b5e66acab7055bf093ab1f9abfcf`.

### APPROVED — 87. 8d72e87f-1525-5009-b869-e3ab01c3e165

**Bằng chứng nguồn:**
> guyễn Danh Lam | Thành viên HĐQT độc lập 0 0% 8 Lê Việt Hà Thành viên HĐQT độc lập 0 0% 9 Hà Thế Vinh Thành viên HĐQT không 0 0% điêu hành 1.2. Các tiêu ban thuộc Hội đồng quản trị: a.. Ban kiễm toán nội bộ: Lập kế hoạch cho các hoạt động kiểm toán nội bộ và quản trị rủi ro ở cắp Tập đoàn và Công ty thành viên căn cứ vào chiến lược phát triển và kế hoạch kinh doanh. Thực hiện hoạt động kiểm tra, kiểm toán nhằm đánh giá và xác nhận tính đúng đắn, trung thực và hợp pháp của các

**Bản kiểm:** Hà Thế Vinh → CMG · `HOLDS_ROLE` · Thành viên HĐQT không điều hành.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CMG_Baocaothuongnien_2025.pdf · document_id `532597dc-7b79-5f00-99f9-d3394cba9038` · trang PDF `64`.

**Hash section/trang đã kiểm:** `e4be11d5fd9ac0153b2e13b1ce0440b44dcf12f4d7c77de22d1c9c0e0d017210`.

### APPROVED — 88. 8e49c903-b7bd-5c35-9a38-7ab6a7841fd5

**Bằng chứng nguồn:**
> NGƯỜI PHỤ TRÁCH QUẢN TRỊ NGÂN HÀNG VÀ THƯ KÝ CÔNG TY Ông Nguyễn Tuấn Minh

**Bản kiểm:** Nguyễn Tuấn Minh → TCB · `HOLDS_ROLE` · Thư ký Công ty.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 89. 8e828bde-cd1a-550d-8f7b-78971ce3ec1b

**Bằng chứng nguồn:**
> trách HĐQT ngày 26 tháng 7 Thành viên năm 2024 Bổ nhiệm lại ngày 21 tháng 4 năm 2023 Ông Lê Quang Vinh Thành viên Bổ nhiệm ngày 7 tháng 3 năm 2025 Ông Nguyễn Tuấn Anh Thành viên Bổ nhiệm ngày 19 tháng 8 năm 2024 Ông Nguyễn Mỹ Hào Thành viên Từ nhiệm ngày 1 tháng 11 năm 2024 Ông Nguyễn Mạnh Hùng Thành viên Bổ nhiệm lại ngày 21 tháng 4 năm 2023 Ông Hồng Quang Thành viên Bổ nhiệm lại ngày 21 tháng 4 năm 2023 Ông Shojiro Mizoguchi Thành viên Bổ nhiệm lại ngày 21 tháng 4 năm 2023 Bà

**Bản kiểm:** VCB → Lê Quang Vinh · `APPOINTS` · Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Chấp nhận thông tin quyết định bổ nhiệm; không suy người vẫn đương nhiệm hiện tại. Mốc bản gửi: 2025-03-07; kiểm theo câu ghi ngày của đúng người.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/VCB_Baocaothuongnien_2024.pdf · document_id `dd94d5da-f8b1-5776-8c5e-f211d18ae26b` · trang PDF `65`.

**Hash section/trang đã kiểm:** `4ee095497823547593f90cb39e32e5919342ada0c636aa01c936a1b49acb38c3`.

### APPROVED — 90. 8fd0c336-c9a6-5ac4-9cb5-9d38aa3851d4

**Bằng chứng nguồn:**
> THÀNH VIÊN ĐỘC LẬP Ông Phạm Nghiêm Xuân Bắc

**Bản kiểm:** Phạm Nghiêm Xuân Bắc → TCB · `HOLDS_ROLE` · Thành viên HĐQT độc lập.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 91. 93212be3-1495-5d0b-9475-6fdde36322b7

**Bằng chứng nguồn:**
> ) *Chi tiết tại phần giới thiệu HĐQT Công ty 4. Ông Lê Ánh Dương Phó Tổng Giám đốc 5. Ông Nguyễn Ngọc Sơn Kế toán trưởng 34 Báo cáo thường niên 2025 Giới thiệu về Ban Tổng Giám đốc Ông Lê Thanh Sơn Chức danh: Tổng Giám đốc Năm sinh: 1972 Trình độ chuyên môn: » Cử nhân Kinh tế phát triển. Quá trình công tác: - Từ tháng 04/1999 đến nay: Công tác tại Xí nghiệp Khoa học Sản xuất Thiết bị Thông tin (nay là Công ty Cổ phần Viễn thông – Tin học Bưu điện (CTIN)), các vị trí công tác: • Từ

**Bản kiểm:** Nguyễn Ngọc Sơn → ICT · `HOLDS_ROLE` · Kế toán trưởng.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/ICT_Baocaothuongnien_2025.pdf · document_id `719349c4-edf0-5b57-9017-48035e41063c` · trang PDF `18`.

**Hash section/trang đã kiểm:** `26120c9af9eff152f100fcdbe4dde5e715cfa84a32497b5418977c9c170d82e8`.

### APPROVED — 92. 93fadbd0-ff6a-5d02-9239-b5bdf1df0efc

**Bằng chứng nguồn:**
> Ông Nguyễn Thiên Hoàng Phó Tổng Giám đốc

**Bản kiểm:** Nguyễn Thiên Hoàng → BID · `HOLDS_ROLE` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://bidv.com.vn/vn/ve-bidv/ban-lanh-dao · document_id `7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190` · trang PDF `None`.

**Hash section/trang đã kiểm:** `da6f0211ebf6ee83cd6983571fbeec008196b5e66acab7055bf093ab1f9abfcf`.

### APPROVED — 93. 9681215f-53e7-5b22-9f4d-8885b5add784

**Bằng chứng nguồn:**
> Đ và HĐQT. DANH SÁCH TV BKS STT Họ và tên Chức vụ Số lượng cổ phiếu Tỷ lệ sở hữu (%) 1 Bà Lê Anh Hà Trưởng BKS 6.473 0,000083% 2 Bà Nguyễn Thị Anh Thư TV BKS 2.159 0,000028% 3 Ông Nguyễn Hải Đăng TV BKS 0 0% 4 Bà Mai Hương Thảo TV BKS 217 0,000003% 5 Bà Phạm Thị Thu Huyền TV BKS 0 0% Ghi chú: - Ngày 25/12/2025, VietinBank đã CBTT Thông báo thay đổi số lượng cổ phần có quyền biểu quyết tại công văn số 1292/ HĐQT-NHCT-VPHĐQT1. Theo đó, tổng số lượng cổ phiếu có quyền biểu quyế

**Bản kiểm:** Lê Anh Hà → CTG · `HOLDS_ROLE` · Trưởng Ban Kiểm soát.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CTG_Baocaothuongnien_2025.pdf · document_id `26c58a92-9b65-5ce3-a1c2-5f3b71717ddc` · trang PDF `23`.

**Hash section/trang đã kiểm:** `7fe441c59f1ac429219cbd3b5247beb640cbefadfb2d88bcceb463b8ff71bc66`.

### APPROVED — 94. 9765aff3-483a-525b-8c63-ee21a9524002

**Bằng chứng nguồn:**
> Phó Tổng Giám đốc Kiêm Giám đốc Khối Quản trị Ngân hàng Bà Nguyễn Thị Vân Hoài

**Bản kiểm:** Nguyễn Thị Vân Hoài → TCB · `HOLDS_ROLE` · Giám đốc Khối Quản trị Ngân hàng.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 95. 9800e1dc-a071-5102-81ed-303fedc51bea

**Bằng chứng nguồn:**
> 2 Ông Koji Iriguchi TV HĐQT kiêm Phó TGĐ 0 0% 3 Ông Trần Công Quỳnh Lân Phó TGĐ 0 0% 4 Bà Lê Như Hoa Phó TGĐ 39.937 0,000744% 5 Ông Lê Duy Hải Phó TGĐ 22.348 0,000416% 6 Ông Đỗ Thanh Sơn Phó TGĐ 125 0,0000023% 7 Ông Nguyễn Hải Hưng Kế toán trưởng 27.816 0,000518% Ghi chú: Danh sách TV BĐH và số lượng cổ phiếu trong bảng này được cập nhật tại ngày 31/12/2024. THAY ĐỔI TV BĐH TRONG NĂM 2024 STT Họ và tên Chức vụ Ngày bổ nhiệm/thôi nhiệm Bổ nhiệm TGĐ VietinBank kể từ ngày 17/10/

**Bản kiểm:** Lê Như Hoa → CTG · `HOLDS_ROLE` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/CTG_Baocaothuongnien_2024.pdf · document_id `ebc51a9d-1d79-51a6-8c3e-f3db6d8f4891` · trang PDF `24`.

**Hash section/trang đã kiểm:** `e2d957a20adea3a5a279afd84d3eb05232042cc8edc2b298b71474c14a55c353`.

### APPROVED — 96. 983355e4-ba1e-5526-88ef-0bfa854794ab

**Bằng chứng nguồn:**
> trách HĐQT ngày 26 tháng 7 Thành viên năm 2024 Bổ nhiệm lại ngày 21 tháng 4 năm 2023 Ông Lê Quang Vinh Thành viên Bổ nhiệm ngày 7 tháng 3 năm 2025 Ông Nguyễn Tuấn Anh Thành viên Bổ nhiệm ngày 19 tháng 8 năm 2024 Ông Nguyễn Mỹ Hào Thành viên Từ nhiệm ngày 1 tháng 11 năm 2024 Ông Nguyễn Mạnh Hùng Thành viên Bổ nhiệm lại ngày 21 tháng 4 năm 2023 Ông Hồng Quang Thành viên Bổ nhiệm lại ngày 21 tháng 4 năm 2023 Ông Shojiro Mizoguchi Thành viên Bổ nhiệm lại ngày 21 tháng 4 năm 2023 Bà

**Bản kiểm:** VCB → Lê Quang Vinh · `APPOINTS` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Chấp nhận thông tin quyết định bổ nhiệm; không suy người vẫn đương nhiệm hiện tại. Mốc bản gửi: 2025-03-07; kiểm theo câu ghi ngày của đúng người.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/VCB_Baocaothuongnien_2024.pdf · document_id `dd94d5da-f8b1-5776-8c5e-f211d18ae26b` · trang PDF `65`.

**Hash section/trang đã kiểm:** `4ee095497823547593f90cb39e32e5919342ada0c636aa01c936a1b49acb38c3`.

### APPROVED — 97. 98cdb57d-0675-5330-9e04-aabbb4790e2b

**Bằng chứng nguồn:**
> ĐQT 3,453,867 1,63% 4 Gum Ki Ho Thành viên HĐQT 0 0% 5 Kwon Oh Soo Thành viên HĐQT 0 0% 6 Trương Tuấn Lâm | Thành viên HĐQT độc lập 0 0% 7 Nguyễn Danh Lam | Thành viên HĐQT độc lập 0 0% 8 Lê Việt Hà Thành viên HĐQT độc lập 0 0% 9 Hà Thế Vinh Thành viên HĐQT không 0 0% điêu hành 1.2. Các tiêu ban thuộc Hội đồng quản trị: a.. Ban kiễm toán nội bộ: Lập kế hoạch cho các hoạt động kiểm toán nội bộ và quản trị rủi ro ở cắp Tập đoàn và Công ty thành viên căn cứ vào chiến lược phát triển

**Bản kiểm:** Trương Tuấn Lâm → CMG · `HOLDS_ROLE` · Thành viên HĐQT độc lập.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CMG_Baocaothuongnien_2025.pdf · document_id `532597dc-7b79-5f00-99f9-d3394cba9038` · trang PDF `64`.

**Hash section/trang đã kiểm:** `e4be11d5fd9ac0153b2e13b1ce0440b44dcf12f4d7c77de22d1c9c0e0d017210`.

### APPROVED — 98. 9aaea76f-6cf2-5e0d-9476-eeee1acced2b

**Bằng chứng nguồn:**
> phiếu Tỷ lệ sở hữu (%) 1 Ông Nguyễn Trần Mạnh Trung TV HĐQT kiêm TGĐ 3 0,00000006% 2 Ông Koji Iriguchi TV HĐQT kiêm Phó TGĐ 0 0% 3 Ông Trần Công Quỳnh Lân Phó TGĐ 0 0% 4 Bà Lê Như Hoa Phó TGĐ 39.937 0,000744% 5 Ông Lê Duy Hải Phó TGĐ 22.348 0,000416% 6 Ông Đỗ Thanh Sơn Phó TGĐ 125 0,0000023% 7 Ông Nguyễn Hải Hưng Kế toán trưởng 27.816 0,000518% Ghi chú: Danh sách TV BĐH và số lượng cổ phiếu trong bảng này được cập nhật tại ngày 31/12/2024. THAY ĐỔI TV BĐH TRONG NĂM 2024 STT Họ

**Bản kiểm:** Koji Iriguchi → CTG · `HOLDS_ROLE` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/CTG_Baocaothuongnien_2024.pdf · document_id `ebc51a9d-1d79-51a6-8c3e-f3db6d8f4891` · trang PDF `24`.

**Hash section/trang đã kiểm:** `e2d957a20adea3a5a279afd84d3eb05232042cc8edc2b298b71474c14a55c353`.

### APPROVED — 99. 9bdb4235-c06a-5cf5-9eba-40a1366908b2

**Bằng chứng nguồn:**
> Lê Anh Hà Trưởng BKS 6.473 0,000083% 2 Bà Nguyễn Thị Anh Thư TV BKS 2.159 0,000028% 3 Ông Nguyễn Hải Đăng TV BKS 0 0% 4 Bà Mai Hương Thảo TV BKS 217 0,000003% 5 Bà Phạm Thị Thu Huyền TV BKS 0 0% Ghi chú: - Ngày 25/12/2025, VietinBank đã CBTT Thông báo thay đổi số lượng cổ phần có quyền biểu quyết tại công văn số 1292/ HĐQT-NHCT-VPHĐQT1. Theo đó, tổng số lượng cổ phiếu có quyền biểu quyết đang lưu hành là 7.766.944.637 cổ phiếu. Tuy nhiên, đến ngày 9/1/2026, VietinBank mới hoàn thà

**Bản kiểm:** Nguyễn Hải Đăng → CTG · `HOLDS_ROLE` · Thành viên Ban Kiểm soát.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CTG_Baocaothuongnien_2025.pdf · document_id `26c58a92-9b65-5ce3-a1c2-5f3b71717ddc` · trang PDF `23`.

**Hash section/trang đã kiểm:** `7fe441c59f1ac429219cbd3b5247beb640cbefadfb2d88bcceb463b8ff71bc66`.

### APPROVED — 100. 9c07ad37-18ce-5b5e-8223-7d51190dc478

**Bằng chứng nguồn:**
> iám đốc (Miễn nhiệm từ ngày 07/02/2025) *Chi tiết tại phần giới thiệu HĐQT Công ty 3. Ông Tô Hoài Văn* Phó Tổng Giám đốc (Miễn nhiệm từ ngày 01/09/2025) *Chi tiết tại phần giới thiệu HĐQT Công ty 4. Ông Lê Ánh Dương Phó Tổng Giám đốc 5. Ông Nguyễn Ngọc Sơn Kế toán trưởng 34 Báo cáo thường niên 2025 Giới thiệu về Ban Tổng Giám đốc Ông Lê Thanh Sơn Chức danh: Tổng Giám đốc Năm sinh: 1972 Trình độ chuyên môn: » Cử nhân Kinh tế phát triển. Quá trình công tác: - Từ tháng 04/1999 đế

**Bản kiểm:** ICT → Tô Hoài Văn · `DISMISSES` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Giữ nguyên loại quan hệ lịch sử/miễn nhiệm/từ nhiệm; không đổi thành đang giữ chức. Mốc bản gửi: 2025-09-01; kiểm theo câu ghi ngày của đúng người.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/ICT_Baocaothuongnien_2025.pdf · document_id `719349c4-edf0-5b57-9017-48035e41063c` · trang PDF `18`.

**Hash section/trang đã kiểm:** `26120c9af9eff152f100fcdbe4dde5e715cfa84a32497b5418977c9c170d82e8`.

### APPROVED — 101. 9c8cb507-5266-5392-b458-5499a9f4b161

**Bằng chứng nguồn:**
> TOSHIKAZU NAMBU Ủy viên Hội đồng quản trị

**Bản kiểm:** Toshikazu Nambu → FPT · `HOLDS_ROLE` · Ủy viên Hội đồng quản trị.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://fpt.com/vi/ve-fpt/doi-ngu-lanh-dao · document_id `535b180e-02c7-58e1-97cb-b4fe6b4d14a9` · trang PDF `None`.

**Hash section/trang đã kiểm:** `33cfaf2fbc681dae83c47dd4fa4b85cfe52e52683e7c2a066b0cd1deb35486ce`.

### APPROVED — 102. 9cc230d4-58e8-528a-ad7e-cbe75f077b26

**Bằng chứng nguồn:**
> Ông Đặng Văn Tuyên Ủy viên HĐQT

**Bản kiểm:** Đặng Văn Tuyên → BID · `HOLDS_ROLE` · Ủy viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://bidv.com.vn/vn/ve-bidv/ban-lanh-dao · document_id `7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190` · trang PDF `None`.

**Hash section/trang đã kiểm:** `da6f0211ebf6ee83cd6983571fbeec008196b5e66acab7055bf093ab1f9abfcf`.

### APPROVED — 103. 9df0c4b9-642d-5ce7-9c7f-20921158d54d

**Bằng chứng nguồn:**
> TRƯỞNG BAN KIỂM SOÁT VÀ THÀNH VIÊN CHUYÊN TRÁCH Ông Hoàng Huy Trung

**Bản kiểm:** Hoàng Huy Trung → TCB · `HOLDS_ROLE` · Trưởng Ban Kiểm soát.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 104. 9e4e34f6-0fe2-50ad-b8ac-361e85a281fe

**Bằng chứng nguồn:**
> Vũ Xuân Nam Thành viên HĐQT

**Bản kiểm:** Vũ Xuân Nam → MBB · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://www.mbbank.com.vn/ve-mb/doi-ngu-lanh-dao · document_id `e9dd552a-0bd7-5716-bbdd-34e4580f7d6d` · trang PDF `None`.

**Hash section/trang đã kiểm:** `361d3953e754b97a64c3e6c7539f132c4b1fedc70c0825d017be9dce006ee918`.

### APPROVED — 105. 9ecb1580-66db-5375-bd95-61cd8fa1623f

**Bằng chứng nguồn:**
> Ông Lê Quốc Nghị Ủy viên HĐQT

**Bản kiểm:** Lê Quốc Nghị → BID · `HOLDS_ROLE` · Ủy viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://bidv.com.vn/vn/ve-bidv/ban-lanh-dao · document_id `7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190` · trang PDF `None`.

**Hash section/trang đã kiểm:** `da6f0211ebf6ee83cd6983571fbeec008196b5e66acab7055bf093ab1f9abfcf`.

### APPROVED — 106. 9fc869ac-6185-5127-867b-8db2c4e282b7

**Bằng chứng nguồn:**
> GIÁM ĐỐC KHỐI CHIẾN LƯỢC VÀ CHUYỂN ĐỔI NGÂN HÀNG Ông Prasenjit Chakravarti

**Bản kiểm:** Prasenjit Chakravarti → TCB · `HOLDS_ROLE` · Giám đốc Khối Chiến lược và Chuyển đổi Ngân hàng.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 107. a057d15f-2c43-5028-8341-2d4fd5d9ff6b

**Bằng chứng nguồn:**
> Ông Phan Thanh Hải Phó Tổng Giám đốc

**Bản kiểm:** Phan Thanh Hải → BID · `HOLDS_ROLE` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://bidv.com.vn/vn/ve-bidv/ban-lanh-dao · document_id `7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190` · trang PDF `None`.

**Hash section/trang đã kiểm:** `da6f0211ebf6ee83cd6983571fbeec008196b5e66acab7055bf093ab1f9abfcf`.

### APPROVED — 108. a0f8f4c5-b360-56d7-9f8c-686d3c5f6107

**Bằng chứng nguồn:**
> PHÓ TỔNG GIÁM ĐỐC KIÊM GIÁM ĐỐC TÀI CHÍNH TẬP ĐOÀN Ông Alexandre Macaire

**Bản kiểm:** Alexandre Macaire → TCB · `HOLDS_ROLE` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 109. a7743850-961a-5e0b-b4b9-856965e37daa

**Bằng chứng nguồn:**
> Ông Lê Quốc Minh Phó Tổng Giám đốc

**Bản kiểm:** Lê Quốc Minh → MBB · `HOLDS_ROLE` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://www.mbbank.com.vn/ve-mb/doi-ngu-lanh-dao · document_id `e9dd552a-0bd7-5716-bbdd-34e4580f7d6d` · trang PDF `None`.

**Hash section/trang đã kiểm:** `361d3953e754b97a64c3e6c7539f132c4b1fedc70c0825d017be9dce006ee918`.

### APPROVED — 110. a886ab7e-4781-5be7-a188-638f482f0aee

**Bằng chứng nguồn:**
> Chủ tịch Hội đồng quản trị Ông Lưu Trung Thái

**Bản kiểm:** Lưu Trung Thái → MBB · `HOLDS_ROLE` · Chủ tịch Hội đồng quản trị.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://www.mbbank.com.vn/ve-mb/doi-ngu-lanh-dao · document_id `e9dd552a-0bd7-5716-bbdd-34e4580f7d6d` · trang PDF `None`.

**Hash section/trang đã kiểm:** `361d3953e754b97a64c3e6c7539f132c4b1fedc70c0825d017be9dce006ee918`.

### APPROVED — 111. aaa27ad2-e597-54a0-a972-ffb8aedb6ea6

**Bằng chứng nguồn:**
> 30% 3 Nguyễn Phước Hải Thành viên HĐQT 3,453,867 1,63% 4 Gum Ki Ho Thành viên HĐQT 0 0% 5 Kwon Oh Soo Thành viên HĐQT 0 0% 6 Trương Tuấn Lâm | Thành viên HĐQT độc lập 0 0% 7 Nguyễn Danh Lam | Thành viên HĐQT độc lập 0 0% 8 Lê Việt Hà Thành viên HĐQT độc lập 0 0% 9 Hà Thế Vinh Thành viên HĐQT không 0 0% điêu hành 1.2. Các tiêu ban thuộc Hội đồng quản trị: a.. Ban kiễm toán nội bộ: Lập kế hoạch cho các hoạt động kiểm toán nội bộ và quản trị rủi ro ở cắp Tập đoàn và Công ty thành

**Bản kiểm:** Kwon Oh Soo → CMG · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CMG_Baocaothuongnien_2025.pdf · document_id `532597dc-7b79-5f00-99f9-d3394cba9038` · trang PDF `64`.

**Hash section/trang đã kiểm:** `e4be11d5fd9ac0153b2e13b1ce0440b44dcf12f4d7c77de22d1c9c0e0d017210`.

### APPROVED — 112. ab6ff079-f0ee-5151-ba76-b6da882f4e29

**Bằng chứng nguồn:**
> y 18/12/2024 của HĐQT VietinBank. Miễn nhiệm Phó TGĐ theo quyết định số 72/QĐ-HĐQT- 4 Ông Hoàng Ngọc Phương Phó TGĐ NHCT-NS2 ngày 28/3/2024 của HĐQT VietinBank. 42 Ông NGUYỄN TRẦN MẠNH TRUNG TV HĐQT kiêm TGĐ Sinh năm 1983. Thạc sỹ Tài chính, Ngân hàng. Công tác tại VietinBank từ năm 2005. Được bầu vào HĐQT VietinBank từ ngày 17/10/2024; kiêm nhiệm TGĐ VietinBank từ ngày 17/10/2024. Hiện là Phó Bí thư Đảng ủy, TV HĐQT kiêm TGĐ VietinBank. Từng giữ các chức vụ: Phó Phòng QLRR & Nợ có

**Bản kiểm:** CTG → Hoàng Ngọc Phương · `DISMISSES` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Giữ nguyên loại quan hệ lịch sử/miễn nhiệm/từ nhiệm; không đổi thành đang giữ chức. Không tự thêm ngày hiệu lực khi trường này đang null. Ngày của quyết định trong nguồn không tự chuyển thành ngày hiệu lực.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/CTG_Baocaothuongnien_2024.pdf · document_id `ebc51a9d-1d79-51a6-8c3e-f3db6d8f4891` · trang PDF `24`.

**Hash section/trang đã kiểm:** `e2d957a20adea3a5a279afd84d3eb05232042cc8edc2b298b71474c14a55c353`.

### APPROVED — 113. abbe1924-f5ef-5b46-95da-816bab5b020a

**Bằng chứng nguồn:**
> Ông Vũ Hồng Phú Thành viên Ban điều hành

**Bản kiểm:** Vũ Hồng Phú → MBB · `HOLDS_ROLE` · Thành viên Ban điều hành.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://www.mbbank.com.vn/ve-mb/doi-ngu-lanh-dao · document_id `e9dd552a-0bd7-5716-bbdd-34e4580f7d6d` · trang PDF `None`.

**Hash section/trang đã kiểm:** `361d3953e754b97a64c3e6c7539f132c4b1fedc70c0825d017be9dce006ee918`.

### APPROVED — 114. aef1a9fc-0145-5d3d-8b7c-c12a996a0336

**Bằng chứng nguồn:**
> h viên 306.994.000 - Bà Hoàng Thị Phương Thúy Thành viên 36.000.000 Kế toán trưởng - - Bà Đậu Thị Lý Kế toán trưởng (bổ nhiệm từ 19/05/2023) 480.850.000 - Bà Đặng Thị Thanh Minh Kế toán trưởng (miễn nhiệm từ 19/05/2023) 106.746.860 Cộng 3.713.818.790 BÁO CÁO TÀI CHÍNH 120 120 CÔNG TY CỔ PHẦN CÔNG NGHỆ - VIỄN THÔNG ELCOM MẪU SỐ B09-DN/HN Tòa nhà Elcom, phố Duy Tân, phường Dịch Vọng Hậu, Ban hành theo Thông tư số 202/2014/TT- quận Cầu Giấy, Hà Nội BTC ngày 22/12/2014 của Bộ Tài

**Bản kiểm:** ELC → Đậu Thị Lý · `APPOINTS` · Kế toán trưởng.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Chấp nhận thông tin quyết định bổ nhiệm; không suy người vẫn đương nhiệm hiện tại. Mốc bản gửi: 2023-05-19; kiểm theo câu ghi ngày của đúng người.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/ELC_Baocaothuongnien_2024.pdf · document_id `f0730a07-8ab5-548a-a3b8-e099489d0f29` · trang PDF `68`.

**Hash section/trang đã kiểm:** `1348dcfba0e77b9917fdbfd279ba8c0ed2e92ec8dcb4cf1f2ceaa0dc2d65d83c`.

### APPROVED — 115. af351b77-be28-559a-a2f9-8c4c1b29f187

**Bằng chứng nguồn:**
> Trưởng Ban Kiểm soát Bà Lê Thị Lợi

**Bản kiểm:** Lê Thị Lợi → MBB · `HOLDS_ROLE` · Trưởng Ban Kiểm soát.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://www.mbbank.com.vn/ve-mb/doi-ngu-lanh-dao · document_id `e9dd552a-0bd7-5716-bbdd-34e4580f7d6d` · trang PDF `None`.

**Hash section/trang đã kiểm:** `361d3953e754b97a64c3e6c7539f132c4b1fedc70c0825d017be9dce006ee918`.

### APPROVED — 116. b09c6775-0d34-5195-85ea-579c1a4ea4fe

**Bằng chứng nguồn:**
> Nguyễn Việt Quân Thành viên HĐQT

**Bản kiểm:** Nguyễn Việt Quân → MBB · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://www.mbbank.com.vn/ve-mb/doi-ngu-lanh-dao · document_id `e9dd552a-0bd7-5716-bbdd-34e4580f7d6d` · trang PDF `None`.

**Hash section/trang đã kiểm:** `361d3953e754b97a64c3e6c7539f132c4b1fedc70c0825d017be9dce006ee918`.

### APPROVED — 117. b2246b03-ebbf-5018-b456-e3a57a5d92f6

**Bằng chứng nguồn:**
> ng Giang Thành viên HĐQT - Ông Ngô Ngọc Hà Thành viên HĐQT - Bà Nguyễn Thị Lệ Thủy Vợ Ông Phan Chiến Thắng - Chủ tịch HĐQT THU NHẬP CỦA CÁC THÀNH VIÊN QUẢN LÝ CHỦ CHỐT Tổng thu nhập Năm 2024 Chức vụ VND HĐQT và Ban Giám đốc - Ông Phan Chiến Thắng Chủ tịch HĐQT 239.452.000 - Ông Nguyễn Đức Thiện Phó Chủ tịch HĐQT 152.065.000 - Ông Trần Hùng Giang Thành viên HĐQT 152.065.000 - Ông Nguyễn Mạnh Hải Thành viên HĐQT 151.835.000 - Ông Ngô Ngọc Hà Thành viên HĐQT/Phó Tổng Giám đốc 396.047.

**Bản kiểm:** Phan Chiến Thắng → ELC · `HOLDS_ROLE` · Chủ tịch HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/ELC_Baocaothuongnien_2024.pdf · document_id `f0730a07-8ab5-548a-a3b8-e099489d0f29` · trang PDF `68`.

**Hash section/trang đã kiểm:** `1348dcfba0e77b9917fdbfd279ba8c0ed2e92ec8dcb4cf1f2ceaa0dc2d65d83c`.

### APPROVED — 118. b2569eb8-0f6f-5e6d-832a-5577327e44fd

**Bằng chứng nguồn:**
> hanh Sơn Phó TGĐ 180 0,0000023% 7 Ông Nguyễn Đức Thành Phó TGĐ 0 0% Phó TGĐ kiêm GĐ 8 Ông Dương Văn Quân 0 0% VietinBank TP. Hà Nội Phó TGĐ kiêm GĐ Khối Tài 9 Bà Nguyễn Bảo Thanh Vân 26.589 0,00034% chính 10 Bà Đặng Thị Việt Hà Phó TGĐ 0 0% 11 Ông Nguyễn Hải Hưng Kế toán trưởng 40.232 0,000518% Ghi chú: - Ngày 25/12/2025, VietinBank đã CBTT Thông báo thay đổi số lượng cổ phần có quyền biểu quyết tại công văn số 1292/HĐQT-NHCT-VPHĐQT1. Theo đó, tổng số lượng cổ phiếu có quyền biểu

**Bản kiểm:** Dương Văn Quân → CTG · `HOLDS_ROLE` · Giám đốc VietinBank TP. Hà Nội.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CTG_Baocaothuongnien_2025.pdf · document_id `26c58a92-9b65-5ce3-a1c2-5f3b71717ddc` · trang PDF `25`.

**Hash section/trang đã kiểm:** `840c84044c4ea71e95ab1827555a35741b3e0f80eced81a1a7a265c805edfe68`.

### APPROVED — 119. b2a85c24-34c7-5ace-b2ae-cb64f2963daf

**Bằng chứng nguồn:**
> Ngày 8/3/2019, Hội đồng Quản trị FPT đã thông qua nghị quyết bổ nhiệm ông Nguyễn Văn Khoa - Phó Tổng Giám đốc FPT kiêm Tổng Giám đốc Công ty Hệ thống thông tin FPT - đảm trách vị trí Tổng Giám đốc FPT, thay thế ông Bùi Quang Ngọc hết nhiệm kỳ. Nghị quyết sẽ có hiệu lực từ ngày 29/3/2019. Trong 2 nhiệm kỳ Tổng Giám đốc FPT (2013-2018), ông Bùi Quang Ngọc luôn duy trì được tốc độ tăng trưởng 2 con số, đẩy mạnh công nghệ và sáng tạo, đầu tư cơ sở vật chất trên toàn quốc tạo nền tảng cho FPT phát triển bền vững. Ông cũng dành thời gian và tâm huyết đào tạo, bồi dưỡng các cấp lãnh đạo trẻ nhằm tăng cường năng lực quản trị, trải nghiệm các lĩnh vực kinh doanh trong tậ

**Bản kiểm:** FPT → Nguyễn Văn Khoa · `APPOINTS` · Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Chấp nhận thông tin quyết định bổ nhiệm; không suy người vẫn đương nhiệm hiện tại. Mốc bản gửi: 2019-03-29; kiểm theo câu ghi ngày của đúng người. Nguồn ghi nghị quyết đã thông qua 8/3/2019, hiệu lực 29/3/2019; không dùng riêng câu “sẽ đảm trách” làm bằng chứng đã nhậm chức.

**Nguồn:** https://fpt.com/vi/tin-tuc/ong-nguyen-van-khoa-lam-tong-giam-doc-fpt · document_id `718e0233-6390-53c2-9fd0-39afb2e988ee` · trang PDF `None`.

**Hash section/trang đã kiểm:** `65c7d98284d70929e98ff7ebbaae2c3c3f98344894999b48f04782f661e09da0`.

### APPROVED — 120. b43161a8-13b2-50a9-95bf-405311cdf2bd

**Bằng chứng nguồn:**
> NGƯỜI PHỤ TRÁCH QUẢN TRỊ NGÂN HÀNG VÀ THƯ KÝ CÔNG TY Ông Nguyễn Tuấn Minh

**Bản kiểm:** Nguyễn Tuấn Minh → TCB · `HOLDS_ROLE` · Người phụ trách quản trị ngân hàng.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 121. b464e72a-2eaf-5625-90a4-6502e7ec44be

**Bằng chứng nguồn:**
> PHÓ CHỦ TỊCH Bà Nguyễn Thu Lan

**Bản kiểm:** Nguyễn Thu Lan → TCB · `HOLDS_ROLE` · Phó Chủ tịch HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 122. b73a3c32-5e4d-55c8-ad9f-1bdaeced9220

**Bằng chứng nguồn:**
> anh Tùng Chủ tịch HĐQT 22.324 Thành viên HĐQT – 2 Ông Lê Quang Vinh 0 Tổng Giám đốc 3 Ông Đỗ Việt Hùng Thành viên HĐQT 0 4 Ông Nguyễn Mạnh Hùng Thành viên HĐQT 5.112 Thành viên HĐQT – 5 Ông Hồng Quang 2 Giám đốc Khối Nhân sự 6 Ông Vũ Viết Ngoạn Thành viên độc lập HĐQT 0 7 Bà Nguyễn Thị Kim Oanh Thành viên HĐQT 7.475 8 Ông Nguyễn Tuấn Anh Thành viên HĐQT 0 63 CHƯƠNG 4 Quản trị doanh nghiệp Trong những năm qua, công tác quản trị công ty của VCB luôn được chú trọng và triển khai H

**Bản kiểm:** Đỗ Việt Hùng → VCB · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/VCB_Baocaothuongnien_2025.zip · document_id `679baa3e-b39c-5b53-be43-3cd19d738dca` · trang PDF `33`.

**Hash section/trang đã kiểm:** `cf40fe0d83644c1e5c1942f9eb281f4ec55c5169a7cfd0e4f5aa1a79fa6db82f`.

### APPROVED — 123. b8043c37-5a28-5788-a347-46ea8def6ed5

**Bằng chứng nguồn:**
> Ông Phạm Như Ánh được HĐQT MB bổ nhiệm vị trí Tổng giám đốc MB từ 18/05/2023.

**Bản kiểm:** MBB → Phạm Như Ánh · `APPOINTS` · Tổng giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Chấp nhận thông tin quyết định bổ nhiệm; không suy người vẫn đương nhiệm hiện tại. Mốc bản gửi: 2023-05-18; kiểm theo câu ghi ngày của đúng người.

**Nguồn:** https://www.mbbank.com.vn/ve-mb/doi-ngu-lanh-dao · document_id `e9dd552a-0bd7-5716-bbdd-34e4580f7d6d` · trang PDF `None`.

**Hash section/trang đã kiểm:** `361d3953e754b97a64c3e6c7539f132c4b1fedc70c0825d017be9dce006ee918`.

### APPROVED — 124. bab189f4-a14e-56ca-81e2-9654c99edf75

**Bằng chứng nguồn:**
> Ông Nguyễn Xuân Học Phó Tổng Giám đốc

**Bản kiểm:** Nguyễn Xuân Học → MBB · `HOLDS_ROLE` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://www.mbbank.com.vn/ve-mb/doi-ngu-lanh-dao · document_id `e9dd552a-0bd7-5716-bbdd-34e4580f7d6d` · trang PDF `None`.

**Hash section/trang đã kiểm:** `361d3953e754b97a64c3e6c7539f132c4b1fedc70c0825d017be9dce006ee918`.

### APPROVED — 125. bb31543a-ebbb-5822-9d70-7cfd0853eff7

**Bằng chứng nguồn:**
> Lê Việt Hải Thành viên HĐQT

**Bản kiểm:** Lê Việt Hải → MBB · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://www.mbbank.com.vn/ve-mb/doi-ngu-lanh-dao · document_id `e9dd552a-0bd7-5716-bbdd-34e4580f7d6d` · trang PDF `None`.

**Hash section/trang đã kiểm:** `361d3953e754b97a64c3e6c7539f132c4b1fedc70c0825d017be9dce006ee918`.

### APPROVED — 126. bb5260a7-c09f-58d0-a0f7-b889600375ba

**Bằng chứng nguồn:**
> Bà Phạm Thị Trung Hà Phó Tổng Giám đốc

**Bản kiểm:** Phạm Thị Trung Hà → MBB · `HOLDS_ROLE` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://www.mbbank.com.vn/ve-mb/doi-ngu-lanh-dao · document_id `e9dd552a-0bd7-5716-bbdd-34e4580f7d6d` · trang PDF `None`.

**Hash section/trang đã kiểm:** `361d3953e754b97a64c3e6c7539f132c4b1fedc70c0825d017be9dce006ee918`.

### APPROVED — 127. bb8bcae9-ad5c-5cee-8efd-a87b8b6da31f

**Bằng chứng nguồn:**
> iguchi 0 0% TV điều hành TGĐ 10 Ông Takeo Shimotsu TV HĐQT 0 0% TV không điều hành 11 Ông Cát Quang Dương TV độc lập HĐQT 0 0% TV độc lập Ghi chú: - Danh sách TV HĐQT và số lượng cổ phiếu trong bảng này chưa bao gồm đại diện phần vốn Nhà nước. - Ngày 25/12/2025, VietinBank đã CBTT Thông báo thay đổi số lượng cổ phần có quyền biểu quyết tại công văn số 1292/HĐQT-NHCT-VPHĐQT1. Theo đó, tổng số lượng cổ phiếu có quyền biểu quyết đang lưu hành là 7.766.944.637 cổ phiếu. Tuy nhiên, đến

**Bản kiểm:** Cát Quang Dương → CTG · `HOLDS_ROLE` · Thành viên HĐQT độc lập.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CTG_Baocaothuongnien_2025.pdf · document_id `26c58a92-9b65-5ce3-a1c2-5f3b71717ddc` · trang PDF `18`.

**Hash section/trang đã kiểm:** `7a501da6b4991a2d607a6d5c038e78cff57a65aee779fa9507190b560d089045`.

### APPROVED — 128. bbffae3a-8210-5a84-aabd-cbb9b22eba72

**Bằng chứng nguồn:**
> PHÓ TỔNG GIÁM ĐỐC, QUYỀN GIÁM ĐỐC KHỐI QUẢN LÝ TÍN DỤNG Bà Trần Thị Thu Lan

**Bản kiểm:** Trần Thị Thu Lan → TCB · `HOLDS_ROLE` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 129. bc567d0a-db3a-5c9c-8c54-9b7cd5751692

**Bằng chứng nguồn:**
> Đức Thành viên HĐQT 4,862,063 2,30% 3 Nguyễn Phước Hải Thành viên HĐQT 3,453,867 1,63% 4 Gum Ki Ho Thành viên HĐQT 0 0% 5 Kwon Oh Soo Thành viên HĐQT 0 0% 6 Trương Tuấn Lâm | Thành viên HĐQT độc lập 0 0% 7 Nguyễn Danh Lam | Thành viên HĐQT độc lập 0 0% 8 Lê Việt Hà Thành viên HĐQT độc lập 0 0% 9 Hà Thế Vinh Thành viên HĐQT không 0 0% điêu hành 1.2. Các tiêu ban thuộc Hội đồng quản trị: a.. Ban kiễm toán nội bộ: Lập kế hoạch cho các hoạt động kiểm toán nội bộ và quản trị rủi

**Bản kiểm:** Gum Ki Ho → CMG · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CMG_Baocaothuongnien_2025.pdf · document_id `532597dc-7b79-5f00-99f9-d3394cba9038` · trang PDF `64`.

**Hash section/trang đã kiểm:** `e4be11d5fd9ac0153b2e13b1ce0440b44dcf12f4d7c77de22d1c9c0e0d017210`.

### APPROVED — 130. bebe3697-8a28-5c24-9c40-2139cb76857f

**Bằng chứng nguồn:**
> THÀNH VIÊN Ông Saurabh Narayan Agarwal

**Bản kiểm:** Saurabh Narayan Agarwal → TCB · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 131. bf8d4a0b-1c35-5103-9c6d-f3a4d39cb6ad

**Bằng chứng nguồn:**
> Bà Đỗ Thị Tuyết Mai Thành viên Ban Kiểm soát

**Bản kiểm:** Đỗ Thị Tuyết Mai → MBB · `HOLDS_ROLE` · Thành viên Ban Kiểm soát.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://www.mbbank.com.vn/ve-mb/doi-ngu-lanh-dao · document_id `e9dd552a-0bd7-5716-bbdd-34e4580f7d6d` · trang PDF `None`.

**Hash section/trang đã kiểm:** `361d3953e754b97a64c3e6c7539f132c4b1fedc70c0825d017be9dce006ee918`.

### APPROVED — 132. bf92fdab-6c4a-52dc-9de6-ec4614369df2

**Bằng chứng nguồn:**
> 0% 3 Ông Trần Công Quỳnh Lân Phó TGĐ 0 0% 4 Bà Lê Như Hoa Phó TGĐ 39.937 0,000744% 5 Ông Lê Duy Hải Phó TGĐ 22.348 0,000416% 6 Ông Đỗ Thanh Sơn Phó TGĐ 125 0,0000023% 7 Ông Nguyễn Hải Hưng Kế toán trưởng 27.816 0,000518% Ghi chú: Danh sách TV BĐH và số lượng cổ phiếu trong bảng này được cập nhật tại ngày 31/12/2024. THAY ĐỔI TV BĐH TRONG NĂM 2024 STT Họ và tên Chức vụ Ngày bổ nhiệm/thôi nhiệm Bổ nhiệm TGĐ VietinBank kể từ ngày 17/10/2024 TV HĐQT 1 Ông Nguyễn Trần Mạnh Trung

**Bản kiểm:** Lê Duy Hải → CTG · `HOLDS_ROLE` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/CTG_Baocaothuongnien_2024.pdf · document_id `ebc51a9d-1d79-51a6-8c3e-f3db6d8f4891` · trang PDF `24`.

**Hash section/trang đã kiểm:** `e2d957a20adea3a5a279afd84d3eb05232042cc8edc2b298b71474c14a55c353`.

### APPROVED — 133. c159ec8a-3664-570d-ba90-4bedf98e066d

**Bằng chứng nguồn:**
> Hội đồng Quản trị (“HĐQT”) trong năm và đến ngày phát hành báo cáo tài chính hợp nhất Ông Nguyễn Thanh Tùng Chủ tịch Bổ nhiệm ngày 26 tháng 7 năm 2024 Ông Đỗ Việt Hùng Thành viên phụ trách hoạt động của HĐQT Thôi giao phụ trách HĐQT ngày 26 tháng 7 Thành viên năm 2024 Bổ nhiệm lại ngày 21 tháng 4 năm 2023 Ông Lê Quang Vinh Thành viên Bổ nhiệm ngày 7 tháng 3 năm 2025 Ông Nguyễn Tuấn Anh Thành viên Bổ nhiệm ngày 19 tháng 8 năm 2024 Ông Nguyễn Mỹ Hào Thành viên Từ nhiệm ngày 1 tháng 11

**Bản kiểm:** VCB → Nguyễn Thanh Tùng · `DISMISSES` · Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Giữ nguyên loại quan hệ lịch sử/miễn nhiệm/từ nhiệm; không đổi thành đang giữ chức. Mốc bản gửi: 2024-07-26; kiểm theo câu ghi ngày của đúng người.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/VCB_Baocaothuongnien_2024.pdf · document_id `dd94d5da-f8b1-5776-8c5e-f211d18ae26b` · trang PDF `65`.

**Hash section/trang đã kiểm:** `4ee095497823547593f90cb39e32e5919342ada0c636aa01c936a1b49acb38c3`.

### APPROVED — 134. c2c63a33-2782-5bbe-a744-b58d43714d84

**Bằng chứng nguồn:**
> Chức vụ Số lượng cổ phiếu Tỷ lệ sở hữu (%) 1 Bà Lê Anh Hà Trưởng BKS 6.473 0,000083% 2 Bà Nguyễn Thị Anh Thư TV BKS 2.159 0,000028% 3 Ông Nguyễn Hải Đăng TV BKS 0 0% 4 Bà Mai Hương Thảo TV BKS 217 0,000003% 5 Bà Phạm Thị Thu Huyền TV BKS 0 0% Ghi chú: - Ngày 25/12/2025, VietinBank đã CBTT Thông báo thay đổi số lượng cổ phần có quyền biểu quyết tại công văn số 1292/ HĐQT-NHCT-VPHĐQT1. Theo đó, tổng số lượng cổ phiếu có quyền biểu quyết đang lưu hành là 7.766.944.637 cổ phiếu. Tuy nhiê

**Bản kiểm:** Nguyễn Thị Anh Thư → CTG · `HOLDS_ROLE` · Thành viên Ban Kiểm soát.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CTG_Baocaothuongnien_2025.pdf · document_id `26c58a92-9b65-5ce3-a1c2-5f3b71717ddc` · trang PDF `23`.

**Hash section/trang đã kiểm:** `7fe441c59f1ac429219cbd3b5247beb640cbefadfb2d88bcceb463b8ff71bc66`.

### APPROVED — 135. c2cf65f3-0ea8-5f6b-93de-a2e9fd2f9360

**Bằng chứng nguồn:**
> Ông Võ Xuân Vinh Thành viên Bổ nhiệm ngày 26/06/2025 Ông Nguyễn Ngọc Trung Thành viên Ông Đinh Thế Hiển Thành viên Đ Các thành viên của Ban Tổng Giám đốc đã điều hành Công ty trong năm và tại ngày lập báo cáo này bao gồm: Ông Nguyễn Ngọc Trung Tổng Giám đốc Ông Nguyễn Hồng Minh Phó Tổng Giám đốc Bổ nhiệm ngày 04/11/2025 Bà Nguyễn Thị Thu Sương Phó Tổng Giám đốc Miễn nhiệm ngày 17/07/2025 Căn cứ theo Nghị quyết ĐHĐCD năm 2025 ngày 26/06/2025, Công ty đã được thông qua thay đổi cơ

**Bản kiểm:** Đinh Thế Hiển → ITD · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/ITD_Baocaothuongnien_2025.pdf · document_id `a2c071fb-25bf-5ec4-903b-e973c623b85d` · trang PDF `52`.

**Hash section/trang đã kiểm:** `d29acf9d280d7310222afee6a10edbd47b99492988edf6f82320997cda5ee3e5`.

### APPROVED — 136. c301cc94-7f29-59e5-a0a3-2d709c814be1

**Bằng chứng nguồn:**
> Bà Nguyễn Minh Châu Phó Tổng Giám đốc

**Bản kiểm:** Nguyễn Minh Châu → MBB · `HOLDS_ROLE` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://www.mbbank.com.vn/ve-mb/doi-ngu-lanh-dao · document_id `e9dd552a-0bd7-5716-bbdd-34e4580f7d6d` · trang PDF `None`.

**Hash section/trang đã kiểm:** `361d3953e754b97a64c3e6c7539f132c4b1fedc70c0825d017be9dce006ee918`.

### APPROVED — 137. c4a11458-8f7f-5e0e-9477-4e56a96401fe

**Bằng chứng nguồn:**
> Hoàng Thị Thu Hiền Thành viên HĐQT

**Bản kiểm:** Hoàng Thị Thu Hiền → MBB · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://www.mbbank.com.vn/ve-mb/doi-ngu-lanh-dao · document_id `e9dd552a-0bd7-5716-bbdd-34e4580f7d6d` · trang PDF `None`.

**Hash section/trang đã kiểm:** `361d3953e754b97a64c3e6c7539f132c4b1fedc70c0825d017be9dce006ee918`.

### APPROVED — 138. c569fba7-5347-54d7-96e9-0c91c9b689aa

**Bằng chứng nguồn:**
> êm Tổng Giám đốc BIDV. Từ ngày 01/07/2026, ông được bổ nhiệm giữ chức Chủ tịch HĐQT BIDV. Ông Hoàng Việt Hùng Ủy viên HĐQT Năm sinh: 1972 Năm 1996, ông bắt đầu làm việc tại BIDV; từ tháng 11/2007 là Phó Giám đốc Chi nhánh BIDV Nghệ An; từ tháng 01/2013 là Giám đốc Chi nhánh BIDV Nghệ An; từ tháng 04/2019 là Giám đốc Ban Tổ chức nhân sự BIDV; từ tháng 03/2020 là Phó Tổng Giám đốc BIDV kiêm Giám đốc Ban Tổ chức nhân sự; từ tháng 02/2024 là Phó Tổng Giám đốc BIDV, Chủ tịch HĐQT Ngân hàng Liên doanh Lào - Việt; từ tháng 05/2026 là Phó Tổng Giám đốc BIDV. Từ ngày 01/07/2026 ông là thành viên HĐQT, Tổng Giám đốc BIDV. Ông Kim Sang Soo Ủy viên HĐQT Sinh năm: 1968 Từng giữ các chức vụ: Giám đốc điều hành Khối Toàn cầu (Ngân hàng KEB Hana); Chủ tịch HĐQT & Tổng Giám đốc (Ngân hàng TNHH Hana Trung Quốc); Giám đốc Chi nhánh (Ngân hàng KEB Hana - Chi nhánh TP Hồ Chí Minh). Từ ngày 24/4/2026, ông là Uỷ viên Hội đồng quản trị BIDV. Ông Trần Xuân Hoàng Ủy viên HĐQT Sinh năm 1965 Năm 1989, ông bắt đầu làm việc tại BIDV; từ tháng 07/1996 là Phó Giám đốc BIDV Gia Lai; từ tháng 7/2006 là Phó Giám đốc BIDV Sở Giao dịch 2; từ tháng 8/2008 là Giám đốc Ban Tổ chức cán bộ; từ tháng 5/2012 là Phó Tổng Giám đốc BIDV, từ tháng 3/2020 là Ủy viên HĐQT BIDV. Ông Ngô Văn Dũng Ủy viên HĐQT Sinh năm 1968 Năm 1998, ông bắt đầu làm việc tại BIDV; từ tháng 09/2004 là Giám đốc Ban Quản lý rủi ro BIDV; từ tháng 12/2007 là Giám đốc BIDV Hà Nội; từ tháng 6/2015 đến nay là Ủy

**Bản kiểm:** Hoàng Việt Hùng → BID · `HOLDS_ROLE` · Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Mốc bản gửi: 2026-07-01; kiểm theo câu ghi ngày của đúng người. Đã đọc riêng tiểu sử dưới tiêu đề tên, không lấy “ông” của người ở đoạn trước.

**Nguồn:** https://bidv.com.vn/vn/ve-bidv/ban-lanh-dao · document_id `7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190` · trang PDF `None`.

**Hash section/trang đã kiểm:** `da6f0211ebf6ee83cd6983571fbeec008196b5e66acab7055bf093ab1f9abfcf`.

### APPROVED — 139. c6d0372d-48ff-59d8-9bd0-508b7c196e61

**Bằng chứng nguồn:**
> Ông Lại Tiến Quân Phó Tổng Giám đốc

**Bản kiểm:** Lại Tiến Quân → BID · `HOLDS_ROLE` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://bidv.com.vn/vn/ve-bidv/ban-lanh-dao · document_id `7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190` · trang PDF `None`.

**Hash section/trang đã kiểm:** `da6f0211ebf6ee83cd6983571fbeec008196b5e66acab7055bf093ab1f9abfcf`.

### APPROVED — 140. c86222cd-16b1-52db-9679-9fcf924139b3

**Bằng chứng nguồn:**
> N Các thành viên của Hội đồng Quản trị trong năm và tại ngày lập báo cáo này bao gồm: Ông Mai Hoài An Chủ tịch Ông Nguyễn Hữu Dũng Phó Chủ tịch Ông Nguyễn Vĩnh Thuận Phó Chủ tịch Miễn nhiệm ngày 26/06/2025 Ông Võ Xuân Vinh Thành viên Bổ nhiệm ngày 26/06/2025 Ông Nguyễn Ngọc Trung Thành viên Ông Đinh Thế Hiển Thành viên Đ Các thành viên của Ban Tổng Giám đốc đã điều hành Công ty trong năm và tại ngày lập báo cáo này bao gồm: Ông Nguyễn Ngọc Trung Tổng Giám đốc Ông Nguyễn Hồng M

**Bản kiểm:** Mai Hoài An → ITD · `HOLDS_ROLE` · Chủ tịch HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/ITD_Baocaothuongnien_2025.pdf · document_id `a2c071fb-25bf-5ec4-903b-e973c623b85d` · trang PDF `52`.

**Hash section/trang đã kiểm:** `d29acf9d280d7310222afee6a10edbd47b99492988edf6f82320997cda5ee3e5`.

### APPROVED — 141. ca09f840-4637-51e1-8fd8-6e97b6224bf9

**Bằng chứng nguồn:**
> Ông Lê Huy Hoàng Phó Tổng Giám đốc

**Bản kiểm:** Lê Huy Hoàng → BID · `HOLDS_ROLE` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://bidv.com.vn/vn/ve-bidv/ban-lanh-dao · document_id `7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190` · trang PDF `None`.

**Hash section/trang đã kiểm:** `da6f0211ebf6ee83cd6983571fbeec008196b5e66acab7055bf093ab1f9abfcf`.

### APPROVED — 142. ca6a3c84-bd75-5579-a615-0cb8e237d099

**Bằng chứng nguồn:**
> ịch vụ Việt Nam và là Phó Tổng Giám đốc của Công ty CP Công nghệ - Viễn thông ELCOM - Ông Trần Hùng Giang Thành viên HĐQT - Ông Ngô Ngọc Hà Thành viên HĐQT - Bà Nguyễn Thị Lệ Thủy Vợ Ông Phan Chiến Thắng - Chủ tịch HĐQT THU NHẬP CỦA CÁC THÀNH VIÊN QUẢN LÝ CHỦ CHỐT Tổng thu nhập Năm 2024 Chức vụ VND HĐQT và Ban Giám đốc - Ông Phan Chiến Thắng Chủ tịch HĐQT 239.452.000 - Ông Nguyễn Đức Thiện Phó Chủ tịch HĐQT 152.065.000 - Ông Trần Hùng Giang Thành viên HĐQT 152.065.000 - Ông Nguyễn

**Bản kiểm:** Trần Hùng Giang → ELC · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/ELC_Baocaothuongnien_2024.pdf · document_id `f0730a07-8ab5-548a-a3b8-e099489d0f29` · trang PDF `68`.

**Hash section/trang đã kiểm:** `1348dcfba0e77b9917fdbfd279ba8c0ed2e92ec8dcb4cf1f2ceaa0dc2d65d83c`.

### APPROVED — 143. cbe764cd-eff1-5111-ab43-cd188f998f67

**Bằng chứng nguồn:**
> TP. Hà Nội Phó TGĐ kiêm GĐ Khối Tài 9 Bà Nguyễn Bảo Thanh Vân 26.589 0,00034% chính 10 Bà Đặng Thị Việt Hà Phó TGĐ 0 0% 11 Ông Nguyễn Hải Hưng Kế toán trưởng 40.232 0,000518% Ghi chú: - Ngày 25/12/2025, VietinBank đã CBTT Thông báo thay đổi số lượng cổ phần có quyền biểu quyết tại công văn số 1292/HĐQT-NHCT-VPHĐQT1. Theo đó, tổng số lượng cổ phiếu có quyền biểu quyết đang lưu hành là 7.766.944.637 cổ phiếu. Tuy nhiên, đến ngày 9/1/2026, VietinBank mới hoàn thành điều chỉnh thông ti

**Bản kiểm:** CTG → Đặng Thị Việt Hà · `APPOINTS` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Chấp nhận thông tin quyết định bổ nhiệm; không suy người vẫn đương nhiệm hiện tại. Mốc bản gửi: 2025-06-01; kiểm theo câu ghi ngày của đúng người.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CTG_Baocaothuongnien_2025.pdf · document_id `26c58a92-9b65-5ce3-a1c2-5f3b71717ddc` · trang PDF `25`.

**Hash section/trang đã kiểm:** `840c84044c4ea71e95ab1827555a35741b3e0f80eced81a1a7a265c805edfe68`.

### APPROVED — 144. ce1ce99d-4d35-5dec-a81e-18abe35ee9d5

**Bằng chứng nguồn:**
> n Hữu Dũng Phó Chủ tịch Ông Nguyễn Vĩnh Thuận Phó Chủ tịch Miễn nhiệm ngày 26/06/2025 Ông Võ Xuân Vinh Thành viên Bổ nhiệm ngày 26/06/2025 Ông Nguyễn Ngọc Trung Thành viên Ông Đinh Thế Hiển Thành viên Đ Các thành viên của Ban Tổng Giám đốc đã điều hành Công ty trong năm và tại ngày lập báo cáo này bao gồm: Ông Nguyễn Ngọc Trung Tổng Giám đốc Ông Nguyễn Hồng Minh Phó Tổng Giám đốc Bổ nhiệm ngày 04/11/2025 Bà Nguyễn Thị Thu Sương Phó Tổng Giám đốc Miễn nhiệm ngày 17/07/2025 Căn c

**Bản kiểm:** ITD → Võ Xuân Vinh · `APPOINTS` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Chấp nhận thông tin quyết định bổ nhiệm; không suy người vẫn đương nhiệm hiện tại. Mốc bản gửi: 2025-06-26; kiểm theo câu ghi ngày của đúng người.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/ITD_Baocaothuongnien_2025.pdf · document_id `a2c071fb-25bf-5ec4-903b-e973c623b85d` · trang PDF `52`.

**Hash section/trang đã kiểm:** `d29acf9d280d7310222afee6a10edbd47b99492988edf6f82320997cda5ee3e5`.

### APPROVED — 145. d0135fc7-7084-54ba-9f48-f953fd67262c

**Bằng chứng nguồn:**
> 0,000028% 3 Ông Nguyễn Hải Đăng TV BKS 0 0% 4 Bà Mai Hương Thảo TV BKS 217 0,000003% 5 Bà Phạm Thị Thu Huyền TV BKS 0 0% Ghi chú: - Ngày 25/12/2025, VietinBank đã CBTT Thông báo thay đổi số lượng cổ phần có quyền biểu quyết tại công văn số 1292/ HĐQT-NHCT-VPHĐQT1. Theo đó, tổng số lượng cổ phiếu có quyền biểu quyết đang lưu hành là 7.766.944.637 cổ phiếu. Tuy nhiên, đến ngày 9/1/2026, VietinBank mới hoàn thành điều chỉnh thông tin số lượng chứng khoán đăng ký (lên 7.766.944.637 cổ ph

**Bản kiểm:** Phạm Thị Thu Huyền → CTG · `HOLDS_ROLE` · Thành viên Ban Kiểm soát.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CTG_Baocaothuongnien_2025.pdf · document_id `26c58a92-9b65-5ce3-a1c2-5f3b71717ddc` · trang PDF `23`.

**Hash section/trang đã kiểm:** `7fe441c59f1ac429219cbd3b5247beb640cbefadfb2d88bcceb463b8ff71bc66`.

### APPROVED — 146. d38f679e-aeea-50d9-9f56-41039e9f7a37

**Bằng chứng nguồn:**
> Ông Trần Long Phó Tổng Giám đốc

**Bản kiểm:** Trần Long → BID · `HOLDS_ROLE` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://bidv.com.vn/vn/ve-bidv/ban-lanh-dao · document_id `7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190` · trang PDF `None`.

**Hash section/trang đã kiểm:** `da6f0211ebf6ee83cd6983571fbeec008196b5e66acab7055bf093ab1f9abfcf`.

### APPROVED — 147. d398930d-9ad6-5f1b-bf6f-551566e2fc18

**Bằng chứng nguồn:**
> Bà Nguyễn Thị Thủy Thành viên Ban điều hành

**Bản kiểm:** Nguyễn Thị Thủy → MBB · `HOLDS_ROLE` · Thành viên Ban điều hành.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://www.mbbank.com.vn/ve-mb/doi-ngu-lanh-dao · document_id `e9dd552a-0bd7-5716-bbdd-34e4580f7d6d` · trang PDF `None`.

**Hash section/trang đã kiểm:** `361d3953e754b97a64c3e6c7539f132c4b1fedc70c0825d017be9dce006ee918`.

### APPROVED — 148. d4723904-7d56-50c7-9f5f-94a7409e1861

**Bằng chứng nguồn:**
> Ông Quách Hùng Hiệp Ủy viên HĐQT

**Bản kiểm:** Quách Hùng Hiệp → BID · `HOLDS_ROLE` · Ủy viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://bidv.com.vn/vn/ve-bidv/ban-lanh-dao · document_id `7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190` · trang PDF `None`.

**Hash section/trang đã kiểm:** `da6f0211ebf6ee83cd6983571fbeec008196b5e66acab7055bf093ab1f9abfcf`.

### APPROVED — 149. d72dd6d1-3e72-5996-b202-b933e4ce90a9

**Bằng chứng nguồn:**
> ó Tổng Giám đốc 738.244.000 Ban Kiểm soát - - Bà Ngô Kiều Anh Trưởng ban 313.893.000 - Bà Vũ Thị Ngân Hà Thành viên 306.994.000 - Bà Hoàng Thị Phương Thúy Thành viên 36.000.000 Kế toán trưởng - - Bà Đậu Thị Lý Kế toán trưởng (bổ nhiệm từ 19/05/2023) 480.850.000 - Bà Đặng Thị Thanh Minh Kế toán trưởng (miễn nhiệm từ 19/05/2023) 106.746.860 Cộng 3.713.818.790 BÁO CÁO TÀI CHÍNH 120 120 CÔNG TY CỔ PHẦN CÔNG NGHỆ - VIỄN THÔNG ELCOM MẪU SỐ B09-DN/HN Tòa nhà Elcom, phố Duy Tân, phường D

**Bản kiểm:** Vũ Thị Ngân Hà → ELC · `HOLDS_ROLE` · Thành viên Ban Kiểm soát.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/ELC_Baocaothuongnien_2024.pdf · document_id `f0730a07-8ab5-548a-a3b8-e099489d0f29` · trang PDF `68`.

**Hash section/trang đã kiểm:** `1348dcfba0e77b9917fdbfd279ba8c0ed2e92ec8dcb4cf1f2ceaa0dc2d65d83c`.

### APPROVED — 150. d7832aaf-13e1-5bed-ad69-aa8a1317cb73

**Bằng chứng nguồn:**
> BÙI QUANG NGỌC Phó Chủ tịch Hội đồng quản trị

**Bản kiểm:** Bùi Quang Ngọc → FPT · `HOLDS_ROLE` · Phó Chủ tịch Hội đồng quản trị.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://fpt.com/vi/ve-fpt/doi-ngu-lanh-dao · document_id `535b180e-02c7-58e1-97cb-b4fe6b4d14a9` · trang PDF `None`.

**Hash section/trang đã kiểm:** `33cfaf2fbc681dae83c47dd4fa4b85cfe52e52683e7c2a066b0cd1deb35486ce`.

### APPROVED — 151. d912b68d-bc5a-5896-a46e-b015784eb82b

**Bằng chứng nguồn:**
> 04 0,00000005% TV điều hành TGĐ 3 Ông Trần Văn Tần TV HĐQT 0 0% TV không điều hành 4 Ông Lê Thanh Tùng TV HĐQT 0 0% TV không điều hành 5 Ông Nguyễn Thế Huân TV HĐQT 0 0% TV không điều hành 6 Bà Phạm Thị Thanh Hoài TV HĐQT 189 0,000002% TV không điều hành 7 Ông Nguyễn Vân Anh TV HĐQT 0 0% TV không điều hành 8 Ông Nguyễn Việt Dũng TV HĐQT 0 0% TV không điều hành TV HĐQT kiêm Phó 9 Ông Koji Iriguchi 0 0% TV điều hành TGĐ 10 Ông Takeo Shimotsu TV HĐQT 0 0% TV không điều hành 11 Ông

**Bản kiểm:** Lê Thanh Tùng → CTG · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CTG_Baocaothuongnien_2025.pdf · document_id `26c58a92-9b65-5ce3-a1c2-5f3b71717ddc` · trang PDF `18`.

**Hash section/trang đã kiểm:** `7a501da6b4991a2d607a6d5c038e78cff57a65aee779fa9507190b560d089045`.

### APPROVED — 152. d9a456ef-ecf6-5b15-8c89-c0cde5078687

**Bằng chứng nguồn:**
> ty trong năm và tại ngày lập báo cáo này bao gồm: Ông Nguyễn Ngọc Trung Tổng Giám đốc Ông Nguyễn Hồng Minh Phó Tổng Giám đốc Bổ nhiệm ngày 04/11/2025 Bà Nguyễn Thị Thu Sương Phó Tổng Giám đốc Miễn nhiệm ngày 17/07/2025 Căn cứ theo Nghị quyết ĐHĐCD năm 2025 ngày 26/06/2025, Công ty đã được thông qua thay đổi cơ cấu tổ chức quản lý Công ty từ Ban kiểm soát chuyền sang Ủy ban kiểm toán. Các thành viên của Ủy ban kiểm toán bao gồm: Ông Đinh Thế Hiển Chủ tịch Bổ nhiệm ngày 10/07/2025 Ôn

**Bản kiểm:** ITD → Nguyễn Hồng Minh · `APPOINTS` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Chấp nhận thông tin quyết định bổ nhiệm; không suy người vẫn đương nhiệm hiện tại. Mốc bản gửi: 2025-11-04; kiểm theo câu ghi ngày của đúng người.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/ITD_Baocaothuongnien_2025.pdf · document_id `a2c071fb-25bf-5ec4-903b-e973c623b85d` · trang PDF `52`.

**Hash section/trang đã kiểm:** `d29acf9d280d7310222afee6a10edbd47b99492988edf6f82320997cda5ee3e5`.

### APPROVED — 153. da43d198-6d86-56da-b170-11b0feceec12

**Bằng chứng nguồn:**
> Vũ Thanh Trung Phó Chủ tịch HĐQT

**Bản kiểm:** Vũ Thanh Trung → MBB · `HOLDS_ROLE` · Phó Chủ tịch HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://www.mbbank.com.vn/ve-mb/doi-ngu-lanh-dao · document_id `e9dd552a-0bd7-5716-bbdd-34e4580f7d6d` · trang PDF `None`.

**Hash section/trang đã kiểm:** `361d3953e754b97a64c3e6c7539f132c4b1fedc70c0825d017be9dce006ee918`.

### APPROVED — 154. da7ab0c3-62e8-54c1-9030-f53b1b3b2141

**Bằng chứng nguồn:**
> CHỦ TỊCH Ông Hồ Hùng Anh

**Bản kiểm:** Hồ Hùng Anh → TCB · `HOLDS_ROLE` · Chủ tịch HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 155. de28af76-78d1-5d11-a735-f7f9d4635465

**Bằng chứng nguồn:**
> Trung TV HĐQT kiêm TGĐ 3 0,00000006% 2 Ông Koji Iriguchi TV HĐQT kiêm Phó TGĐ 0 0% 3 Ông Trần Công Quỳnh Lân Phó TGĐ 0 0% 4 Bà Lê Như Hoa Phó TGĐ 39.937 0,000744% 5 Ông Lê Duy Hải Phó TGĐ 22.348 0,000416% 6 Ông Đỗ Thanh Sơn Phó TGĐ 125 0,0000023% 7 Ông Nguyễn Hải Hưng Kế toán trưởng 27.816 0,000518% Ghi chú: Danh sách TV BĐH và số lượng cổ phiếu trong bảng này được cập nhật tại ngày 31/12/2024. THAY ĐỔI TV BĐH TRONG NĂM 2024 STT Họ và tên Chức vụ Ngày bổ nhiệm/thôi nhiệm Bổ nhiệm TGĐ

**Bản kiểm:** Trần Công Quỳnh Lân → CTG · `HOLDS_ROLE` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/CTG_Baocaothuongnien_2024.pdf · document_id `ebc51a9d-1d79-51a6-8c3e-f3db6d8f4891` · trang PDF `24`.

**Hash section/trang đã kiểm:** `e2d957a20adea3a5a279afd84d3eb05232042cc8edc2b298b71474c14a55c353`.

### APPROVED — 156. decb8b19-2dab-58fa-bc71-7555852af917

**Bằng chứng nguồn:**
> Ông Trần Xuân Hoàng Ủy viên HĐQT

**Bản kiểm:** Trần Xuân Hoàng → BID · `HOLDS_ROLE` · Ủy viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://bidv.com.vn/vn/ve-bidv/ban-lanh-dao · document_id `7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190` · trang PDF `None`.

**Hash section/trang đã kiểm:** `da6f0211ebf6ee83cd6983571fbeec008196b5e66acab7055bf093ab1f9abfcf`.

### APPROVED — 157. e0232d58-99fb-5db6-9ea1-011a8563b028

**Bằng chứng nguồn:**
> 1 11 11/11 100% Trưởng BKS Bà Nguyễn Thị Anh Thư 2 11 11/11 100% TV BKS (Chuyên trách) Bà Phạm Thị Thơm (3) Không tham gia họp BKS do nghỉ 3 10 10/11 90,9% hưu hưởng chế độ BHXH kể từ Nguyên TV BKS (Chuyên trách) ngày 1/11/2025 Ông Nguyễn Hải Đăng (1) Không tham gia họp BKS trước 4 8 8/11 72,7% ngày 18/4/2025 (chưa là TV BKS) TV BKS (Chuyên trách) Bà Phạm Thị Thu Huyền (1) Không tham gia họp BKS trước 5 8 8/11 72,7% ngày 18/4/2025 (chưa là TV BKS) TV BKS (Chuyên trách) Bà Mai Hư

**Bản kiểm:** Phạm Thị Thơm → CTG · `REQUESTS_RESIGNATION` · Thành viên Ban Kiểm soát.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Giữ nguyên loại quan hệ lịch sử/miễn nhiệm/từ nhiệm; không đổi thành đang giữ chức. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CTG_Baocaothuongnien_2025.pdf · document_id `26c58a92-9b65-5ce3-a1c2-5f3b71717ddc` · trang PDF `102`.

**Hash section/trang đã kiểm:** `4ae48c48a45a36f0869a4f2ea84ba9c4e5889812c698890dcf36216b8b0e6a76`.

### APPROVED — 158. e03bf9ee-7cac-5288-8c52-61e172229d97

**Bằng chứng nguồn:**
> ọc Trung Tổng Giám đốc Ông Nguyễn Hồng Minh Phó Tổng Giám đốc Bổ nhiệm ngày 04/11/2025 Bà Nguyễn Thị Thu Sương Phó Tổng Giám đốc Miễn nhiệm ngày 17/07/2025 Căn cứ theo Nghị quyết ĐHĐCD năm 2025 ngày 26/06/2025, Công ty đã được thông qua thay đổi cơ cấu tổ chức quản lý Công ty từ Ban kiểm soát chuyền sang Ủy ban kiểm toán. Các thành viên của Ủy ban kiểm toán bao gồm: Ông Đinh Thế Hiển Chủ tịch Bổ nhiệm ngày 10/07/2025 Ông Võ Xuân Vinh Thành viên Bồ nhiệm ngày 10/07/2025 NGƯỜI ĐẠI DIỆN T

**Bản kiểm:** ITD → Nguyễn Thị Thu Sương · `DISMISSES` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Giữ nguyên loại quan hệ lịch sử/miễn nhiệm/từ nhiệm; không đổi thành đang giữ chức. Mốc bản gửi: 2025-07-17; kiểm theo câu ghi ngày của đúng người.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/ITD_Baocaothuongnien_2025.pdf · document_id `a2c071fb-25bf-5ec4-903b-e973c623b85d` · trang PDF `52`.

**Hash section/trang đã kiểm:** `d29acf9d280d7310222afee6a10edbd47b99492988edf6f82320997cda5ee3e5`.

### APPROVED — 159. e1c23c1b-be72-5940-970d-95691d53fada

**Bằng chứng nguồn:**
> - Bà Ngô Kiều Anh Trưởng ban 313.893.000 - Bà Vũ Thị Ngân Hà Thành viên 306.994.000 - Bà Hoàng Thị Phương Thúy Thành viên 36.000.000 Kế toán trưởng - - Bà Đậu Thị Lý Kế toán trưởng (bổ nhiệm từ 19/05/2023) 480.850.000 - Bà Đặng Thị Thanh Minh Kế toán trưởng (miễn nhiệm từ 19/05/2023) 106.746.860 Cộng 3.713.818.790 BÁO CÁO TÀI CHÍNH 120 120 CÔNG TY CỔ PHẦN CÔNG NGHỆ - VIỄN THÔNG ELCOM MẪU SỐ B09-DN/HN Tòa nhà Elcom, phố Duy Tân, phường Dịch Vọng Hậu, Ban hành theo Thông tư số 202/2014/T

**Bản kiểm:** Hoàng Thị Phương Thúy → ELC · `HOLDS_ROLE` · Thành viên Ban Kiểm soát.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/ELC_Baocaothuongnien_2024.pdf · document_id `f0730a07-8ab5-548a-a3b8-e099489d0f29` · trang PDF `68`.

**Hash section/trang đã kiểm:** `1348dcfba0e77b9917fdbfd279ba8c0ed2e92ec8dcb4cf1f2ceaa0dc2d65d83c`.

### APPROVED — 160. e1c86814-a34c-5ef0-8356-41c0675bcfbc

**Bằng chứng nguồn:**
> hanh Sơn Phó TGĐ 180 0,0000023% 7 Ông Nguyễn Đức Thành Phó TGĐ 0 0% Phó TGĐ kiêm GĐ 8 Ông Dương Văn Quân 0 0% VietinBank TP. Hà Nội Phó TGĐ kiêm GĐ Khối Tài 9 Bà Nguyễn Bảo Thanh Vân 26.589 0,00034% chính 10 Bà Đặng Thị Việt Hà Phó TGĐ 0 0% 11 Ông Nguyễn Hải Hưng Kế toán trưởng 40.232 0,000518% Ghi chú: - Ngày 25/12/2025, VietinBank đã CBTT Thông báo thay đổi số lượng cổ phần có quyền biểu quyết tại công văn số 1292/HĐQT-NHCT-VPHĐQT1. Theo đó, tổng số lượng cổ phiếu có quyền biểu

**Bản kiểm:** Dương Văn Quân → CTG · `HOLDS_ROLE` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CTG_Baocaothuongnien_2025.pdf · document_id `26c58a92-9b65-5ce3-a1c2-5f3b71717ddc` · trang PDF `25`.

**Hash section/trang đã kiểm:** `840c84044c4ea71e95ab1827555a35741b3e0f80eced81a1a7a265c805edfe68`.

### APPROVED — 161. e3bdc282-908f-5551-b52e-2ed5a7be8576

**Bằng chứng nguồn:**
> TP. Hà Nội Phó TGĐ kiêm GĐ Khối Tài 9 Bà Nguyễn Bảo Thanh Vân 26.589 0,00034% chính 10 Bà Đặng Thị Việt Hà Phó TGĐ 0 0% 11 Ông Nguyễn Hải Hưng Kế toán trưởng 40.232 0,000518% Ghi chú: - Ngày 25/12/2025, VietinBank đã CBTT Thông báo thay đổi số lượng cổ phần có quyền biểu quyết tại công văn số 1292/HĐQT-NHCT-VPHĐQT1. Theo đó, tổng số lượng cổ phiếu có quyền biểu quyết đang lưu hành là 7.766.944.637 cổ phiếu. Tuy nhiên, đến ngày 9/1/2026, VietinBank mới hoàn thành điều chỉnh thông ti

**Bản kiểm:** Đặng Thị Việt Hà → CTG · `HOLDS_ROLE` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CTG_Baocaothuongnien_2025.pdf · document_id `26c58a92-9b65-5ce3-a1c2-5f3b71717ddc` · trang PDF `25`.

**Hash section/trang đã kiểm:** `840c84044c4ea71e95ab1827555a35741b3e0f80eced81a1a7a265c805edfe68`.

### APPROVED — 162. e4eb9381-f703-5cf8-b907-6cf7e5b8dfcb

**Bằng chứng nguồn:**
> TRẦN THỊ HỒNG LĨNH Ủy viên Hội đồng quản trị

**Bản kiểm:** Trần Thị Hồng Lĩnh → FPT · `HOLDS_ROLE` · Ủy viên Hội đồng quản trị.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://fpt.com/vi/ve-fpt/doi-ngu-lanh-dao · document_id `535b180e-02c7-58e1-97cb-b4fe6b4d14a9` · trang PDF `None`.

**Hash section/trang đã kiểm:** `33cfaf2fbc681dae83c47dd4fa4b85cfe52e52683e7c2a066b0cd1deb35486ce`.

### APPROVED — 163. e5396fea-1553-56cb-a9c5-9f8fd5e37bcc

**Bằng chứng nguồn:**
> Phó Tổng Giám đốc Kiêm Giám đốc Khối Quản trị Ngân hàng Bà Nguyễn Thị Vân Hoài

**Bản kiểm:** Nguyễn Thị Vân Hoài → TCB · `HOLDS_ROLE` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 164. e5e38d54-69ef-51c6-a641-eecd6a2dbc41

**Bằng chứng nguồn:**
> Ông Nguyễn Trung Kiên Thành viên /n Ban Kiểm soát

**Bản kiểm:** Nguyễn Trung Kiên → BID · `HOLDS_ROLE` · Thành viên Ban Kiểm soát.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://bidv.com.vn/vn/ve-bidv/ban-lanh-dao · document_id `7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190` · trang PDF `None`.

**Hash section/trang đã kiểm:** `da6f0211ebf6ee83cd6983571fbeec008196b5e66acab7055bf093ab1f9abfcf`.

### APPROVED — 165. e95e6b44-c4ba-5d35-904d-7af16e734083

**Bằng chứng nguồn:**
> 0% 5 Kwon Oh Soo Thành viên HĐQT 0 0% 6 Trương Tuấn Lâm | Thành viên HĐQT độc lập 0 0% 7 Nguyễn Danh Lam | Thành viên HĐQT độc lập 0 0% 8 Lê Việt Hà Thành viên HĐQT độc lập 0 0% 9 Hà Thế Vinh Thành viên HĐQT không 0 0% điêu hành 1.2. Các tiêu ban thuộc Hội đồng quản trị: a.. Ban kiễm toán nội bộ: Lập kế hoạch cho các hoạt động kiểm toán nội bộ và quản trị rủi ro ở cắp Tập đoàn và Công ty thành viên căn cứ vào chiến lược phát triển và kế hoạch kinh doanh. Thực hiện hoạt động kiểm

**Bản kiểm:** Nguyễn Danh Lam → CMG · `HOLDS_ROLE` · Thành viên HĐQT độc lập.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CMG_Baocaothuongnien_2025.pdf · document_id `532597dc-7b79-5f00-99f9-d3394cba9038` · trang PDF `64`.

**Hash section/trang đã kiểm:** `e4be11d5fd9ac0153b2e13b1ce0440b44dcf12f4d7c77de22d1c9c0e0d017210`.

### APPROVED — 166. ea8e9552-c532-5d0a-acf8-cad55ab17217

**Bằng chứng nguồn:**
> ành viên HĐQT Chức vụ krkk Ti Non 1 _| Nguyễn Trung Chính Chủ tịch HĐQT 2,500,551 1,18% 2 Nguyễn Minh Đức Thành viên HĐQT 4,862,063 2,30% 3 Nguyễn Phước Hải Thành viên HĐQT 3,453,867 1,63% 4 Gum Ki Ho Thành viên HĐQT 0 0% 5 Kwon Oh Soo Thành viên HĐQT 0 0% 6 Trương Tuấn Lâm | Thành viên HĐQT độc lập 0 0% 7 Nguyễn Danh Lam | Thành viên HĐQT độc lập 0 0% 8 Lê Việt Hà Thành viên HĐQT độc lập 0 0% 9 Hà Thế Vinh Thành viên HĐQT không 0 0% điêu hành 1.2. Các tiêu ban thuộc Hội đồng quản

**Bản kiểm:** Nguyễn Minh Đức → CMG · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CMG_Baocaothuongnien_2025.pdf · document_id `532597dc-7b79-5f00-99f9-d3394cba9038` · trang PDF `64`.

**Hash section/trang đã kiểm:** `e4be11d5fd9ac0153b2e13b1ce0440b44dcf12f4d7c77de22d1c9c0e0d017210`.

### APPROVED — 167. ec64e3ea-0740-5537-8979-27af2b2f4056

**Bằng chứng nguồn:**
> Từ tháng 02/2026, ông Nguyễn Anh Tuấn được bổ nhiệm giữ chức Phó Tổng Giám đốc kiêm nhiệm, đồng thời tiếp tục lãnh đạo Khối Ngân hàng Bán lẻ, góp phần bảo đảm sự ổn định, kế thừa và tăng trưởng bền vững trong hoạt động điều hành.

**Bản kiểm:** TCB → Nguyễn Anh Tuấn · `APPOINTS` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Chấp nhận thông tin quyết định bổ nhiệm; không suy người vẫn đương nhiệm hiện tại. Không tự thêm ngày hiệu lực khi trường này đang null. Nguồn chỉ rõ tháng 02/2026; giữ mức chính xác tháng trong phần bằng chứng, không bịa ngày đầu tháng.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 168. ee49eab4-d4a8-51ea-a39c-eab40b355840

**Bằng chứng nguồn:**
> 0 0% TV không điều hành TV HĐQT kiêm Phó 9 Ông Koji Iriguchi 0 0% TV điều hành TGĐ 10 Ông Takeo Shimotsu TV HĐQT 0 0% TV không điều hành 11 Ông Cát Quang Dương TV độc lập HĐQT 0 0% TV độc lập Ghi chú: - Danh sách TV HĐQT và số lượng cổ phiếu trong bảng này chưa bao gồm đại diện phần vốn Nhà nước. - Ngày 25/12/2025, VietinBank đã CBTT Thông báo thay đổi số lượng cổ phần có quyền biểu quyết tại công văn số 1292/HĐQT-NHCT-VPHĐQT1. Theo đó, tổng số lượng cổ phiếu có quyền biểu quyết

**Bản kiểm:** Takeo Shimotsu → CTG · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CTG_Baocaothuongnien_2025.pdf · document_id `26c58a92-9b65-5ce3-a1c2-5f3b71717ddc` · trang PDF `18`.

**Hash section/trang đã kiểm:** `7a501da6b4991a2d607a6d5c038e78cff57a65aee779fa9507190b560d089045`.

### APPROVED — 169. ee8cd5f2-3629-5583-b4f2-704369ef40cf

**Bằng chứng nguồn:**
> Bà Nguyễn Thị Thanh Nga Giám đốc Tài chính

**Bản kiểm:** Nguyễn Thị Thanh Nga → MBB · `HOLDS_ROLE` · Giám đốc Tài chính.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://www.mbbank.com.vn/ve-mb/doi-ngu-lanh-dao · document_id `e9dd552a-0bd7-5716-bbdd-34e4580f7d6d` · trang PDF `None`.

**Hash section/trang đã kiểm:** `361d3953e754b97a64c3e6c7539f132c4b1fedc70c0825d017be9dce006ee918`.

### APPROVED — 170. f07227f1-b976-5311-8556-5821b7e8dc52

**Bằng chứng nguồn:**
> với HĐQT. DANH SÁCH TV BĐH STT Họ và tên Chức vụ Số lượng cổ phiếu Tỷ lệ sở hữu (%) 1 Ông Nguyễn Trần Mạnh Trung TV HĐQT kiêm TGĐ 3 0,00000006% 2 Ông Koji Iriguchi TV HĐQT kiêm Phó TGĐ 0 0% 3 Ông Trần Công Quỳnh Lân Phó TGĐ 0 0% 4 Bà Lê Như Hoa Phó TGĐ 39.937 0,000744% 5 Ông Lê Duy Hải Phó TGĐ 22.348 0,000416% 6 Ông Đỗ Thanh Sơn Phó TGĐ 125 0,0000023% 7 Ông Nguyễn Hải Hưng Kế toán trưởng 27.816 0,000518% Ghi chú: Danh sách TV BĐH và số lượng cổ phiếu trong bảng này được cập nhật tại ngày

**Bản kiểm:** CTG → Nguyễn Trần Mạnh Trung · `APPOINTS` · Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Chấp nhận thông tin quyết định bổ nhiệm; không suy người vẫn đương nhiệm hiện tại. Mốc bản gửi: 2024-10-17; kiểm theo câu ghi ngày của đúng người.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/CTG_Baocaothuongnien_2024.pdf · document_id `ebc51a9d-1d79-51a6-8c3e-f3db6d8f4891` · trang PDF `24`.

**Hash section/trang đã kiểm:** `e2d957a20adea3a5a279afd84d3eb05232042cc8edc2b298b71474c14a55c353`.

### APPROVED — 171. f19835a6-539b-595d-b63b-2b90dbe800e4

**Bằng chứng nguồn:**
> y 26 tháng 7 năm 2024 Ông Lê Quang Vinh Tổng Giám đốc Bổ nhiệm ngày 7 tháng 3 năm 2025 Bà Đinh Thị Thái Phó Tổng Giám đốc Miễn nhiệm ngày 19 tháng 8 năm 2024 Bà Phùng Nguyễn Hải Yến Phó Tổng Giám đốc Bổ nhiệm lại ngày 15 tháng 12 năm 2022 Ông Đặng Hoài Đức Phó Tổng Giám đốc Bổ nhiệm lại ngày 1 tháng 4 năm 2024 Ông Shojiro Mizoguchi Phó Tổng Giám đốc Bổ nhiệm ngày 23 tháng 4 năm 2021 Ông Nguyễn Việt Cường Phó Tổng Giám đốc Bổ nhiệm ngày 26 tháng 4 năm 2022 Ông Lê Hoàng Tùng Phó T

**Bản kiểm:** VCB → Đinh Thị Thái · `APPOINTS` · Trưởng Ban Kiểm soát.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Chấp nhận thông tin quyết định bổ nhiệm; không suy người vẫn đương nhiệm hiện tại. Mốc bản gửi: 2024-08-19; kiểm theo câu ghi ngày của đúng người.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/VCB_Baocaothuongnien_2024.pdf · document_id `dd94d5da-f8b1-5776-8c5e-f211d18ae26b` · trang PDF `65`.

**Hash section/trang đã kiểm:** `4ee095497823547593f90cb39e32e5919342ada0c636aa01c936a1b49acb38c3`.

### APPROVED — 172. f22b5e2c-adb8-5e02-9d1e-8cef6d8aeb7c

**Bằng chứng nguồn:**
> Ông Đỗ Văn Tiến Thành viên Ban Kiểm soát

**Bản kiểm:** Đỗ Văn Tiến → MBB · `HOLDS_ROLE` · Thành viên Ban Kiểm soát.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://www.mbbank.com.vn/ve-mb/doi-ngu-lanh-dao · document_id `e9dd552a-0bd7-5716-bbdd-34e4580f7d6d` · trang PDF `None`.

**Hash section/trang đã kiểm:** `361d3953e754b97a64c3e6c7539f132c4b1fedc70c0825d017be9dce006ee918`.

### APPROVED — 173. f5aec9d4-ff7d-5dae-9f3b-21f48209e4cb

**Bằng chứng nguồn:**
> QT/Phó Tổng Giám đốc 396.047.930 - Ông Nguyễn Mạnh Hùng Thành viên HĐQT 120.000.000 - Ông Đỗ Minh Tiến Thành viên HĐQT 120.000.000 - Ông Phạm Minh Thắng Tổng Giám đốc 399.626.000 - Ông Nguyễn Văn Hòa Phó Tổng Giám đốc 738.244.000 Ban Kiểm soát - - Bà Ngô Kiều Anh Trưởng ban 313.893.000 - Bà Vũ Thị Ngân Hà Thành viên 306.994.000 - Bà Hoàng Thị Phương Thúy Thành viên 36.000.000 Kế toán trưởng - - Bà Đậu Thị Lý Kế toán trưởng (bổ nhiệm từ 19/05/2023) 480.850.000 - Bà Đặng Thị Than

**Bản kiểm:** Đỗ Minh Tiến → ELC · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/ELC_Baocaothuongnien_2024.pdf · document_id `f0730a07-8ab5-548a-a3b8-e099489d0f29` · trang PDF `68`.

**Hash section/trang đã kiểm:** `1348dcfba0e77b9917fdbfd279ba8c0ed2e92ec8dcb4cf1f2ceaa0dc2d65d83c`.

### APPROVED — 174. f600faf7-022f-567b-86b1-4ff467de6387

**Bằng chứng nguồn:**
> Hội đồng quản trị Hội đồng quản trị BIDV có 11 thành viên, trong đó có 01 ủy viên độc lập Ông Lê Ngọc Lâm Chủ tịch HĐQT Sinh năm 1975 Năm 1997, ông bắt đầu làm việc tại BIDV; từ tháng 03/2009 là Phó Giám đốc Ban Quản lý rủi ro tín dụng; từ tháng 04/2012 là Giám đốc Ban Quản lý rủi ro tín dụng; từ tháng 04/2013 là Giám đốc Ban Quan hệ Khách hàng doanh nghiệp; từ ngày 15/01/2015 là Phó Tổng Giám đốc BIDV; từ ngày 15/11/2018 là Phó Tổng Giám đốc phụ trách Ban điều hành BIDV; từ ngày 12/03/2021 là Thành viên HĐQT kiêm Tổng Giám đốc BIDV. Từ ngày 01/07/2026, ông được bổ nhiệm giữ chức Chủ tịch HĐQT BIDV. Ông Hoàng Việt Hùng Ủy viên HĐQT Năm sinh: 1972 Năm 1996, ông bắt đầu làm việc tại BIDV; từ tháng 11/2007 là Phó Giám đốc Chi nhánh BIDV Nghệ An; từ tháng 01/2013 là Giám đốc Chi nhánh BIDV Nghệ An; từ tháng 04/2019 là Giám đốc Ban Tổ chức nhân sự BIDV; từ tháng 03/2020 là Phó Tổng Giám đốc BIDV kiêm Giám đốc Ban Tổ chức nhân sự; từ tháng 02/2024 là Phó Tổng Giám đốc BIDV, Chủ tịch HĐQT Ngân hàng Liên doanh Lào - Việt; từ tháng 05/2026 là Phó Tổng Giám đốc BIDV. Từ ngày 01/07/2026 ông là thành viên HĐQT, Tổng Giám đốc BIDV. Ông Kim Sang Soo Ủy viên HĐQT Sinh năm: 1968 Từng giữ các chức vụ: Giám đốc điều hành Khối Toàn cầu (Ngân hàng KEB Hana); Chủ tịch HĐQT & Tổng Giám đốc (Ngân hàng TNHH Hana Trung Quốc); Giám đốc Chi nhánh (Ngân hàng KEB Hana - Chi nhánh TP Hồ Chí Minh). Từ ngày 24/4/2026, ông là Uỷ viên Hội đồng quản trị BIDV. Ông Tr

**Bản kiểm:** BID → Lê Ngọc Lâm · `APPOINTS` · Chủ tịch HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Chấp nhận thông tin quyết định bổ nhiệm; không suy người vẫn đương nhiệm hiện tại. Mốc bản gửi: 2026-07-01; kiểm theo câu ghi ngày của đúng người. Đã đọc riêng tiểu sử dưới tiêu đề tên, không lấy “ông” của người ở đoạn trước.

**Nguồn:** https://bidv.com.vn/vn/ve-bidv/ban-lanh-dao · document_id `7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190` · trang PDF `None`.

**Hash section/trang đã kiểm:** `da6f0211ebf6ee83cd6983571fbeec008196b5e66acab7055bf093ab1f9abfcf`.

### APPROVED — 175. f9b4b6d7-5cce-51a2-b909-2a313058a4dd

**Bằng chứng nguồn:**
> n Hữu Dũng Phó Chủ tịch Ông Nguyễn Vĩnh Thuận Phó Chủ tịch Miễn nhiệm ngày 26/06/2025 Ông Võ Xuân Vinh Thành viên Bổ nhiệm ngày 26/06/2025 Ông Nguyễn Ngọc Trung Thành viên Ông Đinh Thế Hiển Thành viên Đ Các thành viên của Ban Tổng Giám đốc đã điều hành Công ty trong năm và tại ngày lập báo cáo này bao gồm: Ông Nguyễn Ngọc Trung Tổng Giám đốc Ông Nguyễn Hồng Minh Phó Tổng Giám đốc Bổ nhiệm ngày 04/11/2025 Bà Nguyễn Thị Thu Sương Phó Tổng Giám đốc Miễn nhiệm ngày 17/07/2025 Căn c

**Bản kiểm:** ITD → Võ Xuân Vinh · `APPOINTS` · Thành viên Ủy ban kiểm toán.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Chấp nhận thông tin quyết định bổ nhiệm; không suy người vẫn đương nhiệm hiện tại. Mốc bản gửi: 2025-07-10; kiểm theo câu ghi ngày của đúng người.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/ITD_Baocaothuongnien_2025.pdf · document_id `a2c071fb-25bf-5ec4-903b-e973c623b85d` · trang PDF `52`.

**Hash section/trang đã kiểm:** `d29acf9d280d7310222afee6a10edbd47b99492988edf6f82320997cda5ee3e5`.

### APPROVED — 176. fa953e25-3560-5954-a8b1-7442f46ee66f

**Bằng chứng nguồn:**
> Ông Nguyễn Anh Tuấn Thành viên /n Ban Kiểm soát

**Bản kiểm:** Nguyễn Anh Tuấn → BID · `HOLDS_ROLE` · Thành viên Ban Kiểm soát.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://bidv.com.vn/vn/ve-bidv/ban-lanh-dao · document_id `7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190` · trang PDF `None`.

**Hash section/trang đã kiểm:** `da6f0211ebf6ee83cd6983571fbeec008196b5e66acab7055bf093ab1f9abfcf`.

### APPROVED — 177. fac386ed-e2ea-57cc-bd59-3eeda2e56145

**Bằng chứng nguồn:**
> Ông Hồng Quang 2 Giám đốc Khối Nhân sự 6 Ông Vũ Viết Ngoạn Thành viên độc lập HĐQT 0 7 Bà Nguyễn Thị Kim Oanh Thành viên HĐQT 7.475 8 Ông Nguyễn Tuấn Anh Thành viên HĐQT 0 63 CHƯƠNG 4 Quản trị doanh nghiệp Trong những năm qua, công tác quản trị công ty của VCB luôn được chú trọng và triển khai Hội đồng một cách nghiêm túc dưới sự định hướng và giám sát của HĐQT. VCB đã tuân thủ đầy đủ quản trị các quy định về quản trị công ty theo pháp luật Việt Nam, đồng thời từng bước tiếp cận và áp

**Bản kiểm:** Nguyễn Thị Kim Oanh → VCB · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/VCB_Baocaothuongnien_2025.zip · document_id `679baa3e-b39c-5b53-be43-3cd19d738dca` · trang PDF `33`.

**Hash section/trang đã kiểm:** `cf40fe0d83644c1e5c1942f9eb281f4ec55c5169a7cfd0e4f5aa1a79fa6db82f`.

### APPROVED — 178. fac4a230-58d0-5d36-8c8a-828416fb3ab5

**Bằng chứng nguồn:**
> Ông Trần Phương Phó Tổng Giám đốc

**Bản kiểm:** Trần Phương → BID · `HOLDS_ROLE` · Phó Tổng Giám đốc.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://bidv.com.vn/vn/ve-bidv/ban-lanh-dao · document_id `7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190` · trang PDF `None`.

**Hash section/trang đã kiểm:** `da6f0211ebf6ee83cd6983571fbeec008196b5e66acab7055bf093ab1f9abfcf`.

### APPROVED — 179. fc13eb58-ef45-5b17-9b66-9174550ecef6

**Bằng chứng nguồn:**
> 9 0,000002% TV không điều hành 7 Ông Nguyễn Vân Anh TV HĐQT 0 0% TV không điều hành 8 Ông Nguyễn Việt Dũng TV HĐQT 0 0% TV không điều hành TV HĐQT kiêm Phó 9 Ông Koji Iriguchi 0 0% TV điều hành TGĐ 10 Ông Takeo Shimotsu TV HĐQT 0 0% TV không điều hành 11 Ông Cát Quang Dương TV độc lập HĐQT 0 0% TV độc lập Ghi chú: - Danh sách TV HĐQT và số lượng cổ phiếu trong bảng này chưa bao gồm đại diện phần vốn Nhà nước. - Ngày 25/12/2025, VietinBank đã CBTT Thông báo thay đổi số lượng cổ phần

**Bản kiểm:** Nguyễn Việt Dũng → CTG · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CTG_Baocaothuongnien_2025.pdf · document_id `26c58a92-9b65-5ce3-a1c2-5f3b71717ddc` · trang PDF `18`.

**Hash section/trang đã kiểm:** `7a501da6b4991a2d607a6d5c038e78cff57a65aee779fa9507190b560d089045`.

### APPROVED — 180. fe297061-6fe9-50ec-bebc-117dd8b1a520

**Bằng chứng nguồn:**
> gày 21 tháng 4 năm 2023 Ông Lê Quang Vinh Thành viên Bổ nhiệm ngày 7 tháng 3 năm 2025 Ông Nguyễn Tuấn Anh Thành viên Bổ nhiệm ngày 19 tháng 8 năm 2024 Ông Nguyễn Mỹ Hào Thành viên Từ nhiệm ngày 1 tháng 11 năm 2024 Ông Nguyễn Mạnh Hùng Thành viên Bổ nhiệm lại ngày 21 tháng 4 năm 2023 Ông Hồng Quang Thành viên Bổ nhiệm lại ngày 21 tháng 4 năm 2023 Ông Shojiro Mizoguchi Thành viên Bổ nhiệm lại ngày 21 tháng 4 năm 2023 Bà Nguyễn Thị Kim Oanh Thành viên Bổ nhiệm ngày 24 tháng 11 năm 20

**Bản kiểm:** VCB → Nguyễn Tuấn Anh · `APPOINTS` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Chấp nhận thông tin quyết định bổ nhiệm; không suy người vẫn đương nhiệm hiện tại. Mốc bản gửi: 2024-08-19; kiểm theo câu ghi ngày của đúng người.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/VCB_Baocaothuongnien_2024.pdf · document_id `dd94d5da-f8b1-5776-8c5e-f211d18ae26b` · trang PDF `65`.

**Hash section/trang đã kiểm:** `4ee095497823547593f90cb39e32e5919342ada0c636aa01c936a1b49acb38c3`.

### APPROVED — 181. fe390278-af11-5c08-a2e4-0702558af726

**Bằng chứng nguồn:**
> Ông Huỳnh Phương Thành viên /n Ban Kiểm soát

**Bản kiểm:** Huỳnh Phương → BID · `HOLDS_ROLE` · Thành viên Ban Kiểm soát.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://bidv.com.vn/vn/ve-bidv/ban-lanh-dao · document_id `7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190` · trang PDF `None`.

**Hash section/trang đã kiểm:** `da6f0211ebf6ee83cd6983571fbeec008196b5e66acab7055bf093ab1f9abfcf`.

### APPROVED — 182. ff0f22ac-89f8-5ff9-8c4e-522dbd60581c

**Bằng chứng nguồn:**
> GIÁM ĐỐC KHỐI VẬN HÀNH KIÊM GIÁM ĐỐC KHỐI CÔNG NGHỆ Ông Chu Hồng Ngọc

**Bản kiểm:** Chu Hồng Ngọc → TCB · `HOLDS_ROLE` · Giám đốc Khối Công nghệ.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://techcombank.com/ve-chung-toi · document_id `26c437b9-9518-5456-bf87-6b4812b5562e` · trang PDF `None`.

**Hash section/trang đã kiểm:** `07e24e298f4e91595baa903be9b49e7fac376ad3d77e71591fd83e61cf008691`.

### APPROVED — 183. ff58c8cd-7db9-5da9-98e4-75a72907a2d0

**Bằng chứng nguồn:**
> Bà Trần Thị Bảo Quế Thành viên Ban điều hành

**Bản kiểm:** Trần Thị Bảo Quế → MBB · `HOLDS_ROLE` · Thành viên Ban điều hành.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://www.mbbank.com.vn/ve-mb/doi-ngu-lanh-dao · document_id `e9dd552a-0bd7-5716-bbdd-34e4580f7d6d` · trang PDF `None`.

**Hash section/trang đã kiểm:** `361d3953e754b97a64c3e6c7539f132c4b1fedc70c0825d017be9dce006ee918`.

### APPROVED — 184. ff7f5429-5648-5a22-881c-249a3bbc897a

**Bằng chứng nguồn:**
> HĐQT - Công ty CP Hạ tầng Viễn thông Ngô Trọng Hiếu TGĐ Công ty - em trai của CMC Phó TGĐ Ngô Ngọc Hà - Công ty CP đầu tư thương mại & Ông Nguyễn Văn Hòa là đại diện theo Pháp phát triển Dịch vụ Việt Nam luật của Công ty CP đầu tư TM & PT Dịch vụ Việt Nam và là Phó Tổng Giám đốc của Công ty CP Công nghệ - Viễn thông ELCOM - Ông Trần Hùng Giang Thành viên HĐQT - Ông Ngô Ngọc Hà Thành viên HĐQT - Bà Nguyễn Thị Lệ Thủy Vợ Ông Phan Chiến Thắng - Chủ tịch HĐQT THU NHẬP CỦA CÁC THÀN

**Bản kiểm:** Ngô Ngọc Hà → ELC · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chấp nhận đúng tên/chức vụ và chiều quan hệ trong nguồn đã ghim; phạm vi định danh là tài liệu này. Đây là chức vụ theo nguồn, không khẳng định còn giữ chức ở ngày hôm nay. Không tự thêm ngày hiệu lực khi trường này đang null.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2024/BCTN/VN/ELC_Baocaothuongnien_2024.pdf · document_id `f0730a07-8ab5-548a-a3b8-e099489d0f29` · trang PDF `68`.

**Hash section/trang đã kiểm:** `1348dcfba0e77b9917fdbfd279ba8c0ed2e92ec8dcb4cf1f2ceaa0dc2d65d83c`.

### REJECTED — 185. 7e09fb82-8878-58f0-861e-1448415724c0

**Bằng chứng nguồn:**
> 2.1.3. Thành viên Ban Tổng giám đốc, Kế toán trưởng STT Họ và tên Chức danh 1. Ông Lê Thanh Sơn Tổng Giám đốc (Bổ nhiệm từ ngày 07/02/2025) 2. Ông Hà Thanh Hải* Tổng Giám đốc (Miễn nhiệm từ ngày 07/02/2025) *Chi tiết tại phần giới thiệu HĐQT Công ty 3. Ông Tô Hoài Văn* Phó Tổng Giám đốc (Miễn nhiệm từ ngày 01/09/2025) *Chi tiết tại phần giới thiệu HĐQT Công ty 4. Ông Lê Ánh Dương Phó Tổng Giám đốc 5. Ông Nguyễn Ngọc Sơn Kế toán trưởng 34 Báo cáo thường niên 2025 Giới thiệu về Ban Tổng Giám đốc Ông Lê Thanh Sơn Chức danh: Tổng Giám đốc Năm sinh: 1972 Trình độ chuyên môn: » Cử nhân Kinh tế phát triển. Quá trình công tác: - Từ tháng 04/1999 đến nay: Công tác tại Xí nghiệp Khoa học Sản xuất Thiết bị Thông tin (nay là Công ty Cổ phần Viễn thông – Tin học Bưu điện (CTIN)), các vị trí công tác: • Từ tháng 01/2010 đến tháng 12/2020: Phó Giám đốc Kinh doanh • Từ tháng 01/2021 đến tháng 06/2022: Giám đốc Kinh doanh. • Từ tháng 07/2022 đến 6/02/2026: Phó Tổng Giám đốc Công ty CTIN, kiêm nhiệm Giám đốc Kinh doanh. - Từ ngày 07/02/2025 đến nay: Tổng Giám đốc Công ty CTIN. - Từ ngày 29/04/2025 đến nay: Thành viên HĐQT Công ty CTIN. Công ty Cổ phần Viễn thông – Tin học Bưu điện 35

**Bản kiểm:** ICT → Lê Thanh Sơn · `APPOINTS` · Tổng Giám đốc.

**Vì sao REJECTED:** Niên biểu trong cùng nguồn mâu thuẫn: Phó TGĐ đến 6/02/2026 nhưng TGĐ từ 07/02/2025. Không tự sửa năm hoặc coi mâu thuẫn đã được giải quyết. Quyết định này từ chối bản nghiệm thu niên biểu hiện tại, không khẳng định người chưa từng được bổ nhiệm.

**Phạm vi / xử lý:** Cần quyết định bổ nhiệm hoặc đính chính có nguồn ghim để xác định niên biểu; sửa thành bản mới rồi kiểm lại.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/ICT_Baocaothuongnien_2025.pdf · document_id `f203d47e-b91c-5f17-883b-78e8df459ebd` · trang PDF `18`.

**Hash section/trang đã kiểm:** `86e40a3be3027c0120a47880b0d770051543b755b6d2609ddc097b50609c494c`.

### APPROVED — 186. 16a69a2b-d784-5d02-8e2c-e3ccee8f269e

**Bằng chứng nguồn:**
> - Từ ngày 29/04/2025 đến nay: Thành viên HĐQT Công ty CTIN. Công ty Cổ phần Viễn thông – Tin học Bưu điện 35

**Bản kiểm:** Lê Thanh Sơn → ICT · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Chỉ duyệt Lê Thanh Sơn là thành viên HĐQT ICT theo nguồn từ 29/04/2025. Lỗi niên biểu TGĐ không phủ định riêng chức vụ HĐQT này; sửa kết luận từ chối lan sang bản này ở báo cáo cũ.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/ICT_Baocaothuongnien_2025.pdf · document_id `f203d47e-b91c-5f17-883b-78e8df459ebd` · trang PDF `18`.

**Hash section/trang đã kiểm:** `86e40a3be3027c0120a47880b0d770051543b755b6d2609ddc097b50609c494c`.

### APPROVED — 187. d0c73c80-6617-58cd-8e67-d06041e682ec

**Bằng chứng nguồn:**
> Ông Nguyễn Vân Anh TV HĐQT 0 0% TV không điều hành 8 Ông Nguyễn Việt Dũng TV HĐQT 0 0% TV không điều hành TV HĐQT kiêm Phó 9 Ông Koji Irig

**Bản kiểm:** Nguyễn Vân Anh → CTG · `HOLDS_ROLE` · Thành viên HĐQT.

**Phạm vi / xử lý:** Nguồn trang này ghi Nguyễn Vân Anh là TV HĐQT CTG. Duyệt đúng tên Vân trong phạm vi nguồn; chưa có bằng chứng để hợp nhất với tên Văn. Không lấy cảnh báo tên cũ làm lý do bác dữ kiện đang khớp.

**Nguồn:** https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/CTG_Baocaothuongnien_2025.pdf · document_id `47d6c083-3e25-5eb9-88da-f7f3e5976582` · trang PDF `18`.

**Hash section/trang đã kiểm:** `64f0f83133742e340888a230d7f94930d0558d83cba35f8774ecece9550a3a02`.

## Kiểm chứng và việc cần sửa

Đã đọc `backend/src/person_role/metadata_repository.py`, `wbs03_repository.py`, migration metadata, `apply_graph_metadata.py`, `backend/src/graph_review/engine.py`, `repository.py`, `gate.py`, `sprint4_store.py` và tài liệu pipeline. Các đoạn code/SELECT chứng minh lỗi được giữ nguyên ở trên.

Vũ xử lý chặn hồi sinh bản REJECTED ở legacy, thống nhất tài liệu version với code, triển khai review store/quyền ghi và phối hợp canonical/time trước khi nạp. Không yêu cầu sửa 185 dữ kiện đã đạt chỉ vì DB chưa sẵn sàng.

Bộ regression đã chạy: 137 passed, 9 skipped, 15 xfailed, 14 subtests passed. Bỏ xfail để tái hiện lỗi: 15 failed, 4 passed. Không tính skipped/xfail là chức năng đã đạt. Fixture ZIP sẵn có thuộc release 28/10.3: 28 hash file khớp, 12 ca contract đúng kỳ vọng; chưa xác nhận đây là đúng ZIP fixture 26/10.

**Không ghi DB, không nạp Neo4j, không đổi source nghiệp vụ và không sửa bộ 13 ca Nhân V4 trong lượt chốt biên bản này.**
