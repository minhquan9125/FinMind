import asyncio, os, sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv('backend/.env')
import asyncpg

async def check():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'], ssl='require')
    
    # 1. Article Cho vay du an BDT (VCB)
    r1 = await conn.fetchrow("SELECT title, published_at, source, symbols, content FROM public.news_articles WHERE title ILIKE '%Cho vay dự án bất động sản%'")
    if r1:
        print("=== ARTICLE 1: VCB ===")
        print(f"Title: {r1['title']}")
        print(f"Symbols: {r1['symbols']}")
        print(f"Content:\n{r1['content'][:800]}\n")
        
    # 2. Article Co tuc BID
    r2 = await conn.fetchrow("SELECT title, published_at, source, symbols, content FROM public.news_articles WHERE title ILIKE '%Lịch chốt quyền trả cổ tức%'")
    if r2:
        print("=== ARTICLE 2: BID ===")
        print(f"Title: {r2['title']}")
        print(f"Symbols: {r2['symbols']}")
        print(f"Content:\n{r2['content'][:800]}\n")

    # 3. Article Q05: Nhung ngan hang co the lai tren 10.000 ty
    r3 = await conn.fetchrow("SELECT title, published_at, source, symbols, content FROM public.news_articles WHERE title ILIKE '%Những ngân hàng có thể lãi trên 10.000 tỷ%'")
    if r3:
        print("=== ARTICLE 3: Q05 ===")
        print(f"Title: {r3['title']}")
        print(f"Symbols: {r3['symbols']}")
        print(f"Content:\n{r3['content'][:800]}\n")

    await conn.close()

if __name__ == '__main__':
    asyncio.run(check())
