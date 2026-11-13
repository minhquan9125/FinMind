# S5-WBS04.1 — Review phần Nhân: đối chiếu ý định và chính tả

Cập nhật 12/11/2026. Phụ trách Hồ Phạm Đăng Nhân; nhánh nhan-sprint-501.
Phạm vi: mẫu, vector, đối chiếu ý định và bằng chứng kiểm thử của Nhân.
Bản này chờ review kỹ thuật. Consumer, ngưỡng, fallback và router thuộc
task khác; các thử nghiệm consumer trước đó không dùng để nghiệm thu Nhân.

## Đã sửa

1. Đọc/độc và lương/lượng: kiểm chính tả Unicode NFC và ngữ cảnh trước
   khi dùng bản bỏ dấu. Hỗ trợ câu không dấu khi có ngữ cảnh phù hợp.
   Dùng chung kiểm chỉ tiêu cho NUMERIC và giải thích diễn biến TREND.
2. Bổ sung “Ai đang làm CEO/CFO”, “người đứng đầu”, “có tin gì mới”.
   Vế giải thích thay đổi tài chính có thể tạo TREND và ghép với NUMERIC.
   Không tự gán mọi câu “vì sao” hoặc câu thuật lại nguồn thành TREND.
3. Giữ raw ranking riêng với bằng chứng quy tắc; confidence=null và
   runtime_enabled=false. Ghi unresolved_requests khi mục tiêu chưa rõ.

## Điểm phải đọc kỹ: câu “độc lập”

Với “Lợi nhuận FPT có độc lập với mảng viễn thông không?”, quy tắc đã ngừng
ép NUMERIC và không còn ghi đè classifier bằng bằng chứng đọc sai.
**Classifier gốc vẫn đề xuất NUMERIC cho bản có dấu**; bản không dấu đề
xuất PERSON_ROLE. Không báo đã phân loại đúng hoặc đã sửa tính bất biến
của model. Câu được ghi unresolved_requests; phần Nhân chưa giải quyết
đúng nhãn cuối cho câu này. Không dùng kết quả đó để tự chọn tuyến.

## Kết quả đã đo

| Bộ đã xem | Có nhãn | V6 đúng | Bản mới đúng |
|---|---:|---:|---:|
| controls | 32 | 32 | 32 |
| development | 84 | 70 | 70 |
| known_diagnostic | 8 | 6 | 6 |
| previous_check | 28 | 24 | 24 |
| regression | 47 | 41 | 41 |
| previous_new_check | 42 | 39 | 39 |
| previous_final_check | 28 | 28 | 28 |
| review_probes | 15 | 15 | 15 |
| additional_checks | 20 | 20 | 20 |

313 hàng cũ giữ nguyên nhãn; không phát sinh đúng→sai. Chín hàng cũ
không có gold không được tính accuracy. Các lỗi cũ vẫn còn, không tự sửa gold.
32 probe bổ sung: **27/27 câu có gold đúng** và
**5/5 kiểm tra không ép nhãn đạt**. Năm câu này chưa có gold, không tính
là phân loại đúng. Các probe cùng tác giả và dựa trên review, không phải test mù.
Giữ training/model/head/điểm gốc. Vector hóa 50 văn bản bằng BGE-M3 cùng
revision ở run01; run02 dùng lại đúng cache sau sửa chung guard TREND.

| Probe chưa chốt gold | Nhãn đề xuất, chưa xác nhận đúng |
|---|---|
| R2-01: Lợi nhuận FPT có độc lập với mảng viễn thông không? | NUMERIC |
| R2-02: Loi nhuan FPT co doc lap voi mang vien thong khong? | PERSON_ROLE |
| R2-30: Giải thích vì sao ông An được bổ nhiệm. | NEWS |
| R2-31: Giải thích vì sao doanh thu giảm theo bài tin đã chỉ định. | NEWS |
| R2-32: Doc luong khach cua VJC nam 2024. | MIXED |

Các tập cũ còn sai:

| Bộ | Mã |
|---|---|
| development | DEV-NUMERIC-2-TCB, DEV-REPORT_CONTENT-2-VCB, DEV-REPORT_CONTENT-2-MBB, DEV-NEWS-1-TCB, DEV-NEWS-1-FPT, DEV-TREND-3-VCB, DEV-TREND-3-TCB, DEV-TREND-3-FPT, DEV-MIXED-1-TCB, DEV-MIXED-2-VCB, DEV-MIXED-2-TCB, DEV-MIXED-2-MBB, DEV-MIXED-2-FPT, DEV-MIXED-3-MBB |
| known_diagnostic | KNOWN-07, KNOWN-08 |
| previous_check | LATER-REPORT_CONTENT-2-DGC, LATER-REPORT_CONTENT-2-PNJ, LATER-NEWS-2-DGC, LATER-MIXED-2-PNJ |
| regression | S5-T-021, S5-T-027, S5-T-037, S5-T-039, S5-T-041, S5-T-042 |
| previous_new_check | NEW-NEWS-3-DBC, NEW-ENTITY_RELATION-2-VHC, NEW-ENTITY_RELATION-2-DBC |

## Phân biệt baseline và thử nghiệm mới

- Sau review Hưng ngày 13/11: bản thử consumer/helper cùng test liên quan
  đã gỡ khỏi backend; nguồn gốc lưu dưới scope-archive/*.snapshot.
  Audit dùng ba ánh xạ nguồn lịch sử rõ ràng, vẫn kiểm hash gốc;
  các nguồn phân loại Nhân đang dùng phải khớp hash hiện tại.
- IntentMatcher/CLI hiện có vẫn trả cosine-max-per-label-v1, đúng hợp đồng 04.1.
- Kết quả V7 ở đây dùng classifier và bằng chứng quy tắc offline.
  Điểm classifier chưa hiệu chỉnh không phải cosine hoặc độ tin cậy.
- Chưa thay baseline/CLI bằng V7; các sửa này chưa hiện diện trong Web Chat.
- Giá thuộc NUMERIC theo schema; nhãn ý định không tự quyết định nguồn BCTC.

## Bằng chứng và chạy lại

- **192/192 test riêng phần Nhân đạt**, không lỗi, skip hoặc test consumer/handoff.
  XML: outputs/s5_intent_review2_20261112/nhan-review-only.xml.
  Đây không phải kiểm thử toàn ứng dụng hoặc E2E Web Chat.
- Sau dọn consumer: 196/196 test đạt, gồm 192 test cũ và 4 test archive.
  Biên bản: outputs/s5_intent_review2_20261112/scope-cleanup-tests.xml.
- Phiên kiểm tra trước review này chưa hoàn tất lượt nạp lại BGE-M3 để
  mã hóa lại 56 query baseline: lần đầu vướng proxy, lần offline nạp model
  quá lâu nên đã dừng. Không ghi lượt đó là PASS; audit dưới đây dùng vector đã lưu.
- Audit tái tạo 345 quyết định; sai lệch probability lớn nhất
  7.77e-16; nguồn, raw ranking và head không đổi.
- Audit V6 vẫn qua. run01 là ứng viên trước hai test âm bổ sung về chất lượng;
  run02 giữ logic cuối nhưng manifest còn xuống dòng Windows. Bản bàn giao
  run03 chuẩn hóa manifest LF, giữ dữ liệu/logic/điểm, có snapshot metadata cũ.
- Artifact: outputs/s5_intent_review2_20261112/run03/results.json và audit.json.
Tại thư mục gốc (không cần DB, provider hay model weights cho audit):

```powershell
$env:PYTHONUTF8='1'
$env:OPENBLAS_NUM_THREADS='4'
.\backend\.venv\Scripts\python.exe backend/scripts/audit_s5_intent_review2.py
.\backend\.venv\Scripts\python.exe backend/scripts/report_s5_intent_review2.py
```

## Cần review/chốt

- Hưng: ngữ cảnh chính tả, role/news/giải thích, bảo toàn ca cũ và giới hạn
  của câu chưa có gold; phân biệt baseline với thử nghiệm V7.
- Nhóm: chốt ranh giới kế hoạch lợi nhuận trước khi dùng làm nhãn chung.
- Chỉ gửi review phần Nhân, chưa tự chốt Done hoặc tích hợp toàn luồng.
Task 01.2 tiếp tục tạm dừng theo yêu cầu Nhân.
