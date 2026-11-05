# WBS03 — sửa extractor và gửi review lại N18/N30/N40

Ngày 05/11/2026. Thực hiện theo đề xuất của Hưng và các giới hạn đã đối chiếu với người dùng.
Đây là thay đổi code và proposal PENDING, không phải quyết định WBS06 hoặc lần nạp Neo4j.

## Đã thực hiện

### 1. Ngày của bảng phải đi cùng quote

`ownership_tables.py` giữ `as_of_evidence` cùng `as_of`, đưa quote ngày vào các mục dùng chung bảng, kể cả khi ngày đứng trước tiêu đề. Nhận thêm câu dẫn "Tại ngày …, … công ty con/liên doanh/liên kết …". Reset ngày, quote và trạng thái bảng khi sang trang mà không có bảng đang mở, hoặc gặp thuyết minh đánh số mới (`1.`, `2.4`, `2.4.`). Vẫn giữ ngày/quote khi tiếp tục cùng bảng sang trang kế tiếp.

Nếu rule danh sách đã nhận cặp thực thể nhưng chưa có ngày, rule bảng có thể bổ sung ngày được trích nguồn. Không ghi đè ngày tường minh của phát biểu khác. ID của ứng viên mới có thể đổi do thời gian là một phần identity; các envelope đã duyệt không bị sửa.

Test tái hiện lỗi đã thất bại trước khi sửa: ngày đứng trước tiêu đề mất quote, câu dẫn bảng không được nhận, ngày bảng khác ở trang trước bị mang sang, thuyết minh mới không reset ngày. Có thêm kiểm tra tiếp tục bảng và tiêu đề công ty con đánh số.

### 2. Registry r3 là đề xuất FTEL, chưa kích hoạt

`company.registry.20261105.r3.changes.json` có phép gộp `CMP-7159a1a0f4ea52a1ffd3` → `CMP-7097a7e10282f47ca683`; chuyển canonical name cũ, alias và ticker FOX vào ID giữ lại. `merged_ids` ghi rõ mapping, không sửa ID lịch sử trong DB hoặc envelope.

`build_registry_revision.py` hỗ trợ merge có kiểm tra: từ chối self-merge, ID thiếu, chuỗi/vòng merge, mapping không khớp, khác loại thực thể, nguồn/đích chưa verified và alias mới trùng thực thể khác. Không thay đổi base trong bộ nhớ; r2 tái lập giống trước. Bản r3 có 1.475 entity, giảm một entity so với r2.

CLI extractor và registry của person-role vẫn dùng bản hiện tại. Chỉ công cụ tạo proposal chọn r3 đề xuất. Trước khi kích hoạt, Hưng/WBS02 phải xác nhận mapping và kiểm tham chiếu trên **Neo4j VPS thực tế**, không suy từ việc cổng 7687 trên máy không mở.

Các alias CMG được Hưng đề xuất chưa thêm vào r3 này: Korea/Malaysia còn cần phân xử danh tính và nguồn. Không lấy `verified=true` làm bằng chứng tự động cho các alias mới.

### 3. Nhãn liên doanh được kiểm bằng nguồn, không bỏ qua gate

`graph_review/models.py` kiểm kiểu chuỗi của `relation_label`. Engine chỉ chấp nhận nhãn `công ty liên doanh`/`công ty liên kết` trên HAS_ASSOCIATE khi đúng cụm chữ có trong quote; nhãn sai/không có nguồn bị từ chối. Không đưa tùy ý `relation_label` vào METADATA để bỏ qua kiểm chứng.

Kiểm nhãn không chứng minh quan hệ hai đầu và không tự phê duyệt cách ánh xạ liên doanh → HAS_ASSOCIATE. Cảnh báo `WARN_EVIDENCE_INSUFFICIENT` cho việc nối tiêu đề/hàng/cột vẫn giữ; cần WBS06/WBS01 chốt quy ước. Không tự đổi enum/schema contract hoặc lớp trả lời.

### 4. Ba proposal có basis từ nguồn chọn tường minh

`backend/scripts/prepare_rejected_proposals.py` đọc ZIP review, kiểm CRC/hash, đối chiếu original ID/hash và trạng thái REJECTED trong quyết định. Chỉ bổ sung từ chunk đã chọn trong **cùng document/version**, từ chối chunk ID xung đột, thiếu cụm basis, sai loại basis hoặc đầu vào đã APPROVED. Xuất ID proposal mới, giữ thời gian/tỷ lệ/hai đầu và trạng thái PENDING; không ghi đè output có sẵn.

Đây là bước bổ sung bằng chứng cho ba ca xác định, chưa phải rule tự gán basis cho mọi quan hệ trong toàn báo cáo. Nguồn đủ basis cho 34 ca đã được review trước đó giữ nguyên trong ZIP gốc.

| Ca | Ngày giữ nguyên | Bổ sung | Còn cần review |
|---|---|---|---|
| N18 Indovina | 2025-12-31 | `accounting_basis=phương pháp vốn chủ sở hữu`, chunk `91aef6a2-2cef-5208-ad0e-ea9e2b562b48` | Quy ước liên doanh; nối bảng với đúng hai đầu |
| N30 FTEL | 2024-12-31 | `consolidation_basis=kiểm soát`, context FPT 2024 trang 161 | Hưng xác nhận r3; review bằng chứng |
| N40 FTEL | 2025-12-31 | `consolidation_basis=hợp nhất toàn bộ`, chunk `d772bc16-0492-5ac8-8a6e-f23a7ad7b86b` | Hưng xác nhận r3; đọc chính sách nối tiếp, phân biệt trạng thái 2025 với thay đổi từ 2026 |

N18/N30 chỉ còn `WARN_EVIDENCE_INSUFFICIENT` ở chẩn đoán offline. N40 còn thêm `WARN_AMBIGUOUS_FACT` vì đoạn nguồn đồng thời đề cập chuyển phương pháp trong tương lai; không tự xóa cảnh báo hoặc đặt `valid_to`.

Gói local: `backend/.tmp/WBS03_REJECTED_RESUBMIT_20261105.zip`. Mở README và `cases/N18.md`, `cases/N30.md`, `cases/N40.md`. Có originals, proposals, registry đề xuất, mapping/hash và đánh giá kỹ thuật. Gói nằm trong `.tmp`, không đi theo Git.

Chạy lại từ gốc repo với output mới:

```powershell
backend/.venv/Scripts/python.exe -X utf8 -m backend.scripts.prepare_rejected_proposals --package "C:/Users/GamingGear/Downloads/WBS06_REVIEW_NHAN_20261105.zip" --output-dir backend/.tmp/WBS03_REJECTED_RESUBMIT_rerun
```

Các kiểm tra mới là **FIXTURE trên bản lưu**, không phải xác minh nguồn LIVE mới. ZIP đầu vào có bằng chứng kiểm LIVE trước đó, nhưng không biến lượt chạy offline này thành LIVE. Chưa thấy tunnel 15433/17687 mở khi kiểm kết nối đầu lượt; cần mở lại tunnel và chạy reader thật trước khi WBS06 chốt.

## CMG — công việc còn phụ thuộc nguồn

- Giữ quyết định REJECTED của N01–N09 cho bản hiện tại. Không gọi North America/Deutschland là "REJECTED vĩnh viễn" chỉ vì chưa khớp bảng hợp nhất.
- WBS01 chuẩn bị snapshot OCR sạch **phiên mới** cho tài liệu `532597dc-7b79-5f00-99f9-d3394cba9038`, trang 88–90 và 109. Giữ snapshot/hash/locator cũ để phát lại lịch sử; không sửa text dưới cùng fingerprint.
- Sau khi có nguồn, đối chiếu **từng pháp nhân, đúng mẹ và đúng hàng** với mốc thời gian. N01 còn định danh/chiều; N07 còn loại hình Korea; N08 cần kiểm APAC/Malaysia và quan hệ trực tiếp/gián tiếp.
- Không lấy lợi ích Tập đoàn ở con chia lợi ích ở mẹ rồi tự ghi thành sở hữu trực tiếp. Không lấy ngày thành lập pháp nhân tự điền `valid_from` của quan hệ sở hữu 100%.
- Các thay đổi mẹ/ngày/loại/ID hoặc nguồn mới phải thành proposal mới, có mapping về ca bị từ chối, rồi WBS06 review lại. Không tự nâng thành APPROVED.

## Kiểm chứng và giới hạn

- 271/271 test trọng tâm extractor/registry/proposal/graph/router và kiểm nguồn đạt. Test mới theo vòng red/green; thử bỏ phép kiểm nhãn trong quote làm test tương ứng thất bại, sau đó đã khôi phục code và chạy lại cả tập test.
- Replay offline trên 20 BCTN/17.664 chunk đã lưu: 69 → 69 ứng viên; mọi ứng viên có as_of đều có quote ngày. Chỉ một ID TCB 2025 đổi do bổ sung ngày: `rel:9e97a35a4e008840693a5d46ba4feac4` → `rel:43e253eba882af1ffbb38b42688f19b7` (`as_of` từ null thành 2025-12-31). Các phiên và bản duyệt cũ giữ nguyên. Output: `backend/.tmp/wbs03-date-scope-final-replay-20261105/`. Không coi là phép đo precision/recall hoặc xác minh nguồn LIVE.
- Không đổi 34 envelope đã duyệt, 13 cạnh graph READY cũ hoặc quyết định WBS06. Không ghi PostgreSQL/Neo4j, không tự deploy registry, không nới điều kiện approve.
- Chưa thực hiện nạp 34 bản APPROVED; bước đó cần review-store receipt và đối chiếu phiên graph mới theo WBS09 như đã thống nhất.
