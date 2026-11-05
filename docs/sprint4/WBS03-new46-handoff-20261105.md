# WBS03 — bàn giao 46 ứng viên mới cho WBS06

Ngày: 05/11/2026. Trạng thái: **chờ Huyền review**, không phải quyết định phê duyệt.

## File gửi Huyền

- ZIP local: `backend/.tmp/WBS03_NEW_46_REVIEW_20261105.zip`.
- Mở `README.md` sau khi giải nén để xem mục lục; mở `cases/N01.md` đến `N46.md` để đọc từng ca.
- SHA256 ZIP: `ad103c578bd52683f78a0857d858fae5868eea5f4db21f3fa0b0920f3e84e478`.
- ZIP và thư mục sinh ra nằm trong `.tmp`, bị Git ignore. Cần gửi ZIP riêng; tài liệu này không chứa toàn bộ kết quả.

## Phạm vi và nguồn

Corpus `b2550a0b-c423-5c50-9b15-6fb6af12e2c6`, index `ecfbf20f-b3e0-5077-bd3e-03f0efb95e6d`, registry `company.registry.20261104.r2.json`.

| BCTN | Số ứng viên mới |
|---|---:|
| FPT 2024 | 10 |
| FPT 2025 | 10 |
| CTG 2024 | 8 |
| CTG 2025 | 9 |
| CMG 2024 | 1 |
| CMG 2025 | 8 |
| **Tổng** | **46** |

Đây là phần mới trong 69 ứng viên sau cải tiến rule bảng. Đã loại đủ 23 relation ID cũ; không thay quyết định 13 APPROVED/10 REJECTED hoặc graph READY hiện tại.

Dùng bản lưu các chunk thật đã được reader xác minh ở lượt trước, tại `backend/.tmp/wbs03-candidates-20261103-gapcheck/`. Chạy lại extractor trên sáu tài liệu và đối chiếu với `backend/.tmp/wbs03-ownership-guards-replay.json`. **Không đọc lại database live trong lượt đóng gói này.** Huyền cần xác minh nguồn đúng phiên qua reader trước khi quyết định.

## Nội dung gói

- `cases/`: tên và ID hai đầu, loại/chiều, tỷ lệ, thời gian, quote nguyên văn, trang, chunk ID, hash và locator; có phần xem toàn bộ chunk.
- `envelopes/`: 46 JSON theo contract 2.1.0, giữ relation ID, bằng chứng và trạng thái PENDING.
- `context/`: chunk cùng tài liệu để tìm cơ sở hợp nhất/hạch toán; chỉ là gợi ý tìm nguồn, chưa tự thêm vào evidence.
- `registry/` và `source-review.md`: registry r2, thay đổi registry và bản đối chiếu của Hưng để tham khảo.
- `review-index.json`, `manifest.json`: phạm vi, ID loại trừ, dấu vết code/input và hash file. `application_load_allowed=false` vì đây là lô PENDING mới, chưa phải gói quyết định WBS06.
- `verify_package.py`: kiểm offline bằng Python chuẩn; không đọc/ghi DB.

## Điểm cần Huyền chốt

1. Tất cả 46 ca thiếu `consolidation_basis` hoặc `accounting_basis` tương ứng khi muốn APPROVED; phải tìm nguồn và bổ sung theo WBS06, không điền mặc định.
2. Chín ca CMG chưa có ngày; N01 còn endpoint chưa resolved. Không dùng năm báo cáo thay cho ngày hiệu lực.
3. FTEL có hai canonical ID cần Hưng chốt; N29/N39 phải phân biệt sở hữu 49,52% với quyền biểu quyết 80,15%.
4. N18 Indovina có nhãn liên doanh, đang biểu diễn HAS_ASSOCIATE; cần đối chiếu quy ước contract. CMC Malay/Korea có ghi chú về công ty mẹ hoặc tên pháp nhân.
5. Trả quyết định qua WBS06: APPROVED/PENDING/REJECTED, lý do, reviewer, reviewed_at, evidence và mapping `original_candidate_id` nếu tạo proposal. Không sửa mất bản đầu vào.

## Kiểm tra đã chạy

- 46/46 envelope qua `validate_envelope()` contract 2.1.0.
- Script kiểm gói đạt: 46 ID duy nhất, toàn bộ PENDING, loại trừ 23 ID cũ, quote/hash chunk khớp cục bộ.
- Không có liên kết Markdown nội bộ bị hỏng; ZIP qua kiểm tra CRC, dung lượng 822.984 byte.
- Đây là kiểm cấu trúc và đóng gói, **không thay nghiệm thu nghiệp vụ, kiểm nguồn live hoặc phê duyệt WBS06**.

Sau khi giải nén, mở CMD trong thư mục gói và chạy:

```cmd
py -X utf8 verify_package.py
```

Không thay schema/registry, không ghi PostgreSQL/Neo4j, không commit hoặc push trong bước này.
