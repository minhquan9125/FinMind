# Lịch tự cập nhật 2026

Kiểm chứng ngày 06/10/2026. `calendar.live.json` là whitelist ngày giao dịch được
suy ra từ lịch thứ Hai–thứ Sáu, trừ ngày nghỉ chính thức. Không dùng lịch fixture.
Ngày làm bù thứ Bảy 10/01 và 22/08 không tổ chức giao dịch.

- [HNX: lịch nghỉ năm 2026](https://www.gov.hnx.vn/vi-vn/chi-tiet-lich-nghi-gd-60021971.html?_page=1),
  03/12/2025, thông báo 5305, căn cứ VNX 1403/SGDVN-THHC ngày 28/11/2025:
  01/01; 16–20/02; 27/04; 30/04–01/05; 31/08–02/09.
- [HNX: bổ sung nghỉ 02/01](https://www.hnx.vn/vi-vn/chi-tiet-lich-nghi-gd-60022084.html?_page=1),
  25/12/2025, căn cứ VNX 1517/SGDVN-THHC; các mục còn lại không thay đổi.
- [HOSE: thông báo 2410 bổ sung Tết Dương lịch toàn thị trường](https://staticfile.hsx.vn/Uploads/UploadDocuments/2437411/20251225_Thong%20bao%20%20ve%20%20viec%20cap%20nhat%20lich%20nghi%20giao%20dich%20Tet%20Duong%20lich%202026%20toan%20thi%20truong.pdf),
  25/12/2025, VNX 1517; đối chiếu thông báo HOSE 2294 ngày 09/12/2025.
- [SSI: quy định HOSE](https://www.ssi.com.vn/en/individual-customer/transaction-regulation-on-hsx):
  thứ Hai–thứ Sáu trừ nghỉ lễ; ATO 09:00–09:15, liên tục 09:15–11:30 và
  13:00–14:30, ATC 14:30–14:45. Tự cập nhật nến giá chỉ chạy đến 14:45;
  không kéo dài theo phiên thỏa thuận đến 15:00.
- [HNX: hỏi đáp](https://upcom.hnx.vn/vi-vn/hoi-dap.html): HNX bắt đầu 09:00,
  liên tục đến 14:30, ATC đến 14:45; UPCOM 09:00–15:00, nghỉ trưa 11:30–13:00.
- [VNDIRECT: HNX](https://support.vndirect.com.vn/hc/vi/articles/360002241873-Quy-%C4%91%E1%BB%8Bnh-giao-d%E1%BB%8Bch-t%E1%BA%A1i-s%C3%A0n-HNX):
  PLO 14:45–15:00. Chỉ lấy bảng điện, không gửi lệnh giao dịch.

Mốc cuối whitelist là 31/12/2026. Ngoài phạm vi hoặc thiếu/hỏng lịch, chỉ cho lấy
thủ công. Trước năm mới phải cập nhật lịch từ thông báo chính thức mới; không tự
suy đoán lịch Tết. Thông báo nghỉ đột xuất cần cập nhật whitelist/override.

Đơn vị quote được kiểm chứng trực tiếp từ vnstock 4.0.9 KBS:
`explorer/kbs/trading.py:price_board` không chia giá; `explorer/kbs/quote.py`
chia OHLC cổ phiếu cho 1000. Live áp dụng cùng divisor, lưu receipt nguyên bản
trong `data/stocks/<MÃ>/live.json`. TD là ngày phiên của nguồn; fetched_at là giờ lấy,
không phải thời điểm khớp lệnh. Basis giá/volume vẫn ghi unknown. Bảng điện được
poll 5 giây sau mỗi phản hồi, không bảo đảm độ trễ thực của nguồn.
