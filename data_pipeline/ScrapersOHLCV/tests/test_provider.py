import base64
import hashlib
import hmac
from datetime import date, datetime, timezone
from decimal import Decimal
from urllib.parse import quote

import pytest

from ohlcv.providers.dnse import DNSEProvider, decode_daily, rest_headers, websocket_auth


NOW = datetime(2026, 10, 6, 3, 0, tzinfo=timezone.utc)


def provider(**kwargs):
    return DNSEProvider("test-key", "test-secret", price_multiplier=Decimal("1000"),
                        price_basis="raw", volume_basis="matched", **kwargs)


def test_rest_signature_matches_documented_path_only_protocol():
    stamp = "Tue, 06 Oct 2026 03:00:00 +0000"
    nonce = "0123456789abcdef0123456789abcdef"
    result = rest_headers("test-key", "test-secret", "/price/ohlc", stamp, nonce)
    signing = f"(request-target): get /price/ohlc\ndate: {stamp}\nnonce: {nonce}"
    expected = quote(base64.b64encode(hmac.new(b"test-secret", signing.encode(), hashlib.sha256).digest()).decode(), safe="")
    assert f'signature="{expected}"' in result["X-Signature"]
    assert result["Date"] == stamp
    assert result["X-Api-Key"] == "test-key"


def test_websocket_auth_protocol():
    result = websocket_auth("key", "secret", 123, "unique")
    assert result["signature"] == hmac.new(b"secret", b"key:123:unique", hashlib.sha256).hexdigest()
    assert result["action"] == "auth"


def test_snapshot_uses_update_timestamp_not_candle_start():
    payload = {"T": "b", "symbol": "FPT", "type": "STOCK", "resolution": "1D",
               "time": 1791219600, "lastUpdated": NOW.timestamp(),
               "open": 100, "high": 105, "low": 99, "close": 102, "volume": 1500}
    bar = provider().decode_stream(payload, {"FPT": "HOSE"}, NOW)
    assert bar.trade_date == date(2026, 10, 6)
    assert bar.open == Decimal("100000")
    assert bar.volume == 1500
    assert bar.source_updated_at == NOW
    assert bar.status == "open"


def test_expected_price_and_intraday_messages_do_not_become_daily_candles():
    assert provider().decode_stream({"T": "e", "symbol": "FPT", "expectedPrice": 100}, {"FPT": "HOSE"}, NOW) is None
    assert provider().decode_stream({"T": "b", "symbol": "FPT", "resolution": "1"}, {"FPT": "HOSE"}, NOW) is None


def test_decode_history_arrays_and_zero_volume_no_trade():
    data = {"t": [1791219600], "o": [100], "h": [105], "l": [99], "c": [102], "v": [1000]}
    bars = decode_daily(data, "FPT", "HOSE", NOW, Decimal("1000"), "raw", "matched")
    assert bars[0].close == Decimal("102000")
    # A source sentinel is no_trade only when every price is zero/null and volume=0.
    data.update(o=[0], h=[0], l=[0], c=[0], v=[0])
    empty = decode_daily(data, "FPT", "HOSE", NOW, Decimal("1000"), "raw", "matched")[0]
    assert empty.quality == "no_trade"
    assert empty.open is None


@pytest.mark.parametrize("payload", [
    {"t": [1791219600], "o": [], "h": [1], "l": [1], "c": [1], "v": [1]},
    {"error": "upstream failure"},
    {"t": [1791219600], "o": [1], "h": [1], "l": [1], "c": [1], "v": [1.5]},
])
def test_bad_source_payloads_are_not_silently_truncated(payload):
    with pytest.raises(ValueError):
        decode_daily(payload, "FPT", "HOSE", NOW, Decimal("1000"), "raw", "matched")


def test_http_auth_failures_do_not_log_or_retry_credentials():
    calls = []
    def transport(url, headers):
        calls.append(url)
        return 401, {}, {"message": "test-secret"}
    with pytest.raises(RuntimeError) as error:
        provider(transport=transport).history("FPT", "HOSE", date(2026, 10, 5), date(2026, 10, 6), NOW)
    assert "test-secret" not in str(error.value)
    assert len(calls) == 1


def test_http_transient_failure_retries_with_new_signature():
    signatures = []
    def transport(url, headers):
        signatures.append(headers["X-Signature"])
        if len(signatures) == 1:
            return 503, {}, {}
        return 200, {}, {"t": [], "o": [], "h": [], "l": [], "c": [], "v": []}
    assert provider(transport=transport, sleep=lambda _: None).history("FPT", "HOSE", date(2026, 10, 5), date(2026, 10, 6), NOW) == []
    assert len(set(signatures)) == 2


def test_history_request_is_daily_and_bounded_to_local_trading_dates():
    urls = []
    def transport(url, headers):
        urls.append(url)
        return 200, {}, {"t": [], "o": [], "h": [], "l": [], "c": [], "v": []}
    provider(transport=transport).history("FPT", "HOSE", date(2026, 10, 5), date(2026, 10, 6), NOW)
    assert "resolution=1D" in urls[0]
    assert "type=STOCK" in urls[0]
    assert urls[0].startswith("https://openapi.dnse.com.vn/price/ohlc?")
