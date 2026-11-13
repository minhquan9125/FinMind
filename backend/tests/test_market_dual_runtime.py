"""Runtime wiring without a real SDK, tunnel or database."""
import asyncio
import os
from datetime import datetime,timezone
from contextlib import asynccontextmanager
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock,Mock,patch
from backend.src.market_data.universe import BACKGROUND_SYMBOLS,resolve_background

class UniverseTests(unittest.TestCase):
 def test_exact_published_thirty_and_missing_mapping(self):
  self.assertEqual(len(BACKGROUND_SYMBOLS),30)
  self.assertEqual(len(set(BACKGROUND_SYMBOLS)),30)
  self.assertIn('BSR',BACKGROUND_SYMBOLS)
  self.assertIn('TCX',BACKGROUND_SYMBOLS)
  mapping,missing=resolve_background([{'symbol':'FPT','exchange':'HOSE'}])
  self.assertEqual(mapping,{'FPT':'HOSE'});self.assertEqual(len(missing),29)
 def test_duplicate_or_wrong_exchange_is_not_silently_accepted(self):
  with self.assertRaises(ValueError):resolve_background([{'symbol':'FPT','exchange':'HOSE'}]*2)
  with self.assertRaises(ValueError):resolve_background([{'symbol':'FPT','exchange':'HNX'}])

class RuntimeTests(unittest.IsolatedAsyncioTestCase):
 async def test_backend_supplies_background60_and_shared_history_callback(self):
  await self.exercise()
 async def test_closing_archive_failure_is_not_reported_as_daily_success(self):
  await self.exercise('disk full')
 async def test_slow_database_flush_does_not_block_quote_scheduler(self):
  await self.exercise(blocked_flush=True)
 async def exercise(self,persistence_error=None,blocked_flush=False):
  from backend.src.market_data import app as runtime
  sdk=Mock();service=Mock();service.tick.return_value={'status':'idle'}
  service.has_live_viewers.return_value=blocked_flush
  service.capture_tracked.return_value=30
  service.status.return_value={'missing_tracked_symbols':[],'persistence_error':persistence_error}
  gate=Mock(return_value=False);gate.calendar.sessions.return_value=[{'end':'14:45'}]
  class FixedDateTime(datetime):
   @classmethod
   def now(cls,tz=None):return datetime(2026,11,11,9,tzinfo=timezone.utc).astimezone(tz or timezone.utc)
  rows=[{'symbol':s,'exchange':'HOSE'} for s in BACKGROUND_SYMBOLS]
  conn=SimpleNamespace(fetch=AsyncMock(return_value=rows))
  class Pool:
   @asynccontextmanager
   async def acquire(self):yield conn
  async def fake_run(*args,on_report=None,**kwargs):
   if on_report:on_report({'indexes':{'VNINDEX':{'blocked':None},'HNXINDEX':{'blocked':'source revised'},
                                      'UPCOMINDEX':{'blocked':None,'deferred':'sdk_busy'}}})
   return 0
  pool=Pool();refresh=SimpleNamespace(run=AsyncMock(side_effect=fake_run))
  application=SimpleNamespace(state=SimpleNamespace())
  release=asyncio.Event()
  async def flush_pending(*args):
   if blocked_flush:await release.wait()
   return {'saved':0 if persistence_error else 30,'failed':0,'rejected':0}
  async def short_wait(awaitable,timeout):
   awaitable.close()
   await asyncio.sleep(.005)
   raise TimeoutError
  with (patch.object(runtime,'CollectorLock'),patch.object(runtime,'BatchSDKClient',return_value=sdk),
        patch.object(runtime,'LiveCoordinator',return_value=service) as build,
        patch.object(runtime,'get_pool',return_value=pool),patch.object(runtime,'FireAntNews'),patch.object(runtime,'NewsService'),
        patch.object(runtime,'SessionGate',return_value=gate),patch.object(runtime,'datetime',FixedDateTime),
        patch.object(runtime,'flush_pending_activity',side_effect=flush_pending),
        patch.object(runtime.importlib,'import_module',return_value=refresh),
        patch.object(runtime.asyncio,'wait_for',side_effect=short_wait),patch.dict(os.environ,{'FINMIND_LIVE_ENABLED':'1'})):
   async with runtime.market_lifespan(application):
    if blocked_flush:
     try:
      for _ in range(40):
       if service.tick.call_count>=2:break
       await asyncio.sleep(.005)
      self.assertGreaterEqual(service.tick.call_count,2,'DB flush stalled quote ticks')
     finally:release.set()
     return
    for _ in range(80):
     if application.state.daily_refresh['last_ok'] is not None:break
     await asyncio.sleep(.005)
    self.assertEqual(build.call_args.kwargs['background_seconds'],60)
    self.assertEqual(refresh.run.await_count,1)
    self.assertIs(refresh.run.call_args.kwargs['index_history'],service.history_for_refresh)
    self.assertEqual(set(refresh.run.call_args.kwargs['symbols']),set(BACKGROUND_SYMBOLS))
    self.assertEqual(application.state.activity_persistence['missing_symbols'],[])
    self.assertEqual(application.state.daily_refresh['last_ok'],not bool(persistence_error))
    # A source revision that blocks an index is visible in the status, not only in report.json.
    self.assertEqual(application.state.daily_refresh['blocked_indexes'],['HNXINDEX'])
    self.assertEqual(application.state.daily_refresh['deferred_indexes'],['UPCOMINDEX'])

if __name__=='__main__':unittest.main()
