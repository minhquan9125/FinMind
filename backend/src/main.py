"""FinMind backend: auth, market data, Vector RAG and fixture research chat.

Research chat reuses intent/evidence validation with fixed fixtures. It does not
query the live vector search or generate financial answers from real data.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .documents.chunk_reconstruction import ReconstructionError

from .api.routers import auth, documents, search, market_data, research_chat
from .market_data.app import lifespan as market_lifespan
from .core.config import get_settings
from .core.db import connect, disconnect


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect()
    try:
        async with market_lifespan(app):
            yield
    finally:
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

@app.get("/")
async def root() -> dict:
    return {"message": "FinMind Backend API is running successfully!", "docs": "/docs", "health": "/api/health"}


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
