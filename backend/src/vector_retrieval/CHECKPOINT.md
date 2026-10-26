# Checkpoint bàn giao — 22/10/2026 (cập nhật sau Bước 2)

Trạng thái: **Đang tiến hành theo HANDOFF_PLAN — đã xong Bước 2 (lọc publisher/ngày), chưa chạy lại Golden/Bước 3-5.** Tự chạy/tự sửa/tự kiểm, không gọi ECC/OmniRoute/sub-agent. Chỉ sửa trong `backend/src/vector_retrieval`, Supabase chỉ đọc.

## Đã hoàn tất trong phiên này

- Rà soát metadata frozen (snapshot 675 docs / 15.058 chunks, pin `86e880eef3b39ddf2515951252025a8f58e700f80416ba24d6fabfe324362bd7`): NEWS 1.750 chunk gồm `fireant.vn` 1.104 / `cafef.vn` 646, header `Tin <pub> | YYYY-MM-DD |` khớp 100% với `locator.url` + `locator.published_at`; FINANCIAL có `section` + `period_code` phân biệt chỉ tiêu/kỳ. Q03/Q08/Q31 đã xác nhận là case lọc publisher/ngày, không phải thiếu chunk.
- Thêm lọc tùy chọn **publisher** (`cafef|fireant`, suy từ `locator.url` frozen) và **published_date** (`YYYY-MM-DD`, suy từ `locator.published_at` frozen) trong `backend.py`: `_publisher`, `_published_date`, `_derive_publisher`, `_derive_published_date`, mở rộng `FIELDS`/`_metadata`/`_matches`, search `publisher`/`published_date` mặc định `None` giữ hành vi cũ, áp dụng trước khi lấy ứng viên ở **cả hai nhánh** dense + BM25 (chung `allowed_ids`), kiểm tra lại sau resolve.
- Nâng cache **version 1 → 2** (`TOKENIZER_VERSION` giữ `vi-fold-v1`): thêm `published_date`/`publisher`/`source_url` mỗi row, `_validate_cache` nghiêm, cache cũ v1 bị `CACHE_VERSION_MISMATCH` và yêu cầu `build` lại (không làm mất kiểm tra index/model/TTL/hash, ghi atomic giữ nguyên). Đã xóa cache v1 cũ `.../434ef5e0-6516-578d-8d18-721d21347e01.json` để tránh nhầm.
- Cập nhật `hoi.py`: `--publisher` (`cafef|fireant`) và `--published-date` (`YYYY-MM-DD`), truyền vào `search`, hiển thị `scope`, lỗi `INVALID_PUBLISHER`/`INVALID_PUBLISHED_DATE`/`CACHE_VERSION_MISMATCH` có hint. CLI giữ nguyên `build`/`search`, cặp `--source-snapshot`/`--snapshot-sha256` và `HF_HUB_OFFLINE`.
- Smoke offline: default compat (không truyền publisher giữ kết quả cũ), lọc `cafef`/`fireant` + ngày đúng trả đúng chunk, lọc sai (`cafef` 2026-08-05, `fireant` sai ngày) trả rỗng, lỗi publisher/date sai định dạng bị `INVALID_*`; FINANCIAL không bị ảnh hưởng khi lọc publisher (trả rỗng đúng vì không có news phù hợp — hành vi chính xác theo spec “sai publisher/ngày trả rỗng”).
- **76 test offline vẫn đạt** (backend/cache_paging/cli/ranking/snapshot_cli/sources) sau đổi version; `README.md` đã cập nhật cache v2, filter publisher/date và ví dụ CLI.

## Chưa hoàn tất (theo HANDOFF_PLAN)

- **Bước 3:** Chưa chạy lại 18 câu đủ nguồn × (có/không lọc publisher/ngày), top 5/top 10, sai mã/kỳ/publisher/ngày, kiểm hash/locator không dùng gold ID. Báo cáo `golden40-snapshot-supabase-20261022.md/.json` ngày 22/10 vẫn là baseline cũ (chưa có filter mới); chưa ghi báo cáo mới.
- **Bước 3 biến thể hỏi tiền và tương đương tiền (Q31):** lọc publisher/ngày không giải quyết case “tiền đầu kỳ vs tiền tại thời điểm” — thuộc cải thiện phân biệt chỉ tiêu/kỳ tổng quát, không hardcode Q31, để Bước 3 đánh giá riêng.
- **Bước 4:** 9 câu PDF Q21–Q29 (thiếu PDF FPT 2024) + 13 câu tính/giá/từ chối — giữ ngoài phạm vi retrieval, không ingest/sửa DB trong task này.
- **Bước 5:** Chưa chạy 1 lượt CLI build/search thật với cache v2 trên Supabase thật; chưa cập nhật receipt `FINAL_GOLDEN_CHECKPOINT`.

## Ràng buộc giữ nguyên

Chỉ sửa `backend/src/vector_retrieval`; Supabase chỉ đọc; không ingest/migration/đổi index/tái embedding/sửa nguồn/B1/frontend/OHLCV; không gọi Gemini; không git add/commit/push; giữ `retrieval_orchestration/chat_history/web/` untracked. Index quan sát ACTIVE `434ef5e0-6516-578d-8d18-721d21347e01`, model `BAAI/bge-m3@5617a9f61b02`, snapshot pin như trên, provenance `FROZEN_SNAPSHOT`.

## File đã sửa phiên này

`backend.py` (lọc publisher/date + cache v2), `hoi.py` (CLI publisher/published-date), `README.md` (docs v2). Chưa sửa `ranking.py`, `sources.py`, `.work/*`, `reports/*`.

## Lệnh đã kiểm chứng phiên này

```powershell
backend\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s backend/src/vector_retrieval/tests -b
# 76 tests OK
```

Lệnh build/search với filter mới (yêu cầu cache v2, chưa chạy trên Supabase thật trong phiên này):

```powershell
$pin = '86e880eef3b39ddf2515951252025a8f58e700f80416ba24d6fabfe324362bd7'
$snap = 'backend/.tmp/corpus-v2.content.manifest.json'
$env:HF_HUB_CACHE = "$PWD/backend/src/vector_retrieval/.cache/huggingface"
backend\.venv\Scripts\python.exe -X utf8 backend/src/vector_retrieval/hoi.py build --index 434ef5e0-6516-578d-8d18-721d21347e01 --allow-building --source-snapshot $snap --snapshot-sha256 $pin
backend\.venv\Scripts\python.exe -X utf8 backend/src/vector_retrieval/hoi.py search --index 434ef5e0-6516-578d-8d18-721d21347e01 --allow-building --source-snapshot $snap --snapshot-sha256 $pin --question "đợt tăng vốn FPT 171,4 triệu" --company FPT --period 2026-09 --doc-type NEWS --publisher cafef --published-date 2026-09-29 --top-k 10 --candidates 50 --json
# mặc định không truyền --publisher/--published-date giữ hành vi cũ
```

Tiếp theo: build cache v2 trên Supabase thật → chạy lại 18 câu (filtered/unfiltered + sai publisher/ngày) → báo cáo tiếng Việt mới (không ghi đè baseline 22/10) → 1 lượt CLI thật → cập nhật checkpoint khi dừng.
