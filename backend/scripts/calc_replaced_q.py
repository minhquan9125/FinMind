import os, asyncio, asyncpg
from dotenv import load_dotenv

load_dotenv('backend/.env')
load_dotenv('.env')

async def main():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'], ssl='require', statement_cache_size=0, timeout=10)
    
    # Q14: MBB volume trung binh 20 phien gan nhat (den 2026-10-06)
    mbb_20 = await conn.fetch("""
        SELECT trade_date, volume, close
        FROM public.price_bars p
        JOIN public.companies c USING(company_id)
        WHERE c.symbol = 'MBB'
        ORDER BY trade_date DESC
        LIMIT 20
    """)
    avg_vol_mbb = sum(r['volume'] for r in mbb_20) / len(mbb_20)
    print(f"Q14: MBB 20 phien gan nhat: min_date={mbb_20[-1]['trade_date']}, max_date={mbb_20[0]['trade_date']}")
    print(f"     Average Volume MBB 20 phien = {avg_vol_mbb:,.0f} co phieu/phien")
    
    # Q16: So sanh bien dong thang 9/2026 giua VCB, MBB, FPT
    # Tu 2026-09-01 den 2026-09-30
    for sym in ['VCB', 'MBB', 'FPT']:
        bars = await conn.fetch("""
            SELECT trade_date, close
            FROM public.price_bars p
            JOIN public.companies c USING(company_id)
            WHERE c.symbol = $1 AND trade_date >= '2026-09-01' AND trade_date <= '2026-09-30'
            ORDER BY trade_date ASC
        """, sym)
        first_c = bars[0]['close']
        last_c = bars[-1]['close']
        diff = last_c - first_c
        pct = (diff / first_c) * 100
        print(f"Q16: {sym} thang 9/2026 ({bars[0]['trade_date']} -> {bars[-1]['trade_date']}): start={first_c}, end={last_c}, diff={diff:.2f} ({pct:.2f}%)")
        
    # Q17: FPT bien do phien (High - Low) lon nhat
    fpt_ranges = await conn.fetch("""
        SELECT trade_date, open, high, low, close, (high - low) as spread
        FROM public.price_bars p
        JOIN public.companies c USING(company_id)
        WHERE c.symbol = 'FPT'
        ORDER BY (high - low) DESC
        LIMIT 3
    """)
    print("Q17: FPT max daily spread:")
    for r in fpt_ranges:
        print(f"     date={r['trade_date']}, high={r['high']}, low={r['low']}, spread={r['spread']:.2f} (x1000 VND)")

    await conn.close()

asyncio.run(main())
