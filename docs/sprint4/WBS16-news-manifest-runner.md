# WBS16 — runner News theo manifest, chuẩn bị full-load

Runner mới: `backend/scripts/run_news_manifest.py`. Dùng lại
`documents.news_event_extractor.extract_batch`, không dùng runner legacy
`run_wbs16_extractor.py` làm bằng chứng nghiệm thu. Không sửa extractor, crawler,
chunking, model, router, chat hay quyết định WBS06.

## Phần đã chuẩn bị và giới hạn

- Đọc đúng danh sách News từ locator của manifest có pin SHA256. Từ chối bài
  ngoài manifest, ID trùng, manifest bị sửa hoặc đề xuất ngoài danh sách.
- Mọi bài có trạng thái staging: `PENDING_REVIEW`, `QUARANTINED`, `NO_CANDIDATE`,
  `ERROR`, `MISSING_SOURCE`, hoặc `UNPROCESSED`. Hai trạng thái đầu là hàng đợi
  cục bộ; chưa ghi quyết định vào review store/quarantine DB.
- `NO_CANDIDATE` chỉ nghĩa là bộ luật hiện có chưa tìm thấy ứng viên; không khẳng
  định tài liệu không có quan hệ. Mọi ứng viên còn cần kiểm định WBS06.
- Checkpoint tách từng bài, ghi atomic, không nhân đôi khi resume. Pin corpus,
  manifest, đầu vào, candidates, receipt và phiên/code extractor. Đầu vào đổi phải
  mở output mới; không sửa checkpoint để tiếp tục. `--retry-errors` thử lại bài
  lỗi với cùng đầu vào, không chạy lại bài đã hoàn tất.
- `--limit` dừng sau số bài chỉ định; `--resume` tiếp tục. Lock ngăn hai runner
  ghi cùng thư mục. Nếu tiến trình bị kill cứng, xác minh tiến trình đã dừng rồi
  mới xóa riêng `.runner.lock`; không xóa dữ liệu checkpoint.
- `report.json` phân biệt staging hoàn tất, kiểm định và đối chiếu DB.
  `database_writes=0`, `review_decisions_written=0`,
  `acceptance_status=NOT_EVALUATED` luôn được giữ ở tầng này.

Đây là runner **staging** và công cụ đối chiếu export. Chưa thay đường ghi
Supabase/Neo4j của WBS01–WBS09. Chưa có receipt WBS09.5 và bộ News thật được bàn
giao để kiểm chứng full-load trong phiên này. Không đánh dấu WBS16 hoàn thành
chỉ vì fixture chạy hoặc hai export trùng nhau.

## Cần lấy tài liệu từ nhóm

1. Hưng/WBS09: receipt kiểm tra mẫu 09.5 mới nhất; lệnh, phiên bản code,
   input/output envelope News, bằng chứng nguồn, kiểm duyệt, rerun và đối chiếu.
   Xác nhận adapter nào chuyển event candidates sang envelope graph; không tự
   dùng `event_group_id` làm `relation_id`.
2. Nhân/data: manifest News đã chốt và SHA256, corpus/index ID; các hàng News
   đúng phiên nguồn; cách đọc nguồn đã ghim và export khóa từ PostgreSQL/Neo4j.
3. Huyền/WBS06: trạng thái APPROVED/PENDING/REJECTED/QUARANTINED và người xử lý
   ca chờ duyệt. Không dùng kết quả trích xuất thay quyết định phê duyệt.

## Chạy fixture và resume

Từ gốc FinMind, dùng Python môi trường hiện có:

```powershell
.\.venv\Scripts\python.exe backend/scripts/run_news_manifest.py --mode fixture --manifest PATH/manifest.json --articles PATH/articles.json --output outputs/wbs16-fixture --limit 10
.\.venv\Scripts\python.exe backend/scripts/run_news_manifest.py --mode fixture --manifest PATH/manifest.json --articles PATH/articles.json --output outputs/wbs16-fixture --resume
```

`articles.json` là array các hàng có `article_id`, `content`, `source`, `url`,
`published_at` nếu có. Thiếu hàng thuộc manifest được báo riêng. Runner không
tự xác minh bài export với DB; người bàn giao phải xuất đúng nguồn đã ghim.
`--candidates` tùy chọn là object `article_id -> array` theo contract extractor
hiện có. Nếu không cung cấp cho một bài, dùng bộ luật hẹp hiện có.

## Gate full và receipt bàn giao

`--mode full --receipt PATH/receipt.json` kiểm gate trước khi tạo output.
Gate chỉ cho chạy toàn danh sách staging; **không cho ghi DB hoặc duyệt graph**.
Định dạng dưới đây là định dạng bàn giao cục bộ của runner, cần thống nhất với
Hưng; không tự khẳng định đây là schema receipt WBS09.5 sẵn có của nhóm.

```json
{
  "schema_version": "wbs09.5-news-handoff-v1",
  "status": "NOT_READY",
  "execution_mode": "LIVE",
  "corpus_version_id": "COPY_FROM_APPROVED_MANIFEST",
  "manifest_sha256": "COPY_FROM_APPROVED_MANIFEST",
  "extractor_version": "news-event-extractor-v1",
  "reviewer": null,
  "reviewed_at": null,
  "evidence_paths": [],
  "checks": {
    "source_verified": false,
    "extractor_contract": false,
    "review_gate": false,
    "idempotent_rerun": false,
    "postgres_neo4j_keys": false
  }
}
```

Mẫu này cố ý chưa đạt. Chỉ người phụ trách kiểm tra cập nhật từ bằng chứng thật.
Gate kiểm tra nội dung khai báo, không kiểm chữ ký hay xác thực người duyệt.
Không đổi thành PASS để mở khóa chạy khi chưa có bằng chứng.

## Đối chiếu hai DB bằng export

Truyền `--postgres-inventory` và `--neo4j-inventory`. Mỗi export có:

```json
{
  "corpus_version_id": "SAME_CORPUS",
  "manifest_sha256": "SAME_MANIFEST_HASH",
  "graph_version_id": "SAME_GRAPH_VERSION",
  "relations": [
    {"relation_id": "REAL_RELATION_KEY", "document_ids": ["REAL_MANIFEST_DOCUMENT_ID"], "review_status": "APPROVED"}
  ]
}
```

PostgreSQL export phải bao gồm toàn bộ quan hệ trong phạm vi, kể cả chưa duyệt;
Neo4j export phải là toàn bộ cạnh của cùng phiên News. Người xuất cần lấy
document IDs từ evidence thật, không đoán từ mã công ty. Không dùng export cắt
mẫu hoặc trộn graph BCTN với News để nghiệm thu.

So sánh tập ID APPROVED của PostgreSQL với Neo4j, đồng thời đối chiếu document
IDs, ghi riêng khóa thiếu/thừa, trạng thái chưa duyệt lọt Neo4j và thống kê mỗi
tài liệu. Thiếu export trả `NOT_READY`; dữ liệu lệch trả `FAIL` và CLI exit 1.
`PASS` chỉ là hai export khớp khóa; không xác nhận độ đầy đủ hay nguồn live của
export, chất lượng trích xuất, hoặc sự đồng bộ DB hiện tại.

Exit code: 0 staging hoàn tất và không phát hiện lệch export; 1 còn bài lỗi,
thiếu/chưa xử lý hoặc đối chiếu FAIL; 2 đầu vào/gate/checkpoint không hợp lệ.
Exit 0 không có nghĩa WBS16 đã nghiệm thu.

## Kiểm thử

```powershell
$env:PYTHONPATH='.;backend'
.\.venv\Scripts\python.exe -m pytest backend/tests/test_news_batch_runner.py backend/tests/test_news_event_extractor.py -q
```

Kiểm tra gate, phạm vi, resume sau ngắt, input/checkpoint thay đổi, không trùng,
lỗi từng bài, thiếu nguồn, trạng thái chưa duyệt và đối chiếu khóa sai/thiếu/thừa.
Các test dùng fixture, không truy cập DB/model/LLM. Bộ legacy
`test_wbs16_event_extractor.py` hiện lỗi import `parse_dates_extended`; đó là
đường extractor khác, chưa được runner này sửa hoặc nghiệm thu.
