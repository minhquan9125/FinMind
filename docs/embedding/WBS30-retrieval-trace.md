# WBS30 — Timing và lỗi của vector retrieval

`POST /api/search/filtered` ghi một trace JSON cho mỗi lần handler chạy vào console backend và `backend/.tmp/retrieval-traces.jsonl`. File local nằm trong `.gitignore`; API không ghi log vào Supabase và không đổi response. Chức năng này chỉ áp dụng cho endpoint vector có lọc, chưa bao gồm `/api/search/price` hoặc luồng hỏi đáp khác.

## Đọc log

Từ thư mục gốc repo, dùng CMD:

```cmd
powershell -NoProfile -Command "Get-Content 'backend/.tmp/retrieval-traces.jsonl' -Tail 3"
```

Mỗi dòng là một JSON object. `trace_id` là ID riêng của lần gọi; `timestamp` theo UTC. `embedding_ms` đo cả lần nạp model đầu tiên nếu model chưa nằm trong RAM. `retrieval_ms` gồm truy vấn vector và dựng/kiểm tra nội dung nguồn; `total_ms` gồm cả tra corpus và tạo response. Các giá trị đều là mili giây.

- `success`: có ít nhất một hit; `hit_count`, `returned_hit_count` và danh sách `{chunk_id, score}` được ghi.
- `empty`: truy vấn thành công nhưng không có hit; hai count bằng `0`, `error_code: null`.
- `error`: truy vấn thất bại; `error_code` an toàn, chẳng hạn `SOURCE_CHANGED` hoặc `EMBEDDING_ERROR`. Nếu SQL đã xếp hạng chunk, `hit_count` và `hits` vẫn ghi số chunk/điểm đã tìm được; `returned_hit_count: null` vì không có response thành công. Nếu lỗi xảy ra trước SQL, `hit_count: null`, `hits: []`. Timing chưa chạy xong là `null`.
- `unverified_hit_count` cho biết số hit trả bằng chế độ `preview_source_changed`; không được xem đó là nguồn đã xác minh.

Trace chỉ chứa ID phiên bản, bộ lọc đã giới hạn, thời gian, số hit, ID chunk, điểm và mã lỗi. Không ghi câu hỏi, text chunk, locator, URL DB, mật khẩu, exception message hoặc stack trace. Giá trị bộ lọc không đúng mẫu an toàn được thay bằng `[redacted]`. Nếu file local không ghi được, API vẫn chạy; console chỉ báo `retrieval_trace_file_unavailable`.

## Kiểm chứng ngày 22/10/2026

Chạy trên corpus-v2 `232fbd29-355f-5a77-ba28-a06b8d5ceb40` với Supabase ở chế độ đọc:

| Trường hợp | HTTP | Trạng thái trace | hit_count | error_code |
| --- | ---: | --- | ---: | --- |
| Q03, `FPT`/`2026-09`/`NEWS` | 200 | `success` | 5 | `null` |
| Cùng câu, công ty `NOPE` | 200 | `empty` | 0 | `null` |
| Q31, `FPT`/`2026-Q2`/`FINANCIAL_STATEMENT` (trace trước cải tiến) | 409 | `error` | `null` | `SOURCE_CHANGED` |

Ba dòng có `embedding_ms`, `retrieval_ms`, `total_ms`; ca thành công có 5 `{chunk_id, score}`. Sau lần kiểm chứng này, code đã bổ sung ghi hit/điểm ngay sau SQL để trace lỗi `SOURCE_CHANGED` vẫn cho biết vector tìm được gì. Kiểm tra bổ sung trên DB thật bằng một vector đã lưu trong index (thay cho bước embed câu hỏi vì môi trường hiện không tải được model) trả HTTP 409, `hit_count: 5`, `returned_hit_count: null`, 5 điểm và `error_code: SOURCE_CHANGED`. Kiểm tra này xác nhận đường đi SQL → xác minh nguồn → trace, không đo chất lượng tìm kiếm theo câu hỏi. Q31 vẫn lỗi xác minh nguồn; WBS30 không sửa dữ liệu hoặc chunk. Lần gọi đầu trước đó mất khoảng 95 giây để nạp BGE-M3; số đo này không đại diện cho truy vấn khi model đã được nạp.

Mẫu rút gọn từ trace Q31 thật trước cải tiến (bỏ các ID để dễ đọc):

```json
{
  "event": "vector_retrieval",
  "status": "error",
  "filters": {"company_symbol": "FPT", "period": "2026-Q2", "doc_type": "FINANCIAL_STATEMENT"},
  "embedding_ms": 1299.698,
  "retrieval_ms": 1396.505,
  "total_ms": 3038.494,
  "hit_count": null,
  "hits": [],
  "error_code": "SOURCE_CHANGED"
}
```

Kiểm tra code không cần DB:

```cmd
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_retrieval_trace.py backend\tests\test_filtered_search_api.py -q -p no:cacheprovider
```
