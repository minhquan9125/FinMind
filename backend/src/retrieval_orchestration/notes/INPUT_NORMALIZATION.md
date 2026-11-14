# Chuẩn hóa câu nhập và ngày tra giá

Phiên bản cấu hình `vi-user-input-v1`, cập nhật 24/10/2026. Chạy trong chat LIVE hiện có; không gọi thêm Gemini hoặc đổi nguồn dữ liệu. Khởi động lại backend sau khi cập nhật code/cấu hình.

## Cơ chế chung

`raw câu hỏi → normalize_user_text → nhận diện intent/ngữ cảnh → retrieval hoặc market feed → B1`.

File `config/input_aliases.json` khai báo các nhóm viết tắt: câu hỏi/giao tiếp, phủ định, thời gian, mã chứng khoán và chỉ tiêu tài chính. Có thể thêm alias rõ nghĩa và từ vào `telex_vocabulary` mà không sửa parser; cấu hình được cache trong tiến trình nên cần restart. `contextual_aliases` ghi các nghĩa có thể có, còn điều kiện lựa chọn nằm trong `input_normalization.py`.

Không phân biệt câu có dấu và không dấu ở bước hiểu intent hiện có. Bước mới xử lý từng từ Telex chưa được bộ gõ chuyển: `aa/aw/ee/oo/ow/uw/uow/dd` và phím thanh `s/f/r/x/j` ở cuối hoặc sau nguyên âm. Chỉ nhận kết quả thuộc vốn từ miền ứng dụng; không tự sửa mọi từ lạ. Một câu có thể trộn dấu, không dấu, viết tắt và Telex. Không chạy chuẩn hóa lên evidence, số liệu nguồn, claims hoặc quotes.

Ví dụ `giaf FPT hoom qua laf bn`, `giá FPT hoom qua là bnhieu` cùng được hiểu là hỏi giá FPT hôm qua. Những câu như `loij nhuaanj sau thuees FPT quy4/2025 laf bn` và `tooms tawts tin tuwcs FPT hoom nay` đi qua cùng lớp chuẩn hóa. Các nhãn ngày viết dính như `ngafy15`, `thg9`, `nam2025` được tách khi rõ là nhãn lịch.

## Bảo vệ dữ liệu và nghĩa

- Mã viết hoa, mã nằm ở vị trí mã, mã đang được hỏi làm rõ được giữ nguyên. `LAF` hoặc `giá laf hôm nay` là mã; `FPT laf bn` có thể chuẩn hóa `laf` thành `la`.
- Giữ URL HTTP/HTTPS (kể cả scheme viết hoa), email, identifier chứa `_`, ngày/số tiền và suffix số lượng như `50k`, `57 tr`, `2 b`. Không xóa hoặc đổi giá trị số. Không cắt câu nếu alias khiến chuỗi quá dài: nếu kết quả vượt8000 ký tự thì giữ nguyên đầu vào.
- `cp`: cổ phiếu trong ngữ cảnh giá/mã, chi phí trước bán hàng/quản lý/lãi/thuế; `hn`: hôm nay khi tra giá/tin, Hà Nội sau ở/tại/TP/UBND. `dt`, `dk`, `bh`, `tr` không được mở rộng toàn cục khi thiếu căn cứ. Ví dụ `ko đk` là không được; `dk doanh nghiệp` là đăng ký doanh nghiệp.
- Từ tài chính tiếng Anh phổ biến và từ chưa xác định được giữ lại. Vốn từ/alias có giới hạn; không bảo đảm nhận mọi tiếng lóng hoặc lỗi chính tả tùy ý. Không tự chọn chỉ tiêu, mã, số liệu mới chỉ vì đoán cách viết.

JSON lịch sử lưu đúng câu người dùng gõ. Parser và Gemini nhận dạng đã chuẩn hóa khi cần, còn bản thân nguồn/quote vẫn nguyên văn. Không thay đổi nơi lưu lịch sử sang Supabase.

## Ngày rút gọn trong ngữ cảnh giá

`market_dates.py` quản lý phần ngày/tháng/năm chờ, riêng với tài chính theo quý/năm:

- Đã hỏi giá hôm qua và biết `23/10/2026`, tiếp `còn ngày15` → `15/10/2026`; `ngày15/9` → `15/09/2026`. Giá trả luôn ghi đầy đủ ngày để thấy phần được kế thừa.
- Hỏi `giá FPT ngày15` mà chưa có tháng/năm rõ ràng → chỉ hỏi tháng/năm, giữ mã và ngày15; `tháng10 năm2026` hoàn tất yêu cầu.
- Chỉ nói `năm2025` sau tra giá → hỏi ngày/tháng cụ thể năm2025, không tự chọn một ngày và không bật menu chỉ tiêu tài chính. Nếu đang chờ năm cho một ngày đã cung cấp thì bổ sung đúng phần năm.
- Ngày không tồn tại không được lăn sang tháng khác; future không lấy giá. Vẫn dùng giá đóng cửa đúng bar ngày được chọn, không tự lấy phiên trước thay thế.
- Chọn số `1` trong menu mã vẫn là chọn mã, không bị hiểu là ngày1. State giá có `anchor_day` từ snapshot khi câu đầu chỉ hỏi giá hiện tại.
- Có thể phục hồi một số phiên cũ bị mất chủ đề (`source_type` trống, không có metric/pending metric) từ kết quả giá trước cùng mã khi user tiếp tục bằng ngày. Không ghi đè câu BCTC/NEWS đang hoạt động hoặc đổi công ty.

Các yêu cầu ngày thiếu/sai trong PRICE không hiện ví dụ quý/tài sản. `_clarification_state` tính cả market request để ghi nhận tiến triển khi user bổ sung tháng/năm. `/moi`, đổi sang câu tài chính hoặc tin vẫn giữ hành vi đã kiểm thử.

## Kiểm thử và giới hạn

`backend/tests/test_user_input.py` gồm tình huống trộn cả câu, bảng alias, ma trận phím thanh Telex sinh từ các từ miền ứng dụng, identifiers, dạng mơ hồ, ngày rút gọn, chọn menu, sửa ngày, phục hồi phiên cũ và SessionStore lưu/mở lại nguyên câu nhập. Có kiểm thử service lấy đúng hai bar ngày khác nhau từ nguồn giả lập, không gọi Gemini. Ma trận sinh không tương đương cam kết hỗ trợ mọi câu tiếng Việt.

Không có thay đổi frontend, SDK/crawler, Supabase, token/timeout/budget hoặc endpoint. Nguồn thị trường vẫn có các giới hạn lịch sử/cache/quota đã mô tả trong `MARKET_CHAT_CONTRACT.md`. Chưa kiểm thử browser/authE2E cho thay đổi này.
