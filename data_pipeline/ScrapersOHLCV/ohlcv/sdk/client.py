"""One isolated persistent SDK process; keeps SDK quota state across quote polls."""
import atexit
from decimal import Decimal
import json
import queue
import subprocess
import threading


class SDKClient:
    def __init__(self, paths, *, timeout=90):
        self.paths=paths
        self.timeout=timeout
        self.lock=threading.Lock()
        self.process=None
        self.responses=None
        atexit.register(self.close)

    def _start(self):
        executable=self.paths.output('.agent-state/vnstock-venv/Scripts/python.exe')
        if not executable.is_file():
            raise RuntimeError('Chưa có môi trường vnstock. Xem README.md.')
        self.process=subprocess.Popen([str(executable),'-B','-m','ohlcv.sdk.worker','--serve'],
            cwd=self.paths.root,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            text=True,encoding='utf-8',bufsize=1,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        responses=queue.Queue()
        self.responses=responses
        stream=self.process.stdout
        def read():
            try:
                while True:
                    line=stream.readline(5*1024*1024+1)
                    if not line or len(line)>5*1024*1024:
                        responses.put(None);return
                    responses.put(line)
            except (OSError,ValueError):
                responses.put(None)
        threading.Thread(target=read,daemon=True).start()

    def _close(self):
        if self.process:
            self.process.kill()
            self.process.wait(timeout=5)
            for stream in (self.process.stdin,self.process.stdout):
                stream.close()
            self.process=None

    def close(self):
        with self.lock:
            self._close()

    def __call__(self, action, symbol=None, *, automatic_exchange=None):
        from ohlcv.history.vnstock import normalize_symbol
        if action not in ('catalog','history','quote'):
            raise ValueError('Invalid SDK action')
        if action!='catalog':symbol=normalize_symbol(symbol)
        if automatic_exchange is not None and automatic_exchange not in ('HOSE','HNX','UPCOM'):
            raise ValueError('Invalid automatic exchange')
        with self.lock:
            try:
                if self.process is None or self.process.poll() is not None:
                    self._close();self._start()
                self.process.stdin.write(json.dumps({'action':action,'symbol':symbol,'automatic_exchange':automatic_exchange})+'\n')
                self.process.stdin.flush()
                line=self.responses.get(timeout=self.timeout)
                if line is None:
                    raise RuntimeError('SDK process stopped')
                payload=json.loads(line,parse_float=Decimal)
                if not isinstance(payload,dict) or 'error' in payload:
                    raise RuntimeError('SDK request failed')
                return payload
            except (OSError,ValueError,RuntimeError,queue.Empty):
                self._close()
                raise RuntimeError('Nguồn vnstock/KBS không phản hồi hoặc đang giới hạn lượt gọi; thử lại sau.') from None
