"""Active company profiles and stored financial data for signed-in readers."""

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from ...auth.authorization import READ_ROLES, require_roles
from ...core.db import get_pool
from ...financial.health_db import get_company_financials, get_financial_health


router = APIRouter(prefix='/api/companies', tags=['companies'],
                   dependencies=[Depends(require_roles(*READ_ROLES))])

_COMPANIES = """
SELECT c.symbol AS id, c.company_name AS name, c.sector, c.exchange, c.industry_type,
       EXISTS (SELECT 1 FROM financial_reports r WHERE r.company_id=c.company_id) AS has_financials
FROM companies c WHERE c.is_active IS TRUE
"""
_READ_ERRORS = (RuntimeError, OSError, TimeoutError, asyncpg.PostgresError, asyncpg.InterfaceError)
_UNAVAILABLE = 'Không đọc được dữ liệu doanh nghiệp; vui lòng thử lại sau.'


async def _company(pool, symbol):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(_COMPANIES + ' AND c.symbol=$1', symbol)
    if row is None:
        raise HTTPException(status_code=404, detail='Không tìm thấy doanh nghiệp.')
    return dict(row)


@router.get('')
async def list_companies() -> list[dict]:
    try:
        async with get_pool().acquire() as conn:
            return [dict(row) for row in await conn.fetch(_COMPANIES + ' ORDER BY c.symbol')]
    except _READ_ERRORS:
        raise HTTPException(status_code=503, detail=_UNAVAILABLE) from None


@router.get('/{symbol}')
async def company_detail(symbol: str) -> dict:
    try:
        return await _company(get_pool(), symbol.upper())
    except _READ_ERRORS:
        raise HTTPException(status_code=503, detail=_UNAVAILABLE) from None


@router.get('/{symbol}/financials')
async def company_financials(symbol: str) -> dict:
    symbol = symbol.upper()
    try:
        pool = get_pool()
        await _company(pool, symbol)
        return {'symbol': symbol, 'periods': await get_company_financials(pool, symbol)}
    except _READ_ERRORS:
        raise HTTPException(status_code=503, detail=_UNAVAILABLE) from None


@router.get('/{symbol}/health')
async def company_health(symbol: str) -> dict:
    symbol = symbol.upper()
    try:
        pool = get_pool()
        await _company(pool, symbol)
        return await get_financial_health(pool, symbol) or {'status': 'NO_DATA'}
    except _READ_ERRORS:
        raise HTTPException(status_code=503, detail=_UNAVAILABLE) from None
