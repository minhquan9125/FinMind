import asyncio, os, sys, json
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv('backend/.env')
import asyncpg

async def check():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'], ssl='require')
    vcb_id = await conn.fetchval("SELECT company_id FROM public.companies WHERE symbol='VCB'")
    cnt = await conn.fetchval("SELECT count(1) FROM public.price_bars WHERE company_id=$1", vcb_id)
    r_first = await conn.fetchrow("SELECT * FROM public.price_bars WHERE company_id=$1 ORDER BY trade_date ASC LIMIT 1", vcb_id)
    r_last = await conn.fetchrow("SELECT * FROM public.price_bars WHERE company_id=$1 ORDER BY trade_date DESC LIMIT 1", vcb_id)
    print(f'VCB in price_bars count: {cnt}')
    print(f'First bar: date={r_first["trade_date"]}, close={r_first["close"]}, open={r_first["open"]}')
    print(f'Last bar:  date={r_last["trade_date"]}, close={r_last["close"]}')
    
    # Check 2026-05-20 and 2026-04-23
    r_may20 = await conn.fetchrow("SELECT * FROM public.price_bars WHERE company_id=$1 AND trade_date='2026-05-20'", vcb_id)
    if r_may20:
        print(f"2026-05-20: O={r_may20['open']}, H={r_may20['high']}, L={r_may20['low']}, C={r_may20['close']}, V={r_may20['volume']}")
    r_apr23 = await conn.fetchrow("SELECT * FROM public.price_bars WHERE company_id=$1 AND trade_date='2026-04-23'", vcb_id)
    if r_apr23:
        print(f"2026-04-23: O={r_apr23['open']}, H={r_apr23['high']}, L={r_apr23['low']}, C={r_apr23['close']}, V={r_apr23['volume']}")
    await conn.close()

if __name__ == '__main__':
    asyncio.run(check())
