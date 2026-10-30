# WBS03 — 25 chunk BCTN để nhóm gán nhãn

Lọc ngày 29/10/2026 từ **20 envelope BCTN đã kiểm chứng** trong corpus frozen `a5338f75-5894-5b8a-bf94-0a6da7c26ced`. Đây là **danh sách cần review, không phải gold đã duyệt**. Chữ trích giữ theo chunk đã index, kể cả lỗi nhận dạng. Mỗi dòng có thể mở bằng `chunk_id` trong `backend/.tmp/wbs03-live-reviewed/<document_id>.candidates.json`; trường `locator.page` là trang PDF theo snapshot. Không đọc/ghi database để tạo danh sách này.

Người review điền cho mỗi ca: **có quan hệ hay không**, loại, `subject` → `object` (hoặc hai đầu đối xứng), canonical ID nếu chắc, thời điểm/tỷ lệ nếu chính câu nguồn xác nhận, trích đoạn chứng minh, và `APPROVED`/`PENDING`/`REJECTED`. Với lỗi OCR/bảng, đối chiếu snapshot nguồn theo locator; không tự sửa chữ trong chunk. Nếu đoạn cắt mất đầu/cuối, kiểm tra chunk liền kề của **cùng document/version**.

## A. Có khả năng chứa quan hệ — cần xác minh (12)

| # | BCTN, trang | `chunk_id` | Dấu hiệu trong text | Cần Huyền/Hưng chốt |
| --- | --- | --- | --- | --- |
| A01 | ELC 2024, 14 | `bdfae5e0-8def-571b-96e5-d381f81c1613` | “công ty con kiểm soút trực tiếp Công ty TNHH Giỏi phóp phần mềm ELCOM … Tỷ lệ sở hữu: 100%” | Tên pháp nhân đúng, quan hệ ELC → công ty con, và 100% gắn đúng dòng nào? OCR lỗi. |
| A02 | ELC 2024, 14 | `331eb5e5-4661-5fae-a372-b0da0c9dc2fc` | “Các công ty con kiểm soát gián tiếp Công ty Cổ phần đầu tư Smortek (Lò công” | Tên/đầu quan hệ, dấu ngoặc và phần tiếp ở chunk sau. Đây là ứng viên `PENDING` hiện có. |
| A03 | ELC 2024, 68 | `ce7034a4-9543-5c93-bf30-1a77879f6afc` | Bảng “Công ty CP Công nghệ VFT Công ty liên kết” | Có đúng là ELC → VFT `HAS_ASSOCIATE` không? Resolver đang gộp nhiều cột. |
| A04 | CTG 2024, 120 | `3e45919b-def0-55e3-b3f9-ace62f12022b` | “Hợp tác với MUFG Bank, triển khai đàm phán với các ĐCTC quốc tế …” | Tách vế hợp tác đã xảy ra khỏi vế đàm phán; xác nhận canonical ID MUFG. |
| A05 | CTG 2024, 63 | `01f164c3-c285-5b73-b98e-fba1902a1166` | Bảng cổ đông: “MUFG Bank 1.059.477.261 19,73%” | Có thể suy ra MUFG → CTG `OWNS_SHARES` tại mốc nào? Xem tiêu đề bảng và canonical ID. |
| A06 | FPT 2024, 15 | `99a2b97d-e947-5d74-ae74-26707458eb73` | “FPT và NVIDIA ký kết hợp tác chiến lược …” | FPT ↔ NVIDIA; cần kiểm tra ranh giới câu bị hai cột trộn và phạm vi hợp tác. |
| A07 | FPT 2025, 215 | `64e80193-4ba4-598c-b11f-bc13fc94d45c` | Bảng bên liên quan: “Công ty Cổ phần Synnex FPT Công ty liên kết” | FPT → Synnex FPT `HAS_ASSOCIATE`? Xác nhận đúng hàng và tên pháp nhân. |
| A08 | MBB 2025, 77 | `53ca40f1-b435-5639-873f-145e4e672589` | “dự án hợp tác giữa Ngân hàng TMCP Quân đội (MB) và Tập đoàn FPT …” | MB ↔ FPT `COOPERATES_WITH`; kiểm tra hai canonical ID và trích đúng vế. |
| A09 | MBB 2024, 48 | `32a0bb6c-974f-58db-844e-8455b5156da2` | “MCredit … Mối quan hệ Công ty con … hợp tác liên doanh giữa Ngân hàng TMCP Quân đội và Ngân hàng SBI Shinsei Bank” | Tách quan hệ công ty con khỏi hợp tác/liên doanh lịch sử; xác minh pháp nhân MCredit. |
| A10 | TCB 2024, 43 | `c6f53d48-c2c7-5b05-bd41-aafa2994aa27` | “TCBS – công ty con môi giới chứng khoán của Ngân hàng” | Techcombank → TCBS `HAS_SUBSIDIARY`? Xác nhận “Ngân hàng” quy chiếu đến ai và tên đầy đủ TCBS. |
| A11 | VCB 2024, 19 | `84f611e5-99e8-5720-a510-4fdf7a94b8d5` | “VFC là công ty con do Vietcombank sở hữu 100% vốn”; đoạn cùng trang nhắc VCBR | Xác minh VFC/VCBR là hai pháp nhân riêng, tỷ lệ 100% cho đúng từng dòng. |
| A12 | VCB 2024, 19 | `5564981f-fbe9-5d97-b14c-5766245e839c` | “VCBT là công ty liên doanh giữa Vietcombank và Công ty FELS Property Holdings Pte, Ltd. … 70:30” | Contract `COOPERATES_WITH` có phù hợp “liên doanh” không; 70:30 thuộc đúng hai bên? |

## B. Ngữ cảnh, thời gian hoặc ranh giới còn mơ hồ (7)

| # | BCTN, trang | `chunk_id` | Dấu hiệu trong text | Cần xác minh |
| --- | --- | --- | --- | --- |
| B01 | ELC 2024, 53 | `03d08caa-5ec4-563c-88ad-5bb3c616bbd2` | Elcom và Thăng Long Xanh ký hợp tác đầu tư, nêu thời hạn đến 2028 | Xem B02 cùng trang trước khi coi quan hệ còn hiệu lực. |
| B02 | ELC 2024, 53 | `54faabe7-d444-510a-98f8-b777488fc7a7` | “Elcom và … Thăng Long Xanh ký Biên bản thanh lý hợp đồng hợp tác đầu tư” | Ngày/thời điểm thanh lý, quan hệ quá khứ; đoạn sau nói **hợp đồng khác** với Thanh Trì. |
| B03 | ELC 2024, 42 | `1c6197fb-7b50-5852-bf79-0e6421958314` | Bảng danh sách công ty con bị dính tên với địa chỉ, ngành và tỷ lệ | Xác định ranh giới từng hàng; không lấy `100%` cho pháp nhân sai. |
| B04 | CTG 2024, 8 | `97f6587b-b693-5d24-b99d-c3b2b6be98ff` | Tiêu đề chung “CÔNG TY CON VÀ CÔNG TY LIÊN KẾT” rồi nhiều tên | Không tự gán mọi tên là công ty con; tìm nơi phân loại riêng. |
| B05 | CTG 2024, 56 | `1993dd92-1491-5679-9181-1c3fdf25c558` | “TỶ LỆ SỞ HỮU CỦA VIETINBANK 73,37%”, trang nói VBI | Tên VBI nằm ở chunk/trang kề nào; tỷ lệ có gắn chắc với VBI không? |
| B06 | FPT 2024, 28 | `042f7055-a563-508b-b2b8-41340271d793` | Sơ đồ “CÔNG TY LIÊN KẾT … CÔNG TY CON … FPT Software FPT IS … Synnex FPT” | Bố cục bị trộn; chưa biết tên nào ở nhánh nào. |
| B07 | ELC 2024, 61 | `7b62c079-af88-525b-abe9-98cec1ad7b50` | Góp vốn hợp tác kinh doanh của Đông Đô; mục đích mua phần vốn góp VFT | Phân biệt Đông Đô ↔ ELC hợp tác với quan hệ sở hữu VFT **mới là mục đích**, chưa chắc đã xảy ra. |

## C. Ca đối chứng để chống tạo quan hệ giả (6)

| # | BCTN, trang | `chunk_id` | Dấu hiệu trong text | Kỳ vọng cần reviewer xác nhận |
| --- | --- | --- | --- | --- |
| C01 | CTG 2024, 27 | `3995bafd-00fe-5d2d-9ab0-d83ca8c39ea1` | “VietinBank tôn trọng, hợp tác và gắn kết” | Từ “hợp tác” mô tả văn hóa, không nêu đối tác pháp nhân cụ thể. |
| C02 | ELC 2024, 13 | `c2e2367b-cc63-545c-b568-7c68b5203531` | “hợp tác với đối tác và khách hàng” | Đối tác không định danh: không tạo cạnh Company–Company. |
| C03 | VCB 2025, 84 | `1150b289-4925-5f2c-aadb-21805eb20379` | “đơn vị được đầu tư không phải là công ty con, công ty liên kết …” | Phủ định/định nghĩa kế toán, không phải quan hệ cụ thể. |
| C04 | ELC 2024, 29 | `44ba958b-4f61-50dd-9678-a5d010cf69d2` | “Thông qua chấm dứt hợp tác đầu tư …” | Không tạo quan hệ hợp tác đang hiệu lực từ câu chấm dứt. |
| C05 | FPT 2024, 15 | `708e34ad-49f5-5fe5-b6ff-bf8f35360ed6` | “FPT hợp tác cùng Aitomatic và Tokyo Electron bố ra mắt hai Nhà máy AI … cho ra mắt SemiKong” | Hai cột bị trộn: kiểm tra xem câu có thực sự nói hợp tác với **cả hai** hay không. |
| C06 | CTG 2025, 59 | `9e587136-9799-50d8-a134-e2743d8f749a` | “Công ty hoạt ộng … tại thời ½iểm … 10.886 tỷ ồng” | Lỗi chữ/định lượng, không tự suy ra tên hay quan hệ chỉ từ tiêu đề “công ty con, liên kết”. |

## Document ID để truy lại snapshot

| BCTN | `document_id` |
| --- | --- |
| ELC 2024 | `0be7ae10-6a32-5b37-9247-db09708bfe11` |
| CTG 2024 | `1718b73f-ddf8-5382-b3e8-641ee71c49a4` |
| CTG 2025 | `47d6c083-3e25-5eb9-88da-f7f3e5976582` |
| FPT 2024 | `44869767-9c49-5478-a6e1-d637cac349ad` |
| FPT 2025 | `5b3b613c-42bd-595e-8c6e-d7f93549bdf3` |
| MBB 2024 | `86438bd5-930e-550d-8491-9f9dc1a87fd5` |
| MBB 2025 | `4ad1c7c5-4931-5375-8835-392b0430cc28` |
| TCB 2024 | `bab87659-c501-5ec2-b600-495dc664b599` |
| VCB 2024 | `ebfbeace-1531-50f0-99e2-1d7aef5fcbbc` |
| VCB 2025 | `847c18d7-6694-530b-8555-76cd2540a6d7` |

**Lưu ý:** các nhãn A/B/C chỉ là mức ưu tiên review. Đáp án gold chỉ hình thành khi người phụ trách xác minh nguồn, loại và chiều quan hệ. Không dùng bảng này làm test “pass” trước bước duyệt.
