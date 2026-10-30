# WBS03 — audit các câu quan hệ BCTN bị bỏ qua

Ngày 29/10/2026. Đầu vào là 20 JSON đã xác minh nguồn ở `backend/.tmp/wbs03-live-reviewed/`: 15.398 chunk BCTN, 1 ứng viên `PENDING`. Audit chạy **offline trên JSON**, không kết nối hay ghi database. Lệnh chạy lại:

```powershell
backend/.venv/Scripts/python.exe -X utf8 backend/scripts/audit_bctn_relation_gaps.py --input-dir backend/.tmp/wbs03-live-reviewed --out backend/.tmp/wbs03-relation-gap-audit.json
```

Script đếm **câu có từ khóa**, không đếm quan hệ đúng. Một câu có thể được tính vào nhiều nhóm. `resolved mention` chỉ phản ánh trạng thái do resolver trả về, chưa bảo đảm đó là tên doanh nghiệp hợp lý; ví dụ `HĐQT`, `Quỹ`, hoặc `Công ty Cổ phần` cũng có thể xuất hiện. Những số dưới đây **không phải precision/recall**.

| Từ khóa | Câu có từ khóa | Bị chặn do phủ định/dự kiến/điều kiện/lịch sử | Không có mention Company | Chỉ mention chưa resolve |
| --- | ---: | ---: | ---: | ---: |
| Công ty con | 850 | 186 | 325 | 55 |
| Công ty liên kết | 185 | 33 | 92 | 8 |
| Sở hữu/nắm giữ | 1.423 | 360 | 613 | 93 |
| Hợp tác/liên doanh | 782 | 132 | 350 | 84 |

Các cột cuối chỉ tính câu **không** bị nhóm từ ngữ chặn. Chi tiết có `document_id`, `chunk_id`, đoạn trích và mention trong `backend/.tmp/wbs03-relation-gap-audit.json` (file local không commit).

## Ca cụ thể cần kiểm tra

| Chunk | Điều thấy trong text đã index | Vì sao chưa xuất quan hệ | Việc tiếp theo |
| --- | --- | --- | --- |
| ELC 2024 `bdfae5e0-8def-571b-96e5-d381f81c1613` | “công ty con kiểm soút trực tiếp Công ty TNHH Giỏi phóp phần mềm ELCOM ... Tỷ lệ sở hữu: 100%” | OCR làm méo `kiểm soát`, tên doanh nghiệp bị resolver kéo thêm `Địa chỉ`. | Vũ xác minh tên và ranh giới text/locator; Hưng bổ sung alias nếu đúng. Sau đó test rule ngữ cảnh công ty phát hành và tỷ lệ trong cùng mục. |
| ELC 2024 `ce7034a4-9543-5c93-bf30-1a77879f6afc` | Bảng “Công ty CP Công nghệ VFT — Công ty liên kết”. | Resolver nuốt cả các cột/kể cả tên công ty kế tiếp vào một mention; dạng bảng không theo mẫu câu hai công ty. | Đối chiếu một hàng bảng bằng nguồn snapshot; dùng issuer ELC chỉ khi hàng và cột `Mối quan hệ` rõ. |
| CTG 2024 `97f6587b-b693-5d24-b99d-c3b2b6be98ff` | Tiêu đề “CÔNG TY CON VÀ CÔNG TY LIÊN KẾT”, dưới đó là nhiều tên. | Tiêu đề gộp hai loại; không xác định từng tên là con hay liên kết chỉ từ đoạn này. | Tìm trang/bảng có phân loại riêng trước khi tạo quan hệ. Không suy ra loại từ tiêu đề gộp. |
| ELC 2024 `03d08caa-5ec4-563c-88ad-5bb3c616bbd2` | Có thỏa thuận hợp tác đầu tư giữa Elcom và Thăng Long Xanh, nêu thời hạn đến 2028. | Resolver tạo mention quá dài nuốt cả hai tên; đoạn tiếp theo `54faabe7-...` nói thanh lý hợp đồng. | Xác minh thời điểm hiệu lực/thanh lý theo snapshot trước khi tạo ứng viên hợp tác hiện hành. |
| CTG 2024 `3e45919b-def0-55e3-b3f9-ace62f12022b` | “Hợp tác với MUFG Bank, triển khai đàm phán ...”. | `MUFG Bank` chưa được resolver đưa thành Company; câu còn chứa hành động đàm phán khác, cần tách đúng vế. | Hưng xác minh pháp nhân/alias; sau đó chỉ gắn quan hệ với vế “Hợp tác với MUFG Bank”. |

## Kết luận kỹ thuật

Ba nút thắt nổi bật là OCR/bố cục bảng làm hỏng ranh giới tên; registry/resolver chưa nhận đúng một số pháp nhân; và rule hiện chỉ xử lý câu có hai mention rõ ràng hoặc một mẫu ngữ cảnh công ty con rất hẹp. **Chưa sửa rule trích xuất sau audit**: các mẫu trên chưa có nhãn đã duyệt và có ca hợp đồng đã thanh lý, nên mở rule ngay có thể tạo quan hệ sai. Bước an toàn tiếp theo là Huyền/Vũ xác minh 20–30 đoạn có `chunk_id` và đáp án mong đợi; Hưng xác minh các alias; rồi dùng chính tập này để sửa rule từng mẫu và đo cả ca đúng lẫn ca sai. Trạng thái WBS03 vẫn là đang làm/review, chưa đủ bằng chứng để nghiệm thu độ bao phủ.
