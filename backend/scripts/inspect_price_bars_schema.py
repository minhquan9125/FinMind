import asyncio, os, sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv('backend/.env')
import asyncpg

async def check():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'], ssl='require')
    cols = await conn.fetch("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'price_bars'
    """)
    print("Columns:")
    for c in cols:
        print(f"  {c['column_name']}: {c['data_type']}")
    
    cons = await conn.fetch("""
        SELECT conname, contype 
        FROM pg_constraint 
        WHERE conrelid = 'public.price_bars'::regclass
    """)
    print("\nConstraints:")
    for c in cons:
        print(f"  Constraint: {c['conname']} ({c['contype']})")
        
    idxs = await conn.fetch("""
        SELECT indexname, indexdef 
        FROM pg_indexes 
        WHERE tablename = 'price_bars'
    """)
    print("\nIndexes:")
    for i in idxs:
        print(f"  Index: {i['indexname']} -> {i['indexdef']}")
        
    # Check sample row in price_bars
    payload = await conn.fetchrow("SELECT source_uri, stored_at, octet_length(payload::text) as size FROM public.raw_payloads WHERE payload_id = '059e8db8-e156-5640-9203-a122e2eb5941'")
    if payload:
        print(f"\nPayload 059e8db8: {dict(payload)}")
        
    print("\nAll raw_payloads:")
    payloads = await conn.fetch("SELECT payload_id, source_uri, stored_at FROM public.raw_payloads ORDER BY stored_at DESC LIMIT 10")
    for p in payloads:
        print(f"  {p['payload_id']} | {p['source_uri']}")
        
    print("\nSources in DB:")
    sources = await conn.fetch("SELECT * FROM public.sources")
    for s in sources:
        print(f"  {dict(s)}")
        
    await conn.close()

if __name__ == '__main__':
    asyncio.run(check())
