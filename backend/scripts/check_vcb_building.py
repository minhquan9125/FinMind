import asyncio, os, sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv('backend/.env')
import asyncpg

async def check():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'], ssl='require')
    r = await conn.fetchrow("SELECT title, published_at, source, symbols, content FROM public.news_articles WHERE title ILIKE '%viết code bằng AI%'")
    if r:
        print(f"Title: {r['title']}")
        print(f"Date: {r['published_at']} | Source: {r['source']} | Syms: {r['symbols']}")
        print(f"Content:\n{r['content'][:1200]}")
    await conn.close()

if __name__ == '__main__':
    asyncio.run(check())
