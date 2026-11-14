from __future__ import annotations

import json
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from urllib.error import HTTPError
import pytest

from ohlcv.providers.dnse import (
    Bar,
    DNSEProvider,
    decode_daily,
    rest_headers,
    websocket_auth,
    _StrictNoRedirect,
)

NOW = datetime(2026, 10, 6, 8, 30, tzinfo=timezone.utc)


def make_provider(**kwargs):
    return DNSEProvider(
        api_key="test-key",
        api_secret="super-secret-key-123",
        price_multiplier=Decimal("1000"),
        price_basis="raw",
        volume_basis="matched",
        **kwargs,
    )


def test_provider_repr_redacts_api_secret():
    p = make_provider()
    rep = repr(p)
    assert "super-secret-key-123" not in rep
    assert "test-key" not in rep
    assert "DNSEProvider" in rep


def test_rest_headers_rejects_crlf_and_quotes():
    with pytest.raises(ValueError, match="CR/LF"):
        rest_headers("key\r\nInjected: True", "secret", "/path", "stamp", "nonce")
    with pytest.raises(ValueError, match="quote"):
        rest_headers('key"withquotes', "secret", "/path", "stamp", "nonce")


def test_websocket_auth_validation():
    with pytest.raises(ValueError, match="timestamp must be an integer"):
        websocket_auth("key", "secret", "12345", "nonce")  # type: ignore
    res = websocket_auth("k", "s", 1700000000, "n1")
    assert res["action"] == "auth"
    assert isinstance(res["signature"], str)


def test_decode_daily_duplicate_timestamps_raise_value_error():
    data = {
        "t": [1791219600, 1791219600],
        "o": [100, 101],
        "h": [105, 105],
        "l": [99, 99],
        "c": [102, 103],
        "v": [1000, 2000],
    }
    with pytest.raises(ValueError, match="Duplicate trade date"):
        decode_daily(data, "FPT", "HOSE", NOW, Decimal("1000"), "raw", "matched")


def test_decode_daily_fractional_volume_rejected():
    data = {
        "t": [1791219600],
        "o": [100],
        "h": [105],
        "l": [99],
        "c": [102],
        "v": [1000.5],
    }
    with pytest.raises(ValueError, match="Fractional volume"):
        decode_daily(data, "FPT", "HOSE", NOW, Decimal("1000"), "raw", "matched")


def test_decode_daily_boolean_volume_and_prices_rejected():
    data = {
        "t": [1791219600],
        "o": [True],
        "h": [105],
        "l": [99],
        "c": [102],
        "v": [1000],
    }
    with pytest.raises(ValueError, match="Boolean"):
        decode_daily(data, "FPT", "HOSE", NOW, Decimal("1000"), "raw", "matched")

    data_bool_vol = {
        "t": [1791219600],
        "o": [100],
        "h": [105],
        "l": [99],
        "c": [102],
        "v": [True],
    }
    with pytest.raises(ValueError, match="Boolean"):
        decode_daily(data_bool_vol, "FPT", "HOSE", NOW, Decimal("1000"), "raw", "matched")


def test_decode_daily_explicit_unknown_provenance():
    data = {
        "t": [1791219600],
        "o": [100],
        "h": [105],
        "l": [99],
        "c": [102],
        "v": [1000],
    }
    bars = decode_daily(data, "FPT", "HOSE", NOW, Decimal("1000"), "unknown", "unknown")
    assert len(bars) == 1
    assert bars[0].price_basis == "unknown"
    assert bars[0].volume_basis == "unknown"
    assert bars[0].source == "dnse"
    assert bars[0].source_updated_at is None


def test_decode_daily_no_trade_sentinel_all_zero_prices():
    data = {
        "t": [1791219600],
        "o": [0],
        "h": [0],
        "l": [0],
        "c": [0],
        "v": [0],
    }
    bars = decode_daily(data, "FPT", "HOSE", NOW, Decimal("1000"), "raw", "matched")
    assert len(bars) == 1
    assert bars[0].quality == "no_trade"
    assert bars[0].open is None
    assert bars[0].high is None
    assert bars[0].low is None
    assert bars[0].close is None
    assert bars[0].volume == 0


def test_decode_stream_rejects_future_last_updated():
    far_future = (NOW + timedelta(minutes=5)).timestamp()
    payload = {
        "T": "b",
        "symbol": "FPT",
        "type": "STOCK",
        "resolution": "1D",
        "time": 1791219600,
        "lastUpdated": far_future,
        "open": 100,
        "high": 105,
        "low": 99,
        "close": 102,
        "volume": 1000,
    }
    with pytest.raises(ValueError, match="in the future"):
        make_provider().decode_stream(payload, {"FPT": "HOSE"}, NOW)


def test_decode_stream_bc_remains_open_status():
    payload = {
        "T": "bc",
        "symbol": "FPT",
        "type": "STOCK",
        "resolution": "1D",
        "time": 1791219600,
        "lastUpdated": NOW.timestamp(),
        "open": 100,
        "high": 105,
        "low": 99,
        "close": 102,
        "volume": 1000,
    }
    bar = make_provider().decode_stream(payload, {"FPT": "HOSE"}, NOW)
    assert bar is not None
    assert bar.status == "open"


def test_redirect_handler_rejection():
    handler = _StrictNoRedirect()
    class DummyReq:
        full_url = "https://openapi.dnse.com.vn/price/ohlc"
    with pytest.raises(HTTPError, match="Redirects not permitted"):
        handler.redirect_request(DummyReq(), None, 302, "Found", {}, "https://evil.com")


def test_history_range_exceeds_366_days_rejected():
    p = make_provider()
    with pytest.raises(ValueError, match="366 calendar days"):
        p.history("FPT", "HOSE", date(2025, 1, 1), date(2026, 1, 15), NOW)


def test_history_retry_after_handling():
    attempts = []
    def transport(url, headers):
        attempts.append(url)
        if len(attempts) == 1:
            return 429, {"Retry-After": "2"}, {}
        return 200, {}, {"t": [], "o": [], "h": [], "l": [], "c": [], "v": []}

    slept = []
    p = make_provider(transport=transport, sleep=lambda s: slept.append(s))
    bars = p.history("FPT", "HOSE", date(2026, 10, 5), date(2026, 10, 6), NOW)
    assert bars == []
    assert len(attempts) == 2
    assert slept == [2.0]
