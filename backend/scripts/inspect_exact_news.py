import asyncio, os, sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv('backend/.env')
import asyncpg

async def check():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'], ssl='require')
    rows = await conn.fetch("SELECT title, published_at, source, content FROM public.news_articles WHERE content ILIKE '%4.240%' OR content ILIKE '%TCB12517%' OR title ILIKE '%Techcombank%'")
    for r in rows:
        print(f"TITLE: {r['title']}")
        print(f"Date: {r['published_at']} | Source: {r['source']}")
        print(f"Snippet: {r['content'][:400]}\n")
    await conn.close()

asyncio.run(check())
