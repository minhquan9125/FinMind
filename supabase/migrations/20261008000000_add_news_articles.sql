-- Bảng lưu tin tức do data_pipeline/scrapers (CafeF, FireAnt) thu thập.
-- An toàn để chạy trên database đang dùng: chỉ tạo mới, không xóa hay sửa bảng khác.

CREATE TABLE IF NOT EXISTS public."news_articles" (
    "article_id"    uuid PRIMARY KEY,
    "source"        varchar(30)  NOT NULL,          -- cafef | fireant
    "external_id"   varchar(64),                    -- id do crawler tạo
    "url"           text         NOT NULL,
    "title"         text         NOT NULL,
    "description"   text,
    "content"       text,
    "published_at"  timestamptz,
    "crawled_at"    timestamptz,
    "symbols"       text[]       NOT NULL DEFAULT '{}',  -- mã chứng khoán liên quan
    "attachments"   jsonb        NOT NULL DEFAULT '[]'::jsonb,
    "marker"        varchar(20),                    -- trạng thái đối chiếu (vd: uncheck)
    "cross_check"   jsonb,
    "payload_id"    uuid REFERENCES public."raw_payloads" ("payload_id"),
    "created_at"    timestamptz  NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS "uq_news_articles_source_url"
    ON public."news_articles" ("source", "url");
CREATE INDEX IF NOT EXISTS "idx_news_articles_published_at"
    ON public."news_articles" ("published_at" DESC);
CREATE INDEX IF NOT EXISTS "idx_news_articles_symbols"
    ON public."news_articles" USING GIN ("symbols");

-- Bật RLS và chưa tạo policy: khóa truy cập qua API công khai (anon/authenticated).
-- Backend dùng kết nối Postgres/service role vẫn đọc ghi bình thường.
ALTER TABLE public."news_articles" ENABLE ROW LEVEL SECURITY;
