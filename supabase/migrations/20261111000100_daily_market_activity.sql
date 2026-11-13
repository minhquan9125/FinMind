-- PostgreSQL daily activity; raw quote and per-field provenance stay traceable.
CREATE TABLE IF NOT EXISTS public.daily_market_activity (
 company_id uuid NOT NULL REFERENCES public.companies(company_id),
 trade_date date NOT NULL,
 source_id uuid NOT NULL REFERENCES public.sources(source_id),
 volume bigint CHECK (volume >= 0),
 total_value_vnd numeric(24,4) CHECK (total_value_vnd >= 0 AND total_value_vnd < 1e20),
 foreign_buy_volume bigint CHECK (foreign_buy_volume >= 0),
 foreign_sell_volume bigint CHECK (foreign_sell_volume >= 0),
 foreign_buy_value_vnd numeric(24,4) CHECK (foreign_buy_value_vnd >= 0 AND foreign_buy_value_vnd < 1e20),
 foreign_sell_value_vnd numeric(24,4) CHECK (foreign_sell_value_vnd >= 0 AND foreign_sell_value_vnd < 1e20),
 volume_basis text NOT NULL DEFAULT 'unknown' CHECK (volume_basis IN ('unknown','matched','total')),
 value_basis text NOT NULL DEFAULT 'unknown' CHECK (value_basis IN ('unknown','matched','total')),
 observation_status text NOT NULL CHECK (observation_status IN ('intraday','after_close')),
 quality_status text NOT NULL DEFAULT 'pending_reconciliation' CHECK (quality_status IN ('pending_reconciliation','validated')),
 source_updated_at timestamptz,
 fetched_at timestamptz NOT NULL,
 payload_id uuid NOT NULL REFERENCES public.raw_payloads(payload_id),
 field_payload_ids jsonb NOT NULL DEFAULT '{}'::jsonb,
 revision integer NOT NULL DEFAULT 1 CHECK (revision > 0),
 updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(company_id,trade_date,source_id)
);
CREATE INDEX IF NOT EXISTS daily_market_activity_source_date
 ON public.daily_market_activity(source_id,trade_date DESC);
ALTER TABLE public.daily_market_activity ENABLE ROW LEVEL SECURITY;
