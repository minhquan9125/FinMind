# Đối chiếu Golden Set với nguồn và vector — 21/10/2026

Snapshot Supabase: **21/10/2026 09:29:34 giờ Việt Nam**.
Chỉ đọc database; không sửa Golden Set, không nhập nguồn, không chạy B1 hay
chấm chất lượng xếp hạng. Worker ingest corpus-v2 vẫn chạy độc lập.

## Kết quả theo nhóm

| Nhóm | Nguồn dữ liệu | Vector / kết luận |
| --- | --- | --- |
| Q01–Q09 | Khớp tiêu đề và ngày bài dẫn trong Golden Set cho đủ 9 câu | Có vector active trong index db-v1; số chunk theo Q01→Q09: 14, 4, 8, 6, 9, 18, 1, 4, 8 |
| Q15, Q17, Q19 | Đủ record VCB 20/05/2026, MSN 27/07/2026, VCB 23/04/2026; giá/volume khớp Golden | Mỗi phiên có 1 chunk active db-v1 chứa đúng price_id |
| Q10 | DB có 234 bài: CafeF 119, FireAnt 115; published_at từ 29/07 đến 14/10/2026 | Không so số 234 của DB hiện tại với đáp án tập cố định 224; cần danh sách thành viên/hash của tập 224 để tái lập đúng phạm vi |
| Q11–Q20, phép tính | Đã tính trực tiếp từ price_bars cho Q11/Q12/Q13/Q14/Q16/Q18/Q20 và đọc phiên Q15/Q17/Q19 | Số liệu giá khớp các giá trị Golden sau làm tròn; Q13 thiếu một ngày đồng cực đại, xem dưới |
| Q21–Q29 | Không có PDF BCTN/BCTC FPT 2024 được ingest trong các document hiện có | Chưa sẵn sàng theo đúng nguồn tài liệu Golden yêu cầu. Có file PDF cục bộ, nhưng không coi như đã ingest; các hàng tài chính structured 2024 không thay được toàn bộ BCTN |
| Q31–Q39 | Đủ mã chỉ tiêu được hỏi ở FPT 2026-Q2 và doanh thu Q1 dùng cho Q39; số nguồn khớp Golden | Tại snapshot chưa có chunk/vector active chứa các observation cụ thể này. Có trong bản nội dung corpus-v2, phải chờ ingest tới đúng các dòng; không suy ra từ số chunk v2 tổng |
| Q30 | Câu hỏi từ chối dự đoán giá/ngoài dữ liệu | Chưa chạy B1; không chấm pass/fail refusal chỉ từ việc không có nguồn |
| Q40 | DB FPT không có hàng kỳ 2026-Q4 | Đủ căn cứ xác định thiếu kỳ yêu cầu ở snapshot; vẫn phải chạy B1 để kiểm tra hành vi từ chối |

Đã dựng lại **75 chunk** thuộc 9 bài tin và 3 phiên giá nói trên bằng bộ đọc
production: nội dung/hash đều PASS. Việc có vector và đọc lại đúng hash **không
chứng minh truy vấn ngữ nghĩa hoặc câu trả lời B1 sẽ đúng**.

## Sai khác cần rà trong Golden Set

Không tự sửa file Golden trong lượt kiểm tra này.

### Q13: hai phiên cùng giá đóng cửa cao nhất

FPT có close tối đa **69,7** ở cả **10/04/2026 và 20/05/2026**. Golden chỉ ghi
10/04. Close tối thiểu **56,56 ngày 27/07/2026** đúng. Cần quy định chấp nhận
cả các ngày đồng hạng hay chỉ ngày xuất hiện đầu tiên.

### Locator tài chính: số đúng nhưng một số trường gốc sai

| Câu | Chỉ tiêu | Trường trong Golden | Trường trong locator DB hiện tại |
| --- | --- | --- | --- |
| Q32 | SHORT_TERM_LOANS_AND_FINANCE_LEASES | bsa55 | **bsa56** |
| Q33 | RETAINED_EARNINGS | bsa79 | **bsa90** |
| Q35 | PARENT_NET_PROFIT | isa21 | **isa22** |
| Q35 | BASIC_EARNINGS_PER_SHARE | isa22 | **isa23** |
| Q36 | CASH_FLOW_OPERATING | cfa15 | **cfa18** |
| Q37 | PURCHASE_FIXED_ASSETS | cfa16 | **cfa19** |

Các giá trị Q31–Q39 khớp số nguồn, nhưng DB đang ghi **SOURCE_NATIVE**, phạm vi
**UNKNOWN**, period_basis **UNVERIFIED**. Chưa đủ căn cứ nâng thành đơn vị VND,
báo cáo hợp nhất hoặc kỳ riêng quý chỉ vì Golden ghi như vậy. Riêng nguồn
normalized FPT có ratioType=RATIO_TTM ở 2026-Q2; Q38 không được diễn giải mặc
định là tỷ suất chỉ tính riêng ba tháng Q2.

Q39 dùng doanh thu Q2 13.788.503.461.199 và Q1 12.479.997.206.775: chênh
1.308.506.254.424, tỷ lệ khoảng 10,48%. Tính toán vẫn cần giữ điều kiện về kỳ
và phạm vi nguồn, không thay bằng suy luận từ vector.

## Các phép tính giá đã đối chiếu

- Q11: VCB 58,96 → 57,3, biến động -2,815468…%, làm tròn -2,82%.
- Q12: max volume toàn bộ 737 bars là MBB 38.940.600 ngày 20/05/2026.
- Q14: CTR 123 phiên, volume trung bình 316.523,577… → khoảng 316.524.
- Q16: NLG giảm mạnh nhất, -24,258289…% → -24,26%.
- Q18: 737 bars: CTR/FPT/MSN/NLG/VCB mỗi mã 123, MBB 122.
- Q20: MBB 19,65 → 19,2; chênh -0,45, -2,290076…% → -2,29%.

Giá ở đơn vị gốc price_scale=1000. Mở rộng cửa sổ hoặc thêm phiên mới có thể
làm thay đáp án tổng hợp; phải cố định cùng tập giá Golden khi đo benchmark.

## Index tại snapshot và cách tái kiểm tra

- db-v1: 2.048 active chunks.
- word-window-v1 (upload): 50 active chunks, document PDF là
  FinMind_BoCauHoiKiemThu_PassFail.pdf, không phải BCTN FPT 2024.
- db-corpus-v2: **835 active chunks**, trạng thái **BUILDING** tại snapshot.
  Đây là tiến độ, không phải một corpus benchmark hoàn chỉnh.

Script: `backend/scripts/audit_golden_sources.py`.
Chi tiết article_id, chunk_id, locator và số liệu:
`backend/.tmp/golden-source-audit-20261021.json`.
Chạy lại sẽ tạo snapshot trạng thái mới, không ghi database.
