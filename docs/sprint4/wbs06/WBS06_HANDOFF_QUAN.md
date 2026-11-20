# Bàn giao Quân — kết quả kiểm thử nguồn, code và từng sự kiện

**Rà soát ngày 02/11/2026. Gửi riêng file Markdown này là đủ.**

## Kết luận của người kiểm thử

**139/139 lượt event đã có kết luận REJECTED đối với bản hiện tại đưa vào graph trả lời** (121 biến thể riêng). Không còn nhóm “chưa phát hiện lỗi nên chưa đánh giá”. Mỗi ca dưới đây ghi lỗi cụ thể hoặc điều kiện nội dung chưa đạt, ngay cạnh câu nguồn và giá trị code trả ra.

Con số 0 APPROVED cho bản event hoàn chỉnh không có nghĩa mọi câu nguồn sai. Ví dụ ra mắt Online Lending và ELC đã phát hành cổ phiếu có nguồn rõ, nhưng bản trả ra vẫn unconfirmed, vai trò unspecified. Các bản planned có thể ghi kế hoạch đúng, song chưa đủ điều kiện làm sự kiện đã có hiệu lực theo tiêu chí nghiệm thu. Báo cáo phân biệt **sai nội dung**, **thiếu thuộc tính cần thiết**, **kế hoạch chưa đủ điều kiện**; không gọi cả ba là bịa đặt. Kết luận trên file không tự ghi những ca thiếu/mơ hồ thành trạng thái REJECTED vĩnh viễn trong DB.

Tổng đầu vào **211 lượt bài / 187 article ID**, gồm **112 lượt có event, 99 lượt không có event**. 139 lượt tạo 136 nhóm sau dedup; việc chạy lại ra giống nhau chỉ chứng minh tính tái lập, không chứng minh gộp đúng nghĩa. Các bài không có event không được tính thành APPROVED cho một quan hệ không tồn tại.

## Phần đã kiểm và đạt

| Hạng mục | Kết luận | Phạm vi |
|---|---|---|
| Nguồn/binding được chọn | APPROVED | 187/187 article ID, index 2264bbb9-024c-5634-abb5-58f399801b34; đối chiếu snapshot, locator, membership. Bốn binding sai ở phiên khác được nêu riêng Q08. |
| Câu evidence có trong nguồn | APPROVED | 112/112 lượt bài có event; chỉ chứng minh câu trích tồn tại. |
| Chạy lại đầu ra | APPROVED | 211/211 lượt khớp khi bỏ relevance_reason/needs_followup; không nghiệm thu follow-up vì thiếu ngày chạy gốc. |
| Đối soát JSON/JSONL/reconcile | APPROVED | Đủ 10 thư mục, 139 lượt/136 nhóm tái lập. Lỗi gộp ý nghĩa vẫn được bàn giao riêng. |
| Không bịa organizer từ tag | APPROVED | Code để unspecified thay vì tự gán organizer là đúng nguyên tắc; bản phục vụ graph vẫn phải xác định được vai trò bằng nguồn. |

## Code đã đọc để lần ngược lỗi

`backend/src/documents/event_news.py`: `_TRIGGERS`/`detect_event_type`, `find_subjects`, `extract_orgs`, `detect_status`, `find_dates`, `extract_financial_figures`, `extract_article`, `_build_event`, `_event_key`, `deduplicate_events`, `load_manifest`, `reconcile`. Đối chiếu thêm `stock_news_kg_template.json` và các file `data/News/*/batch_extracted.json`, JSONL, events sau gộp. Không đánh giá chỉ từ file preview.

Nguồn gốc lỗi: trigger quá rộng; tag được dùng làm subject khi câu không chứng minh vai trò; parser ngày không nhận dấu chấm và chưa phân biệt nghĩa ngày; parties bỏ đối tác/người; gộp theo type+subject bỏ đối tượng hành động. Bộ fixture/test không thay thế kiểm từng nguồn thật.


## Các mục REJECTED — bằng chứng đặt ngay sau kết luận

### REJECTED — Q01 — HĐQT thành đại hội cổ đông

**Bằng chứng trực tiếp — bài thật đã đối chiếu nguồn:**

```json
{
  "article_id": "9cad8358-1095-590e-a3a3-1f26d4e54e6b",
  "event_id": "e1",
  "output_file": "data/News/BID/batch_extracted.json",
  "source_url": "https://cafef.vn/du-lieu/bid-2999491/bid-nghi-quyet-hdqt-phe-duyet-phuong-an-phat-hanh-trai-phieu-tang-von-bidv-theo-hinh-thuc-rieng-le-quy-iv2026.chn",
  "index_version_id": "2264bbb9-024c-5634-abb5-58f399801b34",
  "snapshot_sha256": "fd8e6959ad5e490915b11b3bb970dc613469a6c48783fcd5805f0883e79a5dfc"
}
```
**Đoạn nguồn:**

> BID: Nghị quyết HĐQT phê duyệt Phương án phát hành Trái phiếu tăng vốn BIDV theo hình thức riêng lẻ Quý IV/2026

**Đầu ra thực tế:**

```json
{
  "event_type": "shareholder_meeting",
  "event_name": "Nghị quyết HĐQT"
}
```
**Vì sao từ chối:** nghị quyết HĐQT phê duyệt phương án không chứng minh đại hội cổ đông; sửa `_TRIGGERS`, không tự coi đã phát hành.

**Kết luận trong phạm vi hạng mục:** 38 biến thể event. BID 9cad8358…/e1 là nghị quyết phê duyệt phát hành trái phiếu, không chứng minh cuộc họp cổ đông.

### REJECTED — Q02 — năm thành số tiền

**Bằng chứng trực tiếp — bài thật đã đối chiếu nguồn:**

```json
{
  "article_id": "b421f949-205d-507e-b421-a988aeafee72",
  "event_id": "e2",
  "output_file": "data/News/FPT/batch_extracted.json",
  "source_url": "https://fireant.vn/bai-viet/fpt-co-dong-don-tin-vui-nhan-tam-ung-co-tuc-nam-2026/42522048",
  "index_version_id": "2264bbb9-024c-5634-abb5-58f399801b34",
  "snapshot_sha256": "8cbdcdcad7212ca912edf8ada65d02d85e76a8528d085e1cf35ad8a4987b5778"
}
```
**Đoạn nguồn:**

> Cổ đông FPT sẽ được nhận tạm ứng cổ tức năm 2026 tỷ lệ 10% Theo đó, HĐQT FPT thông qua phương án tạm ứng cổ tức năm 2026 bằng tiền với tỷ lệ 10%/cổ phiếu (1 cổ phiếu nhận 1.000 đồng).

**Đầu ra thực tế:**

```json
{
  "financial_figures_stated": [
    {
      "value_raw": "10% mệnh giá",
      "context": "Hội đồng quản trị Công ty Cổ phần FPT (HOSE: FPT ) đã thông qua nghị quyết chi trả cổ tức bằng tiền mặt với tỷ lệ 10% mệnh giá, tương ứng 1.000 đồng cho mỗi cổ phiếu.",
      "evidence": "Hội đồng quản trị Công ty Cổ phần FPT (HOSE: FPT ) đã thông qua nghị quyết chi trả cổ tức bằng tiền mặt với tỷ lệ 10% mệnh giá, tương ứng 1.000 đồng cho mỗi cổ phiếu."
    },
    {
      "value_raw": "1.000 đồng",
      "context": "Hội đồng quản trị Công ty Cổ phần FPT (HOSE: FPT ) đã thông qua nghị quyết chi trả cổ tức bằng tiền mặt với tỷ lệ 10% mệnh giá, tương ứng 1.000 đồng cho mỗi cổ phiếu.",
      "evidence": "Hội đồng quản trị Công ty Cổ phần FPT (HOSE: FPT ) đã thông qua nghị quyết chi trả cổ tức bằng tiền mặt với tỷ lệ 10% mệnh giá, tương ứng 1.000 đồng cho mỗi cổ phiếu."
    },
    {
      "value_raw": "2026 tỷ",
      "context": "Cổ đông FPT sẽ được nhận tạm ứng cổ tức năm 2026 tỷ lệ 10% Theo đó, HĐQT FPT thông qua phương án tạm ứng cổ tức năm 2026 bằng tiền với tỷ lệ 10%/cổ phiếu (1 cổ phiếu nhận 1.000 đồng).",
      "evidence": "Cổ đông FPT sẽ được nhận tạm ứng cổ tức năm 2026 tỷ lệ 10% Theo đó, HĐQT FPT thông qua phương án tạm ứng cổ tức năm 2026 bằng tiền với tỷ lệ 10%/cổ phiếu (1 cổ phiếu nhận 1.000 đồng)."
    },
    {
      "value_raw": "10%",
      "context": "Cổ đông FPT sẽ được nhận tạm ứng cổ tức năm 2026 tỷ lệ 10% Theo đó, HĐQT FPT thông qua phương án tạm ứng cổ tức năm 2026 bằng tiền với tỷ lệ 10%/cổ phiếu (1 cổ phiếu nhận 1.000 đồng).",
      "evidence": "Cổ đông FPT sẽ được nhận tạm ứng cổ tức năm 2026 tỷ lệ 10% Theo đó, HĐQT FPT thông qua phương án tạm ứng cổ tức năm 2026 bằng tiền với tỷ lệ 10%/cổ phiếu (1 cổ phiếu nhận 1.000 đồng)."
    },
    {
      "value_raw": "1 cổ phiếu",
      "context": "Cổ đông FPT sẽ được nhận tạm ứng cổ tức năm 2026 tỷ lệ 10% Theo đó, HĐQT FPT thông qua phương án tạm ứng cổ tức năm 2026 bằng tiền với tỷ lệ 10%/cổ phiếu (1 cổ phiếu nhận 1.000 đồng).",
      "evidence": "Cổ đông FPT sẽ được nhận tạm ứng cổ tức năm 2026 tỷ lệ 10% Theo đó, HĐQT FPT thông qua phương án tạm ứng cổ tức năm 2026 bằng tiền với tỷ lệ 10%/cổ phiếu (1 cổ phiếu nhận 1.000 đồng)."
    },
    {
      "value_raw": "1.000 đồng",
      "context": "Cổ đông FPT sẽ được nhận tạm ứng cổ tức năm 2026 tỷ lệ 10% Theo đó, HĐQT FPT thông qua phương án tạm ứng cổ tức năm 2026 bằng tiền với tỷ lệ 10%/cổ phiếu (1 cổ phiếu nhận 1.000 đồng).",
      "evidence": "Cổ đông FPT sẽ được nhận tạm ứng cổ tức năm 2026 tỷ lệ 10% Theo đó, HĐQT FPT thông qua phương án tạm ứng cổ tức năm 2026 bằng tiền với tỷ lệ 10%/cổ phiếu (1 cổ phiếu nhận 1.000 đồng)."
    }
  ]
}
```
**Vì sao từ chối:** `2026` là năm trước cụm “tỷ lệ”, không phải số tiền “2026 tỷ”; sửa `_FIGURE`.

**Kết luận trong phạm vi hạng mục:** b421f949…/e2 có value_raw=2026 tỷ từ câu nói năm 2026 và tỷ lệ cổ tức.

### REJECTED — Q03 — gộp hai hợp đồng ở hai bài

**Bằng chứng trực tiếp — test giả lập, không phải hai bài thật:**

```json
{
  "inputs": [
    "FPT đã ký kết hợp đồng với Công ty Alpha ngày 30/10/2026.",
    "FPT đã ký kết hợp đồng với Công ty Beta ngày 30/10/2026."
  ],
  "actual_group_count": 1,
  "actual_event_key": "agreement_signing|fpt|2026-10-30",
  "actual_review_flag": "none",
  "expected": "Hai hợp đồng khác đối tác phải giữ riêng hoặc báo cần kiểm, không gộp chắc chắn."
}
```
**Chỗ sửa:** `_event_key()` thiếu đối tác/object trong khóa.

**Kết luận trong phạm vi hạng mục:** Test FPT–Alpha / FPT–Beta cùng ngày bị gộp, review_flag=none. Đây là test giả lập, không gán thành lỗi của cặp bài thật chưa kiểm.

### REJECTED — Q04 — manifest compact/pretty khác kết quả

**Bằng chứng trực tiếp — cùng dữ liệu, chỉ thay cách xuống dòng:**

```json
{
  "articles": [
    {
      "article_id": "a",
      "title": "",
      "content": "FPT đã ký kết hợp đồng hợp tác.",
      "symbols": [
        "FPT"
      ],
      "source": "synthetic-probe",
      "url": "https://example.invalid/a",
      "published_at": "2026-10-30T10:00:00+07:00"
    }
  ]
}
```

```json
{
  "compact_first_row_keys": [
    "articles"
  ],
  "compact_article_id": null,
  "pretty_first_row_keys": [
    "article_id",
    "title",
    "content",
    "symbols",
    "source",
    "url",
    "published_at"
  ],
  "pretty_article_id": "a"
}
```
**Vì sao từ chối:** expected cả hai đều trả article `a`; actual compact trả object ngoài có khóa `articles`, article_id null. Sửa `load_manifest()`, không đoán JSONL bằng xuống dòng.

**Kết luận trong phạm vi hạng mục:** Cùng object articles, load_manifest đọc khác khi đổi cách xuống dòng.

### REJECTED — Q05 — niêm yết lãi suất thành corporate_action

**Bằng chứng trực tiếp — bài thật đã đối chiếu nguồn:**

```json
{
  "article_id": "7189cb54-2dc4-5d75-a72f-8b3491d1b661",
  "event_id": "e1",
  "output_file": "data/News/CTG/batch_extracted.json",
  "source_url": "https://fireant.vn/bai-viet/lai-suat-vietinbank-hom-nay-gui-tiet-kiem-tai-quay-100-trieu-dong-thu-ve-11-trieu-dong/42521633",
  "index_version_id": "2264bbb9-024c-5634-abb5-58f399801b34",
  "snapshot_sha256": "08da4990e68c32a5ad4bb4ffad8ace59a2205a252a5fa303b198f95d9b8a58f6"
}
```
**Đoạn nguồn:**

> Biểu lãi suất tiền gửi tiết kiệm trực tiếp tại VietinBank hiện đang được niêm yết như sau: Lãi suất tiền gửi kỳ hạn 1 tháng không đổi, neo ở mức 2,1%/năm.

**Đầu ra thực tế:**

```json
{
  "event_type": "corporate_action",
  "event_name": "niêm yết"
}
```
**Vì sao từ chối:** đang nói niêm yết lãi suất tiền gửi, không phải niêm yết chứng khoán; trigger cần ngữ cảnh.

**Kết luận trong phạm vi hạng mục:** 7 biến thể; 7189cb54…/e1 nói biểu lãi suất tiền gửi.

### REJECTED — Q06 — giải thích luật thành event

**Bằng chứng trực tiếp — bài thật đã đối chiếu nguồn:**

```json
{
  "article_id": "a46ed591-fe06-5e17-a880-dacb7fcf7675",
  "event_id": "e1",
  "output_file": "data/News/BID/batch_extracted.json",
  "source_url": "https://fireant.vn/bai-viet/nha-nuoc-giu-gi-nhuong-gi-tai-loat-doanh-nghiep-lon/42525775",
  "index_version_id": "2264bbb9-024c-5634-abb5-58f399801b34",
  "snapshot_sha256": "e770e6bb021e68524bea97121f90bae21f098da16c2ca16e0b130e773fed8fa6"
}
```
**Đoạn nguồn:**

> Theo khoản 1 Điều 148 Luật Doanh nghiệp 2020, nếu điều lệ công ty không quy định tỷ lệ khác, các nghị quyết quan trọng của đại hội đồng cổ đông cần được ít nhất 65% tổng số phiếu biểu quyết của cổ đông dự họp tán thành.

**Đầu ra thực tế:**

```json
{
  "event_type": "shareholder_meeting",
  "subjects": [],
  "status": "unconfirmed"
}
```
**Vì sao từ chối:** đoạn giải thích tỷ lệ biểu quyết theo luật không xác lập một cuộc họp cụ thể của công ty nào.

**Kết luận trong phạm vi hạng mục:** a46ed591…/e1 chỉ giải thích Điều 148, không xác lập cuộc họp của công ty cụ thể.

### REJECTED — Q07 — test chính collect được

**Bằng chứng trực tiếp — lệnh và lỗi collect:**

```text
python -m pytest backend/tests/test_wbs16_event_extractor.py --collect-only -q
ImportError: cannot import name 'parse_dates_extended' from 'src.documents.event_news'
no tests collected, 1 error
```
Test còn import `detect_status_rigorous`, trong khi module hiện có `find_dates()` và `detect_status()`. REJECTED tiêu chí bộ test chính chạy được; không tính test của module khác thay thế.

**Kết luận trong phạm vi hạng mục:** ImportError parse_dates_extended; test còn import detect_status_rigorous không có trong module.

### REJECTED — Q08 — bộ hiện tại đủ điều kiện nạp graph

**Bằng chứng trực tiếp — bài thật đã đối chiếu nguồn:**

```json
{
  "article_id": "43c9d2b7-5403-5b46-87cb-5947a06b2406",
  "event_id": "e1",
  "output_file": "data/News/MBB/batch_extracted.json",
  "source_url": "https://fireant.vn/bai-viet/kbsv-va-ngan-hang-mb-ky-ket-hop-tac-phat-trien-dich-vu-tai-chinh-so/42432878",
  "index_version_id": "2264bbb9-024c-5634-abb5-58f399801b34",
  "snapshot_sha256": "5601dc35e9099f74a816545f041ed352b1917d5b5de8fd22852b7544a56679d1"
}
```
**Đoạn nguồn:**

> KBSV và Ngân hàng MB ký kết hợp tác phát triển dịch vụ tài chính số

**Đầu ra thực tế:**

```json
{
  "parties": [
    {
      "name_raw": "MBB",
      "name_normalized": "MBB",
      "party_type": "organization",
      "role": "unspecified",
      "role_evidence": null,
      "name_source": "metadata"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "status": "unconfirmed"
}
```
**Vì sao chưa đủ nạp:** party chỉ từ metadata, role unspecified, role_evidence null, thời gian chưa xác lập. Output article schema 0.1 chưa phải envelope contract 2.1.0 đã resolve/duyệt; không dùng confidence hay tag thay bằng chứng. Đây là từ chối điều kiện nạp hiện tại, không kết luận bài viết giả.

**Nguồn phiên khác bị chặn — bằng chứng kèm ngay đây để không cần file Vũ:**
**Bằng chứng trực tiếp — kết quả SELECT và kiểm định danh:** index `bcc6251d-ba1b-51d9-8fd5-92eb893a9ff0`, corpus `a5338f75-5894-5b8a-bf94-0a6da7c26ced`.

Quy tắc: stored document ID phải bằng locator source document ID hoặc release alias hợp lệ của nó. Cả bốn dòng sau không thỏa. Đây là từ chối **binding của phiên này**, không phải từ chối chính bài viết.

| Article ID | Stored document ID | Locator source document ID | Release alias kỳ vọng |
|---|---|---|---|
| 97ebe30f-745f-576d-a3aa-08a65d013b38 | 115b0a99-d9a0-50ea-ab6c-a1ac6da67661 | e2b5d203-9756-590d-a7c7-120efe7411bf | 874636b9-b1a4-5f9b-b55a-a8a4aaad5035 |
| d5b2a5e5-6d68-5815-996d-badec50d510a | 33a46815-7218-59fd-a557-69fb3696253c | 44ab17dd-ec76-59a3-80da-95cb7f907312 | eddec916-90bf-5bb1-ba80-8bee74361da6 |
| 68ee9bb4-d1a2-5e84-9cc4-1ea69daf2ed0 | 3b1990e8-10cd-5357-8a61-855e97ef9375 | 7a23fd4f-b978-5d68-b4df-11f6b8587484 | 079cea4d-4fb3-50f5-98e8-b3de2a0092e3 |
| 2b7ec115-7053-5620-867d-dfd2e8dbc52e | 6b9af22c-4f6a-5d55-bc3d-d1da0cefb633 | a10f61c7-e2ee-5c12-962c-9d68f380858c | 58bce1d8-5100-5b0f-a879-46e7f1ec5bcf |

Các bài vẫn có binding hợp lệ ở index `2264bbb9-024c-5634-abb5-58f399801b34`, là phiên dùng để đối chiếu output lần này. WBS07/đơn vị quản lý corpus kiểm mapping trước khi dùng phiên bị từ chối; không giao Quân sửa nội dung bài.

**Kết luận trong phạm vi hạng mục:** Chưa có nghiệm thu mapping entity/role/thời gian, bản chuẩn hóa và review chính thức của bộ này. Không coi tag hoặc unspecified là bằng chứng vai trò.

### REJECTED — Q09 — giữ ngày viết bằng dấu chấm

**Bằng chứng trực tiếp — bài thật đã đối chiếu nguồn:**

```json
{
  "article_id": "4bd6e412-e784-54f8-9825-8a9dcc067c6b",
  "event_id": "e1",
  "output_file": "data/News/VCB/batch_extracted.json",
  "source_url": "https://cafef.vn/du-lieu/vcb-2998160/vcb-mien-nhiem-ong-nguyen-van-tuan-pho-tong-giam-doc-tu-1112026.chn",
  "index_version_id": "2264bbb9-024c-5634-abb5-58f399801b34",
  "snapshot_sha256": "6916235fe902d99aa24eb112c8242aa7143aed5918472b513782655861a675d1"
}
```
**Đoạn nguồn:**

> VCB: Miễn nhiệm ông Nguyễn Văn Tuân - Phó Tổng giám đốc từ 1.11.2026

**Đầu ra thực tế:**

```json
{
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  }
}
```
**Vì sao từ chối:** nguồn có ngày `1.11.2026` nhưng `date_candidates=[]`; `_DATE_FULL` chỉ nhận `/` hoặc `-`. Giữ ngày và bằng chứng, xác định nghĩa ngày riêng; không tự lấy ngày đăng.
| ID / event | Ngày nguyên văn bị bỏ |
|---|---|
| 841ac317-aef6-57c0-98f7-cdc9083389e2 / e1 | 19.8.2026 |
| 297bfed7-5c3a-52e2-9453-ccde8bed48b0 / e1 | 19.10.2026 |
| 6c79fa32-9af7-527b-b6b8-5f41512cc4ad / e1 | 8.10.2026 |
| b0ebbed7-6934-5125-a9cd-be1d58634d53 / e1 | 22.9.2026 |
| 3a3a6751-7c34-549f-921f-cc7907ea9458 / e1 | 11.9.2026 |
| ad5453a3-d532-56c2-8cd3-da318e99860c / e1 | 1.9.2026 |
| 5d9a5566-4256-5703-b789-c80e0cee3d45 / e1 | 1.9.2026 |
| 4bd6e412-e784-54f8-9825-8a9dcc067c6b / e1 | 1.11.2026 |

**Kết luận trong phạm vi hạng mục:** **8 lượt** có ngày nguyên văn nhưng không có trong date_candidates; ví dụ VCB miễn nhiệm từ 1.11.2026, CMG bổ nhiệm từ 19.8.2026.

### REJECTED — Q10 — giữ đối tác Quandela

**Bằng chứng trực tiếp — bài thật đã đối chiếu nguồn:**

```json
{
  "article_id": "829190a9-7533-5c74-85c8-7f126d2a1892",
  "event_id": "e1",
  "output_file": "data/News/FPT/batch_extracted.json",
  "source_url": "https://cafef.vn/fpt-bat-tay-chu-nhan-sieu-may-tinh-luong-tu-quang-tu-manh-nhat-the-gioi-188261021164747188.chn",
  "index_version_id": "2264bbb9-024c-5634-abb5-58f399801b34",
  "snapshot_sha256": "c1aa266790904aa8272f7fe278a8ab8f12937f22867792c3b3f2995715950cc9"
}
```
**Đoạn nguồn:**

> FPT: Giá hiện tại Thay đổi Xem hồ sơ doanh nghiệp TIN MỚI Tập đoàn FPT và Quandela, công ty sở hữu siêu máy tính lượng tử quang tử mạnh nhất thế giới, vừa, ký kết Biên bản ghi nhớ hợp tác nhằm phát triển năng lực nghiên cứu, tích hợp, đào tạo nguồn nhân lực và thúc đẩy ứng dụng công nghệ lượng tử tại Việt Nam.

**Đầu ra thực tế:**

```json
{
  "parties": [
    {
      "name_raw": "FPT",
      "name_normalized": "FPT",
      "party_type": "organization",
      "role": "counterparty",
      "role_evidence": "FPT: Giá hiện tại Thay đổi Xem hồ sơ doanh nghiệp TIN MỚI Tập đoàn FPT và Quandela, công ty sở hữu siêu máy tính lượng tử quang tử mạnh nhất thế giới, vừa, ký kết Biên bản ghi nhớ hợp tác nhằm phát triển năng lực nghiên cứu, tích hợp, đào tạo nguồn nhân lực và thúc đẩy ứng dụng công nghệ lượng tử tại Việt Nam.",
      "name_source": "sentence"
    }
  ]
}
```
**Vì sao từ chối:** nguồn nêu cả FPT và Quandela là bên ký, output bỏ Quandela. Phải giữ bên có evidence rồi resolve, không bỏ đối tác vì ngoài danh sách ticker.

**Kết luận trong phạm vi hạng mục:** 829190a9…/e1: nguồn nêu FPT và Quandela ký; output chỉ có FPT, thiếu Quandela.

### REJECTED — Q11 — alias MB và bên KBSV

**Bằng chứng trực tiếp — bài thật đã đối chiếu nguồn:**

```json
{
  "article_id": "43c9d2b7-5403-5b46-87cb-5947a06b2406",
  "event_id": "e1",
  "output_file": "data/News/MBB/batch_extracted.json",
  "source_url": "https://fireant.vn/bai-viet/kbsv-va-ngan-hang-mb-ky-ket-hop-tac-phat-trien-dich-vu-tai-chinh-so/42432878",
  "index_version_id": "2264bbb9-024c-5634-abb5-58f399801b34",
  "snapshot_sha256": "5601dc35e9099f74a816545f041ed352b1917d5b5de8fd22852b7544a56679d1"
}
```
**Đoạn nguồn:**

> KBSV và Ngân hàng MB ký kết hợp tác phát triển dịch vụ tài chính số

**Đầu ra thực tế:**

```json
{
  "parties": [
    {
      "name_raw": "MBB",
      "name_normalized": "MBB",
      "party_type": "organization",
      "role": "unspecified",
      "role_evidence": null,
      "name_source": "metadata"
    }
  ]
}
```
**Vì sao từ chối:** thiếu KBSV; MB chỉ thành MBB từ metadata, không có role evidence. Cần alias theo ngữ cảnh và giữ các bên ký có nguồn, không gán vai trò cho mọi tag.

**Kết luận trong phạm vi hạng mục:** 43c9d2b7…/e1: nguồn nêu KBSV và Ngân hàng MB ký; output chỉ có MBB từ metadata, role unspecified, evidence null.

### REJECTED — Q12 — hai hợp đồng trong cùng bài

**Bằng chứng trực tiếp — test giả lập trong cùng một bài:**

```json
{
  "input": "FPT đã ký kết hợp đồng với Công ty Alpha ngày 29/10/2026. FPT đã ký kết hợp đồng với Công ty Beta ngày 30/10/2026.",
  "expected_event_count": 2,
  "actual_event_count": 1,
  "actual_dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": [
      {
        "date": "2026-10-29",
        "derived": false,
        "evidence": "29/10/2026"
      },
      {
        "date": "2026-10-30",
        "derived": false,
        "evidence": "30/10/2026"
      }
    ]
  }
}
```
**Vì sao từ chối:** `extract_article()` gom theo `(etype, tuple(subjects))` trước khi dedup, làm hai hợp đồng khác đối tác/ngày thành một. Phải sửa cả cấp gộp trong bài.

**Kết luận trong phạm vi hạng mục:** Test hai câu FPT ký Alpha ngày 29/10 và Beta ngày 30/10 bị gom trước bước dedup vì key chỉ là loại+subjects. Khác Q03 ở cấp gộp.


**Nghiệm thu module hiện tại: REJECTED** vì các lỗi trên còn tồn tại. Các hạng mục kỹ thuật đã đạt vẫn APPROVED; không đổi nguồn thật thành thiếu nguồn.

## Dẫn chứng mới và kết quả mong đợi

| Mã | ID đầy đủ / event | Nguồn và actual output | Expected / chỗ cần sửa |
|---|---|---|---|
| Q09 | 4bd6e412-e784-54f8-9825-8a9dcc067c6b / e1 | VCB: Miễn nhiệm ông Nguyễn Văn Tuân - Phó Tổng giám đốc từ 1.11.2026; date_candidates=[], ngày null. | _DATE_FULL chỉ nhận / hoặc -. Giữ 2026-11-01 và evidence, xác định đây là ngày hiệu lực từ chữ từ; không dùng ngày đăng. |
| Q09 | 841ac317-aef6-57c0-98f7-cdc9083389e2 / e1 | CMG bổ nhiệm ông Đặng Tùng Sơn, ông Nguyễn Hải Sơn từ 19.8.2026; ngày bị bỏ. | Nhận dd.mm.yyyy, giữ các candidate hợp lệ; không tự chọn một ngày nếu có nhiều ngày khác nghĩa. |
| Q10 | 829190a9-7533-5c74-85c8-7f126d2a1892 / e1 | Tập đoàn FPT và Quandela … ký kết Biên bản ghi nhớ. Output parties chỉ có FPT. | Giữ cả hai bên có evidence; tên chưa resolve thì giữ raw và đưa qua bước chuẩn hóa, không bỏ đối tác. |
| Q11 | 43c9d2b7-5403-5b46-87cb-5947a06b2406 / e1 | KBSV và Ngân hàng MB ký kết hợp tác phát triển dịch vụ tài chính số. Actual: chỉ MBB, unspecified, metadata, null role evidence. | Resolve alias MB → MBB có ngữ cảnh; giữ KBSV và bằng chứng vai trò. Không sửa bằng cách gán vai trò cho mọi tag. |
| Q12 | test_separate_contracts_inside_one_article_remain_separate | FPT ký Alpha 29/10/2026. FPT ký Beta 30/10/2026. Actual: 1 event. | Hai hành động khác đối tác/ngày phải được giữ riêng; thiếu định danh thì báo cần kiểm, không gộp chắc chắn. |

Đủ 8 lượt mất ngày đã liệt kê ngay sau Q09. Phụ lục cuối file có 139 lượt event, đoạn nguồn đầy đủ, URL và actual output của từng trường REJECTED.

## Hướng sửa theo code

- **Q01/Q05/Q06:** _TRIGGERS/detect_event_type cần ngữ cảnh hành động và thực thể; tách HĐQT/ĐHĐCĐ, niêm yết lãi suất/niêm yết chứng khoán, giải thích luật/sự kiện được khẳng định.
- **Q02:** _FIGURE/extract_financial_figures loại năm trước tỷ lệ, kiểm đơn vị; không tự thay bằng số tiền khác.
- **Q03/Q12:** _event_key và key nhóm trong extract_article cần phân biệt object/đối tác/thời điểm; không chỉ đổi deduplicate_events mà bỏ lỗi gộp từ trước đó.
- **Q04:** load_manifest phân tích JSON/JSONL theo cấu trúc, không đoán bằng cách xuống dòng.
- **Q09:** find_dates nhận dấu chấm và giữ date candidates/evidence; xác định nghĩa ngày riêng. Có 8 lỗi mất candidate, không tự khẳng định mọi ngày đó đều là event_date.
- **Q10/Q11:** find_subjects chỉ match symbol literal, extract_orgs chủ yếu nhận do/phối hợp tổ chức nên mất đối tác ký kết. Thêm alias và các bên ký có evidence; không lấy metadata thay chứng minh.
- **Q07:** thống nhất API test/code rồi chạy cả test module; không thêm hàm rỗng hoặc bỏ test để lấy PASS.

**Hai ví dụ FPT–Quandela và KBSV–MB từng được dùng ở bản trước như ví dụ có nguồn thật: nguồn đúng, nhưng output chưa đủ bên. Nay ghi REJECTED riêng phần parties, không còn dùng chúng làm ví dụ đầu ra hoàn chỉnh đã đạt.**

## Phần phải phối hợp, không đổ hết cho extractor

Template 1.3.0 và event_news 0.2.0/schema 0.1 là hai cấu trúc/taxonomy khác. news_event_extractor.py là module khác; PASS của nó không chứng minh event_news.py đạt. WBS06 đã có adapter candidate from_news_article, nhưng adapter đó chưa tự biến bản nháp thành envelope/nguồn/identity đã được duyệt. Cần mapping WBS01/WBS02/WBS06/WBS07 cụ thể.

131/139 lượt event lưu unconfirmed, 7 planned, 1 occurred. Giữ nguyên bất định khi nguồn chưa chứng minh; không ép thành occurred để qua kiểm. event_type appointment cũng đang bao gồm miễn nhiệm/từ nhiệm: bước mapping phải đọc hành động thật, không đổi tất cả thành APPOINTS. Entity từ tag, đối tượng được nhắc và bên tổ chức/tham gia cần tách rõ.

## Kiểm thử, fixture và cách nghiệm thu

**137 passed, 9 skipped, 15 xfailed, 14 subtests passed.** Bỏ xfail: **15 failed, 4 passed**, gồm 14 lỗi Quân và V01 Vũ; test module chính vẫn lỗi collect riêng. Không tính xfail/skip là đã đạt. Các test fake nguồn/memory/driver không phải lần chạy Neo4j/DB production.

ZIP fixture hiện có khai release **s4-wbs02-wbs03-2026-10-28.3**: 28 hash khớp, **12/12 kỳ vọng contract đúng**, không cho nạp graph thật. Phần xác nhận đúng bộ 26/10 chưa đạt; kết luận REJECTED và bản trích manifest nằm ngay ở mục fixture bên dưới.

Sau khi sửa: chạy đúng ID thật Q01/Q02/Q05/Q06/Q09/Q10/Q11; Q03/Q04/Q12 phải qua test hồi quy; chạy cả module chính. Trả output mới, extractor version, as_of, input manifest/hash, ID cũ → ID mới. WBS06 kiểm nội dung/nguồn và ghi quyết định; WBS08 chỉ nạp bản được duyệt và chỉ trả lời khi graph READY.

## REJECTED — xác nhận đây là đúng bộ fixture ngày 26/10

**Bằng chứng trực tiếp — manifest và kết quả kiểm ZIP đang có:**

```json
{
  "zip_sha256": "e9d937cf4f95c38e93b94660be25af390e8b6e4ba445264349627c41019f7a90",
  "declared_release": "s4-wbs02-wbs03-2026-10-28.3",
  "schema_version": "2.1.0",
  "manifest_files_checked": 28,
  "manifest_hash_mismatches": [],
  "contract_cases_checked": 12,
  "all_contract_expectations_match": true,
  "any_fixture_authorizes_live_load": false
}
```

**Vì sao từ chối tiêu chí phiên:** manifest tự khai release 28/10.3, chưa chứng minh đây là đúng gói phát hành 26/10. Không suy ngày phát hành từ ngày nằm trong câu giả lập. **APPROVED phần kiểm hash/validator** vì 28 hash khớp và 12 kỳ vọng đúng; đây là hai tiêu chí riêng, không từ chối toàn bộ fixture và không cho fixture nạp graph thật.

## Đối soát đủ 10 thư mục

| Mã | Lượt bài | Lượt event | Nhóm sau gộp | JSON/JSONL + dedup + reconcile |
|---|---|---|---|---|
| BID | 22 | 14 | 14 | APPROVED |
| CMG | 20 | 11 | 9 | APPROVED |
| CTG | 22 | 12 | 12 | APPROVED |
| ELC | 20 | 8 | 8 | APPROVED |
| FPT | 20 | 15 | 14 | APPROVED |
| ICT | 20 | 2 | 2 | APPROVED |
| ITD | 20 | 15 | 15 | APPROVED |
| MBB | 20 | 13 | 13 | APPROVED |
| TCB | 22 | 25 | 25 | APPROVED |
| VCB | 25 | 24 | 24 | APPROVED |



## Kết quả từng sự kiện — đủ 139 lượt

### REJECTED — 1. BID · a46ed591-fe06-5e17-a880-dacb7fcf7675 / e1

**Bằng chứng nguồn:**
> Theo khoản 1 Điều 148 Luật Doanh nghiệp 2020, nếu điều lệ công ty không quy định tỷ lệ khác, các nghị quyết quan trọng của đại hội đồng cổ đông cần được ít nhất 65% tổng số phiếu biểu quyết của cổ đông dự họp tán thành.

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "65%"
  ]
}
```

**Nhóm kết luận:** `KHONG_CO_SU_KIEN`.

**Vì sao REJECTED / cần làm gì:** Nguồn giải thích quy định chung của Luật Doanh nghiệp và tỷ lệ biểu quyết 65%; không xác định công ty hay cuộc họp cụ thể. Không được tạo một sự kiện đại hội cổ đông từ ví dụ pháp luật này.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:a46ed591-fe06-5e17-a880-dacb7fcf7675.

**Định vị:** `data/News/BID/batch_extracted.json` · snapshot `e770e6bb021e68524bea97121f90bae21f098da16c2ca16e0b130e773fed8fa6` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 2. BID · fbced2c9-da5d-5995-a98f-e15260708b97 / e1

**Bằng chứng nguồn:**
> Ở kỳ hạn 12 và 24 tháng, cả bốn ngân hàng cùng niêm yết lãi suất lần lượt 5,4%/năm và 5,5%/năm.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "5,4%",
    "5,5%",
    "2,6%",
    "5,4%",
    "5,5%",
    "5,4%",
    "3,5%",
    "17,5 triệu đồng"
  ]
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Đoạn nguồn đang nói niêm yết lãi suất tiền gửi, không phải niêm yết chứng khoán hay hành động vốn của doanh nghiệp. corporate_action được kích hoạt nhầm bởi từ “niêm yết”; cần loại trường hợp lãi suất khỏi trigger này.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:fbced2c9-da5d-5995-a98f-e15260708b97.

**Định vị:** `data/News/BID/batch_extracted.json` · snapshot `ec3b74bed639bf09c713284ccaae61694d5d25bba802818621d53ec441508d3e` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 3. BID · 3ca48d40-905e-5047-92c9-90bfd5488486 / e1

**Bằng chứng nguồn:**
> Trong báo cáo giải trình, GEL cho biết lợi nhuận trên báo cáo tài chính riêng chủ yếu đến từ cổ tức nhận từ các công ty con, nhưng khoản thu nhập này được loại trừ khi hợp nhất báo cáo tài chính.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "GEL",
      "name_normalized": "GEL",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn giải trình lợi nhuận riêng/hợp nhất do cổ tức nhận từ công ty con, không thông báo GEL thực hiện chia cổ tức. corporate_action đã nhầm khoản thu nhập kế toán thành hành động vốn của GEL.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:3ca48d40-905e-5047-92c9-90bfd5488486.

**Định vị:** `data/News/BID/batch_extracted.json` · snapshot `4acf257f3f60378ece6e8de961e44d2c9db6127ab498ab1bc203e07595d9d696` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 4. BID · 3ca48d40-905e-5047-92c9-90bfd5488486 / e2

**Bằng chứng nguồn:**
> Mã chính thức giao dịch trên HoSE từ ngày 6/2/2026 với giá tham chiếu 28.800 đồng/cp và từng tăng lên hơn 40.000 đồng/cp trong tháng đầu tiên niêm yết.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [],
  "dates": {
    "event_date_start": "2026-02-06",
    "event_date_end": "2026-02-06",
    "date_precision": "day",
    "date_derived": false,
    "date_evidence": "6/2/2026",
    "date_candidates": [
      {
        "date": "2026-02-06",
        "derived": false,
        "evidence": "6/2/2026"
      }
    ]
  },
  "figures": [
    "28.800 đồng",
    "40.000 đồng"
  ]
}
```

**Nhóm kết luận:** `THIEU_THUC_THE`.

**Vì sao REJECTED / cần làm gì:** Nguồn nói mã đã chính thức giao dịch trên HoSE từ 6/2/2026, nhưng parties rỗng và status=unconfirmed. Cần nối GEL qua ngữ cảnh bài và ghi đúng việc đã giao dịch; hiện không có cạnh thực thể đủ rõ dù ngày được trích đúng.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:3ca48d40-905e-5047-92c9-90bfd5488486.

**Định vị:** `data/News/BID/batch_extracted.json` · snapshot `4acf257f3f60378ece6e8de961e44d2c9db6127ab498ab1bc203e07595d9d696` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 5. BID · f2bc443a-32bc-5cbc-a7a1-19639d9d9a69 / e1

**Bằng chứng nguồn:**
> Từ chủ trương đến hành động: dấu ấn tiên phong của BIDV Quy trình triển khai được chuẩn hóa thành các bước rõ ràng: tiếp cận và phân loại nhu cầu của doanh nghiệp trung tâm; tư vấn giải pháp; ký hợp đồng hợp tác tài trợ chuỗi; doanh nghiệp trung tâm giới thiệu doanh nghiệp vệ tinh; ngân hàng thẩm định, cấp hạn mức dựa trên uy tín và sức khỏe tài chính của doanh nghiệp trung tâm; giải ngân; phối hợp giám sát, đối soát, thu nợ.

**Code hiện trả:**

```json
{
  "event_type": "agreement_signing",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "BID",
      "name_normalized": "BID",
      "role": "unspecified",
      "name_source": "metadata"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `KHONG_CO_SU_KIEN`.

**Vì sao REJECTED / cần làm gì:** Đây là mô tả các bước quy trình tài trợ chuỗi, không phải bằng chứng BIDV đã ký một hợp đồng cụ thể. BID lấy từ metadata, không xác định được đối tác hay hợp đồng nào đã ký.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:f2bc443a-32bc-5cbc-a7a1-19639d9d9a69.

**Định vị:** `data/News/BID/batch_extracted.json` · snapshot `95336f9205db06d44e2df17e53a0fed09f55be657b65d4da236d863ed9d33954` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 6. BID · f2bc443a-32bc-5cbc-a7a1-19639d9d9a69 / e2

**Bằng chứng nguồn:**
> Tại Tọa đàm với các định chế tài chính, quỹ đầu tư Hoa Kỳ (New York, 23/9/2026), Tổng Bí thư, Chủ tịch nước Tô Lâm đã gợi mở một thước đo mới.

**Code hiện trả:**

```json
{
  "event_type": "conference_forum",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "BID",
      "name_normalized": "BID",
      "role": "unspecified",
      "name_source": "metadata"
    }
  ],
  "dates": {
    "event_date_start": "2026-09-23",
    "event_date_end": "2026-09-23",
    "date_precision": "day",
    "date_derived": false,
    "date_evidence": "23/9/2026",
    "date_candidates": [
      {
        "date": "2026-09-23",
        "derived": false,
        "evidence": "23/9/2026"
      }
    ]
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_CHU_THE`.

**Vì sao REJECTED / cần làm gì:** Đoạn tọa đàm New York nêu Tô Lâm và các định chế/quỹ Hoa Kỳ. Không có bằng chứng trong câu cho BIDV tham dự; parties=BID từ metadata không đủ chứng minh quan hệ với sự kiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:f2bc443a-32bc-5cbc-a7a1-19639d9d9a69.

**Định vị:** `data/News/BID/batch_extracted.json` · snapshot `95336f9205db06d44e2df17e53a0fed09f55be657b65d4da236d863ed9d33954` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 7. BID · 24a162ed-3e28-5492-853d-010d9a1134a9 / e1

**Bằng chứng nguồn:**
> Ở kỳ hạn 12 và 24 tháng, cả bốn ngân hàng cùng niêm yết lãi suất lần lượt 5,4%/năm và 5,5%/năm.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "5,4%",
    "5,5%",
    "2,6%",
    "5,4%",
    "5,5%",
    "5,4%",
    "3,5%",
    "8,75 triệu đồng"
  ]
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Đoạn nguồn đang nói niêm yết lãi suất tiền gửi, không phải niêm yết chứng khoán hay hành động vốn của doanh nghiệp. corporate_action được kích hoạt nhầm bởi từ “niêm yết”; cần loại trường hợp lãi suất khỏi trigger này.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:24a162ed-3e28-5492-853d-010d9a1134a9.

**Định vị:** `data/News/BID/batch_extracted.json` · snapshot `cbdc0bd877d3c96df50ef01df6a60e6a95682b0ea7f95064a601d3ad22986ee8` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 8. BID · 0e035ab2-cada-559c-adb1-0029e72dcbad / e1

**Bằng chứng nguồn:**
> Theo báo cáo tài chính hợp nhất quý III/2026, tổng tài sản của SACOMBANK đạt 1.057.398 tỷ đồng, tăng hơn 15% so với đầu năm và vượt kế hoạch đại hội cổ đông giao.

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "planned",
  "parties": [],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "1.057.398 tỷ đồng",
    "15%"
  ]
}
```

**Nhóm kết luận:** `KHONG_CO_SU_KIEN`.

**Vì sao REJECTED / cần làm gì:** Câu so sánh kết quả với kế hoạch Đại hội cổ đông chỉ nói mức thực hiện kế hoạch. Việc nhắc ĐHCĐ không chứng minh một cuộc họp mới; không lấy câu kết quả kinh doanh làm sự kiện họp.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:0e035ab2-cada-559c-adb1-0029e72dcbad.

**Định vị:** `data/News/BID/batch_extracted.json` · snapshot `65c56571eef0eb02d85e36d53c722928f27a344187efef20c05662257b58a718` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 9. BID · 856eedea-a092-55e0-86f6-5ecdea899819 / e1

**Bằng chứng nguồn:**
> Trong đó, Agribank có lợi thế tại các kỳ hạn ngắn, trong khi cả bốn ngân hàng cùng niêm yết lãi suất 5,4%/năm ở kỳ hạn 12 tháng và 5,5%/năm ở kỳ hạn 24 tháng.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "5,4%",
    "5,5%",
    "2,6%",
    "5,4%",
    "5,5%",
    "3,5%",
    "3,5 triệu đồng",
    "4,8%"
  ]
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Đoạn nguồn đang nói niêm yết lãi suất tiền gửi, không phải niêm yết chứng khoán hay hành động vốn của doanh nghiệp. corporate_action được kích hoạt nhầm bởi từ “niêm yết”; cần loại trường hợp lãi suất khỏi trigger này.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:856eedea-a092-55e0-86f6-5ecdea899819.

**Định vị:** `data/News/BID/batch_extracted.json` · snapshot `feca8203e6569b042e83fd5521739e497fcd95f3b404499434cce1cd564ae173` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 10. BID · 9cad8358-1095-590e-a3a3-1f26d4e54e6b / e1

**Bằng chứng nguồn:**
> BID: Nghị quyết HĐQT phê duyệt Phương án phát hành Trái phiếu tăng vốn BIDV theo hình thức riêng lẻ Quý IV/2026

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "BID",
      "name_normalized": "BID",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": "2026-10-14",
    "event_date_end": "2026-10-14",
    "date_precision": "day",
    "date_derived": false,
    "date_evidence": "14/10/2026",
    "date_candidates": [
      {
        "date": "2026-10-14",
        "derived": false,
        "evidence": "14/10/2026"
      }
    ]
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:9cad8358-1095-590e-a3a3-1f26d4e54e6b.

**Định vị:** `data/News/BID/batch_extracted.json` · snapshot `fd8e6959ad5e490915b11b3bb970dc613469a6c48783fcd5805f0883e79a5dfc` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 11. BID · 71bd1898-c81b-540e-8ef6-72027008ba00 / e1

**Bằng chứng nguồn:**
> BID: Nghị quyết HĐQT phê duyệt Phương án phát hành, phương án sử dụng và trả nợ vốn thu được từ các đợt phát hành trái phiếu tăng vốn BIDV ra công chúng

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "BID",
      "name_normalized": "BID",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": "2026-10-12",
    "event_date_end": "2026-10-12",
    "date_precision": "day",
    "date_derived": false,
    "date_evidence": "12/10/2026",
    "date_candidates": [
      {
        "date": "2026-10-12",
        "derived": false,
        "evidence": "12/10/2026"
      }
    ]
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:71bd1898-c81b-540e-8ef6-72027008ba00.

**Định vị:** `data/News/BID/batch_extracted.json` · snapshot `96b632c2558575a7c3bd7bcf01d52c3c36449fe203d68fafb9f4a21c78d0f8dc` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 12. BID · a713d99c-9c6c-53a3-b382-cb3a8fa68dcf / e1

**Bằng chứng nguồn:**
> BID: HĐQT thông qua nội dung hợp đồng cho BIC Thái Nguyên thuê trụ sở chi nhánh Cao Bằng trong thời gian chưa sử dụng hết

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "BID",
      "name_normalized": "BID",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:a713d99c-9c6c-53a3-b382-cb3a8fa68dcf.

**Định vị:** `data/News/BID/batch_extracted.json` · snapshot `c4359c200f5263cca327524afb6d568281c199337019bc4a0030f1b0e62468de` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 13. BID · 627cc126-1ddd-5d22-b59e-5798c024f2f0 / e1

**Bằng chứng nguồn:**
> BID: HĐQT thông qua việc cấp hạn mức đối với Keb Hana Bank Co.,LTD

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "BID",
      "name_normalized": "BID",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:627cc126-1ddd-5d22-b59e-5798c024f2f0.

**Định vị:** `data/News/BID/batch_extracted.json` · snapshot `2f4c2872e9f489b2f64f7b6121348934bb4db42e2bca68650e3e2ee731198c2b` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 14. BID · e73283d1-09a8-59b5-b769-9583dcc6ee97 / e1

**Bằng chứng nguồn:**
> BID: Nhận được thông báo về việc giao dịch chứng khoán thay đổi đăng ký niêm yết của HOSE

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "BID",
      "name_normalized": "BID",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_THUOC_TINH`.

**Vì sao REJECTED / cần làm gì:** Đây là thông báo/quyết định về niêm yết. Đầu ra chưa xác định vai trò bên phát hành (unspecified), trạng thái vẫn unconfirmed và chưa phân biệt ngày quyết định với ngày bắt đầu giao dịch. Chấp nhận bài làm bằng chứng thông báo, nhưng bản hiện tại chưa đủ để duyệt quan hệ sự kiện thực thi. Không suy ngày từ tên file đính kèm.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:e73283d1-09a8-59b5-b769-9583dcc6ee97.

**Định vị:** `data/News/BID/batch_extracted.json` · snapshot `98cc582cd7af83a98077ec134db6ee98c3e0da5e93b83051719f39fcdf696790` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 15. CMG · cac5c8c1-57f9-59e8-ba49-c65fc845ed62 / e1

**Bằng chứng nguồn:**
> Tập đoàn CMC giới thiệu hệ sinh thái AI C-PRODUCT tại Diễn đàn Kinh tế Mùa thu 2026

**Code hiện trả:**

```json
{
  "event_type": "conference_forum",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "CMG",
      "name_normalized": "CMG",
      "role": "unspecified",
      "name_source": "metadata"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_VAI_TRO`.

**Vì sao REJECTED / cần làm gì:** Nguồn có diễn đàn C-Product của CMC, nhưng parties chỉ có CMG lấy từ metadata với vai trò unspecified và status=unconfirmed. Cần chứng minh vai trò của CMC tại diễn đàn từ đoạn nguồn; không tự coi tag là organizer.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:cac5c8c1-57f9-59e8-ba49-c65fc845ed62.

**Định vị:** `data/News/CMG/batch_extracted.json` · snapshot `416fa71c8a2865b873ac1208cb7f3eae4a6380f3e8bbd948402d182890f3bd75` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 16. CMG · cac5c8c1-57f9-59e8-ba49-c65fc845ed62 / e2

**Bằng chứng nguồn:**
> Bên cạnh hoạt động triển lãm, ông Lê Minh, Giám đốc Công nghệ CMC TS, tham gia với vai trò diễn giả thảo luận tại phiên chuyên đề về “Năng lực tự chủ AI (AI Sovereign)”, chia sẻ góc nhìn về hạ tầng, dữ liệu, công nghệ và quản trị AI trong bối cảnh Việt Nam thúc đẩy chuyển đổi AI.

**Code hiện trả:**

```json
{
  "event_type": "exhibition_fair",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "CMG",
      "name_normalized": "CMG",
      "role": "unspecified",
      "name_source": "metadata"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_PHAM_VI_THUC_THE`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu diễn giả thuộc CMC TS. Bản chỉ giữ CMG từ metadata; cần phân biệt công ty thành viên, người phát biểu và công ty mẹ. Không tự nâng quan hệ của diễn giả/CMC TS thành vai trò tổ chức của CMG.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:cac5c8c1-57f9-59e8-ba49-c65fc845ed62.

**Định vị:** `data/News/CMG/batch_extracted.json` · snapshot `416fa71c8a2865b873ac1208cb7f3eae4a6380f3e8bbd948402d182890f3bd75` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 17. CMG · 8de11620-b1ea-5b5c-bf5b-0612def9d10a / e1

**Bằng chứng nguồn:**
> Trong chiến lược 2026 – 2030 được Tập đoàn đề ra trong Đại hội đồng cổ đông thường niên năm 2026 diễn ra cuối tháng 7, CMC xác định C-OpenAI, C-Product và AI-X là 3 trụ cột có mối liên hệ từ công nghệ đến sản phẩm và giá trị tạo ra.

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "CMG",
      "name_normalized": "CMG",
      "role": "unspecified",
      "name_source": "metadata"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_TRANG_THAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu đại hội CMC đã diễn ra cuối tháng 7/2026, nhưng đầu ra để unconfirmed và không giữ độ chính xác tháng, vai trò công ty cũng unspecified. Giữ sự kiện lịch sử cùng mốc tháng, không bịa ngày cụ thể.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:8de11620-b1ea-5b5c-bf5b-0612def9d10a.

**Định vị:** `data/News/CMG/batch_extracted.json` · snapshot `0c942721ed0f79617cc74ba714be94b05591d53b88d40b1cf2304cfc3f283f0f` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 18. CMG · 6cff2d8a-fd61-512b-a0ec-129e242b829d / e1

**Bằng chứng nguồn:**
> CMG: Nghị quyết HĐQT số 31 ngày 20/10/2026

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "CMG",
      "name_normalized": "CMG",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": "2026-10-20",
    "event_date_end": "2026-10-20",
    "date_precision": "day",
    "date_derived": false,
    "date_evidence": "20/10/2026",
    "date_candidates": [
      {
        "date": "2026-10-20",
        "derived": false,
        "evidence": "20/10/2026"
      },
      {
        "date": "2026-10-20",
        "derived": false,
        "evidence": "20/10/2026"
      }
    ]
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:6cff2d8a-fd61-512b-a0ec-129e242b829d.

**Định vị:** `data/News/CMG/batch_extracted.json` · snapshot `f3756af14189a142bae00a456e0fd2273904d111a9b0d1c836ed92ca639a70df` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 19. CMG · 0d144bab-7334-5af7-b2e3-2e241bda6ff9 / e1

**Bằng chứng nguồn:**
> CMG: Nghị quyết HĐQT về khoản vay của Trường Đại học CMC tại Ngân hàng SinoPac

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "CMG",
      "name_normalized": "CMG",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": "2026-10-20",
    "event_date_end": "2026-10-20",
    "date_precision": "day",
    "date_derived": false,
    "date_evidence": "20/10/2026",
    "date_candidates": [
      {
        "date": "2026-10-20",
        "derived": false,
        "evidence": "20/10/2026"
      }
    ]
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:0d144bab-7334-5af7-b2e3-2e241bda6ff9.

**Định vị:** `data/News/CMG/batch_extracted.json` · snapshot `5448d2a15cd5a53ce7a4eca7f5d80c273b48e0f569cf4c3da8f87e0a468dcbac` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 20. CMG · 04de7479-7368-59e0-9aee-42d014d669ce / e1

**Bằng chứng nguồn:**
> CMG: Nghị quyết HĐQT số 30/2026 ngày 19/10/2026

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "CMG",
      "name_normalized": "CMG",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": "2026-10-19",
    "event_date_end": "2026-10-19",
    "date_precision": "day",
    "date_derived": false,
    "date_evidence": "19/10/2026",
    "date_candidates": [
      {
        "date": "2026-10-19",
        "derived": false,
        "evidence": "19/10/2026"
      },
      {
        "date": "2026-10-19",
        "derived": false,
        "evidence": "19/10/2026"
      }
    ]
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:04de7479-7368-59e0-9aee-42d014d669ce.

**Định vị:** `data/News/CMG/batch_extracted.json` · snapshot `baa17a5aa54c4f5c96ff442e4e6a8a9a8737c840b84564c12f9629a33b77d70e` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 21. CMG · 699af6a6-92be-5139-8151-53644be324da / e1

**Bằng chứng nguồn:**
> CMG: Nghị quyết HĐQT điều chỉnh hạn mức tín dụng trung - dài hạn cấp cho Trường Đại học CMC

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "CMG",
      "name_normalized": "CMG",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": "2026-10-19",
    "event_date_end": "2026-10-19",
    "date_precision": "day",
    "date_derived": false,
    "date_evidence": "19/10/2026",
    "date_candidates": [
      {
        "date": "2026-10-19",
        "derived": false,
        "evidence": "19/10/2026"
      }
    ]
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:699af6a6-92be-5139-8151-53644be324da.

**Định vị:** `data/News/CMG/batch_extracted.json` · snapshot `613b7eeab98ab06dfc0f653808372b0781111ca756768f1f065c4e02786f394c` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 22. CMG · 37d2f293-7f42-579b-8156-42ab0bdacac6 / e1

**Bằng chứng nguồn:**
> CMG: Nghị quyết HĐQT về việc lựa chọn đơn vị kiểm toán độc lập cho năm tài chính 2026-2028

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "CMG",
      "name_normalized": "CMG",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:37d2f293-7f42-579b-8156-42ab0bdacac6.

**Định vị:** `data/News/CMG/batch_extracted.json` · snapshot `81a64156e26715e9a9e4c0025766887f9d27b3960253ea3ebd84f8eb5c6f7def` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 23. CMG · 0ba11895-2c8a-59b6-bb28-b2fd49f27dfb / e1

**Bằng chứng nguồn:**
> CMG: Nghị quyết HĐQT về việc lựa chọn đơn vị kiểm toán độc lập cho năm tài chính 2026-2028

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "CMG",
      "name_normalized": "CMG",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:0ba11895-2c8a-59b6-bb28-b2fd49f27dfb.

**Định vị:** `data/News/CMG/batch_extracted.json` · snapshot `48221f97271019873ecaae231c5fdf3bd623826fa20bb610f3aa4d9b3481bc2b` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 24. CMG · 841ac317-aef6-57c0-98f7-cdc9083389e2 / e1

**Bằng chứng nguồn:**
> CMG: Bổ nhiệm ông Đặng Tùng Sơn, ông Nguyễn Hải Sơn giữ chức Phó Chủ tịch EVP Tập đoàn từ 19.8.2026

**Code hiện trả:**

```json
{
  "event_type": "appointment",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "CMG",
      "name_normalized": "CMG",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_THUC_THE`.

**Vì sao REJECTED / cần làm gì:** Nguồn bổ nhiệm Đặng Tùng Sơn và Nguyễn Hải Sơn từ 19.8.2026, nhưng đầu ra không biểu diễn đủ hai người và mất ngày dấu chấm. Cần tách đúng người–chức vụ, giữ ngày hiệu lực; không duyệt một bản công ty đơn lẻ thay hai quan hệ nhân sự.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:841ac317-aef6-57c0-98f7-cdc9083389e2.

**Định vị:** `data/News/CMG/batch_extracted.json` · snapshot `0e8b461a8361a84c7e629a44bf4cdcc892a82f188efb3e164e559927130525db` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 25. CMG · 9cb068a6-e38c-53de-a0c2-564178959346 / e1

**Bằng chứng nguồn:**
> CMG: Nghị quyết HĐQT phê duyệt giao dịch với bên có liên quan

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "CMG",
      "name_normalized": "CMG",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:9cb068a6-e38c-53de-a0c2-564178959346.

**Định vị:** `data/News/CMG/batch_extracted.json` · snapshot `c66cd58f12aa21c24d2f671815970034724b2f6a2f056b05fb63ae044defe272` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 26. CTG · a46ed591-fe06-5e17-a880-dacb7fcf7675 / e1

**Bằng chứng nguồn:**
> Theo khoản 1 Điều 148 Luật Doanh nghiệp 2020, nếu điều lệ công ty không quy định tỷ lệ khác, các nghị quyết quan trọng của đại hội đồng cổ đông cần được ít nhất 65% tổng số phiếu biểu quyết của cổ đông dự họp tán thành.

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "65%"
  ]
}
```

**Nhóm kết luận:** `KHONG_CO_SU_KIEN`.

**Vì sao REJECTED / cần làm gì:** Nguồn giải thích quy định chung của Luật Doanh nghiệp và tỷ lệ biểu quyết 65%; không xác định công ty hay cuộc họp cụ thể. Không được tạo một sự kiện đại hội cổ đông từ ví dụ pháp luật này.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:a46ed591-fe06-5e17-a880-dacb7fcf7675.

**Định vị:** `data/News/CTG/batch_extracted.json` · snapshot `e770e6bb021e68524bea97121f90bae21f098da16c2ca16e0b130e773fed8fa6` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 27. CTG · 7189cb54-2dc4-5d75-a72f-8b3491d1b661 / e1

**Bằng chứng nguồn:**
> Biểu lãi suất tiền gửi tiết kiệm trực tiếp tại VietinBank hiện đang được niêm yết như sau: Lãi suất tiền gửi kỳ hạn 1 tháng không đổi, neo ở mức 2,1%/năm.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "CTG",
      "name_normalized": "CTG",
      "role": "unspecified",
      "name_source": "metadata"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "2,1%",
    "2,4%"
  ]
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Đoạn nguồn đang nói niêm yết lãi suất tiền gửi, không phải niêm yết chứng khoán hay hành động vốn của doanh nghiệp. corporate_action được kích hoạt nhầm bởi từ “niêm yết”; cần loại trường hợp lãi suất khỏi trigger này.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:7189cb54-2dc4-5d75-a72f-8b3491d1b661.

**Định vị:** `data/News/CTG/batch_extracted.json` · snapshot `08da4990e68c32a5ad4bb4ffad8ace59a2205a252a5fa303b198f95d9b8a58f6` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 28. CTG · fbced2c9-da5d-5995-a98f-e15260708b97 / e1

**Bằng chứng nguồn:**
> Ở kỳ hạn 12 và 24 tháng, cả bốn ngân hàng cùng niêm yết lãi suất lần lượt 5,4%/năm và 5,5%/năm.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "5,4%",
    "5,5%",
    "2,6%",
    "5,4%",
    "5,5%",
    "5,4%",
    "3,5%",
    "17,5 triệu đồng"
  ]
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Đoạn nguồn đang nói niêm yết lãi suất tiền gửi, không phải niêm yết chứng khoán hay hành động vốn của doanh nghiệp. corporate_action được kích hoạt nhầm bởi từ “niêm yết”; cần loại trường hợp lãi suất khỏi trigger này.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:fbced2c9-da5d-5995-a98f-e15260708b97.

**Định vị:** `data/News/CTG/batch_extracted.json` · snapshot `ec3b74bed639bf09c713284ccaae61694d5d25bba802818621d53ec441508d3e` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 29. CTG · 24a162ed-3e28-5492-853d-010d9a1134a9 / e1

**Bằng chứng nguồn:**
> Ở kỳ hạn 12 và 24 tháng, cả bốn ngân hàng cùng niêm yết lãi suất lần lượt 5,4%/năm và 5,5%/năm.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "5,4%",
    "5,5%",
    "2,6%",
    "5,4%",
    "5,5%",
    "5,4%",
    "3,5%",
    "8,75 triệu đồng"
  ]
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Đoạn nguồn đang nói niêm yết lãi suất tiền gửi, không phải niêm yết chứng khoán hay hành động vốn của doanh nghiệp. corporate_action được kích hoạt nhầm bởi từ “niêm yết”; cần loại trường hợp lãi suất khỏi trigger này.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:24a162ed-3e28-5492-853d-010d9a1134a9.

**Định vị:** `data/News/CTG/batch_extracted.json` · snapshot `cbdc0bd877d3c96df50ef01df6a60e6a95682b0ea7f95064a601d3ad22986ee8` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 30. CTG · 0e035ab2-cada-559c-adb1-0029e72dcbad / e1

**Bằng chứng nguồn:**
> Theo báo cáo tài chính hợp nhất quý III/2026, tổng tài sản của SACOMBANK đạt 1.057.398 tỷ đồng, tăng hơn 15% so với đầu năm và vượt kế hoạch đại hội cổ đông giao.

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "planned",
  "parties": [],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "1.057.398 tỷ đồng",
    "15%"
  ]
}
```

**Nhóm kết luận:** `KHONG_CO_SU_KIEN`.

**Vì sao REJECTED / cần làm gì:** Câu so sánh kết quả với kế hoạch Đại hội cổ đông chỉ nói mức thực hiện kế hoạch. Việc nhắc ĐHCĐ không chứng minh một cuộc họp mới; không lấy câu kết quả kinh doanh làm sự kiện họp.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:0e035ab2-cada-559c-adb1-0029e72dcbad.

**Định vị:** `data/News/CTG/batch_extracted.json` · snapshot `65c56571eef0eb02d85e36d53c722928f27a344187efef20c05662257b58a718` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 31. CTG · d4c3bbaf-cd79-5812-90d0-b1ec3f289572 / e1

**Bằng chứng nguồn:**
> Ngày 26/10, Sở Giao dịch Chứng khoán Hà Nội (HNX) công bố Số liệu Quản lý Sở hữu của Nhà đầu tư nước ngoài của các doanh nghiệp niêm yết trên sàn chứng khoán.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [],
  "dates": {
    "event_date_start": "2026-10-26",
    "event_date_end": "2026-10-26",
    "date_precision": "day",
    "date_derived": true,
    "date_evidence": "Ngày 26/10",
    "date_candidates": [
      {
        "date": "2026-10-26",
        "derived": true,
        "evidence": "Ngày 26/10"
      }
    ]
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn là HNX công bố thống kê sở hữu nước ngoài, không chứng minh doanh nghiệp thực hiện niêm yết/corporate action. parties rỗng; việc xuất hiện tên sở giao dịch không đủ tạo sự kiện niêm yết của một mã.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:d4c3bbaf-cd79-5812-90d0-b1ec3f289572.

**Định vị:** `data/News/CTG/batch_extracted.json` · snapshot `48546a2886cd3f25c719f9d9c5af2909cff995e752d705310b0bcd0b8979a564` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 32. CTG · 53831e97-23e4-559c-8db8-d244a29b2bc0 / e1

**Bằng chứng nguồn:**
> CTG: Nhận được các văn bản của HNX về việc hủy niêm yết trái phiếu CTG123033

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "CTG",
      "name_normalized": "CTG",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_THUOC_TINH`.

**Vì sao REJECTED / cần làm gì:** Đây là thông báo/quyết định về niêm yết. Đầu ra chưa xác định vai trò bên phát hành (unspecified), trạng thái vẫn unconfirmed và chưa phân biệt ngày quyết định với ngày bắt đầu giao dịch. Chấp nhận bài làm bằng chứng thông báo, nhưng bản hiện tại chưa đủ để duyệt quan hệ sự kiện thực thi. Không suy ngày từ tên file đính kèm.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:53831e97-23e4-559c-8db8-d244a29b2bc0.

**Định vị:** `data/News/CTG/batch_extracted.json` · snapshot `a4edc93b136f45a7980e515a9828ec071ff2c8f0d5193722169e6a91558f90f0` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 33. CTG · 09dd1531-c2c6-5eb4-a9d1-84e84d4c34fd / e1

**Bằng chứng nguồn:**
> CTG: HĐQT thông qua nội dung Văn bản sửa đổi bổ sung Hợp đồng kết nối giữa VietinBank và VietinBank FMC

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "CTG",
      "name_normalized": "CTG",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:09dd1531-c2c6-5eb4-a9d1-84e84d4c34fd.

**Định vị:** `data/News/CTG/batch_extracted.json` · snapshot `fa20e8e85b98bfc4bf27651486d80ee114caee1b0448fa39de82f5bc5dff8e2d` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 34. CTG · 5e10451a-a81f-5881-8ffe-2f02bf7c5b61 / e1

**Bằng chứng nguồn:**
> CTG: HĐQT thông qua nội dung Hợp đồng bảo hiểm mọi rủi ro tài sản với VBI

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "CTG",
      "name_normalized": "CTG",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:5e10451a-a81f-5881-8ffe-2f02bf7c5b61.

**Định vị:** `data/News/CTG/batch_extracted.json` · snapshot `c43e0c10e5eea353d2cc3e3aad1c096d45ee0e61bba9fb0b60e169371487c48f` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 35. CTG · 1446c480-6a7e-5845-81b3-da68a94251f7 / e1

**Bằng chứng nguồn:**
> CTG: CBTT HĐQT thông qua nội dung hợp đồng cầm cố, thế chấp giữa Vietinbank với VBI

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "CTG",
      "name_normalized": "CTG",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:1446c480-6a7e-5845-81b3-da68a94251f7.

**Định vị:** `data/News/CTG/batch_extracted.json` · snapshot `c9767bb13bb58635516997b8c7b76847092fdd3a69e3d26c7b1a37e34ef45ec7` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 36. CTG · 42764c58-aa87-5f90-a151-8eff194bad70 / e1

**Bằng chứng nguồn:**
> CTG: Nghị quyết HĐQT thông qua các nội dung liên quan đến phương án phát hành trái phiếu ra công chúng

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "CTG",
      "name_normalized": "CTG",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:42764c58-aa87-5f90-a151-8eff194bad70.

**Định vị:** `data/News/CTG/batch_extracted.json` · snapshot `38493a9e8013d8cbb27a61bedf04c6417753fe72ba84bf334e23daac9ed60579` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 37. CTG · 6b9f8796-054c-5c72-98d6-22a02eea4fc4 / e1

**Bằng chứng nguồn:**
> CTG: HĐQT thông qua nội dung Bản sửa đổi, bổ sung hợp đồng tư vấn và hợp đồng đại lý giữa Vietinbank và VBSE

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "CTG",
      "name_normalized": "CTG",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:6b9f8796-054c-5c72-98d6-22a02eea4fc4.

**Định vị:** `data/News/CTG/batch_extracted.json` · snapshot `601b521e8c758345bcd756e285ff4d51136fabccde88134dd5b9c352f4e7bf20` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 38. ELC · b591b72b-919e-5d23-b952-fefef7c4feb8 / e1

**Bằng chứng nguồn:**
> Tiếp nối đà tăng trưởng, doanh nghiệp công bố giá trị hợp đồng ký kết trong 8 tháng đầu năm 2026 tăng 126% so với cùng kỳ.

**Code hiện trả:**

```json
{
  "event_type": "agreement_signing",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "ELC",
      "name_normalized": "ELC",
      "role": "unspecified",
      "name_source": "metadata"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "126%"
  ]
}
```

**Nhóm kết luận:** `KHONG_CO_SU_KIEN_CU_THE`.

**Vì sao REJECTED / cần làm gì:** Nguồn tổng hợp giá trị hợp đồng ELC trong 8 tháng và tăng trưởng so với cùng kỳ, không chỉ ra một lần ký/hợp đồng/đối tác cụ thể. Không gộp kết quả kinh doanh thành một agreement_signing.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:b591b72b-919e-5d23-b952-fefef7c4feb8.

**Định vị:** `data/News/ELC/batch_extracted.json` · snapshot `aabd3917e1149e516ac6fb5e7d2e9bdfb54ed88eecb704977454b31069598e2e` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 39. ELC · a0652cd5-94bd-5193-a359-f21161abef4d / e1

**Bằng chứng nguồn:**
> ELC: Thông báo về việc niêm yết và giao dịch chứng khoán thay đổi niêm yết

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "ELC",
      "name_normalized": "ELC",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_THUOC_TINH`.

**Vì sao REJECTED / cần làm gì:** Đây là thông báo/quyết định về niêm yết. Đầu ra chưa xác định vai trò bên phát hành (unspecified), trạng thái vẫn unconfirmed và chưa phân biệt ngày quyết định với ngày bắt đầu giao dịch. Chấp nhận bài làm bằng chứng thông báo, nhưng bản hiện tại chưa đủ để duyệt quan hệ sự kiện thực thi. Không suy ngày từ tên file đính kèm.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:a0652cd5-94bd-5193-a359-f21161abef4d.

**Định vị:** `data/News/ELC/batch_extracted.json` · snapshot `37041cadaba3a8dcdf85293802f3cea5d1e321f40a693877b5386afa10e5545f` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 40. ELC · 297bfed7-5c3a-52e2-9453-ccde8bed48b0 / e1

**Bằng chứng nguồn:**
> ELC: 19.10.2026, giao dịch 7.700.890 cp niêm yết bổ sung

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "ELC",
      "name_normalized": "ELC",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "7.700.890 cp"
  ]
}
```

**Nhóm kết luận:** `MAT_NGAY`.

**Vì sao REJECTED / cần làm gì:** Nguồn ghi rõ ngày bằng dấu chấm nhưng dates.event_date_start và date_candidates bỏ mất. Phải giữ ngày đúng nghĩa trong câu (ngày giao dịch/niêm yết/hiệu lực nhân sự), không thay bằng ngày đăng bài. Bản hiện tại còn để vai trò unspecified; ca nhân sự cần định danh người được bổ nhiệm/miễn nhiệm.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:297bfed7-5c3a-52e2-9453-ccde8bed48b0.

**Định vị:** `data/News/ELC/batch_extracted.json` · snapshot `ecb740272a195a206458b0d1c7cf3ade4779b29919a1060060cbd86809047559` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 41. ELC · 4c2f94b4-6fd3-5de8-b60e-e49984d88625 / e1

**Bằng chứng nguồn:**
> ELC: Quyết định về việc thay đổi đăng ký niêm yết

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "ELC",
      "name_normalized": "ELC",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_THUOC_TINH`.

**Vì sao REJECTED / cần làm gì:** Đây là thông báo/quyết định về niêm yết. Đầu ra chưa xác định vai trò bên phát hành (unspecified), trạng thái vẫn unconfirmed và chưa phân biệt ngày quyết định với ngày bắt đầu giao dịch. Chấp nhận bài làm bằng chứng thông báo, nhưng bản hiện tại chưa đủ để duyệt quan hệ sự kiện thực thi. Không suy ngày từ tên file đính kèm.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:4c2f94b4-6fd3-5de8-b60e-e49984d88625.

**Định vị:** `data/News/ELC/batch_extracted.json` · snapshot `34a46a8639091b6398f4490ec30c607fdf26638f60180e5c2346683ed2b245eb` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 42. ELC · 6c79fa32-9af7-527b-b6b8-5f41512cc4ad / e1

**Bằng chứng nguồn:**
> ELC: 8.10.2026, niêm yết bổ sung 7.700.890 cp

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "ELC",
      "name_normalized": "ELC",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "7.700.890 cp"
  ]
}
```

**Nhóm kết luận:** `MAT_NGAY`.

**Vì sao REJECTED / cần làm gì:** Nguồn ghi rõ ngày bằng dấu chấm nhưng dates.event_date_start và date_candidates bỏ mất. Phải giữ ngày đúng nghĩa trong câu (ngày giao dịch/niêm yết/hiệu lực nhân sự), không thay bằng ngày đăng bài. Bản hiện tại còn để vai trò unspecified; ca nhân sự cần định danh người được bổ nhiệm/miễn nhiệm.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:6c79fa32-9af7-527b-b6b8-5f41512cc4ad.

**Định vị:** `data/News/ELC/batch_extracted.json` · snapshot `19165c3d237a941ba88c5cdafcef730ad8bc196affaae5fe8ee1fbf6af24b182` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 43. ELC · d9847e1e-c15e-5e47-ac4e-dd1f6ab28b7f / e1

**Bằng chứng nguồn:**
> ELC: Nghị quyết HĐQT số 03-09/2026 ngày 23/09/2026

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "ELC",
      "name_normalized": "ELC",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": [
      {
        "date": "2026-09-03",
        "derived": false,
        "evidence": "03-09/2026"
      },
      {
        "date": "2026-09-23",
        "derived": false,
        "evidence": "23/09/2026"
      },
      {
        "date": "2026-09-03",
        "derived": false,
        "evidence": "03-09/2026"
      },
      {
        "date": "2026-09-23",
        "derived": false,
        "evidence": "23/09/2026"
      }
    ]
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:d9847e1e-c15e-5e47-ac4e-dd1f6ab28b7f.

**Định vị:** `data/News/ELC/batch_extracted.json` · snapshot `12dc6de720e5346a7cd294610efea7c296e57ccd9790ce030d055761d21432d1` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 44. ELC · 01097e12-0c09-5662-a1be-a6648a5999db / e1

**Bằng chứng nguồn:**
> ELC: Nghị quyết HĐQT đăng ký tăng vốn Điều lệ do hoàn thành đợt phát hành cổ phiếu

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "ELC",
      "name_normalized": "ELC",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": [
      {
        "date": "2026-09-03",
        "derived": false,
        "evidence": "03-09/2026"
      },
      {
        "date": "2026-09-23",
        "derived": false,
        "evidence": "23/09/2026"
      }
    ]
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:01097e12-0c09-5662-a1be-a6648a5999db.

**Định vị:** `data/News/ELC/batch_extracted.json` · snapshot `714d7f9d946deca81a80519536f616a27898f6b56270b4e21d1a72b223f3c57e` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 45. ELC · c1d9b43c-5d30-5917-aba3-a16520fc7508 / e1

**Bằng chứng nguồn:**
> ELC: Đã phát hành 7.700.890 cp để trả cổ tức và tăng vốn cổ phần từ nguồn vốn CSH

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "ELC",
      "name_normalized": "ELC",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "7.700.890 cp"
  ]
}
```

**Nhóm kết luận:** `SAI_TRANG_THAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nói “Đã phát hành 7.700.890 cp” nhưng status vẫn unconfirmed, vai trò ELC unspecified. Số cổ phiếu có bằng chứng; cần thể hiện đúng doanh nghiệp phát hành và trạng thái hoàn tất thay vì duyệt nguyên bản còn bỏ ngỏ.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:c1d9b43c-5d30-5917-aba3-a16520fc7508.

**Định vị:** `data/News/ELC/batch_extracted.json` · snapshot `9d2d616691dd95572b1a5680a503079f5e85e795f84354b0620831dab6ee1d65` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 46. FPT · b421f949-205d-507e-b421-a988aeafee72 / e1

**Bằng chứng nguồn:**
> FPT: Cổ đông đón tin vui, nhận tạm ứng cổ tức năm 2026

**Đoạn nguồn bổ sung về trạng thái:**
> Theo kế hoạch, ngày chốt danh sách cổ đông hưởng quyền là 30/11 và ngày thực hiện chi trả cổ tức là 10/12.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "planned",
  "parties": [
    {
      "name_raw": "FPT",
      "name_normalized": "FPT",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": [
      {
        "date": "2026-11-30",
        "derived": true,
        "evidence": "ngày 30/11"
      },
      {
        "date": "2026-12-10",
        "derived": false,
        "evidence": "10/12/2026"
      }
    ]
  },
  "figures": []
}
```

**Nhóm kết luận:** `KE_HOACH_CHUA_DU_DIEU_KIEN`.

**Vì sao REJECTED / cần làm gì:** Nguồn ghi lịch chốt quyền/chi trả trong tương lai và đầu ra ghi planned. Đây là ghi nhận kế hoạch, không phải bằng chứng đã chi trả. REJECTED ở tiêu chí đưa vào graph sự kiện đã có hiệu lực; không kết luận trường planned là trích sai. Cần tách các mốc chốt quyền/chi trả và định danh bên phát hành trước khi xét bản thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:b421f949-205d-507e-b421-a988aeafee72.

**Định vị:** `data/News/FPT/batch_extracted.json` · snapshot `8cbdcdcad7212ca912edf8ada65d02d85e76a8528d085e1cf35ad8a4987b5778` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 47. FPT · b421f949-205d-507e-b421-a988aeafee72 / e2

**Bằng chứng nguồn:**
> Hội đồng quản trị Công ty Cổ phần FPT (HOSE: FPT ) đã thông qua nghị quyết chi trả cổ tức bằng tiền mặt với tỷ lệ 10% mệnh giá, tương ứng 1.000 đồng cho mỗi cổ phiếu.

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "occurred",
  "parties": [
    {
      "name_raw": "FPT",
      "name_normalized": "FPT",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "10% mệnh giá",
    "1.000 đồng",
    "2026 tỷ",
    "10%",
    "1 cổ phiếu",
    "1.000 đồng"
  ]
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:b421f949-205d-507e-b421-a988aeafee72.

**Định vị:** `data/News/FPT/batch_extracted.json` · snapshot `8cbdcdcad7212ca912edf8ada65d02d85e76a8528d085e1cf35ad8a4987b5778` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

**Lỗi số liệu bổ sung — ERR_NUMERIC_VALUE_MISREAD:** Năm đứng trước cụm tỷ lệ bị đọc thành số tiền.

**Giá trị code:** `2026 tỷ`. **Đối chiếu ngay với nguồn:**
> Cổ đông FPT sẽ được nhận tạm ứng cổ tức năm 2026 tỷ lệ 10% Theo đó, HĐQT FPT thông qua phương án tạm ứng cổ tức năm 2026 bằng tiền với tỷ lệ 10%/cổ phiếu (1 cổ phiếu nhận 1.000 đồng).

### REJECTED — 48. FPT · 5e3877c2-c985-5638-9c54-2a25e91d0bee / e1

**Bằng chứng nguồn:**
> FPT: Giá hiện tại Thay đổi Xem hồ sơ doanh nghiệp TIN MỚI Hội đồng quản trị CTCP FPT (HoSE: FPT) vừa thông qua phương án tạm ứng cổ tức đợt 1 năm 2026 bằng tiền mặt với tỷ lệ 10%, tương ứng 1.000 đồng/cổ phiếu.

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "FPT",
      "name_normalized": "FPT",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "10%",
    "1.000 đồng"
  ]
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:5e3877c2-c985-5638-9c54-2a25e91d0bee.

**Định vị:** `data/News/FPT/batch_extracted.json` · snapshot `4012f78ba38da0b5836950a7d876a81d8e05500c47bd632b19be06947878786f` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 49. FPT · 5e3877c2-c985-5638-9c54-2a25e91d0bee / e2

**Bằng chứng nguồn:**
> Ngày đăng ký cuối cùng để thực hiện quyền là 30/11/2026, thời gian thanh toán dự kiến vào ngày 10/12/2026.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "planned",
  "parties": [
    {
      "name_raw": "FPT",
      "name_normalized": "FPT",
      "role": "unspecified",
      "name_source": "metadata"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": [
      {
        "date": "2026-11-30",
        "derived": false,
        "evidence": "30/11/2026"
      },
      {
        "date": "2026-12-10",
        "derived": false,
        "evidence": "10/12/2026"
      },
      {
        "date": "2026-09-22",
        "derived": false,
        "evidence": "22/9/2026"
      }
    ]
  },
  "figures": [
    "10 cổ phiếu",
    "1 cổ phiếu"
  ]
}
```

**Nhóm kết luận:** `KE_HOACH_CHUA_DU_DIEU_KIEN`.

**Vì sao REJECTED / cần làm gì:** Nguồn ghi lịch chốt quyền/chi trả trong tương lai và đầu ra ghi planned. Đây là ghi nhận kế hoạch, không phải bằng chứng đã chi trả. REJECTED ở tiêu chí đưa vào graph sự kiện đã có hiệu lực; không kết luận trường planned là trích sai. Cần tách các mốc chốt quyền/chi trả và định danh bên phát hành trước khi xét bản thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:5e3877c2-c985-5638-9c54-2a25e91d0bee.

**Định vị:** `data/News/FPT/batch_extracted.json` · snapshot `4012f78ba38da0b5836950a7d876a81d8e05500c47bd632b19be06947878786f` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 50. FPT · 4bca1726-6958-56af-b37e-9128eebc85b1 / e1

**Bằng chứng nguồn:**
> FPT: Quyết định về việc thay đổi đăng ký niêm yết

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "FPT",
      "name_normalized": "FPT",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_THUOC_TINH`.

**Vì sao REJECTED / cần làm gì:** Đây là thông báo/quyết định về niêm yết. Đầu ra chưa xác định vai trò bên phát hành (unspecified), trạng thái vẫn unconfirmed và chưa phân biệt ngày quyết định với ngày bắt đầu giao dịch. Chấp nhận bài làm bằng chứng thông báo, nhưng bản hiện tại chưa đủ để duyệt quan hệ sự kiện thực thi. Không suy ngày từ tên file đính kèm.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:4bca1726-6958-56af-b37e-9128eebc85b1.

**Định vị:** `data/News/FPT/batch_extracted.json` · snapshot `0875e03990df0305baeab45d2c08ff7e0ec1aabd162f208dd9071571de18a407` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 51. FPT · f668f006-4121-50b1-8ad7-c8d07a2cf81a / e1

**Bằng chứng nguồn:**
> FPT: Quyết định về việc thay đổi đăng ký niêm yết

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "FPT",
      "name_normalized": "FPT",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_THUOC_TINH`.

**Vì sao REJECTED / cần làm gì:** Đây là thông báo/quyết định về niêm yết. Đầu ra chưa xác định vai trò bên phát hành (unspecified), trạng thái vẫn unconfirmed và chưa phân biệt ngày quyết định với ngày bắt đầu giao dịch. Chấp nhận bài làm bằng chứng thông báo, nhưng bản hiện tại chưa đủ để duyệt quan hệ sự kiện thực thi. Không suy ngày từ tên file đính kèm.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:f668f006-4121-50b1-8ad7-c8d07a2cf81a.

**Định vị:** `data/News/FPT/batch_extracted.json` · snapshot `febc1260328468b0c7b8a113cb4efa212bfc705f1d11ea82e5a6bcd97aacc8ca` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 52. FPT · a2376ef9-1828-54fa-a546-fd35582ccf18 / e1

**Bằng chứng nguồn:**
> FPT: Nghị quyết HĐQT số 02.10-2026 ngày 27/10/2026

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "FPT",
      "name_normalized": "FPT",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": "2026-10-27",
    "event_date_end": "2026-10-27",
    "date_precision": "day",
    "date_derived": false,
    "date_evidence": "27/10/2026",
    "date_candidates": [
      {
        "date": "2026-10-27",
        "derived": false,
        "evidence": "27/10/2026"
      },
      {
        "date": "2026-10-27",
        "derived": false,
        "evidence": "27/10/2026"
      }
    ]
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:a2376ef9-1828-54fa-a546-fd35582ccf18.

**Định vị:** `data/News/FPT/batch_extracted.json` · snapshot `4e6bc69b7b6b5f1074bf19e6589a59c61b88f15f56a6de51b894c063523f025c` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 53. FPT · 97d4e833-d620-56d9-998e-9fec40cc2c4b / e1

**Bằng chứng nguồn:**
> FPT: Nghị quyết HĐQT số 02.10-2026 ngày 27/10/2026

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "FPT",
      "name_normalized": "FPT",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": "2026-10-27",
    "event_date_end": "2026-10-27",
    "date_precision": "day",
    "date_derived": false,
    "date_evidence": "27/10/2026",
    "date_candidates": [
      {
        "date": "2026-10-27",
        "derived": false,
        "evidence": "27/10/2026"
      },
      {
        "date": "2026-10-27",
        "derived": false,
        "evidence": "27/10/2026"
      }
    ]
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:97d4e833-d620-56d9-998e-9fec40cc2c4b.

**Định vị:** `data/News/FPT/batch_extracted.json` · snapshot `f904d3a38eb288f10c8ecc0ce09b0760befddec9207f5751710b25a873ab6436` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 54. FPT · 0b635e3a-c673-5465-8578-ccb1c049103c / e1

**Bằng chứng nguồn:**
> Doanh nghiệp tập trung đơn giản hóa cơ cấu sở hữu, tái cấu trúc tài chính và ưu tiên giảm nợ vay trước khi chi trả cổ tức.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `KHONG_CO_SU_KIEN_CU_THE`.

**Vì sao REJECTED / cần làm gì:** Nguồn nói ưu tiên tái cấu trúc, giảm nợ trước khi chi trả cổ tức, không xác định một đợt cổ tức đã được quyết định/thực hiện. parties rỗng; không đủ sự kiện và chủ thể để duyệt.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:0b635e3a-c673-5465-8578-ccb1c049103c.

**Định vị:** `data/News/FPT/batch_extracted.json` · snapshot `057dd3db7ee5bcfa83d377d6a5658787c1c4590e10693159c8c0efb37c292a1c` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 55. FPT · e681ff07-f329-570e-b11b-1383fee16a27 / e1

**Bằng chứng nguồn:**
> Cạnh đó, việc FPT niêm yết bổ sung 10,82 triệu cổ phiếu ESOP (cổ phiếu được doanh nghiệp phát hành riêng cho cán bộ, nhân viên hoặc ban lãnh đạo với giá ưu đãi) vào cuối tháng 8.2026 và phát hành 10% cổ phiếu thưởng trong tháng 9.2026 làm gia tăng lượng cổ phiếu tự do chuyển nhượng đúng vào thời điểm cầu yếu cũng được cho là nguyên nhân đẩy giá cổ phiếu FPT vào chuỗi giảm kéo dài nhiều tháng qua.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "FPT",
      "name_normalized": "FPT",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "10,82 triệu cổ phiếu",
    "10%"
  ]
}
```

**Nhóm kết luận:** `GOP_SAI_SU_KIEN`.

**Vì sao REJECTED / cần làm gì:** Nguồn có hai hành động khác nhau: niêm yết ESOP cuối tháng 8/2026 và phát hành cổ phiếu thưởng tháng 9/2026. Bản gộp thành một corporate_action, bỏ mốc tháng và để unconfirmed. Cần tách hành động; nhận định “được cho là” nguyên nhân giảm giá phải giữ quy thuộc nguồn, không thành kết luận nhân quả đã xác minh.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:e681ff07-f329-570e-b11b-1383fee16a27.

**Định vị:** `data/News/FPT/batch_extracted.json` · snapshot `775086749bc1bcd1358f184927cebb4793473722ccf16dc4ae84ffae1c40438d` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 56. FPT · da798b5f-b750-54c0-91a1-570573d5dad3 / e1

**Bằng chứng nguồn:**
> Tại Đại hội đồng cổ đông thường niên năm 2026 diễn ra hồi tháng 4, Chủ tịch Trương Gia Bình cho biết tập đoàn hướng tới mô hình AI-Native trong 5 - 10 năm tới, với AI trở thành nền tảng vận hành và con người giữ vai trò trung tâm của sáng tạo.

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "FPT",
      "name_normalized": "FPT",
      "role": "unspecified",
      "name_source": "metadata"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_TRANG_THAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu ĐHĐCĐ FPT diễn ra hồi tháng 4/2026 nhưng bản để unconfirmed, ngày unknown và FPT từ metadata với vai trò unspecified. Cần giữ bằng chứng FPT trong ngữ cảnh, vai trò và độ chính xác tháng; không coi ngày unknown là không thể test.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:da798b5f-b750-54c0-91a1-570573d5dad3.

**Định vị:** `data/News/FPT/batch_extracted.json` · snapshot `0443c1b871742adc203e0137c557e7d2dd5189f9db68e334bcf15c50af4d0f1a` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 57. FPT · 829190a9-7533-5c74-85c8-7f126d2a1892 / e1

**Bằng chứng nguồn:**
> FPT: Giá hiện tại Thay đổi Xem hồ sơ doanh nghiệp TIN MỚI Tập đoàn FPT và Quandela, công ty sở hữu siêu máy tính lượng tử quang tử mạnh nhất thế giới, vừa, ký kết Biên bản ghi nhớ hợp tác nhằm phát triển năng lực nghiên cứu, tích hợp, đào tạo nguồn nhân lực và thúc đẩy ứng dụng công nghệ lượng tử tại Việt Nam.

**Code hiện trả:**

```json
{
  "event_type": "agreement_signing",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "FPT",
      "name_normalized": "FPT",
      "role": "counterparty",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_DOI_TAC`.

**Vì sao REJECTED / cần làm gì:** Câu nguồn nêu FPT và Quandela ký biên bản ghi nhớ, nhưng parties chỉ có FPT. Thiếu một bên ký đã có sẵn trong nguồn; cần nhận Quandela và trạng thái ký biên bản, không suy thành hợp đồng triển khai hoàn tất.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:829190a9-7533-5c74-85c8-7f126d2a1892.

**Định vị:** `data/News/FPT/batch_extracted.json` · snapshot `c1aa266790904aa8272f7fe278a8ab8f12937f22867792c3b3f2995715950cc9` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 58. FPT · e36e11a6-7773-54ae-a20a-d97ac033de20 / e1

**Bằng chứng nguồn:**
> Cùng với đó, FPT ra mắt MediSight, khung chuyển đổi AI chuyên biệt cho lĩnh vực y tế, kết hợp các tác tử AI (AI Agents), nền tảng dữ liệu và ứng dụng nghiệp vụ.

**Code hiện trả:**

```json
{
  "event_type": "product_launch",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "FPT",
      "name_normalized": "FPT",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "1 triệu"
  ]
}
```

**Nhóm kết luận:** `SAI_TRANG_THAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn khẳng định FPT ra mắt MediSight, nhưng status=unconfirmed và vai trò FPT unspecified. Nội dung ra mắt có căn cứ; bản hiện tại chưa thể hiện đúng trạng thái và vai trò bên giới thiệu sản phẩm.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:e36e11a6-7773-54ae-a20a-d97ac033de20.

**Định vị:** `data/News/FPT/batch_extracted.json` · snapshot `c740cd5c238281812733ddbc43c713201d1c3be04b96e0f43bb69d34bc3b3f0e` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 59. FPT · e36e11a6-7773-54ae-a20a-d97ac033de20 / e2

**Bằng chứng nguồn:**
> Tại Việt Nam, Tập đoàn ký kết hợp tác với Trung tâm Dữ liệu quốc gia trong các lĩnh vực dữ liệu, AI và điện toán hiệu năng cao.

**Code hiện trả:**

```json
{
  "event_type": "agreement_signing",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "FPT",
      "name_normalized": "FPT",
      "role": "unspecified",
      "name_source": "metadata"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_DOI_TAC`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu hợp tác với Trung tâm Dữ liệu quốc gia; bản chỉ giữ FPT từ metadata và bỏ đối tác đã được nêu. Cần nối “Tập đoàn” qua ngữ cảnh FPT và biểu diễn hai bên cùng phạm vi hợp tác.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:e36e11a6-7773-54ae-a20a-d97ac033de20.

**Định vị:** `data/News/FPT/batch_extracted.json` · snapshot `c740cd5c238281812733ddbc43c713201d1c3be04b96e0f43bb69d34bc3b3f0e` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 60. FPT · 62809fa7-df75-5223-ae65-209044c4e0e5 / e1

**Bằng chứng nguồn:**
> Tính đến cuối Quý 3/2026, tỷ trọng nắm giữ PNJ đã giảm xuống mức rất thấp: Quỹ Cổ phiếu Cổ tức (AIF) chỉ còn chiếm 1%, Quỹ Cổ phiếu Hàng đầu (BCF) còn hơn 1% và Quỹ Cổ phiếu Tăng trưởng (MGF) chỉ nhỉnh hơn 2% một chút.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "FPT",
      "name_normalized": "FPT",
      "role": "unspecified",
      "name_source": "metadata"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "1%",
    "2%"
  ]
}
```

**Nhóm kết luận:** `SAI_CHU_THE`.

**Vì sao REJECTED / cần làm gì:** Đoạn nguồn nói tỷ trọng PNJ của các quỹ AIF/BCF/MGF, nhưng parties lại là FPT từ metadata. Nguồn không chứng minh FPT thực hiện corporate action này; không được tạo quan hệ chỉ vì bài nằm trong thư mục FPT.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:62809fa7-df75-5223-ae65-209044c4e0e5.

**Định vị:** `data/News/FPT/batch_extracted.json` · snapshot `1641c698be2715a2cbcc328a75fab700a13d52a2d002a52d3c1323f0970dd587` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 61. ICT · b81646f0-8581-595b-9756-63a689ec798b / e1

**Bằng chứng nguồn:**
> ICT: Nghị quyết HĐQT về việc thông qua chủ trương chấp thuận các hợp đồng, giao dịch giữa CTIN và các bên có liên quan năm 2026

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "ICT",
      "name_normalized": "ICT",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:b81646f0-8581-595b-9756-63a689ec798b.

**Định vị:** `data/News/ICT/batch_extracted.json` · snapshot `079c13c7e35c214a0c15b67e98f1719742682f23a05d16adb2e1d358d0f55b8f` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 62. ICT · 906a534e-35e8-5420-a573-407e39bfe70e / e1

**Bằng chứng nguồn:**
> ICT: Nghị quyết HĐQT thông qua chủ trương chấp thuận các hợp đồng, giao dịch giữa CTIN và các bên có liên quan năm 2026

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "ICT",
      "name_normalized": "ICT",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:906a534e-35e8-5420-a573-407e39bfe70e.

**Định vị:** `data/News/ICT/batch_extracted.json` · snapshot `da196a8a42c72d1a82ab21811735d9b5b68674040145a575de3c73c3c2be0432` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 63. ITD · 3768423a-7ffc-59c1-aa01-e529ea70ae6c / e1

**Bằng chứng nguồn:**
> ITD: Thông báo về việc niêm yết và giao dịch chứng khoán thay đổi niêm yết

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "ITD",
      "name_normalized": "ITD",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_THUOC_TINH`.

**Vì sao REJECTED / cần làm gì:** Đây là thông báo/quyết định về niêm yết. Đầu ra chưa xác định vai trò bên phát hành (unspecified), trạng thái vẫn unconfirmed và chưa phân biệt ngày quyết định với ngày bắt đầu giao dịch. Chấp nhận bài làm bằng chứng thông báo, nhưng bản hiện tại chưa đủ để duyệt quan hệ sự kiện thực thi. Không suy ngày từ tên file đính kèm.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:3768423a-7ffc-59c1-aa01-e529ea70ae6c.

**Định vị:** `data/News/ITD/batch_extracted.json` · snapshot `dd49eeb362af4d662668d99b50a54db00db0f1b26f9265cf67ae7589d236b3ca` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 64. ITD · b0ebbed7-6934-5125-a9cd-be1d58634d53 / e1

**Bằng chứng nguồn:**
> ITD: 22.9.2026, giao dịch 4.710.245 cp niêm yết bổ sung

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "ITD",
      "name_normalized": "ITD",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "4.710.245 cp"
  ]
}
```

**Nhóm kết luận:** `MAT_NGAY`.

**Vì sao REJECTED / cần làm gì:** Nguồn ghi rõ ngày bằng dấu chấm nhưng dates.event_date_start và date_candidates bỏ mất. Phải giữ ngày đúng nghĩa trong câu (ngày giao dịch/niêm yết/hiệu lực nhân sự), không thay bằng ngày đăng bài. Bản hiện tại còn để vai trò unspecified; ca nhân sự cần định danh người được bổ nhiệm/miễn nhiệm.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:b0ebbed7-6934-5125-a9cd-be1d58634d53.

**Định vị:** `data/News/ITD/batch_extracted.json` · snapshot `367d1f8e265b9b01c912e6759c47e2ba140cd04963e669e423a10d2097d1d16e` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 65. ITD · 0f981fdd-e2f8-5552-ab54-ab2344fb210e / e1

**Bằng chứng nguồn:**
> ITD: Quyết định về việc thay đổi đăng ký niêm yết

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "ITD",
      "name_normalized": "ITD",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_THUOC_TINH`.

**Vì sao REJECTED / cần làm gì:** Đây là thông báo/quyết định về niêm yết. Đầu ra chưa xác định vai trò bên phát hành (unspecified), trạng thái vẫn unconfirmed và chưa phân biệt ngày quyết định với ngày bắt đầu giao dịch. Chấp nhận bài làm bằng chứng thông báo, nhưng bản hiện tại chưa đủ để duyệt quan hệ sự kiện thực thi. Không suy ngày từ tên file đính kèm.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:0f981fdd-e2f8-5552-ab54-ab2344fb210e.

**Định vị:** `data/News/ITD/batch_extracted.json` · snapshot `15fc0bbd66c8c7bdee3fb72fda30e6402abff25585a36816e1ba62aa6afa5bb8` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 66. ITD · 3a3a6751-7c34-549f-921f-cc7907ea9458 / e1

**Bằng chứng nguồn:**
> ITD: 11.9.2026, niêm yết bổ sung 4.710.245 cp

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "ITD",
      "name_normalized": "ITD",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "4.710.245 cp"
  ]
}
```

**Nhóm kết luận:** `MAT_NGAY`.

**Vì sao REJECTED / cần làm gì:** Nguồn ghi rõ ngày bằng dấu chấm nhưng dates.event_date_start và date_candidates bỏ mất. Phải giữ ngày đúng nghĩa trong câu (ngày giao dịch/niêm yết/hiệu lực nhân sự), không thay bằng ngày đăng bài. Bản hiện tại còn để vai trò unspecified; ca nhân sự cần định danh người được bổ nhiệm/miễn nhiệm.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:3a3a6751-7c34-549f-921f-cc7907ea9458.

**Định vị:** `data/News/ITD/batch_extracted.json` · snapshot `03331d57bddeb928828269b300cb809db0b8bbca364ad4131d299df4ebddc0d5` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 67. ITD · 2d74b0c4-fece-5510-8d60-09f4ba50f4d8 / e1

**Bằng chứng nguồn:**
> ITD: Thông báo ký hợp đồng kiểm toán BCTC 2026

**Code hiện trả:**

```json
{
  "event_type": "agreement_signing",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "ITD",
      "name_normalized": "ITD",
      "role": "counterparty",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_THUC_THE`.

**Vì sao REJECTED / cần làm gì:** Nguồn là thông báo ký hợp đồng kiểm toán, nhưng parties mới có ITD; thiếu bên kiểm toán và bằng chứng gắn đúng hợp đồng. Không bác việc có thông báo ký, nhưng chưa thể duyệt một quan hệ ký kết đầy đủ từ bản chỉ có một bên; cần đọc hợp đồng/thông báo chi tiết đã ghim.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:2d74b0c4-fece-5510-8d60-09f4ba50f4d8.

**Định vị:** `data/News/ITD/batch_extracted.json` · snapshot `2793eced7ee1675b6c466b4c4626169198040e90e9ddba72ba1fb7c6ed448770` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 68. ITD · 1ace1e56-2500-5d44-9417-30566e5213bb / e1

**Bằng chứng nguồn:**
> ITD: Thông báo ký hợp đồng kiểm toán BCTC 2026

**Code hiện trả:**

```json
{
  "event_type": "agreement_signing",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "ITD",
      "name_normalized": "ITD",
      "role": "counterparty",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_THUC_THE`.

**Vì sao REJECTED / cần làm gì:** Nguồn là thông báo ký hợp đồng kiểm toán, nhưng parties mới có ITD; thiếu bên kiểm toán và bằng chứng gắn đúng hợp đồng. Không bác việc có thông báo ký, nhưng chưa thể duyệt một quan hệ ký kết đầy đủ từ bản chỉ có một bên; cần đọc hợp đồng/thông báo chi tiết đã ghim.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:1ace1e56-2500-5d44-9417-30566e5213bb.

**Định vị:** `data/News/ITD/batch_extracted.json` · snapshot `186e8789a5e950197c276e50835feb30b3c4d76e3a88f84eed999c97b8e39140` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 69. ITD · cc625013-f2b1-52f7-9553-458d07ba8d96 / e1

**Bằng chứng nguồn:**
> ITD: Nghị quyết HĐQT về việc bổ nhiệm Giám đốc Tài chính

**Code hiện trả:**

```json
{
  "event_type": "appointment",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "ITD",
      "name_normalized": "ITD",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_THUC_THE`.

**Vì sao REJECTED / cần làm gì:** Bản bổ nhiệm chỉ giữ mã công ty; không có người được bổ nhiệm trong parties và vai trò công ty là unspecified. Tiêu đề/thông báo hiện có không đủ xác định đầy đủ người, chức vụ và thời điểm có hiệu lực. Cần đọc đúng quyết định đính kèm và ghim nguồn trước khi duyệt; không tự điền tên từ bài khác.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:cc625013-f2b1-52f7-9553-458d07ba8d96.

**Định vị:** `data/News/ITD/batch_extracted.json` · snapshot `77c40a7a9b275b804d2cd0a04eccf01e3f203d589699182a22a2c133f52920d3` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 70. ITD · ad5453a3-d532-56c2-8cd3-da318e99860c / e1

**Bằng chứng nguồn:**
> ITD: Nghị quyết HĐQT bổ nhiệm bà Nguyễn Thị Thu Sương giữ chức Giám đốc Tài chính từ 1.9.2026

**Code hiện trả:**

```json
{
  "event_type": "appointment",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "ITD",
      "name_normalized": "ITD",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `MAT_NGAY`.

**Vì sao REJECTED / cần làm gì:** Nguồn ghi rõ ngày bằng dấu chấm nhưng dates.event_date_start và date_candidates bỏ mất. Phải giữ ngày đúng nghĩa trong câu (ngày giao dịch/niêm yết/hiệu lực nhân sự), không thay bằng ngày đăng bài. Bản hiện tại còn để vai trò unspecified; ca nhân sự cần định danh người được bổ nhiệm/miễn nhiệm.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:ad5453a3-d532-56c2-8cd3-da318e99860c.

**Định vị:** `data/News/ITD/batch_extracted.json` · snapshot `2a32ecdbb62e6bb70acd11ae5b851333b1c88d71447710d5916440bfeb60c23b` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 71. ITD · 5d9a5566-4256-5703-b789-c80e0cee3d45 / e1

**Bằng chứng nguồn:**
> ITD: Bổ nhiệm bà Nguyễn Thị Thu Sương giữ chức Giám đốc Tài chính từ 1.9.2026

**Code hiện trả:**

```json
{
  "event_type": "appointment",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "ITD",
      "name_normalized": "ITD",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `MAT_NGAY`.

**Vì sao REJECTED / cần làm gì:** Nguồn ghi rõ ngày bằng dấu chấm nhưng dates.event_date_start và date_candidates bỏ mất. Phải giữ ngày đúng nghĩa trong câu (ngày giao dịch/niêm yết/hiệu lực nhân sự), không thay bằng ngày đăng bài. Bản hiện tại còn để vai trò unspecified; ca nhân sự cần định danh người được bổ nhiệm/miễn nhiệm.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:5d9a5566-4256-5703-b789-c80e0cee3d45.

**Định vị:** `data/News/ITD/batch_extracted.json` · snapshot `d6d22f1577793da52f81a4ef9ecf8841e6595394670d1d0490e67a8eed4ebdd4` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 72. ITD · ac011cb3-3618-5c0c-9ff3-44d5a68bfdc4 / e1

**Bằng chứng nguồn:**
> ITD: Nghị quyết HĐQT bổ nhiệm bà Nguyễn Thị Thu Sương giữ chức Giám đốc Tài chính

**Code hiện trả:**

```json
{
  "event_type": "appointment",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "ITD",
      "name_normalized": "ITD",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_THUC_THE`.

**Vì sao REJECTED / cần làm gì:** Nguồn đã nêu đích danh người được bổ nhiệm, nhưng parties chỉ chứa công ty với vai trò unspecified, không giữ người và quan hệ bổ nhiệm. Cần trích người cùng chức vụ từ chính câu, giữ riêng quyết định và ngày hiệu lực nếu được nguồn chứng minh.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:ac011cb3-3618-5c0c-9ff3-44d5a68bfdc4.

**Định vị:** `data/News/ITD/batch_extracted.json` · snapshot `d11d16ea210d3ac6173a0e64526102d6c353df59563b2a142aca0fee82741a1e` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 73. ITD · 37495d85-7f6c-598d-a39d-78d248ed7801 / e1

**Bằng chứng nguồn:**
> ITD: Nhận được công văn của UBCKNN về tài liệu báo cáo kết quả đợt phát hành CP để trả cổ tức

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "ITD",
      "name_normalized": "ITD",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_THUOC_TINH`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu công văn/báo cáo kết quả phát hành. Đầu ra chỉ giữ ITD vai trò unspecified và trạng thái unconfirmed; chưa tách sự kiện nhận/công bố kết quả khỏi sự kiện phát hành và chưa gắn vai trò doanh nghiệp. Không coi việc nhận công văn là ngày thực hiện phát hành.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:37495d85-7f6c-598d-a39d-78d248ed7801.

**Định vị:** `data/News/ITD/batch_extracted.json` · snapshot `7cf5f4918da80bf7065228eb0723151ae1018098304a037ba8e71110f93252d7` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 74. ITD · 4bebedcc-b371-5292-a095-d5ac88d1b004 / e1

**Bằng chứng nguồn:**
> ITD: Nhận được công văn của UBCKNN về tài liệu báo cáo kết quả đợt phát hành cổ phiếu để trả cổ tức

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "ITD",
      "name_normalized": "ITD",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_THUOC_TINH`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu công văn/báo cáo kết quả phát hành. Đầu ra chỉ giữ ITD vai trò unspecified và trạng thái unconfirmed; chưa tách sự kiện nhận/công bố kết quả khỏi sự kiện phát hành và chưa gắn vai trò doanh nghiệp. Không coi việc nhận công văn là ngày thực hiện phát hành.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:4bebedcc-b371-5292-a095-d5ac88d1b004.

**Định vị:** `data/News/ITD/batch_extracted.json` · snapshot `4d50666956fc013caa962a473ebe822979d2e17be37fc014674b98a04673d5e4` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 75. ITD · bb3c9d80-a43c-503a-aa68-a2e58f67b227 / e1

**Bằng chứng nguồn:**
> ITD: Nghị quyết HĐQT về việc thay đổi vốn điều lệ

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "ITD",
      "name_normalized": "ITD",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:bb3c9d80-a43c-503a-aa68-a2e58f67b227.

**Định vị:** `data/News/ITD/batch_extracted.json` · snapshot `59557a68f47c1baeecc6a7570d9ddb39b46c93b15b0a17c9c691c16ee53729f3` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 76. ITD · e869cfdd-745f-51f1-a800-4c8c3c893ee4 / e1

**Bằng chứng nguồn:**
> ITD: Nghị quyết HĐQT về việc thay đổi vốn điều lệ

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "ITD",
      "name_normalized": "ITD",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:e869cfdd-745f-51f1-a800-4c8c3c893ee4.

**Định vị:** `data/News/ITD/batch_extracted.json` · snapshot `e9a2c73418faab0f72f45bcc524ab5c606dbada90daf457e02c2e95ba2f3a1ba` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 77. ITD · d57e9a6b-00a8-5242-9c70-ac171ffb3365 / e1

**Bằng chứng nguồn:**
> ITD: Báo cáo kết quả đợt phát hành cổ phiếu để trả cổ tức

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "ITD",
      "name_normalized": "ITD",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_THUOC_TINH`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu công văn/báo cáo kết quả phát hành. Đầu ra chỉ giữ ITD vai trò unspecified và trạng thái unconfirmed; chưa tách sự kiện nhận/công bố kết quả khỏi sự kiện phát hành và chưa gắn vai trò doanh nghiệp. Không coi việc nhận công văn là ngày thực hiện phát hành.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:d57e9a6b-00a8-5242-9c70-ac171ffb3365.

**Định vị:** `data/News/ITD/batch_extracted.json` · snapshot `38fb9380eb57973d3f1ce2c7ae6b9f50f95c3051fde3fa25654d2f955c7b5284` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 78. MBB · 7766c8c6-1170-57ad-9e1a-7977b31373e9 / e1

**Bằng chứng nguồn:**
> Một trong số đó có ông Nguyễn Thành Tiến, ủy viên HĐQT VLA - người tổ chức các khóa học, hội thảo chia sẻ kinh nghiệm đầu tư bất động sản, tài chính và kinh doanh.

**Code hiện trả:**

```json
{
  "event_type": "conference_forum",
  "status": "unconfirmed",
  "parties": [],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `KHONG_CO_SU_KIEN_CU_THE`.

**Vì sao REJECTED / cần làm gì:** Nguồn mô tả ông Nguyễn Thành Tiến là người tổ chức các khóa học/hội thảo nói chung, không xác định một hội thảo cụ thể, ngày hay tổ chức tham gia. parties rỗng; không tạo conference_forum từ mô tả nghề nghiệp.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:7766c8c6-1170-57ad-9e1a-7977b31373e9.

**Định vị:** `data/News/MBB/batch_extracted.json` · snapshot `a96193d2ac3678f77cc538ce60f3be32791c7d697fb3c29784195cac734b2600` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 79. MBB · 58ba5f59-5da6-5080-a97e-40ec3ec1e0d1 / e1

**Bằng chứng nguồn:**
> MBB: HĐQT thông qua hợp đồng, giao dịch giữa MB và Viettel Dominicana

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "MBB",
      "name_normalized": "MBB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:58ba5f59-5da6-5080-a97e-40ec3ec1e0d1.

**Định vị:** `data/News/MBB/batch_extracted.json` · snapshot `f59656ee39066fe081d9d815b2d20699583855a2cf8dbab3345d3fbb8ab6c265` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 80. MBB · 1546c0c6-ba4a-5268-96ee-987e92ecb178 / e1

**Bằng chứng nguồn:**
> MBB: HĐQT thông qua hợp đồng, giao dịch giữa MB và Viettel Dominicana

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "MBB",
      "name_normalized": "MBB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:1546c0c6-ba4a-5268-96ee-987e92ecb178.

**Định vị:** `data/News/MBB/batch_extracted.json` · snapshot `a34cbefdaba186aaf653dd51bcea1e0ab8593af51911de660b73433f039c7e06` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 81. MBB · 5d5aa869-b0a3-56a2-a5c5-a609415ed41f / e1

**Bằng chứng nguồn:**
> Gửi tại quầy: VPBank niêm yết lãi suất 6,4%/năm Theo biểu lãi suất áp dụng từ ngày 24/10/2026, VPBank niêm yết lãi suất tiền gửi tại quầy kỳ hạn 12 tháng ở mức 6,4%/năm đối với khoản tiền dưới 1 tỷ đồng.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "VPB",
      "name_normalized": "VPB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": "2026-10-24",
    "event_date_end": "2026-10-24",
    "date_precision": "day",
    "date_derived": false,
    "date_evidence": "24/10/2026",
    "date_candidates": [
      {
        "date": "2026-10-24",
        "derived": false,
        "evidence": "24/10/2026"
      }
    ]
  },
  "figures": [
    "6,4%",
    "1 tỷ đồng"
  ]
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Đoạn nguồn đang nói niêm yết lãi suất tiền gửi, không phải niêm yết chứng khoán hay hành động vốn của doanh nghiệp. corporate_action được kích hoạt nhầm bởi từ “niêm yết”; cần loại trường hợp lãi suất khỏi trigger này.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:5d5aa869-b0a3-56a2-a5c5-a609415ed41f.

**Định vị:** `data/News/MBB/batch_extracted.json` · snapshot `58e4a23a3bcefbc50ff0a737058f6cd5d26a359808ed492f15baefadfbedfca7` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 82. MBB · 5d5aa869-b0a3-56a2-a5c5-a609415ed41f / e2

**Bằng chứng nguồn:**
> SHB và MB cùng niêm yết lãi suất tại quầy ở mức 5,7%/năm.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "5,7%",
    "6,8%",
    "50 triệu đồng",
    "500 triệu đồng",
    "6,0%"
  ]
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Đoạn nguồn đang nói niêm yết lãi suất tiền gửi, không phải niêm yết chứng khoán hay hành động vốn của doanh nghiệp. corporate_action được kích hoạt nhầm bởi từ “niêm yết”; cần loại trường hợp lãi suất khỏi trigger này.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:5d5aa869-b0a3-56a2-a5c5-a609415ed41f.

**Định vị:** `data/News/MBB/batch_extracted.json` · snapshot `58e4a23a3bcefbc50ff0a737058f6cd5d26a359808ed492f15baefadfbedfca7` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 83. MBB · 5d5aa869-b0a3-56a2-a5c5-a609415ed41f / e3

**Bằng chứng nguồn:**
> HDBank niêm yết lãi suất tiết kiệm thông thường kỳ hạn 12 tháng ở mức 5,2%/năm.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "HDB",
      "name_normalized": "HDB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "5,2%",
    "5,3%"
  ]
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Đoạn nguồn đang nói niêm yết lãi suất tiền gửi, không phải niêm yết chứng khoán hay hành động vốn của doanh nghiệp. corporate_action được kích hoạt nhầm bởi từ “niêm yết”; cần loại trường hợp lãi suất khỏi trigger này.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:5d5aa869-b0a3-56a2-a5c5-a609415ed41f.

**Định vị:** `data/News/MBB/batch_extracted.json` · snapshot `58e4a23a3bcefbc50ff0a737058f6cd5d26a359808ed492f15baefadfbedfca7` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 84. MBB · d4c3bbaf-cd79-5812-90d0-b1ec3f289572 / e1

**Bằng chứng nguồn:**
> Ngày 26/10, Sở Giao dịch Chứng khoán Hà Nội (HNX) công bố Số liệu Quản lý Sở hữu của Nhà đầu tư nước ngoài của các doanh nghiệp niêm yết trên sàn chứng khoán.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [],
  "dates": {
    "event_date_start": "2026-10-26",
    "event_date_end": "2026-10-26",
    "date_precision": "day",
    "date_derived": true,
    "date_evidence": "Ngày 26/10",
    "date_candidates": [
      {
        "date": "2026-10-26",
        "derived": true,
        "evidence": "Ngày 26/10"
      }
    ]
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn là HNX công bố thống kê sở hữu nước ngoài, không chứng minh doanh nghiệp thực hiện niêm yết/corporate action. parties rỗng; việc xuất hiện tên sở giao dịch không đủ tạo sự kiện niêm yết của một mã.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:d4c3bbaf-cd79-5812-90d0-b1ec3f289572.

**Định vị:** `data/News/MBB/batch_extracted.json` · snapshot `48546a2886cd3f25c719f9d9c5af2909cff995e752d705310b0bcd0b8979a564` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 85. MBB · dea88a59-6d75-5214-887c-8bda3249fb63 / e1

**Bằng chứng nguồn:**
> Vietcombank, VietinBank, BIDV, Agribank, MB, HDBank...đều có mặt ký kết thỏa thuận.

**Code hiện trả:**

```json
{
  "event_type": "agreement_signing",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "HDB",
      "name_normalized": "HDB",
      "role": "counterparty",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_DOI_TAC`.

**Vì sao REJECTED / cần làm gì:** Nguồn liệt kê Vietcombank, VietinBank, BIDV, Agribank, MB, HDBank cùng ký, nhưng bản chỉ giữ HDB. Thiếu nhiều bên được nêu trực tiếp; chưa đủ xác định từng thỏa thuận và cặp bên ký, không tự nối tất cả ngân hàng với nhau.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:dea88a59-6d75-5214-887c-8bda3249fb63.

**Định vị:** `data/News/MBB/batch_extracted.json` · snapshot `c9fa9cf599f732a043174b2aea64365f742c1c9aa9c75d1a0b194a6949d8ba6a` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 86. MBB · dea88a59-6d75-5214-887c-8bda3249fb63 / e2

**Bằng chứng nguồn:**
> Tại Hội nghị "Ngành Ngân hàng đồng hành khơi thông nguồn lực Tài chính – Ngân hàng phục vụ tăng trưởng vùng Đông Nam bộ giai đoạn 2026 – 2030" ngày 23/10/2026 do NHNN và UBND TP HCM tổ chức, các ngân hàng và doanh nghiệp đã trao tới 20 thỏa thuận hợp tác cho các dự án, phương án kinh doanh với tổng số tiền khoảng 230 nghìn tỷ đồng.

**Code hiện trả:**

```json
{
  "event_type": "agreement_signing",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "NHNN và UBND TP HCM",
      "name_normalized": "NHNN và UBND TP HCM",
      "role": "organizer",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": "2026-10-23",
    "event_date_end": "2026-10-23",
    "date_precision": "day",
    "date_derived": false,
    "date_evidence": "23/10/2026",
    "date_candidates": [
      {
        "date": "2026-10-23",
        "derived": false,
        "evidence": "23/10/2026"
      }
    ]
  },
  "figures": [
    "230 nghìn"
  ]
}
```

**Nhóm kết luận:** `SAI_VAI_TRO_VA_DON_VI`.

**Vì sao REJECTED / cần làm gì:** NHNN và UBND TP HCM là hai đơn vị tổ chức hội nghị, nhưng bị giữ thành một party organizer của agreement_signing. Các bên thực sự ký bị thiếu. Nguồn ghi khoảng “230 nghìn tỷ đồng”, value_raw chỉ giữ “230 nghìn”, mất đơn vị tỷ đồng. Cần tách hội nghị khỏi các thỏa thuận và giữ đầy đủ đơn vị.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:dea88a59-6d75-5214-887c-8bda3249fb63.

**Định vị:** `data/News/MBB/batch_extracted.json` · snapshot `c9fa9cf599f732a043174b2aea64365f742c1c9aa9c75d1a0b194a6949d8ba6a` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 87. MBB · dea88a59-6d75-5214-887c-8bda3249fb63 / e3

**Bằng chứng nguồn:**
> Trong đó HDBank và Vikki Bank đã trao 5 thỏa thuận hợp tác, Vietcombank tài trợ trao 4 thỏa thuận hợp tác, VietinBank, BIDV, Agribank, MBBank, NCB mỗi ngân hàng trao 2 thỏa thuận hợp tác (bao gồm cả thỏa thuận đồng tài trợ của các ngân hàng) và ACB đã trao 1 thỏa thuận hợp tác.

**Code hiện trả:**

```json
{
  "event_type": "agreement_signing",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "HDB",
      "name_normalized": "HDB",
      "role": "counterparty",
      "name_source": "sentence"
    },
    {
      "name_raw": "MBB",
      "name_normalized": "MBB",
      "role": "counterparty",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `GOP_SAI_SU_KIEN`.

**Vì sao REJECTED / cần làm gì:** Nguồn tổng hợp nhiều thỏa thuận riêng của HDBank/Vikki, Vietcombank và các ngân hàng khác; bản chỉ giữ HDB và MBB làm counterparties của một event. Không chứng minh HDB ký trực tiếp với MBB trong cùng thỏa thuận; cần tách nhóm và đối tác đúng nguồn.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:dea88a59-6d75-5214-887c-8bda3249fb63.

**Định vị:** `data/News/MBB/batch_extracted.json` · snapshot `c9fa9cf599f732a043174b2aea64365f742c1c9aa9c75d1a0b194a6949d8ba6a` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 88. MBB · dea88a59-6d75-5214-887c-8bda3249fb63 / e4

**Bằng chứng nguồn:**
> Các dự án, phương án kinh doanh mà các NHTM và doanh nghiệp trao thỏa thuận tại Hội nghị thuộc đa dạng các ngành, lĩnh vực như: công nghiệp chế tạo, năng lượng, dược phẩm, hạ tầng giao thông, khu công nghiệp, nhà ở xã hội, ...

**Code hiện trả:**

```json
{
  "event_type": "conference_forum",
  "status": "unconfirmed",
  "parties": [],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_THUC_THE`.

**Vì sao REJECTED / cần làm gì:** Câu chỉ liệt kê ngành của các dự án tại hội nghị; bản có parties=[] và không giữ định danh hội nghị/ngân hàng tham gia. Có thể dùng làm chi tiết hội nghị đã định danh, không duyệt như một sự kiện riêng không chủ thể.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:dea88a59-6d75-5214-887c-8bda3249fb63.

**Định vị:** `data/News/MBB/batch_extracted.json` · snapshot `c9fa9cf599f732a043174b2aea64365f742c1c9aa9c75d1a0b194a6949d8ba6a` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 89. MBB · 43c9d2b7-5403-5b46-87cb-5947a06b2406 / e1

**Bằng chứng nguồn:**
> KBSV và Ngân hàng MB ký kết hợp tác phát triển dịch vụ tài chính số

**Code hiện trả:**

```json
{
  "event_type": "agreement_signing",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "MBB",
      "name_normalized": "MBB",
      "role": "unspecified",
      "name_source": "metadata"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_DOI_TAC`.

**Vì sao REJECTED / cần làm gì:** Nguồn ghi KBSV và Ngân hàng MB ký kết. Bản bỏ KBSV, chỉ có MBB từ metadata với vai trò unspecified. Cần nhận alias MB và giữ bằng chứng hai bên ký, không suy từ tag.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:43c9d2b7-5403-5b46-87cb-5947a06b2406.

**Định vị:** `data/News/MBB/batch_extracted.json` · snapshot `5601dc35e9099f74a816545f041ed352b1917d5b5de8fd22852b7544a56679d1` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 90. MBB · 4e0e8f89-a310-53b1-808c-62e28f9e1c32 / e1

**Bằng chứng nguồn:**
> Đây là số cổ phiếu tăng thêm từ cổ tức được chia hằng năm.

**Đoạn nguồn bổ sung về trạng thái:**
> Giá chuyển nhượng tối thiểu được phê duyệt là 20.290 đồng/cổ phiếu, trên cơ sở chứng thư thẩm định giá do VAE phát hành ngày 25/09/2026.﻿ Giao dịch dự kiến thực hiện từ quý 4/2026 theo hình thức bán công khai, khớp lệnh trên Sở Giao dịch Chứng khoán Thành phố Hồ Chí Minh (HOSE).

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "planned",
  "parties": [
    {
      "name_raw": "MBB",
      "name_normalized": "MBB",
      "role": "unspecified",
      "name_source": "metadata"
    }
  ],
  "dates": {
    "event_date_start": "2026-09-25",
    "event_date_end": "2026-09-25",
    "date_precision": "day",
    "date_derived": false,
    "date_evidence": "25/09/2026",
    "date_candidates": [
      {
        "date": "2026-09-25",
        "derived": false,
        "evidence": "25/09/2026"
      }
    ]
  },
  "figures": [
    "20.290 đồng",
    "15%",
    "10.000 đồng"
  ]
}
```

**Nhóm kết luận:** `SAI_NGHIA_NGAY`.

**Vì sao REJECTED / cần làm gì:** 25/09/2026 là ngày VAE phát hành chứng thư thẩm định giá, không phải ngày chuyển nhượng cổ phiếu. Code gán ngày này thành event_date_start; nguồn nói giao dịch dự kiến quý 4/2026. Cần tách ngày chứng thư khỏi lịch giao dịch; không đổi kế hoạch thành giao dịch đã xảy ra.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:4e0e8f89-a310-53b1-808c-62e28f9e1c32.

**Định vị:** `data/News/MBB/batch_extracted.json` · snapshot `025a981ea953f233bb274b0e01f3b23b96ed4f15d0b97186de1bf3a49faaa390` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 91. TCB · 88c6bd2b-8992-52b1-b8e8-5270b3a1f331 / e1

**Bằng chứng nguồn:**
> TCB: Techcombank bổ nhiệm một Phó Tổng Giám đốc

**Code hiện trả:**

```json
{
  "event_type": "appointment",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "TCB",
      "name_normalized": "TCB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_THUC_THE`.

**Vì sao REJECTED / cần làm gì:** Bài có quyết định bổ nhiệm Phan Thị Hải Yến nhưng parties chỉ giữ TCB unspecified, không giữ người/chức vụ/ngày hiệu lực. Cần dùng phần nội dung của chính bài để hoàn thiện quan hệ, không chỉ giữ trigger tiêu đề.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:88c6bd2b-8992-52b1-b8e8-5270b3a1f331.

**Định vị:** `data/News/TCB/batch_extracted.json` · snapshot `6812a59c5ea9a25c0608d1a9882fed7ba7e5486489db797cf79fee97a0fc880c` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 92. TCB · 88c6bd2b-8992-52b1-b8e8-5270b3a1f331 / e2

**Bằng chứng nguồn:**
> Trong một diễn biến khác, HĐQT TCB đã ban hành Nghị quyết thông qua việc tăng vốn góp của Techcombank tại Công ty CP Bảo hiểm Phi Nhân thọ Techcom (TCGIns) theo báo cáo, đề xuất của Tổng giám đốc và các Khối Tài chính & Kế hoạch, Quản trị rủi ro, Quản trị Ngân hàng tại Tờ trình số 105/2026/TTr-TCKH ngày 25/9/2026.

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "planned",
  "parties": [
    {
      "name_raw": "TCB",
      "name_normalized": "TCB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": "2026-09-25",
    "event_date_end": "2026-09-25",
    "date_precision": "day",
    "date_derived": false,
    "date_evidence": "25/9/2026",
    "date_candidates": [
      {
        "date": "2026-09-25",
        "derived": false,
        "evidence": "25/9/2026"
      }
    ]
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:88c6bd2b-8992-52b1-b8e8-5270b3a1f331.

**Định vị:** `data/News/TCB/batch_extracted.json` · snapshot `6812a59c5ea9a25c0608d1a9882fed7ba7e5486489db797cf79fee97a0fc880c` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 93. TCB · 88c6bd2b-8992-52b1-b8e8-5270b3a1f331 / e3

**Bằng chứng nguồn:**
> Ngoài ra, HĐQT Techcombank còn phê duyệt ngày đăng ký cuối cùng chốt danh sách cổ đông để lấy ý kiến bằng văn bản về việc thành lập ngân hàng thương mại TNHH một thành viên do Techcombank sở hữu 100% vốn tại VIFC.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "TCB",
      "name_normalized": "TCB",
      "role": "unspecified",
      "name_source": "metadata"
    }
  ],
  "dates": {
    "event_date_start": "2026-11-03",
    "event_date_end": "2026-11-03",
    "date_precision": "day",
    "date_derived": false,
    "date_evidence": "3/11/2026",
    "date_candidates": [
      {
        "date": "2026-11-03",
        "derived": false,
        "evidence": "3/11/2026"
      }
    ]
  },
  "figures": [
    "100%"
  ]
}
```

**Nhóm kết luận:** `SAI_TRANG_THAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn phê duyệt lịch lấy ý kiến, ngày chốt 3/11/2026 còn ở tương lai tại mốc test và chưa chứng minh đã thành lập ngân hàng. Bản unconfirmed chưa phân biệt quyết định đã phê duyệt với lịch chốt quyền và kết quả thành lập; không duyệt các kết luận đó thành một sự kiện thực thi.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:88c6bd2b-8992-52b1-b8e8-5270b3a1f331.

**Định vị:** `data/News/TCB/batch_extracted.json` · snapshot `6812a59c5ea9a25c0608d1a9882fed7ba7e5486489db797cf79fee97a0fc880c` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 94. TCB · be1904cb-6368-50d7-9990-36ae5d76d02f / e1

**Bằng chứng nguồn:**
> Sacombank dẫn đầu với 7,3%/năm, tiếp đến là VPBank với 7,1%/năm; VCBNeo và MBV cùng niêm yết 7%/năm.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "VPB",
      "name_normalized": "VPB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "7,3%",
    "7,1%",
    "7%",
    "4,75%"
  ]
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Đoạn nguồn đang nói niêm yết lãi suất tiền gửi, không phải niêm yết chứng khoán hay hành động vốn của doanh nghiệp. corporate_action được kích hoạt nhầm bởi từ “niêm yết”; cần loại trường hợp lãi suất khỏi trigger này.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:be1904cb-6368-50d7-9990-36ae5d76d02f.

**Định vị:** `data/News/TCB/batch_extracted.json` · snapshot `2825b0494fcb1df6ff2cb23880853eba2b094e73f94bf442dba4d83e8055421e` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 95. TCB · be1904cb-6368-50d7-9990-36ae5d76d02f / e2

**Bằng chứng nguồn:**
> Techcombank và GPBank cùng niêm yết 5,5%/năm; ABBank 5,3%/năm; Eximbank và HDBank cùng 5%/năm; SeABank 4,75%/năm; KienlongBank 4,65%/năm và SCB 3,9%/năm.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "ABB",
      "name_normalized": "ABB",
      "role": "unspecified",
      "name_source": "sentence"
    },
    {
      "name_raw": "HDB",
      "name_normalized": "HDB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "5,5%",
    "5,3%",
    "5%",
    "4,75%",
    "4,65%",
    "3,9%"
  ]
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Đoạn nguồn đang nói niêm yết lãi suất tiền gửi, không phải niêm yết chứng khoán hay hành động vốn của doanh nghiệp. corporate_action được kích hoạt nhầm bởi từ “niêm yết”; cần loại trường hợp lãi suất khỏi trigger này.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:be1904cb-6368-50d7-9990-36ae5d76d02f.

**Định vị:** `data/News/TCB/batch_extracted.json` · snapshot `2825b0494fcb1df6ff2cb23880853eba2b094e73f94bf442dba4d83e8055421e` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 96. TCB · be1904cb-6368-50d7-9990-36ae5d76d02f / e3

**Bằng chứng nguồn:**
> Sacombank, VCBNeo, MBV, PGBank và VIB cùng niêm yết 7%/năm; BVBank ở mức 6,9%/năm; MSB, BIDV và Techcombank cùng 6,8%/năm.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "7%",
    "6,9%",
    "6,8%",
    "20 đồng"
  ]
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Đoạn nguồn đang nói niêm yết lãi suất tiền gửi, không phải niêm yết chứng khoán hay hành động vốn của doanh nghiệp. corporate_action được kích hoạt nhầm bởi từ “niêm yết”; cần loại trường hợp lãi suất khỏi trigger này.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:be1904cb-6368-50d7-9990-36ae5d76d02f.

**Định vị:** `data/News/TCB/batch_extracted.json` · snapshot `2825b0494fcb1df6ff2cb23880853eba2b094e73f94bf442dba4d83e8055421e` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 97. TCB · 76074e55-9a1a-5b51-ac77-15dea8b3bd4a / e1

**Bằng chứng nguồn:**
> TCB: Thông báo về ngày đăng ký cuối cùng lấy ý kiến cổ đông bằng văn bản

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "TCB",
      "name_normalized": "TCB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_THUOC_TINH`.

**Vì sao REJECTED / cần làm gì:** Có thông báo ngày đăng ký cuối cùng, nhưng bản hiện tại không giữ ngày thực tế, vai trò chủ thể và trạng thái rõ ràng. Nội dung nguồn đang là thông báo kèm tài liệu; cần đọc lịch quyền/đối tượng quyền từ tài liệu đã xác minh. Không lấy ngày trong tên PDF làm ngày chốt quyền.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:76074e55-9a1a-5b51-ac77-15dea8b3bd4a.

**Định vị:** `data/News/TCB/batch_extracted.json` · snapshot `158d0176298a6c3a56e1d468803e1a27338a2e3971038628bf45852580834dec` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 98. TCB · ced0b096-12c3-5c89-a202-67038b5527c1 / e1

**Bằng chứng nguồn:**
> TCB: Thông báo về ngày đăng ký cuối cùng lấy ý kiến cổ đông bằng văn bản

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "TCB",
      "name_normalized": "TCB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_THUOC_TINH`.

**Vì sao REJECTED / cần làm gì:** Có thông báo ngày đăng ký cuối cùng, nhưng bản hiện tại không giữ ngày thực tế, vai trò chủ thể và trạng thái rõ ràng. Nội dung nguồn đang là thông báo kèm tài liệu; cần đọc lịch quyền/đối tượng quyền từ tài liệu đã xác minh. Không lấy ngày trong tên PDF làm ngày chốt quyền.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:ced0b096-12c3-5c89-a202-67038b5527c1.

**Định vị:** `data/News/TCB/batch_extracted.json` · snapshot `8c3eec8d853fc1984a0ceb1476687caa0d71e114f8c1019cc87763f64b274117` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 99. TCB · 8fd8ad93-9090-5ae6-90e3-1e20adaf23dd / e1

**Bằng chứng nguồn:**
> TCB: Thông báo thay đổi nhân sự - Bổ nhiệm PTGĐ (kèm Quyết định)

**Code hiện trả:**

```json
{
  "event_type": "appointment",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "TCB",
      "name_normalized": "TCB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_THUC_THE`.

**Vì sao REJECTED / cần làm gì:** Bản bổ nhiệm chỉ giữ mã công ty; không có người được bổ nhiệm trong parties và vai trò công ty là unspecified. Tiêu đề/thông báo hiện có không đủ xác định đầy đủ người, chức vụ và thời điểm có hiệu lực. Cần đọc đúng quyết định đính kèm và ghim nguồn trước khi duyệt; không tự điền tên từ bài khác.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:8fd8ad93-9090-5ae6-90e3-1e20adaf23dd.

**Định vị:** `data/News/TCB/batch_extracted.json` · snapshot `b42d534373a27e42cad4039e56ddc5064b7393b9f69dfa7816cbbfe034a1ffc3` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 100. TCB · ff9f24a4-ecfe-5534-9756-922725d5e481 / e1

**Bằng chứng nguồn:**
> TCB: Thông báo thay đổi nhân sự - Bổ nhiệm PTGĐ (kèm Quyết định)

**Code hiện trả:**

```json
{
  "event_type": "appointment",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "TCB",
      "name_normalized": "TCB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_THUC_THE`.

**Vì sao REJECTED / cần làm gì:** Bản bổ nhiệm chỉ giữ mã công ty; không có người được bổ nhiệm trong parties và vai trò công ty là unspecified. Tiêu đề/thông báo hiện có không đủ xác định đầy đủ người, chức vụ và thời điểm có hiệu lực. Cần đọc đúng quyết định đính kèm và ghim nguồn trước khi duyệt; không tự điền tên từ bài khác.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:ff9f24a4-ecfe-5534-9756-922725d5e481.

**Định vị:** `data/News/TCB/batch_extracted.json` · snapshot `f32851655b0e7da90af7b89783f35d446f3424235faa08eac0696a0a545e4ac8` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 101. TCB · 68e336f7-93b7-5c61-9643-90dcc0e80372 / e1

**Bằng chứng nguồn:**
> TCB: Quyết định HĐQT về bổ nhiệm PTGĐ - Bà Phan Thị Hải Yến

**Code hiện trả:**

```json
{
  "event_type": "appointment",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "TCB",
      "name_normalized": "TCB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_THUC_THE`.

**Vì sao REJECTED / cần làm gì:** Nguồn đã nêu đích danh người được bổ nhiệm, nhưng parties chỉ chứa công ty với vai trò unspecified, không giữ người và quan hệ bổ nhiệm. Cần trích người cùng chức vụ từ chính câu, giữ riêng quyết định và ngày hiệu lực nếu được nguồn chứng minh.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:68e336f7-93b7-5c61-9643-90dcc0e80372.

**Định vị:** `data/News/TCB/batch_extracted.json` · snapshot `1d4dffbe486621aad794ee3f2d82fa83f04a323edd6a57c53b07935740aaf5d3` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 102. TCB · c126acfc-dd70-53e9-b51a-15d21c4bc50b / e1

**Bằng chứng nguồn:**
> TCB: Quyết định HĐQT về bổ nhiệm PTGĐ - Bà Phan Thị Hải Yến

**Code hiện trả:**

```json
{
  "event_type": "appointment",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "TCB",
      "name_normalized": "TCB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_THUC_THE`.

**Vì sao REJECTED / cần làm gì:** Nguồn đã nêu đích danh người được bổ nhiệm, nhưng parties chỉ chứa công ty với vai trò unspecified, không giữ người và quan hệ bổ nhiệm. Cần trích người cùng chức vụ từ chính câu, giữ riêng quyết định và ngày hiệu lực nếu được nguồn chứng minh.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:c126acfc-dd70-53e9-b51a-15d21c4bc50b.

**Định vị:** `data/News/TCB/batch_extracted.json` · snapshot `eb0601c1d24111ed25f6dbe2e1c8806dfe6c3197c5d14129f22d2d0729e4c4c9` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 103. TCB · 9a268f3d-0039-53b4-ab4e-d163b31782a4 / e1

**Bằng chứng nguồn:**
> TCB: Nghị quyết HĐQT số 0593 ngày 28/10/2026

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "TCB",
      "name_normalized": "TCB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": "2026-10-28",
    "event_date_end": "2026-10-28",
    "date_precision": "day",
    "date_derived": false,
    "date_evidence": "28/10/2026",
    "date_candidates": [
      {
        "date": "2026-10-28",
        "derived": false,
        "evidence": "28/10/2026"
      },
      {
        "date": "2026-10-28",
        "derived": false,
        "evidence": "28/10/2026"
      }
    ]
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:9a268f3d-0039-53b4-ab4e-d163b31782a4.

**Định vị:** `data/News/TCB/batch_extracted.json` · snapshot `e29dc5d6ae5626735ccd8a8a867dfde60a5a104a434d4f41ab69a2b0838cca75` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 104. TCB · d94db945-eae0-5575-8661-d477d1814dd5 / e1

**Bằng chứng nguồn:**
> Dù mặt bằng lãi suất huy động giảm trên diện rộng, một số ngân hàng vẫn niêm yết mức từ 7%/năm trở lên.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "7%",
    "7%",
    "8%"
  ]
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Đoạn nguồn đang nói niêm yết lãi suất tiền gửi, không phải niêm yết chứng khoán hay hành động vốn của doanh nghiệp. corporate_action được kích hoạt nhầm bởi từ “niêm yết”; cần loại trường hợp lãi suất khỏi trigger này.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:d94db945-eae0-5575-8661-d477d1814dd5.

**Định vị:** `data/News/TCB/batch_extracted.json` · snapshot `503d3a7ffa6edf3270e2cf454e4cc54da6cc6476dab509333f3bae5b28025a5c` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 105. TCB · d94db945-eae0-5575-8661-d477d1814dd5 / e2

**Bằng chứng nguồn:**
> Saigonbank đang niêm yết lãi suất kỳ hạn 13 tháng lên đến 7,9%; và VPBank cao nhất 7,4%; Sacombank áp dụng lãi suất cao nhất 7,3%/năm cho khoản tiền gửi từ 500 triệu đồng, kỳ hạn 24-36 tháng; VCBNeo niêm yết 7%/năm tại các kỳ hạn 6-36 tháng; MBV áp dụng 7%/năm tại kỳ hạn 7-36 tháng.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "VPB",
      "name_normalized": "VPB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "7,9%",
    "7,4%",
    "7,3%",
    "500 triệu đồng",
    "7%"
  ]
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Đoạn nguồn đang nói niêm yết lãi suất tiền gửi, không phải niêm yết chứng khoán hay hành động vốn của doanh nghiệp. corporate_action được kích hoạt nhầm bởi từ “niêm yết”; cần loại trường hợp lãi suất khỏi trigger này.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:d94db945-eae0-5575-8661-d477d1814dd5.

**Định vị:** `data/News/TCB/batch_extracted.json` · snapshot `503d3a7ffa6edf3270e2cf454e4cc54da6cc6476dab509333f3bae5b28025a5c` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 106. TCB · 89580733-9833-5973-98c7-a31dd2ccdbcf / e1

**Bằng chứng nguồn:**
> TCB: Nghị quyết HĐQT số 0589, 0591 ngày 27/10/2026

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "TCB",
      "name_normalized": "TCB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": "2026-10-27",
    "event_date_end": "2026-10-27",
    "date_precision": "day",
    "date_derived": false,
    "date_evidence": "27/10/2026",
    "date_candidates": [
      {
        "date": "2026-10-27",
        "derived": false,
        "evidence": "27/10/2026"
      },
      {
        "date": "2026-10-27",
        "derived": false,
        "evidence": "27/10/2026"
      }
    ]
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:89580733-9833-5973-98c7-a31dd2ccdbcf.

**Định vị:** `data/News/TCB/batch_extracted.json` · snapshot `701945b653ec0f6f2caf7cd2f52a870ffcb1c4ae104638a327487e60dfc42fe2` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 107. TCB · 5d5aa869-b0a3-56a2-a5c5-a609415ed41f / e1

**Bằng chứng nguồn:**
> Gửi tại quầy: VPBank niêm yết lãi suất 6,4%/năm Theo biểu lãi suất áp dụng từ ngày 24/10/2026, VPBank niêm yết lãi suất tiền gửi tại quầy kỳ hạn 12 tháng ở mức 6,4%/năm đối với khoản tiền dưới 1 tỷ đồng.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "VPB",
      "name_normalized": "VPB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": "2026-10-24",
    "event_date_end": "2026-10-24",
    "date_precision": "day",
    "date_derived": false,
    "date_evidence": "24/10/2026",
    "date_candidates": [
      {
        "date": "2026-10-24",
        "derived": false,
        "evidence": "24/10/2026"
      }
    ]
  },
  "figures": [
    "6,4%",
    "1 tỷ đồng"
  ]
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Đoạn nguồn đang nói niêm yết lãi suất tiền gửi, không phải niêm yết chứng khoán hay hành động vốn của doanh nghiệp. corporate_action được kích hoạt nhầm bởi từ “niêm yết”; cần loại trường hợp lãi suất khỏi trigger này.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:5d5aa869-b0a3-56a2-a5c5-a609415ed41f.

**Định vị:** `data/News/TCB/batch_extracted.json` · snapshot `58e4a23a3bcefbc50ff0a737058f6cd5d26a359808ed492f15baefadfbedfca7` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 108. TCB · 5d5aa869-b0a3-56a2-a5c5-a609415ed41f / e2

**Bằng chứng nguồn:**
> SHB và MB cùng niêm yết lãi suất tại quầy ở mức 5,7%/năm.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "5,7%",
    "6,8%",
    "50 triệu đồng",
    "500 triệu đồng",
    "6,0%"
  ]
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Đoạn nguồn đang nói niêm yết lãi suất tiền gửi, không phải niêm yết chứng khoán hay hành động vốn của doanh nghiệp. corporate_action được kích hoạt nhầm bởi từ “niêm yết”; cần loại trường hợp lãi suất khỏi trigger này.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:5d5aa869-b0a3-56a2-a5c5-a609415ed41f.

**Định vị:** `data/News/TCB/batch_extracted.json` · snapshot `58e4a23a3bcefbc50ff0a737058f6cd5d26a359808ed492f15baefadfbedfca7` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 109. TCB · 5d5aa869-b0a3-56a2-a5c5-a609415ed41f / e3

**Bằng chứng nguồn:**
> HDBank niêm yết lãi suất tiết kiệm thông thường kỳ hạn 12 tháng ở mức 5,2%/năm.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "HDB",
      "name_normalized": "HDB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "5,2%",
    "5,3%"
  ]
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Đoạn nguồn đang nói niêm yết lãi suất tiền gửi, không phải niêm yết chứng khoán hay hành động vốn của doanh nghiệp. corporate_action được kích hoạt nhầm bởi từ “niêm yết”; cần loại trường hợp lãi suất khỏi trigger này.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:5d5aa869-b0a3-56a2-a5c5-a609415ed41f.

**Định vị:** `data/News/TCB/batch_extracted.json` · snapshot `58e4a23a3bcefbc50ff0a737058f6cd5d26a359808ed492f15baefadfbedfca7` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 110. TCB · 40a6e92f-bd62-5b0f-bdbd-f01b71bfd07f / e1

**Bằng chứng nguồn:**
> TCB: Nghị quyết HĐQT số 0586 ngày 26/10/2026

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "TCB",
      "name_normalized": "TCB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": "2026-10-26",
    "event_date_end": "2026-10-26",
    "date_precision": "day",
    "date_derived": false,
    "date_evidence": "26/10/2026",
    "date_candidates": [
      {
        "date": "2026-10-26",
        "derived": false,
        "evidence": "26/10/2026"
      },
      {
        "date": "2026-10-26",
        "derived": false,
        "evidence": "26/10/2026"
      }
    ]
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:40a6e92f-bd62-5b0f-bdbd-f01b71bfd07f.

**Định vị:** `data/News/TCB/batch_extracted.json` · snapshot `52216580c06755bbf6b5c0bfe8c448ec689da5bd4c33ad9e49b462421ca1ae50` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 111. TCB · d4c3bbaf-cd79-5812-90d0-b1ec3f289572 / e1

**Bằng chứng nguồn:**
> Ngày 26/10, Sở Giao dịch Chứng khoán Hà Nội (HNX) công bố Số liệu Quản lý Sở hữu của Nhà đầu tư nước ngoài của các doanh nghiệp niêm yết trên sàn chứng khoán.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [],
  "dates": {
    "event_date_start": "2026-10-26",
    "event_date_end": "2026-10-26",
    "date_precision": "day",
    "date_derived": true,
    "date_evidence": "Ngày 26/10",
    "date_candidates": [
      {
        "date": "2026-10-26",
        "derived": true,
        "evidence": "Ngày 26/10"
      }
    ]
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn là HNX công bố thống kê sở hữu nước ngoài, không chứng minh doanh nghiệp thực hiện niêm yết/corporate action. parties rỗng; việc xuất hiện tên sở giao dịch không đủ tạo sự kiện niêm yết của một mã.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:d4c3bbaf-cd79-5812-90d0-b1ec3f289572.

**Định vị:** `data/News/TCB/batch_extracted.json` · snapshot `48546a2886cd3f25c719f9d9c5af2909cff995e752d705310b0bcd0b8979a564` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 112. TCB · 5b08bd61-d63f-5bdd-a184-ed0ecb0c9be6 / e1

**Bằng chứng nguồn:**
> TCB: Nghị quyết HĐQT về việc chốt danh sách cổ đông lấy ý kiến cổ đông bằng văn bản

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "TCB",
      "name_normalized": "TCB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:5b08bd61-d63f-5bdd-a184-ed0ecb0c9be6.

**Định vị:** `data/News/TCB/batch_extracted.json` · snapshot `30984202df3799ef186c16230f54ac5a6276ead3beb0c0c94e33b2ae01bf7842` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 113. TCB · af20ecff-0beb-5e3d-bd0f-f69c05d37901 / e1

**Bằng chứng nguồn:**
> Sở Giao dịch Chứng khoán TP.HCM thông báo về ngày đăng ký cuối cùng phát hành cổ phiếu để trả cổ tức cho cổ đông hiện hữu của Ngân hàng Thương mại Cổ phần Kỹ Thương Việt Nam như sau: Các tập tin đính kèm 20261023 - TCB - TB NDKCC phat hanh CP de tra co tuc.pdf Theo HOSE

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "TCB",
      "name_normalized": "TCB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_THUOC_TINH`.

**Vì sao REJECTED / cần làm gì:** Có thông báo ngày đăng ký cuối cùng, nhưng bản hiện tại không giữ ngày thực tế, vai trò chủ thể và trạng thái rõ ràng. Nội dung nguồn đang là thông báo kèm tài liệu; cần đọc lịch quyền/đối tượng quyền từ tài liệu đã xác minh. Không lấy ngày trong tên PDF làm ngày chốt quyền.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:af20ecff-0beb-5e3d-bd0f-f69c05d37901.

**Định vị:** `data/News/TCB/batch_extracted.json` · snapshot `7c9b8e2c92ba81746f164a53fffbf4f12fd20854eaa54a6baf3e9d3e918ecc7c` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 114. TCB · 4b938390-f187-50d3-9eea-77bc6ef1ef03 / e1

**Bằng chứng nguồn:**
> TCB: Nghị quyết HĐQT phê duyệt tăng vốn góp tại Công ty Cổ phần Bảo hiểm Phi nhân thọ Techcom (TGIns)

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "TCB",
      "name_normalized": "TCB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:4b938390-f187-50d3-9eea-77bc6ef1ef03.

**Định vị:** `data/News/TCB/batch_extracted.json` · snapshot `7f698ccb6c1404a3efe550e58769d96907f60dc9c711f86f199eada72be2967a` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 115. TCB · 865825b2-0c8d-5e96-b37b-c536235c9be5 / e1

**Bằng chứng nguồn:**
> Tiến sĩ Jens Lottner, Tổng Giám đốc Techcombank nhận giải thưởng "Ngân hàng Tốt nhất Việt Nam 2026" tại lễ trao giải (Bangkok, Thái Lan).

**Code hiện trả:**

```json
{
  "event_type": "ceremony_other",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "TCB",
      "name_normalized": "TCB",
      "role": "unspecified",
      "name_source": "metadata"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_VAI_TRO`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu Jens Lottner đại diện Techcombank nhận giải tại Bangkok. Bản chỉ giữ TCB từ metadata, vai trò unspecified và unconfirmed; cần giữ người đại diện, vai trò nhận giải/tham dự và bằng chứng thực sự, không suy ngân hàng là đơn vị tổ chức.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:865825b2-0c8d-5e96-b37b-c536235c9be5.

**Định vị:** `data/News/TCB/batch_extracted.json` · snapshot `d03215f5a491cc3a9ec7ee55c0883a08f63d93a0dd6fd6243d6714fbe00299fb` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 116. VCB · a46ed591-fe06-5e17-a880-dacb7fcf7675 / e1

**Bằng chứng nguồn:**
> Theo khoản 1 Điều 148 Luật Doanh nghiệp 2020, nếu điều lệ công ty không quy định tỷ lệ khác, các nghị quyết quan trọng của đại hội đồng cổ đông cần được ít nhất 65% tổng số phiếu biểu quyết của cổ đông dự họp tán thành.

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "65%"
  ]
}
```

**Nhóm kết luận:** `KHONG_CO_SU_KIEN`.

**Vì sao REJECTED / cần làm gì:** Nguồn giải thích quy định chung của Luật Doanh nghiệp và tỷ lệ biểu quyết 65%; không xác định công ty hay cuộc họp cụ thể. Không được tạo một sự kiện đại hội cổ đông từ ví dụ pháp luật này.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:a46ed591-fe06-5e17-a880-dacb7fcf7675.

**Định vị:** `data/News/VCB/batch_extracted.json` · snapshot `e770e6bb021e68524bea97121f90bae21f098da16c2ca16e0b130e773fed8fa6` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 117. VCB · 09407114-1adb-5d05-a9db-396a299243f5 / e1

**Bằng chứng nguồn:**
> Ảnh: Phan Anh Theo biểu lãi suất niêm yết của Ngân hàng TMCP Ngoại thương Việt Nam (Vietcombank) cập nhật lúc 11h00 ngày 29.10, lãi suất tiết kiệm bằng VND tại quầy hiện dao động từ 0,1-5,5%/năm, tùy từng kỳ hạn.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "VCB",
      "name_normalized": "VCB",
      "role": "unspecified",
      "name_source": "metadata"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "5,5%",
    "2,1%",
    "2,4%",
    "5,5%",
    "4,8%"
  ]
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Đoạn nguồn đang nói niêm yết lãi suất tiền gửi, không phải niêm yết chứng khoán hay hành động vốn của doanh nghiệp. corporate_action được kích hoạt nhầm bởi từ “niêm yết”; cần loại trường hợp lãi suất khỏi trigger này.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:09407114-1adb-5d05-a9db-396a299243f5.

**Định vị:** `data/News/VCB/batch_extracted.json` · snapshot `430c5050e135b006b13bc778160a1bb73f96f65fb52aabb7b557c2a90af15130` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 118. VCB · 8931a91c-2d42-5a41-9a32-2f9a1889d3a1 / e1

**Bằng chứng nguồn:**
> Ông Nguyễn Thanh Nghị - Ủy viên BCH TW Đảng,Trưởng Ban Chính sách, chiến lược Trung ương (thứ 2 từ phải sang), ông Lê Quang Vinh - Tổng Giám đốc Vietcombank (hàng đầu tiên thứ 2 từ trái sang) và các đại biểu thăm không gian triển lãm của Vietcombank 2.

**Code hiện trả:**

```json
{
  "event_type": "exhibition_fair",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "VCB",
      "name_normalized": "VCB",
      "role": "unspecified",
      "name_source": "metadata"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_VAI_TRO`.

**Vì sao REJECTED / cần làm gì:** Nguồn mô tả các đại biểu thăm không gian triển lãm Vietcombank. Bản chỉ giữ VCB từ metadata, unspecified; chưa biểu diễn vai trò bên trưng bày/đại biểu với đúng triển lãm. Không được suy VCB là organizer hoặc coi mọi khách thăm là nhân sự VCB.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:8931a91c-2d42-5a41-9a32-2f9a1889d3a1.

**Định vị:** `data/News/VCB/batch_extracted.json` · snapshot `57272ce407e90832488fd891a02fd1d4dc03d5ff6a8ca5b2bd02e237fa8b6fa9` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 119. VCB · 8931a91c-2d42-5a41-9a32-2f9a1889d3a1 / e2

**Bằng chứng nguồn:**
> Online Lending, được Vietcombank ra mắt ngày 28/2/2025, cho phép khách hàng doanh nghiệp thực hiện quy trình giải ngân trực tuyến trên kênh ngân hàng số đủ điều kiện.

**Code hiện trả:**

```json
{
  "event_type": "product_launch",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "VCB",
      "name_normalized": "VCB",
      "role": "unspecified",
      "name_source": "metadata"
    }
  ],
  "dates": {
    "event_date_start": "2025-02-28",
    "event_date_end": "2025-02-28",
    "date_precision": "day",
    "date_derived": false,
    "date_evidence": "28/2/2025",
    "date_candidates": [
      {
        "date": "2025-02-28",
        "derived": false,
        "evidence": "28/2/2025"
      }
    ]
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_TRANG_THAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn ghi Online Lending “được Vietcombank ra mắt ngày 28/2/2025”, nhưng status=unconfirmed và VCB vẫn từ metadata, unspecified. Ngày trích đúng; cần sửa trạng thái và vai trò bên ra mắt có bằng chứng trực tiếp trước khi duyệt nguyên bản.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:8931a91c-2d42-5a41-9a32-2f9a1889d3a1.

**Định vị:** `data/News/VCB/batch_extracted.json` · snapshot `57272ce407e90832488fd891a02fd1d4dc03d5ff6a8ca5b2bd02e237fa8b6fa9` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 120. VCB · 8931a91c-2d42-5a41-9a32-2f9a1889d3a1 / e3

**Bằng chứng nguồn:**
> Sản phẩm: Giải pháp giải ngân trực tuyến - Online Lending dành cho khách hàng doanh nghiệp của Vietcombank Với khách hàng cá nhân, việc phát hành chứng chỉ tiền gửi trực tuyến trên VCB Digibank mở rộng lựa chọn tích lũy và cho phép khách hàng thực hiện giao dịch trên nền tảng số.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "VCB",
      "name_normalized": "VCB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `KHONG_CO_SU_KIEN_CU_THE`.

**Vì sao REJECTED / cần làm gì:** Nguồn mô tả tính năng phát hành chứng chỉ tiền gửi trực tuyến của sản phẩm VCB Digibank, không xác định một đợt phát hành chứng khoán cụ thể. Không biến khả năng cung cấp dịch vụ thành một corporate_action riêng.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:8931a91c-2d42-5a41-9a32-2f9a1889d3a1.

**Định vị:** `data/News/VCB/batch_extracted.json` · snapshot `57272ce407e90832488fd891a02fd1d4dc03d5ff6a8ca5b2bd02e237fa8b6fa9` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 121. VCB · 8931a91c-2d42-5a41-9a32-2f9a1889d3a1 / e4

**Bằng chứng nguồn:**
> Đại diện Vietcombank, Phó Tổng giám đốc Phùng Nguyễn Hải Yến (thứ 2 từ phải sang) nhận Giải Vàng hạng mục Đổi mới sáng tạo số - ASEAN Digital Awards trong khuôn khổ Hội nghị Bộ trưởng Số ASEAN (ADGMIN) lần thứ 6 diễn ra tối 15/01/2026 tại Hà Nội Ở khía cạnh kiểm soát hoạt động, VCB Alert cảnh báo tài khoản nhận tiền có dấu hiệu nghi ngờ gian lận, lừa đảo đã được mở rộng từ giao dịch chuyển tiền nhanh liên ngân hàng sang các giao dịch trong1 Vietcombank trên VCB Digibank và tại quầy.

**Code hiện trả:**

```json
{
  "event_type": "conference_forum",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "VCB",
      "name_normalized": "VCB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": "2026-01-15",
    "event_date_end": "2026-01-15",
    "date_precision": "day",
    "date_derived": false,
    "date_evidence": "15/01/2026",
    "date_candidates": [
      {
        "date": "2026-01-15",
        "derived": false,
        "evidence": "15/01/2026"
      }
    ]
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_VAI_TRO`.

**Vì sao REJECTED / cần làm gì:** Nguồn cho biết Phùng Nguyễn Hải Yến đại diện VCB nhận giải trong hội nghị ADGMIN 15/01/2026. Ngày có căn cứ, nhưng bản chỉ có VCB unspecified và unconfirmed; cần giữ vai trò tham dự/nhận giải, không nhầm với đơn vị tổ chức hội nghị.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:8931a91c-2d42-5a41-9a32-2f9a1889d3a1.

**Định vị:** `data/News/VCB/batch_extracted.json` · snapshot `57272ce407e90832488fd891a02fd1d4dc03d5ff6a8ca5b2bd02e237fa8b6fa9` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 122. VCB · 8931a91c-2d42-5a41-9a32-2f9a1889d3a1 / e5

**Bằng chứng nguồn:**
> Việc đăng ký chữ ký số từ xa qua ứng dụng VCB Digibank thông qua kết nối với Cổng ký số tập trung từ xa VNeID giúp khách hàng tiếp cận phương thức xác thực, ký kết điện tử thuận tiện hơn.

**Code hiện trả:**

```json
{
  "event_type": "agreement_signing",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "VCB",
      "name_normalized": "VCB",
      "role": "counterparty",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `KHONG_CO_SU_KIEN`.

**Vì sao REJECTED / cần làm gì:** Nguồn nói khách hàng sử dụng chữ ký số để ký điện tử. Không nêu một thỏa thuận hợp tác VCB ký với đối tác cụ thể. Gán VCB=counterparty của agreement_signing là suy diễn từ tính năng dịch vụ.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:8931a91c-2d42-5a41-9a32-2f9a1889d3a1.

**Định vị:** `data/News/VCB/batch_extracted.json` · snapshot `57272ce407e90832488fd891a02fd1d4dc03d5ff6a8ca5b2bd02e237fa8b6fa9` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 123. VCB · fbced2c9-da5d-5995-a98f-e15260708b97 / e1

**Bằng chứng nguồn:**
> Ở kỳ hạn 12 và 24 tháng, cả bốn ngân hàng cùng niêm yết lãi suất lần lượt 5,4%/năm và 5,5%/năm.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "5,4%",
    "5,5%",
    "2,6%",
    "5,4%",
    "5,5%",
    "5,4%",
    "3,5%",
    "17,5 triệu đồng"
  ]
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Đoạn nguồn đang nói niêm yết lãi suất tiền gửi, không phải niêm yết chứng khoán hay hành động vốn của doanh nghiệp. corporate_action được kích hoạt nhầm bởi từ “niêm yết”; cần loại trường hợp lãi suất khỏi trigger này.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:fbced2c9-da5d-5995-a98f-e15260708b97.

**Định vị:** `data/News/VCB/batch_extracted.json` · snapshot `ec3b74bed639bf09c713284ccaae61694d5d25bba802818621d53ec441508d3e` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 124. VCB · 5c5e781d-b2e2-57f6-b5ab-7a0d53e95563 / e1

**Bằng chứng nguồn:**
> Tin kinh tế - Tài chính nổi bật VNM: Công ty Cổ phần Sữa Việt Nam (VNM) vừa chính thức công bố nghị quyết Hội đồng Quản trị về việc tạm ứng cổ tức đợt 1 năm 2026 bằng tiền mặt với tỉ lệ 25%, tương ứng cổ đông sở hữu một cổ phiếu sẽ nhận được 2.500 đồng.

**Đoạn nguồn bổ sung về trạng thái:**
> Ngày đăng ký cuối cùng để chốt danh sách cổ đông là 12/11/2026 và thời gian thanh toán dự kiến diễn ra vào ngày 26/11/2026.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "planned",
  "parties": [],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": [
      {
        "date": "2026-11-12",
        "derived": false,
        "evidence": "12/11/2026"
      },
      {
        "date": "2026-11-26",
        "derived": false,
        "evidence": "26/11/2026"
      }
    ]
  },
  "figures": [
    "25%",
    "2.500 đồng",
    "5.200 tỷ đồng",
    "5.225 tỷ đồng"
  ]
}
```

**Nhóm kết luận:** `KE_HOACH_CHUA_DU_DIEU_KIEN`.

**Vì sao REJECTED / cần làm gì:** Nguồn ghi lịch chốt quyền/chi trả trong tương lai và đầu ra ghi planned. Đây là ghi nhận kế hoạch, không phải bằng chứng đã chi trả. REJECTED ở tiêu chí đưa vào graph sự kiện đã có hiệu lực; không kết luận trường planned là trích sai. Cần tách các mốc chốt quyền/chi trả và định danh bên phát hành trước khi xét bản thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:5c5e781d-b2e2-57f6-b5ab-7a0d53e95563.

**Định vị:** `data/News/VCB/batch_extracted.json` · snapshot `2be3cf8b533b21eb82a468030a2ba76061c09db92dc52c445860ccedc1847b8c` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 125. VCB · 5c5e781d-b2e2-57f6-b5ab-7a0d53e95563 / e2

**Bằng chứng nguồn:**
> TCB: Ngân hàng TMCP Kỹ Thương Việt Nam (Techcombank) vừa chính thức công bố quyết định bổ nhiệm bà Phan Thị Hải Yến giữ chức vụ Phó Tổng Giám đốc kiêm Giám đốc Khối Ngân hàng Doanh nghiệp và Định chế Tài chính (CIBG).

**Code hiện trả:**

```json
{
  "event_type": "appointment",
  "status": "unconfirmed",
  "parties": [],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": [
      {
        "date": "2026-11-11",
        "derived": false,
        "evidence": "11/11/2026"
      },
      {
        "date": "2026-10-29",
        "derived": true,
        "evidence": "ngày 29/10"
      }
    ]
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_THUC_THE`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu rõ TCB bổ nhiệm Phan Thị Hải Yến nhưng parties rỗng. Các ngày trong câu kế tiếp còn có thể thuộc tin khác của bản tin tổng hợp; phải tách từng tin, xác định người–công ty–chức vụ và nghĩa từng mốc, không gán ngày lân cận tùy tiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:5c5e781d-b2e2-57f6-b5ab-7a0d53e95563.

**Định vị:** `data/News/VCB/batch_extracted.json` · snapshot `2be3cf8b533b21eb82a468030a2ba76061c09db92dc52c445860ccedc1847b8c` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 126. VCB · 5c5e781d-b2e2-57f6-b5ab-7a0d53e95563 / e3

**Bằng chứng nguồn:**
> EVS: Chứng khoán EVS vừa bổ sung thông tin trình Đại hội đồng cổ đông bất thường năm 2026 về việc đề cử ông Nguyễn Trần Minh Quân - Quyền Tổng Giám đốc tham gia Hội đồng quản trị nhiệm kỳ 2026 - 2031.

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `KE_HOACH_CHUA_DU_DIEU_KIEN`.

**Vì sao REJECTED / cần làm gì:** Nguồn nói bổ sung hồ sơ trình ĐHĐCĐ và đề cử ứng viên EVS, chưa chứng minh cuộc họp đã diễn ra hay ứng viên đã được bầu. Bản parties rỗng, status=unconfirmed; cần giữ trạng thái đề xuất, không duyệt quan hệ nhân sự có hiệu lực.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:5c5e781d-b2e2-57f6-b5ab-7a0d53e95563.

**Định vị:** `data/News/VCB/batch_extracted.json` · snapshot `2be3cf8b533b21eb82a468030a2ba76061c09db92dc52c445860ccedc1847b8c` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 127. VCB · 24a162ed-3e28-5492-853d-010d9a1134a9 / e1

**Bằng chứng nguồn:**
> Ở kỳ hạn 12 và 24 tháng, cả bốn ngân hàng cùng niêm yết lãi suất lần lượt 5,4%/năm và 5,5%/năm.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "5,4%",
    "5,5%",
    "2,6%",
    "5,4%",
    "5,5%",
    "5,4%",
    "3,5%",
    "8,75 triệu đồng"
  ]
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Đoạn nguồn đang nói niêm yết lãi suất tiền gửi, không phải niêm yết chứng khoán hay hành động vốn của doanh nghiệp. corporate_action được kích hoạt nhầm bởi từ “niêm yết”; cần loại trường hợp lãi suất khỏi trigger này.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:24a162ed-3e28-5492-853d-010d9a1134a9.

**Định vị:** `data/News/VCB/batch_extracted.json` · snapshot `cbdc0bd877d3c96df50ef01df6a60e6a95682b0ea7f95064a601d3ad22986ee8` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 128. VCB · 856eedea-a092-55e0-86f6-5ecdea899819 / e1

**Bằng chứng nguồn:**
> Trong đó, Agribank có lợi thế tại các kỳ hạn ngắn, trong khi cả bốn ngân hàng cùng niêm yết lãi suất 5,4%/năm ở kỳ hạn 12 tháng và 5,5%/năm ở kỳ hạn 24 tháng.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": [
    "5,4%",
    "5,5%",
    "2,6%",
    "5,4%",
    "5,5%",
    "3,5%",
    "3,5 triệu đồng",
    "4,8%"
  ]
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Đoạn nguồn đang nói niêm yết lãi suất tiền gửi, không phải niêm yết chứng khoán hay hành động vốn của doanh nghiệp. corporate_action được kích hoạt nhầm bởi từ “niêm yết”; cần loại trường hợp lãi suất khỏi trigger này.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:856eedea-a092-55e0-86f6-5ecdea899819.

**Định vị:** `data/News/VCB/batch_extracted.json` · snapshot `feca8203e6569b042e83fd5521739e497fcd95f3b404499434cce1cd564ae173` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 129. VCB · d4c3bbaf-cd79-5812-90d0-b1ec3f289572 / e1

**Bằng chứng nguồn:**
> Ngày 26/10, Sở Giao dịch Chứng khoán Hà Nội (HNX) công bố Số liệu Quản lý Sở hữu của Nhà đầu tư nước ngoài của các doanh nghiệp niêm yết trên sàn chứng khoán.

**Code hiện trả:**

```json
{
  "event_type": "corporate_action",
  "status": "unconfirmed",
  "parties": [],
  "dates": {
    "event_date_start": "2026-10-26",
    "event_date_end": "2026-10-26",
    "date_precision": "day",
    "date_derived": true,
    "date_evidence": "Ngày 26/10",
    "date_candidates": [
      {
        "date": "2026-10-26",
        "derived": true,
        "evidence": "Ngày 26/10"
      }
    ]
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn là HNX công bố thống kê sở hữu nước ngoài, không chứng minh doanh nghiệp thực hiện niêm yết/corporate action. parties rỗng; việc xuất hiện tên sở giao dịch không đủ tạo sự kiện niêm yết của một mã.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:d4c3bbaf-cd79-5812-90d0-b1ec3f289572.

**Định vị:** `data/News/VCB/batch_extracted.json` · snapshot `48546a2886cd3f25c719f9d9c5af2909cff995e752d705310b0bcd0b8979a564` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 130. VCB · dea88a59-6d75-5214-887c-8bda3249fb63 / e1

**Bằng chứng nguồn:**
> Vietcombank, VietinBank, BIDV, Agribank, MB, HDBank...đều có mặt ký kết thỏa thuận.

**Code hiện trả:**

```json
{
  "event_type": "agreement_signing",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "HDB",
      "name_normalized": "HDB",
      "role": "counterparty",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_DOI_TAC`.

**Vì sao REJECTED / cần làm gì:** Nguồn liệt kê Vietcombank, VietinBank, BIDV, Agribank, MB, HDBank cùng ký, nhưng bản chỉ giữ HDB. Thiếu nhiều bên được nêu trực tiếp; chưa đủ xác định từng thỏa thuận và cặp bên ký, không tự nối tất cả ngân hàng với nhau.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:dea88a59-6d75-5214-887c-8bda3249fb63.

**Định vị:** `data/News/VCB/batch_extracted.json` · snapshot `c9fa9cf599f732a043174b2aea64365f742c1c9aa9c75d1a0b194a6949d8ba6a` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 131. VCB · dea88a59-6d75-5214-887c-8bda3249fb63 / e2

**Bằng chứng nguồn:**
> Tại Hội nghị "Ngành Ngân hàng đồng hành khơi thông nguồn lực Tài chính – Ngân hàng phục vụ tăng trưởng vùng Đông Nam bộ giai đoạn 2026 – 2030" ngày 23/10/2026 do NHNN và UBND TP HCM tổ chức, các ngân hàng và doanh nghiệp đã trao tới 20 thỏa thuận hợp tác cho các dự án, phương án kinh doanh với tổng số tiền khoảng 230 nghìn tỷ đồng.

**Code hiện trả:**

```json
{
  "event_type": "agreement_signing",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "NHNN và UBND TP HCM",
      "name_normalized": "NHNN và UBND TP HCM",
      "role": "organizer",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": "2026-10-23",
    "event_date_end": "2026-10-23",
    "date_precision": "day",
    "date_derived": false,
    "date_evidence": "23/10/2026",
    "date_candidates": [
      {
        "date": "2026-10-23",
        "derived": false,
        "evidence": "23/10/2026"
      }
    ]
  },
  "figures": [
    "230 nghìn"
  ]
}
```

**Nhóm kết luận:** `SAI_VAI_TRO_VA_DON_VI`.

**Vì sao REJECTED / cần làm gì:** NHNN và UBND TP HCM là hai đơn vị tổ chức hội nghị, nhưng bị giữ thành một party organizer của agreement_signing. Các bên thực sự ký bị thiếu. Nguồn ghi khoảng “230 nghìn tỷ đồng”, value_raw chỉ giữ “230 nghìn”, mất đơn vị tỷ đồng. Cần tách hội nghị khỏi các thỏa thuận và giữ đầy đủ đơn vị.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:dea88a59-6d75-5214-887c-8bda3249fb63.

**Định vị:** `data/News/VCB/batch_extracted.json` · snapshot `c9fa9cf599f732a043174b2aea64365f742c1c9aa9c75d1a0b194a6949d8ba6a` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 132. VCB · dea88a59-6d75-5214-887c-8bda3249fb63 / e3

**Bằng chứng nguồn:**
> Trong đó HDBank và Vikki Bank đã trao 5 thỏa thuận hợp tác, Vietcombank tài trợ trao 4 thỏa thuận hợp tác, VietinBank, BIDV, Agribank, MBBank, NCB mỗi ngân hàng trao 2 thỏa thuận hợp tác (bao gồm cả thỏa thuận đồng tài trợ của các ngân hàng) và ACB đã trao 1 thỏa thuận hợp tác.

**Code hiện trả:**

```json
{
  "event_type": "agreement_signing",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "HDB",
      "name_normalized": "HDB",
      "role": "counterparty",
      "name_source": "sentence"
    },
    {
      "name_raw": "MBB",
      "name_normalized": "MBB",
      "role": "counterparty",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `GOP_SAI_SU_KIEN`.

**Vì sao REJECTED / cần làm gì:** Nguồn tổng hợp nhiều thỏa thuận riêng của HDBank/Vikki, Vietcombank và các ngân hàng khác; bản chỉ giữ HDB và MBB làm counterparties của một event. Không chứng minh HDB ký trực tiếp với MBB trong cùng thỏa thuận; cần tách nhóm và đối tác đúng nguồn.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:dea88a59-6d75-5214-887c-8bda3249fb63.

**Định vị:** `data/News/VCB/batch_extracted.json` · snapshot `c9fa9cf599f732a043174b2aea64365f742c1c9aa9c75d1a0b194a6949d8ba6a` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 133. VCB · dea88a59-6d75-5214-887c-8bda3249fb63 / e4

**Bằng chứng nguồn:**
> Các dự án, phương án kinh doanh mà các NHTM và doanh nghiệp trao thỏa thuận tại Hội nghị thuộc đa dạng các ngành, lĩnh vực như: công nghiệp chế tạo, năng lượng, dược phẩm, hạ tầng giao thông, khu công nghiệp, nhà ở xã hội, ...

**Code hiện trả:**

```json
{
  "event_type": "conference_forum",
  "status": "unconfirmed",
  "parties": [],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_THUC_THE`.

**Vì sao REJECTED / cần làm gì:** Câu chỉ liệt kê ngành của các dự án tại hội nghị; bản có parties=[] và không giữ định danh hội nghị/ngân hàng tham gia. Có thể dùng làm chi tiết hội nghị đã định danh, không duyệt như một sự kiện riêng không chủ thể.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:dea88a59-6d75-5214-887c-8bda3249fb63.

**Định vị:** `data/News/VCB/batch_extracted.json` · snapshot `c9fa9cf599f732a043174b2aea64365f742c1c9aa9c75d1a0b194a6949d8ba6a` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 134. VCB · aa25ab96-137b-59f3-87b1-978c19e0dea9 / e1

**Bằng chứng nguồn:**
> VCB: HĐQT thông qua giao dịch với VCBF

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "VCB",
      "name_normalized": "VCB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:aa25ab96-137b-59f3-87b1-978c19e0dea9.

**Định vị:** `data/News/VCB/batch_extracted.json` · snapshot `61a250602387131b57bac0923a5019bed6433d9d440f7aec0fba674ed7e9bd04` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 135. VCB · 4bd6e412-e784-54f8-9825-8a9dcc067c6b / e1

**Bằng chứng nguồn:**
> VCB: Miễn nhiệm ông Nguyễn Văn Tuân - Phó Tổng giám đốc từ 1.11.2026

**Code hiện trả:**

```json
{
  "event_type": "appointment",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "VCB",
      "name_normalized": "VCB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `MAT_NGAY`.

**Vì sao REJECTED / cần làm gì:** Nguồn ghi rõ ngày bằng dấu chấm nhưng dates.event_date_start và date_candidates bỏ mất. Phải giữ ngày đúng nghĩa trong câu (ngày giao dịch/niêm yết/hiệu lực nhân sự), không thay bằng ngày đăng bài. Bản hiện tại còn để vai trò unspecified; ca nhân sự cần định danh người được bổ nhiệm/miễn nhiệm.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:4bd6e412-e784-54f8-9825-8a9dcc067c6b.

**Định vị:** `data/News/VCB/batch_extracted.json` · snapshot `6916235fe902d99aa24eb112c8242aa7143aed5918472b513782655861a675d1` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 136. VCB · 6e9d931a-7df4-5630-a4b7-6ed513a3d38e / e1

**Bằng chứng nguồn:**
> VCB: CBTT thông qua ký kết thỏa thuận LC UPAS và LC Discounting với VFC

**Code hiện trả:**

```json
{
  "event_type": "agreement_signing",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "VCB",
      "name_normalized": "VCB",
      "role": "counterparty",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `THIEU_DOI_TAC`.

**Vì sao REJECTED / cần làm gì:** Nguồn chỉ rõ thông qua việc ký thỏa thuận với VFC. Bản bỏ VFC và chưa phân biệt phê duyệt ký với đã ký. Cần giữ VFC cùng trạng thái quyết định; chưa có chứng minh việc ký kết đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:6e9d931a-7df4-5630-a4b7-6ed513a3d38e.

**Định vị:** `data/News/VCB/batch_extracted.json` · snapshot `e1a5aa212bd40a3b9894a5b4d17081f2211fb92de5825b658e80964e315c59e6` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 137. VCB · f15ab668-fffb-5911-a0a9-3c194de2f961 / e1

**Bằng chứng nguồn:**
> VCB: HĐQT thông qua hợp đồng và giao dịch giữa VCB và VCBM

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "VCB",
      "name_normalized": "VCB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:f15ab668-fffb-5911-a0a9-3c194de2f961.

**Định vị:** `data/News/VCB/batch_extracted.json` · snapshot `29ac1d1c63e48909b0e59359e41234e6ffb50530e67c479992bcdfa1d84ef6bf` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 138. VCB · 66605e84-6ba7-52e7-ba8e-ae39e3c020f2 / e1

**Bằng chứng nguồn:**
> VCB: HĐQT thông qua giao dịch giữa VCB và VCBF

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "VCB",
      "name_normalized": "VCB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:66605e84-6ba7-52e7-ba8e-ae39e3c020f2.

**Định vị:** `data/News/VCB/batch_extracted.json` · snapshot `476e851a33decc9e629594f5637328a0b4ef4bcaf1e5f3bc2a36d589af2773ef` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

### REJECTED — 139. VCB · 97ebe30f-745f-576d-a3aa-08a65d013b38 / e1

**Bằng chứng nguồn:**
> VCB: HĐQT thông qua giao dịch giữa VCB và VCBNeo

**Code hiện trả:**

```json
{
  "event_type": "shareholder_meeting",
  "status": "unconfirmed",
  "parties": [
    {
      "name_raw": "VCB",
      "name_normalized": "VCB",
      "role": "unspecified",
      "name_source": "sentence"
    }
  ],
  "dates": {
    "event_date_start": null,
    "event_date_end": null,
    "date_precision": "unknown",
    "date_derived": false,
    "date_evidence": null,
    "date_candidates": []
  },
  "figures": []
}
```

**Nhóm kết luận:** `SAI_LOAI`.

**Vì sao REJECTED / cần làm gì:** Nguồn nêu nghị quyết/quyết định của HĐQT, không chứng minh một cuộc đại hội cổ đông. event_type=shareholder_meeting sai đối tượng hành động. Giữ đúng quyết định, nội dung phê duyệt và trạng thái; không tự chuyển thành cuộc họp hoặc hành động đã thực hiện.

**Nguồn đã đối chiếu:** finmind:shared-source:2264bbb9-024c-5634-abb5-58f399801b34:news_articles:97ebe30f-745f-576d-a3aa-08a65d013b38.

**Định vị:** `data/News/VCB/batch_extracted.json` · snapshot `551a42ee05fad6ab980e0d3c3106f090ce2e43611da932fa06f6307477d6f8e5` · index `2264bbb9-024c-5634-abb5-58f399801b34`.

## Bài trả events=[] — kiểm riêng việc lọc đầu vào

99 lượt / 88 article ID không có event. Không có cạnh để phê duyệt hoặc từ chối trong các bản này. Việc không tạo cạnh khi thiếu nội dung là an toàn, nhưng không đồng nghĩa đã nghiệm thu độ đầy đủ của extractor. Kiểm code cho thấy `relevance=not_relevant` hiện dựa vào không khớp trigger; đây không phải bằng chứng bài không có sự kiện.

**REJECTED — tiêu chí không bỏ sót:** ngay trong đầu vào có các ca sau mà events=[]; bằng chứng đã đủ để kết luận bộ lọc/trigger còn hụt. Không dùng 99 lượt rỗng để nâng số APPROVED.

| Article ID | Bằng chứng có trong nguồn | Kết quả và xử lý |
|---|---|---|
| `d16f533a-8c39-5de3-a538-63daebe92a40` | CMG: Đã mua lại 9.000 cp làm cp quỹ | REJECTED — Nguồn nêu CMG đã mua lại 9.000 cp làm cổ phiếu quỹ; events=[] bỏ sót hành động vốn. Tiêu đề chỉ giúp phát hiện ca hụt, cần đọc và ghim tài liệu kết quả trước khi tạo cạnh đầy đủ. |
| `b1d3c10f-9361-581a-bbee-08832ddc8a6d` | giao dịch ngân hàng có thể qua AI Agent Chia sẻ về xu hướng ứng dụng trí tuệ nhân tạo (AI) trong hoạt động ngân hàng tại sự kiện Smart Banking 2026 diễn ra mới đây, ông Trần Công Quỳnh Lân, Phó Tổng Giám đốc VietinBank dẫn dự báo của Công ty Gartner (Mỹ) và cho rằng, trong 3 năm tới, cách thức khách hàng sử dụng dịch vụ ngân hàng có thể thay đổi đáng kể. Hiện 99% giao dịch ngân hàng được thực hiện qua kênh ngân hàng số (digital banking), nhưng trong 3 năm tới, khoảng 50% giao dịch có thể được thực hiện thông qua AI Agent. Nhiều doanh nghiệp công nghệ tham gia cung cấp giải pháp AI | REJECTED — Nguồn nêu Trần Công Quỳnh Lân, Phó TGĐ VietinBank, chia sẻ tại Smart Banking 2026; events=[] bỏ sót sự kiện và vai trò diễn giả có trong text. |
| `32d87cf0-4e2d-5949-8189-c9b68b2078cf` | hát vọng làm chủ công nghệ và đưa trí tuệ Việt Nam vươn tầm quốc tế. Ghi nhận bản lĩnh vực doanh nhân và hành động phát triển CMC Lễ tôn vinh và trao tặng danh hiệu “Doanh nhân Việt Nam tiêu biểu - Cúp Thánh Gióng” năm 2026 do Liên đoàn Thương mại và Công nghiệp Việt Nam (VCCI) tổ chức ngày 10/11 tại Hà Nội, nhân dịp kỷ niệm Ngày Doanh nhân Việt Nam 13/10. Được VCCI khởi động từ năm 2006, Cúp Thánh Gióng bước vào kỳ bình xét lần thứ 10 vào năm 2026. Năm nay, chương trình lựa chọn 100 doanh nghiệp tiêu biểu từ hơn 260 hồ sơ được các bộ, ngành, địa phương và Hiệp hội doanh ngh | REJECTED — Nguồn có lễ vinh danh Nguyễn Trung Chính do VCCI tổ chức nhưng events=[]; ngày trong bài có dấu hiệu mâu thuẫn, phải giữ cảnh báo ngày thay vì coi không có sự kiện. |

**REJECTED — lựa chọn corpus chưa đúng quy tắc đã ghi trong template:** `meta.corpus.rule` yêu cầu bỏ bài chỉ có tiêu đề + PDF. Đầu vào hiện có nhiều bài “Các tập tin đính kèm … Theo HOSE”; bản text thông báo không thay thế nội dung PDF. Bài có nguồn/binding hợp lệ vẫn có thể chưa đạt tiêu chí text đủ để trích sự kiện. Sửa bộ lọc hoặc công bố rõ luồng đọc/ghim PDF; không tự coi JSON hợp lệ là đã đọc PDF.

## Test và thứ tự xử lý

1. Sửa trigger HĐQT/lãi suất/ví dụ chung; kiểm lại đúng loại và đúng chủ thể từ câu.
2. Giữ đối tác và người; alias phải có bằng chứng trong ngữ cảnh, không dùng tag làm cạnh.
3. Phân biệt ngày nghị quyết, chứng thư, hiệu lực, chốt quyền và thanh toán; giữ độ chính xác tháng/quý khi nguồn chỉ có thế.
4. Tách sự kiện khác đối tượng/hợp đồng ngay trong một bài trước khi dedup; không gộp chỉ vì cùng type/subject/ngày.
5. Sửa test đang không collect được do import parse_dates_extended/detect_status_rigorous không có; rồi chạy lại bộ ca nguồn thật và các probe lỗi.

Regression đã chạy: **137 passed, 9 skipped, 15 xfailed, 14 subtests passed**. Chạy bỏ xfail tái hiện **15 failed, 4 passed**; module test chính còn lỗi collect đã báo riêng. Không báo toàn bộ extractor đạt chỉ vì các test của module khác pass. Các lỗi nêu trên đang là kết quả kiểm thử, chưa được sửa code nghiệp vụ trong lượt này.

**Không ghi DB, không nạp Neo4j, không ký quyết định duyệt trong ứng dụng. Hai file bàn giao tự chứa bằng chứng cần đọc; không cần gửi kèm JSON/log.**
