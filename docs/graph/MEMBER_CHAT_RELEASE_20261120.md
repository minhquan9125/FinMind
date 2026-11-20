# Bàn giao bản sửa Chat ngày 20/11/2026

## Clone đúng bản code

Nhánh bàn giao: `backup-demo`. Bản sửa được tích hợp từ `fix/chat-member-reviews-20261119` ngày 20/11/2026.

```powershell
git clone --branch backup-demo https://github.com/minhquan9125/FinMind.git
cd FinMind
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
Copy-Item backend/.env.example backend/.env
cd frontend
npm ci
cd ..
```

Máy cần Python 3.12 và Node.js >=20. Không sao chép `.venv` hay `node_modules` giữa các máy.

## Cấu hình để dùng cùng dữ liệu

Nhận secret qua kênh riêng của nhóm rồi điền `backend/.env`:

- `DATABASE_URL`: PostgreSQL chung, có quyền runtime đọc corpus và quyền auth/chat theo tài khoản.
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`: Neo4j chung.
- `JWT_SECRET_KEY`: secret riêng của môi trường backend, ít nhất 32 ký tự.
- `GEMINI_API_KEY` hoặc `GEMINI_API_KEYS`: key được cấp cho thành viên. Xác nhận Free Tier rồi đặt `B1_GEMINI_FREE_TIER_CONFIRMED=true`. Key trên trang Admin của máy khác không đi theo Git.
- `RESEARCH_CORPUS_VERSION_ID`: bản được kiểm tra trên máy Vũ ngày 20/11 là `9354eea4-5dc9-5079-ae81-72d0bc5d5abf`, index `2b4445e6-a211-4f18-8fd3-a865b611f8ce`. ID này chỉ dùng được trên đúng database đã nạp bản đó.

Mỗi máy mở tunnel PostgreSQL/Neo4j của mình theo cổng VPS thực tế do nhóm cung cấp; `localhost` trên máy Vũ không phải localhost trên máy thành viên. Không đẩy password/key lên Git.

Thư mục `outputs/admin-ingestion` là trạng thái vận hành cục bộ, không nằm trong Git. Nếu máy đã có queue, corpus phục vụ trong queue có thể ghi đè ID trong `.env`; kiểm tra bằng preflight bên dưới. Không xóa queue để đổi corpus; dùng thao tác chuyển corpus được cấp quyền. Clone mới chưa có queue sẽ dùng ID trong cấu hình. Các lần nạp mới sau bản này cần nhóm đồng bộ lại corpus phục vụ giữa các máy; hiện chưa có con trỏ phục vụ dùng chung tự đồng bộ mọi backend.

Không cần file PDF/OCR cục bộ để hỏi nguồn đã đóng băng và nạp đầy đủ vào PostgreSQL. Chức năng cào/OCR/nhập mới của Admin cần writer, Tesseract/Poppler và dữ liệu đầu vào riêng: xem [LOCAL_DEMO](../sprint4/LOCAL_DEMO.md).

## Kiểm tra và chạy

```powershell
.\.venv\Scripts\python.exe backend/scripts/check_member_runtime.py --connect
.\.venv\Scripts\python.exe backend/scripts/run_demo_backend.py
```

Preflight chỉ SELECT/kiểm tra kết nối, không đổi quyền, không ghi database, không gọi Gemini. Nó chưa kiểm tra quota key, đăng nhập, độ phủ graph hoặc chất lượng câu trả lời. Nếu thiếu cấu hình phải sửa trước; không dùng secret mẫu. Một cửa sổ khác:

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Mở `http://localhost:5173`; kiểm tra `http://localhost:8000/api/health`. Chờ research/router warmup `ready` trước khi thử. Lần đầu cần tải BGE-M3 theo revision ghim; không bật chế độ offline khi chưa có cache. Có thể cấu hình `HF_HOME` trên chính máy thành viên để tái sử dụng cache chuẩn Hugging Face; không sửa Python để trỏ sang đường dẫn máy Vũ.

## Nghiệm thu sau clone

Đăng nhập bằng tài khoản thành viên, mở phiên mới rồi thử:

1. `Cho tôi biết nhân sự hiện tại của CMG` → nhánh quan hệ, có nguồn và giới hạn thời điểm; không xác nhận hiện tại chỉ từ BCTN cũ.
2. `mà nếu giờ tôi mua ELC được không` → nhận đúng ELC, không xuất hiện mã NEU từ chữ “mà nếu”. Đánh giá vẫn phụ thuộc dữ liệu và quota.
3. `Tin tức VCB mới nhất` → tin đã nạp, ngày đăng và đoạn nội dung khi có; không cào trực tiếp khi hỏi.
4. `Nguồn đâu?` → dùng nguồn của câu trước, giữ link/ngày/trang đã lưu; không tạo URL giả cho chỉ báo tính toán.
5. Chuyển công ty và hỏi tiếp: `Giá FPT hiện tại` → `còn VCB thì sao`.
6. Gửi chuỗi vô nghĩa → yêu cầu viết lại, không phát lại phân tích cũ.

Các test tự động không thay thế nghiệm thu dữ liệu thật. Bộ 560 ca Excel chưa được chấm toàn bộ đúng/sai, không được báo là 560 ca đạt. Gemini có thể diễn đạt khác dù cùng code và dữ liệu; hết quota hoặc tunnel đóng sẽ làm kết quả khác máy đang hoạt động.

## Kiểm tra trước push

- Bộ hồi quy bị ảnh hưởng: 2.341 test backend, 58 test frontend đạt; không phải toàn bộ test tích hợp DB của repository.
- Clone sạch từ commit bàn giao: `npm ci` và `npm run build` đạt; 205 test cấu hình/định tuyến/model cache đạt. Test Python dùng môi trường dependency hiện có đã qua `pip check`, chưa phải cài toàn bộ Python/Torch trên một máy Windows trắng.
- Preflight đọc PostgreSQL/corpus và kết nối Neo4j đạt với cấu hình nhóm được đưa vào process riêng, không commit secret.
- Smoke trực tiếp graph và replay nguồn: 3/4 ca có nguồn hợp lệ (Chủ tịch FPT, Chủ tịch TCB, HĐQT FPT); Chủ tịch VCB trả graph rỗng. Ca này cần kiểm tra luồng văn bản dự phòng riêng, chưa được tính đạt câu trả lời trong lượt bàn giao này.
- Chỉ báo tính toán có đoạn bằng chứng nhưng không nhất thiết có URL bài báo riêng. BCTC/tin tức thiếu URL trong dữ liệu gốc phải được bổ sung provenance qua pipeline, không tự tạo link.
