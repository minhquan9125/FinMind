"""Serving-corpus pointer shared through PostgreSQL: the same corpus on every machine."""
import asyncio
from pathlib import Path

import pytest

from src.documents import admin_corpus, shared_serving
from src.documents.admin_ingestion import Queue
from src.documents.shared_serving import SharedServing, best_effort_publish, refresh_loop, shared_pointer

LOCAL, REMOTE, DEFAULT = ('aaaaaaaa-0000-0000-0000-00000000000%d' % n for n in (1, 2, 3))
IDX_LOCAL, IDX_REMOTE = 'bbbbbbbb-0000-0000-0000-000000000001', 'bbbbbbbb-0000-0000-0000-000000000002'
MIGRATION = Path(__file__).resolve().parents[2] / 'docker' / 'postgres' / 'init' / '095_admin_serving_corpus.sql'


@pytest.fixture(autouse=True)
def clean_pointer():
    shared_pointer().clear()
    yield
    shared_pointer().clear()


class Conn:
    def __init__(self, row=None, fail=False):
        self.row, self.fail, self.executed = row, fail, []

    async def fetchrow(self, sql):
        if self.fail: raise RuntimeError('db down')
        return self.row

    async def execute(self, sql, *args):
        if self.fail: raise RuntimeError('relation does not exist')
        self.executed.append(args)
        return 'INSERT 0 1'


def run(coro):
    return asyncio.run(coro)


# ---- the pointer ---------------------------------------------------------------------------

def test_refresh_copies_the_shared_row_and_a_missing_row_clears_it():
    pointer = SharedServing()
    row = {'corpus': REMOTE, 'idx': IDX_REMOTE, 'updated_by': 'u1'}
    assert run(pointer.refresh(Conn(row))) == {'corpus_id': REMOTE, 'index_id': IDX_REMOTE, 'updated_by': 'u1'}
    assert pointer.corpus_id() == REMOTE
    assert run(pointer.refresh(Conn(None))) is None and pointer.corpus_id() is None


def test_a_failed_refresh_keeps_the_last_good_value():
    pointer = SharedServing()
    pointer.set(REMOTE, IDX_REMOTE)
    with pytest.raises(RuntimeError):
        run(pointer.refresh(Conn(fail=True)))
    assert pointer.corpus_id() == REMOTE


def test_publish_writes_one_row_and_updates_the_local_copy():
    pointer, writer = SharedServing(), Conn()
    run(pointer.publish(writer, REMOTE, IDX_REMOTE, 'admin-1'))
    assert writer.executed == [(REMOTE, IDX_REMOTE, 'admin-1')]
    assert pointer.get()['corpus_id'] == REMOTE


def test_best_effort_publish_never_raises_and_reports_failure():
    assert run(best_effort_publish(Conn(), REMOTE, IDX_REMOTE, 'a')) is True
    assert shared_pointer().corpus_id() == REMOTE
    shared_pointer().clear()
    assert run(best_effort_publish(Conn(fail=True), REMOTE, IDX_REMOTE, 'a')) is False
    assert shared_pointer().corpus_id() is None                 # a failed write never changes what is served


def test_get_returns_a_copy():
    pointer = SharedServing(); pointer.set(REMOTE, IDX_REMOTE)
    pointer.get()['corpus_id'] = 'tampered'
    assert pointer.corpus_id() == REMOTE


# ---- the queue uses it -----------------------------------------------------------------------

def test_the_shared_pointer_decides_over_the_local_one_and_the_default(tmp_path):
    q = Queue(tmp_path)
    assert q.serving_corpus(DEFAULT) == DEFAULT
    q.publish_corpus(LOCAL, IDX_LOCAL)
    assert q.serving_corpus(DEFAULT) == LOCAL                  # no shared row: previous behaviour
    shared_pointer().set(REMOTE, IDX_REMOTE)
    assert q.serving_corpus(DEFAULT) == REMOTE                 # another machine activated REMOTE
    shared_pointer().clear()
    assert q.serving_corpus(DEFAULT) == LOCAL                  # database unreachable or row removed


def test_overview_reports_the_corpus_actually_served(tmp_path):
    q = Queue(tmp_path); q.publish_corpus(LOCAL, IDX_LOCAL)
    assert q.overview(DEFAULT)['corpus_id'] == LOCAL
    shared_pointer().set(REMOTE, IDX_REMOTE)
    assert q.overview(DEFAULT)['corpus_id'] == REMOTE


def test_activation_is_refused_when_another_machine_moved_the_corpus_first(tmp_path):
    q = Queue(tmp_path); q.publish_corpus(LOCAL, IDX_LOCAL)
    job, _ = q.create_job('CRAWL', 'admin')                    # any running job: the guard only reads pointers
    q.update_job(job, 'RUNNING')
    shared_pointer().set(REMOTE, IDX_REMOTE)                   # a teammate switched meanwhile
    with pytest.raises(ValueError, match='SHARED_BASE_CHANGED_REBUILD_REQUIRED'):
        q.finish_index(job, {}, corpus_id=str(UUIDS[0]), default_corpus=DEFAULT, expected_base=LOCAL)


UUIDS = ['cccccccc-0000-0000-0000-000000000001']


# ---- switching shares the choice ---------------------------------------------------------------

class FrozenConn:
    async def fetchrow(self, sql, cid):
        return {'corpus_version_id': str(cid), 'status': 'FROZEN', 'manifest_sha256': 'm' * 64,
                'index_version_id': IDX_REMOTE, 'index_status': 'ACTIVE'}


def test_switching_publishes_to_the_other_machines_and_reports_it(tmp_path):
    q = Queue(tmp_path); q.publish_corpus(LOCAL, IDX_LOCAL)
    calls = []

    async def publish(corpus, index, actor):
        calls.append((corpus, index, actor)); return True
    result = run(admin_corpus.switch_serving(FrozenConn(), q, REMOTE, DEFAULT, 'admin', publish))
    assert calls == [(REMOTE, IDX_REMOTE, 'admin')] and result['shared'] is True


def test_switching_without_a_publisher_stays_local(tmp_path):
    q = Queue(tmp_path); q.publish_corpus(LOCAL, IDX_LOCAL)
    assert run(admin_corpus.switch_serving(FrozenConn(), q, REMOTE, DEFAULT, 'admin'))['shared'] is False
    assert q.serving_corpus(DEFAULT) == REMOTE


# ---- background refresh ------------------------------------------------------------------------

def test_the_refresh_loop_reads_until_stopped_and_survives_errors(monkeypatch):
    reads = []

    class Pool:
        def acquire(self):
            outer = self

            class Ctx:
                async def __aenter__(self_inner):
                    reads.append(1)
                    if len(reads) == 1: raise RuntimeError('first read fails')
                    return Conn({'corpus': REMOTE, 'idx': IDX_REMOTE, 'updated_by': 'u'})

                async def __aexit__(self_inner, *a): return False
            return Ctx()

    async def go():
        stop = asyncio.Event()
        task = asyncio.create_task(refresh_loop(lambda: Pool(), interval=0.01, stop=stop))
        await asyncio.sleep(0.15)
        stop.set()
        await asyncio.wait_for(task, 2)
    run(go())
    assert len(reads) >= 2 and shared_pointer().corpus_id() == REMOTE


# ---- migration ---------------------------------------------------------------------------------

def test_migration_creates_a_read_only_rls_table_with_a_single_row():
    sql = MIGRATION.read_text(encoding='utf-8')
    assert 'CREATE TABLE IF NOT EXISTS public.admin_serving_corpus' in sql
    assert 'CHECK (id = 1)' in sql and 'ENABLE ROW LEVEL SECURITY' in sql
    assert 'REFERENCES public.corpus_versions' in sql and 'REFERENCES public.index_versions' in sql
    assert 'GRANT SELECT ON public.admin_serving_corpus' in sql
    for forbidden in ('GRANT INSERT', 'GRANT UPDATE', 'GRANT ALL', 'TO PUBLIC', 'FOR ALL'):
        assert forbidden not in sql
