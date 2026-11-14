# Golden40 v6 — Bản đề xuất chỉnh sửa để kiểm thử rõ từng chức năng

**Trạng thái: đề xuất, chưa nghiệm thu.** File này chứa 40 câu v6. Không dùng kết quả kiểm thử v5 để kết luận cho v6 và không coi đáp án v5 bên dưới là gold đã duyệt.
Nguồn tham chiếu: bản v5.0 ngày 21/10/2026 người dùng cung cấp, SHA-256 `cd53c32cea638ceb93bfd1d8790ba1ae1e3734e5d276cfa2ecde054a37d04eb1`. Bản v5 cần được lưu riêng nếu nhóm muốn đối chiếu; file hiện tại không phải bản v5.

## Cách đọc và các điểm đã sửa

- 27 câu tìm đoạn bằng vector; 9 câu truy vấn/tính toán; 2 câu tra phiên giá; 2 câu từ chối.
- Câu nhiều ý ghi rõ cần tìm đủ ý nào. Không đưa đáp án, nguồn gold hoặc ID đoạn đúng vào đầu vào truy vấn.
- Q02 chỉ trích số tiền lãi bài báo đã nêu; không lẫn với tự tính lãi một sản phẩm khác.
- Câu giá cố định provider và ngày bắt đầu/kết thúc; bỏ “mọi thời đại”, “ngày cuối hiện tại” và giả định kỷ lục. Cực trị chấp nhận toàn bộ ngày đồng hạng.
- Q31–Q39 hỏi số gốc, không tự biến SOURCE_NATIVE/UNKNOWN thành VND/hợp nhất/riêng quý. Q38 nêu cơ sở TTM; Q39 chỉ khẳng định tăng trưởng khi cơ sở so sánh được xác minh.
- Đáp án v5 được giữ là **tham khảo chưa duyệt lại**, không mặc định đúng. Trường “đáp án được duyệt” và nhãn gold để trống có chủ ý.
- Đây là sửa đề, không chạy B1, không nhập thêm dữ liệu hoặc cập nhật vector.

## Phạm vi corpus và phần còn thiếu

Index dự kiến: `434ef5e0-6516-578d-8d18-721d21347e01`; content manifest hash: `86e880eef3b39ddf2515951252025a8f58e700f80416ba24d6fabfe324362bd7`.
Vector v2 đã ingest/audit trước đó; chưa đăng ký corpus chính thức hoặc chạy B1. Chốt manifest ID lưu thật trước khi gắn nhãn gold.
Giá lịch sử 2018–25/09/2026 và PDF FPT 2024 chưa đủ trong corpus-v2 này. Cần chuẩn bị corpus/candidate mở rộng riêng; không ghi đè bản đã đóng băng.
Ngay trong cửa sổ giá hiện có cũng có khác bản nguồn: Q15 v5 ghi close 64,07 nhưng DB đã audit ghi 64,13. Không trộn đáp án ENTRADE v5 với tập giá v2 khác phiên bản.
Danh sách đoạn tự định vị bên JSON chỉ là **ứng viên để duyệt**, không phải nhãn đúng cuối cùng.

## Dùng bộ đề này để kiểm thử WBS20 và WBS25

**Đầu vào truy vấn** là nguyên văn trường **Câu hỏi đã sửa** của từng Q; chỉ thêm bộ lọc công ty, kỳ/ngày và loại nguồn khi chúng suy ra được từ chính câu hỏi. Không đưa **Cần lấy đủ**, đáp án v5, ID đoạn, content hash hay tài liệu gold vào query hoặc bộ lọc. Luôn ghi lại mã câu, mã index, phạm vi dữ liệu, `top_k`, cấu hình HNSW, thời điểm đo và số chunk active để lần sau so sánh được.

| Nhóm câu | Kiểm tra được gì | Điều kiện trước khi chấm đạt/trượt |
| --- | --- | --- |
| Q01–Q10 | Tìm đoạn tin tức bằng vector; đo top 5/top 10 và độ trễ, thử có lọc và không lọc. Q10 hiện là câu hỏi về bài báo, **không còn là phép đếm bài**. | Cần duyệt nhóm bằng chứng, ID chunk lưu DB và hash. Trước đó chỉ báo kết quả khảo sát, không công bố Recall/MRR chính thức. |
| Q11–Q14, Q16–Q18, Q20 | Lấy đúng tập phiên giá ENTRADE và tính bằng SQL/Decimal; đối chiếu ngày, `price_scale`, dấu và đơn vị. | Cần xác nhận bản nguồn/hash và đáp án theo đúng cửa sổ giá. Không tính các câu này vào Recall vector. |
| Q15, Q19 | Tra đúng một phiên giá và provenance của phiên đó. | Cần xác nhận provider, ngày, `price_id`, `price_scale` và đáp án; không chấm như câu tìm đoạn văn bằng vector. |
| Q21–Q29 | Tìm đoạn trong đúng PDF FPT 2024. | Chờ nạp và chốt phiên bản PDF; không thay bằng báo cáo tài chính clean. |
| Q31–Q38 | Tìm đoạn báo cáo tài chính clean trong index v2. | Cần sửa/kiểm tra đọc lại chunk tài chính đúng renderer, chốt phạm vi corpus, rồi duyệt bằng chứng và đơn vị/cơ sở kỳ. |
| Q39 | Lấy hai số gốc và chỉ tính khi cùng đơn vị, phạm vi, cơ sở kỳ. | Chấm dữ liệu đầu vào và phép tính riêng; không tính vào Recall vector. |
| Q30, Q40 | Kiểm tra hành vi từ chối khi thiếu bằng chứng trong nguồn đã giới hạn. | Chỉ chấm khi phạm vi nguồn đã chốt; vector trả đoạn gần nghĩa không tự động là lỗi. |

**WBS20 — chỉ mục và baseline:** đo cùng một bộ câu đủ điều kiện, cùng snapshot/index và cùng bộ lọc trước/sau HNSW; báo thời gian truy vấn, nguồn tìm được và số câu bị chặn. Nếu không có gold được duyệt, chỉ gọi là *baseline kỹ thuật/tạm thời*, không gọi là điểm chất lượng retrieval. Không so trực tiếp thời gian của index v1 (2.048 chunk active tại lần kiểm tra 21/10) với v2 (15.058 chunk active) để kết luận HNSW nhanh hơn.

**WBS25 — lọc phạm vi:** với mỗi câu đủ nguồn, thử đúng công ty/kỳ/loại tài liệu và thử cố ý sai từng bộ lọc. Kết quả đúng phải giữ nguyên trong phạm vi đã chọn; bộ lọc sai phải trả rỗng hoặc chỉ trả dữ liệu thuộc phạm vi được yêu cầu. Kiểm tra riêng `index_version_id` và `superseded_at IS NULL`. Chưa tuyên bố lọc đúng *corpus-v2* theo manifest khi corpus chưa đăng ký và API chưa kiểm tra membership.

**Trạng thái triển khai tại lần kiểm tra 21/10/2026:** Supabase đã có 15.058 vector v2 nhưng index còn `BUILDING`, chưa có hàng `corpus-v2` trong `corpus_versions`. API `/api/search/filtered` hiện chọn v1. Script `audit_golden_v6.py` chọn trực tiếp index v2 và đọc chunk tài chính bằng renderer ghi trong locator; kết quả của nó chỉ là khảo sát kỹ thuật, chưa phải chấm gold. Nếu nguồn hiện tại đã khác snapshot lúc ingest, báo cáo vẫn giữ hit và ghi `source_resolution_error` cho từng chunk, không xem đoạn lỗi là bằng chứng đọc được. Trong lần thử Q31, cả 5 hit tài chính top 5 gặp lỗi fingerprint nguồn; cần đối chiếu snapshot hoặc nguồn trước khi nghiệm thu retrieval tài chính. Các script audit v1 cũ không dùng để chấm bộ đề này.

Chạy trên **CMD** từ thư mục `backend` (kiểm tra định dạng trước, sau đó chọn hai câu thử hoặc chạy cả bộ):

```cmd
.venv\Scripts\python.exe -X utf8 scripts\audit_golden_v6.py --validate-only
.venv\Scripts\python.exe -X utf8 scripts\audit_golden_v6.py --ids Q01,Q31 --out .tmp\golden-v6-smoke.json
.venv\Scripts\python.exe -X utf8 scripts\audit_golden_v6.py --out .tmp\golden-v6-audit.json --top-k 5
```

Hai lệnh có `--out` chỉ đọc Supabase qua `backend/.env`, chạy embedding cho nhóm câu vector và ghi JSON vào `.tmp` trên máy. Mỗi câu ghi trạng thái, số hit, độ trễ và kết quả hai ca lọc sai công ty/kỳ; câu không thuộc retrieval ghi lý do chưa chấm. Không có `PASS 40/40` hay điểm Recall/MRR cho đến khi có gold được duyệt và corpus được đăng ký.

## Cách chấm đề xuất

1. **Tìm kiếm vector:** chạy hai cấu hình tách biệt: không lọc và lọc công ty/kỳ/loại nguồn suy từ câu hỏi. Không dùng ID gold, mã chỉ tiêu chỉ xuất hiện trong đáp án hoặc tên tài liệu gold làm bộ lọc bí mật.
2. Người duyệt chia câu thành các **nhóm bằng chứng bắt buộc**. Mỗi nhóm chứa các chunk ID lưu DB có thể thay thế nhau, content hash và đoạn trích giải thích vì sao đủ. Một chunk có thể đáp ứng nhiều nhóm nếu chứa đủ ý.
3. Evidence-group Recall@k = số nhóm có ít nhất một chunk đúng trong top-k / số nhóm cần thiết. Báo cáo @5 và @10; ghi riêng tỷ lệ tìm đủ tất cả nhóm. MRR dùng cho câu một nhóm bằng chứng; không trộn với câu tính toàn tập.
4. **Số liệu/tính toán:** chấm tập bản ghi đầu vào đúng, đủ và kết quả số học riêng. Dùng Decimal/SQL, giữ price_scale, không để vector thay phép đếm/MAX/AVG.
5. **Từ chối:** không chấm Recall/MRR. Vector vẫn có thể trả đoạn gần nghĩa; chấm hệ thống có nhận ra thiếu bằng chứng và tránh bịa số hay không.
6. Chỉ chấm các câu đủ nguồn và gold đã duyệt. Luôn báo tổng 40 câu, số đủ điều kiện và số bị chặn; không loại câu khó mà vẫn tuyên bố “40/40 đạt”.
7. Số nguyên đầy đủ so chính xác sau chuẩn hóa định dạng. Số làm tròn cho phép nửa đơn vị ở chữ số hiển thị cuối, chỉ khi đơn vị/quy đổi đã xác minh. Phần trăm 2 chữ số: ±0,005 điểm phần trăm; tỷ lệ 4 chữ số: ±0,00005. Không dùng một dung sai 0,1% chung cho mọi câu.
8. Nếu tách calibration/test, chia theo bài/tài liệu hoặc nhóm nguồn liên quan, không chia ngẫu nhiên các câu cùng PDF/bài sang hai bên. Các câu cùng PDF FPT phải tránh rò rỉ qua tập hiệu chỉnh.

## Danh sách 40 câu sau sửa

| Mã | Cách kiểm thử | Tình trạng cần xử lý |
| --- | --- | --- |
| Q01 | Tìm đoạn bằng vector | Cần duyệt đoạn bằng chứng |
| Q02 | Tìm đoạn bằng vector | Cần duyệt đoạn bằng chứng |
| Q03 | Tìm đoạn bằng vector | Cần duyệt đoạn bằng chứng |
| Q04 | Tìm đoạn bằng vector | Cần duyệt đoạn bằng chứng |
| Q05 | Tìm đoạn bằng vector | Cần duyệt đoạn bằng chứng |
| Q06 | Tìm đoạn bằng vector | Cần duyệt đoạn bằng chứng |
| Q07 | Tìm đoạn bằng vector | Cần duyệt đoạn bằng chứng |
| Q08 | Tìm đoạn bằng vector | Cần duyệt đoạn bằng chứng |
| Q09 | Tìm đoạn bằng vector | Cần duyệt đoạn bằng chứng |
| Q10 | Tìm đoạn bằng vector | Cần duyệt đoạn bằng chứng |
| Q11 | Truy vấn số liệu + tính toán | Cần khớp lại bản nguồn giá |
| Q12 | Truy vấn số liệu + tính toán | Cần khớp lại bản nguồn giá |
| Q13 | Truy vấn số liệu + tính toán | Cần khớp lại bản nguồn giá |
| Q14 | Truy vấn số liệu + tính toán | Cần khớp lại bản nguồn giá |
| Q15 | Tra cứu phiên giá | Cần khớp lại bản nguồn giá |
| Q16 | Truy vấn số liệu + tính toán | Cần khớp lại bản nguồn giá |
| Q17 | Truy vấn số liệu + tính toán | Cần khớp lại bản nguồn giá |
| Q18 | Truy vấn số liệu + tính toán | Cần khớp lại bản nguồn giá |
| Q19 | Tra cứu phiên giá | Cần khớp lại bản nguồn giá |
| Q20 | Truy vấn số liệu + tính toán | Cần khớp lại bản nguồn giá |
| Q21 | Tìm đoạn bằng vector | Chờ nạp/kiểm tra PDF |
| Q22 | Tìm đoạn bằng vector | Chờ nạp/kiểm tra PDF |
| Q23 | Tìm đoạn bằng vector | Chờ nạp/kiểm tra PDF |
| Q24 | Tìm đoạn bằng vector | Chờ nạp/kiểm tra PDF |
| Q25 | Tìm đoạn bằng vector | Chờ nạp/kiểm tra PDF |
| Q26 | Tìm đoạn bằng vector | Chờ nạp/kiểm tra PDF |
| Q27 | Tìm đoạn bằng vector | Chờ nạp/kiểm tra PDF |
| Q28 | Tìm đoạn bằng vector | Chờ nạp/kiểm tra PDF |
| Q29 | Tìm đoạn bằng vector | Chờ nạp/kiểm tra PDF |
| Q30 | Từ chối khi thiếu bằng chứng | Chờ nạp/kiểm tra PDF |
| Q31 | Tìm đoạn bằng vector | Cần xác minh đơn vị/phạm vi/cơ sở kỳ |
| Q32 | Tìm đoạn bằng vector | Cần xác minh đơn vị/phạm vi/cơ sở kỳ |
| Q33 | Tìm đoạn bằng vector | Cần xác minh đơn vị/phạm vi/cơ sở kỳ |
| Q34 | Tìm đoạn bằng vector | Cần xác minh đơn vị/phạm vi/cơ sở kỳ |
| Q35 | Tìm đoạn bằng vector | Cần xác minh đơn vị/phạm vi/cơ sở kỳ |
| Q36 | Tìm đoạn bằng vector | Cần xác minh đơn vị/phạm vi/cơ sở kỳ |
| Q37 | Tìm đoạn bằng vector | Cần xác minh đơn vị/phạm vi/cơ sở kỳ |
| Q38 | Tìm đoạn bằng vector | Cần xác minh đơn vị/phạm vi/cơ sở kỳ |
| Q39 | Truy vấn số liệu + tính toán | Cần xác minh đơn vị/phạm vi/cơ sở kỳ |
| Q40 | Từ chối khi thiếu bằng chứng | Cần duyệt phạm vi thiếu dữ liệu và thử hành vi từ chối |

### Q01 — Tìm đoạn bằng vector

**Câu hỏi đã sửa:** Theo bài FireAnt ngày 01/10/2026 về Techcombank (TCB), hai lô trái phiếu được tất toán trước hạn có mã gì, giá trị từng lô và tổng giá trị được bài viết nêu là bao nhiêu?

**Cần lấy đủ:** Mã hai lô trái phiếu; Giá trị từng lô; Tổng giá trị.
**Cách chấm:** Chỉ chấm khi gold đã duyệt: Evidence-group Recall@5/@10; MRR cho câu có một nhóm bằng chứng. Chấm đúng đáp án riêng.
**Trạng thái:** Cần duyệt đoạn bằng chứng. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** Techcombank tất toán trước hạn 2 lô trái phiếu mã **TCB12517** (1.740 tỷ đồng) và **TCB12518** (2.500 tỷ đồng), tổng giá trị **4.240 tỷ đồng**.

**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q02 — Tìm đoạn bằng vector

**Câu hỏi đã sửa:** Theo bài FireAnt ngày 01/10/2026 về lãi suất VietinBank (CTG), bài viết nêu khách gửi 300 triệu đồng kỳ hạn 24 tháng có thể nhận khoảng bao nhiêu tiền lãi và áp dụng mức lãi suất nào? Chỉ trích thông tin bài viết đã nêu, không tính một sản phẩm tiết kiệm khác.

**Cần lấy đủ:** Tiền gửi và kỳ hạn bài nêu; Số tiền lãi bài nêu; Lãi suất áp dụng.
**Cách chấm:** Chỉ chấm khi gold đã duyệt: Evidence-group Recall@5/@10; MRR cho câu có một nhóm bằng chứng. Chấm đúng đáp án riêng.
**Trạng thái:** Cần duyệt đoạn bằng chứng. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** Số tiền lãi nhận được là **36 triệu đồng** (áp dụng mức lãi suất 6,0%/năm cho kỳ hạn 24 tháng).

**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q03 — Tìm đoạn bằng vector

**Câu hỏi đã sửa:** Theo bài CafeF ngày 29/09/2026 về đợt tăng vốn FPT, số cổ phiếu đã phân phối, số cổ đông nhận cổ phiếu và ngày kết thúc phát hành được nêu là bao nhiêu?

**Cần lấy đủ:** Số cổ phiếu; Số cổ đông; Ngày kết thúc.
**Cách chấm:** Chỉ chấm khi gold đã duyệt: Evidence-group Recall@5/@10; MRR cho câu có một nhóm bằng chứng. Chấm đúng đáp án riêng.
**Trạng thái:** Cần duyệt đoạn bằng chứng. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** FPT phân phối hơn **171,4 triệu cổ phiếu** cho **181.748 cổ đông**. Ngày kết thúc đợt phát hành là ngày **22/09/2026**.

**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q04 — Tìm đoạn bằng vector

**Câu hỏi đã sửa:** Theo bài FireAnt ngày 29/09/2026, số lượng cổ đông FPT và tỷ lệ sở hữu của khối ngoại tại thời điểm bài viết là bao nhiêu?

**Cần lấy đủ:** Số cổ đông; Tỷ lệ khối ngoại.
**Cách chấm:** Chỉ chấm khi gold đã duyệt: Evidence-group Recall@5/@10; MRR cho câu có một nhóm bằng chứng. Chấm đúng đáp án riêng.
**Trạng thái:** Cần duyệt đoạn bằng chứng. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** FPT có gần **182.000 cổ đông**. Khối ngoại nắm giữ **28,5% vốn** (giảm từ mức 49% cuối năm 2022).

**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q05 — Tìm đoạn bằng vector

**Câu hỏi đã sửa:** Theo bản tin dẫn SSI Research ngày 29/09/2026, CTG và VCB được dự báo lợi nhuận trước thuế quý 3/2026 lần lượt bao nhiêu? Đây là dự báo hay kết quả đã thực hiện?

**Cần lấy đủ:** Dự báo CTG; Dự báo VCB; Tính chất dự báo.
**Cách chấm:** Chỉ chấm khi gold đã duyệt: Evidence-group Recall@5/@10; MRR cho câu có một nhóm bằng chứng. Chấm đúng đáp án riêng.
**Trạng thái:** Cần duyệt đoạn bằng chứng. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** **VietinBank (CTG)** được dự báo đạt **13.500 tỷ đồng** LNTT (tăng 27% so với cùng kỳ) và **Vietcombank (VCB)** đứng tiếp theo đạt **12.800 tỷ đồng** LNTT (tăng 14%).

**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q06 — Tìm đoạn bằng vector

**Câu hỏi đã sửa:** Theo bài FireAnt ngày 30/09/2026, quy mô tổng tài sản của MBB và số doanh nghiệp thành viên trong hệ sinh thái được bài viết nêu là bao nhiêu?

**Cần lấy đủ:** Tổng tài sản; Số doanh nghiệp thành viên.
**Cách chấm:** Chỉ chấm khi gold đã duyệt: Evidence-group Recall@5/@10; MRR cho câu có một nhóm bằng chứng. Chấm đúng đáp án riêng.
**Trạng thái:** Cần duyệt đoạn bằng chứng. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** MBB có quy mô tài sản hơn **1,73 triệu tỷ đồng** và hệ sinh thái gồm **8 doanh nghiệp thành viên**.

**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q07 — Tìm đoạn bằng vector

**Câu hỏi đã sửa:** Theo bản tin FireAnt ngày 14/10/2026, Techcombank nhận được chấp thuận về nội dung gì và cơ quan nào chấp thuận? Nếu bài không nêu rõ cơ quan thì không suy đoán.

**Cần lấy đủ:** Nội dung chấp thuận; Cơ quan chấp thuận hoặc chưa nêu.
**Cách chấm:** Chỉ chấm khi gold đã duyệt: Evidence-group Recall@5/@10; MRR cho câu có một nhóm bằng chứng. Chấm đúng đáp án riêng.
**Trạng thái:** Cần duyệt đoạn bằng chứng. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** Techcombank nhận được văn bản chấp thuận từ Ngân hàng Nhà nước về **phương án tăng vốn điều lệ**.

**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q08 — Tìm đoạn bằng vector

**Câu hỏi đã sửa:** Theo bài CafeF ngày 05/08/2026 về Vietcombank Tower, bài viết nêu Vietcombank chi bao nhiêu tiền? Phân biệt giao dịch tăng sở hữu từ 52% lên 70% với thông tin chủ sở hữu 100% tại thời điểm đăng ký doanh nghiệp được dẫn trong bài.

**Cần lấy đủ:** Khoản tiền bài nêu; Mốc sở hữu 52% → 70%; Mốc doanh nghiệp một chủ 100%.
**Cách chấm:** Chỉ chấm khi gold đã duyệt: Evidence-group Recall@5/@10; MRR cho câu có một nhóm bằng chứng. Chấm đúng đáp án riêng.
**Trạng thái:** Cần duyệt đoạn bằng chứng. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** Vietcombank đã chi **3.200 tỷ đồng** (nâng tỷ lệ sở hữu từ 52% lên 70% sau khi nhận chuyển nhượng 18% vốn từ Setra, sau đó chuyển đổi thành Công ty TNHH Một thành viên Vietcombank-Bonday-Benthanh với vốn điều lệ hơn **789 tỷ đồng** do Vietcombank sở hữu 100%).

**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q09 — Tìm đoạn bằng vector

**Câu hỏi đã sửa:** Theo bài CafeF dẫn TCBS Research ngày 28/09/2026, trợ lý lập trình AI của FPT cải thiện tốc độ viết mã bao nhiêu phần trăm và năng suất toàn dự án bao nhiêu phần trăm? Nêu đúng hai cấp độ đo.

**Cần lấy đủ:** Tốc độ viết mã; Năng suất dự án.
**Cách chấm:** Chỉ chấm khi gold đã duyệt: Evidence-group Recall@5/@10; MRR cho câu có một nhóm bằng chứng. Chấm đúng đáp án riêng.
**Trạng thái:** Cần duyệt đoạn bằng chứng. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** Công cụ trợ lý lập trình AI của FPT giúp cải thiện khoảng **30% tốc độ viết mã**, nhưng mức tăng năng suất đo ở cấp độ toàn dự án chỉ khoảng **10%** (chênh lệch 20 điểm phần trăm do dự án công nghệ còn bao gồm các khâu phân tích nghiệp vụ, tích hợp hệ thống, kiểm thử và quản trị dự án).

**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q10 — Tìm đoạn bằng vector

**Câu hỏi đã sửa:** Theo bài CafeF ngày 13/10/2026, tại 30/09/2026 nhân sự toàn hệ sinh thái FPT xấp xỉ bao nhiêu người và tăng thêm bao nhiêu so với cuối năm 2025? Không dùng nhân sự các đơn vị hợp nhất thay tổng hệ sinh thái.

**Cần lấy đủ:** Nhân sự toàn hệ sinh thái; Mức tăng và mốc so sánh.
**Cách chấm:** Chỉ chấm khi gold đã duyệt: Evidence-group Recall@5/@10; MRR cho câu có một nhóm bằng chứng. Chấm đúng đáp án riêng.
**Trạng thái:** Cần duyệt đoạn bằng chứng. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** Tổng quy mô nhân sự toàn hệ sinh thái của FPT đạt **gần 90.000 người**, tăng thêm **3.682 người** (tương đương tăng **4,3%**) so với cuối năm 2025 (trong đó khối các đơn vị được hợp nhất trong BCTC ghi nhận 45.145 nhân sự).

**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q11 — Truy vấn số liệu + tính toán

**Câu hỏi đã sửa:** Trong bản giá ENTRADE đã đóng băng của VCB, lấy giá đóng cửa tại đúng hai ngày 02/01/2018 và 25/09/2026. Hai giá là bao nhiêu và biến động phần trăm giữa hai ngày là bao nhiêu?

**Cần lấy đủ:** Tập giá đúng provider, hash và cửa sổ nêu trong câu hỏi; Các bản ghi đầu vào đủ để tính/tra chính xác.
**Cách chấm:** Chấm đủ dữ liệu đầu vào riêng, phép tính Decimal/SQL riêng; thiếu tập đầu vào không quy thành lỗi xếp hạng vector.
**Trạng thái:** Cần khớp lại bản nguồn giá. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** Close phiên cuối (25/09/2026): **58,0 (×1.000 VND)**. Close phiên đầu (02/01/2018): **23,06 (×1.000 VND)**. Tỷ lệ tăng trưởng toàn kỳ đạt: **+151,52%**.

**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q12 — Truy vấn số liệu + tính toán

**Câu hỏi đã sửa:** Trong bản giá ENTRADE đã đóng băng của MBB, chỉ xét từ 02/01/2018 đến hết 25/09/2026, phiên hoặc các phiên nào có volume lớn nhất và volume đó là bao nhiêu?

**Cần lấy đủ:** Tập giá đúng provider, hash và cửa sổ nêu trong câu hỏi; Các bản ghi đầu vào đủ để tính/tra chính xác.
**Cách chấm:** Chấm đủ dữ liệu đầu vào riêng, phép tính Decimal/SQL riêng; thiếu tập đầu vào không quy thành lỗi xếp hạng vector.
**Trạng thái:** Cần khớp lại bản nguồn giá. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** Phiên ngày **15/08/2025** ghi nhận khối lượng khớp lệnh kỷ lục đạt **117.471.296 cổ phiếu** (giá đóng cửa phiên đạt 22,62 ×1.000 VND).

**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q13 — Truy vấn số liệu + tính toán

**Câu hỏi đã sửa:** Trong bản giá ENTRADE đã đóng băng của FPT từ 02/01/2018 đến hết 25/09/2026, giá đóng cửa cao nhất và thấp nhất là bao nhiêu? Liệt kê tất cả ngày đồng hạng ở từng cực trị.

**Cần lấy đủ:** Tập giá đúng provider, hash và cửa sổ nêu trong câu hỏi; Các bản ghi đầu vào đủ để tính/tra chính xác.
**Cách chấm:** Chấm đủ dữ liệu đầu vào riêng, phép tính Decimal/SQL riêng; thiếu tập đầu vào không quy thành lỗi xếp hạng vector.
**Trạng thái:** Cần khớp lại bản nguồn giá. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** Highest Close đạt **118,06 (×1.000 VND)** vào ngày **23/01/2025**. Lowest Close ghi nhận **10,75 (×1.000 VND)** vào ngày **12/07/2018**.

**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q14 — Truy vấn số liệu + tính toán

**Câu hỏi đã sửa:** Trong bản giá ENTRADE đã đóng băng của MBB, chọn đúng 20 phiên có giao dịch gần nhất không muộn hơn 25/09/2026. Tổng volume và volume bình quân của 20 phiên là bao nhiêu? Nêu ngày đầu và cuối của cửa sổ thực tế.

**Cần lấy đủ:** Tập giá đúng provider, hash và cửa sổ nêu trong câu hỏi; Các bản ghi đầu vào đủ để tính/tra chính xác.
**Cách chấm:** Chấm đủ dữ liệu đầu vào riêng, phép tính Decimal/SQL riêng; thiếu tập đầu vào không quy thành lỗi xếp hạng vector.
**Trạng thái:** Cần khớp lại bản nguồn giá. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** Khối lượng giao dịch bình quân 20 phiên đạt **11.900.830 cổ phiếu/phiên** (tổng volume 20 phiên đạt 238.016.600 cổ phiếu).

**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q15 — Tra cứu phiên giá

**Câu hỏi đã sửa:** Theo bản giá ENTRADE đã đóng băng của VCB, ngày 20/05/2026 có open, high, low, close và volume bao nhiêu? Nêu price_scale và đơn vị theo chính bản nguồn này.

**Cần lấy đủ:** Tập giá đúng provider, hash và cửa sổ nêu trong câu hỏi; Các bản ghi đầu vào đủ để tính/tra chính xác.
**Cách chấm:** Đối chiếu đúng một phiên giá theo provider, ngày và `price_id`; kiểm tra đủ OHLCV, `price_scale` và đơn vị sau khi nguồn/đáp án được duyệt. Không tính Recall/MRR vector.
**Trạng thái:** Cần khớp lại bản nguồn giá. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** Open = **63,17** | High = **64,17** | Low = **61,29** | Close = **64,07 (×1.000 VND)**. Khối lượng khớp lệnh đạt **14.381.600 cổ phiếu**.

**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q16 — Truy vấn số liệu + tính toán

**Câu hỏi đã sửa:** Theo bản giá ENTRADE đã đóng băng, tính phần trăm biến động close của VCB, MBB và FPT từ đúng phiên 03/09/2026 đến 25/09/2026. Mã nào có mức biến động cao nhất? Nếu bằng nhau, liệt kê tất cả mã đồng hạng.

**Cần lấy đủ:** Tập giá đúng provider, hash và cửa sổ nêu trong câu hỏi; Các bản ghi đầu vào đủ để tính/tra chính xác.
**Cách chấm:** Chấm đủ dữ liệu đầu vào riêng, phép tính Decimal/SQL riêng; thiếu tập đầu vào không quy thành lỗi xếp hạng vector.
**Trạng thái:** Cần khớp lại bản nguồn giá. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** **VCB** giữ giá tốt nhất với mức giảm chỉ **−1,19%** (từ 58,70 xuống 58,00 ×1.000 VND); trong khi FPT giảm **−1,43%** (từ 65,64 xuống 64,70 ×1.000 VND) và MBB giảm **−3,40%** (từ 20,60 xuống 19,90 ×1.000 VND).

**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q17 — Truy vấn số liệu + tính toán

**Câu hỏi đã sửa:** Trong bản giá ENTRADE đã đóng băng của FPT từ 02/01/2018 đến hết 25/09/2026, phiên hoặc các phiên nào có high trừ low lớn nhất? Nêu high, low và biên độ, giữ cùng cơ sở giá và price_scale.

**Cần lấy đủ:** Tập giá đúng provider, hash và cửa sổ nêu trong câu hỏi; Các bản ghi đầu vào đủ để tính/tra chính xác.
**Cách chấm:** Chấm đủ dữ liệu đầu vào riêng, phép tính Decimal/SQL riêng; thiếu tập đầu vào không quy thành lỗi xếp hạng vector.
**Trạng thái:** Cần khớp lại bản nguồn giá. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** Phiên ngày **09/04/2025** có biên độ dao động lớn nhất là **7,80 (×1.000 VND)** (tương ứng 7.800 đ/cổ phiếu, với High = 82,64 và Low = 74,84).

**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q18 — Truy vấn số liệu + tính toán

**Câu hỏi đã sửa:** Trong bản giá ENTRADE đã đóng băng của VCB từ 02/01/2018 đến hết 25/09/2026, có bao nhiêu ngày giao dịch phân biệt với bản ghi hợp lệ? Không tính bản trùng ngày, không suy số phiên từ số ngày làm việc.

**Cần lấy đủ:** Tập giá đúng provider, hash và cửa sổ nêu trong câu hỏi; Các bản ghi đầu vào đủ để tính/tra chính xác.
**Cách chấm:** Chấm đủ dữ liệu đầu vào riêng, phép tính Decimal/SQL riêng; thiếu tập đầu vào không quy thành lỗi xếp hạng vector.
**Trạng thái:** Cần khớp lại bản nguồn giá. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** **2.174 phiên giao dịch (bars)**, bao phủ đầy đủ toàn bộ các ngày làm việc liên tục của sàn HOSE từ đầu năm 2018 đến cuối tháng 9/2026.

**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q19 — Tra cứu phiên giá

**Câu hỏi đã sửa:** Theo bản giá ENTRADE đã đóng băng của VCB, ngày 23/04/2026 có volume, open, high, low và close bao nhiêu? Chỉ tra phiên này; không mặc định đây là kỷ lục toàn lịch sử.

**Cần lấy đủ:** Tập giá đúng provider, hash và cửa sổ nêu trong câu hỏi; Các bản ghi đầu vào đủ để tính/tra chính xác.
**Cách chấm:** Đối chiếu đúng một phiên giá theo provider, ngày và `price_id`; kiểm tra đủ OHLCV, `price_scale` và đơn vị sau khi nguồn/đáp án được duyệt. Không tính Recall/MRR vector.
**Trạng thái:** Cần khớp lại bản nguồn giá. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** Volume kỷ lục: **35.200.000 cổ phiếu**. Open = **59,21** | High = **62,98** | Low = **59,11** | Close = **62,28 (×1.000 VND)**.

**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q20 — Truy vấn số liệu + tính toán

**Câu hỏi đã sửa:** Theo bản giá ENTRADE đã đóng băng của MBB, close tại đúng ngày 17/09/2026 và 25/09/2026 là bao nhiêu? Tính chênh lệch có dấu và phần trăm biến động giữa hai ngày.

**Cần lấy đủ:** Tập giá đúng provider, hash và cửa sổ nêu trong câu hỏi; Các bản ghi đầu vào đủ để tính/tra chính xác.
**Cách chấm:** Chấm đủ dữ liệu đầu vào riêng, phép tính Decimal/SQL riêng; thiếu tập đầu vào không quy thành lỗi xếp hạng vector.
**Trạng thái:** Cần khớp lại bản nguồn giá. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** Close ngày 17/09/2026: **20,55** → Close ngày 25/09/2026: **19,90 (×1.000 VND)**. Giảm **0,65 (×1.000 VND)** (tương ứng giảm 650 đ/cổ phiếu), tỷ lệ giảm đạt **−3,16%**.

**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q21 — Tìm đoạn bằng vector

**Câu hỏi đã sửa:** Theo BCTC hợp nhất kiểm toán trong đúng PDF FPT 2024 đã chốt phiên bản, doanh thu thuần năm 2024 là bao nhiêu? Dẫn dòng, cột năm và đơn vị trên bảng.

**Cần lấy đủ:** Đúng bảng/đoạn và tiêu đề, đơn vị, cột năm hoặc phạm vi được hỏi.
**Cách chấm:** Chỉ chấm khi gold đã duyệt: Evidence-group Recall@5/@10; MRR cho câu có một nhóm bằng chứng. Chấm đúng đáp án riêng.
**Trạng thái:** Chờ nạp/kiểm tra PDF. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** `62.848.794.351.367 VND` (hoặc `62.849 tỷ VND`).

**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q22 — Tìm đoạn bằng vector

**Câu hỏi đã sửa:** Theo đúng PDF FPT 2024 đã chốt phiên bản, lợi nhuận sau thuế năm 2024 thuộc cổ đông công ty mẹ là bao nhiêu? Không thay bằng tổng lợi nhuận sau thuế hợp nhất.

**Cần lấy đủ:** Đúng bảng/đoạn và tiêu đề, đơn vị, cột năm hoặc phạm vi được hỏi.
**Cách chấm:** Chỉ chấm khi gold đã duyệt: Evidence-group Recall@5/@10; MRR cho câu có một nhóm bằng chứng. Chấm đúng đáp án riêng.
**Trạng thái:** Chờ nạp/kiểm tra PDF. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** `7.856.767.812.178 VND` (hoặc `7.857 tỷ VND`).

**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q23 — Tìm đoạn bằng vector

**Câu hỏi đã sửa:** Theo bảng cân đối kế toán hợp nhất trong đúng PDF FPT 2024 đã chốt phiên bản, tổng tài sản tại 31/12/2024 là bao nhiêu? Dẫn đúng cột cuối năm và đơn vị.

**Cần lấy đủ:** Đúng bảng/đoạn và tiêu đề, đơn vị, cột năm hoặc phạm vi được hỏi.
**Cách chấm:** Chỉ chấm khi gold đã duyệt: Evidence-group Recall@5/@10; MRR cho câu có một nhóm bằng chứng. Chấm đúng đáp án riêng.
**Trạng thái:** Chờ nạp/kiểm tra PDF. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** `71.999.995.678.620 VND` (hoặc `~72.000 tỷ VND`).

**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q24 — Tìm đoạn bằng vector

**Câu hỏi đã sửa:** Theo báo cáo lưu chuyển tiền tệ hợp nhất trong đúng PDF FPT 2024 đã chốt phiên bản, lưu chuyển tiền thuần từ hoạt động kinh doanh năm 2024 là bao nhiêu?

**Cần lấy đủ:** Đúng bảng/đoạn và tiêu đề, đơn vị, cột năm hoặc phạm vi được hỏi.
**Cách chấm:** Chỉ chấm khi gold đã duyệt: Evidence-group Recall@5/@10; MRR cho câu có một nhóm bằng chứng. Chấm đúng đáp án riêng.
**Trạng thái:** Chờ nạp/kiểm tra PDF. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** `11.703.777.188.868 VND` (hoặc `~11.704 tỷ VND`).

**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q25 — Tìm đoạn bằng vector

**Câu hỏi đã sửa:** Theo Thuyết minh 34(b), báo cáo bộ phận theo khu vực địa lý trong đúng PDF FPT 2024, doanh thu thuần ở cột Nước ngoài năm 2024 là bao nhiêu và bảng ghi đơn vị gì? Không thay bằng doanh thu riêng dịch vụ CNTT nước ngoài.

**Cần lấy đủ:** Đúng bảng/đoạn và tiêu đề, đơn vị, cột năm hoặc phạm vi được hỏi.
**Cách chấm:** Chỉ chấm khi gold đã duyệt: Evidence-group Recall@5/@10; MRR cho câu có một nhóm bằng chứng. Chấm đúng đáp án riêng.
**Trạng thái:** Chờ nạp/kiểm tra PDF. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** `31.294.207 triệu VND` (hoặc `31.294 tỷ VND`).

**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q26 — Tìm đoạn bằng vector

**Câu hỏi đã sửa:** Theo bảng Top 10 cổ đông lớn trong đúng PDF BCTN FPT 2024, cá nhân nào có số cổ phần lớn nhất trong bảng, số cổ phần và tỷ lệ sở hữu là bao nhiêu? Dẫn ngày chốt danh sách nếu tài liệu có nêu.

**Cần lấy đủ:** Đúng bảng/đoạn và tiêu đề, đơn vị, cột năm hoặc phạm vi được hỏi.
**Cách chấm:** Chỉ chấm khi gold đã duyệt: Evidence-group Recall@5/@10; MRR cho câu có một nhóm bằng chứng. Chấm đúng đáp án riêng.
**Trạng thái:** Chờ nạp/kiểm tra PDF. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** **Trương Gia Bình**; sở hữu **102.041.710 cổ phần** (**6,94%**).

**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q27 — Tìm đoạn bằng vector

**Câu hỏi đã sửa:** Theo bảng chi tiết thù lao HĐQT trong đúng PDF BCTN FPT 2024, mức thù lao thực nhận năm 2024 của ông Trương Gia Bình là bao nhiêu? Phân biệt số 0 với ô trống hoặc không công bố.

**Cần lấy đủ:** Đúng bảng/đoạn và tiêu đề, đơn vị, cột năm hoặc phạm vi được hỏi.
**Cách chấm:** Chỉ chấm khi gold đã duyệt: Evidence-group Recall@5/@10; MRR cho câu có một nhóm bằng chứng. Chấm đúng đáp án riêng.
**Trạng thái:** Chờ nạp/kiểm tra PDF. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** **0 VND** (Không nhận thù lao).

**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q28 — Tìm đoạn bằng vector

**Câu hỏi đã sửa:** Theo phần ESG trong đúng PDF BCTN FPT 2024, tỷ lệ nhân sự nữ được công bố là bao nhiêu và mẫu số/phạm vi nhân sự được tài liệu mô tả thế nào? Nếu không nêu rõ phạm vi thì ghi chưa rõ.

**Cần lấy đủ:** Đúng bảng/đoạn và tiêu đề, đơn vị, cột năm hoặc phạm vi được hỏi.
**Cách chấm:** Chỉ chấm khi gold đã duyệt: Evidence-group Recall@5/@10; MRR cho câu có một nhóm bằng chứng. Chấm đúng đáp án riêng.
**Trạng thái:** Chờ nạp/kiểm tra PDF. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** **37,1%**.

**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q29 — Tìm đoạn bằng vector

**Câu hỏi đã sửa:** Theo báo cáo kiểm toán độc lập trong đúng PDF FPT 2024, tên đơn vị kiểm toán và loại ý kiến đối với BCTC hợp nhất năm 2024 là gì? Dẫn đoạn ý kiến và tên đơn vị ký báo cáo.

**Cần lấy đủ:** Đúng bảng/đoạn và tiêu đề, đơn vị, cột năm hoặc phạm vi được hỏi.
**Cách chấm:** Chỉ chấm khi gold đã duyệt: Evidence-group Recall@5/@10; MRR cho câu có một nhóm bằng chứng. Chấm đúng đáp án riêng.
**Trạng thái:** Chờ nạp/kiểm tra PDF. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** **Công ty TNHH PwC (Việt Nam)**; Ý kiến kiểm toán: **Chấp nhận toàn phần** *(trung thực và hợp lý trên các khía cạnh trọng yếu)*.

**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q30 — Từ chối khi thiếu bằng chứng

**Câu hỏi đã sửa:** Chỉ dựa trên đúng PDF BCTN FPT 2024 trong tập kiểm thử, mức giá mục tiêu cổ phiếu FPT vào cuối năm 2025 được tài liệu dự báo là bao nhiêu?

**Cần lấy đủ:** Xác nhận nguồn và phạm vi đóng băng; Trả lời không đủ thông tin, không bịa con số.
**Cách chấm:** Chấm câu trả lời không bịa và nêu thiếu bằng chứng; không dùng Recall/MRR, không yêu cầu vector trả rỗng.
**Trạng thái:** Chờ nạp/kiểm tra PDF. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** **Không có thông tin / Hệ thống phải từ chối trả lời (Safe Refusal)**. BCTN 2024 không đưa ra dự báo giá cổ phiếu tương lai.

**Kỳ vọng đề xuất:** Nêu không đủ thông tin trong đúng nguồn/phạm vi đã chốt; không bịa số. Lý do từ chối phải dựa bằng chứng, không chỉ vì bộ đề gắn nhãn từ chối.
**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q31 — Tìm đoạn bằng vector

**Câu hỏi đã sửa:** Trong bản dữ liệu clean FPT đã đóng băng, tại kỳ 2026-Q2, tiền và các khoản tương đương tiền có giá trị gốc bao nhiêu? Nêu đơn vị và phạm vi báo cáo nếu nguồn xác nhận; nếu chưa thì ghi chưa xác minh.

**Cần lấy đủ:** CASH_AND_CASH_EQUIVALENTS; kỳ 2026-Q2.
**Cách chấm:** Chỉ chấm khi gold đã duyệt: Evidence-group Recall@5/@10; MRR cho câu có một nhóm bằng chứng. Chấm đúng đáp án riêng.
**Trạng thái:** Cần xác minh đơn vị/phạm vi/cơ sở kỳ. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** `8.843.161.132.730 VND` (hoặc `8.843,16 tỷ VND`).

**Tham chiếu trường nguồn đã đối chiếu trước đó:** `bsa2`. Vẫn phải khớp đúng hash file/phiên bản nguồn khi nghiệm thu.
**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q32 — Tìm đoạn bằng vector

**Câu hỏi đã sửa:** Trong bản dữ liệu clean FPT đã đóng băng, tại kỳ 2026-Q2, dư nợ vay và nợ thuê tài chính ngắn hạn có giá trị gốc bao nhiêu? Không thay bằng tổng nợ ngắn hạn hoặc tổng nợ phải trả.

**Cần lấy đủ:** SHORT_TERM_LOANS_AND_FINANCE_LEASES; kỳ 2026-Q2.
**Cách chấm:** Chỉ chấm khi gold đã duyệt: Evidence-group Recall@5/@10; MRR cho câu có một nhóm bằng chứng. Chấm đúng đáp án riêng.
**Trạng thái:** Cần xác minh đơn vị/phạm vi/cơ sở kỳ. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** `16.368.916.886.521 VND` (hoặc `16.368,92 tỷ VND`).

**Tham chiếu trường nguồn đã đối chiếu trước đó:** `bsa56`. Vẫn phải khớp đúng hash file/phiên bản nguồn khi nghiệm thu.
**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q33 — Tìm đoạn bằng vector

**Câu hỏi đã sửa:** Trong bản dữ liệu clean FPT đã đóng băng, tại kỳ 2026-Q2, lợi nhuận sau thuế chưa phân phối lũy kế có giá trị gốc bao nhiêu? Phân biệt số dư lũy kế với phần chưa phân phối riêng kỳ này.

**Cần lấy đủ:** RETAINED_EARNINGS; kỳ 2026-Q2.
**Cách chấm:** Chỉ chấm khi gold đã duyệt: Evidence-group Recall@5/@10; MRR cho câu có một nhóm bằng chứng. Chấm đúng đáp án riêng.
**Trạng thái:** Cần xác minh đơn vị/phạm vi/cơ sở kỳ. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** `20.370.550.280.517 VND` (hoặc `20.370,55 tỷ VND`).

**Tham chiếu trường nguồn đã đối chiếu trước đó:** `bsa90`. Vẫn phải khớp đúng hash file/phiên bản nguồn khi nghiệm thu.
**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q34 — Tìm đoạn bằng vector

**Câu hỏi đã sửa:** Trong bản dữ liệu clean FPT đã đóng băng, doanh thu thuần bán hàng và cung cấp dịch vụ gắn nhãn kỳ 2026-Q2 có giá trị gốc bao nhiêu? Nêu nguồn đã xác nhận riêng quý hay lũy kế chưa; không tự suy từ nhãn kỳ.

**Cần lấy đủ:** NET_REVENUE; kỳ 2026-Q2.
**Cách chấm:** Chỉ chấm khi gold đã duyệt: Evidence-group Recall@5/@10; MRR cho câu có một nhóm bằng chứng. Chấm đúng đáp án riêng.
**Trạng thái:** Cần xác minh đơn vị/phạm vi/cơ sở kỳ. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** `13.788.503.461.199 VND` (hoặc `13.788,50 tỷ VND`).

**Tham chiếu trường nguồn đã đối chiếu trước đó:** `isa3`. Vẫn phải khớp đúng hash file/phiên bản nguồn khi nghiệm thu.
**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q35 — Tìm đoạn bằng vector

**Câu hỏi đã sửa:** Trong bản dữ liệu clean FPT đã đóng băng, kỳ 2026-Q2 có lợi nhuận sau thuế thuộc cổ đông công ty mẹ và lãi cơ bản trên cổ phiếu lần lượt bao nhiêu? Nêu đơn vị/cơ sở kỳ khi có bằng chứng; không dùng tổng LNST thay LNST cổ đông mẹ.

**Cần lấy đủ:** PARENT_NET_PROFIT; kỳ 2026-Q2; BASIC_EARNINGS_PER_SHARE; kỳ 2026-Q2.
**Cách chấm:** Chỉ chấm khi gold đã duyệt: Evidence-group Recall@5/@10; MRR cho câu có một nhóm bằng chứng. Chấm đúng đáp án riêng.
**Trạng thái:** Cần xác minh đơn vị/phạm vi/cơ sở kỳ. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** LNST cổ đông công ty mẹ: `2.567.587.014.434 VND` (hoặc `2.567,59 tỷ VND`); EPS cơ bản: `1.507 VND/cổ phiếu`.

**Tham chiếu trường nguồn đã đối chiếu trước đó:** `isa22; isa23`. Vẫn phải khớp đúng hash file/phiên bản nguồn khi nghiệm thu.
**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q36 — Tìm đoạn bằng vector

**Câu hỏi đã sửa:** Trong bản dữ liệu clean FPT đã đóng băng, lưu chuyển tiền thuần từ hoạt động kinh doanh gắn nhãn kỳ 2026-Q2 có giá trị gốc và dấu thế nào? Nêu riêng quý/lũy kế nếu nguồn xác nhận.

**Cần lấy đủ:** CASH_FLOW_OPERATING; kỳ 2026-Q2.
**Cách chấm:** Chỉ chấm khi gold đã duyệt: Evidence-group Recall@5/@10; MRR cho câu có một nhóm bằng chứng. Chấm đúng đáp án riêng.
**Trạng thái:** Cần xác minh đơn vị/phạm vi/cơ sở kỳ. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** `1.702.147.711.404 VND` (hoặc `1.702,15 tỷ VND`).

**Tham chiếu trường nguồn đã đối chiếu trước đó:** `cfa18`. Vẫn phải khớp đúng hash file/phiên bản nguồn khi nghiệm thu.
**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q37 — Tìm đoạn bằng vector

**Câu hỏi đã sửa:** Trong bản dữ liệu clean FPT đã đóng băng, tiền chi mua sắm và xây dựng tài sản cố định gắn nhãn kỳ 2026-Q2 có giá trị gốc, dấu dòng tiền và độ lớn khoản chi bao nhiêu? Không tự thêm tài sản dài hạn khác vào phạm vi chỉ tiêu.

**Cần lấy đủ:** PURCHASE_FIXED_ASSETS; kỳ 2026-Q2.
**Cách chấm:** Chỉ chấm khi gold đã duyệt: Evidence-group Recall@5/@10; MRR cho câu có một nhóm bằng chứng. Chấm đúng đáp án riêng.
**Trạng thái:** Cần xác minh đơn vị/phạm vi/cơ sở kỳ. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** `-747.414.308.012 VND` (hoặc đã chi `747.414.308.012 VND`, tương đương `~747,41 tỷ VND`).

**Tham chiếu trường nguồn đã đối chiếu trước đó:** `cfa19`. Vẫn phải khớp đúng hash file/phiên bản nguồn khi nghiệm thu.
**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q38 — Tìm đoạn bằng vector

**Câu hỏi đã sửa:** Theo dữ liệu nguồn tại kỳ 2026-Q2, tỷ suất sinh lời trên vốn chủ sở hữu (ROE) và biên lợi nhuận gộp của FPT có giá trị gốc bao nhiêu và được nguồn ghi theo cơ sở kỳ nào? Không mặc định các tỷ lệ chỉ tính riêng ba tháng Q2.

**Cần lấy đủ:** ROE; kỳ 2026-Q2; GROSS_MARGIN; kỳ 2026-Q2.
**Cách chấm:** Chỉ chấm khi gold đã duyệt: Evidence-group Recall@5/@10; MRR cho câu có một nhóm bằng chứng. Chấm đúng đáp án riêng.
**Trạng thái:** Cần xác minh đơn vị/phạm vi/cơ sở kỳ. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** ROE: `0,2647` (tương đương `26,47%`); Gross Margin: `0,3468` (tương đương `34,68%`).

**Tham chiếu trường nguồn đã đối chiếu trước đó:** `roe; grossMargin`. Vẫn phải khớp đúng hash file/phiên bản nguồn khi nghiệm thu.
**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q39 — Truy vấn số liệu + tính toán

**Câu hỏi đã sửa:** Lấy hai giá trị doanh thu thuần gắn nhãn 2026-Q1 và 2026-Q2 trong cùng bản clean FPT đã đóng băng. Nếu đơn vị, phạm vi và cơ sở kỳ so sánh được đã xác minh, tính chênh lệch và phần trăm biến động; nếu chưa, nêu hai số gốc và điều kiện còn thiếu, không khẳng định tăng trưởng kinh tế.

**Cần lấy đủ:** NET_REVENUE; kỳ 2026-Q1 và 2026-Q2.
**Cách chấm:** Chấm đủ dữ liệu đầu vào riêng, phép tính Decimal/SQL riêng; thiếu tập đầu vào không quy thành lỗi xếp hạng vector.
**Trạng thái:** Cần xác minh đơn vị/phạm vi/cơ sở kỳ. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** Tăng `1.308.506.254.424 VND` (tương đương `~1.308,51 tỷ VND`), đạt mức tăng trưởng `10,48%` so với quý 1/2026.

**Tham chiếu trường nguồn đã đối chiếu trước đó:** `isa3`. Vẫn phải khớp đúng hash file/phiên bản nguồn khi nghiệm thu.
**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

### Q40 — Từ chối khi thiếu bằng chứng

**Câu hỏi đã sửa:** Chỉ dựa trên bản clean FPT được đóng băng trong tập kiểm thử này, doanh thu thuần và lợi nhuận sau thuế kỳ 2026-Q4 là bao nhiêu?

**Cần lấy đủ:** Xác nhận nguồn và phạm vi đóng băng; Trả lời không đủ thông tin, không bịa con số.
**Cách chấm:** Chấm câu trả lời không bịa và nêu thiếu bằng chứng; không dùng Recall/MRR, không yêu cầu vector trả rỗng.
**Trạng thái:** Cần duyệt phạm vi thiếu dữ liệu và thử hành vi từ chối. Chưa có nhãn gold được duyệt.

**Đáp án v5 để đối chiếu, chưa duyệt lại:** `Không có thông tin / Hệ thống phải từ chối trả lời (Safe Refusal)`. Lý do: Cơ sở dữ liệu BCTC đã chốt chỉ có đến kỳ Quý 2/2026 (2026-Q2). Kỳ Quý 4/2026 chưa kết thúc và chưa phát hành báo cáo tài chính.

**Kỳ vọng đề xuất:** Nêu không đủ thông tin trong đúng nguồn/phạm vi đã chốt; không bịa số. Lý do từ chối phải dựa bằng chứng, không chỉ vì bộ đề gắn nhãn từ chối.
**Phiếu duyệt cần bổ sung:** document ID lưu DB; nhóm chunk ID đúng; content hash; locator; bằng chứng; đơn vị/cơ sở kỳ; đáp án duyệt; người/ngày duyệt.

## Các file đi kèm

Tài liệu đề cập `Golden40_V6_De_xuat.json` (câu hỏi gốc/sửa, loại kiểm thử, đáp án v5 tham khảo, điều kiện nguồn và ứng viên bằng chứng), nhưng **file này chưa có trong workspace tại lần kiểm tra 21/10/2026**. Cần nhận file và duyệt `gold_evidence_groups`/`approved_answer` trước khi chấm chính thức. Trường gold còn trống là công việc chưa duyệt, không phải bài test thất bại. Không đưa toàn bộ JSON chứa đáp án vào prompt truy vấn.
