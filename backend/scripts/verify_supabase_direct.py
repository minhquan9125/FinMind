import os
import sys
import json
import asyncio
from pathlib import Path

PROJECT_ROOT = Path("c:/Users/dieuh/Downloads/duan/FinMind")
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

async def main():
    import asyncpg
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / "backend/.env")
    load_dotenv(PROJECT_ROOT / ".env")
    
    conn = await asyncpg.connect(os.environ["DATABASE_URL"], ssl="require", statement_cache_size=0, timeout=15)
    
    out_lines = []
    def log(msg):
        out_lines.append(msg)
        try:
            print(msg.encode('ascii', 'replace').decode('ascii'))
        except Exception:
            pass

    log("=" * 80)
    log("KIEM TRA DONG NHAT GIUA BO CAU HOI VA DATA TREN SUPABASE")
    log("=" * 80)
    
    # -------------------------------------------------------------
    # LO 1: TIN TUC (news_articles)
    # -------------------------------------------------------------
    log("\n>>> [LO 1: TIN TUC - news_articles]")
    news_count = await conn.fetchval("SELECT count(*) FROM public.news_articles")
    log(f"Tong so bai tin trong public.news_articles: {news_count}")
    
    # Q01: MSN 28/09/2026 MBS
    q1 = await conn.fetch("""
        SELECT article_id, title, published_at, source, content 
        FROM public.news_articles 
        WHERE published_at::date = '2026-09-28' AND (title ILIKE '%MBS%' OR title ILIKE '%Masan%' OR content ILIKE '%3.984%')
        LIMIT 1
    """)
    if q1:
        row = q1[0]
        has_3984 = "3.984" in row["content"]
        has_230 = "230%" in row["content"]
        has_nuiphao = "Núi Pháo" in row["content"]
        log(f"Q01 (MSN MBS): [KHOP 100%] Title: '{row['title']}' | 3.984 ti: {has_3984} | 230%: {has_230} | Nui Phao: {has_nuiphao}")
    else:
        log("Q01: [CHUA TIM THAY BAI THEO FILTER]")

    # Q02: CTR 29/07/2026
    q2 = await conn.fetch("""
        SELECT title, content FROM public.news_articles 
        WHERE published_at::date = '2026-07-29' AND (title ILIKE '%quân đội%' OR content ILIKE '%7.959%')
        LIMIT 1
    """)
    if q2:
        row = q2[0]
        has_7959 = "7.959" in row["content"]
        has_402 = "402" in row["content"]
        log(f"Q02 (CTR H1/26): [KHOP] Title: '{row['title'][:50]}' | 7.959 ti: {has_7959} | 402 ti: {has_402}")
    else:
        log("Q02: [CHUA TIM THAY]")

    # Q03: FPT phat hanh co phieu 29/09/2026
    q3 = await conn.fetch("""
        SELECT title, content FROM public.news_articles 
        WHERE content ILIKE '%171,4%' OR content ILIKE '%181.748%'
        LIMIT 1
    """)
    if q3:
        row = q3[0]
        log(f"Q03 (FPT Phat hanh): [KHOP] Title: '{row['title'][:50]}'")
    else:
        log("Q03: [CHUA TIM THAY]")

    # Q09: CTR no xau 15/09/2026
    q9 = await conn.fetch("""
        SELECT title, content FROM public.news_articles 
        WHERE content ILIKE '%97,4%' OR (published_at::date = '2026-09-15' AND content ILIKE '%Faros%')
        LIMIT 1
    """)
    if q9:
        row = q9[0]
        log(f"Q09 (CTR no xau): [KHOP] Title: '{row['title'][:50]}'")
    else:
        log("Q09: [CHUA TIM THAY]")
        
    # Q10: Dem theo source
    src_dist = await conn.fetch("SELECT source, count(*) as cnt FROM public.news_articles GROUP BY source")
    log(f"Q10 (Phan bo nguon trong DB): {[dict(r) for r in src_dist]}")

    # -------------------------------------------------------------
    # LO 2: GIA CO PHIEU (price_bars)
    # -------------------------------------------------------------
    log("\n>>> [LO 2: GIA CO PHIEU - price_bars]")
    price_count = await conn.fetchval("SELECT count(*) FROM public.price_bars")
    log(f"Tong so ban ghi price_bars: {price_count}")
    
    # Q11: VCB 06/10/2026 vs 09/04/2026
    p_vcb_first = await conn.fetchrow("SELECT trade_date, close FROM public.price_bars JOIN public.companies c USING(company_id) WHERE c.symbol='VCB' ORDER BY trade_date ASC LIMIT 1")
    p_vcb_last = await conn.fetchrow("SELECT trade_date, close FROM public.price_bars JOIN public.companies c USING(company_id) WHERE c.symbol='VCB' ORDER BY trade_date DESC LIMIT 1")
    log(f"Q11 (VCB start/end): First date={p_vcb_first['trade_date']}, close={p_vcb_first['close']} | Last date={p_vcb_last['trade_date']}, close={p_vcb_last['close']}")
    
    # Q13: FPT High / Low
    p_fpt_high = await conn.fetchrow("SELECT trade_date, high, close FROM public.price_bars JOIN public.companies c USING(company_id) WHERE c.symbol='FPT' ORDER BY close DESC LIMIT 1")
    p_fpt_low = await conn.fetchrow("SELECT trade_date, low, close FROM public.price_bars JOIN public.companies c USING(company_id) WHERE c.symbol='FPT' ORDER BY close ASC LIMIT 1")
    log(f"Q13 (FPT Extreme close): Highest close date={p_fpt_high['trade_date']}, close={p_fpt_high['close']} | Lowest close date={p_fpt_low['trade_date']}, close={p_fpt_low['close']}")

    # Q15: VCB 2026-09-25
    p_vcb_sep25 = await conn.fetchrow("SELECT p.* FROM public.price_bars p JOIN public.companies c USING(company_id) WHERE c.symbol='VCB' AND trade_date = '2026-09-25'")
    if p_vcb_sep25:
        log(f"Q15 (VCB 2026-09-25): open={p_vcb_sep25['open']}, high={p_vcb_sep25['high']}, low={p_vcb_sep25['low']}, close={p_vcb_sep25['close']}, vol={p_vcb_sep25['volume']}")
    else:
        log("Q15: [KHONG THAY PHIEN 2026-09-25]")

    # Q19: VCB Volume ky luc
    p_vcb_maxvol = await conn.fetchrow("SELECT trade_date, volume, open, high, low, close FROM public.price_bars JOIN public.companies c USING(company_id) WHERE c.symbol='VCB' ORDER BY volume DESC LIMIT 1")
    log(f"Q19 (VCB Max Volume): date={p_vcb_maxvol['trade_date']}, volume={p_vcb_maxvol['volume']:,}, close={p_vcb_maxvol['close']}")

    # Q20: MBB 2026-09-30 vs 2026-10-06
    p_mbb_1 = await conn.fetchrow("SELECT trade_date, close FROM public.price_bars JOIN public.companies c USING(company_id) WHERE c.symbol='MBB' AND trade_date = '2026-09-30'")
    p_mbb_2 = await conn.fetchrow("SELECT trade_date, close FROM public.price_bars JOIN public.companies c USING(company_id) WHERE c.symbol='MBB' AND trade_date = '2026-10-06'")
    if p_mbb_1 and p_mbb_2:
        diff = p_mbb_2['close'] - p_mbb_1['close']
        pct = (diff / p_mbb_1['close']) * 100
        log(f"Q20 (MBB): 30/09 close={p_mbb_1['close']} | 06/10 close={p_mbb_2['close']} | Diff={diff:.2f} ({pct:.2f}%)")

    # -------------------------------------------------------------
    # LO 3: TAI LIEU PDF & DOCUMENTS
    # -------------------------------------------------------------
    log("\n>>> [LO 3: TAI LIEU BCTN/BCTC PDF - documents]")
    docs = await conn.fetch("SELECT doc_type, count(*) as cnt FROM public.documents GROUP BY doc_type")
    log(f"Phan bo doc_type trong public.documents: {[dict(r) for r in docs]}")
    fpt_pdf_docs = await conn.fetch("SELECT document_id, title, doc_type, external_id FROM public.documents WHERE title ILIKE '%FPT%' OR external_id ILIKE '%FPT%'")
    log(f"Tai lieu FPT trong public.documents: {len(fpt_pdf_docs)} tai lieu")
    for d in fpt_pdf_docs[:5]:
        log(f"  - [{d['doc_type']}] {d['title']}")

    log("\n>>> [LO 4: BCTC CO CAU TRUC - observations]")
    obs_cols = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'observations'")
    log(f"Cac cot cua observations: {[r['column_name'] for r in obs_cols]}")
    metric_cols = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'metrics'")
    log(f"Cac cot cua metrics: {[r['column_name'] for r in metric_cols]}")
    period_cols = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'reporting_periods'")
    log(f"Cac cot cua reporting_periods: {[r['column_name'] for r in period_cols]}")
    
    fpt_q2_obs = await conn.fetch("""
        SELECT m.code, m.canonical_name, o.value 
        FROM public.observations o
        JOIN public.financial_reports r ON o.report_id = r.report_id
        JOIN public.companies c ON r.company_id = c.company_id
        JOIN public.metrics m ON o.metric_id = m.metric_id
        JOIN public.reporting_periods p ON r.period_id = p.period_id
        WHERE c.symbol = 'FPT' AND p.period_code = '2026-Q2'
        AND m.code IN (
            'CASH_AND_CASH_EQUIVALENTS',
            'SHORT_TERM_LOANS_AND_FINANCE_LEASES', 
            'RETAINED_EARNINGS', 
            'NET_REVENUE', 
            'PARENT_NET_PROFIT', 
            'BASIC_EARNINGS_PER_SHARE',
            'CASH_FLOW_OPERATING',
            'PURCHASE_FIXED_ASSETS',
            'ROE',
            'GROSS_MARGIN'
        )
    """)
    log(f"So metrics quan trong cua FPT 2026-Q2 tim thay trong Supabase: {len(fpt_q2_obs)}/10")
    for r in fpt_q2_obs:
        log(f"  * {r['code']} ({r['canonical_name']}): {r['value']:,}")

    await conn.close()
    
    report_file = PROJECT_ROOT / "docs/review/supabase_crosscheck_report.txt"
    report_file.write_text("\n".join(out_lines), encoding="utf-8")
    print("\nREPORT WRITTEN TO: " + str(report_file))

if __name__ == '__main__':
    asyncio.run(main())
