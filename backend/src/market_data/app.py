"""Standalone read-only API for local UI work without PostgreSQL."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..api.routers.market_data import router

app = FastAPI(title="FinMind Market Data API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:5174", "http://127.0.0.1:5174",
    ],
    allow_methods=["GET"],
    allow_headers=["*"],
    expose_headers=["ETag"],
)
app.include_router(router)
