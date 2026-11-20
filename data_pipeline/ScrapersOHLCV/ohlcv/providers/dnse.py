from __future__ import annotations

import base64
import hashlib
import hmac
import json
import ssl
import time
import uuid
import re
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timezone, timedelta
from decimal import Decimal, InvalidOperation, localcontext
from email.utils import formatdate, parsedate_to_datetime
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import quote, urlencode
import urllib.request
import urllib.error

_BASE_URL = "https://openapi.dnse.com.vn"
_OHLC_PATH = "/price/ohlc"
_DEFAULT_API_VERSION = "2026-07-23"
_MAX_BODY_BYTES = 5 * 1024 * 1024  # 5 MiB
_VN_TZ = timezone(timedelta(hours=7))
_ALLOWED_EXCHANGES = {"HOSE", "HNX", "UPCOM"}
_ALLOWED_PRICE_BASIS = {"raw", "adjusted", "unknown"}
_ALLOWED_VOLUME_BASIS = {"matched", "total", "unknown"}
_ALLOWED_STATUS = {"open", "closed", "pending_reconciliation"}
_ALLOWED_QUALITY = {"complete", "no_trade", "unknown", "suspect"}
_MAX_SQLITE_INT = (1 << 63) - 1


from ohlcv.core.models import Bar


class _StrictNoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, f"Redirects not permitted: {code}", headers, fp)


def _validate_header_value(name: str, value: str) -> None:
    if not isinstance(value, str) or any(ord(c) < 32 or ord(c) > 126 for c in value):
        raise ValueError(f"CR/LF/Null injection detected in header {name}")


def rest_headers(key: str, secret: str, path: str, stamp: str, nonce: str, version: str = _DEFAULT_API_VERSION) -> dict[str, str]:
    _validate_header_value("key", key)
    _validate_header_value("stamp", stamp)
    _validate_header_value("nonce", nonce)
    _validate_header_value("version", version)
    if '"' in key or '"' in nonce:
        raise ValueError("Double quote injection detected in header parameters")

    # Signing string path WITHOUT query parameters
    clean_path = path.split("?")[0]
    signing_str = f"(request-target): get {clean_path}\ndate: {stamp}\nnonce: {nonce}"
    mac = hmac.new(secret.encode("utf-8"), signing_str.encode("utf-8"), hashlib.sha256).digest()
    raw_sig = base64.b64encode(mac).decode("ascii")
    sig_quoted = quote(raw_sig, safe="")
    # Note: headers list does NOT include nonce although signing string does
    sig_header = f'Signature keyId="{key}",algorithm="hmac-sha256",headers="(request-target) date",signature="{sig_quoted}",nonce="{nonce}"'
    return {
        "Date": stamp,
        "X-Api-Key": key,
        "X-Signature": sig_header,
        "version": version,
    }


def websocket_auth(key: str, secret: str, timestamp: int, nonce: str) -> dict[str, Any]:
    if type(timestamp) is not int:
        raise ValueError("timestamp must be an integer")
    _validate_header_value("key", str(key))
    _validate_header_value("nonce", str(nonce))
    payload_str = f"{key}:{timestamp}:{nonce}"
    sig = hmac.new(secret.encode("utf-8"), payload_str.encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "action": "auth",
        "api_key": key,
        "timestamp": timestamp,
        "nonce": nonce,
        "signature": sig,
    }


def _parse_json_strictly(body_bytes: bytes) -> Any:
    if len(body_bytes) > _MAX_BODY_BYTES:
        raise ValueError(f"Response body exceeded limit of {_MAX_BODY_BYTES} bytes")
    try:
        text = body_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Malformed UTF-8 response payload") from exc
    try:
        return json.loads(text, parse_float=Decimal, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(f"Illegal JSON constant: {c}")))
    except Exception as exc:
        raise ValueError("Invalid JSON payload") from None


def _parse_retry_after(header_val: str | None, now: datetime) -> float | None:
    if not header_val:
        return None
    header_val = header_val.strip()
    if not header_val:
        return None
    if header_val.isdigit():
        val = float(header_val)
        return min(max(val, 0.0), 30.0)
    try:
        dt = parsedate_to_datetime(header_val)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        diff = (dt - now).total_seconds()
        return min(max(diff, 0.0), 30.0)
    except Exception:
        return None


def _epoch_to_vn_date(ts_val: Any) -> date:
    if type(ts_val) is bool or not isinstance(ts_val, (int, float, Decimal)):
        raise ValueError(f"Timestamp must be numeric: {ts_val!r}")
    val = float(ts_val)
    if val > 1e11:
        val = val / 1000.0
    elif val < 0 or val > 4e9:
        raise ValueError(f"Timestamp out of valid historical range: {ts_val}")
    try:
        dt_utc = datetime.fromtimestamp(val, tz=timezone.utc)
        dt_vn = dt_utc.astimezone(_VN_TZ)
        return dt_vn.date()
    except Exception as exc:
        raise ValueError(f"Timestamp conversion error: {ts_val}") from exc


def _to_clean_decimal(val: Any, multiplier: Decimal) -> Decimal | None:
    if val is None:
        return None
    if type(val) is bool:
        raise ValueError("Boolean cannot be converted to Decimal price")
    if isinstance(val, (int, str)):
        d = Decimal(str(val))
    elif isinstance(val, Decimal):
        d = val
    elif isinstance(val, float):
        d = Decimal(str(val))
    else:
        raise ValueError(f"Unsupported price type: {type(val)!r}")
    if not d.is_finite():
        raise ValueError(f"Price not finite: {d}")
    with localcontext() as ctx:
        ctx.prec = max(38, len(d.as_tuple().digits) + len(multiplier.as_tuple().digits))
        return d * multiplier


def _to_clean_volume(val: Any) -> int:
    if type(val) is bool:
        raise ValueError("Boolean cannot be converted to volume")
    if isinstance(val, int):
        vol = val
    elif isinstance(val, Decimal):
        if not val.is_finite():
            raise ValueError('Nonfinite volume')
        if val != val.to_integral_value():
            raise ValueError(f"Fractional volume not allowed: {val}")
        vol = int(val)
    elif isinstance(val, float):
        if not val.is_integer():
            raise ValueError(f"Fractional volume not allowed: {val}")
        vol = int(val)
    elif isinstance(val, str) and val.isdigit():
        vol = int(val)
    else:
        raise ValueError(f"Invalid volume value: {val!r}")
    if vol < 0 or vol > _MAX_SQLITE_INT:
        raise ValueError(f"Volume out of range: {vol}")
    return vol


def decode_daily(
    data: Mapping[str, Any],
    symbol: str,
    exchange: str,
    now: datetime,
    multiplier: Decimal,
    price_basis: str,
    volume_basis: str,
) -> list[Bar]:
    if (not isinstance(symbol, str) or not re.fullmatch(r'[A-Z0-9]{1,10}', symbol)
            or not isinstance(exchange, str) or exchange not in _ALLOWED_EXCHANGES
            or not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None
            or not isinstance(multiplier, Decimal) or not multiplier.is_finite() or multiplier <= 0
            or not isinstance(price_basis, str) or price_basis not in _ALLOWED_PRICE_BASIS
            or not isinstance(volume_basis, str) or volume_basis not in _ALLOWED_VOLUME_BASIS):
        raise ValueError('Invalid daily decode configuration')
    if not isinstance(data, Mapping):
        raise ValueError("Payload must be a dictionary/mapping")
    if "error" in data or data.get("status") in ("error", "failed"):
        raise ValueError("Upstream data returned error status")
    required_keys = ["t", "o", "h", "l", "c", "v"]
    for k in required_keys:
        if k not in data:
            raise ValueError(f"Missing required series key '{k}' in response")
        if not isinstance(data[k], list):
            raise ValueError(f"Series key '{k}' must be a list")

    t_list, o_list, h_list, l_list, c_list, v_list = (
        data["t"], data["o"], data["h"], data["l"], data["c"], data["v"]
    )
    n = len(t_list)
    if not (len(o_list) == n and len(h_list) == n and len(l_list) == n and len(c_list) == n and len(v_list) == n):
        raise ValueError(f"Misaligned OHLCV arrays: t={n}, o={len(o_list)}, h={len(h_list)}, l={len(l_list)}, c={len(c_list)}, v={len(v_list)}")

    bars: list[Bar] = []
    seen_dates: set[date] = set()
    for i in range(n):
        t_val = t_list[i]
        trade_date = _epoch_to_vn_date(t_val)
        if trade_date in seen_dates:
            raise ValueError(f"Duplicate trade date encountered in series: {trade_date}")
        seen_dates.add(trade_date)

        raw_o, raw_h, raw_l, raw_c, raw_v = o_list[i], h_list[i], l_list[i], c_list[i], v_list[i]
        vol = _to_clean_volume(raw_v)

        o_dec = _to_clean_decimal(raw_o, multiplier)
        h_dec = _to_clean_decimal(raw_h, multiplier)
        l_dec = _to_clean_decimal(raw_l, multiplier)
        c_dec = _to_clean_decimal(raw_c, multiplier)

        all_zero_or_none = (
            (o_dec is None or o_dec == 0) and
            (h_dec is None or h_dec == 0) and
            (l_dec is None or l_dec == 0) and
            (c_dec is None or c_dec == 0)
        )
        if all_zero_or_none and vol == 0:
            bar = Bar(
                symbol=symbol,
                exchange=exchange,
                trade_date=trade_date,
                open=None,
                high=None,
                low=None,
                close=None,
                volume=0,
                source="dnse",
                price_basis=price_basis,
                volume_basis=volume_basis,
                status="open",
                quality="no_trade",
                source_updated_at=None,
                received_at=now,
            )
        else:
            bar = Bar(
                symbol=symbol,
                exchange=exchange,
                trade_date=trade_date,
                open=o_dec,
                high=h_dec,
                low=l_dec,
                close=c_dec,
                volume=vol,
                source="dnse",
                price_basis=price_basis,
                volume_basis=volume_basis,
                status="open",
                quality="complete",
                source_updated_at=None,
                received_at=now,
            )
        bars.append(bar)
    return bars


class DNSEProvider:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        *,
        price_multiplier: Decimal,
        price_basis: str,
        volume_basis: str,
        transport: Callable[[str, Mapping[str, str]], tuple[int, Mapping[str, str], Any]] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 3,
        timeout: float = 15,
        api_version: str = _DEFAULT_API_VERSION,
    ) -> None:
        if not isinstance(api_key, str) or not api_key:
            raise ValueError("api_key must be a non-empty string")
        if not isinstance(api_secret, str) or not api_secret:
            raise ValueError("api_secret must be a non-empty string")
        if not isinstance(price_multiplier, Decimal) or not price_multiplier.is_finite() or price_multiplier <= 0:
            raise ValueError("price_multiplier must be a positive finite Decimal")
        if price_basis not in _ALLOWED_PRICE_BASIS:
            raise ValueError(f"Invalid price_basis: {price_basis}")
        if volume_basis not in _ALLOWED_VOLUME_BASIS:
            raise ValueError(f"Invalid volume_basis: {volume_basis}")
        if type(max_attempts) is not int or not (1 <= max_attempts <= 5):
            raise ValueError("max_attempts must be between 1 and 5")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not (0 < timeout <= 120):
            raise ValueError("timeout must be between 0 and 120 seconds")

        self._api_key = api_key
        self._api_secret = api_secret
        self.price_multiplier = price_multiplier
        self.price_basis = price_basis
        self.volume_basis = volume_basis
        self._transport = transport
        self._sleep = sleep
        self._max_attempts = max_attempts
        self._timeout = timeout
        self._api_version = api_version

    def __repr__(self) -> str:
        return f"DNSEProvider(api_key='***', price_basis={self.price_basis!r}, volume_basis={self.volume_basis!r})"

    def _default_transport(self, url: str, headers: Mapping[str, str]) -> tuple[int, Mapping[str, str], Any]:
        if not url.startswith(_BASE_URL):
            raise ValueError(f"URL disallowed, must start with {_BASE_URL}")
        ctx = ssl.create_default_context()
        opener = urllib.request.build_opener(_StrictNoRedirect(), urllib.request.HTTPSHandler(context=ctx))
        req = urllib.request.Request(url, headers=dict(headers), method="GET")
        try:
            with opener.open(req, timeout=self._timeout) as resp:
                status = resp.status
                resp_headers = {k: v for k, v in resp.headers.items()}
                body = resp.read(_MAX_BODY_BYTES + 1)
                parsed = _parse_json_strictly(body)
                return status, resp_headers, parsed
        except urllib.error.HTTPError as exc:
            resp_headers = {k: v for k, v in exc.headers.items()} if exc.headers else {}
            status = exc.code
            exc.close()
            return status, resp_headers, {}
        except urllib.error.URLError as exc:
            raise OSError(f"Network error connecting to DNSE: {exc.reason}") from None

    def _execute_with_retry(self, path_with_query: str, now: datetime) -> Any:
        clean_path = path_with_query.split("?")[0]
        full_url = f"{_BASE_URL}{path_with_query}"
        last_err: Exception | None = None

        for attempt in range(1, self._max_attempts + 1):
            nonce = uuid.uuid4().hex
            stamp = formatdate(timeval=None, localtime=False, usegmt=True)
            hdrs = rest_headers(self._api_key, self._api_secret, clean_path, stamp, nonce, self._api_version)
            try:
                if self._transport is not None:
                    status, resp_headers, payload = self._transport(full_url, hdrs)
                else:
                    status, resp_headers, payload = self._default_transport(full_url, hdrs)
            except OSError as err:
                last_err = RuntimeError(f"DNSE transport connection failure on attempt {attempt}")
                if attempt == self._max_attempts:
                    raise last_err from None
                self._sleep(min(0.5 * (2 ** (attempt - 1)), 30.0))
                continue
            except Exception as err:
                # Redact any accidental credential leak in exception
                raise RuntimeError("DNSE request failed") from None

            if 200 <= status < 300:
                if not isinstance(payload, Mapping):
                    raise ValueError("DNSE upstream returned non-dictionary response")
                return payload

            if status in (401, 403):
                raise RuntimeError(f"DNSE authentication/authorization failed with HTTP {status}")

            if status in (429, 500, 502, 503, 504):
                last_err = RuntimeError(f"DNSE transient HTTP error {status}")
                if attempt == self._max_attempts:
                    raise last_err
                retry_after_hdr = resp_headers.get("Retry-After") or resp_headers.get("retry-after")
                parsed_wait = _parse_retry_after(retry_after_hdr, now)
                wait_time = parsed_wait if parsed_wait is not None else min(0.5 * (2 ** (attempt - 1)), 30.0)
                self._sleep(wait_time)
                continue

            raise RuntimeError(f"DNSE upstream returned unhandled HTTP error {status}")

        raise last_err or RuntimeError("DNSE request attempts exhausted")

    def history(
        self,
        symbol: str,
        exchange: str,
        start: date,
        end: date,
        now: datetime,
    ) -> list[Bar]:
        if not isinstance(symbol, str) or not re.fullmatch(r'[A-Z0-9]{1,10}', symbol):
            raise ValueError("Invalid symbol")
        if exchange not in _ALLOWED_EXCHANGES:
            raise ValueError(f"Invalid exchange: {exchange}")
        if not isinstance(start, date) or isinstance(start, datetime):
            raise ValueError("start must be a date")
        if not isinstance(end, date) or isinstance(end, datetime):
            raise ValueError("end must be a date")
        if start > end:
            raise ValueError(f"start date ({start}) cannot be after end date ({end})")
        if (end - start).days > 366:
            raise ValueError("Requested date range exceeds maximum allowed limit of 366 calendar days")
        if not isinstance(now, datetime) or now.tzinfo is None or now.tzinfo.utcoffset(now) is None:
            raise ValueError("now must be an aware datetime")

        # Local VN midnight epoch seconds
        start_dt = datetime.combine(start, dt_time.min, tzinfo=_VN_TZ)
        end_next_dt = datetime.combine(end + timedelta(days=1), dt_time.min, tzinfo=_VN_TZ)
        from_ts = int(start_dt.timestamp())
        to_ts = int(end_next_dt.timestamp()) - 1

        query = urlencode({
            "symbol": symbol,
            "resolution": "1D",
            "type": "STOCK",
            "from": str(from_ts),
            "to": str(to_ts),
        })
        path_with_query = f"{_OHLC_PATH}?{query}"
        payload = self._execute_with_retry(path_with_query, now)
        bars = decode_daily(payload, symbol, exchange, now, self.price_multiplier, self.price_basis, self.volume_basis)
        return [b for b in bars if start <= b.trade_date <= end]

    def decode_stream(self, payload: Mapping[str, Any], symbol_exchanges: Mapping[str, str], now: datetime) -> Bar | None:
        if not isinstance(payload, Mapping):
            return None
        msg_type = payload.get("T")
        if msg_type not in ("b", "bc"):
            return None

        if payload.get("type") != "STOCK":
            return None
        if str(payload.get("resolution")) != "1D":
            return None

        symbol = payload.get("symbol")
        if not symbol or symbol not in symbol_exchanges:
            return None
        exchange = symbol_exchanges[symbol]
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        if any(field not in payload for field in ('open', 'high', 'low', 'close', 'volume')):
            raise ValueError("Streaming candle missing OHLCV fields")

        raw_time = payload.get("time")
        if raw_time is None:
            raise ValueError("Streaming candle missing time")
        trade_date = _epoch_to_vn_date(raw_time)

        source_updated_at: datetime | None = None
        raw_updated = payload.get("lastUpdated")
        if raw_updated is not None:
            if type(raw_updated) is bool or not isinstance(raw_updated, (int, float, Decimal)):
                raise ValueError("lastUpdated must be numeric")
            up_val = float(raw_updated)
            if up_val > 1e11:
                up_val = up_val / 1000.0
            source_updated_at = datetime.fromtimestamp(up_val, tz=timezone.utc)
            if source_updated_at > now + timedelta(seconds=60):
                raise ValueError(f"source_updated_at ({source_updated_at}) is in the future relative to now ({now})")

        vol = _to_clean_volume(payload.get("volume", 0))
        o_dec = _to_clean_decimal(payload.get("open"), self.price_multiplier)
        h_dec = _to_clean_decimal(payload.get("high"), self.price_multiplier)
        l_dec = _to_clean_decimal(payload.get("low"), self.price_multiplier)
        c_dec = _to_clean_decimal(payload.get("close"), self.price_multiplier)

        all_zero_or_none = (
            (o_dec is None or o_dec == 0) and
            (h_dec is None or h_dec == 0) and
            (l_dec is None or l_dec == 0) and
            (c_dec is None or c_dec == 0)
        )
        if all_zero_or_none and vol == 0:
            return Bar(
                symbol=symbol,
                exchange=exchange,
                trade_date=trade_date,
                open=None,
                high=None,
                low=None,
                close=None,
                volume=0,
                source="dnse",
                price_basis=self.price_basis,
                volume_basis=self.volume_basis,
                status="open",
                quality="no_trade",
                source_updated_at=source_updated_at,
                received_at=now,
            )
        return Bar(
            symbol=symbol,
            exchange=exchange,
            trade_date=trade_date,
            open=o_dec,
            high=h_dec,
            low=l_dec,
            close=c_dec,
            volume=vol,
            source="dnse",
            price_basis=self.price_basis,
            volume_basis=self.volume_basis,
            status="open",
            quality="complete",
            source_updated_at=source_updated_at,
            received_at=now,
        )
