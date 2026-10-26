# Kiểm tra OCR bằng Gemini trên báo cáo 2024

Đầu vào: 46 trang mà bộ trích xuất báo cáo thường niên đã chuyển sang Tesseract.
Model được gọi trên ảnh trang PDF; kết quả đối chiếu với Tesseract trong OCR router.

- Có bản đọc bằng model: 35/46 trang.
- Chưa có bản đọc bằng model: 11 trang; giữ bản Tesseract.
- Có model nhưng cần rà soát: 6 trang.
- Số đọc khác Tesseract trên 9 trang; tính cả cờ của router, 11 trang có model cần đối chiếu PDF.
- Cờ trên các trang có model: {'ENGINES_DISAGREE': 6, 'NEAR_EMPTY': 7}.

| Mã | Trang cần OCR | Model đọc được | Cần đối chiếu PDF | Chưa có model |
|---|---:|---:|---:|---|
| BID | 2 | 2 | 1 | — |
| CMG | 11 | 11 | 4 | — |
| CTG | 3 | 3 | 2 | — |
| ELC | 4 | 2 | 1 | 2, 70 |
| FPT | 3 | 2 | 0 | 2 |
| ITD | 7 | 7 | 1 | — |
| MBB | 10 | 6 | 1 | 55, 68, 75, 184 |
| TCB | 5 | 1 | 0 | 1, 9, 14, 26 |
| VCB | 1 | 1 | 1 | — |

## Trang cần rà soát

- BID trang 1: NUMBER_AGREEMENT=0
- CMG trang 1: ENGINES_DISAGREE, NUMBER_AGREEMENT=0
- CMG trang 13: ENGINES_DISAGREE
- CMG trang 76: NEAR_EMPTY, ENGINES_DISAGREE
- CMG trang 77: ENGINES_DISAGREE, NUMBER_AGREEMENT=0.2
- CTG trang 1: NUMBER_AGREEMENT=0.429
- CTG trang 2: NUMBER_AGREEMENT=0
- ELC trang 2: GEMINI_FAILED
- ELC trang 70: GEMINI_FAILED
- ELC trang 71: NEAR_EMPTY, ENGINES_DISAGREE, NUMBER_AGREEMENT=0
- FPT trang 2: GEMINI_FAILED
- ITD trang 1: NUMBER_AGREEMENT=0.8
- MBB trang 2: NEAR_EMPTY, ENGINES_DISAGREE, NUMBER_AGREEMENT=0
- MBB trang 55: NEAR_EMPTY, GEMINI_FAILED
- MBB trang 68: GEMINI_FAILED
- MBB trang 75: GEMINI_FAILED
- MBB trang 184: NEAR_EMPTY, GEMINI_FAILED
- TCB trang 1: GEMINI_FAILED
- TCB trang 9: GEMINI_FAILED
- TCB trang 14: GEMINI_FAILED
- TCB trang 26: GEMINI_FAILED
- VCB trang 1: NUMBER_AGREEMENT=0.667

Model 3.8 Flash gặp lỗi 503 và giới hạn 20 lượt gọi miễn phí trong ngày.
Model 3.6 Flash giải quyết được một phần; các lượt còn lại có lỗi 503.
Model 2.5 Flash trả 404 cho tài khoản này nên không được dùng tiếp.
Báo cáo này không xác nhận toàn bộ chữ và bảng chính xác; các trang REVIEW cần đối chiếu PDF.
