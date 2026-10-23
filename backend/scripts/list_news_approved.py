import asyncio, os, sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv('backend/.env')
import asyncpg

APPROVED = ['VCB', 'BID', 'CTG', 'MBB', 'TCB', 'FPT', 'CMG', 'ELC', 'ITD', 'ICT']

async def main():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'], ssl='require')
    
    print('=== ARTICLES FOR EACH APPROVED SYMBOL ===')
    for sym in APPROVED:
        rows = await conn.fetch('''
            SELECT article_id, source, published_at, title, symbols
            FROM public.news_articles
            WHERE $1 = ANY(symbols)
            ORDER BY published_at DESC
        ''', sym)
        print(f"\n[{sym}] - Total: {len(rows)} articles")
        for r in rows[:5]:
            print(f"  {r['published_at'].strftime('%Y-%m-%d')} | {r['source']} | {r['title']} | symbols={r['symbols']}")

asyncio.run(main())
