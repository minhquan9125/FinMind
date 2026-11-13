"""BCTC refresh schedule: pure slot rules, status exposure and runtime gating."""
import asyncio
import os
import unittest
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from backend.src.market_data.session import VN


def at(d, h, m=0, month=11):
    return datetime(2026, month, d, h, m, tzinfo=VN)


class NextSlotTests(unittest.TestCase):
    def test_slots(self):
        from backend.src.market_data.app import next_financial_refresh as nxt
        self.assertEqual(nxt(at(12, 17)), at(12, 18))              # in season, same day
        self.assertEqual(nxt(at(12, 18, 30)), at(13, 18))          # in season, next day
        self.assertEqual(nxt(at(16, 10)), at(16, 18))              # off season Monday
        self.assertEqual(nxt(at(17, 10)), at(23, 18))              # off season Tuesday -> Monday
        self.assertEqual(nxt(at(14, 19, month=1)), at(15, 18, month=1))  # first day of season
        self.assertEqual(nxt(at(15, 19, month=11)), at(16, 18))    # season ends 15/11 inclusive, 16/11 is Monday
        self.assertEqual(nxt(at(20, 17, month=8)), at(20, 18, month=8))  # 20/08 inclusive
        self.assertEqual(nxt(datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc)), at(12, 18))  # UTC input


class StatusTests(unittest.TestCase):
    def test_status_includes_financial_refresh(self):
        from backend.src.api.routers.market_data import live_status
        state = SimpleNamespace(financial_refresh={'last_ok': None})
        service = Mock(); service.status.return_value = {}
        out = live_status(SimpleNamespace(app=SimpleNamespace(state=state)), service)
        self.assertEqual(out['financial_refresh'], {'last_ok': None})


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def exercise(self, table, codes, price_busy=False, *, scenario=None, flag='1'):
        from backend.src.market_data import app as runtime
        service = Mock(); service.tick.return_value = {'status': 'idle'}
        service.has_live_viewers.return_value = False
        service.capture_tracked.return_value = 30
        service.status.return_value = {'persistence_error': None}
        gate = Mock(); gate.calendar.sessions.return_value = []
        clock = {'now': datetime(2026, 11, 12, 18, 1, tzinfo=VN)}

        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return clock['now'].astimezone(tz or timezone.utc)
        conn = SimpleNamespace(fetch=AsyncMock(return_value=[{'symbol': s, 'exchange': 'HOSE'} for s in runtime.BACKGROUND_SYMBOLS]),
                               fetchval=AsyncMock(return_value=table))
        class Pool:
            @asynccontextmanager
            async def acquire(self): yield conn
        prices = SimpleNamespace(run=AsyncMock(return_value=0))
        calls = iter(codes)
        async def fin_run(apply, *, now, **kw):
            code = next(calls)
            if isinstance(code, Exception): raise code
            return code
        fin = SimpleNamespace(run=AsyncMock(side_effect=fin_run))
        def import_module(name):
            return fin if name.endswith('refresh_financial_statements') else prices
        async def short_wait(awaitable, timeout):
            awaitable.close(); await asyncio.sleep(.005); raise TimeoutError
        application = SimpleNamespace(state=SimpleNamespace())
        with (patch.object(runtime, 'CollectorLock'), patch.object(runtime, 'BatchSDKClient'),
              patch.object(runtime, 'LiveCoordinator', return_value=service),
              patch.object(runtime, 'get_pool', return_value=Pool()), patch.object(runtime, 'FireAntNews'),
              patch.object(runtime, 'NewsService'), patch.object(runtime, 'SessionGate', return_value=gate),
              patch.object(runtime, 'datetime', Clock),
              patch.object(runtime, 'flush_pending_activity', AsyncMock(return_value={'saved': 30, 'failed': 0, 'rejected': 0})),
              patch.object(runtime.importlib, 'import_module', side_effect=import_module),
              patch.object(runtime.asyncio, 'wait_for', side_effect=short_wait),
              patch.dict(os.environ, {'FINMIND_LIVE_ENABLED': '1', **({'FINMIND_BCTC_REFRESH': flag} if flag is not None else {})})):
            async with runtime.market_lifespan(application):
                st = application.state
                self.assertEqual(st.financial_refresh['next_run_at'], at(13, 18).isoformat())  # no start-up run
                for _ in range(100):
                    if st.daily_refresh['last_ok'] is not None: break
                    await asyncio.sleep(.005)
                self.assertEqual(fin.run.await_count, 0)
                if scenario is not None:
                    await scenario(st, fin, prices, clock, service)
                    return st.financial_refresh, fin, clock
                clock['now'] = at(13, 18, 1)
                for _ in range(200):
                    if st.financial_refresh['last_ok'] is not None or st.financial_refresh.get('reason') in ('MIGRATION_MISSING', 'DISABLED'): break
                    await asyncio.sleep(.005)
                return st.financial_refresh, fin, clock

    async def test_success_schedules_next_slot(self):
        st, fin, _ = await self.exercise('financial_report_verifications', [0])
        self.assertTrue(st['last_ok']); self.assertEqual(st['last_exit_code'], 0)
        self.assertEqual(st['next_run_at'], at(14, 18).isoformat()); self.assertEqual(fin.run.await_count, 1)
        self.assertIs(fin.run.call_args.args[0], True)

    async def test_missing_table_skips_job_until_next_slot(self):
        st, fin, _ = await self.exercise(None, [0])
        self.assertEqual(st['reason'], 'MIGRATION_MISSING'); self.assertEqual(fin.run.await_count, 0)
        self.assertEqual(st['next_run_at'], at(14, 18).isoformat())

    async def test_job_is_off_unless_the_flag_is_set(self):
        # Applying the migration must not by itself turn on unattended --apply (final review #1).
        for flag in (None, '0', 'true'):
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop('FINMIND_BCTC_REFRESH', None)
                st, fin, _ = await self.exercise('financial_report_verifications', [0], flag=flag)
            self.assertEqual(st['reason'], 'DISABLED'); self.assertEqual(fin.run.await_count, 0)
            self.assertIsNone(st['last_ok']); self.assertEqual(st['next_run_at'], at(14, 18).isoformat())

    async def test_failure_retries_in_30_minutes(self):
        st, fin, clock = await self.exercise('financial_report_verifications', [1])
        self.assertFalse(st['last_ok']); self.assertEqual(st['last_exit_code'], 1)
        self.assertEqual(st['next_run_at'], at(13, 18, 31).isoformat())


    async def wait_for_runtime(self, predicate):
        for _ in range(200):
            if predicate(): return
            await asyncio.sleep(.005)
        self.assertTrue(predicate(), 'runtime condition not reached')

    async def test_financial_refresh_blocks_due_price_refresh_until_finished(self):
        async def scenario(st, fin, prices, clock, service):
            release = asyncio.Event()
            events = []
            async def financial_run(*args, **kwargs):
                events.append('financial_started')
                await release.wait()
                events.append('financial_finished')
                return 0
            async def price_run(*args, **kwargs):
                events.append('price')
                return 0
            fin.run.side_effect = financial_run
            prices.run.side_effect = price_run
            clock['now'] = at(13, 18, 1)
            try:
                await self.wait_for_runtime(lambda: fin.run.await_count == 1)
                self.assertEqual(prices.run.await_count, 2)
                self.assertEqual(events, ['price', 'financial_started'])
                clock['now'] = at(14, 15, 36)
                ticks = service.tick.call_count
                await self.wait_for_runtime(lambda: service.tick.call_count >= ticks + 3)
                self.assertEqual(prices.run.await_count, 2)
                self.assertEqual(events, ['price', 'financial_started'])
            finally:
                release.set()
            await self.wait_for_runtime(lambda: prices.run.await_count == 3)
            self.assertEqual(events, ['price', 'financial_started', 'financial_finished', 'price'])
            self.assertTrue(st.financial_refresh['last_ok'])
        await self.exercise('financial_report_verifications', [0], scenario=scenario)

    async def test_failure_retry_budget_exhausts_and_resets_at_main_slot(self):
        async def scenario(st, fin, prices, clock, service):
            slots = ((at(13, 18, 1), at(13, 18, 31)),
                     (at(13, 18, 31), at(13, 19, 1)),
                     (at(13, 19, 1), at(14, 18)),
                     (at(14, 18), at(14, 18, 30)))
            for count, (run_at, next_at) in enumerate(slots, 1):
                clock['now'] = run_at
                await self.wait_for_runtime(
                    lambda: st.financial_refresh['last_run_at'] == run_at.isoformat())
                self.assertEqual(fin.run.await_count, count)
                self.assertFalse(st.financial_refresh['last_ok'])
                self.assertEqual(st.financial_refresh['last_exit_code'], 1)
                self.assertEqual(st.financial_refresh['reason'], 'JOB_FAILED')
                self.assertEqual(st.financial_refresh['next_run_at'], next_at.isoformat())
        await self.exercise('financial_report_verifications', [1, 1, 1, 1], scenario=scenario)


if __name__ == '__main__':
    unittest.main()
