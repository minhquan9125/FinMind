"""Saved market data with a shared, bounded live-price overlay."""

import hashlib
import json
import re
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from ...market_data.repository import FileMarketDataRepository
from ...market_data.live import BusyError, stock_symbol

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
    request: Request,
    response: Response,
    limit: int = Query(60, ge=1, le=250),
    if_none_match: str | None = Header(default=None),
    repository: FileMarketDataRepository = Depends(get_market_data_repository),
) -> Any:
    try:
        normalized = normalize_symbol(symbol)
        service = getattr(request.app.state, "live", None)
        result = (service.read(normalized, limit, repository=repository) if service is not None
                  else repository.get_ohlcv(normalized, limit))
        # Both live quotes and requested limit participate in the HTTP validator.
        version = '"' + hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False).encode()).hexdigest() + '"'
        if if_none_match == version:
            return Response(status_code=304, headers={"ETag": version, "Cache-Control": "no-cache"})
        response.headers["ETag"] = version
        response.headers["Cache-Control"] = "no-cache"
        return result
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail="Không đọc được dữ liệu OHLCV đã lưu.") from exc


class ViewerRequest(BaseModel):
    symbol: str = Field(min_length=3, max_length=10)


class ViewerResponse(BaseModel):
    symbol: str | None = None
    watching: bool
    poll_seconds: float | None = None


def get_live_service(request: Request):
    service = getattr(request.app.state, "live", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Tự cập nhật giá đang tắt; API vẫn đọc dữ liệu đã lưu.")
    return service


@router.put("/live/viewers/{viewer_id}", response_model=ViewerResponse)
def watch_price(viewer_id: UUID, body: ViewerRequest, service=Depends(get_live_service)):
    try:
        symbol = stock_symbol(body.symbol.upper())
        service.watch(str(viewer_id), symbol)
        return {"symbol": symbol, "watching": True, "poll_seconds": service.poll_seconds}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except OverflowError:
        raise HTTPException(status_code=429, detail="Đã đạt giới hạn mã hoặc người xem.", headers={"Retry-After": "20"}) from None


@router.delete("/live/viewers/{viewer_id}", response_model=ViewerResponse)
def unwatch_price(viewer_id: UUID, service=Depends(get_live_service)):
    service.unwatch(str(viewer_id))
    return {"watching": False}


@router.post("/stocks/{symbol}/refresh")
def refresh_price(symbol: str, service=Depends(get_live_service)) -> dict:
    try:
        return service.refresh(stock_symbol(symbol.upper()))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except BusyError as exc:
        raise HTTPException(status_code=429, detail=str(exc), headers={"Retry-After": str(exc.wait_seconds)}) from None
    except (RuntimeError, OSError):
        raise HTTPException(status_code=503, detail="Nguồn chưa trả giá hợp lệ; giữ biểu đồ gần nhất và thử lại sau.") from None


@router.get("/live/status")
def live_status(service=Depends(get_live_service)) -> dict:
    return service.status()


@router.post("/stocks/{symbol}/history")
def load_stock_history(symbol: str, service=Depends(get_live_service)) -> dict:
    try:
        return service.stock_history(stock_symbol(symbol.upper()))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except BusyError as exc:
        raise HTTPException(status_code=429, detail=str(exc), headers={"Retry-After": str(exc.wait_seconds)}) from None
    except (RuntimeError, OSError):
        raise HTTPException(status_code=503, detail="Chưa tải được lịch sử cổ phiếu; giữ biểu đồ đã có.") from None


@router.post("/companies/{symbol}/news/refresh")
def refresh_company_news(symbol: str, request: Request) -> dict:
    service = getattr(request.app.state, "news", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Bộ lấy tin chưa chạy.")
    try:
        return service.refresh(stock_symbol(symbol.upper()))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except BusyError as exc:
        raise HTTPException(status_code=429, detail="Đang chờ lấy tin; vui lòng thử lại sau.", headers={"Retry-After": str(exc.wait_seconds)}) from None


@router.get("/indices/{symbol}/ohlcv")
def get_index_history(symbol: str, service=Depends(get_live_service)) -> dict:
    try:
        return service.index_history(symbol.upper())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except BusyError as exc:
        raise HTTPException(status_code=429, detail=str(exc), headers={"Retry-After": str(exc.wait_seconds)}) from None
    except (RuntimeError, OSError):
        raise HTTPException(status_code=503, detail="Chưa lấy được dữ liệu chỉ số; vui lòng thử lại sau.") from None


@router.get("/news")
def get_market_news(limit: int = Query(10, ge=1, le=50),
                    repository: FileMarketDataRepository = Depends(get_market_data_repository)) -> dict:
    try:
        return repository.get_news(None, limit)
    except (OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=503, detail="Không đọc được tin thị trường đã lưu.") from exc


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
