import http.client
import json
import threading
import pytest
from ohlcv.app.server import ChartServer
from ohlcv.storage.store import ProjectPaths


@pytest.fixture
def server(local_tmp):
    (local_tmp/'web/chart.html').write_text('<meta http-equiv="Content-Security-Policy" content="connect-src \'none\'"><body>Chart</body>', encoding='utf-8')
    class FakeService:
        lock=threading.Lock()
        def fetch(self,*args):
            raise RuntimeError('Test fixture has no provider')
        def load(self, symbol, refresh=False):
            if symbol == 'BAD': raise ValueError('Unknown ticker')
            return {'version':1,'count':0,'bars':[], 'symbol':symbol}
    instance=ChartServer(('127.0.0.1',0),ProjectPaths(local_tmp),service=FakeService())
    thread=threading.Thread(target=instance.serve_forever,daemon=True)
    thread.start()
    yield instance
    instance.shutdown()
    instance.server_close()
    thread.join()

def request(server,method,path,body=None,headers=None):
    conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
    conn.request(method,path,body,headers or {})
    res=conn.getresponse()
    result=(res.status,res.read(),dict(res.getheaders()))
    conn.close()
    return result

def auth(server):
    return {'Origin':server.origin, 'X-Chart-Token':server.token,'Content-Type':'application/json'}

def test_serve_only_chart_and_health(server):
    status,body,headers=request(server,'GET','/')
    assert status==200 and server.token.encode() in body
    assert headers['Cache-Control']=='no-store'
    assert request(server,'GET','/api/health')[0]==200
    assert request(server,'GET','/../.agent-state/vnstock-home/api_key.json')[0]==404
    assert request(server,'GET','/README.md')[0]==404

def test_cross_origin_and_host_blocked(server):
    assert request(server,'POST','/api/load','{"symbol":"FPT"}')[0]==403
    bad=auth(server)|{'Origin':'https://evil.example'}
    assert request(server,'POST','/api/load','{"symbol":"FPT"}',bad)[0]==403
    assert request(server,'GET','/',headers={'Host':'evil.example'})[0]==403
    assert request(server,'POST','/api/load','{"symbol":"FPT"}',auth(server)|{'X-Chart-Token':'ä'*64})[0]==403

def test_load_and_bad_requests(server):
    assert request(server,'POST','/api/load','{"symbol":"FPT"}',auth(server))[0]==200
    assert request(server,'POST','/api/load','{"symbol":"BAD"}',auth(server))[0]==400
    assert request(server,'POST','/api/load','{"symbol":"FPT","refresh":"yes"}',auth(server))[0]==400
    assert request(server,'POST','/api/load','not json',auth(server))[0]==400
    assert request(server,'POST','/api/load','x'*2049,auth(server))[0]==413

def test_detect_own_existing_server(server):
    from ohlcv.app.server import existing_chart
    assert existing_chart(server.server_port) is True


def test_live_endpoints_enforce_auth_and_fields(server):
    calls=[]
    class Live:
        def status(self,symbol):calls.append(('session',symbol));return {'session':{'active':False,'phase':'ended'}}
        def quote(self,symbol):calls.append(('quote',symbol));return {'session':{'active':False},'quote':None}
    server.live=Live()
    for route in ('/api/session','/api/quote'):
        assert request(server,'POST',route,'{"symbol":"FPT"}')[0]==403
        assert request(server,'POST',route,'{"symbol":"FPT","refresh":true}',auth(server))[0]==400
        assert request(server,'POST',route,'{"symbol":"FPT"}',auth(server))[0]==200
    assert calls==[('session','FPT'),('quote','FPT')]


def test_latest_saved_snapshot_embedding_escapes_script(server):
    text='<body><script id="initial-data" type="application/json">{}</script>'
    server.paths.output('web/chart.html').write_text(text,encoding='utf-8')
    server.paths.atomic_json('data/stocks/FPT/data.json',{'name':'</script><script>alert(1)</script>','bars':[]})
    status,raw,_=request(server,'GET','/')
    assert status==200
    assert b'alert(1)' in raw and b'\\u003c/script>' in raw
    assert raw.count(b'<script')==1


def test_production_server_sdk_budget_and_shutdown(local_tmp,monkeypatch):
    import ohlcv.app.server as module
    from ohlcv.realtime.session import RateBudget
    now=[0];calls=[]
    class Client:
        def __init__(self,paths):pass
        def __call__(self,*args):calls.append(args);return {'rows':[]}
        def close(self):calls.append(('close',))
    monkeypatch.setattr(module,'SDKClient',Client)
    monkeypatch.setattr(module,'RateBudget',lambda:RateBudget(clock=lambda:now[0]))
    monkeypatch.setattr(module.time,'sleep',lambda delay:now.__setitem__(0,now[0]+delay))
    instance=ChartServer(('127.0.0.1',0),ProjectPaths(local_tmp))
    try:
        instance.service.fetch('history','FPT');instance.service.fetch('catalog')
        assert now[0]==5
        assert instance.live.lock is instance.service.lock
        assert instance.live.budget.reserve()==5
        assert calls==[('history','FPT'),('catalog',None)]
    finally:instance.server_close()
    assert calls[-1]==('close',)

@pytest.mark.parametrize('own_server',[True,False])
def test_launcher_reuses_only_own_server(monkeypatch,own_server):
    import ohlcv.app.server as module
    calls=[]
    def occupied(*args,**kwargs): raise OSError('busy')
    monkeypatch.setattr(module,'ChartServer',occupied)
    monkeypatch.setattr(module,'existing_chart',lambda port:own_server)
    monkeypatch.setattr(module.webbrowser,'open',lambda url:calls.append(url))
    assert module.main(['--open']) == (0 if own_server else 2)
    assert calls==(['http://127.0.0.1:18765/'] if own_server else [])
