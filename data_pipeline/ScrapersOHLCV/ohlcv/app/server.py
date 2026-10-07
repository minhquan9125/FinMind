"""Local chart UI: only explicit ticker requests trigger bounded vnstock fetching."""
from __future__ import annotations

import argparse
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import secrets
import sys
import threading
import time
from urllib.parse import urlsplit
import webbrowser

from ohlcv.storage.store import ProjectPaths
from ohlcv.history.vnstock import StockService
from ohlcv.realtime.session import RateBudget
from ohlcv.realtime.quote import LiveService
from ohlcv.sdk.client import SDKClient


class ChartServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, paths, *, service=None, live=None):
        if address[0] != '127.0.0.1':
            raise ValueError('Chart server must bind to loopback only')
        self.paths = paths
        self.sdk = None
        budget=RateBudget()
        if service is None:
            self.sdk=SDKClient(paths)
            def fetch(action,symbol=None):
                while True:
                    wait=budget.reserve(3)
                    if not wait:break
                    time.sleep(wait)
                return self.sdk(action,symbol)
            self.service=StockService(paths,fetch=fetch)
        else:
            self.service=service
        def fetch_live(action,symbol):
            if self.sdk:
                saved=json.loads(paths.output(f'data/stocks/{symbol}/data.json').read_text(encoding='utf-8'))
                return self.sdk(action,symbol,automatic_exchange=saved['bars'][-1]['exchange'])
            return self.service.fetch(action,symbol)
        self.live=live or LiveService(paths,fetch=fetch_live,budget=budget,lock=self.service.lock)
        self.token = secrets.token_hex(32)
        super().__init__(address, ChartHandler)
        self.origin = f'http://127.0.0.1:{self.server_port}'

    def server_close(self):
        super().server_close()
        if self.sdk:self.sdk.close()


class ChartHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def send(self, status, payload, content_type='application/json; charset=utf-8'):
        raw = payload if isinstance(payload,bytes) else json.dumps(payload,ensure_ascii=False,allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(raw)

    def valid_host(self):
        return self.headers.get('Host') == urlsplit(self.server.origin).netloc

    def do_GET(self):
        if not self.valid_host():
            self.send(403,{'error':'Host không hợp lệ.'})
            return
        route = urlsplit(self.path).path
        if route in ('/','/chart.html'):
            try:
                text = self.server.paths.output('web/chart.html').read_text(encoding='utf-8')
                # Restore the newest saved FPT snapshot on launch without contacting the provider.
                saved=self.server.paths.output('data/stocks/FPT/data.json')
                if saved.is_file():
                    snapshot=json.loads(saved.read_text(encoding='utf-8'))
                    raw=json.dumps(snapshot,ensure_ascii=False,allow_nan=False).replace('<','\\u003c')
                    text=re.sub(r'(<script id="initial-data" type="application/json">)[\s\S]*?(</script>)',
                                lambda match:match[1]+'\n'+raw+'\n'+match[2],text,count=1)
                text = text.replace("connect-src 'none'", "connect-src 'self'")
                text = text.replace('<body>',f'<body><meta name="chart-token" content="{self.server.token}">',1)
                self.send(200,text.encode('utf-8'),'text/html; charset=utf-8')
            except OSError:
                self.send(500,{'error':'Không đọc được chart.html.'})
        elif route == '/api/health':
            self.send(200,{'application':'ScrapersOHLCV','mode':'vnstock','version':1})
        elif route == '/api/stocks':
            folder = self.server.paths.output('data/stocks')
            symbols=[]
            if folder.is_dir():
                for item in folder.iterdir():
                    try:
                        from ohlcv.history.vnstock import normalize_symbol
                        symbol = normalize_symbol(item.name)
                        if self.server.paths.output(f'data/stocks/{symbol}/data.json').is_file():
                            symbols.append(symbol)
                    except ValueError:
                        continue
            self.send(200,{'symbols':sorted(symbols)})
        else:
            self.send(404,{'error':'Không tìm thấy.'})

    def do_POST(self):
        token = self.headers.get('X-Chart-Token','')
        if (not self.valid_host() or self.headers.get('Origin') != self.server.origin
                or not token.isascii() or not secrets.compare_digest(token,self.server.token)):
            self.send(403,{'error':'Hãy mở biểu đồ từ server cục bộ.'})
            return
        if self.path not in ('/api/load','/api/session','/api/quote'):
            self.send(404,{'error':'Không tìm thấy.'})
            return
        try:
            length = int(self.headers.get('Content-Length','0'))
            if not 0 < length <= 2048:
                self.send(413,{'error':'Yêu cầu quá lớn hoặc rỗng.'})
                return
            if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
                raise ValueError('Cần yêu cầu JSON.')
            payload = json.loads(self.rfile.read(length))
            allowed={'symbol','refresh'} if self.path=='/api/load' else {'symbol'}
            if not isinstance(payload,dict) or set(payload)-allowed:
                raise ValueError('Yêu cầu không hợp lệ.')
            refresh = payload.get('refresh',False)
            if type(refresh) is not bool:
                raise ValueError('refresh phải là boolean.')
            if self.path=='/api/session':
                data=self.server.live.status(payload.get('symbol'))
            elif self.path=='/api/quote':
                data=self.server.live.quote(payload.get('symbol'))
            else:
                data = self.server.service.load(payload.get('symbol'),refresh=refresh)
            self.send(200,data)
        except (ValueError,TypeError) as issue:
            self.send(400,{'error':str(issue)})
        except RuntimeError as issue:
            self.send(503,{'error':str(issue)})
        except (OSError,KeyError):
            self.send(500,{'error':'Không đọc hoặc lưu được dữ liệu; bản lưu trước vẫn được giữ.'})


def existing_chart(port):
    connection = http.client.HTTPConnection('127.0.0.1',port,timeout=2)
    try:
        connection.request('GET','/api/health')
        response=connection.getresponse()
        raw=response.read(1025)
        return response.status==200 and len(raw)<=1024 and json.loads(raw)=={'application':'ScrapersOHLCV','mode':'vnstock','version':1}
    except (OSError,ValueError,http.client.HTTPException):
        return False
    finally:
        connection.close()


def main(argv=None):
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description='Biểu đồ vnstock với ô nhập mã và thư mục dữ liệu từng mã.')
    parser.add_argument('--port',type=int,default=18765)
    parser.add_argument('--open',action='store_true',help='Mở trình duyệt khi khởi động')
    args=parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error('Port phải từ 1024 đến 65535.')
    try:
        server=ChartServer(('127.0.0.1',args.port),ProjectPaths())
    except OSError:
        if existing_chart(args.port):
            url=f'http://127.0.0.1:{args.port}/'
            print(f'Biểu đồ đã chạy: {url}')
            if args.open:
                webbrowser.open(url)
            return 0
        print(f'Cổng {args.port} đang được ứng dụng khác sử dụng hoặc không mở được; chọn --port khác.')
        return 2
    print(f'Biểu đồ: {server.origin}/\nDữ liệu: data/stocks/<MÃ>/data.json\nTự lấy mã đang xem trong phiên; ngoài phiên lấy thủ công. Ctrl+C để dừng.',flush=True)
    if args.open:
        threading.Timer(.5,lambda:webbrowser.open(server.origin+'/')).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
