"""Technical indicators from stored daily bars: standard formulas, checked against an independent float version."""
from datetime import date, timedelta
from decimal import Decimal
import math
import random

import pytest

from src.market_data.indicators import compute_indicators


def bars(closes, *, spread=Decimal("0.5"), volume=1000, start=date(2026, 1, 1)):
    rows = []
    for i, close in enumerate(closes):
        close = Decimal(str(close))
        rows.append(dict(trade_date=start + timedelta(days=i), open=close, high=close + spread,
                         low=close - spread, close=close, volume=volume))
    return rows


def random_bars(n=120, seed=7):
    rnd = random.Random(seed)
    price, rows = 50.0, []
    for i in range(n):
        open_ = price
        price = max(5.0, price * (1 + rnd.uniform(-0.03, 0.03)))
        high, low = max(open_, price) * (1 + rnd.uniform(0, 0.01)), min(open_, price) * (1 - rnd.uniform(0, 0.01))
        rows.append(dict(trade_date=date(2026, 1, 1) + timedelta(days=i), open=Decimal(f"{open_:.2f}"),
                         high=Decimal(f"{high:.2f}"), low=Decimal(f"{low:.2f}"), close=Decimal(f"{price:.2f}"),
                         volume=rnd.randint(1000, 9000)))
    for row in rows:  # keep OHLC consistent after rounding
        row["high"] = max(row["high"], row["open"], row["close"])
        row["low"] = min(row["low"], row["open"], row["close"])
    return rows


# ---- independent float reference (textbook definitions) ----
def ema(values, n):
    k, out = 2 / (n + 1), [sum(values[:n]) / n]
    for v in values[n:]:
        out.append(out[-1] + k * (v - out[-1]))
    return out


def wilder(values, n):
    out = [sum(values[:n]) / n]
    for v in values[n:]:
        out.append((out[-1] * (n - 1) + v) / n)
    return out


def reference(rows):
    c = [float(r["close"]) for r in rows]
    h = [float(r["high"]) for r in rows]
    l = [float(r["low"]) for r in rows]
    v = [r["volume"] for r in rows]
    e12, e26 = ema(c, 12), ema(c, 26)
    macd = [a - b for a, b in zip(e12[14:], e26)]
    signal = ema(macd, 9)
    last20 = c[-20:]
    mid = sum(last20) / 20
    sd = math.sqrt(sum((x - mid) ** 2 for x in last20) / 20)
    tr = [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, len(c))]
    atr = wilder(tr, 14)[-1]
    k_values = [(c[i] - min(l[i - 13:i + 1])) / (max(h[i - 13:i + 1]) - min(l[i - 13:i + 1])) * 100
                for i in range(len(c) - 3, len(c))]
    tp = [(h[i] + l[i] + c[i]) / 3 for i in range(len(c))]
    pos = sum(tp[i] * v[i] for i in range(len(c) - 14, len(c)) if tp[i] > tp[i - 1])
    neg = sum(tp[i] * v[i] for i in range(len(c) - 14, len(c)) if tp[i] < tp[i - 1])
    plus_dm = [max(h[i] - h[i - 1], 0) if h[i] - h[i - 1] > l[i - 1] - l[i] else 0 for i in range(1, len(c))]
    minus_dm = [max(l[i - 1] - l[i], 0) if l[i - 1] - l[i] > h[i] - h[i - 1] else 0 for i in range(1, len(c))]
    s_tr, s_p, s_m = wilder(tr, 14), wilder(plus_dm, 14), wilder(minus_dm, 14)
    pdi = [100 * p / t for p, t in zip(s_p, s_tr)]
    mdi = [100 * m / t for m, t in zip(s_m, s_tr)]
    dx = [100 * abs(p - m) / (p + m) for p, m in zip(pdi, mdi)]
    return dict(macd=macd[-1], signal=signal[-1], mid=mid, upper=mid + 2 * sd, lower=mid - 2 * sd, atr=atr,
                k=k_values[-1], d=sum(k_values) / 3, mfi=100 - 100 / (1 + pos / neg),
                adx=wilder(dx, 14)[-1], pdi=pdi[-1], mdi=mdi[-1])


def test_matches_independent_reference_on_random_series():
    rows = random_bars()
    out, ref = compute_indicators(rows), reference(rows)
    pairs = dict(macd=out["macd"]["macd"], signal=out["macd"]["signal"], mid=out["bollinger"]["middle"],
                 upper=out["bollinger"]["upper"], lower=out["bollinger"]["lower"], atr=out["atr"]["value"],
                 k=out["stochastic"]["k"], d=out["stochastic"]["d"], mfi=out["mfi"]["value"],
                 adx=out["adx"]["adx"], pdi=out["adx"]["plus_di"], mdi=out["adx"]["minus_di"])
    for name, value in pairs.items():
        assert float(value) == pytest.approx(ref[name], abs=1e-3), name


def test_steady_rise_reads_as_strong_uptrend_and_overbought():
    out = compute_indicators(bars([10 + i for i in range(80)]))
    assert Decimal(out["macd"]["macd"]) > 0
    assert Decimal(out["adx"]["plus_di"]) > Decimal(out["adx"]["minus_di"])
    assert Decimal(out["adx"]["adx"]) > 25 and out["adx"]["reading"] == "xu hướng mạnh"
    assert out["mfi"]["value"] == "100.0000" and out["mfi"]["reading"] == "vùng quá mua"
    assert out["obv"]["direction"] == "tăng"


def test_flat_prices_give_no_band_position_and_no_stochastic():
    out = compute_indicators(bars([20] * 80, spread=Decimal("0")))
    assert out["bollinger"]["percent_b"] is None
    assert out["stochastic"] is None  # highest high == lowest low: undefined
    assert out["macd"]["macd"] == "0.0000"


def test_too_few_sessions_leave_indicators_out():
    out = compute_indicators(bars([10 + i for i in range(20)]))
    assert out["macd"] is None and out["adx"] is None
    assert out["bollinger"] is not None and out["atr"] is not None


def test_missing_volume_skips_only_volume_indicators():
    rows = random_bars()
    rows[-3]["volume"] = None
    out = compute_indicators(rows)
    assert out["mfi"] is None and out["obv"] is None
    assert out["macd"] is not None


def test_sessions_before_a_corporate_action_are_not_used():
    rows = random_bars(120)
    out = compute_indicators(rows, since="2026-04-20")  # only ~20 sessions after the flagged day
    assert out["sessions"] < 30 and out["macd"] is None


def test_each_indicator_says_what_its_current_level_means():
    falling = compute_indicators(bars([100 - i * 0.8 for i in range(80)]))
    assert "đà giảm" in falling["macd"]["meaning"]
    assert "cận dưới" in falling["bollinger"]["meaning"] or "thủng dải dưới" in falling["bollinger"]["meaning"]
    assert "mức thấp nhất 14 phiên" in falling["stochastic"]["meaning"]
    assert "rút ra" in falling["mfi"]["meaning"]
    assert "áp lực bán" in falling["obv"]["meaning"]
    assert "xu hướng giảm" in falling["adx"]["meaning"]
    rising = compute_indicators(bars([10 + i for i in range(80)]))
    assert "đà tăng" in rising["macd"]["meaning"] and "xu hướng tăng" in rising["adx"]["meaning"]
