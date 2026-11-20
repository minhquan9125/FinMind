from datetime import date
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routers import companies as api
from src.auth.authorization import Principal, current_principal
from src.core.db import get_pool
from src.financial.company_facts import build_periods, period_status


def row(period, code, value, unit='VND', status='VERIFIED', ptype='YEAR', year=2025, quarter=None, end=date(2025, 12, 31)):
    return dict(period_code=period, period_type=ptype, fiscal_year=year, quarter=quarter, end_date=end,
                published_at=date(2026, 3, 20), code=code, value=Decimal(value), unit=unit, v_status=status)


def test_bank_revenue_is_operating_income_and_growth_needs_same_unit():
    rows = [row('2025-YEAR', 'TOTAL_OPERATING_INCOME', '120'), row('2025-YEAR', 'NET_REVENUE', '999'),
            row('2024-YEAR', 'TOTAL_OPERATING_INCOME', '100', year=2024, end=date(2024, 12, 31)),
            row('2026-Q1', 'TOTAL_OPERATING_INCOME', '50', unit='SOURCE_NATIVE', ptype='QUARTER', year=2026, quarter=1, end=date(2026, 3, 31)),
            row('2025-Q1', 'TOTAL_OPERATING_INCOME', '40', ptype='QUARTER', year=2025, quarter=1, end=date(2025, 3, 31))]
    periods = {p['period']: p for p in build_periods(rows, 'BANK')}
    assert periods['2025-YEAR']['facts']['revenue']['value'] == 120
    assert abs(periods['2025-YEAR']['facts']['revenueYoy']['value'] - 0.2) < 1e-9
    assert 'revenueYoy' not in periods['2026-Q1']['facts']  # VND vs unconfirmed unit: no growth
    assert periods['2025-YEAR']['label'] == 'Năm 2025' and periods['2026-Q1']['label'] == 'Quý 1/2026'


def test_periods_are_newest_first_with_year_before_q4():
    rows = [row('2025-Q4', 'TOTAL_ASSETS', '1', ptype='QUARTER', quarter=4), row('2025-YEAR', 'TOTAL_ASSETS', '1'),
            row('2026-Q1', 'TOTAL_ASSETS', '1', ptype='QUARTER', year=2026, quarter=1, end=date(2026, 3, 31))]
    assert [p['period'] for p in build_periods(rows, 'TECH')] == ['2026-Q1', '2025-YEAR', '2025-Q4']


def test_period_status_ignores_unchecked_ratios():
    rows = [row('2025-YEAR', 'TOTAL_ASSETS', '1'), row('2025-YEAR', 'ROE', '0.2', unit='SOURCE_NATIVE', status=None)]
    assert build_periods(rows, 'TECH')[0]['status'] == 'VERIFIED'
    assert period_status(['VERIFIED', 'MISMATCH']) == 'MISMATCH'
    assert period_status(['VERIFIED', None]) == 'PARTIAL'
    assert period_status([None, None]) is None


class Conn:
    async def fetchrow(self, sql, *args):
        return None

    def transaction(self, **kw):
        class Tx:
            async def __aenter__(self): return None
            async def __aexit__(self, *exc): return False
        return Tx()


class Pool:
    def acquire(self):
        class Ctx:
            async def __aenter__(self): return Conn()
            async def __aexit__(self, *exc): return False
        return Ctx()


def test_unknown_company_is_404_and_role_is_required():
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_pool] = lambda: Pool()
    app.dependency_overrides[current_principal] = lambda: Principal(None, frozenset({'RESEARCHER'}))
    assert TestClient(app).get('/api/companies/ZZZ').status_code == 404
    app.dependency_overrides[current_principal] = lambda: Principal(None, frozenset())
    assert TestClient(app).get('/api/companies/FPT').status_code == 403
