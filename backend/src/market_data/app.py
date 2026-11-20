"""Standalone market API; one shared guest SDK collector for visible charts."""

import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import datetime, time as dt_time, timedelta
import importlib
import os
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..api.routers.market_data import router
from .live import LiveCoordinator
from .repository import FileMarketDataRepository
from .sdk import BatchSDKClient, CollectorLock
from .session import AUTO_COLLECTION_END, SessionGate, VN
from .universe import BACKGROUND_SYMBOLS,UNIVERSE_SOURCE,UNIVERSE_OBSERVED_AT,resolve_background
from .news import FireAntNews, NewsService
from ..core.db import connect, disconnect, get_pool
from .activity_store import flush_pending_activity, ingest_module

# Daily bars are appended once the session is final (the refresh script's 15:30 cut-off).
DAILY_REFRESH_AT = dt_time(15, 35)
REFRESH_RETRY = timedelta(minutes=30)


def next_daily_refresh(now):
    """The coming 15:35 Vietnam time: later today, otherwise tomorrow."""
    local = now.astimezone(VN)
    today = datetime.combine(local.date(), DAILY_REFRESH_AT, VN)
    return today if local < today else today + timedelta(days=1)


# BCTC refresh: 18:00 Vietnam time daily in filing seasons (inclusive), otherwise Mondays.
FINANCIAL_REFRESH_AT = dt_time(18, 0)
FILING_SEASONS = ((1, 15, 2, 15), (4, 15, 5, 15), (7, 15, 8, 20), (10, 15, 11, 15))
FINANCIAL_MAX_RETRIES = 2


def next_financial_refresh(now):
    local = now.astimezone(VN)
    for offset in range(8):
        day = local.date() + timedelta(days=offset)
        in_season = any((m1, d1) <= (day.month, day.day) <= (m2, d2) for m1, d1, m2, d2 in FILING_SEASONS)
        slot = datetime.combine(day, FINANCIAL_REFRESH_AT, VN)
        if (in_season or day.weekday() == 0) and slot > local:
            return slot


@asynccontextmanager
async def lifespan(app):
    # The standalone market API needs the same user/role store as the main app.
    # When nested by src.main, its pool already exists and remains owned there.
    owns_pool = False
    try:
        get_pool()
    except RuntimeError:
        await connect()
        owns_pool = True
    try:
        async with market_lifespan(app):
            yield
    finally:
        if owns_pool:
            await disconnect()


@asynccontextmanager
async def market_lifespan(app):
    app.state.live = None
    root = Path(os.getenv("FINMIND_DATA_ROOT") or Path(__file__).resolve().parents[3]).resolve()
    news_fetch = FireAntNews()
    app.state.news = NewsService(news_fetch, FileMarketDataRepository(root))
    if os.getenv("FINMIND_LIVE_ENABLED", "1") == "0":
        try:
            yield
        finally:
            news_fetch.close()
            app.state.news = None
        return
    collector_lock = CollectorLock(root / ".agent-state/market-live/collector.lock")
    collector_lock.acquire()
    sdk = BatchSDKClient(root, timeout=90)  # a cold SDK start alone takes about 30 seconds
    stop = asyncio.Event()
    task = None
    try:
        repository=FileMarketDataRepository(root)
        gate = SessionGate(root)
        service = LiveCoordinator(lambda symbols: sdk(symbols, automatic=True), gate, repository,
                                  manual_fetch=sdk,
                                  history_fetch=sdk.history,
                                  poll_seconds=float(os.getenv("FINMIND_LIVE_POLL_SECONDS", "5")),
                                  background_seconds=60,
                                  budget_path=root/'.agent-state/market-live/request-budget.json',
                                  snapshot_sink=repository.save_daily_quote,
                                  max_wait_seconds=float(os.getenv("FINMIND_LIVE_MAX_WAIT_SECONDS", "8")))
        app.state.live = service
        app.state.activity_persistence={'saved':0,'rejected':0,'failed':0,'error':None,'tracked':[],
            'configured_symbols':list(BACKGROUND_SYMBOLS),'missing_symbols':list(BACKGROUND_SYMBOLS),
            'universe_source':UNIVERSE_SOURCE,'universe_observed_at':UNIVERSE_OBSERVED_AT}

        app.state.daily_refresh={'last_run_at':None,'last_ok':None,
                                 'next_run_at':datetime.now(VN).isoformat(),'deferred_for_live':False}
        app.state.financial_refresh={'last_run_at':None,'last_ok':None,'last_exit_code':None,'reason':None,
                                     'next_run_at':next_financial_refresh(datetime.now(VN)).isoformat()}
        persistence_lock=asyncio.Lock()

        async def flush_activity():
            async with persistence_lock:
                return await flush_pending_activity(get_pool(),repository)

        async def daily_refresh(now):
            """Closing activity snapshot, then append every closed session still missing."""
            captured=True
            try:
                trading_day=gate.calendar is not None and gate.calendar.sessions('HOSE',now.date())
                # During the session the collector already archives; this covers a late start.
                if trading_day and now.time()>=AUTO_COLLECTION_END:
                    captured=await asyncio.to_thread(service.capture_tracked)==len(BACKGROUND_SYMBOLS)
                    captured=captured and not service.status().get('persistence_error')
                    flushed=await flush_activity()
                    app.state.activity_persistence.update(flushed)
                    captured=captured and not flushed['failed'] and not flushed['rejected']
            except Exception:
                captured=False  # retried together with the refresh
            ingest_module()  # puts the repository root on sys.path for the shared script
            refresh=importlib.import_module('backend.scripts.refresh_market_prices')
            # The backend already owns the collector lock, so its SDK client reads the index.
            def show(report):
                # Index blocks/deferrals must be visible in the status, not only in report.json.
                indexes=report.get('indexes',{})
                app.state.daily_refresh.update(
                    blocked_indexes=sorted(i for i,item in indexes.items() if item.get('blocked')),
                    deferred_indexes=sorted(i for i,item in indexes.items() if item.get('deferred')))
            return await refresh.run(True,index_history=service.history_for_refresh,symbols=BACKGROUND_SYMBOLS,
                                     on_report=show)==0 and captured

        async def financial_refresh(now):
            """Exit code of the BCTC job; None when the table is not migrated; 'DISABLED' when not opted in."""
            # Opt-in: applying the migration alone must not start unattended --apply runs.
            if os.environ.get('FINMIND_BCTC_REFRESH') != '1':
                return 'DISABLED'
            async with get_pool().acquire() as conn:
                if await conn.fetchval("SELECT to_regclass('public.financial_report_verifications')") is None:
                    return None
            ingest_module()
            job=importlib.import_module('backend.scripts.refresh_financial_statements')
            # Network, PDF and OCR work inside run() is offloaded with asyncio.to_thread.
            return await job.run(True,now=now)

        async def collect():
            next_flush=0
            mapped=False
            refresh_at=datetime.now(VN)  # first run right after start-up catches up missed days
            refresh_task=None
            persistence_task=None
            fin_task=None
            fin_at=datetime.fromisoformat(app.state.financial_refresh['next_run_at'])  # no run at start-up
            fin_retries=0

            async def persist():
                nonlocal mapped
                try:
                    if not mapped:
                        async with asyncio.timeout(5):
                            async with get_pool().acquire() as conn:
                                rows=await conn.fetch('''SELECT symbol,exchange FROM public.companies
                                    WHERE symbol=ANY($1::text[]) AND is_active IS TRUE''',list(BACKGROUND_SYMBOLS))
                        mapping,missing=resolve_background(rows)
                        app.state.activity_persistence['missing_symbols']=missing
                        if missing:raise ValueError('Incomplete background company mapping')
                        service.set_tracked_symbols(mapping)
                        mapped=True
                        app.state.activity_persistence['tracked']=sorted(mapping)
                    result=await flush_activity()
                    app.state.activity_persistence.update(result,error='Chưa ghi được dữ liệu ngày vào DB.' if result['failed'] else None)
                except Exception:
                    app.state.activity_persistence.update(failed=1,error='Chưa kết nối được bộ lưu dữ liệu ngày.')

            while not stop.is_set():
                now=datetime.now(VN)
                if refresh_task is not None and refresh_task.done():
                    ok=refresh_task.exception() is None and refresh_task.result()
                    refresh_task=None
                    refresh_at=next_daily_refresh(now) if ok else now+REFRESH_RETRY
                    app.state.daily_refresh.update(last_run_at=now.isoformat(),last_ok=bool(ok),
                                                   next_run_at=refresh_at.isoformat())
                if mapped and refresh_task is None and fin_task is None and now>=refresh_at:
                    deferred=service.has_live_viewers()
                    app.state.daily_refresh['deferred_for_live']=deferred
                    if not deferred:refresh_task=asyncio.create_task(daily_refresh(now))
                if fin_task is not None and fin_task.done():
                    fin_task_result=None if fin_task.exception() else fin_task.result()
                    failed=fin_task.exception() is not None or fin_task_result not in (0,None,'DISABLED')
                    fin_task=None
                    if failed and fin_retries<FINANCIAL_MAX_RETRIES:
                        fin_retries+=1;fin_at=now+REFRESH_RETRY
                    else:
                        fin_retries=0;fin_at=next_financial_refresh(now)
                    missing=fin_task_result is None and not failed
                    disabled=fin_task_result=='DISABLED'
                    app.state.financial_refresh.update(last_run_at=now.isoformat(),
                        last_ok=None if disabled else (not failed and not missing),
                        last_exit_code=None if disabled else fin_task_result,
                        reason='DISABLED' if disabled else ('MIGRATION_MISSING' if missing else ('JOB_FAILED' if failed else None)),
                        next_run_at=fin_at.isoformat())
                if mapped and fin_task is None and refresh_task is None and now>=fin_at:
                    fin_task=asyncio.create_task(financial_refresh(now))
                if time.monotonic()>=next_flush and (persistence_task is None or persistence_task.done()):
                    next_flush=time.monotonic()+60
                    # Slow DB writes must never hold the five-second quote scheduler.
                    persistence_task=asyncio.create_task(persist())
                await asyncio.to_thread(service.tick)
                try:
                    await asyncio.wait_for(stop.wait(), timeout=1)
                except TimeoutError:
                    pass
            if refresh_task is not None:
                refresh_task.cancel()  # an unfinished append rolls back; the next start retries it
                with suppress(asyncio.CancelledError,Exception):
                    await refresh_task
            if fin_task is not None:
                fin_task.cancel()
                with suppress(asyncio.CancelledError,Exception):
                    await fin_task
            if persistence_task is not None:
                with suppress(asyncio.CancelledError,Exception):await persistence_task
            # Stop accepting new SDK work first, then drain the last durable observations.
            try:
                result=await flush_activity()
                app.state.activity_persistence.update(result)
            except Exception:
                app.state.activity_persistence.update(failed=1,error='Còn dữ liệu ngày chờ nhập lại.')

        task = asyncio.create_task(collect())
        yield
    finally:
        stop.set()
        try:
            if task:
                await task  # Finish in-flight work before closing SDK/releasing exclusive lock.
        finally:
            try:
                await asyncio.to_thread(sdk.close)
            finally:
                collector_lock.close()
                app.state.live = None
                news_fetch.close()
                app.state.news = None

app = FastAPI(title="FinMind Market Data API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:5174", "http://127.0.0.1:5174",
    ],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    expose_headers=["ETag", "Retry-After"],
)
app.include_router(router)
