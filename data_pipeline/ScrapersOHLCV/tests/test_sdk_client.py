import io
import json
import queue
import sys
from types import SimpleNamespace

import pandas as pd
import pytest

from ohlcv.sdk.client import SDKClient
from ohlcv.storage.store import ProjectPaths


class Process:
    def __init__(self,lines=''):
        self.stdin=io.StringIO();self.stdout=io.StringIO(lines);self.killed=False
    def poll(self):return None
    def kill(self):self.killed=True
    def wait(self,timeout):return 0


def test_persistent_sdk_protocol_reuses_process_and_decimal_tokens(local_tmp,monkeypatch):
    paths=ProjectPaths(local_tmp)
    executable=paths.output('.agent-state/vnstock-venv/Scripts/python.exe')
    executable.parent.mkdir(parents=True);executable.write_bytes(b'test stub')
    process=Process('{"rows":[{"price":0.125}]}\n{"rows":[]}\n');starts=[]
    def popen(*args,**kwargs):starts.append((args,kwargs));return process
    monkeypatch.setattr('ohlcv.sdk.client.subprocess.Popen',popen)
    client=SDKClient(paths,timeout=.1)
    assert str(client('quote','FPT')['rows'][0]['price'])=='0.125'
    assert client('catalog')['rows']==[]
    assert len(starts)==1 and '--serve' in starts[0][0][0]
    assert starts[0][1]['cwd']==paths.root
    assert [json.loads(line)['action'] for line in process.stdin.getvalue().splitlines()]==['quote','catalog']
    client.close();assert process.killed


@pytest.mark.parametrize('line',['{"error":"failed"}\n','not-json\n','[]\n',''])
def test_bad_sdk_protocol_kills_child(local_tmp,monkeypatch,line):
    paths=ProjectPaths(local_tmp);process=Process(line)
    client=SDKClient(paths,timeout=.01)
    def start():
        client.process=process;client.responses=queue.Queue();client.responses.put(line or None)
    monkeypatch.setattr(client,'_start',start)
    with pytest.raises(RuntimeError):client('quote','FPT')
    assert process.killed and client.process is None
    client.close()


def test_timeout_and_missing_environment(local_tmp,monkeypatch):
    client=SDKClient(ProjectPaths(local_tmp),timeout=.01)
    with pytest.raises(RuntimeError):client('catalog')
    process=Process()
    def start():client.process=process;client.responses=queue.Queue()
    monkeypatch.setattr(client,'_start',start)
    with pytest.raises(RuntimeError):client('history','FPT')
    assert process.killed
    with pytest.raises(ValueError):client('exec','FPT')
    with pytest.raises(ValueError):client('quote','../FPT')


def test_worker_serve_protocol_scoped_environment_and_one_sdk_import(local_tmp,monkeypatch):
    from ohlcv.sdk import worker
    import os
    paths=ProjectPaths(local_tmp);calls=[]
    history=pd.DataFrame([{'time':'2026-10-06','open':62.,'high':62.2,'low':60.,'close':60.4,'volume':10}])
    quote=pd.DataFrame([{'symbol':'FPT','exchange':'HOSE','TD':'06/10/2026','open_price':62000.,
                         'high_price':62200.,'low_price':60000.,'close_price':60400.,'volume_accumulated':10}])
    class Equity:
        def quote(self,**kwargs):calls.append(('quote',kwargs));return quote
        def ohlcv(self,**kwargs):calls.append(('history',kwargs));return history
    class Market:
        def equity(self,symbol):assert symbol=='FPT';return Equity()
    class Reference:
        def __init__(self):self.equity=self
        def list_by_exchange(self):return pd.DataFrame([{'symbol':'FPT','exchange':'HOSE','type':'stock'}])
    monkeypatch.setitem(sys.modules,'vnstock',SimpleNamespace(Market=Market,Reference=Reference))
    monkeypatch.setattr('ohlcv.storage.store.ProjectPaths',lambda:paths)
    monkeypatch.setattr('importlib.metadata.version',lambda name:'test version')
    for name in ('USERPROFILE','VNSTOCK_DISABLE_AGENT_SETUP','VNSTOCK_AGENT_TARGETS','VNSTOCK_TELEMETRY','MPLCONFIGDIR','TEMP','TMP','VNSTOCK_API_KEY'):
        monkeypatch.setenv(name,os.environ.get(name,''))
    monkeypatch.setattr(sys,'dont_write_bytecode',True)
    output=io.StringIO()
    monkeypatch.setattr(sys,'stdout',output)
    items=[{'action':action,'symbol':'FPT'} for action in ['quote','history','catalog','bad']]
    items.append({'action':'quote','symbol':'FPT','automatic_exchange':'HOSE'})
    monkeypatch.setattr(sys,'stdin',io.StringIO('\n'.join(json.dumps(item) for item in items)+'\n'))
    monkeypatch.setattr(sys,'argv',['worker','--serve'])
    assert worker.main()==0
    replies=[json.loads(line) for line in output.getvalue().splitlines()]
    assert replies[0]['rows'][0]['close_price']=='60400.0'
    assert replies[1]['rows'][0]['close']=='60.4'
    assert replies[2]['rows'][0]['symbol']=='FPT'
    assert 'error' in replies[3] and len(calls)==2
    assert replies[4]['session_closed'] is True  # No verified calendar in this isolated fixture.
    assert os.environ['USERPROFILE']==str(paths.output('.agent-state/vnstock-home'))
    assert 'VNSTOCK_API_KEY' not in os.environ
    monkeypatch.setattr(sys,'argv',['worker','history'])
    assert worker.main()==2
    monkeypatch.setattr(sys,'argv',['worker','exec'])
    assert worker.main()==2
