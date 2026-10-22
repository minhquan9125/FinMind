import asyncio
import uuid

from src.documents.repository import vector_search_filtered


class FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self):
        self.transaction_args = None
        self.sql = None
        self.args = None

    def transaction(self, **kwargs):
        self.transaction_args = kwargs
        return FakeTransaction()

    async def fetch(self, sql, *args):
        self.sql = sql
        self.args = args
        return []


class FakeAcquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakePool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        return FakeAcquire(self.connection)


def test_filtered_search_is_read_only_and_binds_all_values():
    connection = FakeConnection()
    index_id = str(uuid.uuid4())

    result = asyncio.run(vector_search_filtered(
        FakePool(connection), index_id, [0.1, 0.2], 5,
        company_symbol="FPT", period="2026-05", doc_type="PRICE_HISTORY",
    ))

    assert result == []
    assert connection.transaction_args == {"readonly": True, "isolation": "repeatable_read"}
    assert "t.superseded_at IS NULL" in connection.sql
    assert "t.locator_json->>'period_code'" in connection.sql
    assert "upper(d.doc_type)=upper($4)" in connection.sql
    assert connection.args == (uuid.UUID(index_id), "FPT", "2026-05", "PRICE_HISTORY", [0.1, 0.2], 5)


def test_filtered_search_parameterizes_user_filter_values():
    connection = FakeConnection()
    index_id = str(uuid.uuid4())
    malicious = "FPT' OR TRUE --"

    asyncio.run(vector_search_filtered(
        FakePool(connection), index_id, [0.1], 3, company_symbol=malicious,
    ))

    assert malicious not in connection.sql
    assert connection.args[1] == malicious
