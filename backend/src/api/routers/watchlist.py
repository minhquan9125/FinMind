"""Per-user company watchlist, stored in public.watchlists."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from ...auth.authorization import READ_ROLES, Principal, require_roles
from ...core.db import get_pool

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])
reader = require_roles(*READ_ROLES)
Symbol = Annotated[str, Path(pattern=r"^[A-Za-z0-9]{1,10}$")]

_COMPANY = "c.symbol AS ticker, c.company_name AS name, c.sector, c.exchange"
_ACTIVE = "c.is_active IS NOT FALSE"


@router.get("")
async def watchlist(principal: Principal = Depends(reader), pool=Depends(get_pool)):
    """The user's followed companies, plus every active company that can be added."""
    async with pool.acquire() as conn:
        items = await conn.fetch(
            f"""SELECT {_COMPANY}, w.pinned_at FROM public.watchlists w
                JOIN public.companies c USING (company_id)
                WHERE w.user_id = $1 ORDER BY w.pinned_at NULLS FIRST, c.symbol""",
            principal.user_id)
        companies = await conn.fetch(f"SELECT {_COMPANY} FROM public.companies c WHERE {_ACTIVE} ORDER BY c.symbol")
    return {"items": [dict(r) for r in items], "companies": [dict(r) for r in companies]}


@router.put("/{symbol}", status_code=204)
async def follow(symbol: Symbol, principal: Principal = Depends(reader), pool=Depends(get_pool)):
    """Follow a company. Following it again keeps the original pinned time."""
    async with pool.acquire() as conn:
        company_id = await conn.fetchval(
            f"SELECT c.company_id FROM public.companies c WHERE c.symbol = $1 AND {_ACTIVE}", symbol.upper())
        if company_id is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy doanh nghiệp.")
        await conn.execute(
            """INSERT INTO public.watchlists (user_id, company_id, pinned_at) VALUES ($1, $2, now())
               ON CONFLICT (user_id, company_id) DO NOTHING""",
            principal.user_id, company_id)


@router.delete("/{symbol}", status_code=204)
async def unfollow(symbol: Symbol, principal: Principal = Depends(reader), pool=Depends(get_pool)):
    """Stop following a company. Removing one that is not followed is not an error."""
    async with pool.acquire() as conn:
        await conn.execute(
            """DELETE FROM public.watchlists w USING public.companies c
               WHERE w.company_id = c.company_id AND w.user_id = $1 AND c.symbol = $2""",
            principal.user_id, symbol.upper())
