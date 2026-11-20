# Budget Web Chat theo câu hỏi

Service LiveResearchService được cache ở API. Trước đây Budget đặt trên service nên giới hạn mặc định 20 lần sinh và 65.536 token cộng dồn suốt vòng đời process, ảnh hưởng mọi phiên dùng service đó.

Mỗi lần answer hiện tạo một worker nhẹ bằng shallow copy và Budget riêng. Retriever, provider và connection pool vẫn dùng chung; bộ đếm không dùng chung. Router, news, vector, market và các fallback trong cùng lượt vẫn nhận một budget. Không reset budget của lượt khác khi có truy vấn đồng thời. Kết quả answering có budget_scope=REQUEST; xem số tiêu thụ tại answering.budget, không dùng service.budget làm thống kê tổng.

Không thay giới hạn của CLI hay Budget truyền trực tiếp vào complete_retrieval. Không tăng quota Google và không thay thế rate limit theo người dùng/ngày. Lượt hỏi mới được cấp budget mới, vì vậy giới hạn mặc định không còn là hạn mức chi phí tổng của hệ thống.

Kiểm tra: 99 test đạt gồm 25 lượt nối tiếp trên cùng phiên, 25 lượt đồng thời trên service dùng chung, giới hạn trong mỗi lượt vẫn có hiệu lực và hồi quy chat/BCTN/B1. Không gọi Gemini thật trong các test này.

File bàn giao: backend/src/retrieval_orchestration/live_research.py và backend/tests/test_live_request_budget.py.
