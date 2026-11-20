# Báo cáo chất lượng JSON BCTN

- Phương pháp: pypdf cho trang có lớp chữ; Tesseract cho 46 trang cần OCR.
- Bản ghi nguồn: 10; PDF kê khai: 11; PDF đã xử lý: 10.
- Kết quả: 1 đạt không cảnh báo, 10 cần rà soát, 0 lỗi kiểm tra.
- Tổng trang: 1252; trang chưa đọc được chữ sau OCR: 1.

| Mã | Năm | PDF | Trang | Có chữ | Thiếu chữ | Độ phủ | Trạng thái | Lỗi | Cảnh báo |
|---|---:|---|---:|---:|---:|---:|---|---|---|
| BID | 2024 | BID_Baocaothuongnien_2024.pdf | 0 | 0 | 0 | — | PARTIAL | Không | MANIFEST_PDF_NOT_LOCAL |
| BID | 2024 | Bao_cao_thuong_nien_BIDV_2024.FNL.pdf | 91 | 91 | 0 | 100.0% | PARTIAL | Không | TESSERACT_TEXT_REQUIRES_MANUAL_REVIEW |
| CMG | 2024 | CMG_2024_511722.pdf | 77 | 77 | 0 | 100.0% | PARTIAL | Không | TESSERACT_TEXT_REQUIRES_MANUAL_REVIEW |
| CTG | 2024 | CTG_2024_495896.pdf | 186 | 186 | 0 | 100.0% | PARTIAL | Không | TESSERACT_TEXT_REQUIRES_MANUAL_REVIEW |
| ELC | 2024 | ELC_2024_500811.pdf | 139 | 139 | 0 | 100.0% | PARTIAL | Không | TESSERACT_TEXT_REQUIRES_MANUAL_REVIEW |
| FPT | 2024 | FPT_2024_498332.pdf | 215 | 215 | 0 | 100.0% | PARTIAL | Không | TESSERACT_TEXT_REQUIRES_MANUAL_REVIEW |
| ICT | 2024 | ICT_2024_501210.pdf | 61 | 61 | 0 | 100.0% | PASS | Không | Không |
| ITD | 2024 | ITD_2024_509309.pdf | 46 | 46 | 0 | 100.0% | PARTIAL | Không | TESSERACT_TEXT_REQUIRES_MANUAL_REVIEW |
| MBB | 2024 | MBB_2024_502187.pdf | 184 | 183 | 1 | 99.46% | PARTIAL | Không | TESSERACT_TEXT_REQUIRES_MANUAL_REVIEW |
| TCB | 2024 | TCB_2024_499236.pdf | 146 | 146 | 0 | 100.0% | PARTIAL | Không | TESSERACT_TEXT_REQUIRES_MANUAL_REVIEW |
| VCB | 2024 | VCB_2024_501264.pdf | 107 | 107 | 0 | 100.0% | PARTIAL | Không | TESSERACT_TEXT_REQUIRES_MANUAL_REVIEW |

## Ghi chú

`PARTIAL` nghĩa là cần rà soát nội dung OCR, trang chưa đọc được chữ, hoặc đường dẫn PDF kê khai chưa có tệp cục bộ.
`FAIL` nghĩa là lỗi cấu trúc, metadata, hash nguồn hoặc khai báo OCR; cần xử lý trước khi nhập corpus.
`MANIFEST_PDF_NOT_LOCAL` chỉ áp dụng cho đường dẫn PDF cụ thể trong manifest; không có nghĩa mọi PDF của mã đó đều thiếu.
Kiểm tra này xác nhận tính toàn vẹn cấu trúc và nguồn, không bảo đảm bảng/đoạn văn trích xuất đúng thứ tự hoặc nội dung đã được người kiểm duyệt xác nhận.
