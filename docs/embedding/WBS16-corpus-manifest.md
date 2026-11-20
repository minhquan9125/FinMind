# WBS16 — Manifest corpus phiên bản ban đầu

Manifest chốt các chunk **đã ingest trong một index**, không đọc JSON crawler hay chạy embedding. Cấu hình index, danh sách tài liệu, hash tài liệu, ID/vị trí/hash/nội dung/locator từng chunk được lưu trong JSON. Chỉ lấy chunk hiện hành lúc chốt; việc đọc lại corpus này về sau phải dùng danh sách chunk ID trong manifest, không chọn lại tất cả chunk hiện hành của index.

## Chạy

Từ gốc `FinMind`, dùng Python đã cài đủ thư viện backend; thay `python` bằng đường dẫn Python của máy nếu chưa có trên PATH. Kết nối lấy từ `backend/.env` hoặc `.env`.

```powershell
# Xuất snapshot, chỉ đọc DB
python -X utf8 backend/scripts/freeze_corpus.py --label corpus-v1 --out backend/.tmp/corpus-v1.manifest.json
# Đăng ký vào corpus_versions và corpus_documents
python -X utf8 backend/scripts/freeze_corpus.py --label corpus-v1 --out backend/.tmp/corpus-v1.manifest.json --apply
```

Chạy lại cùng lệnh/cùng dữ liệu trả `already_registered`, không đổi thời gian chốt hoặc thêm thành viên. Dữ liệu khác phải dùng nhãn và file mới, ví dụ `corpus-v2`. File đã tồn tại khác nội dung hoặc nhãn đã dùng cho corpus khác đều bị từ chối. Mọi ghi DB nằm trong một transaction; không thay đổi documents/text_chunks/vector. Khóa SHARE ngắn hạn giữ documents/text_chunks ổn định khi chốt, có thể khiến ingest khác chờ đến khi chốt xong.

## Contract

- `manifest_sha256` là SHA-256 của UTF-8 JSON canonical của trường `manifest`: sort keys, dấu phân cách `,`/`:`, không escape Unicode. Không phải hash toàn file có indent.
- `corpus_version_id` được tính UUID5 từ hash này, không phụ thuộc thời điểm chạy hoặc thứ tự kết quả SQL. Cấu hình, nội dung, locator hay thành viên thay đổi sẽ tạo phiên bản khác.
- `corpus_versions` lưu ID, nhãn, index, hash manifest, thời điểm và trạng thái `FROZEN`. `frozen_by` để NULL vì CLI chưa có phiên đăng nhập người dùng; không tự nhận danh tính của thành viên khác.
- `corpus_documents` lưu document ID và hash tại lúc chốt. `documents.sha256` hiện hành có thể đổi khi ingest; dùng hash trong corpus để đối chiếu bản gốc.
- JSON là danh sách thành viên **ở mức chunk** và bản sao nội dung/locator. Hai bảng hiện tại không có liên kết corpus–chunk; chỉ lọc corpus_documents + index chưa đủ cô lập phiên bản sau lần ingest tiếp theo. WBS25 cần đọc danh sách chunk ID đã chốt.
- Manifest không sao chép vector. Nếu retention sau này xóa chunk cũ, manifest vẫn còn chữ/locator nhưng truy vấn vector bản cũ không còn đủ. WBS này chưa thay đổi retention; trước khi cần phục hồi đầy đủ corpus lịch sử, cần cơ chế giữ chunk thuộc corpus hoặc snapshot vector.
- File nằm trong `.tmp` được Git ignore: phải giữ và bàn giao file cùng báo cáo, không chỉ gửi mã corpus/hash. Không đưa vector hoặc thông tin kết nối vào Git.
- Nguồn tài chính chưa có observations, nên corpus đầu tiên không có tài liệu tài chính; không tuyên bố đã nghiệm thu nguồn này. Graph/facts/prices membership có task riêng, không tự tạo trong WBS16 chunk manifest.

## Kết quả kiểm tra ngày 16/10/2026

Snapshot từ DB: 249 tài liệu, 2.048 chunk (6 hồ sơ công ty, 204 giá, 88 chỉ số, 1.750 tin).

- Corpus ID: `7c2ea700-fd01-5adc-a467-af4fea532741`.
- Manifest SHA-256: `e9391c8af33b64888ea7b7c386a526110c35aab7fc2c469366e648f41c393f41`.
- File cục bộ: `backend/.tmp/corpus-v1.manifest.json`.
- Đã đăng ký `corpus-v1` thật vào Supabase: 1 corpus version, 249 liên kết tài liệu. Chạy lại trả `already_registered`; toàn bộ danh sách/hash tài liệu khớp manifest, không thêm bản trùng.
- 85 test manifest + chunking + ingest + embedding + locator + retention đạt. Kiểm tra thứ tự SQL không đổi ID, locator đổi tạo phiên bản mới, dữ liệu/hash/vector/locator không hợp lệ bị từ chối, chạy lại không ghi thêm, payload bị sửa không đăng ký được.
