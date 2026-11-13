# Đánh giá toàn bộ dự án trên nhánh `backup-demo` và kế hoạch hoàn thiện

Ngày: 13/11/2026. Người kiểm: Hưng (cùng Claude).
Nhánh kiểm: `backup-demo` @ `4544ba04` (đã gồm PR #76 `feature/bctc-health-chat`).

Cách kiểm:
- dựng đồ thị import từ `backend/src/main.py`, tính cả import nằm trong hàm;
- đối chiếu route backend với lời gọi frontend;
- đối chiếu bảng DB với code;
- chạy toàn bộ test;
- so `backup-demo` với các nhánh còn lại.

Mọi số liệu dưới đây đều đo trên máy, không ước đoán.

## 0. Kết luận nhanh

- **`backup-demo` mới là nhánh chính thật.** `main` dừng ở 05/10 và chậm 176 commit. Cần chốt với nhóm: đổi nhánh mặc định trên GitHub, hoặc đưa `backup-demo` vào `main`.
- **Chat chạy được, nhưng có 3 cơ chế phân loại ý định chồng nhau.** Bộ phân loại của Nhân/Huyền (Sprint 5) chưa có trên nhánh chính.
- **Web chỉ có 3 phần dùng dữ liệu thật: chat, đồ thị và trang admin.** Dashboard, danh sách công ty, phần tài chính trong trang công ty, Profile và Watchlist vẫn dùng dữ liệu giả, dù DB đã có dữ liệu thật.
- **DB có khoảng 26 bảng đã thiết kế nhưng không có code dùng.** Trong khi đó, trang admin lưu job, đánh giá, cấu hình, audit và khóa Gemini vào SQLite trên máy chạy backend.
- **Test:** 3243 pass, 6 fail. Cả 6 lỗi đều do môi trường hoặc thiếu file mẫu, không phải lỗi logic.

## 1. Luồng chat hiện tại (đã nối)

```
Tin nhắn → research_chat.get_store → ObservedResearch(LiveResearchService)
  1. Chào hỏi → trả lời cố định
  2. WebChatRouter (hybrid_router: decision_engine + intent_policy, luật)
       └ chỉ nhận route GRAPH/BOTH → Neo4jChatRetriever (chức vụ, quan hệ) ; còn lại trả None
  3. AdminNewsChat (tin đã OCR/duyệt từ trang admin) → nếu NO_DATA thì đi tiếp
  4. analyze_live (regex trong live_research.py)
       ├ MARKET_LOOKUP: giá / tin / phân tích (MarketResearch: giá, xu hướng + chỉ báo, sức khỏe BCTC, tin)
       ├ SEARCH: BCTC/BCTN qua DenseEvidenceRetriever (pgvector, corpus phục vụ)
       └ hỏi lại / từ chối
  5. complete_retrieval → Gemini (xoay khóa, gọi lại 1 lần khi quá tải) → kiểm trích dẫn từng ý
```

**Ba cơ chế phân loại ý định đang tồn tại:**

| Cơ chế | Ở đâu | Trạng thái |
|---|---|---|
| hybrid_router (luật) | `retrieval_orchestration/hybrid_router/` | Đang chạy, chỉ cho GRAPH/BOTH |
| analyze_live (regex) | `live_research.py` | Đang chạy cho BCTC, tin, giá, phân tích |
| Router embedding V7 + contract fallback (Nhân, Huyền) | nhánh `nhan-sprint-501`, `huyen-sprint-sprint501` | **Chưa merge.** Mỗi nhánh có 2 xung đột với `backup-demo` |

## 2. Phát hiện chi tiết

### 2.1 Frontend: các trang còn dùng dữ liệu giả

| Trang | Nguồn dữ liệu hiện tại | DB/API thật đã có |
|---|---|---|
| Dashboard (`pages/dashboard/api.js`) | `makeDashboardFixture()` | Giá, tin, xu hướng có trong DB; **chưa có API** |
| Danh sách công ty (`pages/companies/api.js`) | `catalogFixtures` | Bảng `companies`; **chưa có API** |
| Chi tiết công ty: phần tài chính (`detailApi.js`, `detailMock.js`) | Số tổng tài sản/nợ viết cứng theo mã | `financial_reports`, `observations`, sức khỏe BCTC (`health_db.get_financial_health`); **chưa có API** |
| Chi tiết công ty: giá, tin | **Thật** (`marketDataApi.js`) | ✔ |
| Profile (`pages/profile/api.js`) | `profileFixtures` | Bảng users/roles; **chưa có API `/me`** |
| Watchlist | Lưu ở `localStorage`, dùng `researcherMock` | Bảng `watchlists` có trong schema nhưng **không có code** |
| Research (chat) | **Thật** | ✔ |
| Graph | **Thật** (`/api/graph`, có chế độ dữ liệu mẫu) | ✔ |
| Admin (ingestion, jobs, traces, sources, corpus, cấu hình, đánh giá, audit) | **Thật** (`operationsApi.js`, admin ingestion) | ✔ |

Tên người dùng trên menu ở nhiều trang vẫn lấy từ `researcherMock`/`userMenu`, chưa lấy từ tài khoản đăng nhập.

### 2.2 Backend: API còn thiếu

- `GET /api/companies`, `GET /api/companies/{symbol}`: danh mục công ty.
- `GET /api/companies/{symbol}/financials?period=`: số liệu BCTC theo kỳ, kèm trạng thái đã đối chiếu PDF.
- `GET /api/companies/{symbol}/health`: dùng lại `get_financial_health`, chat đã dùng hàm này.
- `GET /api/market-data/stocks/{symbol}/trend`: chỉ báo kỹ thuật. Hàm `get_price_trend` đã có; cần kiểm route `/analysis` đã trả phần này chưa.
- `GET /api/auth/me`, `PUT /api/watchlist`.
- `GET /api/dashboard`: gom giá, tin mới, mã theo dõi.

### 2.3 Code không được app gọi tới

Tổng: 388 module, 140 module được gọi từ `main.py`. Phần còn lại:

| Nhóm | Ghi chú | Đề xuất |
|---|---|---|
| `backend/src/**/.agent-state/`, `vector_retrieval/.work/` (~170 file) | Bản nháp của agent; **git không theo dõi**, chỉ nằm trên máy | Xóa trên máy hoặc thêm vào `.gitignore`. Không ảnh hưởng nhánh chính |
| `person_role/*`, `graph/*` (ingest, sprint4_store, wbs09_pipeline, source_person_claims), `graph_review/*`, `sprint4_runtime/*` | Pipeline trích xuất người/quan hệ và đẩy lên Neo4j, chạy bằng `backend/scripts` | Đúng thiết kế (chạy offline). Cần một tài liệu chạy lại pipeline và chốt 1 bản duy nhất (đang có `sprint4_runtime`, `wbs02_person_registry` và `person_role` trùng chức năng: `contracts.py`/`entities.py` lặp ở 3 nơi) |
| `wbs02_person_registry/*` | Chỉ test gọi; test thiếu file mẫu `backend/resources/person_role/wbs02-r2/examples/*.json` (chưa commit) | Commit file mẫu, hoặc gộp vào `person_role` |
| `documents/event_news.py` (863 dòng), `wbs16_extractor.py` ở thư mục gốc | Trích sự kiện từ tin (WBS16); chỉ có script và test | Chốt có đưa vào chat hoặc đồ thị không; nếu không thì để trong `scripts` |
| `financial/verification*.py`, `statement_pdf.py` | Chạy qua job `refresh_financial_statements.py` | Đúng thiết kế |
| `retrieval_orchestration/hoi.py`, `web_sessions.py`, `vector_retrieval/hoi.py`, `b1_answering/cli`, `hybrid_router/evaluate_baseline.py` | CLI và kho phiên cũ dùng file JSON (web chat đã chuyển sang Postgres) | Đánh dấu là công cụ dev hoặc xóa |

### 2.4 Cơ sở dữ liệu

**Bảng có trong schema nhưng không có code dùng:**
- `watchlists`, `feedback`;
- `queries`, `query_companies`, `retrieval_results`, `answers`, `claims`, `citations`, `claim_verifications`: dùng để lưu vết từng câu hỏi;
- `audit_logs`, `usage_events`;
- `evaluation_runs`, `evaluation_results`, `golden_sets`, `golden_questions`, `golden_question_companies`;
- `system_configs`, `config_versions`;
- `permissions`, `role_permissions`;
- `gate_decisions`, `gate_decision_evidence`, `calc_inputs`, `corpus_facts`, `metric_aliases`, `reason_codes`, `admin_serving_corpus`.

**Lưu trữ trùng chức năng:** trang admin lưu job, bài viết, đánh giá, giới hạn, budget, khóa Gemini (đã mã hóa) và số liệu chat vào SQLite trong `admin_ingestion_directory` (`admin_ingestion.py`, `evaluation_runner.py`, `limit_overrides.py`, `api_budget.py`, `key_store.py`, `research_metrics.py`). Hệ quả:
- dữ liệu này nằm trên máy chạy backend, mỗi máy một bản;
- không dùng các bảng Postgres tương ứng đã thiết kế (`audit_logs`, `evaluation_*`, `system_configs`).

**Schema lệch nhau:**
- `daily_market_activity` chỉ có trong `supabase/migrations`. File khởi tạo `docker/postgres/init` thiếu bảng này, nên Docker dựng mới sẽ thiếu bảng.
- `admin_serving_corpus` thì ngược lại: chỉ có trong Docker init, thiếu trong migration.

**Dữ liệu BCTC (đo trên VPS):**
- 172 báo cáo đã đối chiếu: 22 khớp đủ, 120 khớp một phần, 30 lệch.
- Phần sức khỏe tài chính: 7/10 mã chưa có chỉ số nào đã xác minh.
- Job tự cập nhật (`FINMIND_BCTC_REFRESH`) đang tắt.

### 2.5 Bảo mật và cấu hình

- `jwt_secret_key` có giá trị mặc định viết cứng trong `core/config.py`. Nếu `.env` không đặt thì mọi môi trường dùng chung secret này.
- `POST /api/search/price` và `POST /api/search/filtered` **không yêu cầu đăng nhập**. Route `filtered` còn chạy embedding, nên dễ bị lạm dụng tài nguyên.
- Endpoint làm mới token (`/api/auth/refresh`) đã có.

### 2.6 Test và môi trường

- 6 test fail:
  - `test_admin_news_ocr`: venv thiếu `Pillow`. Gói này có trong `requirements.txt` nhưng chưa cài;
  - 5 test `test_wbs02_person_identity_integration`: thiếu file mẫu chưa commit.
- Repo chứa file tạm đã commit:
  - `tmp/` (1605 file);
  - ở thư mục gốc: `chunks_thu.json`, `interactive_test.py`, `run_event_news.py`, `wbs16_extractor.py`, `test_wbs16_extractor.py`, `interface/`, `models/`.
- `outputs/` (414 MB) và `data/` (2,5 GB) nằm trên máy.

### 2.7 Nhánh còn chưa merge vào `backup-demo`

| Nhánh | Nội dung | Số commit | Ghi chú |
|---|---|---|---|
| `feature/wbs10-wbs14-routed-answer` (Quân, 13/11) | Ghép bằng chứng BOTH (đồ thị + tài liệu), câu trả lời theo route | 1 | Sửa `live_research.py`, `hybrid_router`, `ResearchChat.jsx`; ưu tiên review và merge |
| `huyen-sprint-sprint501` | Router 04.2 + contract fallback 07.1 | 60 | 2 xung đột |
| `nhan-sprint-501` | Thư viện ý định V7, đặc tả nhãn v2 | 51 | 2 xung đột; chờ `classify_intent` và run04 |
| `nhan-sprint-411`, `hungLamDum`, `huyen-fe`, `feature/ocr-pipeline`, `feature/CrawlingNews`, `main`… | Cũ (trước 10/11) | — | Cần chủ nhánh xác nhận đóng hay merge |

## 3. Kế hoạch đề xuất

Thứ tự theo phụ thuộc. Người phụ trách theo sheet Sprint 5; task chưa có người nhận thì ghi "cần giao".

### Giai đoạn 1: Dọn nền, 1–2 ngày (trước 15/11)

1. Chốt nhánh chính: đưa `backup-demo` thành nhánh mặc định, hoặc merge vào `main`. *Người quyết: cả nhóm.*
2. Review và merge `feature/wbs10-wbs14-routed-answer` (BOTH, 12.2) trước, vì nhánh này sửa đúng luồng chat. *Quân, Hưng review.*
3. Sửa môi trường test: cài `Pillow`, commit file mẫu WBS02 (hoặc gỡ test). Xóa `tmp/` và các file tạm ở thư mục gốc khỏi git. *Cần giao.*
4. Bảo mật:
   - bỏ giá trị mặc định của `jwt_secret_key` (thiếu thì báo lỗi khi khởi động);
   - thêm yêu cầu đăng nhập cho `/api/search/price` và `/api/search/filtered`.
   *Quân (06.x).*
5. Đồng bộ schema: thêm `daily_market_activity` vào Docker init, thêm `admin_serving_corpus` vào migration. *Cần giao.*

### Giai đoạn 2: Một bộ định tuyến duy nhất cho chat, tuần 2

6. Chốt bộ nhãn v2 (11 nhóm, file `S5-INTENT-v2-gui-Nhan.md`). *Nhân, Huyền.*
7. Nhân giao `classify_intent()` cùng thư viện v2 và kết quả run04 (BGE-M3). Huyền cập nhật router 04.2 và contract 07.1 theo nhãn mới, rồi rebase lên `backup-demo` (giải 2 xung đột). *Nhân, Huyền.*
8. Gộp 3 cơ chế thành một luồng (05.1 và 07.2), không phá các luồng đang đúng:
   - router v2 chạy trước và quyết định nhóm;
   - `hybrid_router` trở thành bộ xử lý của nhóm GRAPH/BOTH;
   - `analyze_live` chỉ còn làm việc trích slot (mã, kỳ, chỉ tiêu, trọng tâm) và xử lý các nhóm GIA/SO_LIEU/PHAN_TICH/NEWS;
   - router chưa chắc chắn thì gọi AI fallback; vẫn không chắc thì hỏi lại.
   *Hưng.*
9. Lưu vết mỗi câu hỏi vào các bảng `queries`/`retrieval_results`/`answers`/`citations` đã có, thay cho số liệu SQLite. Bảng này phục vụ 13.2 (đo router) và trang admin traces. *Hưng hoặc Vũ.*

### Giai đoạn 3: Đưa dữ liệu thật lên web, tuần 2

10. API công ty và tài chính (mục 2.2); thay `detailApi.js`, `companies/api.js` bằng lời gọi thật. Hiện cả số đã đối chiếu PDF lẫn số Vietcap, có nhãn trạng thái rõ. *Cần giao (gần 08.2/10.2 của Hưng).*
11. Dashboard thật: giá và xu hướng các mã theo dõi, tin mới, kỳ BCTC mới nhất. *Cần giao.*
12. Watchlist (WBS15) và Profile: dùng bảng `watchlists` và API `/me`; bỏ `researcherMock` khỏi menu. *Vũ.*
13. Trang admin quản lý quyền (WBS14): dùng bảng `permissions`/`role_permissions`. *Vũ.*

### Giai đoạn 4: Chất lượng dữ liệu và đánh giá, tuần 2 đến cuối sprint

14. Tăng độ phủ BCTC: tìm vì sao 120 báo cáo chỉ khớp một phần, rồi sửa bộ đọc OCR; xem 30 báo cáo lệch (CMG 12). Sau đó bật `FINMIND_BCTC_REFRESH`. *Hưng hoặc Codex.*
15. Quyết định nơi lưu dữ liệu admin: giữ SQLite (chỉ chạy một máy) hay chuyển sang các bảng Postgres đã có (`audit_logs`, `evaluation_*`, `system_configs`). Nếu demo chạy nhiều máy thì nên chuyển. *Cả nhóm.*
16. Pipeline đồ thị: chọn một bản giữa `person_role`, `wbs02_person_registry` và `sprint4_runtime`; viết hướng dẫn chạy lại; quyết định số phận `event_news` (WBS16). *Nhân, Vũ.*
17. Hồi quy và demo (13.1–13.4): chạy bộ câu hỏi trên luồng đã gộp; đo tỷ lệ chọn đúng nhánh, thời gian phản hồi, tỷ lệ ý bị lược; viết kịch bản demo. *Cả nhóm.*

## 4. Rủi ro cần theo dõi

- Gemini bản miễn phí hay báo 503 hoặc timeout. Hệ thống đã xoay khóa và gọi lại 1 lần, nhưng demo vẫn có thể gặp "không khả dụng".
- Khi gộp 3 cơ chế định tuyến, câu đang đúng có thể bị đổi nhánh. Cần chạy bộ câu hồi quy trước và sau khi gộp.
- 7/10 mã chưa có chỉ số tài chính đã xác minh, nên câu "phân tích tài chính" phần lớn sẽ trả lời "chưa đủ dữ liệu" nếu chưa xong mục 14.
