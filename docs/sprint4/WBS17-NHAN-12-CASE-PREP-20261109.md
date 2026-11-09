# Nhân — chuẩn bị 12 câu GRAPH/BOTH còn thiếu

Ngày 09/11/2026. Lấy nguyên 12 câu từ Excel chung; không đổi câu hỏi, đáp án,
gold hoặc trạng thái chạy. Đây là yêu cầu bàn giao dữ liệu cho benchmark của
Nhân, không phải kết quả chạy, envelope nạp graph hay quyết định APPROVED.
Các kỳ vọng dưới đây vẫn là **DRAFT theo bộ test**, cần chốt với nguồn.

12 câu dùng chung **6 gói dữ liệu**: 3 nhân sự và 3 sự kiện. JSON đi kèm:
`wbs17/pending-graph-both-20261109.json`. Các trường runtime còn thiếu để `null`;
không tạo Person/Event/relation ID giả để mở khóa benchmark.

## Gói cần nhóm bàn giao

| Gói | Câu dùng chung | Quan hệ/kỳ vọng trong đề | Phần CONTENT cần thêm cho BOTH |
|---|---|---|---|
| P1 | GRAPH_04, BOTH_04 | VCB → Nguyễn Thanh Tùng, APPOINTS, Chủ tịch HĐQT, 26/07/2024 | Nguyên văn hàng bổ nhiệm trong BCTN VCB 2024, PDF trang 65 |
| P2 | GRAPH_05, BOTH_05 | ITD → Nguyễn Vĩnh Thuận, DISMISSES, Phó Chủ tịch HĐQT, 26/06/2025 | Hàng riêng của Nguyễn Hồng Minh: bổ nhiệm Phó Tổng Giám đốc 04/11/2025, cùng bảng trang 52; không gán ngày/hàng cho người bị miễn nhiệm |
| P3 | GRAPH_06, BOTH_06 | BID → Lê Ngọc Lâm, APPOINTS, Chủ tịch HĐQT, 01/07/2026 theo snapshot | Đoạn từ 12/03/2021 giữ chức Thành viên HĐQT kiêm Tổng Giám đốc; không dùng năm sinh thay bằng chứng lịch sử chức vụ |
| E1 | GRAPH_07, BOTH_07 | Event thông qua nghị quyết cổ tức → FPT, INVOLVES | 10% mệnh giá, 1.000 đồng/cổ phiếu; không khẳng định đã chi trả |
| E2 | GRAPH_08, BOTH_08 | Event đã phát hành cổ phiếu → ELC, INVOLVES | 7.700.890 cổ phiếu, trả cổ tức và tăng vốn từ nguồn vốn chủ sở hữu |
| E3 | GRAPH_09, BOTH_09 | Event phê duyệt phương án trái phiếu → BID, INVOLVES | Trái phiếu tăng vốn, riêng lẻ, quý IV/2026; không khẳng định phát hành hoàn tất |

Nhân sự: Hưng xác nhận canonical IDs/registry, Vũ hỗ trợ nguồn trích xuất;
sự kiện: Quân xác nhận Event ID, giai đoạn và participant role. Huyền bàn giao
receipt review tương ứng; owner publish bàn giao phiên và readback. Đây là
phân luồng yêu cầu theo task đã có, không gán Nhân tự sửa các module đó.

## Nguồn đã có đầu mối

Các ID sau được nối từ các câu VECTOR đã có trong cùng Excel. **Chưa replay
lại nguồn ngày 09/11 và chưa chứng minh các chunk chứa đủ mọi chi tiết BOTH.**
Chúng là đầu mối để owner kiểm tra, không tự đưa vào gold mới.

| Gói | Câu VECTOR đối chiếu | Document ID | Chunk ID gợi ý |
|---|---|---|---|
| P1 | TC_VECTOR_01 | dd94d5da-f8b1-5776-8c5e-f211d18ae26b | 8203616d-60a9-5572-8594-c012730a6169; 9b28a95a-083c-5fa1-ba74-8f9321bd6f01; b8de74c0-bde2-55a4-936f-ec16c5034c37 |
| P2 | TC_VECTOR_02 | a2c071fb-25bf-5ec4-903b-e973c623b85d | 9c58ad01-d5d9-5d7e-a2d1-eb8ee588565e |
| P3 | TC_VECTOR_03 | 7c8d45c4-6d1a-5b1e-a04e-4cd3f1e70190 | 183e7b12-084d-5bc0-8a6d-978e3aa8419f |
| E1 | TC_VECTOR_04 | bf912c6c-4857-5a04-908b-d9116b38c255 | f2c46deb-e739-502b-a6b7-4dcdae20e828 |
| E2 | TC_VECTOR_05 | a184caae-530f-5353-9b2c-abb999dad0df | 31ccb2e7-2c4c-58da-adc0-2d8df793b5cc |
| E3 | TC_VECTOR_06 | f3160868-7d46-53f4-b6d8-86de0bd09e0f | 25d8726a-722a-571d-849a-fe265e078c7d |

Extraction ID nhân sự và article ID sự kiện được giữ nguyên trong JSON. Với
News, ngày đăng lần lượt 29/10, 17/09 và 16/10/2026; đó không tự là ngày sự kiện.
E3 có kỳ dự kiến quý IV/2026, không được biến thành ngày phát hành thực tế.
Không gán trang PDF cho web/News.

## Mapping còn thiếu đã xác định cụ thể

Đã đọc hai registry local `company.registry.json` và
`company.registry.20261105.r3.json`: VCB, BID, FPT có một candidate Company ID
theo ticker; **ITD và ELC chưa có ticker mapping trong hai file này**. Điều này
không khẳng định registry triển khai của nhóm cũng thiếu. Cần owner gửi đúng
đường dẫn/phiên/hash registry đang phục vụ để đối chiếu.

Ba Company ID local gợi ý được ghi trong JSON, chưa tự điền thành mapping đã
duyệt. Cả ba Person ID, ba Event ID, relation IDs và graph version phục vụ
12 câu vẫn cần bàn giao. Không dùng ID của SourcePersonOccurrence như canonical
Person ID hoặc tự đưa 185 claims theo tài liệu vào graph chat.

## Nội dung owner cần trả cho mỗi gói

1. Commit tích hợp; registry path/hash; Company ID và Person/Event ID đã xác
   minh. Với Person phải có căn cứ nối danh tính, không gộp theo tên giống nhau.
2. Relation ID, loại/chiều cạnh, chức vụ hoặc participant role, giai đoạn sự
   kiện; chỉ rõ trường thời gian theo contract. Ngày thiếu để unknown, không
   điền published_at hoặc năm báo cáo thay ngày hiệu lực; không suy valid_to.
3. Corpus/index, graph_version_id, receipt review và receipt publish READY;
   xác nhận phiên nào adapter của chat thực sự được cấu hình đọc.
4. Document/chunk, phiên/hash nguồn, locator, quote và offsets chứng minh
   fact. BOTH cần thêm span riêng cho chi tiết đọc văn bản ở bảng đầu.
5. Readback bằng truy vấn đọc: đúng phiên, đúng endpoint, evidence; kết quả
   sau chạy lại không nhân đôi. Receipt nguồn không thay approval cả câu test.

Owner có thể điền các trường `handoff_required` trong JSON hoặc gửi receipt
tương đương có đủ trường. JSON này chỉ dùng bàn giao, không đưa vào script nạp.

## Nhân kiểm gì sau khi nhận

- Đọc phiên READY và các cạnh bằng ID cụ thể; đối chiếu chiều Company → Person
  hoặc Event → Company, role, stage và trường thời gian với nguồn.
- Replay nguồn trong transaction chỉ đọc; kiểm membership corpus/index,
  document version/hash, locator, quote và offsets nếu contract yêu cầu.
- GRAPH dùng nguyên câu Excel, không ép route bằng đáp án. BOTH phải nối
  kết quả GRAPH với CONTENT đúng công ty/tài liệu/người/sự kiện. Không dùng
  Person/Event/relation ID làm ticker hoặc lấy hàng kế bên để trả lời.
- Chốt gold chung từ bằng chứng; chỉ nâng readiness sau khi các điều kiện thật
  đã đủ. Giữ SETUP_REQUIRED/Blocked nếu thiếu một phần, không ghi SKIP thành PASS.
- Chạy B1/B2 thành run mới, cùng commit/corpus/model/cấu hình được chốt, tối
  thiểu 1 warmup và 5 lượt/profile/câu. Chốt bộ lọc tài liệu B1 tường minh trước
  lượt đo; không tự suy kỳ tài liệu từ ngày bổ nhiệm hoặc ngày đăng bài.
- Ghi route, scope, chiều/loại/ngày/phiên, bằng chứng, status và latency; Answer
  chỉ chấm khi hai pipeline Answer được bàn giao. Không gộp run mới với live02.

Nếu owner cung cấp được ít gói hơn thì Nhân kiểm và đo các gói đủ trước; không
cần chờ cả 6 gói hoặc chờ E2E của Huyền. Không sửa cấu hình hay ghi DB trong
lượt chuẩn bị này.

## Tin nhắn có thể gửi nhóm

Nhân đã tách 12 câu còn thiếu thành 6 gói trong tài liệu này. Nhờ Hưng/Vũ xác
nhận mapping và nguồn P1–P3; Quân xác nhận Event ID/stage/participant role cho
E1–E3; Huyền và owner publish gửi receipt review, phiên READY và readback.
Hai file registry local Nhân kiểm chưa có ticker ITD/ELC, nhờ xác nhận registry
đang phục vụ. Document/chunk đầu mối đã có trong bảng nên không cần dựng lại
bộ đề. Gói nào sẵn gửi trước để Nhân chạy benchmark; thiếu gì ghi rõ, không cần
tự điền ID/ngày hoặc nâng APPROVED để đủ biểu mẫu.

## Câu hỏi nguyên văn

### TC_GRAPH_04 (GRAPH, P1)

VCB bổ nhiệm ông Nguyễn Thanh Tùng làm Chủ tịch HĐQT vào ngày nào theo BCTN 2024?

### TC_GRAPH_05 (GRAPH, P2)

ITD miễn nhiệm ai ở vị trí Phó Chủ tịch HĐQT ngày 26/06/2025?

### TC_GRAPH_06 (GRAPH, P3)

Theo hồ sơ lãnh đạo BIDV được chốt trong nguồn, ai được bổ nhiệm Chủ tịch HĐQT từ 01/07/2026?

### TC_GRAPH_07 (GRAPH, E1)

Trong graph gắn bài b421f949-205d-507e-b421-a988aeafee72, sự kiện thông qua nghị quyết cổ tức liên quan doanh nghiệp nào?

### TC_GRAPH_08 (GRAPH, E2)

Sự kiện đã phát hành cổ phiếu trong bài c1d9b43c-5d30-5917-aba3-a16520fc7508 liên quan doanh nghiệp nào?

### TC_GRAPH_09 (GRAPH, E3)

Sự kiện HĐQT phê duyệt phương án trái phiếu trong bài 9cad8358-1095-590e-a3a3-1f26d4e54e6b liên quan doanh nghiệp nào?

### TC_BOTH_04 (BOTH, P1)

Tìm người được VCB bổ nhiệm Chủ tịch HĐQT ngày 26/07/2024, rồi trích nguyên văn hàng bổ nhiệm trong báo cáo.

### TC_BOTH_05 (BOTH, P2)

Tìm Phó Chủ tịch HĐQT bị ITD miễn nhiệm ngày 26/06/2025, rồi đọc cùng bảng để nêu ngày bổ nhiệm Phó Tổng Giám đốc Nguyễn Hồng Minh.

### TC_BOTH_06 (BOTH, P3)

Tìm người được BIDV bổ nhiệm Chủ tịch HĐQT từ 01/07/2026 rồi tóm tắt chức vụ ông này giữ từ 12/03/2021 trong tiểu sử.

### TC_BOTH_07 (BOTH, E1)

Từ sự kiện thông qua nghị quyết cổ tức của bài b421f949-205d-507e-b421-a988aeafee72, tìm doanh nghiệp liên quan rồi nêu tỷ lệ và số tiền trong bài.

### TC_BOTH_08 (BOTH, E2)

Từ sự kiện phát hành trong bài c1d9b43c-5d30-5917-aba3-a16520fc7508, tìm doanh nghiệp liên quan rồi nêu số cổ phiếu và mục đích.

### TC_BOTH_09 (BOTH, E3)

Từ sự kiện phê duyệt phương án trong bài 9cad8358-1095-590e-a3a3-1f26d4e54e6b, tìm doanh nghiệp rồi đọc chi tiết loại giao dịch và kỳ dự kiến.
