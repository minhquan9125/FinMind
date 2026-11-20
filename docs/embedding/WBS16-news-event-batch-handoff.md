# WBS16 — bàn giao extractor sự kiện News theo lô

`backend/src/documents/news_event_extractor.py` nhận manifest đã đóng băng, một lô tối đa 100 hàng `news_articles`, và hàm sinh ứng viên. Đầu ra chỉ là JSON; không ghi vào `news_articles` hay bảng graph. CLI `backend/scripts/extract_news_events_batch.py` chạy với tệp JSON đã chọn trước. Task này không chạy full-load.

## Contract

- Chỉ xử lý `article_id` có locator `news_articles` trong tài liệu `NEWS` của manifest. Nếu manifest có hash, xác minh hash trước khi xử lý. Không dùng `symbols` làm bằng chứng vai trò.
- Mỗi ứng viên cần `event_type`, `status`, `subject` (`name`, `role`, `symbol` nếu xác định), `participants`, `object`, `source_span`, `event_time`, `event_time_precision`. `source_span` phải là chuỗi con nguyên văn của `content`; actor, object và các participant phải xuất hiện trong span. Thiếu căn cứ trả `REVIEW` cho bài đó.
- `published_at` lấy từ hàng News. `announced_at` và `event_time` là trường độc lập, mặc định `null`. Muốn điền ngày phải có span ngày riêng trong thân bài, kiểm tra được đúng độ hạt `day`, `month`, `year` hoặc `range`. Không dùng ngày đăng làm ngày diễn ra.
- `OCCURRED`, `PLANNED`, `CANCELLED`, `UNCONFIRMED` là trạng thái của hành động được trích. `CONFLICT` chỉ là trạng thái nhóm khi các nguồn bất đồng; mọi `source_claims` vẫn giữ trạng thái gốc, URL, đoạn văn, ngày đăng và chi tiết riêng.
- `event_ref` tùy chọn dành cho người kiểm định gắn các bài cập nhật cùng sự kiện khi cách diễn đạt object khác nhau. Nếu không có, khóa nhóm dựa trên actor + loại sự kiện + object + thời gian. Không tự gộp hai đợt phát hành khác nhau. `event_group_id` ổn định cho cùng khóa.
- Không có trường tác động tài chính hay nhân quả trong đầu ra. Các trường lạ từ ứng viên không được chuyển tiếp. Một bài có thể có 0..n sự kiện; ứng viên không đạt validator không trở thành event.

## Gọi từ WBS16

Lấy các bài theo **danh sách `article_id` đã chọn** và thành viên manifest, rồi gọi `extract_batch(manifest, articles, propose)` trong Python. `propose(article)` trả một list ứng viên. `rule_candidates` là bộ luật hẹp đi kèm để khởi động; nó chỉ nhận vài mẫu actor + động từ + object rõ ràng, giữ ngày hành động chưa biết và đưa câu thiếu dấu hiệu thời vào `UNCONFIRMED`. Với các ca phức tạp trong bộ nhãn FireAnt, dùng bộ đề xuất riêng hoặc người kiểm định và vẫn đi qua cùng validator. Kết quả `NO_EVENT` của bộ luật hẹp có nghĩa **chưa tìm thấy bằng luật này**, không phải khẳng định bài không có sự kiện.

Ví dụ CLI (đường dẫn là ví dụ, không phải lệnh full-load):

```powershell
& 'C:/Users/pc/.venv/Scripts/python.exe' backend/scripts/extract_news_events_batch.py `
  --manifest backend/.tmp/corpus-v1.manifest.json `
  --articles backend/.tmp/news-selected-articles.json `
  --candidates backend/.tmp/news-selected-candidates.json `
  --out backend/.tmp/news-events-batch-01.json
```

`--articles` là JSON array có ít nhất `article_id`, `source`, `url`, `content`, `published_at`; `--candidates` là JSON object ánh xạ `article_id` sang array ứng viên và có thể bỏ qua để dùng luật hẹp. Tệp output phải là đường dẫn mới để không ghi đè kết quả kiểm định cũ. Không đưa API key hay `.env` vào các tệp này.

Ví dụ một ứng viên cho bài có span `FPT đã hoàn thiện hai AI Factory tại Nhật Bản và Việt Nam`:

```json
{
  "event_type": "FACILITY_COMPLETION",
  "status": "OCCURRED",
  "subject": {"name": "FPT", "symbol": "FPT", "role": "operator"},
  "participants": [],
  "object": "hai AI Factory",
  "source_span": "FPT đã hoàn thiện hai AI Factory tại Nhật Bản và Việt Nam",
  "event_time": null,
  "event_time_precision": "unknown",
  "announced_at": null
}
```

Các nhãn hiện theo bản nháp `docs/fireant-event-labeling-10-symbols.md`; cần mentor chốt taxonomy trước khi ghi event vào graph hoặc chạy rộng. Kiểm thử batch dùng fixture cục bộ, không xác nhận lại toàn bộ 234 bài News trên Supabase.
