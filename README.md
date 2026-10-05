Để Vector RAG chạy đúng với dữ liệu tài chính, cần kiểm tra và sửa các mục dưới đây. Theo rà soát code, có vài vấn đề về đơn vị và kỳ báo cáo; cần xử lý trước khi nạp BID vào Supabase.
Ưu tiên	Cần kiểm tra	Cách sửa
1. Đơn vị số tiền	/api/documents/json và /api/documents/import-symbol/{symbol} dùng _statement_pages() để tạo nội dung chunk. Hàm này hiện ghi giá trị VND thô mà không ghi đơn vị.	Thống nhất mọi đường ingest: số tiền thành triệu VND, ghi nhãn rõ, ví dụ TỔNG TÀI SẢN: 3.440.840.854 triệu VND.
2. Kỳ lưu chuyển tiền tệ	BCTC Q2 trình bày dòng tiền lũy kế từ 01/01 đến 30/06; JSON lại gắn nhãn 2026-Q2.	Ghi rõ basis là lũy kế 6 tháng. Nếu cần hỏi riêng dòng tiền quý 2, phải tính từ số lũy kế Q2 trừ số lũy kế Q1. Không dùng nhãn “Q2 riêng” cho số lũy kế.
3. Khác biệt số liệu	Một số giá trị JSON không khớp PDF, chẳng hạn bsb112, bsb113, isb29, cfa18.	Kiểm tra JSON thô và đúng phiên bản báo cáo crawler đã lấy. Chỉ sửa giá trị sau khi xác nhận nguồn và kỳ; không tự chọn số từ PDF khác phiên bản.
4. Ánh xạ mã chỉ tiêu	Tên map nhìn chung hợp lý nhưng vài mã nội bộ như nob66, nob69, nob70 chưa có định nghĩa rõ.	Chỉ map sang tên chuẩn khi có định nghĩa từ nguồn; nếu chưa rõ, giữ mã gốc và đánh dấu chưa xác minh.
5. Chunk không cắt mất ngữ cảnh	Dữ liệu tài chính có nhiều chỉ tiêu trong một kỳ; cần kiểm tra build_chunks() không tách số khỏi tên mã, kỳ hoặc đơn vị.	Mỗi chunk phải giữ đủ mã cổ phiếu, tên báo cáo, kỳ, basis, chỉ tiêu, giá trị và đơn vị.
6. Trùng dữ liệu khi nạp lại	Cần kiểm tra API có nhận diện tài liệu đã nạp hay có thể tạo nhiều bản/chunk trùng.	Đặt khóa chống trùng theo mã cổ phiếu + kỳ + phiên bản dữ liệu; khi cập nhật thì thay đúng bộ chunk cũ.
7. Embedding và tìm kiếm	Kiểm tra model tạo vector đúng 1024 chiều, cùng model cho lúc nạp và lúc tìm kiếm; chỉ mục dùng cosine phù hợp.	Nếu đổi model hoặc cách chuẩn hóa vector, phải tạo lại embeddings cho dữ liệu cũ trước khi tìm kiếm.


Thứ tự làm để chạy được:
1. Sửa cách tạo text để đơn vị và kỳ được ghi rõ, thống nhất giữa các endpoint ingest.
2. Sửa nhãn cash flow thành “lũy kế 6 tháng” hoặc xác nhận nguồn để phân biệt Q2 riêng.
3. Xác minh và xử lý các số liệu lệch nguồn.
4. Nạp lại BID sau khi xóa/thay bộ dữ liệu BID cũ, tránh tìm kiếm lẫn chunk cũ và mới.
5. Kiểm tra một câu hỏi mẫu như “Tổng tài sản BID tại 30/06/2026 là bao nhiêu?” để xác nhận kết quả trả về đúng số, kỳ và đơn vị.
Trong đó, mục 1 là lỗi cần sửa trực tiếp để nội dung Vector RAG không gây hiểu sai. Mục 2–4 cần làm trước khi tin kết quả tài chính.