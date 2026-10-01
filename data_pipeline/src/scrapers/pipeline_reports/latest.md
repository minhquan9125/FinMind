# Báo cáo chạy thu thập tin

Thời gian: 2026-10-01T09:12:57.852432+00:00 — mã: VIC, VJC
Kết quả: ok; hạn mức 10 bài mỗi nguồn/phạm vi.

- Nhóm đủ hạn mức và không lỗi: 6/6
- Bài hợp lệ trong lượt chạy (gồm bài đã lưu): 60
- Lượt bài thêm mới vào JSON hôm nay: 41
- File dữ liệu được ghi: 6; file mới tạo: 4
- Cross-check: ok
- Record cross-check thành công: 100; check: 8; uncheck: 92
- Phân tích uncheck: ok
- Bài uncheck được phân tích (URL duy nhất): 91
- Cặp ứng viên khác cách viết: 3; số bài uncheck liên quan: 6
- Cặp cùng tiêu đề: 0

Check là độ giống văn bản >80%. Ứng viên cùng sự kiện cần đọc lại; phân tích không tự đổi marker.
Record có thể lặp giữa ngày/mã. Các chỉ số cross-check và phân tích chỉ thuộc phạm vi lượt chạy.

## Thu thập từng nguồn/phạm vi

| Phạm vi | Nguồn   | Hợp lệ/hạn mức |  Lỗi | Thêm mới | Ghi file |
| ------- | ------- | -------------: | ---: | -------: | -------- |
| market  | cafef   |          10/10 |    0 |        0 | có       |
| VIC     | cafef   |          10/10 |    0 |       10 | có       |
| VJC     | cafef   |          10/10 |    0 |       10 | có       |
| market  | fireant |          10/10 |    0 |        1 | có       |
| VIC     | fireant |          10/10 |    0 |       10 | có       |
| VJC     | fireant |          10/10 |    0 |       10 | có       |

## Dữ liệu hiện có theo từng thư mục (mọi ngày)

| Thư mục                     | File JSON | File mới lượt này | Record | Check | Uncheck | Chưa marker |
| --------------------------- | --------: | ----------------: | -----: | ----: | ------: | ----------: |
| tin_tuc_theo_ma/CTR/cafef   |         1 |                 0 |     10 |     0 |      10 |           0 |
| tin_tuc_theo_ma/CTR/fireant |         1 |                 0 |     10 |     0 |      10 |           0 |
| tin_tuc_theo_ma/FPT/cafef   |         1 |                 0 |     10 |     0 |      10 |           0 |
| tin_tuc_theo_ma/FPT/fireant |         1 |                 0 |     10 |     0 |      10 |           0 |
| tin_tuc_theo_ma/HPG/cafef   |         1 |                 0 |     10 |     1 |       9 |           0 |
| tin_tuc_theo_ma/HPG/fireant |         1 |                 0 |     10 |     1 |       9 |           0 |
| tin_tuc_theo_ma/TPB/cafef   |         1 |                 0 |     10 |     1 |       9 |           0 |
| tin_tuc_theo_ma/TPB/fireant |         1 |                 0 |     10 |     1 |       9 |           0 |
| tin_tuc_theo_ma/VCB/cafef   |         1 |                 0 |     10 |     0 |      10 |           0 |
| tin_tuc_theo_ma/VCB/fireant |         1 |                 0 |     10 |     0 |      10 |           0 |
| tin_tuc_theo_ma/VIC/cafef   |         1 |                 1 |     10 |     0 |      10 |           0 |
| tin_tuc_theo_ma/VIC/fireant |         1 |                 1 |     10 |     0 |      10 |           0 |
| tin_tuc_theo_ma/VJC/cafef   |         1 |                 1 |     10 |     1 |       9 |           0 |
| tin_tuc_theo_ma/VJC/fireant |         1 |                 1 |     10 |     1 |       9 |           0 |
| tin_tuc_chung/cafef         |         2 |                 0 |     25 |     3 |      22 |           0 |
| tin_tuc_chung/fireant       |         2 |                 0 |     35 |     3 |      32 |           0 |

Bằng chứng ghép cặp: `events.md` và `events.json` cạnh báo cáo này.
