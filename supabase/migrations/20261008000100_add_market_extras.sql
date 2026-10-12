-- Bổ sung bảng cho dữ liệu của data_pipeline/ScrapersOHLCV chưa có chỗ lưu:
--   price_indicators      SMA20/SMA50/RSI14 theo từng nến trong price_bars
--   market_index_bars     nến ngày của chỉ số (VNINDEX, VN30, HNXINDEX...), đơn vị điểm
--   market_live_snapshots bảng điện (live.json) mới nhất của mỗi mã/chỉ số
-- Chỉ tạo mới (IF NOT EXISTS), không xóa hay sửa bảng khác. Chạy sau 20261008000000_add_news_articles.sql.

CREATE TABLE IF NOT EXISTS public."price_indicators" (
    "price_id"   uuid PRIMARY KEY REFERENCES public."price_bars" ("price_id") ON DELETE CASCADE,
    "sma20"      numeric,
    "sma50"      numeric,
    "rsi14"      numeric,
    "updated_at" timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public."market_index_bars" (
    "index_symbol" varchar(20)  NOT NULL,           -- VNINDEX | VN30 | HNXINDEX | UPCOMINDEX
    "index_name"   varchar(100),
    "exchange"     varchar(10),
    "trade_date"   date         NOT NULL,
    "open"         numeric(18, 4),
    "high"         numeric(18, 4),
    "low"          numeric(18, 4),
    "close"        numeric(18, 4),
    "volume"       bigint,
    "sma20"        numeric,
    "sma50"        numeric,
    "rsi14"        numeric,
    "payload_id"   uuid REFERENCES public."raw_payloads" ("payload_id"),
    PRIMARY KEY ("index_symbol", "trade_date")
);

CREATE TABLE IF NOT EXISTS public."market_live_snapshots" (
    "symbol"          varchar(20) PRIMARY KEY,
    "instrument_type" varchar(10) NOT NULL DEFAULT 'stock',   -- stock | index
    "fetched_at"      timestamptz,
    "data"            jsonb       NOT NULL,                   -- nguyên nội dung live.json
    "payload_id"      uuid REFERENCES public."raw_payloads" ("payload_id"),
    "updated_at"      timestamptz NOT NULL DEFAULT now()
);

-- Bật RLS, chưa có policy: khóa API công khai; backend dùng kết nối Postgres vẫn đọc ghi bình thường.
ALTER TABLE public."price_indicators"      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."market_index_bars"     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."market_live_snapshots" ENABLE ROW LEVEL SECURITY;
