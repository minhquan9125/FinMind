"""Company APIs use active DB rows and exact, individually verified financial facts."""

import asyncio
from contextlib import asynccontextmanager
from decimal import Decimal, localcontext
import importlib
import importlib.util
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from src.auth.authorization import Principal, current_principal
from src.financial import health_db


PATHS = (
    '/api/companies', '/api/companies/FPT',
    '/api/companies/FPT/financials', '/api/companies/FPT/health',
)
COMPANIES = [
    dict(id='ZZT', name='No reports', sector=None, exchange=None, industry_type=None, has_financials=False),
    dict(id='FPT', name='FPT Corporation', sector='Technology', exchange='HOSE',
         industry_type='TECH', has_financials=True),
]


class FakePool:
    def __init__(self, failure=None):
        self.calls, self.options, self.failure = [], [], failure

    @asynccontextmanager
    async def acquire(self):
        if self.failure:
            raise self.failure
        yield self

    @asynccontextmanager
    async def _transaction(self):
        yield

    def transaction(self, **options):
        self.options.append(options)
        return self._transaction()

    async def fetch(self, sql, *args):
        self.calls.append((sql, args))
        rows = [dict(row) for row in COMPANIES]
        if 'is_active' not in sql:
            rows.append(dict(COMPANIES[0], id='OLD'))
        if args:
            rows = [row for row in rows if row['id'] == args[0]]
        if 'ORDER BY' in sql.upper():
            rows.sort(key=lambda row: row['id'])
        return rows

    async def fetchrow(self, sql, *args):
        rows = await self.fetch(sql, *args)
        return rows[0] if rows else None


def observation(code='TOTAL_ASSETS', *, period='2026-Q3', value=Decimal('80000'),
                scale=Decimal('1000000000'), status='VERIFIED', **extra):
    section = ('INCOME_STATEMENT' if code in {'NET_REVENUE', 'PROFIT_AFTER_TAX', 'TOTAL_OPERATING_INCOME'}
               else 'CASH_FLOW' if code == 'CASH_FLOW_OPERATING' else 'BALANCE_SHEET')
    return dict(symbol='FPT', industry_type='TECH', section=section, code=code,
                period_code=period, value=value, scale=scale, unit='VND', currency='VND',
                locator_json={'unit_status': status}, observation_id=str(uuid4()),
                report_id='report-1', **extra)


@pytest.fixture
def company_client(monkeypatch):
    # Import the production app without running its DB/model/network lifespan.
    from src.main import app
    pool = FakePool()
    roles = ['RESEARCHER']
    app.dependency_overrides[current_principal] = lambda: Principal(uuid4(), frozenset(roles))
    if importlib.util.find_spec('src.api.routers.companies') is not None:
        router = importlib.import_module('src.api.routers.companies')
        monkeypatch.setattr(router, 'get_pool', lambda: pool)
    client = TestClient(app, raise_server_exceptions=False)
    try:
        yield client, pool, roles, app
    finally:
        client.close()
        app.dependency_overrides.pop(current_principal, None)


@pytest.mark.parametrize('path', PATHS)
def test_all_company_routes_require_login_and_a_read_role(company_client, path):
    client, pool, roles, app = company_client
    app.dependency_overrides.pop(current_principal)
    assert client.get(path).status_code == 401
    assert client.get(path, headers={'Authorization': 'Bearer invalid'}).status_code == 401
    app.dependency_overrides[current_principal] = lambda: Principal(uuid4(), frozenset(roles))
    roles[:] = ['GUEST']
    assert client.get(path).status_code == 403
    assert pool.calls == []


def test_list_and_detail_use_active_rows_has_reports_and_bound_symbols(company_client):
    client, pool, _, _ = company_client
    response = client.get('/api/companies')
    assert response.status_code == 200
    assert response.json() == [COMPANIES[1], COMPANIES[0]]
    response = client.get('/api/companies/fpt')
    assert response.status_code == 200
    assert response.json() == COMPANIES[1]
    for sql, args in pool.calls:
        assert 'is_active' in sql
        assert 'financial_reports' in sql
        assert 'EXISTS' in sql.upper()
        assert 'company_name' in sql
        assert 'FPT' not in sql
        if args:
            assert args == ('FPT',)


@pytest.mark.parametrize('suffix', ['', '/financials', '/health'])
@pytest.mark.parametrize('symbol', ['ZZZ', 'OLD'])
def test_unknown_and_inactive_company_is_404(company_client, symbol, suffix):
    client, _, _, _ = company_client
    response = client.get(f'/api/companies/{symbol}{suffix}')
    assert response.status_code == 404
    assert response.json() == {'detail': 'Không tìm thấy doanh nghiệp.'}


def test_known_company_without_reports_has_empty_financials_and_no_health(company_client, monkeypatch):
    client, _, _, _ = company_client
    called = []

    async def no_rows(conn, symbols):
        called.append(symbols)
        return []

    async def no_health(pool, symbol):
        assert symbol == 'ZZT'
        return None

    monkeypatch.setattr(health_db, 'fetch_health_records', no_rows)
    router = importlib.import_module('src.api.routers.companies')
    monkeypatch.setattr(router, 'get_financial_health', no_health)
    response = client.get('/api/companies/zzt/financials')
    assert response.status_code == 200
    assert response.json() == {'symbol': 'ZZT', 'periods': []}
    response = client.get('/api/companies/zzt/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'NO_DATA'}
    assert called == [['ZZT']]


def test_financials_route_and_health_return_the_domain_data(company_client, monkeypatch):
    client, pool, _, _ = company_client
    router = importlib.import_module('src.api.routers.companies')
    expected = [{'period': '2026-Q3', 'facts': [], 'source': None}]
    health = {'symbol': 'FPT', 'period': '2026-Q3', 'status': 'partial'}

    async def financials(received, symbol):
        assert received is pool and symbol == 'FPT'
        return expected

    async def financial_health(received, symbol):
        assert received is pool and symbol == 'FPT'
        return health

    monkeypatch.setattr(router, 'get_company_financials', financials)
    monkeypatch.setattr(router, 'get_financial_health', financial_health)
    response = client.get('/api/companies/fpt/financials')
    assert response.status_code == 200
    assert response.json() == {'symbol': 'FPT', 'periods': expected}
    response = client.get('/api/companies/fpt/health')
    assert response.status_code == 200
    assert response.json() == health


@pytest.mark.parametrize('path', PATHS)
def test_database_errors_are_sanitized(company_client, path):
    client, pool, _, _ = company_client
    pool.failure = OSError('postgresql://synthetic-user:synthetic-password@host/db')
    response = client.get(path)
    assert response.status_code == 503
    assert 'synthetic-password' not in response.text
    assert 'postgresql' not in response.text


def financials(monkeypatch, rows, citation=None):
    """New helper is looked up only when the test runs, so baseline collection stays valid."""
    pool, cited = FakePool(), []

    async def fetch(conn, symbols):
        assert conn is pool and symbols == ['FPT']
        return rows

    async def cite(conn, observation_id):
        assert conn is pool
        cited.append(observation_id)
        return citation

    monkeypatch.setattr(health_db, 'fetch_health_records', fetch)
    monkeypatch.setattr(health_db, 'citation_for', cite)
    result = asyncio.run(health_db.get_company_financials(pool, 'FPT'))
    assert pool.options == [{'readonly': True}]
    return result, cited


def test_money_strings_exact_precision_status_and_first_verified_source(monkeypatch):
    rows = [observation('NET_REVENUE', status='UNVERIFIED'),
            observation(), observation('TOTAL_LIABILITIES', value=Decimal('0')),
            observation('PROFIT_AFTER_TAX', value=Decimal('-123.45'), scale=Decimal('1000')),
            observation('CASH_FLOW_OPERATING', value=Decimal('123456789012345678901234567890.123456789'))]
    source = {'title': 'BCTC Q3 2026', 'url': 'https://example.test/report.pdf', 'page': 7}
    with localcontext() as context:
        context.prec = 6
        periods, cited = financials(monkeypatch, rows, source)
    facts = {fact['code']: fact for fact in periods[0]['facts']}
    assert periods[0]['period'] == '2026-Q3'
    assert facts['TOTAL_ASSETS'] == dict(code='TOTAL_ASSETS', label='tổng tài sản',
                                         value_vnd='80000000000000', status='VERIFIED')
    assert facts['NET_REVENUE']['status'] == 'UNVERIFIED'
    assert Decimal(facts['TOTAL_LIABILITIES']['value_vnd']) == 0
    assert Decimal(facts['PROFIT_AFTER_TAX']['value_vnd']) == Decimal('-123450')
    assert isinstance(facts['CASH_FLOW_OPERATING']['value_vnd'], str)
    assert Decimal(facts['CASH_FLOW_OPERATING']['value_vnd']) == Decimal('123456789012345678901234567890123456789')
    assert periods[0]['source'] == source
    assert cited == [rows[1]['observation_id']]


@pytest.mark.parametrize('value,scale', [
    (None, Decimal('1000')), (Decimal('2'), None), ('invalid', Decimal('1')),
    (Decimal('NaN'), Decimal('1')), (Decimal('Infinity'), Decimal('1')),
    (Decimal('1'), Decimal('-Infinity')), (1.5, Decimal('1')), (True, Decimal('1')),
    (Decimal('80000'), Decimal('0')), (Decimal('80000'), Decimal('-1000')),
])
def test_missing_or_invalid_money_is_null_without_invented_zero(monkeypatch, value, scale):
    periods, _ = financials(monkeypatch, [observation(value=value, scale=scale, status='UNVERIFIED')])
    assert periods[0]['facts'][0]['value_vnd'] is None
    assert periods[0]['facts'][0]['status'] == 'UNVERIFIED'
    assert periods[0]['source'] is None


def test_unverified_rows_and_null_locator_do_not_get_a_pdf_source(monkeypatch):
    rows = [observation(status='UNVERIFIED'), observation('NET_REVENUE', status='UNKNOWN')]
    rows[1]['locator_json'] = None
    periods, cited = financials(monkeypatch, rows, {'title': 'Must not be used'})
    assert {fact['status'] for fact in periods[0]['facts']} == {'UNVERIFIED'}
    assert periods[0]['source'] is None
    assert cited == []


def test_newest_eight_periods_numeric_year_with_annual_after_q4(monkeypatch):
    codes = ['2024-YEAR', '2026-Q2', '2025-Q1', '2025-Q4', '2026-Q3',
             '2025-YEAR', '2025-Q2', '2025-Q3', '2026-Q1', '2024-Q4']
    periods, _ = financials(monkeypatch, [observation(period=period, status='UNVERIFIED') for period in codes])
    assert [period['period'] for period in periods] == [
        '2026-Q3', '2026-Q2', '2026-Q1', '2025-YEAR', '2025-Q4', '2025-Q3', '2025-Q2', '2025-Q1']


def test_actual_equity_and_bank_codes_are_truthful_and_ratios_are_excluded(monkeypatch):
    rows = [observation('OWNERS_EQUITY'), observation('TOTAL_OPERATING_INCOME'),
            observation('ROE'), observation('UNSUPPORTED_METRIC')]
    rows[1]['industry_type'] = 'BANK'
    rows[2]['section'] = 'RATIO'
    periods, _ = financials(monkeypatch, rows)
    facts = {fact['code']: fact for fact in periods[0]['facts']}
    assert set(facts) == {'TOTAL_EQUITY', 'TOTAL_OPERATING_INCOME'}
    assert facts['TOTAL_EQUITY']['label'] == 'tổng vốn chủ sở hữu'
    assert facts['TOTAL_OPERATING_INCOME']['label'] == 'tổng thu nhập hoạt động'


def test_metric_must_belong_to_its_statement_section(monkeypatch):
    rows = [observation('TOTAL_ASSETS'), observation('PROFIT_AFTER_TAX'),
            observation('CASH_FLOW_OPERATING')]
    rows[1]['section'] = 'CASH_FLOW'
    rows[2]['section'] = 'INCOME_STATEMENT'
    periods, _ = financials(monkeypatch, rows)
    assert [fact['code'] for fact in periods[0]['facts']] == ['TOTAL_ASSETS']


@pytest.mark.parametrize('difference', ['value', 'basis', 'scope', 'status'])
def test_conflicting_duplicate_fact_is_omitted_with_bounded_warning(monkeypatch, caplog, difference):
    rows = [observation(), observation(), observation('NET_REVENUE')]
    rows[2]['section'] = 'INCOME_STATEMENT'
    if difference == 'value':
        rows[1]['value'] = Decimal('42')
    elif difference == 'status':
        rows[1]['locator_json']['unit_status'] = 'UNVERIFIED'
    else:
        field = 'period_basis' if difference == 'basis' else 'statement_scope'
        rows[0]['locator_json'][field] = 'FIRST'
        rows[1]['locator_json'][field] = 'SECOND'
    periods, cited = financials(monkeypatch, rows)
    assert [fact['code'] for fact in periods[0]['facts']] == ['NET_REVENUE']
    assert cited == [rows[2]['observation_id']]
    warnings = [record for record in caplog.records if record.levelname == 'WARNING']
    assert len(warnings) == 1
    assert all(value in warnings[0].getMessage() for value in ('FPT', '2026-Q3', 'TOTAL_ASSETS'))


def test_identical_duplicate_fact_is_deduplicated(monkeypatch):
    periods, _ = financials(monkeypatch, [observation(), observation()])
    assert len(periods[0]['facts']) == 1


def test_no_financial_observations_returns_an_empty_list(monkeypatch):
    periods, cited = financials(monkeypatch, [])
    assert periods == []
    assert cited == []


@pytest.mark.parametrize('role', [
    'RESEARCHER', 'FINANCIAL_ANALYST', 'DATA_ENGINEER', 'EVALUATOR', 'ADMINISTRATOR',
])
@pytest.mark.parametrize('path', PATHS)
def test_every_read_role_can_use_every_company_route(company_client, monkeypatch, role, path):
    client, _, roles, _ = company_client
    router = importlib.import_module('src.api.routers.companies')

    async def no_financials(pool, symbol):
        assert symbol == 'FPT'
        return []

    async def no_health(pool, symbol):
        assert symbol == 'FPT'
        return None

    monkeypatch.setattr(router, 'get_company_financials', no_financials)
    monkeypatch.setattr(router, 'get_financial_health', no_health)
    roles[:] = [role]
    assert client.get(path).status_code == 200


def test_company_queries_run_against_isolated_database(monkeypatch):
    from fastapi import HTTPException
    from backend.tests.financial_db_fixture import create_financial_db, drop_financial_db

    async def check():
        router = importlib.import_module('src.api.routers.companies')
        admin, conn, dbname = await create_financial_db()
        try:
            class ConnectionPool:
                @asynccontextmanager
                async def acquire(self):
                    yield conn

            monkeypatch.setattr(router, 'get_pool', lambda: ConnectionPool())
            company_ids = {symbol: uuid4() for symbol in ('FPT', 'ZZT', 'OLD', 'NUL')}
            await conn.executemany(
                'INSERT INTO companies(company_id,symbol,company_name,sector,exchange,industry_type,is_active) '
                'VALUES($1,$2,$3,$4,$5,$6,$7)',
                [
                    (company_ids['ZZT'], 'ZZT', 'No reports', None, None, None, True),
                    (company_ids['OLD'], 'OLD', 'Inactive company', None, None, None, False),
                    (company_ids['FPT'], 'FPT', 'FPT Corporation', 'Technology', 'HOSE', 'TECH', True),
                    (company_ids['NUL'], 'NUL', 'Unspecified active state', None, None, None, None),
                ],
            )
            period_id = uuid4()
            await conn.execute(
                'INSERT INTO reporting_periods(period_id,period_code,fiscal_year,quarter,period_type,'
                "start_date,end_date) VALUES($1,'2026-Q3',2026,3,'QUARTER','2026-07-01','2026-09-30')",
                period_id,
            )
            await conn.executemany(
                'INSERT INTO financial_reports(report_id,company_id,period_id,statement_scope,'
                "audit_status,report_version) VALUES($1,$2,$3,'CONSOLIDATED','UNKNOWN',$4)",
                [(uuid4(), company_ids[symbol], period_id, version)
                 for symbol, version in (('FPT', 1), ('FPT', 2), ('OLD', 1))],
            )

            assert await router.list_companies() == [COMPANIES[1], COMPANIES[0]]
            assert await router.company_detail('fpt') == COMPANIES[1]
            assert await router.company_financials('zzt') == {'symbol': 'ZZT', 'periods': []}
            for reader in (router.company_detail, router.company_financials, router.company_health):
                for symbol in ('ZZZ', 'OLD', 'NUL', "FPT' OR 1=1 --"):
                    with pytest.raises(HTTPException) as caught:
                        await reader(symbol)
                    assert caught.value.status_code == 404
                    assert caught.value.detail == 'Không tìm thấy doanh nghiệp.'

            await conn.execute('DELETE FROM financial_reports WHERE company_id=$1', company_ids['FPT'])
            assert await router.company_detail('FPT') == dict(COMPANIES[1], has_financials=False)
        finally:
            await drop_financial_db(admin, conn, dbname)

    asyncio.run(check())
