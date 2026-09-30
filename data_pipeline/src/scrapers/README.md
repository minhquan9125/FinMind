# Cào tin tức CafeF và FireAnt

`stock_news_collector.py` thu thập bài viết công khai, trích nội dung văn bản và lưu vào JSON UTF-8. File này hoạt động độc lập với collector dữ liệu giá và báo cáo tài chính trong cùng thư mục.

## Cách cào

| Nguồn | Tìm link bài | Tải bài |
|---|---|---|
| CafeF | Đọc [RSS thị trường chứng khoán](https://cafef.vn/thi-truong-chung-khoan.rss) bằng `requests` và lấy thẻ `item/link`. | Dùng `Scrapling Fetcher` đọc HTML. |
| FireAnt | Mở trang chủ bằng `Scrapling DynamicFetcher`, tìm link trong mục **Bài viết & tin tức** do JavaScript hiển thị. | Dùng `DynamicFetcher` mở từng bài. |

Collector chỉ chấp nhận URL bài cụ thể có dạng `cafef.vn/...-<id>.chn` hoặc `fireant.vn/bai-viet/<slug>/<id>`. Với mỗi link, nó mở trang, yêu cầu HTTP 200, kiểm tra URL sau chuyển hướng và URL canonical (nếu có), rồi lấy tiêu đề, mô tả, nội dung và ngày đăng. Trang không đọc được hoặc không đúng dạng bài sẽ bị bỏ qua. Các lần chạy cách nhau ít nhất một giây giữa các bài mới.

Link ở trường `url` là **link trực tiếp đến bài viết**; dán vào thanh địa chỉ trình duyệt sẽ mở trang bài, không phải trang chủ hay RSS. Link có thể ngừng hoạt động về sau nếu trang nguồn xóa hoặc đổi URL.

## Cài và chạy

Chạy các lệnh từ thư mục gốc dự án. Cần Python 3.10 trở lên và kết nối mạng. FireAnt cần Chromium cho trang JavaScript.

```powershell
python -m pip install "requests>=2.32,<3" "scrapling[fetchers]>=0.4,<1"
scrapling install

# CafeF (mặc định), tối đa 10 link ứng viên
python data_pipeline/src/scrapers/stock_news_collector.py --source cafef --limit 10

# FireAnt
python data_pipeline/src/scrapers/stock_news_collector.py --source fireant --limit 10

# Cả hai nguồn, tối đa 10 link ứng viên mỗi nguồn
python data_pipeline/src/scrapers/stock_news_collector.py --source all --limit 10

# Một hoặc nhiều URL bài cụ thể; --url có ưu tiên hơn --source
python data_pipeline/src/scrapers/stock_news_collector.py --url "https://cafef.vn/vinfast-vua-bat-tay-ong-lon-han-quoc-so-huu-vat-lieu-o-to-hang-dau-the-gioi-188260930110613803.chn"
```

Lệnh trên lưu vào `data_pipeline/src/scrapers/stock_news.json`. Đổi vị trí bằng `--output <đường-dẫn-json>` nếu cần. Lượt cào thử đã có trong [news_trial.json](news_trial.json): 3 bài CafeF và 3 bài FireAnt, thu thập ngày 30/09/2026.

## Dạng dữ liệu

Đầu ra là **JSON**, không phải PDF hay HTML. Cấu trúc:

```json
{
  "schema_version": "1.0",
  "articles": [
    {
      "id": "9961de58a0d7de464e08",
      "source": "cafef",
      "url": "https://cafef.vn/vinfast-vua-bat-tay-ong-lon-han-quoc-so-huu-vat-lieu-o-to-hang-dau-the-gioi-188260930110613803.chn",
      "title": "VinFast vừa “bắt tay” ông lớn Hàn Quốc sở hữu vật liệu ô tô hàng đầu thế giới",
      "description": "Tóm tắt từ trang nguồn",
      "content": "Nội dung văn bản được trích từ trang bài",
      "published_at": "2026-09-30T11:17:00",
      "crawled_at": "2026-09-30T04:26:10.312836+00:00"
    }
  ]
}
```

`id` là 20 ký tự đầu của SHA-256 trên URL bài. `published_at` giữ giá trị trang nguồn cung cấp, có thể là `null` hoặc không có múi giờ; `crawled_at` là giờ UTC. Nếu file đầu ra đã tồn tại, collector giữ bài cũ và thêm bài mới theo URL để tránh trùng. Nếu không có bài hợp lệ và chưa có file cũ, chương trình trả mã lỗi 1 và không tạo file trống.

## Giới hạn hiện tại

- RSS CafeF chỉ cho các bài mới trong feed, không phải toàn bộ kho lưu trữ.
- Mục FireAnt có cả tin kinh tế và doanh nghiệp ngoài chủ đề chứng khoán. Collector chưa lọc mức liên quan đến mã cổ phiếu hoặc chủ đề đầu tư; cần lọc thêm trước khi dùng làm corpus tin chứng khoán.
- Nội dung trích từ HTML có thể còn nhãn giao diện hoặc chú thích ảnh. Bố cục trang nguồn thay đổi có thể khiến một số bài bị bỏ qua.
- Collector lưu văn bản và URL, không tải ảnh hay tệp đính kèm.
