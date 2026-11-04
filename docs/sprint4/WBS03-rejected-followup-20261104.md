# WBS03/WBS06 — bằng chứng bổ sung cho 10 ứng viên bị từ chối

Ngày 04/11/2026. Phạm vi: corpus BCTN `b2550a0b-c423-5c50-9b15-6fb6af12e2c6`,
index `ecfbf20f-b3e0-5077-bd3e-03f0efb95e6d`. Đây là gói **đề nghị kiểm tra lại**,
không thay quyết định `REJECTED` trong [bàn giao WBS06](wbs06/WBS06_HANDOFF_NHAN.md).
Các chunk liệt kê dưới đây đã được `PostgresSourceReader.read_current` dựng lại từ
snapshot nguồn trong một transaction PostgreSQL `READ ONLY REPEATABLE READ`, kiểm
corpus/index, locator và hash; `verification_mode=LIVE`. Điều này xác minh chữ nguồn
đã ghim, chưa xác nhận cách diễn giải quan hệ hoặc ngày hiệu lực.

## Tám ứng viên VCB

| Quan hệ | Năm | ID ứng viên | Chunk quan hệ | Chứng cứ thời gian cần xem cùng trang |
| --- | ---: | --- | --- | --- |
| VCB → VCBL, `HAS_SUBSIDIARY` | 2025 | `rel:54a63c17919c89a13b9a364669a20138` | `2ceea344-77ec-52e7-92e3-a5037a1eb64b` | `0591c75e-cfaf-5f1f-a7d9-a4c7f9133fa9`, `d5b9656b-477a-53f4-bd6d-e77879223586` |
| VCB → VCBL, `HAS_SUBSIDIARY` | 2024 | `rel:c3d36770dd3753c0b5d30a0a291b4f50` | `f45912ed-4282-5edb-88ce-a43c11c3776b` | `7db9d42c-10cf-5e2d-9514-398915ae1074`, `eefa24cd-1b3e-534d-8320-e132bf2eeb41` |
| VCB → VCBR, `HAS_SUBSIDIARY` | 2025 | `rel:f11468f41fb1cae28c0617bd7eec521f` | `4eb699ea-63f8-58c3-a0e6-55f1bb62f66c` | Hai chunk bảng VCB 2025 ở trên |
| VCB → VCBR, `HAS_SUBSIDIARY` | 2024 | `rel:a308917230b9e53c1db06a113af0f530` | `4da429da-4ebd-5fef-9fad-4054093f8eb5` | Hai chunk bảng VCB 2024 ở trên |
| VCB → VCBL, `OWNS_SHARES` | 2025 | `rel:a6e698eb7ae99ff04d7e694ffe12eb87` | `2ceea344-77ec-52e7-92e3-a5037a1eb64b` | Cùng bảng 2025; còn thiếu `holding_basis` |
| VCB → VCBL, `OWNS_SHARES` | 2024 | `rel:f25bca89fa66800b87257166d554bad9` | `f45912ed-4282-5edb-88ce-a43c11c3776b` | Cùng bảng 2024; còn thiếu `holding_basis` |
| VCB → VCBS, `OWNS_SHARES` | 2025 | `rel:b619ed16494a3f38a14729f21f1b1910` | `8b2d615a-ce16-53ae-a636-ab227e4ad934` | Cùng bảng 2025; còn thiếu `holding_basis` |
| VCB → VCBS, `OWNS_SHARES` | 2024 | `rel:deb37325f74612ded314754484380a9f` | `1f233fca-f45b-5996-a9c3-31566c16a351` | Cùng bảng 2024; còn thiếu `holding_basis` |

Trang 18 BCTN VCB 2025 (`document_id=679baa3e-b39c-5b53-be43-3cd19d738dca`)
có mục “Thông tin chung công ty con”, tiêu đề bảng chứa `31/12/2025` và các
hàng VCBS, VCBL, VCBR ghi 100%. Trang 19 BCTN VCB 2024
(`document_id=dd94d5da-f8b1-5776-8c5e-f211d18ae26b`) có cấu trúc tương tự,
tiêu đề chứa `31/12/2024`. **Cần nhìn bố cục bảng** để xác định ngày nằm trên
cột tỷ lệ sở hữu hay chỉ cột vốn đầu tư và xác định từng hàng thuộc mục công ty
con. Chữ OCR ghép các cột, nên chưa thể tự gán `as_of` cho 8 ứng viên. Ngày
trên giấy phép hoạt động/đăng ký kinh doanh trong cùng hàng **không phải** ngày
bắt đầu quan hệ. Bảng 100% cũng chưa chứng minh tỷ lệ đó là sở hữu trực tiếp
hay gián tiếp; bốn ứng viên `OWNS_SHARES` vẫn cần bằng chứng `holding_basis`
riêng. Các chunk quan hệ trong bảng trên giữ nguyên theo WBS06.

## Hai ứng viên BID và MBB

| Quan hệ | ID ứng viên / chunk quan hệ | Nguồn bổ sung đã kiểm tra | Kết luận hiện tại |
| --- | --- | --- | --- |
| BIDV → BIC, `HAS_SUBSIDIARY` | `rel:dd01697e444a009d219d8956a9b09077` / `8e2d6222-9db8-506b-9b44-500f6b356682` | BCTN BID 2025, `document_id=c0a80084-f786-5abe-9f16-84b1f466c118`, PDF trang 36, chunk `c6ba5562-5d3f-5f3f-8c2a-6233fb88e67b`: tên BIC và “Tỷ lệ sở hữu của BIDV 51,01%”. | Bổ sung ngữ cảnh nhận diện BIC; chưa thấy mốc ngày gắn rõ với quan hệ. Ngày giấy phép trong bảng là ngày giấy phép. |
| MB ↔ FPT, `COOPERATES_WITH` | `rel:023629b35242df030f87b93a34d85b58` / `f4303a40-b295-5f6b-99b8-a2ddfdb6edc9` | BCTN MBB 2025, `document_id=faf61b2a-9dba-57d4-91e4-d7eca3edb4c7`, PDF trang 77: đoạn ghi dự án kiểm kê phát thải là hợp tác MB–FPT. | Có quan hệ và phạm vi dự án, chưa có ngày bắt đầu hoặc mốc `as_of` trực tiếp cho phát biểu. Năm BCTN không thay cho mốc này. |

## Đối chiếu thêm với PDF cục bộ

Tôi đọc lớp chữ và vị trí dòng/cột của bốn PDF dưới đây. SHA256 của từng file
cục bộ khớp `ocr_standard/.../source.json`; đây là cách kiểm tra bản PDF dùng
cho OCR, **không thay thế** phép kiểm hash snapshot/chunk của reader PostgreSQL.
Trang PDF là số trang vật lý tính từ 1; một trang PDF VCB chứa hai trang in.

| PDF cục bộ | SHA256 | Trang và điều xác minh được | Điều chưa chứng minh được |
| --- | --- | --- | --- |
| `data/references/vietstock/annual_reports/files_pdf/VCB/2025/VCB_Baocaothuongnien_2025.pdf` | `1c93629bcd35e99ad19221e8af38400b53e84c154b4a9f93dcbaee83a9ebaba3` | PDF trang 18, trang in 32–33: mục “Thông tin chung công ty con” nêu VCBS, VCBL, VCBR; các hàng VCBL/VCBR có 100%. `31/12/2025` ở vùng tiêu đề bảng; các ngày 31/10/2017, 20/09/2017 và 15/09/2025 nằm trong phần giấy phép/đăng ký. | Chưa gắn chắc mốc `31/12/2025` với từng phát biểu quan hệ; không có bằng chứng rõ `holding_basis=direct/indirect`. Ngày giấy phép không phải ngày quan hệ. |
| `data/references/vietstock/annual_reports/files_pdf/VCB/2024/VCB_2024_501264.pdf` | `0a54c7e25712351cef1df5be0e8c3f121ca45577864acaf0113aab2580db1120` | PDF trang 19, trang in 34–35: cùng mục công ty con, có hàng VCBS/VCBL/VCBR và mốc `31/12/2024` ở vùng tiêu đề. | Lớp chữ PDF tách cột chưa đủ rõ để chốt `as_of` cho từng hàng hoặc sở hữu trực tiếp/gián tiếp. Ngày giấy phép trong hàng không thay thế mốc này. |
| `data/references/vietstock/annual_reports/files_pdf/BID/2025/BID_2025_542007.pdf` | `c95251ea276f8ea9138d58b4d95e45d90cfa8d341b0acabfaf9774f96d2ee586` | PDF trang 36: BIC nằm trong danh sách công ty con/liên doanh/liên kết; chunk nguồn đã ghim ghi BIDV sở hữu 51,01%. | Chưa tìm được ngày gắn trực tiếp với quan hệ BIDV–BIC; ngày giấy phép không đủ. |
| `data/references/vietstock/annual_reports/files_pdf/MBB/2025/MBB_2025_537873.pdf` | `d67772421ddeceac697de71c5a84945ae7c34779bae44d6456738844d4950521` | PDF trang 77: đoạn dự án kiểm kê phát thải ghi hợp tác MB–FPT. | Năm của chương/dự án hoặc năm BCTN không phải mốc bắt đầu hay `as_of` của hợp tác. |

Điểm “chữ bị trộn” ở VCB là hiện tượng trích chữ từ bảng nhiều cột và hai
trang in trên một trang PDF: các ô khác nhau có thể nối vào cùng dòng text.
Không có bằng chứng database lưu sai hàng hoặc hỏng dữ liệu. Sửa trực tiếp
`raw_payloads`/`text_chunks` của corpus đã ghim sẽ làm hash, locator và
`document_version` không còn khớp. Nếu nhóm muốn nâng chất lượng OCR, cần tạo
source release và index/corpus version mới rồi kiểm thử lại; **không cần sửa DB
để xử lý mười quyết định WBS06 này**.

**Đề nghị WBS06:** Xem hình/bố cục bảng VCB 2024–2025 và quyết định có đủ
căn cứ ngày cho **bốn** quan hệ công ty con hay chưa. Chỉ khi có nguồn xác
nhận, lập bản bổ sung giữ nguyên ID ứng viên và ghim thêm chunk/locator/quote
cho mốc thời gian. Với bốn cạnh sở hữu, tiếp tục tìm nguồn nêu rõ trực tiếp
hoặc gián tiếp; nếu không có thì giữ `REJECTED`. BID và MBB cũng giữ
`REJECTED` cho đến khi có mốc thời gian gắn với đúng quan hệ. Không nạp bất kỳ
ứng viên nào trong mười ca này vào graph `READY` hiện tại.
