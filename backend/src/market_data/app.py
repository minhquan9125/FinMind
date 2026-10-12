"""Standalone market API; one shared guest SDK collector for visible charts."""

import asyncio
from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..api.routers.market_data import router
from .live import LiveCoordinator
from .repository import FileMarketDataRepository
from .sdk import BatchSDKClient, CollectorLock
from .session import SessionGate
from .news import FireAntNews, NewsService


@asynccontextmanager
async def lifespan(app):
    app.state.live = None
    root = Path(os.getenv("FINMIND_DATA_ROOT") or Path(__file__).resolve().parents[3]).resolve()
    news_fetch = FireAntNews()
    app.state.news = NewsService(news_fetch, FileMarketDataRepository(root))
    if os.getenv("FINMIND_LIVE_ENABLED", "1") == "0":
        try:
            yield
        finally:
            news_fetch.close()
            app.state.news = None
        return
    collector_lock = CollectorLock(root / ".agent-state/market-live/collector.lock")
    collector_lock.acquire()
    sdk = BatchSDKClient(root)
    stop = asyncio.Event()
    task = None
    try:
        service = LiveCoordinator(lambda symbols: sdk(symbols, automatic=True), SessionGate(root), FileMarketDataRepository(root),
                                  manual_fetch=sdk,
                                  history_fetch=sdk.history,
                                  poll_seconds=float(os.getenv("FINMIND_LIVE_POLL_SECONDS", "5")))
        app.state.live = service

        async def collect():
            while not stop.is_set():
                await asyncio.to_thread(service.tick)
                try:
                    await asyncio.wait_for(stop.wait(), timeout=1)
                except TimeoutError:
                    pass

        task = asyncio.create_task(collect())
        yield
    finally:
        stop.set()
        try:
            if task:
                await task  # Finish in-flight work before closing SDK/releasing exclusive lock.
        finally:
            try:
                await asyncio.to_thread(sdk.close)
            finally:
                collector_lock.close()
                app.state.live = None
                news_fetch.close()
                app.state.news = None

app = FastAPI(title="FinMind Market Data API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:5174", "http://127.0.0.1:5174",
    ],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    expose_headers=["ETag", "Retry-After"],
)
app.include_router(router)
