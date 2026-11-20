# Bổ sung yêu cầu giao diện — dùng frontend đã có

User 20/10 yêu cầu dùng frontend hiện có, không tạo frontend mới. Tài liệu này **thay thế phần mô tả shell/layout ResearchChat trong WEB_CHAT_CONTRACT.md**; hợp đồng HTTP và chatApi giữ nguyên.

ResearchPage.jsx hiện có Sidebar, header, hai tab Hỏi FinMind/Bảng so sánh, nút Lịch sử/Nghiên cứu mới và comparison DataTable. Coordinator sẽ gắn panel vào đúng vị trí tab copilot và giữ nguyên Sidebar/header/compare, bỏ copilot mock và composer mock. Worker KHÔNG sửa ResearchPage.jsx và KHÔNG tạo app/router/sidebar/header/page shell mới.

`ResearchChat.jsx` default component là **panel nhúng** trong trang cũ, props:
- `historyOpen` boolean: mở Drawer lịch sử; `onHistoryClose()` đóng.
- `resetKey` integer: thay đổi (> initial value) thì bắt đầu hội thoại mới (không tự xóa file).
- `onHistoryCount(number)`, `onBusyChange(boolean)` là các setter ổn định từ parent để header hiện count/disable nút.

Panel dùng useAuth để lấy user/isLoading; không chứa Sidebar, navigation hay auth profile riêng. Có thể dùng useSearchParams từ router chỉ prefill question. Dùng Drawer từ ../../shared/ui/index.js với props open/title/onClose (đã có). Nội dung là bubbles tất cả lượt chat, context summary, badge dữ liệu mẫu và composer có label "Câu hỏi", button "Gửi". Cùng Tailwind xanh/trắng/slate hiện tại. Panel `flex min-h-0 flex-1 flex-col`, vùng messages scroll flex1 và composer cuối. Min-height không tràn trang/mobile. Header của panel không lặp header ResearchPage.

Lịch sử tải qua listSessions, Drawer hiển thị preview/turns/date, button mỗi phiên ghi "Mở và tiếp tục" gọi resumeSession, tạo file con. Nút "Tải lại lịch sử" khi lỗi. Tránh tên key JSX trùng. New resetKey clear session ID/transcript, gửi đầu tiên create lazy; không tự POST create trong mount hoặc StrictMode (tránh tạo phiên trống). Cho phép xem rỗng khi chưa đăng nhập với link /login, composer disabled. sessionStorage giữ activeID theo user.id, mount GET restore, cleanup/stale guard khi unmount/user đổi; không hiện transcript của user trước dù một render chuyển user. Không tự gửi query URL, chỉ prefill.

Guard bằng ref chống double-submit, snapshot/request generation để bỏ stale response của user cũ. Không tự retry POST. Lỗi giữ input và snapshot trước, trạng thái lỗi role=alert; nếu create thành công nhưng send fail, giữ session mới trong state/storage để retry không tạo thêm file rỗng. Nếu401 cần đăng nhập lại. Nếu409 có nút "Tải lại phiên" dùng getSession, giữ nguyên input. Tắt các thao tác send/new/open khi bận; bảo vệ khi resetKey đổi giữa request. List refresh lỗi không biến lượt chat đã lưu thành lỗi gửi hoặc phục hồi input đã gửi. Dùng React18, không thêm dependency, không gọi mock evaluator.

Test `chatApi.test.js` Node --test thực sự gọi các exported API methods bằng boundary fetch/localStorage fake; kiểm contract/header/body và missingtoken/http/network/badJSON, không import JSX. Test output ngắn gọn. Component kiểm journey bằng trình duyệt khi tích hợp; không tuyên bố Node tests đã test React.

Giữ output ngắn: panel khoảng200-260 dòng, API client khoảng50-80 dòng, tests khoảng80 dòng; tách helper nội bộ nếu dễ đọc, không tạo file ngoài allowlist.
