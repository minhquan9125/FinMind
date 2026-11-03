# WBS15 – API contract cho Graph Viewer (bằng chứng thật)

Phiên bản contract: `graph-viewer-v1` · 03/11/2026 · bên cung cấp: WBS09 (Hưng) · bên dùng: WBS15 (Huyền).

Contract này mô tả dữ liệu Graph Viewer (`frontend/src/pages/graph/`) đọc từ graph Sprint 4
(WBS08 Neo4j, WBS09 `RelationRetrieval`). Backend đã có route tại
`backend/src/api/routers/graph_viewer.py` (truy vấn ở `backend/src/graph/viewer.py`, test
`backend/tests/test_graph_viewer_api.py`). UI có thể dựng bằng fixture đúng shape này (mục 7), rồi
chỉ thay thân `getGraph` trong `api.js`.

## 1. Nguyên tắc

- Chỉ đọc graph version `READY`. Mọi cạnh trong graph đã qua WBS06 (`APPROVED`); API không trả
  quan hệ PENDING/REJECTED và không có cờ để xin chúng.
- **Một request = một `graph_version_id`.** Không trộn phiên. Mọi response trả lại `meta` của
  phiên đó để UI hiển thị và so khớp.
- Backend tự kiểm giới hạn (hop ≤ 2, limit, timeout); không tin tham số từ frontend.
- Locator giữ nguyên như lúc trích xuất. BCTN/PDF có `page`; News không có trang → `page: null`,
  UI **không** tự tạo trang PDF.
- Lỗi API hiển thị là lỗi (ErrorState). Không thay bằng dữ liệu minh họa.
- Auth: `Authorization: Bearer <access_token>`, vai trò đọc như `market-data`
  (`RESEARCHER`, `FINANCIAL_ANALYST`, `DATA_ENGINEER`, `EVALUATOR`, `ADMINISTRATOR`).
- Ngày: `YYYY-MM-DD`; thời điểm: ISO 8601 có múi giờ.

## 2. `GET /api/graph/versions`

Danh sách phiên graph có thể xem. UI dùng để chọn phiên (mặc định: phần tử đầu, mới nhất).

```json
{
  "versions": [
    {
      "graph_version_id": "ae47d046-fb4f-579c-8d78-2287770bf8ea",
      "status": "READY",
      "corpus_id": "b2550a0b-c423-5c50-9b15-6fb6af12e2c6",
      "index_version_id": "ecfbf20f-b3e0-5077-bd3e-03f0efb95e6d",
      "contract_version": "2.1.0",
      "relation_count": 13
    }
  ]
}
```

- Chỉ trả `READY`. Rỗng → `{"versions": []}` (UI: EmptyState "Chưa có phiên graph được công bố").
- BCTN và News là phiên riêng vì khác index; phân biệt qua `index_version_id`. WBS08 chưa lưu thời
  điểm publish nên không có trường đó.

## 3. `GET /api/graph/entities`

Tìm root (thay `rootOptions` cố định trong `mock.js`).

| Tham số | Bắt buộc | Mô tả |
|---|---|---|
| `graph_version_id` | có | UUID phiên |
| `q` | có | 1–100 ký tự; mã CK (tra registry → `entity_id`), `entity_id`, hoặc chuỗi con của tên/alias (không phân biệt hoa thường) |
| `type` | không | `Company` \| `Person` \| `Event` |
| `limit` | không | 1–50, mặc định 20 |

```json
{
  "meta": { "graph_version_id": "ae47d046-fb4f-579c-8d78-2287770bf8ea", "status": "READY" },
  "items": [
    {
      "id": "CMP-00e0481af8b436b4645f",
      "type": "Company",
      "label": "Ngân hàng Thương mại Cổ phần Kỹ Thương Việt Nam",
      "ticker": "TCB",
      "relation_count": 5
    }
  ],
  "truncated": false
}
```

## 4. `GET /api/graph/neighborhood`

Đồ thị quanh một root, dùng cho Cytoscape. Shape `nodes/edges` giữ như fixture hiện tại
(`id`, `type`, `label`, `detail`, `source`, `target`), thêm trường bằng chứng.

| Tham số | Bắt buộc | Mô tả |
|---|---|---|
| `graph_version_id` | có | UUID phiên `READY` |
| `entity_id` | có | `id` từ mục 3 |
| `hops` | không | `1` hoặc `2`, mặc định `2` (UI tự mở rộng dần trong dữ liệu đã tải) |
| `relation_type` | không | lặp được; `OWNS_SHARES`, `HAS_SUBSIDIARY`, `HAS_ASSOCIATE`, `COOPERATES_WITH`, `HOLDS_ROLE`, `APPOINTS`, `DISMISSES`, `INVOLVES` |
| `from`, `to` | không | khoảng ngày; cạnh chỉ có `as_of` phải nằm trong khoảng, cạnh có `valid_from/valid_to` chỉ cần giao khoảng |
| `limit` | không | số đường đi tối đa 1–100, mặc định 50 |

```json
{
  "meta": {
    "graph_version_id": "ae47d046-fb4f-579c-8d78-2287770bf8ea",
    "status": "READY",
    "corpus_id": "b2550a0b-c423-5c50-9b15-6fb6af12e2c6",
    "index_version_id": "ecfbf20f-b3e0-5077-bd3e-03f0efb95e6d",
    "root_id": "CMP-00e0481af8b436b4645f",
    "hops": 2,
    "filters": { "relation_type": [], "from": null, "to": null },
    "limit": 50,
    "truncated": false,
    "generated_at": "2026-11-04T09:05:00+07:00"
  },
  "nodes": [
    {
      "id": "CMP-00e0481af8b436b4645f",
      "type": "Company",
      "label": "Ngân hàng Thương mại Cổ phần Kỹ Thương Việt Nam",
      "detail": "TCB",
      "ticker": "TCB",
      "aliases": ["TCB", "Techcombank", "Ngân hàng TMCP Kỹ thương Việt Nam"],
      "attributes": {}
    },
    {
      "id": "CMP-322902610d1a878d95d3",
      "type": "Company",
      "label": "Công ty Cổ phần Chứng khoán Kỹ Thương",
      "detail": "TCBS",
      "ticker": "TCBS",
      "aliases": ["TCBS", "Công ty Cổ phần Chứng khoán Kỹ Thương"],
      "attributes": {}
    }
  ],
  "edges": [
    {
      "id": "review:bceddd14947a63a6afddeb22ec2cc385",
      "source": "CMP-00e0481af8b436b4645f",
      "target": "CMP-322902610d1a878d95d3",
      "type": "HAS_SUBSIDIARY",
      "attributes": { "consolidation_basis": "hợp nhất toàn bộ" },
      "temporal": { "as_of": "2025-12-31", "valid_from": null, "valid_to": null },
      "review": {
        "status": "APPROVED",
        "reviewer": "Trần Diệu Huyền",
        "reviewed_at": "2026-11-02T17:13:40+07:00"
      },
      "evidence_count": 3,
      "evidence_preview": {
        "document_id": "85deaf00-3748-5f3d-95a2-68495dc229fc",
        "page": 154,
        "quote": "… Công ty Cổ phần Chứng khoán Kỹ Thương …"
      }
    }
  ]
}
```

Quy ước:

- `edges[].id` = `relation_id` (duy nhất trong một phiên). `source` → `target` theo đúng chiều
  quan hệ (`HOLDS_ROLE`: Person → Company; `APPOINTS`/`DISMISSES`: Company → Person;
  `INVOLVES`: Event → Company/Person; `COOPERATES_WITH`: không có hướng nghĩa, ID nhỏ hơn là `source`).
- Node `type`: `Company` | `Person` | `Event`. Event có `attributes.event_type`, `attributes.occurred_at`.
- `detail`: chuỗi ngắn để hiển thị (mã CK của Company, `event_type` của Event); có thể `null`.
- `evidence_preview`: evidence đầu tiên của cạnh (`page` từ locator, có thể `null`); tên tài liệu và
  link mở nguồn chỉ có ở mục 5.
- Hai quan hệ cùng cặp nhưng khác thời điểm là **hai cạnh** (ví dụ TCB→TCBS `as_of` 2024-12-31 và
  2025-12-31). UI phải hiển thị được cạnh song song.
- **Rỗng:** root có trong phiên nhưng không có cạnh khớp bộ lọc → `200`, `nodes` chỉ có root, `edges: []`.
- **Nhiều kết quả:** vượt `limit` → `meta.truncated: true`; UI báo "Đang hiển thị một phần, hãy lọc
  theo loại quan hệ/thời gian".

## 5. `GET /api/graph/relations/{relation_id}`

Chi tiết khi bấm cạnh (Drawer). Tham số bắt buộc: `graph_version_id`.

```json
{
  "meta": { "graph_version_id": "ae47d046-fb4f-579c-8d78-2287770bf8ea", "status": "READY" },
  "relation": {
    "id": "review:bceddd14947a63a6afddeb22ec2cc385",
    "type": "HAS_SUBSIDIARY",
    "source": { "id": "CMP-00e0481af8b436b4645f", "type": "Company", "label": "Ngân hàng Thương mại Cổ phần Kỹ Thương Việt Nam" },
    "target": { "id": "CMP-322902610d1a878d95d3", "type": "Company", "label": "Công ty Cổ phần Chứng khoán Kỹ Thương" },
    "attributes": { "consolidation_basis": "hợp nhất toàn bộ" },
    "temporal": { "as_of": "2025-12-31", "valid_from": null, "valid_to": null },
    "review": { "status": "APPROVED", "reviewer": "Trần Diệu Huyền", "reviewed_at": "2026-11-02T17:13:40+07:00" },
    "extraction": {
      "relation_id": "review:bceddd14947a63a6afddeb22ec2cc385",
      "source_batch_id": "wbs09:1f0c…",
      "corpus_id": "b2550a0b-c423-5c50-9b15-6fb6af12e2c6",
      "index_version_id": "ecfbf20f-b3e0-5077-bd3e-03f0efb95e6d"
    }
  },
  "evidence": [
    {
      "document_id": "85deaf00-3748-5f3d-95a2-68495dc229fc",
      "document_version": "835e04340143d6d419cad400389ca1161da0178e4497cdd9ec34c2966cb0c14b",
      "chunk_id": "4d3df972-94af-535a-ad99-fefdc1aa69e1",
      "title": "TCB — Báo cáo thường niên 2025",
      "doc_type": "ANNUAL_REPORT",
      "quote": "… đoạn nguyên văn từ chunk …",
      "locator": {
        "kind": "db_text_span", "page": 154, "section_index": 153,
        "char_start": 0, "char_end": 523, "text_start": 47,
        "offset_basis": "normalized_section_body", "offset_unit": "unicode_codepoint",
        "content_hash": "5898cf1d7ca12b65917e792d70034f5cbd6bc0754fca88fce9a6010b4cf9cb93"
      },
      "open": {
        "status": "AVAILABLE",
        "kind": "PDF_PAGE",
        "url": "https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/TCB_Baocaothuongnien_2025.pdf",
        "page": 154,
        "reason": null
      }
    }
  ]
}
```

- `locator` trả **nguyên văn** như lúc trích xuất (hiện có trong `evidence_json` trên cạnh Neo4j).
- `quote` là đoạn đã được duyệt; UI hiển thị nguyên văn, không cắt ghép.
- `open`: backend lấy `documents.source_url` theo **`chunk_id`** (`text_chunks` → `documents`, như
  `read_annual_chunk`), vì `document_id` của corpus khác có thể là release alias; tra theo chunk
  luôn ra đúng tài liệu chứa đoạn nguồn.
  - `kind`: `PDF_PAGE` (BCTN, mở `url#page=<page>`) | `WEB_ARTICLE` (News, mở `url`, `page: null`).
  - `status`: `AVAILABLE` | `UNAVAILABLE`. `UNAVAILABLE` kèm `reason`: `SOURCE_URL_MISSING` hoặc
    `DOCUMENT_NOT_FOUND` (chunk không còn trong DB, hoặc DB tra nguồn lỗi). Khi `UNAVAILABLE`,
    `url: null`; UI vẫn hiện quote và locator, ghi "Không mở được nguồn gốc".
  - `title`, `doc_type` lấy từ DB; `null` khi không tra được.
- Không có endpoint xem PDF nội bộ trong contract này; UI mở URL gốc ở tab mới.

## 6. Lỗi

Theo kiểu FastAPI hiện có: `{"detail": {"code": "...", "message": "..."}}`.

| HTTP | `code` | Khi nào | UI |
|---|---|---|---|
| 400 | `INVALID_PARAMETER` | ngày sai định dạng, `from` > `to`, loại quan hệ/`type` lạ | báo lỗi tham số |
| 422 | (FastAPI) | thiếu tham số bắt buộc, `hops`/`limit`/`q` ngoài miền | báo lỗi tham số |
| 401/403 | (auth) | thiếu/không đủ quyền | về đăng nhập |
| 404 | `GRAPH_VERSION_NOT_FOUND` | phiên không tồn tại | chọn phiên khác |
| 409 | `GRAPH_VERSION_NOT_READY` | phiên đang `BUILDING` | "Phiên chưa công bố" |
| 404 | `ENTITY_NOT_FOUND` | root không có trong phiên | EmptyState, gợi ý tìm lại |
| 404 | `RELATION_NOT_FOUND` | cạnh không thuộc phiên | đóng Drawer, báo lỗi |
| 503 | `GRAPH_UNAVAILABLE` | Neo4j không kết nối được | ErrorState + Thử lại |
| 504 | `GRAPH_TIMEOUT` | quá timeout truy vấn (5 giây) | ErrorState, gợi ý giảm hop/lọc |

## 7. Fixture cho UI (trước khi có API)

- Giữ `?fixture=empty|error|loading` của trang hiện tại; thêm `?fixture=truncated` và
  `?fixture=source-unavailable`.
- Fixture phải theo shape mục 4–5 và có nhãn rõ là fixture trên UI (`StatusBadge` "Fixture"), giống
  footer hiện tại. Khi gọi API thật thì không còn nhánh rơi về fixture lúc lỗi.
- Dữ liệu fixture đề xuất: 13 quan hệ TCB/ELC của gói Nhân V4 (đã được WBS06 duyệt), gồm cặp
  TCB→TCBS hai thời điểm để thử cạnh song song.

## 8. Kiểm tra khi nghiệm thu WBS15

- So một cạnh trên màn hình với `GET /api/graph/relations/{id}`: loại, chiều, thời gian, người
  duyệt, quote, locator, `graph_version_id` trùng khớp.
- Đổi phiên → toàn bộ node/cạnh tải lại theo phiên mới, không giữ cạnh của phiên cũ.
- Rỗng, `truncated`, 409, 503/504, `open.status = UNAVAILABLE` đều có trạng thái riêng.
- Màn hình hẹp (≤ 390 px): Drawer đọc được quote/locator, không tràn ngang.

## 9. Phía backend (đã triển khai, WBS09)

- `neighborhood` dùng `RelationRetrieval.query` (`backend/src/graph/relation_retrieval.py`), xin thêm
  1 đường đi để biết `truncated`; node đọc từ `GraphEntity` của cùng phiên.
- `versions`, `entities`, `relations/{id}` là truy vấn đọc trên Neo4j (`GraphVersion`,
  `GraphEntity`, `GRAPH_RELATION`), timeout 5 giây. Kết nối lấy từ `NEO4J_*` như `GraphStore`.
- Chưa chạy trên Neo4j thật; test dùng reader giả.
- `open` đọc `documents.source_url`/`doc_type` từ PostgreSQL theo `chunk_id` trong corpus của phiên
  (đã kiểm trên DB VPS: chunk `4d3df972…` → tài liệu `85deaf00…`, trang 154,
  `https://static2.vietstock.vn/data/HOSE/2025/BCTN/VN/TCB_Baocaothuongnien_2025.pdf`;
  News lưu URL FireAnt `https://fireant.vn/bai-viet/...`).
- `review.reviewer` lấy từ cạnh Neo4j; gói V4 tái tạo bằng script hiện ghi
  `WBS06-offline-proposal-for-user-acceptance`, cần WBS06/WBS07 ghi tên người duyệt thật trước khi nạp.
