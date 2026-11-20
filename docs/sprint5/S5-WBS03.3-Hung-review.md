# Hưng — Review S5-WBS03.3

Ngày review: 10/11/2026. Nhánh nguồn: `origin/nhan-sprint-501`.
Commit: `0c80ac584f20fa93957e768aae3ea0f9f83fe191`.

## Kết luận kỹ thuật

Chưa phát hiện lỗi chặn trong phạm vi tạo, lưu phiên bản và đọc lại thư viện vector.
Artifact hiện tại đạt các kiểm tra trực tiếp bên dưới. Đã tái tạo toàn bộ 90 vector
bằng BGE-M3 thật, không chỉ đọc lại báo cáo của tác giả. Không sửa code hoặc dữ liệu
nguồn, không merge/push và không thay đổi WebChat.

Đây là kết quả kiểm tra của Codex cho Hưng. Cổng review độc lập ECC chưa hoàn tất;
không coi báo cáo này là bằng chứng workflow ECC đã được nghiệm thu.

## Bằng chứng chạy lại

| Hạng mục | Kết quả |
|---|---|
| Test có sẵn | 28 passed, xem `tests.xml` |
| Đọc toàn bộ artifact | 90 × 1024, float32, hữu hạn, chuẩn hóa L2 |
| Norm nhỏ nhất/lớn nhất | 0.9999998808 / 1.0000001192 |
| Nhãn | 6 nhãn đơn × 12 câu; MIXED 18 câu; tổng 90 |
| Snapshot nguồn | library, schema và dataset manifest khớp từng byte với nguồn |
| Tách test | 56 câu test riêng; không giao ID với thư viện; builder chỉ encode library.jsonl |
| Tái tạo 3 câu | S5-L-001, S5-L-046, S5-L-090; sai lệch tối đa 7.6368451e-8 |
| Dựng lại đủ 90 câu | Đạt `np.allclose(atol=1e-5, rtol=1e-5)`; sai lệch tối đa 6.0349703e-7 |

Checksum SHA-256 của vectors.npy gốc:
`67e61d4dbae5252e9ff473ee8c84d1ac47c435b16cb1e747250bd9a28cf2f7a8`.

Bằng chứng mới nằm cùng thư mục báo cáo: `readback.json`, `tests.xml`,
`reencoding.json`, `full-rebuild-comparison.json`, `rebuild.log` và `rebuilt-library/`.
Không ghi đè verification.json của tác giả.

## Phiên bản, model và khả năng tái tạo

- Library `s5-intent-library-v1`, dataset `s5-intent-dataset-v1-draft3`, schema
  `s5-intent-labels-v1-draft2` được ghi riêng; giữ tên draft để bảo toàn snapshot
  đã được duyệt là phù hợp.
- Model `BAAI/bge-m3`, full revision
  `5617a9f61b028005a4858fdac845db406aefb181` khớp cấu hình dự án.
- Manifest lưu thứ tự row ID, checksum bốn file, dimension, dtype, normalization,
  preprocessing, device, batch size, max sequence length và phiên bản thư viện Python.
- Loader kiểm tra hash, liên kết provenance, thứ tự ID, shape, dtype và norm.
  Các caller cần so sánh embedding phải truyền expected_model/expected_revision;
  script tái tạo hiện tại đã kiểm tra hai giá trị này trước encode.
- Builder giữ snapshot trước model call, không ghi đè thư mục có sẵn và ghi manifest
  sau cùng. Test hiện có kiểm tra lỗi checksum, vector sai và thay nguồn khi encode.
- Môi trường reviewer: Python 3.12.14, NumPy 2.5.4, Torch 2.6.0,
  sentence-transformers 3.1.1, transformers 4.57.6, huggingface-hub 0.36.2.
  Khác Python/NumPy của tác giả nhưng tái tạo vẫn đạt dung sai; không yêu cầu
  checksum vector dựng lại giống tuyệt đối trên mọi môi trường.
- Model chạy CPU, offline, từ cache đúng revision; không tải weights hoặc gọi DB.

## Giới hạn và trạng thái workflow

Không có ZIP bàn giao gốc trong nhánh đã fetch, nên chưa xác minh chính ZIP đó hoặc
lặp lại thao tác giải nén của tác giả. Kiểm tra này chạy từ checkout worktree mới.
Không đo accuracy, không đối chiếu câu hỏi 04.1 và không thử tích hợp WebChat.
Checksum phát hiện hỏng hoặc thay đổi file; không phải chữ ký xác thực tác giả.

Lượt pytest đầu bị sandbox chặn thư mục tạm; chạy lại có quyền đã đạt 28/28.
ECC manager đã tạo WBS nhưng hai lượt worker lỗi `Gateway connection failed`.
Stage hiện xếp hàng vì các route trong packet bị quarantined; chưa có proposal,
QA hoặc review độc lập đạt cổng. Không xóa lease, không thay packet đã phát,
không tăng budget và không ghi nhận worker thất bại thành thành công.

Ngoại lệ coordinator: tự đọc code và chạy kiểm chứng để cung cấp kết quả hữu ích
trong lúc ECC không dùng được. Chỉ tạo báo cáo và receipt ngoài các file candidate
đã đăng ký; chưa tích hợp candidate nào. Muốn hoàn tất cổng ECC cần khôi phục
gateway và xử lý đúng các lease bằng bằng chứng upstream, rồi tiếp tục workflow
`hung-s5-wbs033-review` cùng job `s5033-review` và budget hiện tại.

Workspace chính vẫn ở midterm_demo; sửa chưa commit tại graph_store.py được giữ nguyên.

## Kiểm tra bổ sung theo yêu cầu Hưng

Hưng yêu cầu bỏ qua ZIP, tập trung các kiểm tra còn lại. Đã chạy lại 28 test gốc
cùng 27 ca mới trong `test_failure_cases.py`: **55 passed, 0 failed, 0 errors,
0 skipped**. Receipt: `failure-cases.xml`; đọc lại artifact thật sau test:
`readback-after-failure-cases.json`.

- Không giao nhau giữa hai tập theo ID, văn bản chuẩn hóa chữ thường/bỏ dấu/
  dấu câu/khoảng trắng, hoặc family_id. Kiểm tra này không chứng minh mọi diễn đạt
  khác nhau về ngữ nghĩa đều độc lập; bộ dữ liệu không phải blind evaluation.
- Xóa từng file trong năm file artifact: loader từ chối. Sửa từng payload trong
  bốn file có checksum: loader từ chối trước khi parse nội dung bị sửa.
- Cập nhật checksum vector sau khi đưa NaN, +Inf, -Inf, vector 0, norm sai,
  thiếu hàng, sai số chiều hoặc float64: loader vẫn từ chối theo hợp đồng vector.
- Truyền model hoặc revision khác: loader từ chối.
- Tiêm lỗi disk-full sau khi ghi một phần tại từng bước library, schema, dataset
  manifest, vectors, artifact manifest: exception được truyền ra; artifact dở dang
  không đọc được thành READY; bản hoàn chỉnh trước đó giữ nguyên từng checksum.
- Encoder ném exception: chưa tạo thư mục output. Hai builder cùng ghi một đường
  dẫn: một thành công, một FileExistsError; artifact kết quả đọc được đầy đủ.

Lưu ý vận hành: lỗi I/O có thể để lại thư mục output dở dang. Builder chủ động
từ chối ghi đè đường dẫn đó trước khi encode; dùng đường dẫn mới khi chạy lại.
Đây là giới hạn phục hồi, không phải mất/hỏng bản thư viện cũ. Test tiêm lỗi có
kiểm soát, không thực sự làm đầy ổ đĩa hoặc cắt điện máy.

Không sửa code production. Các test bổ sung do coordinator viết trong phạm vi
ngoại lệ đã ghi, không coi là QA/review độc lập qua ECC. Kết luận kỹ thuật giữ
nguyên: chưa phát hiện lỗi chặn ở phạm vi 03.3 sau các kiểm tra bổ sung.
