import asyncio, os, sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv('backend/.env')
import asyncpg

async def main():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'], ssl='require')
    
    # 1. Tables in public
    tables = await conn.fetch("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name
    """)
    print('=== TABLES IN PUBLIC ===')
    for t in tables:
        tname = t['table_name']
        try:
            cnt = await conn.fetchval(f"SELECT count(*) FROM public.{tname}")
            print(f"  {tname}: {cnt} rows")
        except Exception as e:
            print(f"  {tname}: error {e}")
        
    # 2. Companies in database
    print('\n=== COMPANIES IN DATABASE ===')
    companies = await conn.fetch('SELECT * FROM public.companies ORDER BY symbol')
    for c in companies:
        print(dict(c))

    # 3. Price bars summary in database
    print('\n=== PRICE BARS IN DATABASE ===')
    p_rows = await conn.fetch("""
        SELECT c.symbol, count(p.*) as count, min(p.trade_date) as min_date, max(p.trade_date) as max_date
        FROM public.price_bars p
        JOIN public.companies c ON p.company_id = c.company_id
        GROUP BY c.symbol
        ORDER BY c.symbol
    """)
    for r in p_rows:
        print(dict(r))

    # 4. News articles summary
    print('\n=== NEWS ARTICLES SUMMARY ===')
    sources = await conn.fetch("""
        SELECT source, count(*) as count, min(published_at) as min_date, max(published_at) as max_date
        FROM public.news_articles
        GROUP BY source
    """)
    for s in sources:
        print(dict(s))

    # 5. Financial reports & observations in database
    print('\n=== FINANCIAL REPORTS IN DATABASE ===')
    reports = await conn.fetch("""
        SELECT c.symbol, count(r.*) as count
        FROM public.financial_reports r
        JOIN public.companies c ON r.company_id = c.company_id
        GROUP BY c.symbol
    """)
    for rep in reports:
        print(dict(rep))

    print('\n=== OBSERVATIONS BY SYMBOL ===')
    obs = await conn.fetch("""
        SELECT c.symbol, count(o.*) as count
        FROM public.observations o
        JOIN public.financial_reports r ON o.report_id = r.report_id
        JOIN public.companies c ON r.company_id = c.company_id
        GROUP BY c.symbol
    """)
    for ob in obs:
        print(dict(ob))

asyncio.run(main())
