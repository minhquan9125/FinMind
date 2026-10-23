import os
import sys
import json

sys.stdout.reconfigure(encoding='utf-8')

print("="*60)
print("VERIFYING LO 2: GIA CO PHIEU (Q11 - Q20)")
print("="*60)

# Check Q11: VCB start/end
def get_bars(d):
    return d.get("price_history", d.get("data", d))

with open("data/normalized/VCB.json", "r", encoding="utf-8") as f:
    vcb = json.load(f)
vcb_bars = get_bars(vcb)
first_vcb = vcb_bars[0]
last_vcb = vcb_bars[-1]
growth_vcb = (last_vcb['close'] - first_vcb['close']) / first_vcb['close'] * 100
print(f"Q11 VCB: total bars={len(vcb_bars)}")
print(f"  First: date={first_vcb['date']}, close={first_vcb['close']}")
print(f"  Last:  date={last_vcb['date']}, close={last_vcb['close']}")
print(f"  Growth: {growth_vcb:.4f}% -> {growth_vcb:.2f}%")

# Check Q12: MBB max volume
with open("data/normalized/MBB.json", "r", encoding="utf-8") as f:
    mbb = json.load(f)
mbb_bars = get_bars(mbb)
max_vol_mbb = max(mbb_bars, key=lambda x: x['volume'])
print(f"\nQ12 MBB: total bars={len(mbb_bars)}")
print(f"  Max Volume bar: {max_vol_mbb}")

# Check Q13: BID max close & max volume
with open("data/normalized/BID.json", "r", encoding="utf-8") as f:
    bid = json.load(f)
bid_bars = get_bars(bid)
max_close_bid = max(bid_bars, key=lambda x: x['close'])
max_vol_bid = max(bid_bars, key=lambda x: x['volume'])
print(f"\nQ13 BID: total bars={len(bid_bars)}")
print(f"  Max Close: {max_close_bid}")
print(f"  Max Volume: {max_vol_bid}")

# Check Q14: CTG max close & max volume
with open("data/normalized/CTG.json", "r", encoding="utf-8") as f:
    ctg = json.load(f)
ctg_bars = get_bars(ctg)
max_close_ctg = max(ctg_bars, key=lambda x: x['close'])
max_vol_ctg = max(ctg_bars, key=lambda x: x['volume'])
print(f"\nQ14 CTG: total bars={len(ctg_bars)}")
print(f"  Max Close: {max_close_ctg}")
print(f"  Max Volume: {max_vol_ctg}")

# Check Q15: VCB 2026-04-23 vs 2026-04-22
bar_23 = next((b for b in vcb_bars if b['date'] == '2026-04-23'), None)
bar_22 = next((b for b in vcb_bars if b['date'] == '2026-04-22'), None)
max_vol_vcb = max(vcb_bars, key=lambda x: x['volume'])
print(f"\nQ15 VCB 2026-04-23:")
print(f"  Max vol in history: {max_vol_vcb}")
print(f"  2026-04-23: {bar_23}")
print(f"  2026-04-22: {bar_22}")
if bar_23 and bar_22:
    pct_vcb = (bar_23['close'] - bar_22['close']) / bar_22['close'] * 100
    print(f"  Change: ({bar_23['close']} - {bar_22['close']}) / {bar_22['close']} = {pct_vcb:.4f}% -> {pct_vcb:.2f}%")

# Check Q16: Banking comparison 2026-09-03 to 2026-09-25 (VCB, BID, CTG, MBB, TCB)
print(f"\nQ16 Banking 2026-09-03 to 2026-09-25:")
for sym in ['VCB', 'BID', 'CTG', 'MBB', 'TCB']:
    with open(f"data/normalized/{sym}.json", "r", encoding="utf-8") as f:
        d = json.load(f)
    bars = get_bars(d)
    b_start = next((b for b in bars if b['date'] == '2026-09-03'), None)
    b_end = next((b for b in bars if b['date'] == '2026-09-25'), None)
    pct = (b_end['close'] - b_start['close']) / b_start['close'] * 100
    print(f"  {sym}: Start {b_start['date']}={b_start['close']}, End {b_end['date']}={b_end['close']}, Change={pct:.4f}% -> {pct:.2f}%")

# Check Q17: FPT ATH Close & Max Daily Range (High - Low)
with open("data/normalized/FPT.json", "r", encoding="utf-8") as f:
    fpt = json.load(f)
fpt_bars = get_bars(fpt)
max_close_fpt = max(fpt_bars, key=lambda x: x['close'])
max_range_fpt = max(fpt_bars, key=lambda x: round(x['high'] - x['low'], 4))
print(f"\nQ17 FPT: total bars={len(fpt_bars)}")
print(f"  Max Close: {max_close_fpt}")
print(f"  Max Range: date={max_range_fpt['date']}, high={max_range_fpt['high']}, low={max_range_fpt['low']}, range={round(max_range_fpt['high'] - max_range_fpt['low'], 2)}, open={max_range_fpt['open']}, close={max_range_fpt['close']}")

# Check Q18: FPT vs CMG in Sep 2026
with open("data/normalized/CMG.json", "r", encoding="utf-8") as f:
    cmg = json.load(f)
cmg_bars = get_bars(cmg)
fpt_s = next((b for b in fpt_bars if b['date'] == '2026-09-03'), None)
fpt_e = next((b for b in fpt_bars if b['date'] == '2026-09-25'), None)
cmg_s = next((b for b in cmg_bars if b['date'] == '2026-09-03'), None)
cmg_e = next((b for b in cmg_bars if b['date'] == '2026-09-25'), None)
fpt_chg = (fpt_e['close'] - fpt_s['close']) / fpt_s['close'] * 100
cmg_chg = (cmg_e['close'] - cmg_s['close']) / cmg_s['close'] * 100
print(f"\nQ18 FPT vs CMG (2026-09-03 to 2026-09-25):")
print(f"  FPT: {fpt_s['close']} -> {fpt_e['close']}, Change={fpt_chg:.4f}% -> {fpt_chg:.2f}%")
print(f"  CMG: {cmg_s['close']} -> {cmg_e['close']}, Change={cmg_chg:.4f}% -> {cmg_chg:.2f}%")

# Check Q19: TCB SMA20 volume up to 2026-09-25
with open("data/normalized/TCB.json", "r", encoding="utf-8") as f:
    tcb = json.load(f)
tcb_bars = get_bars(tcb)
idx_25 = next(i for i, b in enumerate(tcb_bars) if b['date'] == '2026-09-25')
last_20 = tcb_bars[idx_25-19:idx_25+1]
total_vol_20 = sum(b['volume'] for b in last_20)
sma20_vol = total_vol_20 / 20
print(f"\nQ19 TCB SMA20 Volume (last 20 bars up to {tcb_bars[idx_25]['date']}):")
print(f"  Start bar: {last_20[0]['date']}, End bar: {last_20[-1]['date']}")
print(f"  Count: {len(last_20)}")
print(f"  Total Volume: {total_vol_20}")
print(f"  SMA20 Volume: {sma20_vol}")

# Check Q20: Mid-cap tech ELC, ITD, ICT
print(f"\nQ20 Mid-cap Tech ELC, ITD, ICT:")
for sym in ['ELC', 'ITD', 'ICT']:
    with open(f"data/normalized/{sym}.json", "r", encoding="utf-8") as f:
        d = json.load(f)
    bars = get_bars(d)
    first = bars[0]
    last = bars[-1]
    pct = (last['close'] - first['close']) / first['close'] * 100
    print(f"  {sym} ({len(bars)} bars): First {first['date']}={first['close']}, Last {last['date']}={last['close']}, Change={pct:.4f}% -> {pct:.2f}%")

print("\n" + "="*60)
print("VERIFYING LO 4: BAO CAO TAI CHINH FPT (Q31 - Q40)")
print("="*60)
with open("data_pipeline/FinancialCleaner/data/FPT/tai_chinh_clean.json", "r", encoding="utf-8") as f:
    fc = json.load(f)

def get_metrics_dict(section_name, period):
    items = fc['báo_cáo_tài_chính'][section_name]
    item = next((x for x in items if x['kỳ_báo_cáo'] == period), None)
    if not item:
        return {}
    res = {}
    for m in item['chỉ_tiêu']:
        if m.get('mã_chuẩn'):
            res[m['mã_chuẩn']] = m
        if m.get('trường_gốc'):
            res[m['trường_gốc']] = m
    return res

bs_2026_q2 = get_metrics_dict('bảng_cân_đối_kế_toán', '2026-Q2')
is_2026_q2 = get_metrics_dict('kết_quả_kinh_doanh', '2026-Q2')
cf_2026_q2 = get_metrics_dict('lưu_chuyển_tiền_tệ', '2026-Q2')
ratio_2026_q2 = get_metrics_dict('chỉ_số_tài_chính', '2026-Q2')

print("Q31 (bsa2 / CASH_AND_CASH_EQUIVALENTS):")
print("  Value:", bs_2026_q2.get('CASH_AND_CASH_EQUIVALENTS', {}).get('giá_trị'))
print("  Formatted:", bs_2026_q2.get('CASH_AND_CASH_EQUIVALENTS', {}).get('giá_trị_hiển_thị'))

print("\nQ32 (Short-term loans bsa56 vs bsa55, bsa54, bsa53):")
print("  SHORT_TERM_LOANS_AND_FINANCE_LEASES (bsa56):", bs_2026_q2.get('SHORT_TERM_LOANS_AND_FINANCE_LEASES', {}).get('giá_trị'))
print("  CURRENT_LIABILITIES (bsa55):", bs_2026_q2.get('CURRENT_LIABILITIES', {}).get('giá_trị'))
print("  TOTAL_LIABILITIES (bsa54):", bs_2026_q2.get('TOTAL_LIABILITIES', {}).get('giá_trị'))
print("  TOTAL_ASSETS (bsa53):", bs_2026_q2.get('TOTAL_ASSETS', {}).get('giá_trị'))

print("\nQ33 (Retained earnings bsa90 vs bsa178, bsa80, bsa78):")
print("  RETAINED_EARNINGS (bsa90):", bs_2026_q2.get('RETAINED_EARNINGS', {}).get('giá_trị'))
print("  CURRENT_PERIOD_RETAINED_EARNINGS (bsa178):", bs_2026_q2.get('bsa178', {}).get('giá_trị'))
print("  CHARTER_CAPITAL (bsa80):", bs_2026_q2.get('bsa80', {}).get('giá_trị'))
print("  OWNERS_EQUITY (bsa78):", bs_2026_q2.get('bsa78', {}).get('giá_trị'))

print("\nQ34 (Net revenue isa3 vs isa2, isa1):")
print("  NET_REVENUE (isa3):", is_2026_q2.get('NET_REVENUE', {}).get('giá_trị'))
print("  REVENUE_DEDUCTIONS (isa2):", is_2026_q2.get('isa2', {}).get('giá_trị'))
print("  GROSS_REVENUE (isa1):", is_2026_q2.get('isa1', {}).get('giá_trị'))

print("\nQ35 (Parent net profit isa22 & EPS isa23 vs isa20, isa21):")
print("  PARENT_NET_PROFIT (isa22):", is_2026_q2.get('PARENT_NET_PROFIT', {}).get('giá_trị'))
print("  BASIC_EARNINGS_PER_SHARE (isa23):", is_2026_q2.get('BASIC_EARNINGS_PER_SHARE', {}).get('giá_trị'))
print("  PROFIT_AFTER_TAX (isa20):", is_2026_q2.get('PROFIT_AFTER_TAX', {}).get('giá_trị'))
print("  NON_CONTROLLING_INTERESTS (isa21):", is_2026_q2.get('isa21', {}).get('giá_trị'))

print("\nQ36 (CFO cfa18):")
print("  CASH_FLOW_OPERATING (cfa18):", cf_2026_q2.get('CASH_FLOW_OPERATING', {}).get('giá_trị'))

print("\nQ37 (Capex cfa19):")
print("  PURCHASE_FIXED_ASSETS (cfa19):", cf_2026_q2.get('PURCHASE_FIXED_ASSETS', {}).get('giá_trị'))

print("\nQ38 (ROE & GROSS_MARGIN):")
print("  ROE:", ratio_2026_q2.get('ROE', {}).get('giá_trị'))
print("  GROSS_MARGIN:", ratio_2026_q2.get('GROSS_MARGIN', {}).get('giá_trị'))

print("\nQ39 (Deterministic QoQ Q1 vs Q2 2026):")
is_2026_q1 = get_metrics_dict('kết_quả_kinh_doanh', '2026-Q1')
q1_rev = is_2026_q1.get('NET_REVENUE', {}).get('giá_trị')
q2_rev = is_2026_q2.get('NET_REVENUE', {}).get('giá_trị')
diff_rev = q2_rev - q1_rev
pct_rev = diff_rev / q1_rev * 100
print(f"  Q1 Net Rev: {q1_rev}")
print(f"  Q2 Net Rev: {q2_rev}")
print(f"  Diff: {diff_rev}")
print(f"  Growth %: {pct_rev:.4f}% -> {pct_rev:.2f}%")

print("\nQ40 (Safe refusal 2026-Q4):")
periods_is = [x['kỳ_báo_cáo'] for x in fc['báo_cáo_tài_chính']['kết_quả_kinh_doanh']]
print("  Periods count:", len(periods_is))
print("  First 3:", periods_is[:3], "Last 3:", periods_is[-3:])
print("  Is 2026-Q4 in periods?", '2026-Q4' in periods_is)
