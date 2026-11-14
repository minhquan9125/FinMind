# WBS03 — Nhờ Hưng đối chiếu tay quan hệ BCTN

**Corpus:** `b2550a0b-c423-5c50-9b15-6fb6af12e2c6`

**Index:** `ecfbf20f-b3e0-5077-bd3e-03f0efb95e6d`
**Kết quả WBS03 ngày 30/10/2026:** đọc 20 BCTN, xác minh 17.664 chunk, xuất 8 ứng viên `PENDING`. Đây **chưa phải quan hệ đã được duyệt**.

Chào Hưng, nhờ bạn mở đúng snapshot nguồn theo `chunk_id` và kiểm tra các ca dưới đây. Với mỗi ca, vui lòng ghi: **có quan hệ hay không; hai tên pháp lý đầy đủ và canonical ID; chiều và loại quan hệ; trực tiếp hay gián tiếp; tỷ lệ/thời điểm chỉ khi nguồn nói rõ; câu chứng minh và `chunk_id`**. Nếu tên hoặc câu bị cắt ở ranh giới chunk, xem thêm đoạn liền kề cùng tài liệu và phiên nguồn. Không suy ra dữ kiện chỉ từ tên doanh nghiệp.

## Cách mở một ca trong pgAdmin

Kết nối database `finmind` trên VPS bằng pgAdmin → mở **Query Tool** → chạy SQL chỉ đọc dưới đây. Thay `b102a5c0-6c8e-54fd-bf09-f9e5234948be` bằng `chunk_id` ở bảng phía dưới. Truy vấn giới hạn đúng corpus/index, tìm bản snapshot đã ghim trong `raw_payloads`, rồi hiện tên BCTN, trang PDF, URL và **đoạn chữ nguồn** theo locator. Nó phục vụ đối chiếu tay; phép kiểm tra hash đầy đủ được thực hiện bởi Python reader WBS03/Vũ.

```sql
SELECT
    t.chunk_id,
    d.document_id,
    d.title,
    t.page_number AS pdf_page,
    d.source_url AS pdf_url,
    substring(
        (r.payload::jsonb -> 'sections'
            -> ((t.locator_json #>> '{reconstruction,section_index}')::int)
            ->> 'body')
        FROM ((t.locator_json #>> '{reconstruction,char_start}')::int + 1)
        FOR ((t.locator_json #>> '{reconstruction,char_end}')::int
           - (t.locator_json #>> '{reconstruction,char_start}')::int)
    ) AS source_text
FROM public.text_chunks AS t
JOIN public.documents AS d ON d.document_id = t.document_id
JOIN public.corpus_versions AS cv ON cv.index_version_id = t.index_version_id
JOIN public.corpus_documents AS cd
  ON cd.corpus_version_id = cv.corpus_version_id
 AND cd.document_id = d.document_id
 AND cd.document_hash = d.sha256
JOIN public.raw_payloads AS r
  ON r.source_uri = (
      'finmind:shared-source:' || t.index_version_id::text
      || ':annual_reports:' || (t.locator_json ->> 'source_id')
  )
WHERE cv.corpus_version_id = 'b2550a0b-c423-5c50-9b15-6fb6af12e2c6'::uuid
  AND d.doc_type = 'ANNUAL_REPORT'
  AND t.superseded_at IS NULL
  AND t.chunk_id = 'b102a5c0-6c8e-54fd-bf09-f9e5234948be'::uuid;
```

Với chunk ví dụ, kết quả là **TCB BCTN 2025, PDF trang 39**. Đoạn nguồn bắt đầu “Công ty con / Công Ty Cổ Phần Chứng Khoán Kỹ Thương (Techcom Securities - TCBS)”. Số **76** in ngay trong chữ là số trang trình bày của báo cáo, khác `pdf_page = 39` trong locator; để mở PDF, dùng `pdf_url` và trang PDF 39. Nếu chữ chưa đủ để quyết định, xem thêm phần còn lại của cùng trang/đoạn liền kề, không tự ghép tên bằng phỏng đoán.

## Tám ứng viên cần kiểm tra

| # | BCTN, trang | Chunk ID | Điều cần Hưng xác minh |
|---|---|---|---|
| 1 | TCB 2025, trang 39 | `b102a5c0-6c8e-54fd-bf09-f9e5234948be` | Mục “Công ty con” có xác nhận **TCB → Công ty Cổ phần Chứng khoán Kỹ Thương (TCBS)** tại kỳ này không? Hai canonical ID hiện dùng có đúng không? |
| 2 | TCB 2024, trang 32 | `b32c6e1a-7d50-5e9a-8036-9b0fe7a59590` | Xác nhận quan hệ **TCB → TCBS** cho năm 2024. So với ca 1, nguồn nói rõ thời điểm hiệu lực nào hay chỉ là bằng chứng của từng BCTN? |
| 3 | TCB 2024, trang 35 | `4ce022d2-27b0-5053-a55b-a9fafd332cb9` | **TCB → Công ty Cổ phần Quản lý Quỹ Kỹ Thương** có đúng là quan hệ công ty con không? Kiểm tra tên và canonical ID. |
| 4 | TCB 2024, trang 36 | `4690db74-eb51-595e-b467-2c8deaf4a0fa` | Ứng viên bị cắt ở “**Công ty TNHH Một thành viên Quản lý nợ và…**”. Tên đầy đủ và canonical ID là gì? Nguồn có xác nhận là công ty con của TCB không? |
| 5 | BID 2025, trang 63 | `4298445a-935f-5a25-b965-b21075f2b9f9` | Ứng viên bị cắt ở “**Tổng Công ty Cổ phần Bảo hiểm Ngân hàng Đầu tư và…**”. Xác định tên đầy đủ/ID; quan hệ với BID là công ty con hay loại khác? |
| 6 | VCB 2024, trang 19 | `f45912ed-4282-5edb-88ce-a43c11c3776b` | Ứng viên chỉ ghi “**Công ty TNHH Một thành viên…**”. Có thể xác định **duy nhất** pháp nhân từ nguồn không? Nếu không, ghi rõ là không đủ bằng chứng để dùng. |
| 7 | ELC 2024, trang 14 | `107c2ccc-3f33-5117-a521-7fed698f78a9` | Tên đầy đủ có phải **Công ty TNHH Giải pháp phần mềm ELCOM** không? Đây là công ty con **trực tiếp** của ELC? Nguồn có nêu tỷ lệ sở hữu không? |
| 8 | ELC 2024, trang 14 | `e67bc152-bd52-539e-9cde-32ef4bfca7a6` | Nguồn mới ghi **Smartek** là công ty con của **Datanova**, ELC kiểm soát gián tiếp. Xác minh tên pháp lý và ID của cả ba; nên biểu diễn `ELC → Smartek`, `Datanova → Smartek`, hay cả hai? Tỷ lệ nào được nêu rõ và thuộc cạnh nào? |

`document_id` tương ứng trong corpus mới: TCB 2025 `85deaf00-3748-5f3d-95a2-68495dc229fc`; TCB 2024 `8ec9c4e6-cd43-559a-837b-49335340f4c5`; BID 2025 `c0a80084-f786-5abe-9f16-84b1f466c118`; VCB 2024 `dd94d5da-f8b1-5776-8c5e-f211d18ae26b`; ELC 2024 `f0730a07-8ab5-548a-a3b8-e099489d0f29`.

## Hai điểm cần chốt cho contract và kiểm thử

1. **Quan hệ TCB–TCBS xuất hiện ở hai năm:** ca 1 và 2 hiện tạo cùng `relation_id` nhưng có `document_id`, `chunk_id` và bằng chứng khác nhau. Theo contract, nên lưu **một quan hệ với hai evidence** hay **hai phát biểu theo từng năm với ID khác nhau**? Cách nào giữ được lịch sử mà không tạo cạnh trùng khi WBS08 nạp cùng graph version?
2. **Ca đối chứng để kiểm tra rule:** ngoài 8 ứng viên, nhờ Hưng chọn vài đoạn chắc chắn có quan hệ mà WBS03 bỏ sót và vài đoạn chỉ cùng nhắc hai công ty nhưng **không có quan hệ**. Với mỗi đoạn, ghi `document_id`, `chunk_id`, câu nguồn và kết luận mong đợi. Có thể dùng [danh sách 25 ca cần review](WBS03-BCTN-review-queue.md) để tìm ý tưởng, **nhưng chunk ID trong danh sách đó thuộc corpus v5 cũ**, cần định vị lại đoạn tương ứng trong corpus mới trước khi gán nhãn. Bộ này giúp Nhân sửa rule và đo việc nhận đúng/bỏ đúng; 8 ứng viên hiện tại chưa đủ để kết luận độ bao phủ.

## Mẫu trả lời cho mỗi ca

| Trường | Hưng điền |
|---|---|
| Số ca; BCTN; `document_id`; `chunk_id` | |
| Có quan hệ? Loại và chiều chính xác? | |
| Tên pháp lý và canonical ID của hai đầu | |
| Trực tiếp/gián tiếp; tỷ lệ; thời điểm **nếu nguồn nêu rõ** | |
| Câu chứng minh; cần thêm chunk liền kề nào? | |
| Chỗ còn mơ hồ hoặc không đủ bằng chứng | |

Hưng giúp **đối chiếu nội dung nguồn và registry**; Huyền/WBS06 quyết định trạng thái kiểm duyệt `APPROVED`, `PENDING` hoặc `REJECTED`. Nhân chỉ dùng kết quả để sửa/kiểm thử WBS03; chưa tự ghi các ứng viên này vào Neo4j.
