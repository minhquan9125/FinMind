# Giao diện

`chart.html` chứa HTML/CSS/JavaScript, nến màu đặc, volume và controller polling.
Muốn nhập mã/lấy mới/auto trong phiên: mở `Mo-bieu-do.cmd` ở **thư mục cha**.
Mở trực tiếp HTML là chế độ offline; không gọi nguồn.

Tìm `this.pollMs = options.pollMs ?? 5000` để đổi thời gian chờ giữa hai phản hồi
quote. Đơn vị mili giây; lưu rồi F5 trang. Nhãn “mỗi 5 giây” cũng nằm trong file
này. Hạn mức backend nằm ở `ohlcv/live_session.py` (`spacing=5`,16credit/phút);
đổi Python cần khởi động lại server. Thời gian phản hồi nguồn có thể dài hơn.

Server vẫn phục vụ URL `/` và `/chart.html`; vị trí file thật là `web/chart.html`.
Không cần Node để sử dụng app. Node chỉ phục vụ kiểm thử.
