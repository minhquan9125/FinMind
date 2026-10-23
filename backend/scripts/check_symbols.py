import os, asyncio, asyncpg
from dotenv import load_dotenv

load_dotenv('backend/.env')
load_dotenv('.env')

async def main():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'], ssl='require', statement_cache_size=0, timeout=10)
    comps = await conn.fetch("SELECT symbol FROM public.companies ORDER BY symbol")
    print("Companies in DB:", [r['symbol'] for r in comps])
    
    # Check symbols in price_bars
    price_symbols = await conn.fetch("SELECT DISTINCT c.symbol FROM public.price_bars p JOIN public.companies c USING(company_id) ORDER BY c.symbol")
    print("Symbols in price_bars:", [r['symbol'] for r in price_symbols])
    
    # Check symbols in news_articles
    news_symbols = await conn.fetch("SELECT DISTINCT jsonb_array_elements_text(symbols) as s FROM public.news_articles WHERE symbols IS NOT NULL ORDER BY s")
    print("Symbols in news_articles (sample 15):", [r['s'] for r in news_symbols[:15]])
    
    await conn.close()

asyncio.run(main())
