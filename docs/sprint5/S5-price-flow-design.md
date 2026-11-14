# FinMind — Thiết kế phân tích diễn biến cổ phiếu và dòng tiền

Trạng thái: người dùng chốt hướng phân tích trong cuộc hội thoại ngày 10/11/2026. Đây là quyết định thiết kế; chưa phải tính năng đã triển khai.

## Mục tiêu đã chốt

FinMind sử dụng dữ liệu lịch sử để giải thích diễn biến gần thời điểm phân tích của từng mã, có số liệu, khoảng ngày và nguồn kiểm tra lại. Giai đoạn đầu tập trung diễn biến cổ phiếu và dòng tiền. Giai đoạn sau kết hợp báo cáo tài chính và tin tức để đánh giá hoạt động, sức khỏe doanh nghiệp.

Hướng được chọn: phân tích giá–khối lượng bằng các phép tính và quy tắc giải thích rõ ràng, bổ sung giao dịch khối ngoại, so sánh thị trường và mức biến động. Đây là khung tổng hợp cho FinMind; không mặc định là mô hình dự báo xác suất tăng/giảm.

## Các hướng đã cân nhắc

| Hướng | Quyết định và lý do |
|---|---|
| Giá–khối lượng theo quy tắc, bổ sung khối ngoại và thị trường | Chọn cho giai đoạn đầu: phù hợp mục tiêu mô tả, dễ truy nguồn và tái tính |
| Wyckoff | Có thể nghiên cứu bổ sung; chưa đưa việc nhận dạng giai đoạn tích lũy/phân phối vào phạm vi đầu |
| Machine Learning dự báo | Để sau khi có yêu cầu dự báo và tiêu chí đánh giá riêng; hiện chưa chọn model hoặc huấn luyện |

## Năm phần của kết quả phân tích

| Phần | Số liệu và mục đích |
|---|---|
| Diễn biến giá | Thay đổi 1/5/20 phiên; giá đóng cửa so với trung bình 20 phiên |
| Mức độ giao dịch | Khối lượng và giá trị giao dịch so với kỳ trước hoặc bình quân trước đó |
| Giao dịch khối ngoại | Giá trị mua, bán và mua/bán ròng trong cùng khoảng |
| Tương quan thị trường | So sánh mức tăng/giảm với chỉ số tham chiếu phù hợp; nhóm ngành bổ sung sau |
| Mức biến động | Biên độ phiên; chọn ATR hoặc biến động lợi suất khi cụ thể hóa bộ chỉ tiêu |

Các cửa sổ 1/5/20 phiên là mốc phân tích ban đầu đã trình bày trong phương án được chốt. Công thức, ngưỡng diễn giải, chỉ số tham chiếu từng mã và lựa chọn cụ thể ATR/biến động lợi suất cần ghi rõ trong hợp đồng triển khai; không coi chúng đã được kiểm định bởi việc chốt hướng.

## Quy tắc diễn giải và dữ liệu

- Tách số liệu quan sát được khỏi nhận định. Nhận định phải dẫn các số liệu hỗ trợ và nêu tín hiệu mâu thuẫn khi có.
- Dữ liệu khối ngoại phải đến từ trường giao dịch mua/bán tương ứng; không suy ra từ volume hoặc màu nến. Giá trị giao dịch thực tế cũng cần nguồn riêng.
- Tính trên các phiên cùng phạm vi, công bố ngày đầu/cuối, số phiên thực tế, thời điểm dữ liệu và nguồn. So sánh với thị trường phải căn cùng ngày.
- Muốn tính thay đổi n phiên cần giá cuối và giá của n phiên trước; không nhầm n mức giá với n khoảng lợi suất. Số ngày lịch và số phiên được phân biệt.
- Phân tích cuối phiên và dữ liệu trong phiên cần được phân biệt khi thiết kế đầu vào; không trộn chúng âm thầm.
- Giữ rõ đơn vị, hệ số giá và cơ sở điều chỉnh. Sự kiện chia tách/cổ tức có thể ảnh hưởng cách diễn giải chuỗi chưa điều chỉnh.
- Thiếu dữ liệu thì ghi thiếu và giới hạn kết luận. Không điền số giả hoặc coi thiếu bằng 0. Các phép tính phải tái lập được; phần diễn giải không tự tạo số liệu hoặc nguyên nhân.
- Chưa có quyết định về giao diện, API, cơ chế cập nhật dữ liệu hoặc thang điểm tổng hợp. Chốt khung không đồng nghĩa chốt các chi tiết này.

## Liên hệ S5-WBS08.1 và hiện trạng đã kiểm tra

S5-WBS08.1 cung cấp nền dữ liệu: ngày đầu/cuối, số phiên, nguồn, chuỗi mẫu và biến động có thể truy lại. Snapshot năm 2026 đã xuất phục vụ kiểm tra dữ liệu, không phải cửa sổ cố định của báo cáo phân tích gần hiện tại.

Snapshot DB kiểm tra ngày 10/11/2026 có dữ liệu đến 29/10/2026, 10 mã, 2.012 phiên trong mẫu. Nguồn ENTRADE còn PENDING, price_scale=1000, is_adjusted=false. Có OHLCV; độ phủ giá trị giao dịch, dữ liệu khối ngoại và chỉ số tham chiếu chưa được kiểm tra đầy đủ. Luồng chart hiện dùng snapshot/runtime vnstock/KBS khác nguồn DB; cần kiểm tra tính tương thích trước khi dùng chung.

Đề xuất công cụ xuất lại của workflow ECC `hung-s5-wbs081-series` chưa đạt QA/review; không được xem là chức năng đã tích hợp. Không tự tiếp tục workflow đó trong bước ghi nhận thiết kế này.

## Tài liệu tham khảo đã tra cứu

- [Schwab — Trading Volume as a Market Indicator](https://www.schwab.com/learn/story/trading-volume-as-market-indicator): quan hệ giá và volume, giới hạn diễn giải.
- [StockCharts — Wyckoff Method](https://chartschool.stockcharts.com/table-of-contents/market-analysis/wyckoff-analysis-articles/the-wyckoff-method-a-tutorial): cách tiếp cận cung–cầu qua giá và khối lượng.
- [Fidelity — ATR](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/atr): đo mức biến động, không xác định chiều giá.

## Bước tiếp theo

Khảo sát nguồn và độ phủ từng trường, chốt bộ chỉ tiêu/công thức và hợp đồng kết quả, rồi lập WBS triển khai theo phạm vi đó. Kết quả cần được nghiệm thu bằng phép tính độc lập và các tình huống thiếu dữ liệu trước khi ghép vào luồng sử dụng.

Đã hoàn thành audit chỉ đọc ngày 10/11/2026: xem [độ sẵn sàng dữ liệu](S5-price-flow-readiness.md). Tính được chỉ tiêu lịch sử giá/volume; còn thiếu chuỗi ngày khối ngoại/giá trị giao dịch, benchmark chưa đồng bộ và cơ sở giá giữa nguồn cần đối soát. Đây là kết quả kiểm tra, chưa thay đổi hoặc triển khai khung đã chốt.
