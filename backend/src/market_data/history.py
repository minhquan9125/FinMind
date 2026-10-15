"""Daily index snapshots; SDK decimals stay strings and index prices stay points."""
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

INDEX_NAMES = {"VNINDEX": "VN-INDEX", "VN30": "VN30", "HNXINDEX": "HNX-INDEX", "UPCOMINDEX": "UPCOM-INDEX"}


def normalize_index_history(symbol, result):
    if symbol not in INDEX_NAMES:
        raise ValueError("Chỉ số không được hỗ trợ.")
    return normalize_history(symbol, result, is_index=True)


def normalize_history(symbol, result, *, is_index=False):
    if not is_index:
        from .live import stock_symbol
        stock_symbol(symbol)
    stamp = datetime.fromisoformat(result["fetched_at"])
    if stamp.tzinfo is None:
        raise ValueError("Thiếu múi giờ nguồn.")
    rows = result["rows"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= 400:
        raise ValueError("Nguồn không có lịch sử chỉ số.")
    bars = {}
    for row in rows:
        day = datetime.fromisoformat(row["time"]).date()
        if day in bars or not stamp.date() - timedelta(days=366) <= day <= stamp.date():
            raise ValueError("Ngày chỉ số không hợp lệ.")
        prices = {}
        for field in ("open", "high", "low", "close"):
            value = row[field]
            if type(value) not in (str, int):
                raise ValueError("Giá chỉ số không hợp lệ.")
            try:
                price = Decimal(value)
            except InvalidOperation:
                raise ValueError("Giá chỉ số không hợp lệ.") from None
            if not price.is_finite() or price <= 0:
                raise ValueError("Giá chỉ số không hợp lệ.")
            prices[field] = price
        if not prices["low"] <= min(prices["open"], prices["close"]) <= max(prices["open"], prices["close"]) <= prices["high"]:
            raise ValueError("Quan hệ OHLC không hợp lệ.")
        volume = row["volume"]
        if type(volume) is not int or not 0 <= volume <= (1 << 63) - 1:
            raise ValueError("Khối lượng không hợp lệ.")
        bars[day] = {"date": day.isoformat(), **{key: str(value) for key, value in prices.items()},
                     "volume": volume, "source": "vnstock_kbs", "status": "pending_reconciliation",
                     "quality": "complete", "price_basis": "index_points" if is_index else "unknown", "volume_basis": "unknown"}
    return {"symbol": symbol, "interval": "1D", "source": "vnstock_kbs", "fetched_at": result["fetched_at"],
            "price_unit": "points" if is_index else "unknown", "bars": [bars[day] for day in sorted(bars)]}
