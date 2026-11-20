# WBS19 — Kiểm tra chunker với dữ liệu clean ngày 20/10/2026

## Cập nhật sau khi sửa năm lỗi

Đã sửa đủ năm lỗi của lượt kiểm tra ban đầu:

1. Tiêu đề mới không tự nhận mọi số là triệu VND.
2. Dòng có đơn vị trống hoặc SOURCE_NATIVE ghi rõ “đơn vị chưa xác minh”.
3. Cùng report_id nhưng period_code khác nhau: báo lỗi, không dựng chunk.
4. Cùng report_id nhưng symbol khác nhau: báo lỗi nêu báo cáo và hai mã công ty.
5. observation_id trùng trong đầu vào, kể cả khác nhóm/báo cáo: báo lỗi nêu mã trùng; không tự bỏ dòng hoặc cộng số.

Phần 4 đã chạy riêng: 9 kiểm tra đạt. Sau phần 5, bộ hồi quy gồm
`test_db_chunking.py`, `test_db_chunking_sources.py`, `test_chunk_reconstruction.py`,
`test_clean_financial_chunk_edge_cases.py`, `test_chunking.py`: **87 passed**.
Bao gồm đổi thứ tự dòng, trùng dòng giống hệt hoặc khác giá trị, hai công ty ở
hai báo cáo riêng, cùng mã chỉ tiêu ở nhiều kỳ và dựng lại chunk tài chính v1/v2/v3.

Không ghi Supabase, không sửa số liệu nguồn hoặc tái tạo vector. Kiểm tra hợp lệ
không làm đổi nội dung/ID của đầu vào hợp lệ; các phiên bản dựng chữ cũ được giữ
để đọc chunk đã lưu. Kết quả FPT và số chunk ở phần dưới thuộc lượt khảo sát
ban đầu, chưa phải kết quả chạy lại toàn bộ file FPT bằng bản dựng mới.

Các phần tiếp theo giữ lại kết quả khảo sát trước khi sửa để đối chiếu.

## Phạm vi

Kiểm tra đầu vào JSON FinancialCleaner và bộ tạo chunk từ các dòng tài chính
sau khi nhập vào các bảng ERD. Không upload PDF, không gọi provider/embedding,
không kết nối hoặc ghi Supabase, không sửa code chunker. Mẫu tổng hợp chỉ tồn tại
trong bộ test và thư mục tạm của pytest; file clean người dùng cung cấp giữ nguyên.

Bộ hồi quy cũ được chạy riêng; kết quả của nhánh upload JSON cũ không được
đánh đồng với kiểm thử JSON FinancialCleaner.

## File clean FPT thực tế

Nguồn: `tai_chinh_clean.json` do người dùng cung cấp. SHA-256:
`bc1e71ab499081bfd1e94107d414a6a12920c3febec4e56ea4300a1955468fa7`.

| Nội dung | Kết quả |
| --- | --- |
| Báo cáo theo kỳ | 42 |
| Giá trị chỉ tiêu | 6.690 |
| Chunk tạo trong bộ nhớ | 669 |
| Kiểm tra đủ mã dòng, không thiếu/lặp | Đạt |
| Dựng lại nội dung từ locator và so hash | Đạt cho toàn bộ chunk |
| Chạy lại cho cùng ID/nội dung/locator | Đạt |
| Chunk vượt 130 từ trong file FPT này | 0 |
| Hash file nguồn sau khi thử | Giữ nguyên |

Độ phủ/khớp hash chỉ xác nhận giữ đúng nội dung được bộ dựng tạo ra; không
chứng nhận đơn vị, kỳ riêng quý/TTM hoặc độ chính xác hiển thị đã đúng nghiệp vụ.

## Mẫu khó: 17 ca, 12 đạt và 5 chưa đạt

| Tình huống | Số ca | Kết quả và ý nghĩa |
| --- | --- | --- |
| JSON clean nhỏ qua bộ đọc thật | 1 | Đạt; giá trị giữ nguyên, locator dựng lại đúng |
| Tên chỉ tiêu dài 600 từ | 1 | Đạt việc giữ nguyên dòng; chunk vượt 130 từ theo ngoại lệ một dòng không được cắt |
| Thiếu kỳ, sai quý, trùng mã chỉ tiêu trong clean, mã nguồn không khớp mã chuẩn | 4 | Bộ đọc clean từ chối được |
| Một báo cáo 1.200 chỉ tiêu | 1 | Không mất/lặp dòng; mọi chunk trong giới hạn 130 từ; kiểm tra dựng lại chunk đầu/giữa/cuối |
| Kỳ có 75, 70 hoặc 1 chỉ tiêu; có kỳ nhiều nhóm báo cáo | 1 | Không trộn báo cáo/nhóm, phủ đủ từng dòng |
| Đảo thứ tự chỉ tiêu và thứ tự báo cáo | 1 | Nội dung và ID từng báo cáo ổn định |
| Thiếu tên chỉ tiêu nhưng còn mã | 1 | Dùng mã làm nhãn thay thế |
| Giá trị null ở bộ dựng dòng | 1 | Ghi rõ không có dữ liệu, không biến thành số 0 |
| Giá trị bằng 0 và âm | 1 | Không bị loại bỏ hoặc đổi dấu |
| Đơn vị SOURCE_NATIVE | 1 | Chưa đạt: tiêu đề vẫn ghi triệu VND |
| Hai dòng cùng report_id nhưng khác kỳ | 1 | Chưa đạt: bộ dựng chưa từ chối, lấy kỳ từ dòng đầu |
| Hai dòng cùng report_id nhưng khác công ty | 1 | Chưa đạt: bộ dựng chưa từ chối, lấy công ty từ dòng đầu |
| Hai dòng trùng observation_id tại đầu vào bộ dựng | 1 | Chưa đạt: bộ dựng chưa có kiểm tra chặn trùng ID |
| Thiếu đơn vị ở dòng | 1 | Chưa đạt: chưa ghi rõ đơn vị chưa xác minh |

Ba ca mâu thuẫn kỳ/công ty và trùng observation_id là kiểm tra phòng vệ của
bộ dựng với dữ liệu tổng hợp cố ý sai. Chúng không chứng minh database hiện tại
có dữ liệu sai; database và importer có các ràng buộc riêng. File FPT thực tế
không phát hiện mất/lặp dòng trong phép kiểm tra này.

## Hồi quy có sẵn

45 ca: 44 đạt, 1 chưa đạt. Ca chưa đạt đã được ghi nhận trước lượt kiểm tra này:
`test_financial_json_to_pages_statement_drops_none_values` mong nhãn `isa1:`
nhưng code trả `ISA1 (ISA1):`. Cần chốt định dạng mong đợi trước khi sửa
test hoặc formatter, không mặc định thay assertion để làm test xanh.

Tổng hai bộ: **62 ca, 56 đạt và 6 chưa đạt**. Phép thử FPT thật được ghi nhận
riêng, không cộng giả thành một số lượng test pytest.

## Cách chạy lại mẫu khó

Chạy từ gốc repo:

```powershell
.\.venv\Scripts\python.exe -B -m pytest backend/tests/test_clean_financial_chunk_edge_cases.py -q --tb=short
```

Test mới cố ý giữ các yêu cầu chưa đáp ứng dưới dạng FAIL, không dùng xfail
hoặc đổi code ứng dụng trong lượt rà soát. Không nên báo bộ test đạt toàn bộ
hoặc nghiệm thu WBS19 chỉ từ kết quả chia đủ dòng FPT.

## Các sửa đổi cần làm tiếp

1. Bỏ tiêu đề đơn vị chung không đúng; dòng chưa xác minh đơn vị phải ghi rõ.
2. Thêm kiểm tra metadata đồng nhất trong một báo cáo và ID dòng không trùng
   trước khi tạo nội dung. Báo lỗi rõ ràng, không tự sửa hoặc gộp số liệu sai.
3. Thực hiện yêu cầu Decimal/4 chữ số thập phân trong định dạng hiển thị bằng
   một thay đổi có phiên bản, kiểm tra tác động hash/locator cũ trước khi triển khai.
4. Giải quyết test hồi quy về nhãn JSON và chạy lại các ca chịu ảnh hưởng.

Chưa thực hiện các sửa đổi trên, chưa tạo lại chunk/vector và chưa cập nhật DB.
