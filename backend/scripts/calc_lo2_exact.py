import json, sys
sys.stdout.reconfigure(encoding='utf-8')

def load_stock(sym):
    with open(f'data/normalized/{sym}.json', 'r', encoding='utf-8') as f:
        return json.load(f)['price_history']

vcb = load_stock('VCB')
mbb = load_stock('MBB')
fpt = load_stock('FPT')

print('=== Q11: VCB biến động kỳ ===')
# Kỳ toàn dữ liệu: 2018-01-02 đến 2026-09-25
p_first = vcb[0]
p_last = vcb[-1]
chg = (p_last['close'] - p_first['close']) / p_first['close'] * 100
print(f"Toàn kỳ: First={p_first['date']} close={p_first['close']} -> Last={p_last['date']} close={p_last['close']} => Biến động={chg:.2f}%")

# Kỳ năm 2026: từ phiên đầu năm 2026-01-02 đến phiên cuối 2026-09-25
vcb_2026 = [p for p in vcb if p['date'].startswith('2026')]
chg_2026 = (vcb_2026[-1]['close'] - vcb_2026[0]['close']) / vcb_2026[0]['close'] * 100
print(f"Năm 2026: First={vcb_2026[0]['date']} close={vcb_2026[0]['close']} -> Last={vcb_2026[-1]['date']} close={vcb_2026[-1]['close']} => Biến động={chg_2026:.2f}%")

print('\n=== Q12: MBB Max Volume ===')
mbb_max_vol = max(mbb, key=lambda x: x['volume'])
print(f"MBB Max Volume: date={mbb_max_vol['date']}, volume={mbb_max_vol['volume']:,}, close={mbb_max_vol['close']}")

print('\n=== Q13: FPT Highest & Lowest Close ===')
fpt_max_c = max(fpt, key=lambda x: x['close'])
fpt_min_c = min(fpt, key=lambda x: x['close'])
print(f"FPT Toàn kỳ: Highest close={fpt_max_c['close']} ({fpt_max_c['date']}), Lowest close={fpt_min_c['close']} ({fpt_min_c['date']})")

print('\n=== Q14: MBB 20 phiên gần nhất (đến 25/09/2026) ===')
mbb_20 = mbb[-20:]
mbb_20_sum = sum(p['volume'] for p in mbb_20)
mbb_20_avg = mbb_20_sum / 20
print(f"MBB 20 phiên: từ {mbb_20[0]['date']} đến {mbb_20[-1]['date']}")
print(f"MBB 20 phiên sum volume: {mbb_20_sum:,}")
print(f"MBB 20 phiên avg volume: {mbb_20_avg:,.2f} CP/phiên (làm tròn: {round(mbb_20_avg):,} CP/phiên)")

print('\n=== Q15: VCB phiên 20/05/2026 ===')
vcb_may20 = [p for p in vcb if p['date'] == '2026-05-20'][0]
print(f"VCB 2026-05-20: Open={vcb_may20['open']}, High={vcb_may20['high']}, Low={vcb_may20['low']}, Close={vcb_may20['close']}, Volume={vcb_may20['volume']:,}")

print('\n=== Q16: So sánh tháng 09/2026 (03/09/2026 đến 25/09/2026) ===')
vcb_sep = [p for p in vcb if p['date'].startswith('2026-09')]
mbb_sep = [p for p in mbb if p['date'].startswith('2026-09')]
fpt_sep = [p for p in fpt if p['date'].startswith('2026-09')]
print(f"Tháng 9: từ {vcb_sep[0]['date']} đến {vcb_sep[-1]['date']} (tổng {len(vcb_sep)} phiên)")
vcb_sep_chg = (vcb_sep[-1]['close'] - vcb_sep[0]['close']) / vcb_sep[0]['close'] * 100
mbb_sep_chg = (mbb_sep[-1]['close'] - mbb_sep[0]['close']) / mbb_sep[0]['close'] * 100
fpt_sep_chg = (fpt_sep[-1]['close'] - fpt_sep[0]['close']) / fpt_sep[0]['close'] * 100
print(f"VCB: {vcb_sep[0]['close']} -> {vcb_sep[-1]['close']} ({vcb_sep_chg:.2f}%)")
print(f"MBB: {mbb_sep[0]['close']} -> {mbb_sep[-1]['close']} ({mbb_sep_chg:.2f}%)")
print(f"FPT: {fpt_sep[0]['close']} -> {fpt_sep[-1]['close']} ({fpt_sep_chg:.2f}%)")

print('\n=== Q17: FPT biên độ dao động phiên (High - Low) ===')
fpt_spreads = [(p['date'], round(p['high'] - p['low'], 2), p['high'], p['low'], p['open'], p['close']) for p in fpt]
max_spread = max(fpt_spreads, key=lambda x: x[1])
print(f"FPT Toàn kỳ Max Spread: date={max_spread[0]}, spread={max_spread[1]}, High={max_spread[2]}, Low={max_spread[3]}")
fpt_2026 = [p for p in fpt if p['date'].startswith('2026')]
fpt_2026_spreads = [(p['date'], round(p['high'] - p['low'], 2), p['high'], p['low'], p['open'], p['close']) for p in fpt_2026]
max_2026_spread = max(fpt_2026_spreads, key=lambda x: x[1])
print(f"FPT 2026 Max Spread: date={max_2026_spread[0]}, spread={max_2026_spread[1]}, High={max_2026_spread[2]}, Low={max_2026_spread[3]}")

print('\n=== Q18: Tổng số bars của VCB ===')
print(f"VCB total bars: {len(vcb)} (từ {vcb[0]['date']} đến {vcb[-1]['date']})")

print('\n=== Q19: VCB Max Volume ===')
vcb_max_vol = max(vcb, key=lambda x: x['volume'])
print(f"VCB Max Volume: date={vcb_max_vol['date']}, volume={vcb_max_vol['volume']:,}, Open={vcb_max_vol['open']}, High={vcb_max_vol['high']}, Low={vcb_max_vol['low']}, Close={vcb_max_vol['close']}")

print('\n=== Q20: MBB so sánh 2 phiên cuối (18/09/2026 vs 25/09/2026) ===')
p_prev = [p for p in mbb if p['date'] == '2026-09-18'][0]
p_curr = [p for p in mbb if p['date'] == '2026-09-25'][0]
diff = p_curr['close'] - p_prev['close']
pct = diff / p_prev['close'] * 100
print(f"MBB 2026-09-18 close={p_prev['close']} vs 2026-09-25 close={p_curr['close']}")
print(f"Diff = {diff:.2f}, Pct = {pct:.2f}%")
