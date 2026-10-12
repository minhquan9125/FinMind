"""Bounded IPC, one SDK process and one cross-process collector lock."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time


class CollectorLock:
    def __init__(self, path):
        self.path = Path(path)
        self.stream = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("a+b")
        try:
            if os.name == "nt":
                import msvcrt
                if self.path.stat().st_size == 0:
                    self.stream.write(b"0")
                    self.stream.flush()
                self.stream.seek(0)
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.stream.close()
            self.stream = None
            raise RuntimeError("Bộ lấy giá đã chạy ở tiến trình khác. Chỉ chạy API giá với --workers 1.") from None

    def close(self):
        if self.stream is not None:
            if os.name == "nt":
                import msvcrt
                self.stream.seek(0)
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            self.stream.close()
            self.stream = None


class BatchSDKClient:
    def __init__(self, root, *, executable=None, timeout=40):
        self.root = Path(root).resolve()
        self.home = self.root / ".agent-state/market-live/sdk-home"
        installed = self.root / "data_pipeline/ScrapersOHLCV/.agent-state/vnstock-venv/Scripts/python.exe"
        self.executable = executable or os.getenv("FINMIND_VNSTOCK_PYTHON") or (str(installed) if installed.is_file() else sys.executable)
        self.timeout = timeout
        self.process = None
        self.responses = None
        self.lock = threading.Lock()
        self.restart_after = 0

    def _start(self):
        import time
        if time.monotonic() < self.restart_after:
            raise RuntimeError("SDK đang nghỉ sau lỗi; thử lại sau.")
        env = {**os.environ, "FINMIND_LIVE_SDK_HOME": str(self.home), "PYTHONDONTWRITEBYTECODE": "1"}
        self.process = subprocess.Popen(
            [self.executable, "-B", "-m", "backend.src.market_data.sdk_worker"], cwd=self.root,
            env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", bufsize=1, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        responses = queue.Queue(maxsize=2)
        self.responses = responses
        stream = self.process.stdout

        def read():
            try:
                while True:
                    line = stream.readline(2 * 1024 * 1024 + 1)
                    if not line or len(line) > 2 * 1024 * 1024:
                        responses.put_nowait(None)
                        return
                    responses.put_nowait(line)
            except (OSError, ValueError, queue.Full):
                try:
                    responses.put_nowait(None)
                except queue.Full:
                    pass
        threading.Thread(target=read, daemon=True).start()

    def _close(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.kill()
            self.process.wait(timeout=5)
            for stream in (self.process.stdin, self.process.stdout):
                stream.close()
            self.process = None

    def close(self):
        with self.lock:
            self._close()

    def __call__(self, symbols, *, automatic=False):
        import time
        from .live import stock_symbol
        if not 1 <= len(symbols) <= 100:
            raise ValueError("Invalid batch size")
        symbols = [stock_symbol(symbol) for symbol in symbols]
        return self._send({"symbols": symbols, "automatic": automatic})

    def history(self, symbol):
        from .history import INDEX_NAMES
        if symbol not in INDEX_NAMES:
            from .live import stock_symbol
            stock_symbol(symbol)
        return self._send({"action": "index_history" if symbol in INDEX_NAMES else "stock_history", "symbol": symbol})

    def _send(self, payload):
        with self.lock:
            try:
                if self.process is None or self.process.poll() is not None:
                    self._close()
                    self._start()
                self.process.stdin.write(json.dumps(payload) + "\n")
                self.process.stdin.flush()
                line = self.responses.get(timeout=self.timeout)
                if line is None:
                    self._close()
                    self.restart_after = time.monotonic() + 60
                    raise RuntimeError("SDK đã dừng; thử lại sau.")
                result = json.loads(line)
                if not isinstance(result, dict) or "error" in result:
                    # A normal SDK error keeps the process and its quota counters alive.
                    raise RuntimeError("SDK chưa trả dữ liệu hợp lệ.")
                return result
            except (OSError, ValueError, queue.Empty):
                self._close()
                self.restart_after = time.monotonic() + 60
                raise RuntimeError("SDK không phản hồi; thử lại sau.") from None
