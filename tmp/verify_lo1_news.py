import asyncio
import os
import sys
import asyncpg
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv(".env")
load_dotenv("backend/.env")

DATABASE_URL = os.environ.get("DATABASE_URL")

async def verify_news():
    print("Connecting to Supabase database...")
    conn = await asyncpg.connect(DATABASE_URL, ssl="require", statement_cache_size=0, timeout=20)
    print("Connected successfully!\n")

    queries = [
        ("Q01", "TCB bond buyback 4.240 tỷ, TCB12517, TCB12518",
         """SELECT article_id, title, published_at, source, symbols, content 
            FROM public.news_articles 
            WHERE title ILIKE '%tất toán%trái phiếu%' OR content ILIKE '%TCB12517%'"""),
            
        ("Q02", "CTG lãi suất 0,1-6%, gửi 300 tr nhận 36 tr",
         """SELECT article_id, title, published_at, source, symbols, content 
            FROM public.news_articles 
            WHERE title ILIKE '%300 triệu%36 triệu%' OR content ILIKE '%300 triệu đồng nhận 36 triệu%'"""),

        ("Q03", "FPT 171,4 triệu cổ phiếu cho 181.748 cổ đông",
         """SELECT article_id, title, published_at, source, symbols, content 
            FROM public.news_articles 
            WHERE content ILIKE '%171,4 triệu%' AND content ILIKE '%181.748%'"""),

        ("Q04", "FPT Toyota Tsusho NEXTY Electronics 44 ngày",
         """SELECT article_id, title, published_at, source, symbols, content 
            FROM public.news_articles 
            WHERE content ILIKE '%NEXTY Electronics%' OR title ILIKE '%Toyota%FPT%'"""),

        ("Q05", "SSI Research CTG 13.500 tỷ LNTT (+27%), VCB 12.800 tỷ (+14%)",
         """SELECT article_id, title, published_at, source, symbols, content 
            FROM public.news_articles 
            WHERE content ILIKE '%13.500 tỷ đồng lợi nhuận trước thuế%' OR (content ILIKE '%13.500%' AND content ILIKE '%12.800%')"""),

        ("Q06", "MBB tài sản > 1,73 triệu tỷ, 8 doanh nghiệp thành viên",
         """SELECT article_id, title, published_at, source, symbols, content 
            FROM public.news_articles 
            WHERE content ILIKE '%1 73 triệu tỷ%' OR (title ILIKE '%kết nối dòng vốn%' AND content ILIKE '%8 doanh nghiệp%')"""),

        ("Q07", "TCB tăng vốn 35.730,97 tỷ (cổ tức 35.431 tỷ, ESOP 300 tỷ, vốn 106.593 tỷ)",
         """SELECT article_id, title, published_at, source, symbols, content 
            FROM public.news_articles 
            WHERE content ILIKE '%35.730,97%' OR content ILIKE '%106.593%'"""),

        ("Q08", "VCB tháp 35 tầng VCB Tower (Setra 1.202 tỷ + Bonday 2.004 tỷ = 3.206 tỷ)",
         """SELECT article_id, title, published_at, source, symbols, content 
            FROM public.news_articles 
            WHERE content ILIKE '%3.206 tỷ%' OR title ILIKE '%35 tầng%trung tâm%Tp.HCM%'"""),

        ("Q09", "TCBS FPT AI viết code nhanh 30% năng suất 10%",
         """SELECT article_id, title, published_at, source, symbols, content 
            FROM public.news_articles 
            WHERE content ILIKE '%nhanh hơn 30% nhưng năng suất%' OR title ILIKE '%nhanh hơn 30%'"""),

        ("Q10", "FPT nhân sự ~90.000 (+3.682, +4,3%), khối BCTC 45.145",
         """SELECT article_id, title, published_at, source, symbols, content 
            FROM public.news_articles 
            WHERE content ILIKE '%45.145%' OR title ILIKE '%90.000 người%3.682%'""")
    ]

    for q_id, desc, sql in queries:
        rows = await conn.fetch(sql)
        print(f"=== {q_id}: {desc} ===")
        if rows:
            r = rows[0]
            print(f"  FOUND: article_id={r['article_id']}")
            print(f"  Title: {r['title']}")
            print(f"  Published_at: {r['published_at']} | Source: {r['source']} | Symbols: {r['symbols']}")
            snippet = r['content'].replace('\n', ' ')[:300]
            print(f"  Snippet: {snippet}...\n")
        else:
            print("  NOT FOUND!\n")

    await conn.close()

asyncio.run(verify_news())
