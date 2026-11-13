"""The signed-in user's watchlist, stored in public.watchlists (one row per user and company)."""
from fastapi import APIRouter, Depends, HTTPException

from ...auth.authorization import Principal, current_principal
from ...core.db import get_pool

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

_LIST = """SELECT c.symbol AS id, c.company_name AS name, c.sector, c.exchange, w.pinned_at
           FROM watchlists w JOIN companies c USING (company_id)
           WHERE w.user_id = $1 ORDER BY w.pinned_at, c.symbol"""


@router.get("")
async def list_watchlist(principal: Principal = Depends(current_principal)) -> list[dict]:
    rows = await get_pool().fetch(_LIST, principal.user_id)
    return [{**dict(row), "pinned_at": row["pinned_at"].isoformat() if row["pinned_at"] else None} for row in rows]


@router.put("/{symbol}")
async def add_symbol(symbol: str, principal: Principal = Depends(current_principal)) -> list[dict]:
    company_id = await get_pool().fetchval(
        "SELECT company_id FROM companies WHERE symbol = $1 AND is_active", symbol.upper())
    if company_id is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy doanh nghiệp.")
    await get_pool().execute(
        "INSERT INTO watchlists(user_id, company_id, pinned_at) VALUES ($1, $2, now()) "
        "ON CONFLICT (user_id, company_id) DO NOTHING", principal.user_id, company_id)
    return await list_watchlist(principal)


@router.delete("/{symbol}")
async def remove_symbol(symbol: str, principal: Principal = Depends(current_principal)) -> list[dict]:
    await get_pool().execute(
        "DELETE FROM watchlists w USING companies c "
        "WHERE w.company_id = c.company_id AND w.user_id = $1 AND c.symbol = $2",
        principal.user_id, symbol.upper())
    return await list_watchlist(principal)
