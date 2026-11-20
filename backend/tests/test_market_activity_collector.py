from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from backend.src.market_data.live import LiveCoordinator
from backend.src.market_data.repository import FileMarketDataRepository
from backend.src.market_data.activity_store import flush_pending_activity
from backend.tests.test_market_data_live import quote

VN=timezone(timedelta(hours=7))


class ActivityCollectorTests(unittest.TestCase):
    def setUp(self):
        self.root=Path.cwd()/'.agent-state/test-activity'/uuid4().hex
        self.root.mkdir(parents=True)
        self.repo=FileMarketDataRepository(self.root)
        self.now=datetime(2026,10,8,10,tzinfo=VN)
        self.seconds=0
        self.fetch=Mock(side_effect=lambda symbols:{'fetched_at':self.now.isoformat(),'rows':[quote(s) for s in symbols]})

    def test_zero_viewers_and_viewers_share_one_batch_and_archive(self):
        service=LiveCoordinator(self.fetch,lambda e:True,self.repo,now=lambda:self.now,
            clock=lambda:self.seconds,tracked_symbols={'FPT':'HOSE','MBB':'HOSE'},snapshot_sink=self.repo.save_daily_quote)
        self.assertEqual(service.tick()['accepted'],2)
        self.assertEqual(self.fetch.call_args.args[0],['FPT','MBB'])
        self.assertEqual(len(self.repo.pending_activity()),2)
        for i in range(100):service.watch(str(i),'FPT')
        self.seconds=5;service.tick()
        self.assertEqual(self.fetch.call_count,2)
        self.assertEqual(len(self.repo.pending_activity()),2)

    def test_closing_capture_archives_tracked_stocks_once_outside_the_session(self):
        service=LiveCoordinator(self.fetch,lambda e:False,self.repo,now=lambda:self.now,
            clock=lambda:self.seconds,tracked_symbols={'FPT':'HOSE','MBB':'HOSE'},snapshot_sink=self.repo.save_daily_quote)
        service.watch('viewer','HPG')
        self.assertEqual(service.capture_tracked(),2)
        self.assertEqual(self.fetch.call_args.args[0],['FPT','MBB'])
        self.assertEqual(sorted(item['symbol'] for item in self.repo.pending_activity()),['FPT','MBB'])
        empty=LiveCoordinator(self.fetch,lambda e:False,self.repo)
        self.assertEqual(empty.capture_tracked(),0)
        self.assertEqual(self.fetch.call_count,1)

    def test_daily_refresh_runs_at_1535_vietnam_time(self):
        from backend.src.market_data.app import next_daily_refresh
        at=lambda *parts:datetime(2026,11,*parts,tzinfo=VN)
        self.assertEqual(next_daily_refresh(at(12,9,0)),at(12,15,35))
        self.assertEqual(next_daily_refresh(at(12,15,35)),at(13,15,35))
        self.assertEqual(next_daily_refresh(datetime(2026,11,12,8,34,tzinfo=timezone.utc)),at(12,15,35))

    def test_closed_calendar_never_fetches_tracked(self):
        service=LiveCoordinator(self.fetch,lambda e:False,self.repo,tracked_symbols={'FPT':'HOSE'})
        self.assertEqual(service.tick()['status'],'idle');self.fetch.assert_not_called()

    def test_sink_failure_is_not_provider_backoff(self):
        service=LiveCoordinator(self.fetch,lambda e:True,self.repo,now=lambda:self.now,
            clock=lambda:self.seconds,tracked_symbols={'FPT':'HOSE'},snapshot_sink=Mock(side_effect=OSError('disk')))
        service.watch('viewer','FPT')
        self.assertEqual(service.tick()['status'],'ok')
        self.assertTrue(service.status()['persistence_error'])
        self.seconds=5
        self.assertEqual(service.tick()['status'],'ok')
        self.assertEqual(self.fetch.call_count,2)

    def test_restart_ack_content_and_multiple_days(self):
        data={'fetched_at':self.now.isoformat(),'rows':[quote()]}
        self.repo.save_daily_quote(data)
        reopened=FileMarketDataRepository(self.root)
        item=reopened.pending_activity()[0]
        self.assertTrue(reopened.ack_activity(item,'inserted'))
        self.assertEqual(reopened.pending_activity(),[])
        changed={'fetched_at':(self.now+timedelta(minutes=1)).isoformat(),'rows':[quote(volume_accumulated=150)]}
        self.repo.save_daily_quote(changed)
        self.assertFalse(reopened.ack_activity(item,'inserted'))
        self.assertEqual(len(reopened.pending_activity()),1)
        tomorrow={'fetched_at':(self.now+timedelta(days=1)).isoformat(),'rows':[quote(TD='09/10/2026')]}
        self.repo.save_daily_quote(tomorrow)
        self.assertEqual(len(reopened.pending_activity()),2)
        self.repo.save_daily_quote(data)
        self.assertEqual(reopened.pending_activity()[0]['envelope']['rows'][0]['volume_accumulated'],150)

    def test_invalid_path_and_multirow_archive_rejected(self):
        for symbol in ('../FPT','FPT/','CONX'):
            with self.subTest(symbol=symbol),self.assertRaises(ValueError):
                self.repo.save_daily_quote({'fetched_at':self.now.isoformat(),'rows':[quote(symbol)]})
        with self.assertRaises(ValueError):self.repo.save_daily_quote({'fetched_at':self.now.isoformat(),'rows':[quote(),quote()]})


class ActivityFlushTests(unittest.IsolatedAsyncioTestCase):
    async def test_persistent_archive_failures_do_not_starve_later_symbols(self):
        for failed_symbols in (('FPT',),('FPT','HPG')):
            with self.subTest(failed_symbols=failed_symbols):
                root=Path.cwd()/'.agent-state/test-activity'/uuid4().hex;root.mkdir(parents=True)
                repo=FileMarketDataRepository(root)
                for symbol in (*failed_symbols,'MBB'):
                    repo.save_daily_quote({'fetched_at':'2026-10-08T10:00:00+07:00','rows':[quote(symbol)]})
                archives={item['symbol']:item['path'] for item in repo.pending_activity()}
                original={symbol:archives[symbol].read_bytes() for symbol in failed_symbols}
                class Pool:
                    @asynccontextmanager
                    async def acquire(self):yield object()
                calls=[]
                async def import_or_fail(conn,plan):
                    calls.append(plan['symbol'])
                    if plan['symbol'] in failed_symbols:raise ConnectionError('sensitive-database-detail')
                    return {'activity_status':'inserted'}
                with patch('backend.scripts.ingest_market_news_to_supabase.apply_live',new=import_or_fail):
                    for minute in (1,2):
                        repo.save_daily_quote({'fetched_at':f'2026-10-08T10:0{minute}:00+07:00',
                            'rows':[quote('MBB',volume_accumulated=100+minute)]})
                        calls.clear()
                        result=await flush_pending_activity(Pool(),repo)
                        self.assertEqual(calls,[*failed_symbols,'MBB'])
                        self.assertEqual(result,{'saved':1,'rejected':0,'failed':len(failed_symbols),'deferred':0})
                        self.assertNotIn('sensitive-database-detail',json.dumps(result))
                        reopened=FileMarketDataRepository(root)
                        self.assertEqual([item['symbol'] for item in reopened.pending_activity()],list(failed_symbols))
                        self.assertEqual(json.loads(archives['MBB'].with_suffix('.ack.json').read_text())['status'],'inserted')
                        for symbol in failed_symbols:
                            self.assertEqual(archives[symbol].read_bytes(),original[symbol])
                            self.assertFalse(archives[symbol].with_suffix('.ack.json').exists())

    async def test_archive_failure_then_timeout_stops_before_later_symbols(self):
        root=Path.cwd()/'.agent-state/test-activity'/uuid4().hex;root.mkdir(parents=True)
        repo=FileMarketDataRepository(root)
        for symbol in ('FPT','HPG','MBB'):
            repo.save_daily_quote({'fetched_at':'2026-10-08T10:00:00+07:00','rows':[quote(symbol)]})
        class Pool:
            @asynccontextmanager
            async def acquire(self):yield object()
        with patch('backend.scripts.ingest_market_news_to_supabase.apply_live',
                new=AsyncMock(side_effect=[ConnectionError('secret'),TimeoutError(),{'activity_status':'inserted'}])) as apply:
            result=await flush_pending_activity(Pool(),repo)
        self.assertEqual([call.args[1]['symbol'] for call in apply.await_args_list],['FPT','HPG'])
        self.assertEqual(result,{'saved':0,'rejected':0,'failed':2,'deferred':0})
        self.assertEqual([item['symbol'] for item in FileMarketDataRepository(root).pending_activity()],['FPT','HPG','MBB'])
        self.assertNotIn('secret',json.dumps(result))

    async def test_outage_preserves_backlog_then_recovery_acknowledges(self):
        root=Path.cwd()/'.agent-state/test-activity'/uuid4().hex;root.mkdir(parents=True)
        repo=FileMarketDataRepository(root)
        repo.save_daily_quote({'fetched_at':'2026-10-08T10:00:00+07:00','rows':[quote()]})
        class Pool:
            @asynccontextmanager
            async def acquire(self):yield object()
        with patch('backend.scripts.ingest_market_news_to_supabase.apply_live',new=AsyncMock(side_effect=ConnectionError('secret'))) as apply:
            result=await flush_pending_activity(Pool(),repo)
            self.assertEqual(result['failed'],1);self.assertEqual(len(repo.pending_activity()),1)
            self.assertNotIn('secret',json.dumps(result))
            apply.side_effect=None;apply.return_value={'activity_status':'inserted'}
            result=await flush_pending_activity(Pool(),repo)
            self.assertEqual(result['saved'],1);self.assertEqual(repo.pending_activity(),[])

    async def test_never_imported_symbols_go_before_recently_imported_ones(self):
        # A flush that can only finish part of the queue must not keep re-importing the same changing
        # symbols while the rest of the basket never gets a turn.
        root=Path.cwd()/'.agent-state/test-activity'/uuid4().hex;root.mkdir(parents=True)
        repo=FileMarketDataRepository(root)
        repo.save_daily_quote({'fetched_at':'2026-10-08T10:00:00+07:00','rows':[quote('FPT')]})
        repo.ack_activity(repo.pending_activity()[0],'inserted')
        repo.save_daily_quote({'fetched_at':'2026-10-08T10:01:00+07:00','rows':[quote('FPT',volume_accumulated=150)]})
        repo.save_daily_quote({'fetched_at':'2026-10-08T10:01:00+07:00','rows':[quote('MBB')]})
        class Pool:
            @asynccontextmanager
            async def acquire(self):yield object()
        imported=[]
        async def one_then_timeout(conn,plan):
            if imported:raise TimeoutError()
            imported.append(plan['symbol'])
            return {'activity_status':'inserted'}
        with patch('backend.scripts.ingest_market_news_to_supabase.apply_live',new=one_then_timeout):
            result=await flush_pending_activity(Pool(),repo)
        self.assertEqual((imported,result['saved'],result['failed'],result['deferred']),(['MBB'],1,0,1))

    async def test_running_out_of_flush_time_is_pending_not_failure(self):
        # After the close all 30 archives change at once; a flush that saves some and runs out of
        # time must not read as a failure, or the daily refresh retries every 30 minutes.
        root=Path.cwd()/'.agent-state/test-activity'/uuid4().hex;root.mkdir(parents=True)
        repo=FileMarketDataRepository(root)
        for symbol in ('FPT','MBB'):
            repo.save_daily_quote({'fetched_at':'2026-10-08T10:00:00+07:00','rows':[quote(symbol)]})
        class Pool:
            @asynccontextmanager
            async def acquire(self):yield object()
        calls=[]
        async def slow_second(conn,plan):
            calls.append(plan['symbol'])
            if len(calls)>1:await asyncio.sleep(1)
            return {'activity_status':'inserted'}
        with patch('backend.scripts.ingest_market_news_to_supabase.apply_live',new=slow_second):
            result=await flush_pending_activity(Pool(),repo,timeout=.2)
        self.assertEqual((result['saved'],result['failed'],result.get('deferred')),(1,0,1))
        self.assertEqual(len(repo.pending_activity()),1)

    async def test_database_timeout_keeps_durable_record(self):
        root=Path.cwd()/'.agent-state/test-activity'/uuid4().hex;root.mkdir(parents=True)
        repo=FileMarketDataRepository(root)
        repo.save_daily_quote({'fetched_at':'2026-10-08T10:00:00+07:00','rows':[quote()]})
        class Pool:
            @asynccontextmanager
            async def acquire(self):yield object()
        async def delayed(*args):await asyncio.sleep(10)
        with patch('backend.scripts.ingest_market_news_to_supabase.apply_live',new=delayed):
            result=await flush_pending_activity(Pool(),repo,timeout=.01)
        self.assertEqual(result['failed'],1);self.assertEqual(len(repo.pending_activity()),1)


if __name__=='__main__':unittest.main()


class RuntimeImportTests(unittest.TestCase):
    def test_importer_is_reachable_when_api_runs_as_src_package(self):
        # The launcher starts ``uvicorn src.main:app`` from backend/, without the repository root on sys.path.
        import os, subprocess, sys
        code = ("from src.market_data.activity_store import ingest_module\n"
                "ingest = ingest_module()\n"
                "from backend.src.market_data.activity import normalize_activity\n"
                "print(len(ingest.PROJECT_SYMBOLS))")
        done = subprocess.run([sys.executable, '-B', '-c', code], cwd=Path(__file__).resolve().parents[1],
                              capture_output=True, text=True, env={**os.environ, 'PYTHONPATH': ''})
        self.assertEqual((done.returncode, done.stdout.strip()), (0, '10'), done.stderr)


class UntrackedViewerTests(ActivityCollectorTests):
    def test_viewer_only_symbol_is_served_but_never_archived(self):
        service=LiveCoordinator(self.fetch,lambda e:True,self.repo,now=lambda:self.now,
            clock=lambda:self.seconds,tracked_symbols={'FPT':'HOSE'},snapshot_sink=self.repo.save_daily_quote)
        service.watch('viewer','HPG')
        self.assertEqual(service.tick()['accepted'],2)
        self.assertEqual([item['symbol'] for item in self.repo.pending_activity()],['FPT'])
