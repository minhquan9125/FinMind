# Bàn giao Tasks 2–4: nối dữ liệu doanh nghiệp lên web

Ngày 13/11/2026. Worktree: `D:/Win/Capstone 1/FinMind-codex`. Nhánh `codex/company-data-wiring`, bắt đầu từ `origin/backup-demo` tại `4544ba04`.

Đã nối danh mục doanh nghiệp và BCTC với API có xác thực; hiển thị kỳ thực, đơn vị tỷ VNĐ, trạng thái xác minh và liên kết nguồn. Schema được đồng bộ bằng file SQL, không áp lên VPS. Không push hoặc mở PR; Hưng review và tích hợp.

## Commit và phạm vi

| Task | Commit | Message |
|---|---|---|
| 2 | 7bbb29b9 | chore: sync daily_market_activity/admin_serving_corpus schema and drop tracked tmp and unused admin fixtures |
| 3 | bf1b2d08 | feat(api): companies, financials and health endpoints from verified BCTC data |
| 4 | c1c4fc32 | feat(web): company list and financials from the API |

Task 2:

- `.gitignore`: thêm `**/.agent-state/`, `**/.work/`, `pytest-cache-files-*/`.
- `docker/postgres/init/010_schema.sql`: nối nguyên DDL `daily_market_activity` từ migration hiện có; giữ nguyên phần schema cũ.
- `supabase/migrations/20261114000000_admin_serving_corpus.sql`: sao chép nguyên byte từ `docker/postgres/init/095_admin_serving_corpus.sql`, bao gồm khóa, RLS, GRANT và policy. DDL thực tế nằm trong file `095`, khác vị trí nêu trong plan.
- Xóa 1.605 file đang được theo dõi trong `tmp/` và đúng bảy file admin: `auditMock.js`, `configurationMock.js`, `corpusMock.js`, `evaluationMock.js`, `sourcesMock.js`, `tracesMock.js`, `mock.js`.

Task 3:

- `backend/src/api/routers/companies.py`: bốn GET endpoint `/api/companies`, `/{symbol}`, `/{symbol}/financials`, `/{symbol}/health`; dùng `require_roles(*READ_ROLES)`, SQL có tham số và doanh nghiệp đang hoạt động. Mã không có trong danh mục trả 404 tiếng Việt; mã chưa có BCTC trả danh sách kỳ rỗng/`NO_DATA`; lỗi kết nối trả 503 không lộ thông tin DB.
- `backend/src/financial/health_db.py`: thêm `get_company_financials`; giữ nguyên 9.813 byte của phần đọc/health cũ. Tiền đi bằng chuỗi Decimal VND, nhân đúng `value × scale`, không dùng float. Số thiếu/không hữu hạn và scale không dương trả null. Giới hạn tám kỳ mới nhất; nguồn từ `citation_for` của quan sát VERIFIED đầu tiên còn hợp lệ.
- Ánh xạ `OWNERS_EQUITY` thực tế trong DB thành `TOTAL_EQUITY` tại API. Ngân hàng dùng `TOTAL_OPERATING_INCOME` với nhãn tổng thu nhập hoạt động, không gắn nhầm thành doanh thu thuần.
- Các dòng trùng nhưng khác số, trạng thái hoặc cơ sở báo cáo được bỏ khỏi facts và ghi warning; không cộng/gộp hoặc ghi đè âm thầm.
- `backend/src/main.py`: chỉ hai dòng import/include router sau `admin_ingestion`, không sửa lifespan.
- `backend/tests/test_companies_api.py`: 59 trường hợp, gồm cả năm READ_ROLES, 401/403/404, trường hợp rỗng, số tiền/chứng cứ, kỳ và truy vấn thật trên DB test `15434`.

Task 4:

- `frontend/src/pages/companies/api.js`, `detailApi.js`: gọi API bằng `authorizedFetch`; giữ chức năng fixture rỗng/lỗi/loading cho thử giao diện, mặc định lấy dữ liệu thật. `Number(value_vnd) / 1e9` chỉ dùng để hiển thị. Null không trở thành 0; chỉ nhận link nguồn HTTP(S).
- `frontend/src/pages/companies/CompanyDetailPage.jsx`: kỳ lấy từ dữ liệu; xử lý kỳ yêu cầu không tồn tại; nhãn xác minh riêng cho từng fact; nguồn/trang PDF thật; trạng thái chưa có BCTC. Câu hỏi gợi ý cũng theo kỳ đang chọn, không cố định FY2025.
- Xóa `frontend/src/pages/companies/detailMock.js`; giữ `companies/mock.js` vì dashboard vẫn phụ thuộc.
- `frontend/tests/companyApi.test.js`: 11 trường hợp API/auth/mapping/đơn vị/null/nguồn/lỗi.

## Kiểm chứng

Các lệnh Python dùng interpreter có sẵn tại `D:/Win/Capstone 1/FinMind/backend/.venv/Scripts/python.exe`, chạy từ worktree mới. Runner `.work/run_tests.py` gọi `pytest.main` và chặn kết nối asyncpg ngoài localhost `15434`; không thay assertion hoặc bỏ test để làm xanh. Argv, exit code và SHA log nằm trong `.agent-state/backup-demo-wiring-20261113/`.

| Gate | Lệnh/tham số | Kết quả cuối |
|---|---|---|
| API + health + schema | `.work/run_tests.py backend/tests/test_companies_api.py backend/tests/test_financial_health_db.py backend/tests/test_financial_verification_schema.py -q -p no:cacheprovider --tb=short` | **87 passed, 30 subtests passed** |
| Frontend | Từ `frontend/`, `node --test` với danh sách tường minh 26 file `*.test.js` trong `src/` và `tests/` | **149 passed, 0 failed** |
| Build | Từ `frontend/`, `npm run build` | **PASS**; còn warning GraphCanvas chunk trên 500 kB |
| Backend đầy đủ | `.work/run_tests.py backend/tests backend/src/b1_answering/tests -q -p no:cacheprovider --continue-on-collection-errors --tb=short` | **3303 passed, 32 skipped, 2 xfailed, 757 subtests passed; 5 failed đã biết** |
| Schema thực trên DB test | `.work/check_schema.py` | **PASS**: PK/FK/RLS của hai bảng; migration admin chạy hai lần; hai runtime role chỉ SELECT, không INSERT/UPDATE/DELETE/TRUNCATE |
| Whitespace/phạm vi | `git diff --check` và kiểm danh sách file thay đổi | **PASS** |

Năm lỗi còn lại đều thuộc `backend/tests/test_wbs02_person_identity_integration.py`, do thiếu fixture `person.registry.sqlite`/handoff theo baseline. Không sửa hoặc bỏ những test này. Bộ backend đầy đủ vì vậy vẫn exit 1; không gọi là toàn bộ suite xanh.

Baseline ban đầu: 7 failed, 3242 passed, 32 skipped, 2 xfailed, 757 subtests. Ngoài năm WBS02, thiếu Pillow làm OCR lỗi và một test OS unlock thất bại ở lượt baseline. Đã cài đúng dependency đã khai báo `Pillow>=10,<13` (bản 12.3.0), không nâng các dependency khác. Hai test OCR/OS unlock chạy riêng đều pass và không còn lỗi trong lượt full cuối.

Node 24 không nhận dạng `node --test tests/` như plan giả định (`MODULE_NOT_FOUND`). Lệnh cuối dùng danh sách file tường minh, có cả test admin và các test nằm trong `src`; không loại trừ test nào. Hai warning backend có sẵn về Starlette/httpx và fixture runpy vẫn được ghi trong log.

TDD: 36 test API mới thất bại trên code gốc; test frontend thất bại trên fixtures cũ. Review tìm thêm lỗi scale bằng 0/âm: hai ca mới thất bại, sau đó bổ sung một điều kiện `scale <= 0` và chạy lại các gate trên source cuối. Receipt RED được giữ.

## Kiểm tra trình duyệt và JSON từ API giả lập

Đã chạy Vite ở port riêng `18581`, Chrome context riêng và chặn toàn bộ `/api/` bằng fixture trước khi ứng dụng khởi tạo. Không gọi backend đang phục vụ người dùng hoặc DB production. Đã dừng server thử và đóng tab thử.

DOM xác nhận: kỳ không hợp lệ quay về kỳ mới nhất; đổi kỳ đổi số và câu hỏi nghiên cứu; 80.000 tỷ hiển thị từ chuỗi VND; null khác 0; hai nhãn xác minh; href/trang nguồn; doanh nghiệp chưa có BCTC và mã không tồn tại hiển thị đúng. Không khẳng định đã thử valid deep-link hoặc chuyển ticker trực tiếp trong cùng màn hình. Receipt: `browser-checks.json`.

Response dưới đây lấy từ chính router đăng ký trong app với FakePool/nguồn giả, HTTP 200, đã giới hạn còn một kỳ. **Đây là dữ liệu thử tổng hợp, không phải số tài chính FPT thực.**

```json
{
  "symbol": "FPT",
  "periods": [
    {
      "period": "2026-Q3",
      "facts": [
        {
          "code": "TOTAL_ASSETS",
          "label": "tổng tài sản",
          "value_vnd": "80000000000000",
          "status": "VERIFIED"
        },
        {
          "code": "TOTAL_LIABILITIES",
          "label": "tổng nợ phải trả",
          "value_vnd": "80000000000000",
          "status": "VERIFIED"
        },
        {
          "code": "TOTAL_EQUITY",
          "label": "tổng vốn chủ sở hữu",
          "value_vnd": "80000000000000",
          "status": "VERIFIED"
        },
        {
          "code": "NET_REVENUE",
          "label": "doanh thu thuần",
          "value_vnd": "80000000000000",
          "status": "VERIFIED"
        },
        {
          "code": "PROFIT_AFTER_TAX",
          "label": "lợi nhuận sau thuế",
          "value_vnd": "80000000000000",
          "status": "UNVERIFIED"
        },
        {
          "code": "CASH_FLOW_OPERATING",
          "label": "lưu chuyển tiền thuần từ hoạt động kinh doanh",
          "value_vnd": "80000000000000",
          "status": "VERIFIED"
        }
      ],
      "source": {
        "title": "Synthetic FPT BCTC fixture",
        "url": "https://example.test/fpt.pdf",
        "page": 7
      }
    }
  ]
}
```

## File gốc đã giữ nguyên

Tác giả dưới đây là kết quả `git log -1 --format=%an -- <file>`, chỉ là người commit gần nhất, không khẳng định chủ sở hữu nghiệp vụ.

| File | Tác giả commit gần nhất |
|---|---|
| `chunks_thu.json` | dinhhuynhvu12 |
| `interactive_test.py` | dieuhuyentran |
| `run_event_news.py` | minhquan9125 |
| `wbs16_extractor.py` | minhquan9125 |
| `test_wbs16_extractor.py` | minhquan9125 |
| `stock_news_kg_template.json` | minhquan9125 |

## Giới hạn và khác biệt với plan

- `VERIFIED` theo đúng hợp đồng handoff: `locator_json.unit_status == VERIFIED`. Đây là metadata xác minh đơn vị được reader hiện tại cung cấp; riêng nó không chứng minh mọi số tiền đã được đối chiếu theo từng chỉ tiêu với PDF. Không thay đổi cơ chế xác minh BCTC trong gói nối web này.
- Không sửa `CompanySearchPage.jsx` ngoài allowlist: danh mục đã dùng dữ liệu API nhưng header còn chữ Mock và chưa render badge `has_financials`; adapter đã xuất đúng status/tone.
- Lệnh grep nguyên văn `detailMock` trong toàn `frontend/src` còn một dòng mô tả cũ tại `frontend/src/pages/dashboard/README.md`. File này thuộc vùng Hưng giữ; không sửa để chạy cho xanh. Không còn import/tham chiếu runtime JS/JSX tới file bị xóa.
- Không áp migration lên VPS, không kiểm thử dữ liệu production, không restart backend, không bật tự cập nhật BCTC. Hưng còn Tasks 1, 5, 6, 7 và kiểm tra tích hợp sau merge.
- Screenshot không được lưu vì tool Chrome giới hạn thư mục output ở workspace gốc; bằng chứng kiểm giao diện là DOM assertions, không khai báo có ảnh.
- ECC canonical queue không gọi inference vì các model slot đang quarantined. Không giải phóng slot hoặc đổi cấu hình/budget. Có ghi ngoại lệ coordinator/native worker; QA và review dùng agent riêng cùng receipts thực. Không khẳng định đã qua gate độc lập model của ECC canonical.

Review/QA cuối: xem `qa-review.md`, `code-review.md`; source/evidence hashes ở `final-hashes.json` trong state. Ba thư mục report phát sinh từ test full đã được chuyển vào state bị gitignore; không commit output thử.
