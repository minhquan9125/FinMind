# Đề xuất ranh giới nhãn và hợp đồng consumer — DRAFT, 12/11/2026

Chưa có xác nhận của nhóm cho phần bổ sung này. Không thay nội dung hay trạng
thái của `intent-labels.v1.json` đã duyệt, không sửa gold cũ để tăng accuracy.

## Ranh giới “kế hoạch lợi nhuận”

Đề xuất gán theo mục tiêu trả lời, không chỉ vì có từ “lợi nhuận” hoặc “kế hoạch”:

| Câu | Nhãn đề xuất | Lý do |
|---|---|---|
| Theo BCTN FPT 2025, lợi nhuận mục tiêu năm 2026 là bao nhiêu? | NUMERIC | Lấy một giá trị mục tiêu; phải ghi đây là kế hoạch, không phải kết quả thực hiện. |
| Tóm tắt kế hoạch lợi nhuận và các biện pháp thực hiện trong BCTN FPT 2025. | REPORT_CONTENT | Thuật lại kế hoạch/biện pháp trong nguồn, không tự đánh giá. |
| Dựa trên số liệu các năm, kế hoạch lợi nhuận 2026 của FPT có khả thi không? | TREND | Yêu cầu nhận định; phải đối chiếu phạm vi định nghĩa TREND đã duyệt trước khi chốt. |
| Cho biết lợi nhuận mục tiêu 2026 rồi đánh giá khả năng hoàn thành dựa trên chuỗi số liệu. | MIXED (NUMERIC, TREND) | Hai đầu ra độc lập: con số và nhận định. |
| Tóm tắt kế hoạch lợi nhuận của FPT. | Chưa đủ thông tin để chốt | Cần biết tài liệu/kỳ và người dùng muốn tóm tắt nội dung hay lấy chỉ tiêu. |

Nhờ nhóm xác nhận cả trường hợp đánh giá tính khả thi có nằm trong TREND hay
cần hỏi lại/ngoài phạm vi; không tự mở rộng taxonomy đã duyệt. Sau khi chốt mới
cập nhật schema phiên bản mới và thêm cặp library/test độc lập tương ứng.

## Metadata bắt buộc ở cửa vào policy 04.2

Theo review của Hưng, consumer chặn V3 khai báo đúng nhưng mặc định cosine nếu
thiếu metadata, khiến ví dụ probability 0,71 có thể đi SEARCH/VECTOR. Đây là lỗi
contract cần Huyền sửa/kiểm chứng trên source consumer của mình. Checkout hiện
tại chưa có consumer đó; tài liệu này không phải bằng chứng đã sửa nó.

Đề nghị từ chối đầu vào thiếu/null/rỗng `ranking_policy` hoặc `score_type`, kể
cả thiếu cả hai. Không suy loại điểm từ giá trị 0–1, tên nhãn hoặc từ score=0,71.
Không gọi fallback AI khi payload hỏng contract rồi ghi đó là phân loại thành công;
cần phân biệt lỗi payload với câu hỏi không chắc chắn.

| Payload | Kết quả contract cần kiểm |
|---|---|
| Thiếu ranking_policy, dù score_type là cosine | Từ chối contract, không SEARCH |
| Thiếu score_type, dù ranking_policy là cosine | Từ chối contract, không SEARCH |
| Thiếu cả hai, score=0,71 | Từ chối contract, không mặc định cosine |
| Metadata null/rỗng/loại lạ hoặc hai khóa không khớp | Từ chối contract |
| Metadata classifier probability đúng, score=0,71 | Không dùng policy/ngưỡng cosine |
| V3/V4 decision evidence, confidence=null | Không đi qua ngưỡng 0,65/0,08 |
| Cosine hợp lệ, đúng cả hai khóa theo contract hiện tại | Mới xét ngưỡng và phạm vi công ty/kỳ |

## Bốn điểm cần hai phần cùng chốt

1. V3/V4 không đi qua ngưỡng cosine 0,65/0,08. Đổi loại điểm cần contract và
   calibration riêng; giữ policy cosine hiện có cho đầu vào cosine hợp lệ.
2. Khi `resolution.intent_label` khác nhãn đầu của `base_ranking`, giữ cả hai
   cùng lý do. Chưa có confidence đã kiểm chứng: không tự lấy nhãn nào rồi gắn
   điểm của nhãn kia. Đề xuất xử lý xác minh/hỏi lại/fallback theo contract
   thống nhất, chưa cho V3/V4 tự điều khiển tuyến bằng điểm cũ.
3. MIXED không mặc định BOTH. Chọn tuyến theo thành phần và dữ liệu cần dùng;
   hai thành phần cùng truy xuất tài liệu có thể không cần GRAPH.
4. Probability hiện chưa hiệu chỉnh; không gọi nó là “độ tin cậy” đã kiểm
   chứng. `resolution.confidence` vẫn null; reason không được đổi thành 1,0.

Hưng review logic/bằng chứng của phía Nhân; Huyền kiểm tra consumer và ca thiếu
metadata. Nhóm chốt ranh giới nhãn và hợp đồng trước khi nghiệm thu tích hợp.
