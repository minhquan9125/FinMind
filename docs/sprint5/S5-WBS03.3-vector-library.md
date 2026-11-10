# S5-WBS03.3 — Vector hóa và lưu phiên bản thư viện

Phụ trách: Hồ Phạm Đăng Nhân. Ngày thực hiện: 10/11/2026.
Giờ dự kiến backlog: 2 giờ; không phải giờ công thực tế đã ghi nhận.

## Đầu vào và kết quả

Đầu vào là 90 câu trong `intent-dataset-v1/library.jsonl`, bản dữ liệu
`s5-intent-dataset-v1-draft3`. Nội dung đã qua review Hưng và Nhân đã xác nhận nhóm
duyệt bảng nhãn. Giữ nguyên ID phiên bản snapshot đã review dù tên còn chứa draft;
không sửa câu hoặc nhãn trong task vector hóa. Không vector hóa 56 câu test.

Đã dùng dịch vụ `EmbeddingService` hiện có để tạo đủ ma trận **90 × 1024** bằng
**BAAI/bge-m3**, revision đầy đủ `5617a9f61b028005a4858fdac845db406aefb181`.
Máy đã có model cache; lượt chạy dùng chế độ offline trên CPU, batch size 8.
Vector là float32, chuẩn hóa L2; văn bản được giữ nguyên dấu và viết tắt, không
áp dụng hàm bỏ dấu dùng cho kiểm tra câu trùng của 03.2.

Phiên bản thư viện: **s5-intent-library-v1**. Gói nằm tại
[intent-library-v1](../../outputs/s5_wbs033_20261110/intent-library-v1).

| File | Nội dung |
|---|---|
| vectors.npy | Ma trận vector; hàng i ứng với câu hàng i trong library.jsonl. Đọc bằng np.load(..., allow_pickle=False). |
| library.jsonl | Bản sao chính xác 90 câu, ID, nhãn, component_intents và metadata từ bộ được duyệt. |
| label-schema.json | Snapshot định nghĩa nhãn tương ứng, có checksum. |
| dataset-manifest.json | Snapshot manifest đầu vào 03.2, chứa version và trạng thái duyệt của dữ liệu. |
| manifest.json | Version thư viện, model/revision, số chiều, chuẩn hóa, thứ tự ID, checksum các file và phiên bản thư viện Python đã dùng. |

`dataset-manifest.json` mô tả thời điểm chuẩn bị bộ câu 03.2 nên trường
embedding_generated của snapshot đó vẫn false. Kết quả vector hóa được ghi ở
manifest thư viện riêng với task S5-WBS03.3 và status READY; không sửa snapshot
đầu vào để khiến dữ liệu đã review thay đổi checksum.

## Cách đã thực hiện

1. Kiểm tra bộ dữ liệu 03.2, checksum và trạng thái duyệt trước khi nạp model.
2. Chỉ đọc text từ library.jsonl theo đúng thứ tự, gọi embed_texts của dịch vụ
   embedding hiện có. Đây không phải model router trả graph_score/content_score.
3. Kiểm tra đủ hàng, đúng số chiều, hữu hạn và norm gần 1; chỉ sau đó tạo thư mục
   artifact và lưu dữ liệu. Manifest được ghi cuối, không ghi đè thư mục đã có.
4. Đọc lại artifact bằng load_library: kiểm tra hash, phiên bản, hàng/ID,
   kích thước, dtype, chuẩn hóa và model/revision nếu caller yêu cầu.
5. Tạo lại ba câu đại diện bằng model thật nạp lại ở tiến trình khác và so với
   vector đã lưu. Kết quả chi tiết nằm trong báo cáo verification.json.

Mười bài test artifact dùng encoder giả để thử các nhánh lỗi, không coi đó là
bằng chứng đã chạy BGE-M3. Cùng 14 bài test dữ liệu 03.2, tổng 24 bài đã đạt.
Việc embedding thật được chứng minh bằng artifact, manifest model và báo cáo
[kiểm tra đọc lại/tái tạo](../../outputs/s5_wbs033_20261110/verification.json).

## Chạy lại và tái tạo

Các lệnh chạy ở gốc FinMind. Dùng môi trường Python đã cài dependency backend;
ví dụ trên máy Nhân là `backend/.venv`. Model cần có sẵn trong cache hoặc được
tải từ nguồn được nhóm sử dụng khi chủ động bật mạng. Không kèm trọng số 2 GB
vào gói vector. Revision model đã được pin trong cấu hình và manifest.

Kiểm tra artifact mà không nạp model:

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/build_s5_intent_library.py --verify-only
```

Tạo một thư viện khác từ cùng đầu vào, không ghi đè bản v1:

```powershell
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$env:TOKENIZERS_PARALLELISM='false'
$env:OMP_NUM_THREADS='4'
$env:MKL_NUM_THREADS='4'
.\backend\.venv\Scripts\python.exe backend/scripts/build_s5_intent_library.py --output outputs/s5_wbs033_20261110/intent-library-rebuild --library-version s5-intent-library-rebuild
```

Kiểm tra tất cả vector và tạo lại ba câu đại diện:

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/verify_s5_intent_library.py --reencode --report outputs/s5_wbs033_20261110/verification.json
```

Model name/revision trong môi trường chạy phải khớp thư viện. Batch size, thiết bị,
phiên bản Torch/Transformers và phần cứng có thể làm khác sai số dấu phẩy động;
phép so tái tạo dùng atol=rtol=1e-5, không hứa bit giống nhau trên mọi thiết bị.
Giữ LF cho các file JSON/JSONL để checksum không đổi khi checkout Windows/Linux.

## Giới hạn và bước tiếp theo

Task này hoàn tất phần tạo/lưu/đọc lại vector thư viện; chưa đo chất lượng phân
loại và không thay đổi WebChat, router hoặc dữ liệu PostgreSQL/Neo4j.
Các lỗi router đã biết trước task này không được xem là đã sửa nhờ có vector.

S5-WBS04.1 sẽ tạo vector câu hỏi bằng cùng model/revision, đối chiếu với thư viện
và trả các nhóm gần nhất cùng điểm tương đồng. Ngưỡng, route và fallback thuộc
task sau; chưa triển khai ở đây. Bộ 56 câu test được giữ riêng cho bước đánh giá.
