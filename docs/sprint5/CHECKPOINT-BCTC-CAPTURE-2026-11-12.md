# Checkpoint BCTC capture — 12/11/2026, 10:08 GMT+7

## Mốc 17:10 — Claude: hệ thống tự lấy metadata BCTC được, không cần file có sẵn trên máy

User yêu cầu: chỉ dùng dữ liệu trong DB, và hệ thống phải tự kiếm metadata thay vì dựa vào PDF có sẵn trên máy. Đã kiểm, chưa sửa code, chưa ghi DB.

**1. Tự suy từ chính số Vietcap (offline, raw đã lưu):**
- Raw có `yearReport`, `lengthReport` (5 = năm, 1–4 = quý), `publicDate`, `updateDate`. Giá trị là VND tuyệt đối; EPS (`isa23`) là VND/cổ phiếu.
- Tổng 4 quý so với số năm: FPT 2018–2025 lệch ≤0,3%, BID 2018–2025 lệch ≤2,8% ở chỉ tiêu chính (`isa16`, `isa17`). Vậy **số quý là quý riêng, không phải lũy kế**. Chênh nhỏ là điều chỉnh sau kiểm toán. Riêng BID `isa18` lệch lớn (−48% đến +14%). Theo mapping, `isa18` là thuế TNDN hoãn lại: khoản nhỏ, điều chỉnh khi kiểm toán, nên không dùng để kiểm tổng quý.
- Hiện thu BCTC chưa có lịch tự chạy: `backend/src/market_data/app.py` chỉ lên lịch cho giá.
- Kiểm này chạy được tự động trên DB cho mọi mã và năm có đủ 4 quý.

**2. Vietstock catalog có sẵn BCTC quý và năm (đã probe, chỉ danh mục, không tải file):**
- `/data/getrptdoctype`: type 1 "Báo cáo tài chính" (cùng client với `data_pipeline/annual_reports/vietstock_download_annual.py`; hiện client chỉ lọc type 2 "thường niên").
- `/data/getrptterm` cho type 1 có các kỳ: Năm=1, Q1=2, Q2=3, Q3=4, Q4=5, 6T=9, 9T=12.
- `/data/getrptfile` với FPT 2025 trả, mỗi kỳ, 2 file: "BCTC Hợp nhất …" và "BCTC Công ty mẹ …". Tên ghi "Kiểm toán" (năm) hoặc "Soát xét" (6 tháng). Kèm `Url` (static2.vietstock.vn) và `LastUpdate`.
- Tức là **phạm vi (hợp nhất/riêng) và trạng thái kiểm toán/soát xét lấy từ metadata danh mục**, không cần đọc PDF. Muốn lấy đơn vị tính và ngày kết thúc năm tài chính thì cần tải PDF, đọc vài trang đầu; PDF scan dùng OCR sẵn có.

**Giới hạn và rủi ro:**
- Endpoint Vietstock là giao diện website quan sát được, không phải API tài liệu công khai.
- Source VIETCAP_VCI vẫn PENDING/disabled. Bật nguồn mới cần team duyệt.

**Đề xuất (chưa làm, cần user duyệt):** tham số hóa document type trong client Vietstock; lưu danh mục BCTC vào DB (append, version theo `LastUpdate`); job tự kiểm tổng quý = năm và EPS; ghi metadata đã xác minh kèm bằng chứng vào DB. Lịch chạy: hằng ngày trong mùa nộp BCTC, hằng tuần ngoài mùa.

## Mốc 14:38 — Claude bắt đầu việc B: đối soát với BCTC gốc, bổ sung metadata có bằng chứng, rồi thiết kế ghi DB giữ lịch sử

User chọn việc B (không làm 20 mã còn lại của rổ VN30 trong lượt này). Chưa sửa code, chưa ghi DB, chưa gọi nguồn ngoài. Chỉ đọc DB (READ ONLY).

**Điểm nghẽn:** `analysis-latest/report.md` trả `insufficient_data` cho mọi chỉ tiêu của 10 mã. Lý do: API Vietcap không kèm 5 loại metadata, gồm
- đơn vị tiền,
- phạm vi hợp nhất/riêng,
- kỳ thực (quý riêng hay lũy kế; năm tài chính lệch, ví dụ CMG 01/04–31/03),
- cơ sở so sánh (số restated, ví dụ FPT 2026),
- định nghĩa/đơn vị tỷ số.

**Nguồn đối chiếu đã tìm thấy (đọc DB chỉ đọc lúc 14:30):**
- `documents.doc_type='FINANCIAL_STATEMENT'` (khoảng 372 tài liệu/mã) có `file_type=DB`, không có PDF. Tài liệu này sinh từ chính dữ liệu API, **không dùng làm bằng chứng độc lập**.
- `documents.doc_type='ANNUAL_REPORT'` là **BCTN gốc 2024 và 2025** (PDF vietstock, có `pdf_sha256`, khoảng 215–233 trang/bản với FPT). PDF có sẵn trên máy cho đủ 10 mã × 2 năm ở `data/references/vietstock/annual_reports/files_pdf/<MÃ>/<NĂM>/`.
- Bảng `text_chunks` trên VPS **không có cột chữ**. Chỉ có `locator_json` (pdf_page, row_keys, pdf_sha256), nên nội dung phải đọc lại từ PDF.

**Bước tiếp theo đã định:**
1. Mỗi mã, mỗi năm (2024, 2025): đọc trang BCTC trong BCTN để lấy, kèm số trang làm bằng chứng:
   - đơn vị ("Đơn vị tính: triệu VND/VND"),
   - phạm vi ("hợp nhất"/"riêng"),
   - ngày kết thúc năm tài chính,
   - đơn vị kiểm toán.
2. So 3–5 chỉ tiêu chính của báo cáo năm (doanh thu, LNST, tổng tài sản, vốn chủ) giữa số API trong `captures/revalidated-97qr6a38/observations.json` và số trong PDF. Khớp thì gắn metadata năm đó là "đã xác minh, có trang nguồn"; lệch thì ghi lệch, không sửa số.
3. Giới hạn: BCTN chỉ chứng minh được **kỳ năm**. Kỳ quý chưa có nguồn gốc trên máy; cần BCTC quý từ HOSE/IR, hỏi user trước khi tải.
4. Sau đó mới thiết kế ghi DB: append và versioning, giữ nguyên số lịch sử; cần user duyệt thiết kế trước khi viết code.

Ranh giới giữ nguyên như các mục dưới: không ghi DB/schema/source approval, không chạy old importer `--apply`, không commit/push. Phần giá (Claude) đang chạy song song, refresh 15:35 hôm nay; checkpoint giá ở `CHECKPOINT-CLAUDE-2026-11-11.md`.

## Mốc cuối13:51 — code và dữ liệu local đã hoàn tất

**Đã tích hợp3file +follow-up2file có review, root144test/106subtests PASS, script/modulehelp PASS. Đã có snapshot10/10mã,3947input phân tích được mapping, mọi nhóm tới nhãn2026-Q3 của nguồn. Chưa ghiDB, chưa xácminh đủ metadata để kếtluận mạnh/yếu.** Mục này thay thế các trạng thái pending/chưa tíchhợp bên dưới; giữlịch sử để truyvết.

- Source thật:40HTTPrequest trongbatch `captures/20261112T063634Z-l8uk8akb/`. Raw đầu cả40HTTP200, parser ban đầu9complete/ICTfailed. Giữ nguyên manifestpartial và `real-capture-receipt.json` successfalse, khôngsửa thànhthànhcông.
- NguyênnhânICT là **Vietcap organCode=CTIN, ticker=ICT**; rawcũ `data/raw/ICT_raw.json` cũngcùngđịnhdanh. Đã thêm aliascompany-specificICT→CTIN, ticker nếu có vẫn phảiICT; ratio khôngcóticker vẫn kiểm internalID đãxácminh. Không cho organCode bấtkỳ. TestmớiREDSourcecompanymismatch→GREEN34; old/newidentity/rawsource_fields giữnguyên.
- Sau reviewfollowup pinreceiptSHA `d533e4e6e99e2bb2b8557b961a68ad9342c860d60433f8da68f45401a656c665`, hashguard tíchhợp2filecode/test; wrapperkhông đổi. Manifest `.agent-state/bctc-capture/integration.json` cófollowups, root_verification_pending=false/root_checks_passed=true. Beforeimage/receiptbanđầu còn `.agent-state/bctc-capture/integration-before-ict.json`.
- **Tái kiểmngoạituyến40raw gốc, không thêmHTTP**, thành `outputs/sprint5/bctc-enrichment-20261112/captures/revalidated-97qr6a38/`. `manifest.json` modeoffline_revalidation/statuscomplete/10company; `observations.json`3947records;10normalizedfiles cófullsourcefields. Mọi hashraw và giátrị chínhxácđối chiếuđạt;23file nguồn/protected source giữnguyên; manifestpartialgốc giữnguyên.
- **Receipt dữliệu cuối:** `outputs/sprint5/bctc-enrichment-20261112/revalidated-capture-receipt.json` successtrue/10companies/2026Q3/rawhash/valueroundtrip/originalunchanged/database_writtenfalse. Báocáo `captures/revalidated-97qr6a38/analysis-latest/report.{md,json}` đủ10mã, hiệninsufficient_data trungthực vìAPIkhôngcungcấpunit/scope/fiscal/basis/ratio_definitionđãxácminh. Completeởđây làcapture/revalidation, khôngphảiBCTCđãapprovedhoặckếtluậnkinhdoanh.
- **Receipt test cuối:** `integrated-verification.json`, `root-tests.log`:144passed/106subtestspassed,1runpywarningtestentrypoint. Root2import/helpchecksPASS. `candidate-verification.json`34test+probe-replay+packagehelpPASS. `code-review.md`nativeAPPROVEhashpins; khôngclaimcanonicalECCPASS.

Userđãyêucầu checkpoint từngmốc: mốc33/root143 đãlưu trước khi chạy nguồn, sauđó phát hiện/sửa ICTvàmốc34/root144+10mãlocalnày. Khôngphát sinhDB/schema/sourceapproval/SDK/key/account/price/Chat/UIwrites, khôngrestart/commit/push.

**Làmtiếp:** dùnglocalobservations đểkiểm/đốisoátBCTC gốc, bổsungmetadata cóbằngchứng; rồithiếtkếappend/versioningDB giữnguyênlịchsử. Không chạy oldimporter mutableupsert `--apply` hoặcđánh dấuunit/scopeverifiedđểlàmchochỉtiêu tínhđược. ĐọcREADMEcapture đểchạybatchmới; khôngrerun integration.py hoặcoldonboardingbatch. Cácbudgetcanonical/supplemental đãhết theođồnghồ; khôngdispatchthêmworker từallowancecũ. ReviewICTđượcnhậntronglượtcuốiđãadmit trướcdeadline, receiptđếnsaumốc13:43; timingoverrun đượcgiữtrongreview/rulings, khônggiảbudgetPASS/resetdeadline.

## Mốc mới nhất — CODE ĐÃ TÍCH HỢP VÀ ROOT CHECKS PASS

Đã sửa2điểm còn lại,33testsGREEN, native review APPROVE đúng3candidateSHA/receiptSHA `65642ff4966d8d5d0d31be12f295316df9073139fa75bb02c0a2913f70b2c52b`. Đã tích hợp3file allowlist vào source chính; manifest `.agent-state/bctc-capture/integration.json` root_verification_pending=false/root_checks_passed=true. Root financial+capture+JSONingest tests và cả script/modulehelp PASS (`integrated-verification.json`, root-tests.log). Không copy2dependencyreadonly/không sửa giá/DB/sourceapproval. Review supplemental1turn đã xong, chưa claimcanonicalECCPASS.

**Tại mốc code này chưa chạy batch thật10mã/chưa ghiDB.** Các ghi chú13:29 và10:08 bên dưới là lịch sử, không còn trạng thái rootchưa tíchhợp. Bước tiếp theo riêng: chạy capturefinancialonly10mã vào output mới, kiểmmanifest/rawhash/latestperiod/nguồn cũ bấtbiến, rồi checkpoint dữ liệu. Không chạy lại integration.py trên root đã tích hợp vì guard cố ý từchối baseline khác.

## Cập nhật13:29 — resumed theo user, candidate33PASS

User yêu cầu làm tiếp vàcheckpoint từngmốc. Đã sửa MAPPED-only analysisfilter, bổsung missingperiod_start/end/fiscal_label_convention/currency/audit_status. Quan sát33testsRED1failure trướcfix (`review-fix-red.log/json`), saufix33PASS+offline5payloadreplay+realpackagehelpPASS. Receipt `candidate-verification.json` đã pin3candidateSHA/logSHA hiện tại. Đang reviewcuối theo supplement<=2reviewturn/900s13:28; oldcanonical24call7200s expired khôngreset/drive. Chưa tích hợp root/chưa chạy10symbolbatch tại mốc13:29. Các notes10:08bên dưới giữlịch sử, khôngdùng làm trạngtháimớinhất.

**User yêu cầu checkpoint để tiếp tục ở phiên/agent khác. Đã dừng tại trạng thái đang dở: capture chưa tích hợp vào source chính, chưa chạy batch thật10mã, chưa ghi PostgreSQL.** Bộ tính BCTC7file của milestone trước vẫn đã tích hợp; xem `CHECKPOINT-BCTC-2026-11-12.md` cho102test tài chính PASS và giới hạn dữ liệu.

## Yêu cầu đang làm

User giao kiểm tra cơ chế cào BCTC và bổ sung phần lấy được; sau đó nhắn “tiếp tuc”, rồi yêu cầu checkpoint. Claude đang làm giá/Chat; không sửa các file đó. Mục tiêu mới: BCTC riêng khỏi giá, giữ exactnumbers/raw/provenance, lấy các kỳ API đã có, không đoán unit/phạm vi hợp nhất/lũy kế khi nguồn không nói rõ.

## Kết quả kiểm tra thực tế

- Collector cũ: `data_pipeline/financial_data/collect_financial_data.py`. Một mã chỉ publish khi giáENTRADE và cả4nhóm tài chính thành công; BCTC bị phụ thuộc nguồn giá. Dùng `resp.json()` có float; thiếu responsebytehash/requestreceipt. Source rows/pubDate/updateDate/ratioType có nhưng metadata đơn vị/phạm vi/kỳ chưa được xác minh hoặc đi xuyên tới phân tích đầy đủ.
- **5 request thật qua endpoint đang dùng đều HTTP200**: FPT INCOME_STATEMENT/BALANCE_SHEET/CASH_FLOW/RATIO, BID INCOME_STATEMENT. Lượt sandbox ban đầu ProxyError; chạy lại đúngscript elevated thành công, không đổi account/key/SDK hoặc né401/403/429. Sourceclient UserAgentFinMind, Origin/Referer đúng cấu hình pipeline.
- FPT cả4nhóm tới **2026-Q3**:43rows mỗi statement,40ratio. BIDincome43rows. DB milestone trước đa số mớiQ2,TCBQ3. Endpoint trả statement `{years,quarters}`, ratio list; không có bằng chứng đầy đủ unit/consolidation/fiscal/perimeter. Không lấy năm/quý làm bằng chứng số quý riêng hay lũy kế.
- Bằng chứng `outputs/sprint5/bctc-enrichment-20261112/probe.json`,5file raw JSON FPT/BID và `probe-replay.json`. Đây là probe/capture cục bộ, **không phải batch10mã hoặc DB đã cập nhật**.

## Code candidate đang có

Staging: `.agent-state/bctc-capture/native-candidate/`. Chỉ3file được sửa/tích hợp:

1. `data_pipeline/financial_data/financial_capture.py` mới: `decode_section`, `financial_records`, `capture_financial`.
2. `data_pipeline/financial_data/run_financial_pipeline.py`: thêm `--financial-only`, `--output-root`; default cũ giữ nguyên; thêm ROOT/FINANCIAL_DIR importpath để chạy script/module.
3. `backend/tests/test_financial_capture.py`: **33test độc lập đã staged**, syntaxPASS theoQA. Bản30test trước đã chạyPASS;33test chưa chạy sau khi thêm regressions.

Hai dependency **chỉ copy để thử package import** trong candidate: `collect_financial_data.py`, `normalize_financial_data.py`. Không sửa và không copy chúng đè root. Source chính của3file CAPTURE vẫn khớp baseline, xác nhận `checkpoint-inventory.json/root_capture_paths_unchanged=true`; financial_capture.py/test mới chưa tồn tại ởroot.

Thiết kế/code đã có: requests4nhóm tuần tự, min2smonotonic mọi attempt, tối đa2network/5xxattempts;401/403/429 dừng toànbatch,5xxRetryAfter cũngdừng thay vì thử sớm; no redirects. Mỗi response giữ bytes/hash trướcdecode; exact_json Decimal/duplicatekeys/nonfinite validation; strictticker/year/quarter/groups; annualquarter5 giữtrongsource_fields dù normalizedquarterNone. IDs local contenthash gồmrawSHA/URL/symbol/section/period/field/code/mappingSHA, không giả DBUUID. UnitSOURCE_NATIVE/scopeUNKNOWN/PENDING, không tự phêduyệt. Mỗi run tạo folderexclusive mới, nguyên dữ liệu cũ; một company chỉ complete sau4section+mapping+ghi normalized.

`financial_records` giữmọi numericfield (kể cảUNMAPPED). Để tránh lặp~60MBprovenance/FPT(~600MB/10mã), captureobservations.json chỉ nhắm inputfinancial-health; mọi field vẫn đủ ở raw/fullnormalized/source_fields. Manifest records_scope và source_metric_count/observations phân biệt phạm vi. **Lọc hiện còn thiếu điều kiện MAPPED — xem lỗi cần sửa dưới đây.**

## Bằng chứng kiểm thử và trạng thái gate

- RED đầu do chưa có capturemodule: `.agent-state/bctc-capture/red.log`, `red-receipt.json`.
- Bản30test PASS đã chạy elevated (tempfileWindows sandbox gâystall; reviewer chỉ ngắt ownprocess rồi elevatedPASS). Native reviewer cũng independently chạy30PASS và kiểm loghash.
- Receipt gần nhất `outputs/sprint5/bctc-enrichment-20261112/candidate-verification.json`: unit30PASS, offlineprobe-replayPASS, **package-help thật khôngmock PASS**. Package form root cũ đã RED ModuleNotFound; wrappercandidate thêm FINANCIAL_DIR và2dependencyreadonlycopies để thử đúnglayout.
- **Receipt này hiện stale:** QA sau đó thêm3tests thành33. Inventory10:08: `receipt_matches_current_candidate=false`, `candidate_test_count=33`. Không dùng receipt cũ để tích hợp/claim33PASS.
- Review `.agent-state/bctc-capture/code-review.md` đã **đóng băng, chưa phê duyệt** theo yêu cầu checkpoint. `design-review.md` ghi3điều kiện integrity đã triển khai; remaining fixes dưới đây.

## Làm tiếp đúng chỗ

1. Chạy33test để quan sát RED mới, lưuactualargv/exit/loghash. Tối thiểu regression UNMAPPEDanalysisfilter phải fail;503RetryAfter/OSError gate dự kiến đã được code hiện tại xử lý nhưng cần thực thi.
2. Trong `capture_financial`, `selected` hiện chỉ `row['code'] in ANALYSIS_CODES`. **Thêm `row['mapping_status']=='MAPPED'`**. Trường raw lạ `ROE` fallbackuppercaseROE không được thành inputknownmetric nếu không có mappingthật. Vẫn giữ nó trong `financial_records`, raw vàfullnormalized.
3. Bổ sung `period_start`, `period_end`, `fiscal_label_convention` vào UNKNOWN_FIELDS/missing_financial_metadata; có thể thêm currency/audit_status để danh sách thiếu đầy đủ. Các giá trị vẫn unknown, không gán metadata giả.
4. Rerun `verify_candidate.py` elevated, phải33PASS +actual5payloadreplay +package-help. Script pin3candidateSHA/logSHA; code/test không được thay saureceipt.
5. Native reviewer reviewfixes và receiptmới, **APPROVE đúnghash** rồi mới tích hợp đúng3file với currentrootSHA so `source-baseline.json`. Chưa có integrationreceipt cho CAPTURE; không copy toàncandidate.
6. Rootregression: new33capturetests +financial102/importJSONtests; script/module--help thật. Không gọi broadcleanerhistoricalhashgate để rồi sửahashfixture: lỗi1test/10subcase đã biết từmilestone trước, sources cũ có thể khác manifestlịch sử; giữnguyên.
7. Chỉ saugates trên mới chạy nguồn thật: rootCLI `--financial-only --symbols VCB,BID,CTG,MBB,TCB,FPT,CMG,ELC,ITD,ICT --output-root outputs/sprint5/bctc-enrichment-20261112/captures`.40requestbaseline/min2s, tựstop401403429; lưu hash cácsource/data cũ trước/sau để chứng minh không ghi đè. Batchthật này **chưa chạy**.
8. Kiểmmanifest, count/latestperiod mỗi4section, sourcebytehash/Decimal/metadata; chạy `backend/scripts/report_financial_health.py` với observations snapshot mới. Mô tả rõ snapshotlocal vsDBpersisted, missingmetadata không thành0/validated. Cập nhật checkpoint/context từ receipts thật.

Fixedcandidate runner từ gốcrepo:

```powershell
backend/.venv/Scripts/python.exe -X utf8 -B outputs/sprint5/bctc-enrichment-20261112/verify_candidate.py
```

Runner tự đặt cwdcandidate. Windows tempfile cần escalation; không coi sandboxcleanupstall là productfail. Read `CAPTURE-CONTRACT.md` và `docs/superpowers/plans/2026-11-12-bctc-capture.md` trước khi sửa; không đọc/in.env/credentials.

## Ranh giới và workflow

DB thật FinMindVPS127.0.0.1:15433/finmind, không Supabase/LAN5432. Không ghiDB/schema/sourceapproval/SDK/key/account, không restartapp/tunnel/frontend, khôngcommit/push. Oldimporter mutableupserts không được chạy `--apply` với capture mới; lưuDB/versioning/enrichment cần gate riêng, không ghi đè số lịch sử haytrộn restatedbasisFPT2026. Giá/Chat doClaude sửa đồngthời; không reset cácfiledirty/untracked.

Canonicalworkflow mới `s5-bctc-capture-20261112`, session01a1c543-94f8-7c73-9b56-15473db10e76, ownerturn01a1cd7b-6337-7d63-b44e-137047c77859 từtrustedruntime. Sharedbudget24calls/7200s, max2repairrounds; initialized khoảng09:26, không resetdeadline/budget khihandoff. Drivequeued vìquarantinedroutes,0APIinference. Recordedcoordinator exception:2reusednativehelpers/4turns(QA2,review2), nativeusageunknown, allocationmax6within24sharedbound. KhôngclaimcanonicalECCPASS/distinctmodelreview. Khôngclearleases/resumeoldpausedbenchmark. QAđãxong;reviewđãfreeze; không cólivecapture/workerđangchạy cần chờ.

- 12/11 Claude: Task 1/10 kế hoạch BCTC metadata xong — migration `supabase/migrations/20261112000000_financial_report_verifications.sql` (append-only trigger), test 15434 PASS, review Approved. Chưa áp VPS.
- 12/11 Claude: Task 2/10 xong — `data_pipeline/financial_data/vietstock_statements.py` (danh mục BCTC Vietstock, nhịp ≥1s, khớp đúng loại "Báo cáo tài chính"), 14 test PASS, review Approved sau 1 vòng sửa.
- 12/11 Claude: Task 3/10 xong — `backend/src/financial/statement_pdf.py` (tìm số VND/triệu, đơn vị, năm tài chính chỉ theo câu "năm tài chính kết thúc", cột so sánh cùng dòng), 18 test PASS, review Approved sau 1 vòng sửa.
- 12/11 Claude: Task 4/10 xong — `backend/src/financial/verification.py` (kết luận VERIFIED/PARTIAL/MISMATCH; không đọc được năm tài chính thì PARTIAL; số mã dòng không tính là lệch), 39 test PASS, review Approved sau 1 vòng sửa.
- 12/11 Claude: Task 5/10 xong — `backend/src/financial/verification_store.py` (ghi DB chỉ thêm: nguồn, job, payload, PDF, phiên bản số liệu, xác minh, cách ly; khóa advisory chống trùng khi chạy song song), 14 test PASS trên DB test, review Approved sau 1 vòng sửa.
- 12/11 Claude: Task 6/10 xong — `backend/src/financial/health_db.py` (bộ tính đọc DB, gộp xác minh hiện hành từng trường, giá trị lấy từ gói thô; `citation_for` trả tên tài liệu/link/trang) + `report_financial_health.py --from-db`, 63 test PASS, review Approved sau 1 vòng sửa.
- 12/11 Claude: Task 7/10 xong — job `backend/scripts/refresh_financial_statements.py` (mặc định chạy thử; mỗi mã 1 transaction; chốt an toàn >4 phiên bản/mã; so số chịu được nhiễu float của dữ liệu cũ; tra chỉ tiêu theo mã+bảng+ngành; tải lại PDF khi nguồn cập nhật), 89 test PASS, review Approved sau 1 vòng sửa. Chưa chạy thật.
- 12/11 Claude: Task 8/10 xong — renderer vector `db-financial-v5` (đầu đoạn ghi phạm vi/đơn vị đã xác minh + tên tài liệu; locator có url/tên/trang; dựng lại đoạn ghim đúng lần xác minh), `chunk_from_supabase.py --financial-renderer`, 103 test PASS, review Approved sau 1 vòng sửa. Chưa ghi vector (cần Nhân đồng ý).
- 13/11 Claude: Task 9/10 (lịch chạy BCTC 18:00, chờ migration mới chạy) đã code + 39 test PASS; review còn 2 việc. Đã tách 3 phần A/B/C giao Codex: `docs/sprint5/HANDOFF-CODEX-BCTC-METADATA-2026-11-13.md`. Claude không đụng file của 3 phần đó.

Codex: Phần A xong (13/11/2026) — `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_financial_refresh_schedule.py backend/tests/test_market_dual_runtime.py backend/tests/test_price_analysis_api.py backend/tests/test_market_activity_collector.py -q -p no:cacheprovider` — 41 passed, 1 skipped, 10 subtests passed in 4.97s.
Đã tích hợp candidate được QA/review và đối chiếu SHA; fixed argv/strict-warning policy, log và receipt: `.agent-state/bctc-metadata-20261113/integration-META-A.json`. Chỉ dùng DB test15434; chưa áp migration/refresh lên DB thật.

Codex: Phần C xong (13/11/2026) — `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_financial_verification_store.py backend/tests/test_financial_verification_schema.py backend/tests/test_financial_statements_refresh.py backend/tests/test_financial_health_db.py -q -p no:cacheprovider` — 48 passed, 10 subtests passed in 55.06s.
Đã tích hợp candidate được QA/review và đối chiếu SHA; fixed argv/strict-warning policy, log và receipt: `.agent-state/bctc-metadata-20261113/integration-META-C.json`. Chỉ dùng DB test 15434; chưa áp migration/refresh lên DB thật. GRANT: chỉ có mẫu role `finmind_chat_runtime` dành riêng cho `research_chat`, không có role tài chính phù hợp nên giữ nguyên quyền; test xác nhận Chat không được truy cập bảng xác minh.

Codex: Phần B chưa xong — candidate đã hoàn thiện offload và ZIP theo handoff mới; gate hiện `103 passed, 1 failed, 7 subtests passed`: hàm `extract_zip_pdfs` cũ xóa PDF không hợp lệ khi handle còn mở, gây WinError 32 trên Windows. Không sửa assertion để làm xanh, chưa tích hợp hai file B.
Đang chờ người dùng cho phép sửa thêm `data_pipeline/annual_reports/vietstock_download_annual.py` ngoài danh sách chín file; bản sửa tối thiểu: `.agent-state/bctc-metadata-20261113/extractor-fix-proposal.md`. Sau khi được phép: sửa helper trong candidate, chạy lại gate B, review receipt mới, tích hợp B và checkpoint. Không chạy Task 10/DB thật.

Codex: Phần B xong (13/11/2026) — `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_financial_statements_refresh.py backend/tests/test_financial_verification_store.py backend/tests/test_financial_verification.py backend/tests/test_statement_pdf.py backend/tests/test_vietstock_statements.py backend/tests/test_financial_health_db.py data_pipeline/annual_reports/tests -q -p no:cacheprovider` — 113 passed, 8 subtests passed in 42.06s.
Đã tích hợp B và sửa helper `extract_zip_pdfs` theo quyền bổ sung của người dùng: đóng handle trước khi xóa, giữ CRLF/lọc đường dẫn/giới hạn ZIP. Review cuối `code-review-b.md` APPROVE; root receipt `.agent-state/bctc-metadata-20261113/integration-META-B.json` gồm cả `annual_reports/tests`. A–B–C đã hoàn tất, thay thế trạng thái B chờ ở trên; chỉ dùng DB test 15434, chưa áp migration/refresh lên DB thật.
- 13/11 Claude: Codex xong A/B/C. Claude chạy lại toàn bộ test kế hoạch: 306 passed, 1 skipped. Đã sửa thêm `statement_pdf.py`/`verification.py` sau khi thử PDF thật (OCR dự phòng cho scan/lớp chữ lỗi/trang ảnh; đọc câu năm tài chính không ghi năm và câu "Kỳ kế toán năm" của ngân hàng; luật đơn vị theo trang có ghi đơn vị). Đang review toàn nhánh (opus). Chưa áp migration/chạy thật.
- 13/11 Claude: chỉnh đọc PDF thật — đơn vị ở dòng tiêu đề cột và trang "(tiếp theo)"; OCR đọc thêm tới trang 30 khi chưa thấy câu năm tài chính (ngân hàng); số bị OCR làm vỡ không bị coi là "lệch"; cơ sở so sánh chỉ xét chỉ tiêu KQKD. Chấm lại trên PDF thật: ELC Q3/2025 và FPT năm 2025 ra VERIFIED; FPT/TCB/VCB Q3 hợp nhất đã xác minh đơn vị, còn thiếu 1 chỉ tiêu do OCR hoặc chưa có trang năm tài chính trong cache. 78 test PASS.
- 13/11 ~10:15 Claude (tiếp quản fix wave vì Codex hết token, Codex mới có test đỏ trong `.agent-state/bctc-fixwave-20261113`, chưa sửa file chính). ĐÃ XONG (TDD, test PASS): #1 cờ `FINMIND_BCTC_REFRESH` mặc định tắt → reason DISABLED, không retry (`app.py`, 13 test schedule/runtime); #2 GRANT SELECT,INSERT finmind_developer + SELECT finmind_graph_reader trong migration và `010_schema.sql` (DO $$ bỏ qua role vắng; 28 test schema/store); #5 lỗi OCR (CalledProcessError/TimeoutExpired/OSError) → PdfUnreadable, `OMP_THREAD_LIMIT=1`; #11 bỏ NUL khỏi snippet; #6 health_db: currency=VND khi đơn vị đã xác minh, bảng cân đối period_start=period_end, không gộp RESTATED, `citation_for` cần số trang (56 test health); #7 phạm vi chỉ lấy khi tìm thấy chỉ tiêu bắt buộc; #8 quý CMG lệch lịch không VERIFIED; #9 ngân hàng lệch chỉ tiêu tùy chọn → PARTIAL/OPTIONAL_VALUE_MISMATCH (70 test pdf/verification). CÒN LẠI: #3 payload chỉ lưu khi có ghi, #4 cache OCR theo sha256, #10 choose() chọn kết luận nhiều chỉ tiêu nhất, #12 ZIP quá cỡ, #13 chỉ tiêu Vietcap lạ, #14 chạy thử read-only session (đều trong `refresh_financial_statements.py`/`verification_store.py`), #15 hậu tố đơn vị từng dòng vector v5 (`db_chunking.py`); sau đó review lại phần sửa. Chưa áp migration/chạy thật.
- 13/11 Claude: đã sửa V7 của Nhân (S5-WBS04.1) và push lên `nhan-sprint-501` commit `c5a9bf3c` theo yêu cầu user: chỉ thêm mẫu vào `intent_semantic_requests.py` + 30 test; 222 test PASS; replay 345 quyết định run03: sửa 26, hồi quy 0; đúng nhánh 167 câu 85,0%→98,2% (tập đã xem). Nhân cần chạy run04 với BGE-M3 để chốt. Chi tiết `outputs/sprint5/nhan-v7-fix-20261113/README.md`.
- 13/11 ~10:45 Claude: đợt sửa sau review cuối XONG 15/15 (thêm #3 dữ liệu thô chỉ lưu khi có ghi, #4 cache kết quả OCR theo sha256, #10 chọn kết luận nhiều chỉ tiêu nhất, #12 ZIP quá cỡ bỏ qua, #13 chỉ tiêu Vietcap lạ → báo cáo + cách ly UNKNOWN_METRIC thay vì hỏng mã, #14 chạy thử chỉ đọc ở mức phiên DB, #15 vector v5 giữ hậu tố "đơn vị chưa xác minh" cho dòng EPS/không phải VND). Toàn bộ test kế hoạch: 339 passed, 1 skipped. Đang review lại phần sửa. Chưa áp migration/chạy thật.
- 13/11 ~11:05 Claude: review lại đợt sửa (opus): 15/15 đạt; đã sửa thêm lỗi mới quan trọng (lỗi OCR do máy như thiếu Tesseract/timeout không còn bị cache vĩnh viễn — lớp `OcrUnavailable`), ghi cache lỗi không làm hỏng file, EPS giữ đơn vị VND/cổ phiếu. Reviewer: sẵn sàng chạy thử Task 10. Chờ user nói "chạy thật".
- 13/11 Claude TASK 10 (user: "chạy thật"): đã áp migration lên VPS bằng finmind_team (bảng + 2 trigger + GRANT finmind_developer INSERT,SELECT / finmind_graph_reader SELECT); VIETCAP_VCI → APPROVED, thêm nguồn "Vietstock BCTC" APPROVED; ENTRADE/vnstock_kbs giữ PENDING. Số dòng trước: `outputs/sprint5/bctc-task10/before.json`. Đang chạy thử.
- 13/11 ~11:45 Claude: PHẦN 2 (chat) đã code theo `docs/superpowers/specs/2026-11-13-financial-health-chat-design.md`: bằng chứng `FINANCIAL_HEALTH` (finmind_db) trong `market_contract.feed_item`, đoạn văn do code sinh (`backend/src/financial/health_passage.py`), `health_db.get_financial_health` (đọc chỉ đọc, cache 10 phút, chọn kỳ gần nhất có chỉ số đã xác minh, so nhóm, link PDF+trang qua `citation_for`), `MarketResearch(health_reader=…)` nối ở `research_chat.py`, prompt grounded thêm 1 câu. Test: 9 test mới + 579 test chat/market (src) + 100 (root) PASS. Chưa restart backend.
- 13/11 11:50 Claude TASK 10: chạy thử 10 mã xong (5 tiến trình song song), 0 mã lỗi. new_versions 1–2/mã: tỷ số theo giá (P/E, P/B, P/S, cổ tức, vốn hóa, số CP) kỳ 2025-YEAR/TCB 2026-Q3 do Vietcap tính lại theo giá; VCB 2024-YEAR EPS 5571→3727 (chia cổ phiếu thưởng). Kết quả: VERIFIED VCB 0, BID 2, CTG 2, MBB 4, TCB 4, FPT 6, CMG 0, ELC 4, ITD 0, ICT 0; lệch: CMG 12, FPT 6, VCB 6, TCB/MBB/ELC 2. 11:56 bắt đầu --apply (5 tiến trình). VIỆC CẦN TRƯỚC KHI BẬT LỊCH: loại tỷ số theo giá khỏi phép so restatement (nếu không, mỗi ngày sinh phiên bản và có thể chạm chốt 4).
- 13/11 12:10 Claude TASK 10 XONG: --apply 10/10 mã ok (financial_reports 1638→1686, observations 308546→315954 dòng cũ giữ nguyên, PDF BCTC 152, verifications 172 = 22 VERIFIED/120 PARTIAL/30 MISMATCH, quarantine +30, raw_payloads +37). --apply lần 2: 0 dòng mới mọi bảng (chỉ ingestion_jobs +20). Số trước/sau: `outputs/sprint5/bctc-task10/{before,after1,after2}.json`. Sửa lỗi phát hiện khi chạy thật: `health_db.fetch_health_records` trả id dạng UUID làm bộ tính loại mọi chỉ tiêu ("missing_observation_id") ở đường chat → chuyển sang chuỗi + test. Chat giờ thấy: MBB 2025 doanh thu +22,16%, LNST +19,31%; FPT/ELC Q3/2026 nợ/tài sản 41,54%/42,16% kèm link BCTC; 7 mã còn "chưa đủ dữ liệu đã xác minh". Backend đang tắt; lần chạy tới (Chạy-FinMind.cmd) dùng code mới. Lịch BCTC 18:00 vẫn TẮT (chưa đặt FINMIND_BCTC_REFRESH).
- 13/11 ~13:15 Claude: thử chat "phân tích fpt" → bị router hỏi chỉ tiêu BCTC (không vào MARKET_ANALYSIS). Sửa `live_research._market_intent`: "phân tích/đánh giá/mạnh hay yếu" → phân tích thị trường khi câu không nhắc chỉ tiêu tài chính, năm/quý hay BCTC/BCTN/báo cáo/chiến lược. 9 test mới; 1694 test router/chat PASS.

## 13/11 chiều — chat "phân tích fpt" báo "dịch vụ tạo câu trả lời không khả dụng"
- Nguyên nhân (gọi lại Gemini thật với bằng chứng đã lưu):
  1. `_units` hiểu "tỷ lệ nợ" là đơn vị "tỷ", nên loại câu sức khỏe tài chính (`UNSUPPORTED_CLAIM`).
  2. Schema MARKET_ANALYSIS cho phép 6 ý × 3 trích dẫn × 700 ký tự, vượt `max_output_tokens` 2048 (`OUTPUT_LIMIT_EXCEEDED`).
  3. Chỉ cần 1 ý sai là bỏ cả câu trả lời.
  4. Gemini thỉnh thoảng trả HTTP lỗi (`GEMINI_UNAVAILABLE`): khoảng 2/13 lần gọi, không retry theo policy.
- Sửa trong `grounded.py` và `service.py`:
  - bỏ qua "tỷ lệ/suất/trọng/giá" khi kiểm đơn vị;
  - dòng đầu của FINANCIAL_HEALTH/PRICE_TREND tính vào ngữ cảnh kiểm;
  - siết giới hạn: 5 ý, 500 ký tự mỗi ý, 4 trích dẫn × 300 ký tự;
  - MARKET_ANALYSIS chỉ lược ý không khớp nguồn (`PARTIAL_CLAIMS`, có ghi chú), không còn ý nào thì vẫn fail-closed.
- Kết quả: 297 test answering/market pass. Gemini thật 6/6 lần có câu trả lời, token đầu ra ~1300.
- Cần restart backend để nạp code mới.

Codex: market-ratio versions xong (13/11/2026) — values_differ bỏ đúng8code theo giá, EPS/kế toán vẫn tạo phiên bản. backend/.venv/Scripts/python.exe -m pytest backend/tests/test_financial_capture.py backend/tests/test_financial_health.py backend/tests/test_financial_health_chat.py backend/tests/test_financial_health_db.py backend/tests/test_financial_health_store.py backend/tests/test_financial_peers.py backend/tests/test_financial_refresh_schedule.py backend/tests/test_financial_statements_refresh.py backend/tests/test_financial_verification.py backend/tests/test_financial_verification_schema.py backend/tests/test_financial_verification_store.py -q -p no:cacheprovider —216passed/432subtests, QA/review APPROVE; full argv/warning policy ở receipt integration.json.
Dry run read-only FPT/MBB:0new_versions/0new_reports ở cả hai, sáu nhóm bảng theo dõi không đổi; không --apply/không bật FINMIND_BCTC_REFRESH. Báo cáo code/nguồn/diff/test/audit: docs/sprint5/REPORT-CODEX-MARKET-RATIO-VERSIONS-2026-11-13.md; còn8MISMATCH đã có (không ghi mới), ngoài phạm vi bản sửa này.
