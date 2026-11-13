"""Pure trend labels for one stock from its stored daily bars; no database or provider access.

``analyze_trend`` labels three horizons with fixed rules (spec 2026-11-12-price-trend-design):
UP, DOWN, SIDEWAYS, UNCLEAR or INSUFFICIENT_DATA, each with fixed reason codes and the numbers
behind them. Decimals are HALF_UP four-place strings; unavailable numbers are None. A day whose
close moves beyond the exchange's daily band (unadjusted prices) forces UNCLEAR, because a split
or stock dividend would otherwise read as a crash.
"""
from decimal import Decimal, localcontext

from .analysis import _decimal, _formatted, _row_day, _source, _volume

# horizon sessions: (slope lookback sessions, widest range in % still counted as sideways)
HORIZONS = {20: (5, Decimal("8")), 60: (15, Decimal("15")), 200: (50, Decimal("30"))}
SLOPE_LIMIT = Decimal("1")
BENCHMARK = {"HOSE": "VNINDEX", "HNX": "HNXINDEX", "UPCOM": "UPCOMINDEX"}
DAILY_BAND = {"HOSE": Decimal("7"), "HNX": Decimal("10"), "UPCOM": Decimal("15")}
BAND_TOLERANCE = Decimal("0.5")
MAX_SESSIONS = 260
YEAR_SESSIONS = 250
LABELS_VI = {"UP": "Tăng", "DOWN": "Giảm", "SIDEWAYS": "Đi ngang/tích lũy",
             "UNCLEAR": "Chưa rõ xu hướng", "INSUFFICIENT_DATA": "Chưa đủ dữ liệu"}
HORIZON_NAMES = {20: "Ngắn hạn", 60: "Trung hạn", 200: "Dài hạn"}
DISCLAIMER = "Mô tả từ dữ liệu giá đã lưu, không phải khuyến nghị."


def _percent(new, old):
    return (new - old) / old * 100


def _mean(values):
    return Decimal(sum(values)) / len(values)


def _rows(price_rows):
    rows = []
    for original in price_rows:
        row = dict(original)
        row["trade_date"] = _row_day(row)
        for field in ("open", "high", "low", "close"):
            row[field] = _decimal(row.get(field), positive=True)
        if not row["low"] <= min(row["open"], row["close"]) <= max(row["open"], row["close"]) <= row["high"]:
            raise ValueError("Invalid OHLC relationships")
        row["volume"] = _volume(row.get("volume"))
        if type(row.get("price_scale")) is not int or row["price_scale"] <= 0:
            raise ValueError("A positive integer price_scale is required")
        if type(row.get("is_adjusted")) is not bool:
            raise ValueError("Explicit boolean adjustment is required")
        rows.append(row)
    if not rows:
        raise ValueError("No stored prices")
    rows.sort(key=lambda row: row["trade_date"])
    if len({row["trade_date"] for row in rows}) != len(rows):
        raise ValueError("Duplicate stock date")
    rows = rows[-MAX_SESSIONS:]
    if len({(_source(r), r["price_scale"], r["is_adjusted"]) for r in rows}) > 1:
        raise ValueError("Mixed price source, scale or adjustment")
    return rows


def _corporate_action_days(rows, limit):
    """Days whose close-to-close move exceeds the exchange band (with tolerance)."""
    return [row["trade_date"].isoformat() for previous, row in zip(rows, rows[1:])
            if abs(_percent(row["close"], previous["close"])) > limit]


def _horizon(rows, h, lookback, sideways, flagged, index_close):
    empty = dict(label="INSUFFICIENT_DATA", sessions=h, lookback=lookback, sma=None, slope_percent=None,
                 return_percent=None, range_percent=None, close_vs_sma_percent=None, index_return_percent=None,
                 reasons=["not_enough_sessions"])
    n = len(rows)
    if n < h + lookback:
        return empty
    closes = [row["close"] for row in rows]
    close = closes[-1]
    sma = _mean(closes[-h:])
    previous_sma = _mean(closes[-h - lookback:-lookback])
    slope = _percent(sma, previous_sma)
    ret = _percent(close, closes[-1 - h])
    low = min(row["low"] for row in rows[-h:])
    spread = _percent(max(row["high"] for row in rows[-h:]), low)
    reasons = []
    flags = [day for day in flagged if day >= rows[n - h - lookback + 1]["trade_date"].isoformat()]
    reasons += [f"possible_corporate_action:{day}" for day in flags]
    if close > sma:
        reasons.append("close_above_sma")
    elif close < sma:
        reasons.append("close_below_sma")
    reasons.append("sma_rising" if slope > SLOPE_LIMIT else "sma_falling" if slope < -SLOPE_LIMIT else "sma_flat")
    if ret > 0:
        reasons.append("positive_return")
    elif ret < 0:
        reasons.append("negative_return")
    if spread <= sideways:
        reasons.append("narrow_range")
    if flags:
        label = "UNCLEAR"
    elif close > sma and slope > SLOPE_LIMIT and ret > 0:
        label = "UP"
    elif close < sma and slope < -SLOPE_LIMIT and ret < 0:
        label = "DOWN"
    elif spread <= sideways and abs(slope) <= SLOPE_LIMIT:
        label = "SIDEWAYS"
    else:
        label = "UNCLEAR"
        reasons.append("mixed_signals")
    # The index must have every one of the same h+1 stock dates; nearby quotes never substitute.
    window = [row["trade_date"] for row in rows[-1 - h:]]
    index_return = None
    if all(day in index_close for day in window):
        index_return = _percent(index_close[window[-1]], index_close[window[0]])
    else:
        reasons.append("index_not_enough_sessions")
    return dict(label=label, sessions=h, lookback=lookback, sma=_formatted(sma), slope_percent=_formatted(slope),
                return_percent=None if flags else _formatted(ret), range_percent=None if flags else _formatted(spread),
                close_vs_sma_percent=_formatted(_percent(close, sma)),
                index_return_percent=_formatted(index_return), reasons=reasons)


def analyze_trend(price_rows, index_rows, *, exchange, rsi14):
    if exchange not in BENCHMARK:
        raise ValueError("Unsupported exchange")
    with localcontext() as context:
        context.prec = 34
        rows = _rows(price_rows)
        index_close = {}
        for row in index_rows:
            try:
                index_close[_row_day(row)] = _decimal(row.get("close"), positive=True)
            except (AttributeError, TypeError, ValueError):
                continue
        flagged = _corporate_action_days(rows, DAILY_BAND[exchange] + BAND_TOLERANCE)
        horizons = {str(h): _horizon(rows, h, lookback, sideways, flagged, index_close)
                    for h, (lookback, sideways) in HORIZONS.items()}
        year = rows[-YEAR_SESSIONS:]
        close = rows[-1]["close"]
        year_flagged = [day for day in flagged if day > year[0]["trade_date"].isoformat()]
        context_out = dict(high_52w=None, high_52w_date=None, low_52w=None, low_52w_date=None,
                           from_high_percent=None, from_low_percent=None,
                           rsi14=_formatted(_decimal(rsi14)) if rsi14 is not None else None,
                           volume20_vs_volume60=None)
        if not year_flagged:
            high = max(year, key=lambda row: (row["high"], row["trade_date"]))
            low = min(year, key=lambda row: (row["low"], -row["trade_date"].toordinal()))
            context_out.update(high_52w=_formatted(high["high"]), high_52w_date=high["trade_date"].isoformat(),
                               low_52w=_formatted(low["low"]), low_52w_date=low["trade_date"].isoformat(),
                               from_high_percent=_formatted(_percent(close, high["high"])),
                               from_low_percent=_formatted(_percent(close, low["low"])))
        volumes = [row["volume"] for row in rows[-60:]]
        if len(volumes) == 60 and None not in volumes and sum(volumes):
            context_out["volume20_vs_volume60"] = _formatted(_mean(volumes[-20:]) / _mean(volumes))
    last = rows[-1]
    _, source_name = _source(last)
    warnings = []
    if last.get("approval_status") != "APPROVED":
        warnings.append("prices_source_not_approved")
    if not last["is_adjusted"]:
        warnings.append("unadjusted_prices")
    # Only flags that touched a horizon or the 52-week facts are worth a warning.
    used = {r for item in horizons.values() for r in item["reasons"] if r.startswith("possible_corporate_action:")}
    used |= {f"possible_corporate_action:{day}" for day in year_flagged}
    warnings += sorted(used)
    return dict(as_of=last["trade_date"].isoformat(), benchmark=BENCHMARK[exchange],
                source=dict(name=source_name, approval_status=last.get("approval_status"),
                            is_adjusted=last["is_adjusted"], price_scale=last["price_scale"]),
                horizons=horizons, context=context_out, warnings=warnings)


def _vi(value):
    """Chat text: two decimals with a Vietnamese comma (the stored values keep four places)."""
    return f"{Decimal(value):.2f}".replace(".", ",")


def _reason_text(h, item):
    """Why the label was given, from the same rule outcomes analyze_trend recorded."""
    phrases = {"close_above_sma": f"giá trên SMA{h}", "close_below_sma": f"giá dưới SMA{h}",
               "sma_rising": f"SMA{h} dốc lên hơn {SLOPE_LIMIT}%", "sma_falling": f"SMA{h} dốc xuống hơn {SLOPE_LIMIT}%",
               "sma_flat": f"SMA{h} gần như phẳng (trong khoảng ±{SLOPE_LIMIT}%)",
               "positive_return": "lợi suất dương", "negative_return": "lợi suất âm",
               "narrow_range": f"biên độ cao-thấp không quá {HORIZONS[h][1]}%"}
    used = {"UP": ("close_above_sma", "sma_rising", "positive_return"),
            "DOWN": ("close_below_sma", "sma_falling", "negative_return"),
            "SIDEWAYS": ("narrow_range", "sma_flat")}.get(item["label"], tuple(phrases))
    parts = ", ".join(phrases[r] for r in item["reasons"] if r in used)
    if item["label"] == "INSUFFICIENT_DATA":
        return " Lý do: chưa đủ số phiên giao dịch đã lưu."
    if "mixed_signals" in item["reasons"]:
        return f" Lý do: tín hiệu trái chiều ({parts})."
    return f" Lý do: {parts}." if parts and item["label"] != "UNCLEAR" else ""


def _vnd(value, scale):
    return f"{Decimal(value) * scale:,.0f}".replace(",", ".")


def trend_passage(symbol, trend):
    """Fixed Vietnamese text for the chatbot's evidence; states the labels exactly as computed."""
    source = trend["source"]
    approved = "đã duyệt" if source["approval_status"] == "APPROVED" else "chưa duyệt"
    lines = [f"Xu hướng giá {symbol} tính đến phiên {trend['as_of']} "
             f"(nguồn giá {source['name']}, {approved}; so với {trend['benchmark']}):"]
    for h in HORIZONS:
        item = trend["horizons"][str(h)]
        line = f"- {HORIZON_NAMES[h]}: {LABELS_VI[item['label']]} ({h} phiên)." + _reason_text(h, item)
        if item["return_percent"] is not None:
            line += (f" Lợi suất {_vi(item['return_percent'])}%, giá so với SMA{h} {_vi(item['close_vs_sma_percent'])}%,"
                     f" độ dốc SMA{h} {_vi(item['slope_percent'])}%, biên độ cao-thấp {_vi(item['range_percent'])}%.")
            line += (f" {trend['benchmark']} cùng kỳ {_vi(item['index_return_percent'])}%."
                     if item["index_return_percent"] is not None else " Chưa đủ dữ liệu chỉ số cùng kỳ.")
        days = [r.split(":", 1)[1] for r in item["reasons"] if r.startswith("possible_corporate_action:")]
        if days:
            line += (f" Có ngày giá biến động vượt biên độ sàn ({', '.join(days)}), có thể do chia tách hoặc cổ tức"
                     " cổ phiếu nên chưa kết luận xu hướng.")
        lines.append(line)
    context = trend["context"]
    facts = []
    if context["high_52w"] is not None:
        scale = source["price_scale"]
        facts.append(f"đỉnh 52 tuần {_vnd(context['high_52w'], scale)} VND ngày {context['high_52w_date']}"
                     f" (giá hiện tại {_vi(context['from_high_percent'])}% so với đỉnh)")
        facts.append(f"đáy 52 tuần {_vnd(context['low_52w'], scale)} VND ngày {context['low_52w_date']}")
    if context["rsi14"] is not None:
        facts.append(f"RSI14 {_vi(context['rsi14'])}")
    if context["volume20_vs_volume60"] is not None:
        facts.append(f"khối lượng trung bình 20 phiên bằng {_vi(context['volume20_vs_volume60'])} lần trung bình 60 phiên")
    if facts:
        lines.append("Dữ kiện: " + "; ".join(facts) + ".")
    if not source["is_adjusted"]:
        lines.append("Giá chưa điều chỉnh theo sự kiện doanh nghiệp.")
    lines.append(DISCLAIMER)
    return "\n".join(lines)
