# WBS03 — kiểm tra khoảng trống quan hệ BCTN (04/11/2026)

## Phạm vi và cách chạy

Chạy `extract_bctn_from_db.py` trên corpus `b2550a0b-c423-5c50-9b15-6fb6af12e2c6`
qua PostgreSQL VPS. Reader dùng transaction `READ ONLY REPEATABLE READ`, dựng lại
và xác minh 17.664 chunk của 20 BCTN. Kết quả là 23 ứng viên `PENDING`, giống
lượt chạy trước. Không ghi PostgreSQL hoặc Neo4j. JSON mỗi tài liệu nằm tại
`backend/.tmp/wbs03-candidates-20261103-gapcheck/` (Git ignore).

Sau đó chạy `audit_bctn_relation_gaps.py` offline; kết quả tại
`backend/.tmp/wbs03-gaps-20261103-gapcheck.json`. Audit nhóm 28 kiểu câu có
từ khóa quan hệ. Số câu có từ khóa **không phải** số quan hệ đúng hay số ca bị
bỏ sót; một câu có thể thuộc nhiều nhóm.

```cmd
backend\.venv\Scripts\python.exe -X utf8 backend\scripts\extract_bctn_from_db.py --corpus-version-id b2550a0b-c423-5c50-9b15-6fb6af12e2c6 --output-dir backend\.tmp\wbs03-candidates-20261103-gapcheck
backend\.venv\Scripts\python.exe -X utf8 backend\scripts\audit_bctn_relation_gaps.py --input-dir backend\.tmp\wbs03-candidates-20261103-gapcheck --out backend\.tmp\wbs03-gaps-20261103-gapcheck.json --sample-limit 8
```

Hai lệnh từ thư mục gốc repo; nếu chạy lại, chọn tên output mới vì script từ
chối ghi đè.

## Ứng viên theo BCTN

| Mã | 2024 | 2025 | Cộng |
| --- | ---: | ---: | ---: |
| VCB | 4 | 4 | 8 |
| BID | 0 | 1 | 1 |
| CTG | 0 | 0 | 0 |
| MBB | 0 | 1 | 1 |
| TCB | 3 | 2 | 5 |
| FPT | 0 | 0 | 0 |
| CMG | 0 | 0 | 0 |
| ELC | 8 | 0 | 8 |
| ITD | 0 | 0 | 0 |
| ICT | 0 | 0 | 0 |

Đây là số ứng viên extractor tạo ra, không phải số quan hệ được WBS06 duyệt.
Lô Neo4j hiện tại chỉ có 13 cạnh APPROVED: 5 từ TCB, 7 từ ELC và 1 từ
Datanova đến Smartek. Mười ứng viên VCB/BID/MBB–FPT còn lại bị WBS06 từ chối
ở lần duyệt V4 vì thiếu căn cứ thời gian; riêng bốn cạnh sở hữu VCB còn thiếu
căn cứ trực tiếp/gián tiếp. Không đổi trạng thái bằng cách chạy lại extractor.

## Ca ưu tiên đối chiếu

1. **CMG 2025, PDF trang 8, chunk
   `01b50d4b-5505-5beb-8382-6cef9197fdf2`.** Text đã xác minh có dòng
   “Công ty TNHH CMC Global … 100%”, tiếp theo là “Các công ty con của Công
   ty TNHH CMC Global …” và “Công ty TNHH CMC Châu Á Thái Bình Dương … CMC
   Global sở hữu 100% vốn góp”. Chưa thể xuất cạnh đáng tin chỉ bằng câu này:
   cần xác nhận tên pháp nhân CMC Global và CMC-APAC trong registry, xác định
   phạm vi từng hàng bảng và đối chiếu bản nguồn. Riêng issuer CMG trong DB là
   `Tập đoàn Công nghệ CMC`, trong khi registry verified hiện chỉ có tên/alias
   `CÔNG TY CỔ PHẦN TẬP ĐOÀN CÔNG NGHỆ CMC`, `Công ty cổ phần tập đoàn Công
   nghệ CMC` và `CMG`; `_issuer_entity` yêu cầu tên DB khớp duy nhất alias
   verified. Đây là một chặn cụ thể cho các rule dùng issuer CMG làm đầu cạnh.
2. **FPT 2025, PDF trang 32, chunk
   `4e9fd7a3-1992-5ccc-9b53-86487c4cdb55`.** Sơ đồ có nhãn “CÔNG TY
   CON”, “CÔNG TY LIÊN KẾT” và một hàng tên gồm FPT Software, FPT IS,
   FPT Digital, FPT Smart Cloud, Synnex FPT. Text trộn nhiều cột và tỷ lệ
   sở hữu không còn nằm chắc cùng tên; không được ghép tỷ lệ hoặc loại quan hệ
   bằng vị trí chuỗi đơn thuần. Trang 99, chunk
   `99b539f8-b645-55d0-9393-acd4a9bccee1` có nhắc FPT Telecom là “Công ty
   con trong cùng Tập đoàn”, nhưng vẫn cần kiểm tra ranh giới hàng và nguồn
   trước khi tạo ứng viên FPT → FPT Telecom. Registry có một pháp nhân FPT
   Telecom đã verified (`CMP-7159a1a0f4ea52a1ffd3`), nhưng chữ trích từ
   sơ đồ bị lẫn cột nên chưa đủ để tự gán chiều/loại quan hệ. Các tên ngắn
   “FPT Software”, “FPT Smart Cloud” và “Synnex FPT” chưa khớp duy nhất
   với alias verified trong registry hiện dùng; không tạo canonical ID mới.
3. **CTG 2025, PDF trang 8, chunk
   `ef87adef-6447-5f7c-a00a-69578f025d9c`.** Tiêu đề gộp “CÔNG TY CON VÀ
   CÔNG TY LIÊN KẾT”, không tự xác định được loại cho từng tên bên dưới. Cần
   bảng/hàng phân loại riêng; không thêm một rule gán tất cả là công ty con.
   Chunk CTG 2024 `97f6587b-b693-5d24-b99d-c3b2b6be98ff` thuộc index cũ,
   không nằm trong corpus này nên không dùng làm bằng chứng nghiệm thu.
4. **ICT 2025, PDF trang 7, chunk
   `87856d67-862d-5fce-981f-413f62e21cb3`.** Mục “Các công ty con, Công
   ty liên kết” đi kèm “Không có”. Đây là ca âm tính: extractor trả 0 ứng viên
   là phù hợp với đoạn đang xem, không phải bằng chứng rule bị thiếu.

## Bước tiếp theo

- Ưu tiên **10 ca đã trích nhưng bị từ chối**: bổ sung bằng chứng thời gian và,
  với sở hữu VCB, cơ sở trực tiếp/gián tiếp; chuyển WBS06 duyệt lại. Không tự
  sửa trạng thái hoặc nạp Neo4j.
- Với quan hệ mới, lập mẫu đối chiếu từ các chunk CMG/FPT/CTG nêu trên: hai
  pháp nhân, chiều, loại, thời gian, quote, page và locator. Đối chiếu registry
  trước khi đổi alias; sau đó thêm từng rule hẹp cùng test dương/âm.
- Chạy lại extractor sang output mới, so ID/quote với lượt 23 ứng viên, rồi
  bàn giao các ứng viên mới cho WBS06. Chỉ quan hệ APPROVED mới được nạp vào
  một graph version mới. Bản READY hiện tại là bất biến.

Chưa sửa extractor, registry, contract hoặc database trong lượt audit này.
