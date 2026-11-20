# Market ratios không tạo phiên bản BCTC — 13/11/2026

Đã sửa một lần tại verification_store.values_differ, dùng chung cho append_reports và plan_reports. Chỉ thay đổi tám chỉ số thị trường dưới đây không tạo phiên bản. Mọi chỉ tiêu kế toán khác vẫn được so như trước; EPS 5571 → 3727 vẫn tạo phiên bản. Không cập nhật hoặc xóa dữ liệu đã lưu.

| Code | Field Vietcap | Mapping BANK / TECH |
|---|---|---|
| NUMBER_OF_SHARES_MKT_CAP | numberOfSharesMktCap | backend/src/financial/mapping.py:219 / :434 |
| MARKET_CAP | marketCap | backend/src/financial/mapping.py:220 / :435 |
| DIVIDEND_YIELD | dividendYield | backend/src/financial/mapping.py:221 / :436 |
| PE | pe | backend/src/financial/mapping.py:222 / :437 |
| PB | pb | backend/src/financial/mapping.py:223 / :438 |
| PS | ps | backend/src/financial/mapping.py:224 / :439 |
| PRICE_TO_CASH_FLOW | priceToCashFlow | backend/src/financial/mapping.py:225 / :440 |
| EV_TO_EBITDA | evToEbitda | backend/src/financial/mapping.py:226 / :441 |

Nguồn đối chiếu: block định giá/thị trường trong mapping và raw response FPT/MBB/VCB; paths trong .agent-state/market-ratio-versions-20261113/market-ratio-evidence.md. Test DB chỉ có ROE; phép SELECT catalog production được user cho phép và ép read-only từ lúc kết nối đã xác nhận đủ tám code RATIO trong 69 dòng distinct. EPS cơ bản/suy giảm thuộc INCOME_STATEMENT. Không đoán alias BVPS và không bỏ code nào khác. Mẫu raw xác nhận tên field, không chứng minh trực tiếp biến động giá hàng ngày.

Ba file thay đổi:

- backend/src/financial/verification_store.py: frozen set tám code và một điều kiện trong phép so sánh dùng chung.
- backend/tests/test_financial_verification_store.py: sáu test mới cho apply/comparison, gồm EPS và kế toán.
- backend/tests/test_financial_statements_refresh.py: ba test mới cho dry-run planner.

Diff đầy đủ: .agent-state/market-ratio-versions-20261113/change.diff. Test cũ và kiểu xuống dòng giữ nguyên. Không sửa refresh script, file Chat/xu hướng/health passage Hưng đang sửa, schema hay cấu hình.

Kiểm chứng:

- TDD RED: 15 lỗi kỳ vọng, 50 pass, 280 subtest pass.
- Candidate và source chính: 216 passed, 432 subtests passed, đủ 11 file test_financial_*.py.
- PE/PB-only không tạo version ở hai caller; PE + doanh thu hoặc ROE vẫn tạo đúng version; EPS 5571 → 3727 tạo version. Khi kế toán đổi, phiên bản mới vẫn lưu market ratio mới đi kèm.
- Cả 272 code mapped khác vẫn kích hoạt so sánh. Điều kiện shared-key/None và xử lý sai số cũ không đổi.
- QA/review độc lập APPROVE; receipts/hash ở qa-review.md, code-review.md, all.json, integration.json trong thư mục state.
- Test chỉ DB 15434, không provider. Fixed argv đủ trong integration.json. Warnings-as-errors trừ đúng hai warning cũ: Starlette/httpx2 và runpy fixture đã import module. Không đổi dependency hoặc assertion để làm xanh.

Dry run nguồn thật:

- Entry point backend/scripts/refresh_financial_statements.py --symbols FPT,MBB, không --apply; harness ép mọi kết nối DB read-only từ startup và kiểm SHOW transaction_read_only=on.
- FPT: new_reports=0, new_versions=0; MBB: new_reports=0, new_versions=0; exit0.
- Các nhóm bảng đối chiếu trước/sau không đổi:

| Nhóm theo dõi | Trước | Sau |
|---|---:|---:|
| financial_reports | 340 | 340 |
| observations | 63436 | 63436 |
| financial_report_verifications | 36 | 36 |
| documents | 899 | 899 |
| financial_raw_payloads | 57 | 57 |
| financial_ingestion_jobs | 60 | 60 |

Bốn nhóm đầu lọc FPT/MBB; raw payload/job lọc nguồn VIETCAP_VCI và Vietstock BCTC. Audit CLI có một kết nối read-only. Report nguồn: outputs/financial-refresh/20261113-152918-475941/report.json. Receipt/log che thông tin kết nối: .agent-state/market-ratio-versions-20261113/live-dry-run.json và .log.

Giới hạn: dry run vẫn nhận lại 8 kết luận MISMATCH (FPT6/MBB2), verifications_added=0. Đây là vấn đề xác minh số liệu đã có, không phải version mới do ratio; không sửa trong gói này và không ghi DB. Không dọn các phiên bản cũ đã tạo trước đó.

Không bật/thay đổi FINMIND_BCTC_REFRESH; parent flag không bật. Không --apply, restart backend, commit/push/đổi nhánh. Hưng review trước bước vận hành tiếp theo.

Canonical manager dừng trước inference vì packet vượt giới hạn; native exception bốn lượt trong allowance12calls/7200s, usageunknown. Không claim canonical distinct-model ECCPASS. Candidate fixwave cũ lỗi thời không tích hợp; source fixwave/Task10 hiện tại giữ nguyên.
