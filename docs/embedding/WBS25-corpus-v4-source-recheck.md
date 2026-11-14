# Kiểm tra retrieval tài chính trên corpus-v4

Ngày 23/10/2026, đọc Supabase ở chế độ chỉ đọc. Corpus `33d33730-0f0a-5274-a7f8-8d32a6be07e8` (`corpus-v4-clean-mapped`, `FROZEN`) dùng index `e3725b7d-1a39-5196-b000-3496dbab388f` (`ACTIVE`). Index có 7.158 chunk hiện hành, trong đó 5.103 chunk tài chính. Corpus-v2 cũ vẫn tồn tại riêng.

## Vì sao backend cũ báo lỗi

Locator tài chính v4 dùng `db-financial-v4`, trong khi reader ở branch Nhân trước cập nhật chỉ biết đến v3. Thử tạm chấp nhận tên phiên bản trong bộ nhớ vẫn cho 5/5 hit Q31 báo `SOURCE_CHANGED`: nội dung v4 không thể dựng đúng bằng cách đọc các bảng tài chính live theo renderer cũ.

Nhánh `backup-demo` đọc lại payload nguồn gốc đã ghim trong `raw_payloads`, dùng metadata của release để dựng nội dung rồi xác minh ID, membership, fingerprint và hash. Phần đọc chỉ-read này đã được tích hợp riêng cho index v4 vào `backend/src/documents/repository.py`; các index cũ giữ đường đọc hiện có. Không đưa nguyên nhánh `backup-demo` vào vì nhánh đó đã phân kỳ và sửa cùng các file API/repository đang có thay đổi WBS20/WBS30.

## Kết quả kiểm tra

Chạy `audit_golden_v6.py` trên corpus-v4 với Q31–Q38, `top_k=5`: cả 8 câu có 5 hit/câu, **0/40 lỗi dựng nguồn**, 0 retrieval error; lọc sai công ty hoặc kỳ đều rỗng. Trước khi tích hợp reader v4, cùng lượt audit có 40/40 hit báo `UNSUPPORTED_VERSION`. Q31–Q32 trên corpus-v2 cũ vẫn có 10/10 hit báo fingerprint nguồn thay đổi; không dùng v2 để nghiệm thu v4.

Lệnh chạy lại từ gốc repo trong CMD:

```cmd
set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1
backend\.venv\Scripts\python.exe -X utf8 backend\scripts\audit_golden_v6.py --corpus-version-id 33d33730-0f0a-5274-a7f8-8d32a6be07e8 --ids Q31,Q32,Q33,Q34,Q35,Q36,Q37,Q38 --out backend\.tmp\golden-v6-corpus-v4-after-reader-port.json
```

Báo cáo chi tiết nằm trong `backend/.tmp/golden-v6-corpus-v4-after-reader-port.json` (file local được Git ignore). Thử API `/api/search/filtered` với vector đã lưu trong index v4 và phạm vi FPT/2026-Q2/FINANCIAL_STATEMENT trả HTTP 200, 5 kết quả, trace `success`. Lượt API này kiểm tra đường SQL → nguồn → response/trace, không đo chất lượng embedding theo câu hỏi. Bộ 55 test code/API/reader và bộ 53 test chunking/edge-case/API tài liệu đều qua. Bộ thứ hai cần chạy ở môi trường có quyền ghi thư mục tạm của pytest.

**Giới hạn:** 40/40 ở đây là **40 hit của 8 câu Q31–Q38 được dựng nguồn**, không phải 40 câu Golden được chấm đúng đáp án. Nhánh `backup-demo` báo 40 câu qua kiểm tra transport/nguồn ở endpoint và logic truy vấn khác; muốn so sánh chất lượng hoặc nghiệm thu đủ Golden cần chạy đúng bộ câu hỏi, điều kiện lọc và evidence được duyệt. Không suy ra đơn vị tài chính đã được xác minh chỉ từ việc hash của chunk khớp.
