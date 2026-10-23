import asyncio, os, sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv('backend/.env')
import asyncpg

async def main():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'], ssl='require')
    
    # Lấy FPT company_id
    fpt_id = await conn.fetchval("SELECT company_id FROM public.companies WHERE symbol = 'FPT'")
    
    # Lấy report_id 2026-Q2 của FPT
    rep_2026_q2 = await conn.fetchval('''
        SELECT r.report_id 
        FROM public.financial_reports r
        JOIN public.reporting_periods p ON r.period_id = p.period_id
        WHERE r.company_id = $1 AND p.fiscal_year = 2026 AND p.quarter = 2
    ''', fpt_id)
    print('FPT 2026-Q2 report_id:', rep_2026_q2)
    
    # Query các metrics của Q31-Q38
    codes = ['CASH_AND_CASH_EQUIVALENTS', 'SHORT_TERM_LOANS_AND_FINANCE_LEASES', 'RETAINED_EARNINGS', 
             'NET_REVENUE', 'PARENT_NET_PROFIT', 'BASIC_EARNINGS_PER_SHARE', 
             'CASH_FLOW_OPERATING', 'PURCHASE_FIXED_ASSETS', 'ROE', 'GROSS_MARGIN']
             
    rows = await conn.fetch('''
        SELECT m.code, m.canonical_name, o.value, o.unit, o.locator_json
        FROM public.observations o
        JOIN public.metrics m ON o.metric_id = m.metric_id
        WHERE o.report_id = $1 AND m.code = ANY($2)
    ''', rep_2026_q2, codes)
    
    for r in rows:
        print(f"{r['code']}: value={r['value']} | unit={r['unit']}")

asyncio.run(main())
