import asyncio, os, sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv('backend/.env')
import asyncpg

async def check():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'], ssl='require')
    
    print("=== VERIFY LÔ 2 DIRECTLY ON SUPABASE price_bars ===")
    
    # Q11: VCB 2018-01-02 vs 2026-09-25
    r_vcb_first = await conn.fetchrow("""
        SELECT close FROM public.price_bars p JOIN public.companies c ON p.company_id=c.company_id
        WHERE c.symbol='VCB' AND p.trade_date='2018-01-02'
    """)
    r_vcb_sep25 = await conn.fetchrow("""
        SELECT close FROM public.price_bars p JOIN public.companies c ON p.company_id=c.company_id
        WHERE c.symbol='VCB' AND p.trade_date='2026-09-25'
    """)
    c1, c2 = float(r_vcb_first['close']), float(r_vcb_sep25['close'])
    pct11 = (c2 - c1) / c1 * 100
    print(f"Q11 VCB: first={c1}, sep25={c2}, change={pct11:.2f}% (Expected: 23.06, 58.0, +151.52%)")
    
    # Q12: MBB max volume
    r_mbb_max = await conn.fetchrow("""
        SELECT trade_date, volume, close FROM public.price_bars p JOIN public.companies c ON p.company_id=c.company_id
        WHERE c.symbol='MBB' ORDER BY volume DESC LIMIT 1
    """)
    print(f"Q12 MBB max vol: date={r_mbb_max['trade_date']}, vol={r_mbb_max['volume']}, close={r_mbb_max['close']} (Expected: 2025-08-15, 117471296, 22.62)")
    
    # Q13: FPT highest & lowest close
    r_fpt_max = await conn.fetchrow("""
        SELECT trade_date, close FROM public.price_bars p JOIN public.companies c ON p.company_id=c.company_id
        WHERE c.symbol='FPT' ORDER BY close DESC LIMIT 1
    """)
    r_fpt_min = await conn.fetchrow("""
        SELECT trade_date, close FROM public.price_bars p JOIN public.companies c ON p.company_id=c.company_id
        WHERE c.symbol='FPT' ORDER BY close ASC LIMIT 1
    """)
    print(f"Q13 FPT max close: date={r_fpt_max['trade_date']}, close={r_fpt_max['close']} (Expected: 2025-01-23, 118.06)")
    print(f"Q13 FPT min close: date={r_fpt_min['trade_date']}, close={r_fpt_min['close']} (Expected: 2018-07-12, 10.75)")
    
    # Q14: MBB 20 bars up to 2026-09-25
    mbb_20 = await conn.fetch("""
        SELECT trade_date, volume FROM public.price_bars p JOIN public.companies c ON p.company_id=c.company_id
        WHERE c.symbol='MBB' AND p.trade_date <= '2026-09-25'
        ORDER BY p.trade_date DESC LIMIT 20
    """)
    total_vol = sum(r['volume'] for r in mbb_20)
    avg_vol = total_vol / 20
    print(f"Q14 MBB SMA20 vol: total={total_vol}, avg={avg_vol:.0f} (Expected: total=238016600, avg=11900830)")
    
    # Q15: VCB 2026-05-20
    r_vcb_may20 = await conn.fetchrow("""
        SELECT open, high, low, close, volume FROM public.price_bars p JOIN public.companies c ON p.company_id=c.company_id
        WHERE c.symbol='VCB' AND p.trade_date='2026-05-20'
    """)
    print(f"Q15 VCB 2026-05-20: O={r_vcb_may20['open']}, H={r_vcb_may20['high']}, L={r_vcb_may20['low']}, C={r_vcb_may20['close']}, V={r_vcb_may20['volume']}")
    print("  Expected: O=63.17, H=64.17, L=61.29, C=64.07, V=14381600")
    
    # Q16: Compare Sept 2026 (2026-09-03 to 2026-09-25)
    for sym in ['VCB', 'MBB', 'FPT']:
        r_start = await conn.fetchrow("SELECT close FROM public.price_bars p JOIN public.companies c ON p.company_id=c.company_id WHERE c.symbol=$1 AND p.trade_date='2026-09-03'", sym)
        r_end = await conn.fetchrow("SELECT close FROM public.price_bars p JOIN public.companies c ON p.company_id=c.company_id WHERE c.symbol=$1 AND p.trade_date='2026-09-25'", sym)
        cs, ce = float(r_start['close']), float(r_end['close'])
        pct = (ce - cs) / cs * 100
        print(f"Q16 {sym}: start={cs}, end={ce}, change={pct:.2f}%")
    print("  Expected: VCB=-1.19%, FPT=-1.43%, MBB=-3.40%")
    
    # Q17: FPT max spread
    r_fpt_spread = await conn.fetchrow("""
        SELECT trade_date, high, low, (high - low) as spread FROM public.price_bars p JOIN public.companies c ON p.company_id=c.company_id
        WHERE c.symbol='FPT' ORDER BY (high - low) DESC LIMIT 1
    """)
    print(f"Q17 FPT max spread: date={r_fpt_spread['trade_date']}, H={r_fpt_spread['high']}, L={r_fpt_spread['low']}, spread={r_fpt_spread['spread']} (Expected: 2025-04-09, 82.64, 74.84, 7.80)")
    
    # Q18: VCB total bars in Entrade period
    cnt_vcb_entrade = await conn.fetchval("""
        SELECT count(1) FROM public.price_bars p JOIN public.companies c ON p.company_id=c.company_id
        WHERE c.symbol='VCB' AND p.trade_date >= '2018-01-02' AND p.trade_date <= '2026-09-25'
    """)
    print(f"Q18 VCB bars in Entrade range (2018-01-02 to 2026-09-25): {cnt_vcb_entrade} (Expected: 2174)")
    
    # Q19: VCB 2026-04-23
    r_vcb_apr23 = await conn.fetchrow("""
        SELECT open, high, low, close, volume FROM public.price_bars p JOIN public.companies c ON p.company_id=c.company_id
        WHERE c.symbol='VCB' AND p.trade_date='2026-04-23'
    """)
    print(f"Q19 VCB 2026-04-23: O={r_vcb_apr23['open']}, H={r_vcb_apr23['high']}, L={r_vcb_apr23['low']}, C={r_vcb_apr23['close']}, V={r_vcb_apr23['volume']}")
    print("  Expected: O=59.21, H=62.98, L=59.11, C=62.28, V=35200000")
    
    # Q20: MBB 2026-09-17 vs 2026-09-25
    r_mbb_sep17 = await conn.fetchrow("SELECT close FROM public.price_bars p JOIN public.companies c ON p.company_id=c.company_id WHERE c.symbol='MBB' AND p.trade_date='2026-09-17'")
    r_mbb_sep25 = await conn.fetchrow("SELECT close FROM public.price_bars p JOIN public.companies c ON p.company_id=c.company_id WHERE c.symbol='MBB' AND p.trade_date='2026-09-25'")
    c17, c25 = float(r_mbb_sep17['close']), float(r_mbb_sep25['close'])
    diff20 = c25 - c17
    pct20 = diff20 / c17 * 100
    print(f"Q20 MBB 17 vs 25: sep17={c17}, sep25={c25}, diff={diff20:.2f}, change={pct20:.2f}%")
    print("  Expected: sep17=20.55, sep25=19.90, diff=-0.65, change=-3.16%")
    
    await conn.close()

if __name__ == '__main__':
    asyncio.run(check())
