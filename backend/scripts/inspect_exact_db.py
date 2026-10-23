import asyncio, os, sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv('backend/.env')
import asyncpg

async def check():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'], ssl='require')

    print('=== ALL COMPANIES ===')
    comps = await conn.fetch("SELECT * FROM public.companies ORDER BY symbol")
    comp_map = {}
    for comp in comps:
        print(f"  {comp['symbol']}: {comp['company_id']} ({comp['company_name']})")
        comp_map[comp['company_id']] = comp['symbol']

    print('\n=== PRICE_BARS BY COMPANY ===')
    rows = await conn.fetch("""
        SELECT company_id, MIN(trade_date) as min_date, MAX(trade_date) as max_date, COUNT(*) as cnt
        FROM public.price_bars
        GROUP BY company_id
    """)
    for r in rows:
        sym = comp_map.get(r['company_id'], str(r['company_id']))
        print(f"  {sym}: {r['min_date']} to {r['max_date']} ({r['cnt']} bars)")

    # Kiểm tra VCB
    print('\n=== VCB FIRST & LAST BARS ===')
    vcb_id = [cid for cid, s in comp_map.items() if s == 'VCB'][0]
    r_first = await conn.fetchrow("SELECT * FROM public.price_bars WHERE company_id=$1 ORDER BY trade_date ASC LIMIT 1", vcb_id)
    r_last = await conn.fetchrow("SELECT * FROM public.price_bars WHERE company_id=$1 ORDER BY trade_date DESC LIMIT 1", vcb_id)
    print(f"  VCB first: date={r_first['trade_date']}, close={r_first['close']}, open={r_first['open']}")
    print(f"  VCB last:  date={r_last['trade_date']}, close={r_last['close']}")

    # Kiểm tra MBB max volume
    mbb_id = [cid for cid, s in comp_map.items() if s == 'MBB'][0]
    r_mbb_max = await conn.fetchrow("SELECT trade_date, volume, close FROM public.price_bars WHERE company_id=$1 ORDER BY volume DESC LIMIT 1", mbb_id)
    print(f"  MBB max volume: date={r_mbb_max['trade_date']}, volume={r_mbb_max['volume']}, close={r_mbb_max['close']}")

    # Kiểm tra FPT highest & lowest close
    fpt_id = [cid for cid, s in comp_map.items() if s == 'FPT'][0]
    r_fpt_high = await conn.fetchrow("SELECT trade_date, close FROM public.price_bars WHERE company_id=$1 ORDER BY close DESC LIMIT 1", fpt_id)
    r_fpt_low = await conn.fetchrow("SELECT trade_date, close FROM public.price_bars WHERE company_id=$1 ORDER BY close ASC LIMIT 1", fpt_id)
    print(f"  FPT highest close: date={r_fpt_high['trade_date']}, close={r_fpt_high['close']}")
    print(f"  FPT lowest close:  date={r_fpt_low['trade_date']}, close={r_fpt_low['close']}")

    # Kiểm tra VCB 2026-05-20 & 2026-04-23
    r_vcb_may20 = await conn.fetchrow("SELECT * FROM public.price_bars WHERE company_id=$1 AND trade_date='2026-05-20'", vcb_id)
    if r_vcb_may20:
        print(f"  VCB 2026-05-20: O={r_vcb_may20['open']}, H={r_vcb_may20['high']}, L={r_vcb_may20['low']}, C={r_vcb_may20['close']}, vol={r_vcb_may20['volume']}")
    r_vcb_apr23 = await conn.fetchrow("SELECT * FROM public.price_bars WHERE company_id=$1 AND trade_date='2026-04-23'", vcb_id)
    if r_vcb_apr23:
        print(f"  VCB 2026-04-23: O={r_vcb_apr23['open']}, H={r_vcb_apr23['high']}, L={r_vcb_apr23['low']}, C={r_vcb_apr23['close']}, vol={r_vcb_apr23['volume']}")

    # Kiểm tra FPT intraday max spread
    r_fpt_spread = await conn.fetchrow("""
        SELECT trade_date, high, low, (high - low) as spread 
        FROM public.price_bars 
        WHERE company_id=$1 
        ORDER BY (high - low) DESC LIMIT 1
    """, fpt_id)
    print(f"  FPT max spread: date={r_fpt_spread['trade_date']}, high={r_fpt_spread['high']}, low={r_fpt_spread['low']}, spread={r_fpt_spread['spread']}")

    # Kiểm tra MBB SMA20 volume up to 2026-10-06
    rows_mbb_20 = await conn.fetch("""
        SELECT trade_date, volume 
        FROM public.price_bars 
        WHERE company_id=$1 AND trade_date <= '2026-10-06'
        ORDER BY trade_date DESC LIMIT 20
    """, mbb_id)
    vols = [r['volume'] for r in rows_mbb_20]
    avg_vol = sum(vols) / len(vols)
    print(f"  MBB 20 bars up to 2026-10-06: avg_vol={avg_vol:.0f}, total={sum(vols)}")
    print(f"    From {rows_mbb_20[-1]['trade_date']} to {rows_mbb_20[0]['trade_date']}")

    # Kiểm tra VCB, MBB, FPT tháng 9/2026
    print('\n=== SEPTEMBER 2026 CHANGES ===')
    for sym, cid in [('VCB', vcb_id), ('MBB', mbb_id), ('FPT', fpt_id)]:
        r_start = await conn.fetchrow("SELECT trade_date, close FROM public.price_bars WHERE company_id=$1 AND trade_date >= '2026-09-01' ORDER BY trade_date ASC LIMIT 1", cid)
        r_end = await conn.fetchrow("SELECT trade_date, close FROM public.price_bars WHERE company_id=$1 AND trade_date <= '2026-09-30' ORDER BY trade_date DESC LIMIT 1", cid)
        pct = (r_end['close'] - r_start['close']) / r_start['close'] * 100
        print(f"  {sym}: start={r_start['trade_date']} close={r_start['close']} -> end={r_end['trade_date']} close={r_end['close']} | change={pct:.2f}%")

    await conn.close()

asyncio.run(check())
