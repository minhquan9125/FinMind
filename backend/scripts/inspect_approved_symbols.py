import os
import sys
import asyncio
from pathlib import Path

PROJECT_ROOT = Path("c:/Users/dieuh/Downloads/duan/FinMind")

async def main():
    import asyncpg
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / "backend/.env")
    load_dotenv(PROJECT_ROOT / ".env")
    
    conn = await asyncpg.connect(os.environ["DATABASE_URL"], ssl="require", statement_cache_size=0, timeout=10)
    
    valid_symbols = ['VCB', 'BID', 'CTG', 'MBB', 'TCB', 'FPT', 'CMG', 'ELC', 'ITD', 'ICT']
    print(f"=== CHECKING 10 APPROVED SYMBOLS: {valid_symbols} ===")
    
    # 1. Check companies
    comp_rows = await conn.fetch("SELECT symbol, company_name, industry_type, sector FROM public.companies WHERE symbol = ANY($1) ORDER BY symbol", valid_symbols)
    print(f"\n1. Companies found in DB ({len(comp_rows)}/10):")
    for r in comp_rows:
        msg = f"  - {r['symbol']}: {r['company_name']} | Industry: {r['industry_type']}"
        print(msg.encode('ascii', 'replace').decode('ascii'))
        
    # 2. Check price_bars
    price_rows = await conn.fetch("""
        SELECT c.symbol, count(p.price_id) as bar_count, min(p.trade_date) as min_date, max(p.trade_date) as max_date
        FROM public.price_bars p
        JOIN public.companies c USING(company_id)
        WHERE c.symbol = ANY($1)
        GROUP BY c.symbol
        ORDER BY c.symbol
    """, valid_symbols)
    print(f"\n2. Price bars in DB ({len(price_rows)}/10 symbols have bars):")
    for r in price_rows:
        print(f"  - {r['symbol']}: {r['bar_count']} bars (from {r['min_date']} to {r['max_date']})")
        
    # Check normalized JSON files
    norm_dir = PROJECT_ROOT / "data/normalized"
    print(f"\n3. Checking data/normalized/ directory:")
    if norm_dir.exists():
        files = list(norm_dir.glob("*.json"))
        print(f"  Found {len(files)} normalized files: {[f.name for f in files]}")
    else:
        print(f"  Directory data/normalized does not exist")
        
    # Check data_pipeline/FinancialCleaner/data
    clean_dir = PROJECT_ROOT / "data_pipeline/FinancialCleaner/data"
    if clean_dir.exists():
        subdirs = [d.name for d in clean_dir.iterdir() if d.is_dir()]
        print(f"\n4. FinancialCleaner symbols in {clean_dir}:")
        print(f"  {subdirs}")
        
    # 5. Check news_articles
    print(f"\n5. News articles mentioning approved symbols:")
    for sym in valid_symbols:
        news_items = await conn.fetch("""
            SELECT article_id, title, published_at, source 
            FROM public.news_articles 
            WHERE symbols @> ARRAY[$1]::varchar[] OR symbols @> ARRAY[$1]::text[] OR title ILIKE $2
            ORDER BY published_at DESC
            LIMIT 5
        """, sym, f"%{sym}%")
        print(f"  - {sym}: {len(news_items)} recent articles found")
        for n in news_items[:2]:
            msg = f"      [{n['published_at'].strftime('%Y-%m-%d')}] [{n['source']}] {n['title'][:70]}"
            print(msg.encode('ascii', 'replace').decode('ascii'))
            
    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
