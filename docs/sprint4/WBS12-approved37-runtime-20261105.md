# Nạp bổ sung N18/N30/N40 và nối router — 05/11/2026

Người dùng yêu cầu tìm cách xử lý ba envelope còn thiếu, nạp và nối runtime. Đã nạp bổ sung 3 cạnh vào phiên `96cc8e0d-f78e-49d0-83ac-56c53245c1ed`, batch `approved3-live-d00f44efea03`, trạng thái READY. Cùng phiên 34 cạnh trước, đủ **37/37 ca mới được chấp nhận**. Các phiên cũ không bị sửa.

## Nguồn quyết định và cách dựng bản nhập

Không tìm thấy ba file envelope xuất riêng của reviewer tại máy. Đã dùng đúng proposal N18/N30/N40 đã gửi và biên bản `BAN_GIAO_REVIEW_NHAN_20261105 (1).md`, kiểm hash proposal, đối chiếu ID được biên bản chấp nhận, rồi thẩm định lại nguồn LIVE theo yêu cầu người dùng.

Bản nhập dùng reviewer `Codex-live-revalidation-on-user-request` và ID mới có tiền tố `review-import:`. Manifest giữ mapping từ ID ứng viên gốc → proposal → ID reviewer ghi trong biên bản → ID nhập mới. **Không tuyên bố đây là bản xuất gốc hoặc byte-equivalent với file reviewer chưa cung cấp, không ký thay Huyền/Hưng.**

N40 bổ sung các chunk FPT 2025 trang 176, gồm phần tiếp nối chính sách áp dụng từ năm tài chính 2026. Quote được chọn thành các đoạn nguyên văn riêng để phân biệt dữ kiện hợp nhất năm 2025 với việc chuyển phương pháp năm 2026; full chunk gốc vẫn được lưu. Không suy `valid_to`. Ngày, hai đầu, tỷ lệ và loại quan hệ của ba proposal giữ nguyên. N18 giữ `relation_label="công ty liên doanh"`; không chuyển nghĩa nghiệp vụ thành công ty liên kết.

`PostgresSourceReader` kiểm LIVE trong transaction READ ONLY REPEATABLE READ. Cả ba bản kiểm không có ERR_, chỉ còn WARN_EVIDENCE_INSUFFICIENT cho nối hàng bảng; đã kiểm thủ công trong phạm vi nguồn và quyết định chấp nhận từng ca của biên bản. Không nới gate hoặc xóa cảnh báo máy.

## Nạp và đối chiếu

- 3 cạnh, 4 thực thể; hợp nhất alias trước khi chuẩn bị batch.
- Đối chiếu toàn bộ ID, chiều, thuộc tính, thời gian, evidence và batch hash trước publish và sau READY.
- Chạy lại cùng batch là no-op. Fingerprint các phiên cũ trước/sau không đổi.
- Script độc lập `verify_sprint4_graph.py`: 3/3 cạnh, `passed=true`, `errors=[]`.
- Kiểm graph đích không có tham chiếu entity ID FTEL bị gộp `CMP-7159a1a0f4ea52a1ffd3`; không xóa hoặc di trú dữ liệu lịch sử.

Receipt, envelope và mapping local: `backend/.tmp/wbs08-approved3-live-import-20261105/`. Biên bản nguồn được giữ nguyên cùng hash trong manifest. Các file `.tmp` không đi theo Git.

## Runtime router

Đã bổ sung hai trường Settings `sprint4_graph_versions`, `sprint4_company_registry`; API router đọc cả cấu hình `.env` thay vì chỉ nhận biến được export từ terminal. Shell environment vẫn ưu tiên; không tự chọn phiên graph mới nhất.

Cấu hình local `.env` và `backend/.env` đã được lưu:

- `HYBRID_ROUTER_MODE=live`.
- Các phiên: `s4-bctn-b2550a0b-v4-20261102`, `95260e20-ea3f-4d76-9ae5-185356cd437d`, `96cc8e0d-f78e-49d0-83ac-56c53245c1ed`.
- Registry r3 đã chốt mapping FTEL trong phạm vi dữ liệu review; không sửa r1/r2 hoặc entity lịch sử.
- Kết nối Neo4j dùng cấu hình VPS đã có, qua tunnel 17687. Cấu hình trước được sao lưu local trong `.tmp` bị Git ignore; không đưa mật khẩu vào tài liệu hoặc commit.

Đã mở server kiểm thử riêng cổng 8012, dùng classifier production và DB/Neo4j thật, tắt collector/warmup trong riêng tiến trình thử. Kết quả HTTP `/api/hybrid-router/run`:

| Ca | Scope | HTTP / route / status | Cạnh mới | Evidence có xác minh nguồn |
|---|---|---|---|---|
| N30 | FPT 2024 | 200 / GRAPH / OK | Có | Có, 59 lượt evidence trong kết quả |
| N40 | FPT 2025 | 200 / GRAPH / OK | Có | Có, 54 lượt evidence trong kết quả |
| N18 | CTG 2025 | 200 / GRAPH / OK | Có, giữ nhãn liên doanh | Có, 47 lượt evidence trong kết quả |

Số evidence là lượt tham chiếu trong toàn kết quả, không phải số nguồn độc lập. API là đầu ra retrieval, chưa chứng nhận nội dung trả lời văn xuôi hoặc E2E giao diện. Server 8012 đã được dừng sau thử; không dừng ứng dụng của người dùng. Backend chạy lại theo launcher thường sẽ nhận cấu hình mới; cần giữ tunnel mở.

Hồi quy cuối: **276/276 test đạt**, gồm ba test mới cho cấu hình từ `.env`, mapping registry và adapter nhận đúng scope. Test mới thất bại trên code cũ rồi đạt sau sửa. Pytest chạy với thư mục tạm riêng vì sandbox Windows gây WinError 5 cho tmp_path; không bỏ test hoặc hạ kiểm tra.

## Review store — phần còn cần người xác nhận

Chưa ghi `public.graph_review_results`/`graph_review_audit`. Đây là bảng audit yêu cầu Principal có quyền ứng dụng phù hợp và ADMINISTRATOR để xác nhận cảnh báo thủ công. Kết nối DB `finmind_nhan` không tự chứng minh danh tính/quyền của một tài khoản ứng dụng; chưa xác định được tài khoản người dùng để ghi audit. Không dựng actor giả, mượn tài khoản người khác hoặc tự cấp quyền để hoàn tất số liệu.

Do đó đây là kết quả writer WBS08 + router LIVE đã kiểm, **chưa phải nghiệm thu WBS09 qua review store**. Gói nguồn và mapping đã sẵn sàng cho bước đồng bộ qua tài khoản được phép. N40 có hồ sơ kiểm đoạn nối tiếp riêng; không dùng bản proposal cũ thay bản nhập hiện tại.

Chín ca CMG vẫn ở ngoài graph. Không thay đổi quyết định của đợt 23 ứng viên cũ.
