# WBS03 — chạy thử 25 ca BCTN đã lọc

Ngày 29/10/2026. Chạy lại **extractor hiện tại** trên 10 envelope BCTN đã xác minh nguồn trong `backend/.tmp/wbs03-live-reviewed/`: 10.098 chunk. Đầu vào và danh sách ca ở [WBS03-BCTN-review-queue.md](WBS03-BCTN-review-queue.md). Chạy hoàn toàn offline, không gọi LLM, không ghi database/Neo4j. Kết quả từng ca và `relation_id` nằm ở `backend/.tmp/wbs03-review-queue-test.json` (file local không commit).

| Nhóm | Số ca | Có ứng viên từ đúng `chunk_id` | Không có ứng viên |
| --- | ---: | ---: | ---: |
| A — có khả năng chứa quan hệ | 12 | 1 | 11 |
| B — cần ngữ cảnh/thời gian | 7 | 0 | 7 |
| C — ca đối chứng dễ nhận sai | 6 | 0 | 6 |

**A02** là ca duy nhất được xuất: ELC 2024 → “Công ty Cổ phần đầu tư Smortek (Lò công”, loại `HAS_SUBSIDIARY`, `relation_id=rel:96015f6571bd0ab1afc772bf847a4678`, trạng thái `PENDING`, đầu công ty con **chưa resolve**. Chưa thể coi là đúng cho đến khi đối chiếu tên và bằng chứng.

| Ca | Kết quả | Chẩn đoán sơ bộ |
| --- | --- | --- |
| A01 | Không có | Tên và từ “kiểm soát” bị OCR làm méo; resolver kéo cả “Địa chỉ” vào tên. |
| A02 | 1 `PENDING` | Tên Smortek bị cắt ở ranh giới chunk; cần review. |
| A03 | Không có | Bảng công ty liên kết; resolver nuốt các cột/tên kế tiếp. |
| A04 | Không có | `MUFG Bank` chưa thành Company mention; câu có thêm vế “đàm phán”. |
| A05 | Không có | Bảng cổ đông không có động từ sở hữu; MUFG không được resolver nhận ở chunk này. |
| A06 | Không có | `FPT` trong chunk vẫn unresolved và NVIDIA chưa được nhận diện; bố cục hai cột bị trộn. |
| A07 | Không có | Bảng liên kết; Synnex FPT bị resolver nuốt cùng số/cột khác. |
| A08 | Không có | MB và FPT có mention resolved, nhưng “hợp tác giữa” đứng **trước** hai tên; rule hiện chưa xử lý mẫu này. Resolver còn tạo một mention quá dài. |
| A09 | Không có | Một đoạn gồm quan hệ công ty con và liên doanh khi thành lập; cần tách từng phát biểu/thời kỳ. |
| A10 | Không có | TCBS và Techcombank được nhận diện, nhưng mẫu “TCBS – công ty con … của Ngân hàng” chưa khớp rule chiều quan hệ. |
| A11 | Không có | VFC/VCBR chưa được tách rõ khỏi bảng và chưa có hai pháp nhân đã resolve trong cùng câu. |
| A12 | Không có | Liên doanh VCBT/FELS kèm bảng tỷ lệ; cần xác nhận cách ánh xạ vào contract hợp tác. |
| B01–B07 | Đều không có | Chưa tạo quan hệ từ câu thiếu ngữ cảnh, bảng bị trộn hoặc hợp đồng có thể đã thanh lý. |
| C01–C06 | Đều không có | Chưa thấy ứng viên giả trong sáu ca đối chứng này. |

**Không được đọc “1/12” là recall hoặc “6/6” là precision:** nhóm A chỉ là *ca nghi có quan hệ*, chưa có gold do Huyền duyệt; nhóm C cũng cần reviewer xác nhận. Kết quả cho thấy rule hiện quá bảo thủ với nhiều mẫu có tiềm năng, đặc biệt A08/A10 là cơ hội sửa rule rõ ràng sau khi người review xác nhận chiều và bằng chứng. Bước tiếp theo: Huyền duyệt A/B/C; Hưng xác nhận alias/canonical ID; Vũ đối chiếu lỗi OCR/bảng. Sau đó dùng cùng 25 ca để sửa rule và đo lại, đồng thời kiểm tra có phát sinh ứng viên sai ở nhóm C không.
