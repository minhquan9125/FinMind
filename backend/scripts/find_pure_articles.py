import asyncio, os, sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv('backend/.env')
import asyncpg

async def check():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'], ssl='require')
    
    rows = await conn.fetch("""
        SELECT article_id, source, title, published_at, symbols, content
        FROM public.news_articles
        ORDER BY published_at DESC
    """)
    
    approved = {'VCB', 'BID', 'CTG', 'MBB', 'TCB', 'FPT', 'CMG', 'ELC', 'ITD', 'ICT'}
    
    pure_articles = []
    for r in rows:
        syms = set(r['symbols'] or [])
        if syms and syms.issubset(approved):
            pure_articles.append(r)
            
    print(f"Total pure approved articles: {len(pure_articles)}")
    for i, a in enumerate(pure_articles):
        pub = a['published_at'].strftime('%Y-%m-%d') if a['published_at'] else 'N/A'
        print(f"{i+1}. [{pub}] [{a['source']}] {a['symbols']} -> {a['title']}")

    await conn.close()

if __name__ == '__main__':
    asyncio.run(check())
