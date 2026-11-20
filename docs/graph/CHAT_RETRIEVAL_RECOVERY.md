# Tìm bổ sung trước khi sinh câu trả lời

Phạm vi: cơ chế dùng chung cho các mã công ty trong corpus, không có đáp án hoặc dữ kiện viết cứng theo FPT.

| Nhánh | Cách tìm bổ sung |
| --- | --- |
| BCTC | Chốt kỳ mới nhất nếu người dùng chưa nêu kỳ; tìm đúng công ty/kỳ bằng vector hoặc hybrid. Nếu không có dòng đúng chỉ tiêu và phạm vi, dùng BM25 trên các chunk cùng phạm vi rồi đọc lại nguồn. |
| Hồ sơ công ty | Nếu tìm đầu rỗng, dùng BM25 trên hồ sơ cùng công ty và corpus. |
| BCTN | Kết hợp kết quả semantic và BM25 trong đúng công ty/năm báo cáo; replay bằng chứng theo hợp đồng BCTN hiện có. |
| NEWS | Kết hợp semantic/BM25 trong corpus, giữ ngày đăng và bộ lọc nguồn; reader NEWS tiếp tục đọc các đoạn của bài đã chọn. |
| Graph/BOTH | Graph trả rỗng thì tìm văn bản nguồn tương ứng. Không tạo cạnh Neo4j mới, không tự duyệt quan hệ. Lỗi hash/replay/quyền hoặc dịch vụ không bị coi là graph rỗng. |
| Câu chưa chỉ rõ nguồn | Chọn NEWS hoặc BCTN trước; nếu mức khớp chủ đề thấp thì thử thêm một nguồn. Đây là heuristic về độ bao phủ, không phải xác nhận câu trả lời đúng. |
| Giá và phép tính | Giữ reader dữ liệu giá và phép tính xác định hiện có; không lấy giá hoặc kỳ khác để thay câu hỏi. |

## Ràng buộc

- Không đổi công ty, chỉ tiêu, năm/quý, hợp nhất/riêng lẻ, lũy kế/riêng quý, URL bài đang được hỏi hoặc nguồn được chỉ rõ.
- Tìm bổ sung không đồng nghĩa gọi Gemini thêm một lần. Bằng chứng được thu thập trước bước sinh; gate nguồn/trích dẫn hiện có vẫn quyết định có trả lời được hay không.
- Phần bổ sung BCTC/hồ sơ dùng chung ngân sách thời gian 20 giây trong một lượt retrieve. CONTENT thêm tối đa một nguồn, tối đa 20 giây. Graph rỗng thêm một lượt văn bản, tối đa min(timeout router, 20 giây).
- Giới hạn bổ sung không phải tổng SLA 20 giây cho toàn bộ câu hỏi. Tìm đầu, nạp cache, graph và sinh câu trả lời vẫn có thời gian riêng.
- Hết thời gian mà chưa tìm được không được thông báo như đã xác nhận thiếu dữ liệu.
- Chỉ xếp hạng lại; không viết/sửa bằng chứng, không ghi database, không tự tạo nội dung PDF bị thiếu.
- Trace ghi nhánh tìm, công ty, kỳ, kết quả và timeout. So sánh bằng chứng trùng dựa trên danh tính nguồn và hash; điểm xếp hạng có thể khác nhau.

## Kiểm tra

- Test ma trận 10 mã × 4 nguồn, đổi chỉ tiêu, phạm vi riêng lẻ/hợp nhất, hash sai, graph rỗng, timeout và corpus đổi.
- Probe chỉ đọc trên corpus đang phục vụ: cố tình trả rỗng ở bước hybrid, sau đó tìm BCTC/hồ sơ qua BM25 và chạy prepare_evidence. Kết quả 20/20 lượt có bằng chứng hợp lệ.
- Probe này không gọi Gemini, không chấm tính đúng của câu trả lời AI và không thay việc nghiệm thu bộ Excel.
- Script/kết quả probe: `C:/NhanhFrontend/outputs/member-tests-fix-20261119/probe_recovery_all_companies.py` và `recovery-real-source-probe.json` (ngoài Git).
