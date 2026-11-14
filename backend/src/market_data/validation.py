"""Validate KBS day-to-date rows and preserve the existing API's decimal strings."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, DecimalException
import re

VN = timezone(timedelta(hours=7))


def _price(value):
    if type(value) not in (str, int, Decimal):
        raise ValueError("Giá phải là chuỗi thập phân, Decimal hoặc số nguyên.")
    try:
        number = Decimal(value)
        if not number.is_finite() or number <= 0:
            raise ValueError("Giá phải dương và hữu hạn.")
        return number
    except (DecimalException, TypeError):
        raise ValueError("Giá không hợp lệ.") from None


def normalize_quote(row, fetched_at, *, today, automatic, previous=None):
    try:
        symbol = row["symbol"]
        if not isinstance(symbol, str) or not re.fullmatch(r"[A-Z]{3}", symbol):
            raise ValueError("Mã cổ phiếu không hợp lệ.")
        if row["exchange"] not in ("HOSE", "HNX", "UPCOM"):
            raise ValueError("Sàn không hợp lệ.")
        if not isinstance(row["TD"], str) or not re.fullmatch(r"\d{2}/\d{2}/\d{4}", row["TD"]):
            raise ValueError("Ngày bảng điện không hợp lệ.")
        day = datetime.strptime(row["TD"], "%d/%m/%Y").date()
        stamp = datetime.fromisoformat(fetched_at)
        if stamp.tzinfo is None or stamp.utcoffset() is None or stamp.astimezone(VN).date() != today:
            raise ValueError("Thời điểm lấy giá không hợp lệ.")
        if day > today or (automatic and day != today):
            raise ValueError("Ngày giá không khớp phiên.")
        prices = {field: _price(_price(row[field + "_price"]) / 1000) for field in ("open", "high", "low", "close")}
        if not prices["low"] <= prices["open"] <= prices["high"] or not prices["low"] <= prices["close"] <= prices["high"]:
            raise ValueError("Quan hệ OHLC không hợp lệ.")
        volume = row["volume_accumulated"]
        if type(volume) is not int or not 1 <= volume <= (1 << 63) - 1:
            raise ValueError("Khối lượng giao dịch không hợp lệ.")
        status = "open" if automatic else "pending_reconciliation"
        if previous:
            old_day = datetime.strptime(previous["date"], "%Y-%m-%d").date()
            if old_day > day:
                raise ValueError("Nguồn trả ngày cũ hơn bản đã lưu.")
            if old_day == day:
                if previous.get("source") != "vnstock_kbs" or any(previous.get(field) != "unknown" for field in ("price_basis", "volume_basis")):
                    raise ValueError("Không trộn nguồn hoặc cơ sở giá khác nhau.")
                if previous.get("status") == "closed":
                    raise ValueError("Không mở lại nến đã đối soát đóng phiên.")
                old_volume = previous["volume"]
                if type(old_volume) is not int or old_volume < 0:
                    raise ValueError("Khối lượng đã lưu không hợp lệ.")
                if (volume < old_volume or prices["high"] < _price(previous["high"])
                        or prices["low"] > _price(previous["low"]) or prices["open"] != _price(previous["open"])):
                    raise ValueError("Nguồn trả dữ liệu OHLCV lùi.")
                if previous.get("status") == "pending_reconciliation":
                    status = "pending_reconciliation"
        return {"date": day.isoformat(), **{key: str(value) for key, value in prices.items()},
                "volume": volume, "status": status, "quality": "complete", "price_basis": "unknown",
                "volume_basis": "unknown", "source": "vnstock_kbs"}
    except (KeyError, TypeError, DecimalException, OverflowError):
        raise ValueError("Bảng điện thiếu trường hoặc sai kiểu dữ liệu.") from None
