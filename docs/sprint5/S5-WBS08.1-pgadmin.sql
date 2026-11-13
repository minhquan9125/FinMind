-- S5-WBS08.1: chạy nguyên file trong pgAdmin Query Tool của database FinMind.
-- Chỉ đọc. Thay hai mốc ngày ở CTE bounds trong cả hai truy vấn nếu đổi mẫu.
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '30s';

-- 1. Độ phủ toàn bộ và mẫu năm 2026; đơn vị OHLC giữ nguyên từ DB.
WITH bounds AS (
    SELECT DATE '2026-01-01' AS start_date, DATE '2026-10-29' AS end_date
), coverage AS (
    SELECT company_id, min(trade_date) AS available_first,
           max(trade_date) AS available_last, count(*) AS available_count
    FROM public.price_bars GROUP BY company_id
), sample AS (
    SELECT p.*,
           row_number() OVER (PARTITION BY company_id ORDER BY trade_date) AS first_rank,
           row_number() OVER (PARTITION BY company_id ORDER BY trade_date DESC) AS last_rank
    FROM public.price_bars p CROSS JOIN bounds b
    WHERE p.trade_date BETWEEN b.start_date AND b.end_date
)
SELECT c.symbol, v.available_first, v.available_last, v.available_count,
       min(p.trade_date) AS first_date, max(p.trade_date) AS last_date,
       count(p.price_id) AS session_count,
       max(p.close) FILTER (WHERE first_rank = 1) AS first_close,
       max(p.close) FILTER (WHERE last_rank = 1) AS last_close,
       CASE WHEN count(p.price_id) >= 2
                  AND max(p.close) FILTER (WHERE first_rank = 1) <> 0
            THEN max(p.close) FILTER (WHERE last_rank = 1)
               - max(p.close) FILTER (WHERE first_rank = 1) END AS change,
       CASE WHEN count(p.price_id) >= 2 THEN round(
           (max(p.close) FILTER (WHERE last_rank = 1)
            - max(p.close) FILTER (WHERE first_rank = 1))
           / nullif(max(p.close) FILTER (WHERE first_rank = 1), 0) * 100, 2
       ) END AS change_percent,
       array_agg(DISTINCT p.price_scale) FILTER (WHERE p.price_id IS NOT NULL) AS price_scales,
       array_agg(DISTINCT p.is_adjusted) FILTER (WHERE p.price_id IS NOT NULL) AS adjusted_flags,
       array_agg(DISTINCT p.price_id::text) FILTER (WHERE first_rank = 1) AS first_price_ids,
       array_agg(DISTINCT p.price_id::text) FILTER (WHERE last_rank = 1) AS last_price_ids
FROM public.companies c
JOIN coverage v USING (company_id)
LEFT JOIN sample p USING (company_id)
GROUP BY c.symbol, v.available_first, v.available_last, v.available_count
ORDER BY c.symbol;

-- 2. Toàn bộ nến trong mẫu và chuỗi truy nguồn.
WITH bounds AS (
    SELECT DATE '2026-01-01' AS start_date, DATE '2026-10-29' AS end_date
)
SELECT c.symbol, c.company_name, p.price_id, p.company_id, p.trade_date,
       p.open, p.high, p.low, p.close, p.volume, p.price_scale, p.is_adjusted,
       p.payload_id, r.source_uri, r.sha256 AS source_sha256,
       r.job_id, j.source_id, s.name AS source_name, s.approval_status
FROM public.price_bars p
JOIN public.companies c USING (company_id)
LEFT JOIN public.raw_payloads r USING (payload_id)
LEFT JOIN public.ingestion_jobs j USING (job_id)
LEFT JOIN public.sources s USING (source_id)
CROSS JOIN bounds b
WHERE p.trade_date BETWEEN b.start_date AND b.end_date
ORDER BY c.symbol, p.trade_date;

ROLLBACK;
