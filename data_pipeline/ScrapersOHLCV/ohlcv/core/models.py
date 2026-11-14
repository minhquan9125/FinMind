from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping
import re

_SYMBOL_RE = re.compile(r"^[A-Z0-9]{1,10}\Z")
_ALLOWED_EXCHANGES = {"HOSE", "HNX", "UPCOM"}
_SOURCE_RE = re.compile(r"[a-z][a-z0-9_-]{0,63}")
_ALLOWED_PRICE_BASIS = {"raw", "adjusted", "unknown"}
_ALLOWED_VOLUME_BASIS = {"matched", "total", "unknown"}
_ALLOWED_STATUS = {"open", "closed", "pending_reconciliation"}
_ALLOWED_QUALITY = {"complete", "no_trade", "unknown", "suspect"}
_MAX_SQLITE_INT = (1 << 63) - 1


@dataclass(frozen=True, slots=True)
class Bar:
    symbol: str
    exchange: str
    trade_date: date
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    volume: int
    source: str = "dnse"
    price_basis: str = "raw"
    volume_basis: str = "matched"
    status: str = "open"
    quality: str = "complete"
    source_updated_at: datetime | None = None
    received_at: datetime | None = None
    reconciled_at: datetime | None = None
    revision: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not _SYMBOL_RE.fullmatch(self.symbol):
            raise ValueError(f"Invalid symbol: {self.symbol!r}")
        if not isinstance(self.exchange, str) or self.exchange not in _ALLOWED_EXCHANGES:
            raise ValueError(f"Invalid exchange: {self.exchange!r}")
        if not isinstance(self.trade_date, date) or isinstance(self.trade_date, datetime):
            raise ValueError(f"Invalid trade_date: {self.trade_date!r}")
        if not isinstance(self.source, str) or not _SOURCE_RE.fullmatch(self.source):
            raise ValueError("Invalid source identifier")
        if not isinstance(self.price_basis, str) or self.price_basis not in _ALLOWED_PRICE_BASIS:
            raise ValueError(f"Invalid price_basis: {self.price_basis!r}")
        if not isinstance(self.volume_basis, str) or self.volume_basis not in _ALLOWED_VOLUME_BASIS:
            raise ValueError(f"Invalid volume_basis: {self.volume_basis!r}")
        if not isinstance(self.status, str) or self.status not in _ALLOWED_STATUS:
            raise ValueError(f"Invalid status: {self.status!r}")
        if not isinstance(self.quality, str) or self.quality not in _ALLOWED_QUALITY:
            raise ValueError(f"Invalid quality: {self.quality!r}")

        if type(self.volume) is not int or self.volume < 0 or self.volume > _MAX_SQLITE_INT:
            raise ValueError(f"Invalid volume: {self.volume!r}")

        for dt_field, val in [
            ("source_updated_at", self.source_updated_at),
            ("received_at", self.received_at),
            ("reconciled_at", self.reconciled_at),
        ]:
            if val is not None:
                if not isinstance(val, datetime) or val.tzinfo is None or val.tzinfo.utcoffset(val) is None:
                    raise ValueError(f"{dt_field} must be an aware datetime")

        if self.status == "closed" and self.reconciled_at is None:
            raise ValueError("Closed bar requires reconciled_at timestamp")

        ohlc = (self.open, self.high, self.low, self.close)
        all_none = all(x is None for x in ohlc)
        none_count = sum(x is None for x in ohlc)

        if all_none:
            if self.volume != 0:
                raise ValueError("Null OHLC requires volume == 0")
            if self.quality != "no_trade":
                raise ValueError("Null OHLC requires quality == 'no_trade'")
        else:
            if self.quality == "no_trade":
                raise ValueError("quality == 'no_trade' requires all OHLC null and volume == 0")
            if none_count > 0:
                raise ValueError("Partial OHLC values not permitted")
            for name, val in [("open", self.open), ("high", self.high), ("low", self.low), ("close", self.close)]:
                if type(val) is bool or not isinstance(val, Decimal) or not val.is_finite() or val <= 0:
                    raise ValueError(f"{name} must be a positive finite Decimal")
            assert self.high is not None and self.low is not None and self.open is not None and self.close is not None
            if self.high < self.low:
                raise ValueError(f"high ({self.high}) cannot be less than low ({self.low})")
            if self.open > self.high or self.open < self.low:
                raise ValueError(f"open ({self.open}) outside [low ({self.low}), high ({self.high})]")
            if self.close > self.high or self.close < self.low:
                raise ValueError(f"close ({self.close}) outside [low ({self.low}), high ({self.high})]")

        if type(self.revision) is not int or self.revision < 1 or self.revision > _MAX_SQLITE_INT:
            raise ValueError(f"Invalid revision: {self.revision!r}")

    def payload_tuple(self) -> tuple[Any, ...]:
        return (
            self.symbol,
            self.exchange,
            self.trade_date,
            self.open,
            self.high,
            self.low,
            self.close,
            self.volume,
            self.source,
            self.price_basis,
            self.volume_basis,
            self.status,
            self.quality,
            self.source_updated_at,
            self.reconciled_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "trade_date": self.trade_date.isoformat(),
            "open": str(self.open) if self.open is not None else None,
            "high": str(self.high) if self.high is not None else None,
            "low": str(self.low) if self.low is not None else None,
            "close": str(self.close) if self.close is not None else None,
            "volume": self.volume,
            "source": self.source,
            "price_basis": self.price_basis,
            "volume_basis": self.volume_basis,
            "status": self.status,
            "quality": self.quality,
            "source_updated_at": self.source_updated_at.isoformat() if self.source_updated_at else None,
            "received_at": self.received_at.isoformat() if self.received_at else None,
            "reconciled_at": self.reconciled_at.isoformat() if self.reconciled_at else None,
            "revision": self.revision,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Bar":
        def _parse_dt(val: Any, field_name: str) -> datetime | None:
            if val is None:
                return None
            if isinstance(val, datetime):
                return val
            if isinstance(val, str):
                if not val.strip():
                    raise ValueError(f"Invalid empty string for datetime field {field_name}")
                return datetime.fromisoformat(val)
            raise ValueError(f"Invalid datetime format for {field_name}: {type(val)!r}")

        def _parse_date(val: Any) -> date:
            if isinstance(val, date) and not isinstance(val, datetime):
                return val
            if isinstance(val, str):
                if not val.strip():
                    raise ValueError("Invalid empty string for trade_date")
                return date.fromisoformat(val)
            raise ValueError(f"Invalid date format: {type(val)!r}")

        def _parse_dec(val: Any, field_name: str) -> Decimal | None:
            if val is None:
                return None
            if type(val) is bool or isinstance(val, float):
                raise ValueError(f"Lossy or boolean input for {field_name}: {val!r}")
            if isinstance(val, str):
                if not val.strip():
                    raise ValueError(f"Invalid empty string for decimal field {field_name}")
                try:
                    return Decimal(val)
                except InvalidOperation as exc:
                    raise ValueError(f"Invalid Decimal string for {field_name}") from exc
            if isinstance(val, (int, Decimal)):
                return Decimal(val)
            raise ValueError(f"Unsupported decimal type for {field_name}: {type(val)!r}")

        def _parse_strict_int(val: Any, field_name: str) -> int:
            if type(val) is not int:
                raise ValueError(f"{field_name} must be a strict integer, got {type(val)!r}")
            return val

        volume_val = data.get("volume")
        if "volume" not in data or volume_val is None:
            raise ValueError("Missing volume field")
        parsed_volume = _parse_strict_int(volume_val, "volume")

        revision_val = data.get("revision", 1)
        parsed_revision = _parse_strict_int(revision_val, "revision")

        symbol = data.get("symbol")
        if not isinstance(symbol, str):
            raise ValueError("symbol must be a string")

        exchange = data.get("exchange")
        if not isinstance(exchange, str):
            raise ValueError("exchange must be a string")

        return cls(
            symbol=symbol,
            exchange=exchange,
            trade_date=_parse_date(data["trade_date"]),
            open=_parse_dec(data.get("open"), "open"),
            high=_parse_dec(data.get("high"), "high"),
            low=_parse_dec(data.get("low"), "low"),
            close=_parse_dec(data.get("close"), "close"),
            volume=parsed_volume,
            source=data.get("source", "dnse"),
            price_basis=data.get("price_basis", "raw"),
            volume_basis=data.get("volume_basis", "matched"),
            status=data.get("status", "open"),
            quality=data.get("quality", "complete"),
            source_updated_at=_parse_dt(data.get("source_updated_at"), "source_updated_at"),
            received_at=_parse_dt(data.get("received_at"), "received_at"),
            reconciled_at=_parse_dt(data.get("reconciled_at"), "reconciled_at"),
            revision=parsed_revision,
        )
