"""Read-only endpoints backed by saved crawler files."""

import json
import re
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response

from ...market_data.repository import FileMarketDataRepository

router = APIRouter(prefix="/api/market-data", tags=["market-data"])


def get_market_data_repository() -> FileMarketDataRepository:
    # Swap this dependency for a Supabase reader later. The API contract stays the same.
    return FileMarketDataRepository()


def normalize_symbol(symbol: str) -> str:
    normalized = symbol.upper()
    if not re.fullmatch(r"[A-Z0-9]{1,10}", normalized):
        raise HTTPException(status_code=400, detail="Mã chứng khoán không hợp lệ.")
    return normalized


@router.get("/stocks/{symbol}/ohlcv")
def get_ohlcv(
    symbol: str,
    response: Response,
    limit: int = Query(60, ge=1, le=250),
    if_none_match: str | None = Header(default=None),
    repository: FileMarketDataRepository = Depends(get_market_data_repository),
) -> Any:
    try:
        normalized = normalize_symbol(symbol)
        version = repository.ohlcv_version(normalized)
        if version and if_none_match == version:
            return Response(status_code=304, headers={"ETag": version, "Cache-Control": "no-cache"})
        result = repository.get_ohlcv(normalized, limit)
        if version:
            response.headers["ETag"] = version
        response.headers["Cache-Control"] = "no-cache"
        return result
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail="Không đọc được dữ liệu OHLCV đã lưu.") from exc


@router.get("/companies/{symbol}/news")
def get_news(
    symbol: str,
    limit: int = Query(10, ge=1, le=50),
    repository: FileMarketDataRepository = Depends(get_market_data_repository),
) -> dict:
    try:
        return repository.get_news(normalize_symbol(symbol), limit)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail="Không đọc được tin FireAnt đã lưu.") from exc
