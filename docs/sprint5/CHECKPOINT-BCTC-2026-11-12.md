# Checkpoint BCTC — Codex làm song song Claude giá

**Bổ sung10:08:** phần kiểm tra/bổ sung collector đang dở đã bàn giao riêng ở `CHECKPOINT-BCTC-CAPTURE-2026-11-12.md`. Candidate3file chưa tích hợp,33test chưa chạy đủ, chưa cào thật10mã/chưa ghiDB. Mốc completed bên dưới chỉ thuộc bộ tính BCTC7file của milestone trước.

**Trạng thái cuối12/11/2026: đã tích hợp7file BCTC sau review APPROVE và kiểmhash.102test tài chính/65subtests PASS, gồm52test mới; Q2/defaultlatest report thật10mã chạyPASS.** Không ghi VPS/đổi source approval hoặc sửa file giá/Chat/API/frontend. Đây là bản đầu của bộ tính và kiểm dữ liệu; **chưa nghiệm thu kết luận doanh nghiệp mạnh/yếu từ dữ liệu thật thiếu metadata**.

Broader FinancialCleaner có16test,15PASS;1test fingerprint cũ thất bại ở10subcase vì hash normalized hiện tại khác manifest lịch sử. Đã tái hiện độc lập không import financial-health; hash10source trước/sau test không đổi. Không sửa manifest/source chỉ để làm xanh. `integrated-verification.json` giữ success=false của broader suite; **`financial-feature-verification.json` ghi riêng feature_checks_passed=true và legacy_cleaner_suite_passed=false**, không tuyên bố toàn bộ regression xanh.

## Phạm vi

User muốn dùng BCTC để xem doanh nghiệp phát triển và đối chiếu mã cùng ngành. Tách ba lớp: tín hiệu tài chính từng mã; so từng chỉ tiêu với median peer; adapter snapshot/report. Không huấn luyện ML, gán điểm tổng hợp tùy ý hoặc gọi một mã mạnh hơn toàn ngành chỉ từ một chỉ tiêu. Bank/Tech riêng, không lấy khối ngoại làm dòng tiền BCTC.

Các file mới sau khi tích hợp: `backend/src/financial/health.py`, `peers.py`, `health_store.py`; `backend/scripts/report_financial_health.py`; `backend/tests/test_financial_{health,peers,health_store}.py`. Mapping/exact_json/importer/database/schema và toàn bộ phần giá của Claude không bị sửa. API/cách chạy trong `financial-health/README.md`, contract và datareadiness cùng thư mục.

## Dữ liệu thật

Audit đọc đúngFinMindVPS127.0.0.1:15433/finmind trong READONLY/REPEATABLEREAD, xác thực target trước kết nối.1638reports/308546observations,10mã cóBCTC;24company thêm cho rổ giá chưa cófinancialreports.1752fact từ2024 được export riêng. Hầu hết gần nhất2026Q2;TCBQ3. Snapshot/receipt ở `outputs/sprint5/financial-health-20261112/{audit.json,observations.json}`; không đọc/in credentials. Một lần audit lại sandbox timeout, retry elevated thành công; không có ghiDB.

Nguồn VIETCAP_VCI PENDING/disabled giữ nguyên. `financial_reports.statement_scope` legacy chứa section, không chứng minh consolidated; tiền gánVND chưa có unit_statusverified, ratioSOURCE_NATIVE chưa có định nghĩa/scale; thiếu periodbasis/fiscalwindow/perimeter. Do đó currentrealdata chưa thể dùng để kết luận mạnh/yếu; bộ tính trả `insufficient_data`, không giả0. FPT2026 đổi hợp nhấtFPTTelecom, số2025 so sánh phải restated; CMC/ITD có năm tài chính lệch calendar. Primarylinks/issuerreportedexample trong DATA-READINESS.md; không dùng số % báo chí để suy ngược prior chính xác.

## Kiểm thử/review

QA độc lập52tests; RED trước module, RED regression18fail/1error cho review findings, GREEN sau sửa. Các gate gồm exactDecimal/provenance/positivebase/quý-vsYTD/fiscalSTART_YEAR-END_YEAR/ratio_definition/profileBANK-TECH/minimum3peers/direction/median/partialcoverage/legacyYYYY-YEAR/defaultCLI. Dataset1752rawfacts exactnumeric roundtrip và inputSHA giữ nguyên; actualQ2/defaultlatest10companies báo thiếu trung thực. Raw evidence có raw_value, không làm mất số dài vì contextDecimal50 khi scale.

Native reviewer độc lập chạy45test bản đầu rồi52test correctedPASS, kiểm7candidatehash +3loghash và APPROVE đúngreceiptSHA. BốnImportant đã sửa, thêmfixannualperiod/defaultreport. `.agent-state/financial-health/code-review.md` giữ finding/history/approvedSHA. Integrationmanifest `.agent-state/financial-health/integration.json`: root_verification_pending=false, root_feature_checks_passed=true, legacy_cleaner_suite_passed=false. Không copy lại candidate đèroot.

Báo cáo đã xuất: `outputs/sprint5/financial-health-20261112/report-q2/report.{json,md}` (cùng kỳ2026Q2), `report-latest/report.{json,md}` (TCBQ3/othersQ2, không ép peer). Source snapshotSHA không đổi; raw evidence exactnumeric roundtripPASS. `src.financial.*` import trong backend và compile7file PASS; không chạy UI/Chat, markettest hoặc restart khi các file đó không thuộc thay đổi này. Root102test có50regression sẵn của importer/chunk cùng52test mới. Bộcleaner16test chạy riêng cwd chuẩn tránh namespacecollision khipytestgom2package tests; broadfailure còn lại là fingerprint nêu trên, không lỗi import.

## Workflow và tiếp tục

Canonical s5-financial-health-20261112 queued(allselectedroutesquarantined),0APIcalls. Sharedbudget24calls/7200s, sameownerturn01a1cd52-d6ce-7383-ac03-d8d416c72b5f, không reset old workflows/leases. Recorded coordinator exception +2nativehelperstarts/5turns(QA3,review2); usageunknown, không distinctmodelECCPASS. Internalnativeallocation6max nằmtrong24sharedbound. Rulings/progress .agent-state/financial-health/. Không cần chạy lại sourcecào/rolloutgiá của ngày11Nov.

Sau integration/checks: Claude có thể gọi API thuần từ Chat ở phase riêng, phải hiện status/reasons/evidence, không diễn giải insufficient_data thành kinh doanh suy giảm. Muốn kết luận thật cần đối soát/fillmetadata BCTC theo từngmã/kỳ, dùng restatedcomparatives và nhóm ngành/kỳ hợp lệ. Không tự phê duyệt nguồn hoặc épunit unknown thànhVND/percent. Giữ nguồn snapshot để xem lại audit; không chạy apply/import từ checkpoint lịch sử.
