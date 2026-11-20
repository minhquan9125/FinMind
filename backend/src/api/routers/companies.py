"""Company catalog and per-company BCTC facts (read-only)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from ...auth.authorization import READ_ROLES, require_roles
from ...core.db import get_pool
from ...financial.company_facts import company_detail, list_companies

router = APIRouter(prefix="/api/companies", tags=["companies"], dependencies=[Depends(require_roles(*READ_ROLES))])
Symbol = Annotated[str, Path(pattern=r"^[A-Za-z0-9]{1,10}$")]


@router.get("")
async def companies(pool=Depends(get_pool)):
    async with pool.acquire() as conn:
        return {"items": await list_companies(conn)}


@router.get("/{symbol}")
async def company(symbol: Symbol, pool=Depends(get_pool)):
    async with pool.acquire() as conn:
        async with conn.transaction(readonly=True):
            detail = await company_detail(conn, symbol.upper())
    if detail is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy doanh nghiệp.")
    return detail
