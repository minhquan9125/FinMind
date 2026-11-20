# Hồ sơ doanh nghiệp trong Web Chat — 08/11/2026

Nguyên nhân: mã công ty đứng riêng bị giao cho classifier chọn tuyến; chính sách hồ sơ ngành nghề lại chọn GRAPH/find_relationships. Ngữ cảnh nhân sự cũ và nhánh bắt chữ “tin” có thể khiến câu hỏi thông tin công ty trả về nhân sự hoặc tin tức.

Đã sửa chính sách chung: hồ sơ doanh nghiệp dùng VECTOR/COMPANY_PROFILE/find_company_profile; mã đứng riêng mặc định hồ sơ, trừ khi đang bổ sung công ty cho một câu hỏi còn thiếu phạm vi. Chuyển sang hồ sơ sẽ bỏ bộ lọc chủ đề cũ. Câu hỏi nhân sự rõ ràng tiếp tục dùng GRAPH; yêu cầu hồ sơ và nhân sự dùng BOTH với nguồn COMPANY_PROFILE cho phần nội dung. Chào hỏi được xử lý tại chỗ. Gợi ý công ty lấy danh mục dự án thay vì ba mã viết cố định.

Kiểm tra: 335 test đạt trong bộ định tuyến, chat, BCTN và an toàn liên quan. Truy xuất thật của BID, CMG, CTG, ELC, FPT, ICT, ITD, MBB, TCB, VCB đều có một bằng chứng COMPANY_PROFILE hợp lệ và đúng mã; kết quả tại outputs/company-profile-20261108/verification.json. Không gửi thêm bằng chứng sang Gemini trong lượt kiểm tra này. Chưa coi đây là nghiệm thu toàn bộ cách diễn đạt của Gemini hoặc mọi yêu cầu kết hợp.

Backend đã khởi động lại; /api/health báo research_warmup và router_warmup ready. Thử tại http://127.0.0.1:5173/research với “Thông tin công ty VCB”, “FPT”, “Ai là Chủ tịch FPT?”, “Giới thiệu FPT và ban lãnh đạo”. Nội dung hồ sơ chỉ gồm dữ kiện thực có trong corpus; không tự bổ sung lịch sử hay sản phẩm chưa có nguồn.
