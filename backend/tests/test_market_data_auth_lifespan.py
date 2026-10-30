"""The standalone market API must initialize the role database itself."""

import asyncio
from contextlib import asynccontextmanager
from importlib import import_module


market_app = import_module("src.market_data.app")


def test_standalone_market_api_owns_database_connection(monkeypatch):
    calls = []
    initialized = False

    def get_pool():
        if not initialized:
            raise RuntimeError("not connected")
        return object()

    async def connect():
        nonlocal initialized
        initialized = True
        calls.append("connect")

    async def disconnect():
        calls.append("disconnect")

    @asynccontextmanager
    async def market_lifespan(app):
        calls.append("market open")
        yield
        calls.append("market close")

    monkeypatch.setattr(market_app, "get_pool", get_pool)
    monkeypatch.setattr(market_app, "connect", connect)
    monkeypatch.setattr(market_app, "disconnect", disconnect)
    monkeypatch.setattr(market_app, "market_lifespan", market_lifespan)

    async def run():
        async with market_app.lifespan(market_app.app):
            calls.append("serving")

    asyncio.run(run())
    assert calls == ["connect", "market open", "serving", "market close", "disconnect"]


def test_nested_market_api_leaves_main_database_open(monkeypatch):
    calls = []
    monkeypatch.setattr(market_app, "get_pool", lambda: object())

    async def unexpected():
        calls.append("database changed")

    @asynccontextmanager
    async def market_lifespan(app):
        calls.append("market open")
        yield
        calls.append("market close")

    monkeypatch.setattr(market_app, "connect", unexpected)
    monkeypatch.setattr(market_app, "disconnect", unexpected)
    monkeypatch.setattr(market_app, "market_lifespan", market_lifespan)

    async def run():
        async with market_app.lifespan(market_app.app):
            calls.append("serving")

    asyncio.run(run())
    assert calls == ["market open", "serving", "market close"]
