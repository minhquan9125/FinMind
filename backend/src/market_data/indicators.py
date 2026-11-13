"""Technical indicators from stored daily bars; pure, no database or provider access.

Standard definitions: MACD(12,26,9) with SMA-seeded EMAs, Bollinger(20,2) with population deviation,
ATR14/ADX14 with Wilder smoothing, Stochastic(14,3), MFI14 and the 20-session OBV change.
Each result carries a conventional reading (overbought, strong trend, ...) as description, never as advice.
Rows must already be normalized by trend._rows (Decimal OHLC, ascending dates).
"""
from decimal import Decimal, localcontext

from .analysis import _formatted


def _ema(values, n):
    k, out = Decimal(2) / (n + 1), [sum(values[:n]) / n]
    for value in values[n:]:
        out.append(out[-1] + k * (value - out[-1]))
    return out


def _wilder(values, n):
    out = [sum(values[:n]) / n]
    for value in values[n:]:
        out.append((out[-1] * (n - 1) + value) / n)
    return out


def _zone(value, high, low):
    return "vùng quá mua" if value > high else "vùng quá bán" if value < low else "vùng trung tính"


def _macd(c):
    if len(c) < 34:
        return None
    e12, e26 = _ema(c, 12), _ema(c, 26)
    line = [a - b for a, b in zip(e12[14:], e26)]
    macd, signal = line[-1], _ema(line, 9)[-1]
    position = "trên" if macd > signal else "dưới" if macd < signal else "bằng"
    side = "đà giảm" if macd < 0 else "đà tăng"
    change = ("đang mạnh thêm" if (macd < signal) == (macd < 0) and macd != signal else
              "đang yếu đi" if macd != signal else "đang chững lại")
    return dict(macd=_formatted(macd), signal=_formatted(signal), histogram=_formatted(macd - signal),
                reading=f"MACD {position} đường tín hiệu",
                meaning=f"{side} đang chiếm ưu thế và {change}")


def _bollinger(c):
    if len(c) < 20:
        return None
    last = c[-20:]
    middle = sum(last) / 20
    sd = (sum((x - middle) ** 2 for x in last) / 20).sqrt()
    upper, lower = middle + 2 * sd, middle - 2 * sd
    percent_b = (c[-1] - lower) / (upper - lower) * 100 if upper != lower else None
    reading = meaning = None
    if percent_b is not None:
        reading = ("giá trên dải trên" if percent_b > 100 else "giá dưới dải dưới" if percent_b < 0
                   else "giá nằm trong dải")
        meaning = ("giá vượt lên trên dải trên, tức là tăng mạnh bất thường so với 20 phiên gần nhất" if percent_b > 100
                   else "giá thủng dải dưới, tức là giảm mạnh bất thường so với 20 phiên gần nhất" if percent_b < 0
                   else "giá đang ở gần cận dưới của dải, tức là thấp so với mức thường thấy 20 phiên gần nhất"
                   if percent_b <= 20 else
                   "giá đang ở gần cận trên của dải, tức là cao so với mức thường thấy 20 phiên gần nhất"
                   if percent_b >= 80 else "giá đang ở khoảng giữa dải, quanh mức thường thấy 20 phiên gần nhất")
    return dict(upper=_formatted(upper), middle=_formatted(middle), lower=_formatted(lower),
                percent_b=_formatted(percent_b), bandwidth_percent=_formatted((upper - lower) / middle * 100),
                reading=reading, meaning=meaning)


def _true_ranges(h, l, c):
    return [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, len(c))]


def _atr(h, l, c):
    if len(c) < 15:
        return None
    atr = _wilder(_true_ranges(h, l, c), 14)[-1]
    return dict(value=_formatted(atr), percent_of_close=_formatted(atr / c[-1] * 100))


def _stochastic(h, l, c):
    if len(c) < 16:
        return None
    k_values = []
    for i in range(len(c) - 3, len(c)):
        hh, ll = max(h[i - 13:i + 1]), min(l[i - 13:i + 1])
        if hh == ll:
            return None
        k_values.append((c[i] - ll) / (hh - ll) * 100)
    k, d = k_values[-1], sum(k_values) / 3
    meaning = ("giá đóng cửa đang sát mức thấp nhất 14 phiên" if k < 20 else
               "giá đóng cửa đang sát mức cao nhất 14 phiên" if k > 80 else
               "giá đóng cửa đang ở khoảng giữa vùng cao-thấp 14 phiên")
    return dict(k=_formatted(k), d=_formatted(d), reading=_zone(k, 80, 20), meaning=meaning)


def _mfi(h, l, c, v):
    if len(c) < 15 or None in v[-15:]:
        return None
    tp = [(h[i] + l[i] + c[i]) / 3 for i in range(len(c))]
    pos = sum(tp[i] * v[i] for i in range(len(c) - 14, len(c)) if tp[i] > tp[i - 1])
    neg = sum(tp[i] * v[i] for i in range(len(c) - 14, len(c)) if tp[i] < tp[i - 1])
    if not pos and not neg:
        return None
    value = Decimal(100) if not neg else 100 - 100 / (1 + pos / neg)
    meaning = ("tiền rút ra áp đảo tiền vào trong 14 phiên" if value < 20 else
               "tiền vào áp đảo tiền rút ra trong 14 phiên" if value > 80 else
               "tiền vào và rút ra tương đối cân bằng trong 14 phiên")
    return dict(value=_formatted(value), reading=_zone(value, 80, 20), meaning=meaning)


def _obv(c, v):
    if len(c) < 21 or None in v[-21:]:
        return None
    change = sum(v[i] if c[i] > c[i - 1] else -v[i] if c[i] < c[i - 1] else 0 for i in range(len(c) - 20, len(c)))
    meaning = ("khối lượng ở các phiên tăng giá lớn hơn các phiên giảm giá: áp lực mua chiếm ưu thế" if change > 0 else
               "khối lượng ở các phiên giảm giá lớn hơn các phiên tăng giá: áp lực bán chiếm ưu thế" if change < 0 else
               "khối lượng phiên tăng và phiên giảm cân bằng")
    return dict(change_20=change, direction="tăng" if change > 0 else "giảm" if change < 0 else "đi ngang",
                meaning=meaning)


def _adx(h, l, c):
    if len(c) < 28:
        return None
    tr = _true_ranges(h, l, c)
    up = [h[i] - h[i - 1] for i in range(1, len(c))]
    down = [l[i - 1] - l[i] for i in range(1, len(c))]
    plus = [u if u > d and u > 0 else Decimal(0) for u, d in zip(up, down)]
    minus = [d if d > u and d > 0 else Decimal(0) for u, d in zip(up, down)]
    s_tr, s_plus, s_minus = _wilder(tr, 14), _wilder(plus, 14), _wilder(minus, 14)
    if 0 in s_tr:
        return None
    pdi = [100 * p / t for p, t in zip(s_plus, s_tr)]
    mdi = [100 * m / t for m, t in zip(s_minus, s_tr)]
    if any(p + m == 0 for p, m in zip(pdi, mdi)):
        return None
    adx = _wilder([100 * abs(p - m) / (p + m) for p, m in zip(pdi, mdi)], 14)[-1]
    strength = "xu hướng mạnh" if adx > 25 else "xu hướng yếu hoặc chưa rõ" if adx < 20 else "xu hướng trung bình"
    side = "bên tăng chiếm ưu thế" if pdi[-1] > mdi[-1] else "bên giảm chiếm ưu thế" if pdi[-1] < mdi[-1] else "hai bên cân bằng"
    direction = "xu hướng tăng" if pdi[-1] > mdi[-1] else "xu hướng giảm" if pdi[-1] < mdi[-1] else "xu hướng"
    level = "đang mạnh" if adx > 25 else "còn yếu hoặc chưa rõ" if adx < 20 else "ở mức trung bình"
    return dict(adx=_formatted(adx), plus_di=_formatted(pdi[-1]), minus_di=_formatted(mdi[-1]),
                reading=strength, side=side, meaning=f"{direction} hiện tại {level}")


def compute_indicators(rows, *, since=None):
    """`since`: ISO day of the last suspected corporate action; only later sessions are used,
    because unadjusted prices across a split would read as a crash."""
    rows = [r for r in rows if since is None or r["trade_date"].isoformat() > since]
    with localcontext() as context:
        context.prec = 34
        h, l, c = ([r[key] for r in rows] for key in ("high", "low", "close"))
        v = [r.get("volume") for r in rows]
        return dict(sessions=len(rows), as_of=rows[-1]["trade_date"].isoformat() if rows else None,
                    macd=_macd(c), bollinger=_bollinger(c), atr=_atr(h, l, c), stochastic=_stochastic(h, l, c),
                    mfi=_mfi(h, l, c, v), obv=_obv(c, v), adx=_adx(h, l, c))
