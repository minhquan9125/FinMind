from datetime import date
from decimal import Decimal
import pytest
from ohlcv.core.models import Bar
from ohlcv.providers.dnse import decode_daily, rest_headers
from test_provider import NOW, provider


def series():
    return dict(t=[1791219600], o=[100], h=[105], l=[99], c=[102], v=[1000])


def test_provider_returns_shared_model_and_version_header():
    bar = decode_daily(series(), 'FPT', 'HOSE', NOW, Decimal('1'), 'raw', 'matched')[0]
    assert isinstance(bar, Bar)
    assert rest_headers('key', 'secret', '/price/ohlc', 'stamp', 'nonce')['version'] == '2026-07-23'


@pytest.mark.parametrize('field', ['open', 'high', 'low', 'close', 'volume'])
def test_missing_stream_field_is_not_no_trade(field):
    payload = dict(T='b', symbol='FPT', type='STOCK', resolution='1D', time=1791219600,
                   lastUpdated=NOW.timestamp(), open=0, high=0, low=0, close=0, volume=0)
    del payload[field]
    with pytest.raises(ValueError):
        provider().decode_stream(payload, {'FPT':'HOSE'}, NOW)


def test_invalid_symbol_rejected_before_request():
    calls = []
    p = provider(transport=lambda *args: calls.append(args))
    with pytest.raises(ValueError):
        p.history('../FPT', 'HOSE', date(2026, 10, 5), date(2026, 10, 6), NOW)
    assert not calls


def test_source_error_payload_not_echoed():
    p = provider(transport=lambda *args: (200, {}, {'error':'test-secret'}))
    with pytest.raises(ValueError) as exc:
        p.history('FPT', 'HOSE', date(2026, 10, 5), date(2026, 10, 6), NOW)
    assert 'test-secret' not in str(exc.value)


@pytest.mark.parametrize('attempts', [True, 1.5, 0, 6])
def test_invalid_attempt_count(attempts):
    with pytest.raises(ValueError):
        provider(max_attempts=attempts)


def test_scaling_retains_long_decimal_precision():
    value = Decimal('100.1234567890123456789012345678901234567890123456789')
    data = series()
    data.update(o=[value], c=[value])
    bar = decode_daily(data, 'FPT', 'HOSE', NOW, Decimal('1000'), 'raw', 'matched')[0]
    assert str(bar.open) == '100123.4567890123456789012345678901234567890123456789000'
