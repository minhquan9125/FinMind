"""Đẩy dữ liệu crawler lên Supabase ngay khi crawler lưu file JSON.

JSON vẫn là bộ nhớ đệm cục bộ của crawler (crawler đọc lại để gộp dữ liệu). Mỗi lần lưu xong,
crawler gọi push_ohlcv / push_news để ghi thêm vào database. Module này KHÔNG BAO GIỜ làm crawler
lỗi: thiếu DATABASE_URL, thiếu thư viện hoặc database không kết nối được thì chỉ in cảnh báo.

Tắt hẳn: đặt biến môi trường FINMIND_DB_SINK=off. Cần DATABASE_URL trong .env hoặc backend/.env.
Logic ghi dùng chung với backend/scripts/ingest_market_news_to_supabase.py (script nạp bù dữ liệu cũ).
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
import time
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INGEST_SCRIPT = PROJECT_ROOT / "backend" / "scripts" / "ingest_market_news_to_supabase.py"
MIN_SECONDS_BETWEEN_PRICE_PUSHES = 60  # tự cập nhật 5 giây/lần: gộp lại, không đẩy liên tục
TIMEOUT_SECONDS = 60

_lock = threading.Lock()
_last_push: dict[str, float] = {}
_warned: set[str] = set()
_ingest: Any = None


def _warn(key: str, message: str) -> None:
    if key not in _warned:
        _warned.add(key)
        print(f"[supabase_sink] {message}", file=sys.stderr, flush=True)


def _database_url() -> str | None:
    if os.environ.get("FINMIND_DB_SINK", "").lower() in {"off", "0", "false"}:
        return None
    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / "backend" / ".env")
        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass
    return os.environ.get("DATABASE_URL")


def _load_ingest() -> Any:
    global _ingest
    if _ingest is None:
        spec = importlib.util.spec_from_file_location("finmind_ingest_market_news", INGEST_SCRIPT)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        module.STABLE_PAYLOAD_IDS = True  # một payload/job cho mỗi file, ghi đè tại chỗ
        _ingest = module
    return _ingest


async def _with_connection(url: str, work) -> None:
    import asyncpg
    conn = await asyncpg.connect(url, ssl="require" if "supabase" in url else None,
                                 statement_cache_size=0, timeout=20)
    try:
        await work(conn)
    finally:
        await conn.close()


def _run(url: str, work) -> None:
    # Chạy trong luồng riêng để không vướng event loop đang chạy (nếu có) của crawler.
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(asyncio.run, _with_connection(url, work)).result(timeout=TIMEOUT_SECONDS)


def push_ohlcv(path: Path, payload: dict[str, Any]) -> None:
    """Gọi sau khi lưu data/stocks/<MÃ>/data.json hoặc live.json."""
    try:
        path = Path(path).resolve()
        if path.name not in {"data.json", "live.json"} or path.parent.parent.name != "stocks":
            return
        url = _database_url()
        if not url:
            return
        now = time.monotonic()
        with _lock:
            if now - _last_push.get(str(path), -1e9) < MIN_SECONDS_BETWEEN_PRICE_PUSHES:
                return
            _last_push[str(path)] = now
        ingest = _load_ingest()
        if not path.is_relative_to(ingest.OHLCV_DIR.resolve()):
            return  # file ngoài thư mục dữ liệu thật (vd: test dùng thư mục tạm) thì không đẩy
        data_path = path.parent / "data.json"
        if path.name == "data.json":
            plan = ingest.build_price_plan(data_path, payload)
            live_file = path.parent / "live.json"
            plan["live"] = json.loads(live_file.read_text(encoding="utf-8")) if live_file.exists() else None
            _run(url, lambda conn: ingest.apply_prices(conn, [plan], overwrite=True))
        else:
            plan = {"symbol": path.parent.name.upper(), "path": data_path, "live": payload, "live_path": path,
                    "source": "vnstock_kbs", "is_index": path.parent.name.upper() in ingest.INDEX_SYMBOLS}
            _run(url, lambda conn: ingest.apply_live(conn, plan))
    except Exception as exc:  # noqa: BLE001 - sink không được làm hỏng crawler
        _warn("ohlcv", f"Không đẩy được dữ liệu giá lên Supabase ({type(exc).__name__}: {exc}). Crawler vẫn lưu JSON bình thường.")


def push_news(path: Path, payload: dict[str, Any]) -> None:
    """Gọi sau khi lưu một file tin theo ngày trong scrapers/data/."""
    try:
        path = Path(path).resolve()
        url = _database_url()
        if not url or not isinstance(payload, dict) or not isinstance(payload.get("articles"), list):
            return
        ingest = _load_ingest()
        if not path.is_relative_to(ingest.NEWS_DIR.resolve()):
            return  # file ngoài thư mục dữ liệu thật (vd: test dùng thư mục tạm) thì không đẩy
        files, articles = ingest.build_news_plan(path, payload)
        if files and articles:
            _run(url, lambda conn: ingest.apply_news(conn, files, articles))
    except Exception as exc:  # noqa: BLE001
        _warn("news", f"Không đẩy được tin tức lên Supabase ({type(exc).__name__}: {exc}). Crawler vẫn lưu JSON bình thường.")
