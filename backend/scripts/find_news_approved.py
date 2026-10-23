import os
import asyncio
import asyncpg
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path("c:/Users/dieuh/Downloads/duan/FinMind")
load_dotenv(PROJECT_ROOT / "backend/.env")
load_dotenv(PROJECT_ROOT / ".env")

async def main():
    conn = await asyncpg.connect(os.environ["DATABASE_URL"], ssl="require", statement_cache_size=0, timeout=15)
    
    symbols = ['VCB', 'BID', 'CTG', 'MBB', 'TCB', 'FPT', 'CMG', 'ELC', 'ITD', 'ICT']
    
    rows = await conn.fetch("""
        SELECT article_id, title, published_at, source, symbols, content
        FROM public.news_articles
        ORDER BY published_at DESC
    """)
    
    out = []
    out.append(f"Total articles in news_articles: {len(rows)}")
    
    matches = {s: [] for s in symbols}
    
    for r in rows:
        content = r['content'] or ''
        title = r['title'] or ''
        syms = r['symbols'] or []
        for s in symbols:
            if s in syms or s in title or f" {s} " in content:
                matches[s].append(r)
                
    for s in symbols:
        out.append(f"\n=== SYMBOL: {s} ({len(matches[s])} articles) ===")
        for a in matches[s][:8]:
            pub = a['published_at'].strftime('%Y-%m-%d') if a['published_at'] else 'N/A'
            src = a['source']
            title = a['title']
            # Find interesting numbers
            excerpt = a['content'][:250].replace('\n', ' ')
            out.append(f"  * [{pub}] [{src}] {title}")
            out.append(f"    -> Excerpt: {excerpt}...")
            
    await conn.close()
    
    target = PROJECT_ROOT / "docs/review/approved_news_found.txt"
    target.write_text("\n".join(out), encoding="utf-8")
    print(f"Results written to: {target}")

if __name__ == '__main__':
    asyncio.run(main())
