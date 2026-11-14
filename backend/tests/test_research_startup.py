"""Startup readiness waits for shared warmup; failures remain observable and safe."""
import asyncio
from types import SimpleNamespace

import pytest

from src import main
from src.core.config import Settings


def setup(monkeypatch, warmup, **options):
    settings = SimpleNamespace(research_chat_live=True, research_warmup_enabled=True,
                               research_warmup_timeout_seconds=1, **options)
    monkeypatch.setattr(main, 'settings', settings)
    retriever = SimpleNamespace(warmup=warmup)
    store = SimpleNamespace(engine=SimpleNamespace(retriever=retriever))
    monkeypatch.setattr(main.research_chat, 'get_store', lambda: store)
    return SimpleNamespace(state=SimpleNamespace()), settings


def test_startup_waits_and_marks_ready_without_chat_or_generation(monkeypatch):
    events = []
    async def warmup():
        events.append('warm')
        await asyncio.sleep(0)
        return {'backend': 'hybrid', 'index_version_id': 'pinned-index'}
    app, _ = setup(monkeypatch, warmup)
    asyncio.run(main.warmup_research(app))
    assert events == ['warm']
    assert app.state.research_warmup['status'] == 'ready'
    assert app.state.research_warmup['backend'] == 'hybrid'


@pytest.mark.parametrize('flag', ['research_chat_live', 'research_warmup_enabled'])
def test_disabled_warmup_does_not_construct_store(monkeypatch, flag):
    app, settings = setup(monkeypatch, None)
    setattr(settings, flag, False)
    def forbidden(): raise AssertionError('disabled must not load model or pool')
    monkeypatch.setattr(main.research_chat, 'get_store', forbidden)
    asyncio.run(main.warmup_research(app))
    assert app.state.research_warmup['status'] == 'disabled'


@pytest.mark.parametrize('failure', ['error', 'timeout'])
def test_failure_is_nonfatal_bounded_and_does_not_log_secrets(monkeypatch, caplog, failure):
    async def warmup():
        if failure == 'timeout': await asyncio.sleep(1)
        else: raise RuntimeError('sensitive DSN and key')
    app, settings = setup(monkeypatch, warmup)
    settings.research_warmup_timeout_seconds = 0.01
    asyncio.run(main.warmup_research(app))
    state = app.state.research_warmup
    assert state['status'] == 'failed'
    assert state['reason_code'] == ('WARMUP_TIMEOUT' if failure == 'timeout' else 'WARMUP_FAILED')
    assert 'sensitive' not in caplog.text


def test_shutdown_cancellation_propagates(monkeypatch):
    async def warmup(): raise asyncio.CancelledError()
    app, _ = setup(monkeypatch, warmup)
    with pytest.raises(asyncio.CancelledError): asyncio.run(main.warmup_research(app))


def test_warmup_is_enabled_by_default_with_bounded_timeout():
    settings = Settings(_env_file=None)
    assert settings.research_warmup_enabled is True
    assert 0 < settings.research_warmup_timeout_seconds <= 600
    for timeout in (0, -1, float('inf'), float('nan'), 601):
        with pytest.raises(ValueError): Settings(_env_file=None, research_warmup_timeout_seconds=timeout)
