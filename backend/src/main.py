"""FinMind backend: auth, market data, Vector RAG and corpus research chat.

Research chat defaults to a pinned corpus and verified sources. Gemini is enabled
only with a configured key and explicit Free Tier confirmation; fixture CLI remains separate.
"""

from contextlib import asynccontextmanager
import asyncio
import logging
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .documents.chunk_reconstruction import ReconstructionError

from .api.routers import auth, documents, search, market_data, research_chat, hybrid_router
from .market_data.app import lifespan as market_lifespan
from .core.config import get_settings
from .core.db import connect, disconnect


settings = get_settings()
logger = logging.getLogger('uvicorn.error')


async def warmup_research(app: FastAPI):
    """Finish shared retrieval initialization before accepting the first request."""
    app.state.research_warmup = {'status': 'disabled'}
    app.state.router_warmup = {'status': 'disabled'}
    if not settings.research_chat_live or not settings.research_warmup_enabled:
        return
    started = time.monotonic()
    app.state.research_warmup = {'status': 'warming'}
    app.state.router_warmup = {'status': 'warming'}
    logger.info('Research warmup started: loading embedding model and retrieval cache')
    try:
        await asyncio.wait_for(
            asyncio.to_thread(hybrid_router.warmup_router),
            timeout=settings.research_warmup_timeout_seconds,
        )
    except Exception:
        app.state.router_warmup = {'status': 'failed', 'reason_code': 'ROUTER_WARMUP_FAILED'}
        logger.warning('Hybrid router warmup failed; the first request will retry')
    else:
        app.state.router_warmup = {'status': 'ready'}
        logger.info('Hybrid router warmup ready')
    try:
        store = research_chat.get_store()
        details = await asyncio.wait_for(store.engine.retriever.warmup(),
                                         timeout=settings.research_warmup_timeout_seconds)
    except Exception as exc:
        # Do not expose raw exceptions: DB/model errors may contain credentials/paths.
        code = 'WARMUP_TIMEOUT' if isinstance(exc, TimeoutError) else 'WARMUP_FAILED'
        app.state.research_warmup = {'status': 'failed', 'reason_code': code,
                                    'elapsed_seconds': round(time.monotonic()-started, 2)}
        logger.warning('Research warmup failed (%s); retrieval will retry on demand', code)
    else:
        app.state.research_warmup = {'status': 'ready', **details,
                                    'elapsed_seconds': round(time.monotonic()-started, 2)}
        logger.info('Research warmup ready (%.2fs)', time.monotonic()-started)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect()
    research_chat.get_store.cache_clear()
    try:
        async with market_lifespan(app):
            research_chat.configure_market_services(getattr(app.state, 'live', None), getattr(app.state, 'news', None))
            # Serve auth and health without waiting for model/cache initialization.
            # The chat shares this task's model lock and hybrid cache lock.
            warmup_task = asyncio.create_task(warmup_research(app), name='research-warmup')
            app.state.research_warmup_task = warmup_task
            await asyncio.sleep(0)
            try:
                yield
            finally:
                # Keep the event loop and DB pool alive until bounded warmup finishes.
                await warmup_task
    finally:
        research_chat.configure_market_services()
        await disconnect()


app = FastAPI(title="FinMind Vector RAG API", version="0.1.0", lifespan=lifespan)


@app.exception_handler(ReconstructionError)
async def source_reconstruction_error(request, exc):
    return JSONResponse(status_code=409, content={
        'detail': 'Không thể xác minh nội dung nguồn của kết quả. Cần kiểm tra hoặc lập chỉ mục lại nguồn.',
        'reason_code': exc.code,
    })

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_origin,
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["ETag", "Retry-After"],
)

app.include_router(documents.router)
app.include_router(search.router)
app.include_router(auth.router)
app.include_router(market_data.router)
app.include_router(research_chat.router)
app.include_router(hybrid_router.router)

@app.get("/")
async def root() -> dict:
    return {"message": "FinMind Backend API is running successfully!", "docs": "/docs", "health": "/api/health"}


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "research_warmup": getattr(app.state, 'research_warmup', {'status': 'not_started'}),
        "router_warmup": getattr(app.state, 'router_warmup', {'status': 'not_started'}),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
