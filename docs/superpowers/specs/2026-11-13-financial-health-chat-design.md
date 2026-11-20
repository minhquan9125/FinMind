# Thiết kế ngắn: đưa tình hình tài chính (BCTC đã xác minh) vào chat — 13/11/2026

User duyệt ngày 13/11 ("làm đi"). Thay đổi nhỏ, theo đúng mẫu đã có của `PRICE_TREND`.

## Mục đích
Với câu hỏi phân tích một mã (`MARKET_ANALYSIS`), chatbot có thêm một bằng chứng "tình hình tài chính" cạnh xu hướng giá. Bằng chứng gồm các chỉ số từ BCTC đã xác minh, kèm hyperlink tới PDF BCTC (tên tài liệu và số trang) để hiện dưới câu trả lời.

## Cách làm (đã chọn)
- `backend/src/financial/health_db.py`: thêm `get_financial_health(pool, symbol)`.
  - Đọc DB chỉ đọc qua `fetch_health_records` cho cả nhóm 10 mã (cần cho phần so với nhóm).
  - Tính bằng `build_report` sẵn có.
  - Trả về: kỳ, các chỉ số của mã, so với trung vị nhóm, và danh sách trích dẫn lấy từ `citation_for` (chỉ số đã xác minh mới có link).
- `backend/src/financial/health_passage.py` (mới, hàm thuần): sinh đoạn văn bằng chứng từ kết quả trên. Đoạn văn do code viết, không do AI viết.
- `backend/src/b1_answering/evidence/market_contract.py`: `feed_item` nhận thêm `kind='FINANCIAL_HEALTH'`, `provider='finmind_db'`; kiểm hợp lệ, `locator.url` và `title` từ trích dẫn đầu tiên.
- `backend/src/retrieval_orchestration/market_research.py`: thêm tham số `health_reader` giống `trend_reader`. Lỗi đọc thì bỏ khối này và chat vẫn trả lời như cũ.
- `backend/src/api/routers/research_chat.py`: nối `health_reader`.
- `backend/src/retrieval_orchestration/live_research.py`: `citation_title` coi `FINANCIAL_HEALTH` là trích dẫn có tiêu đề riêng.
- `backend/src/b1_answering/evidence/grounded.py`: thêm 1 câu vào prompt MARKET_ANALYSIS: chỉ nêu chỉ số có trong bằng chứng; chỉ số "chưa đủ dữ liệu đã xác minh" phải nói đúng như vậy; không tự kết luận mạnh/yếu vượt quá bằng chứng; không khuyến nghị.

## Không làm
Điểm tổng hợp mạnh/yếu; router mới hay ngưỡng ý định của Huyền và Nhân; giao diện mới.

## Test
- hợp đồng `feed_item` cho loại mới;
- đoạn văn sinh đúng: chỉ số chưa xác minh nói "chưa đủ dữ liệu đã xác minh";
- `health_reader` lỗi thì phân tích vẫn trả lời;
- chỉ số chưa xác minh không có link.
