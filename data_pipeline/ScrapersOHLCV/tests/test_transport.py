from datetime import date
from decimal import Decimal
from urllib.error import HTTPError
import urllib.request
import pytest
from ohlcv.providers.dnse import decode_daily
from test_provider import provider, NOW


class Response:
    def __init__(self, data):
        self.data, self.status, self.headers, self.limit = data, 200, {}, None
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def read(self, limit):
        self.limit = limit
        return self.data


def test_default_http_transport_verifies_tls_limits_body_and_preserves_decimal(monkeypatch):
    response = Response(b'{"t":[1791219600],"o":[100.1234567890123456789],"h":[105],"l":[99],"c":[102],"v":[1000]}')
    handlers, requests = [], []
    class Opener:
        def open(self, request, timeout):
            requests.append((request, timeout))
            return response
    def build(*values):
        handlers.extend(values)
        return Opener()
    monkeypatch.setattr(urllib.request, 'build_opener', build)
    bars = provider().history('FPT','HOSE',date(2026,10,6),date(2026,10,6),NOW)
    assert bars[0].open == Decimal('100123.4567890123456789000')
    assert response.limit == 5*1024*1024+1
    tls = next(h for h in handlers if isinstance(h, urllib.request.HTTPSHandler))
    assert tls._context.check_hostname
    assert requests[0][0].get_header('Version') == '2026-07-23'


def test_default_http_auth_failure_closes_error_response(monkeypatch):
    import io
    body = io.BytesIO(b'secret-test-response')
    error = HTTPError('https://openapi.dnse.com.vn/price/ohlc',401,'secret-test-response',{},body)
    class Opener:
        def open(self,*args,**kwargs):
            raise error
    monkeypatch.setattr(urllib.request,'build_opener',lambda *args: Opener())
    with pytest.raises(RuntimeError) as exc:
        provider().history('FPT','HOSE',date(2026,10,6),date(2026,10,6),NOW)
    assert 'secret-test-response' not in str(exc.value)
    assert body.closed


@pytest.mark.parametrize('bad', [b'{broken', b'{"x":NaN}', b'\xff', b'x'*(5*1024*1024+1)], ids=['broken','nonfinite','utf8','oversized'])
def test_invalid_default_response_no_retry_or_sensitive_error(monkeypatch, bad):
    calls = []
    class Opener:
        def open(self,*args,**kwargs):
            calls.append(1)
            return Response(bad)
    monkeypatch.setattr(urllib.request,'build_opener',lambda *args: Opener())
    with pytest.raises(RuntimeError):
        provider().history('FPT','HOSE',date(2026,10,6),date(2026,10,6),NOW)
    assert calls == [1]


def test_network_failure_retry_and_new_nonce(monkeypatch):
    from urllib.error import URLError
    calls = []
    class Opener:
        def open(self,request,timeout):
            calls.append(request.get_header('X-signature'))
            if len(calls) == 1:
                raise URLError('test-secret')
            return Response(b'{"t":[],"o":[],"h":[],"l":[],"c":[],"v":[]}')
    monkeypatch.setattr(urllib.request,'build_opener',lambda *args: Opener())
    assert provider(sleep=lambda _:None).history('FPT','HOSE',date(2026,10,6),date(2026,10,6),NOW) == []
    assert len(set(calls)) == 2


@pytest.mark.parametrize('multiplier,basis', [(Decimal('-1'),'raw'),(Decimal('1'),'invalid')])
def test_empty_decoder_still_validates_config(multiplier, basis):
    with pytest.raises(ValueError):
        decode_daily(dict(t=[],o=[],h=[],l=[],c=[],v=[]),'FPT','HOSE',NOW,multiplier,basis,'matched')


def test_nonfinite_volume_is_rejected_consistently():
    data = dict(t=[1791219600],o=[100],h=[105],l=[99],c=[102],v=[Decimal('NaN')])
    with pytest.raises(ValueError):
        decode_daily(data,'FPT','HOSE',NOW,Decimal('1'),'raw','matched')
