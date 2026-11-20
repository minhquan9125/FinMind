"""Serving-corpus pointer shared through PostgreSQL, so every backend serves the same corpus.

The local admin queue (SQLite) stays per machine for jobs, articles and audit. Only this pointer
must be common: whoever activates or switches a corpus writes it here, and every backend reads it.
Reads are served from an in-memory copy refreshed in the background, so the chat path never waits
on the database. When the database or the table is unavailable the local pointer is used, which is
exactly the previous behaviour.
"""
from __future__ import annotations

import asyncio
import logging
import threading

TABLE = 'public.admin_serving_corpus'
logger = logging.getLogger(__name__)


class SharedServing:
    def __init__(self):
        self._lock = threading.Lock()
        self._value = None

    def get(self):
        """{'corpus_id', 'index_id', 'updated_by'} from the last successful read, else None. No I/O."""
        with self._lock:
            return dict(self._value) if self._value else None

    def corpus_id(self):
        value = self.get()
        return value['corpus_id'] if value else None

    def set(self, corpus_id, index_id, updated_by=None):
        with self._lock:
            self._value = {'corpus_id': str(corpus_id), 'index_id': str(index_id), 'updated_by': updated_by}

    def clear(self):
        with self._lock:
            self._value = None

    async def refresh(self, conn):
        """Read the shared row. A missing row clears the copy; a read error keeps the last good value."""
        row = await conn.fetchrow(
            f'SELECT corpus_version_id::text AS corpus, index_version_id::text AS idx, updated_by FROM {TABLE} WHERE id = 1')
        if row is None:
            self.clear()
        else:
            self.set(row['corpus'], row['idx'], row['updated_by'])
        return self.get()

    async def publish(self, writer, corpus_id, index_id, actor):
        """Upsert the shared row with a writer connection and update the local copy."""
        await writer.execute(
            f'''INSERT INTO {TABLE}(id, corpus_version_id, index_version_id, updated_by)
                VALUES (1, $1::uuid, $2::uuid, $3)
                ON CONFLICT (id) DO UPDATE SET corpus_version_id = EXCLUDED.corpus_version_id,
                    index_version_id = EXCLUDED.index_version_id, updated_at = now(), updated_by = EXCLUDED.updated_by''',
            str(corpus_id), str(index_id), str(actor))
        self.set(corpus_id, index_id, str(actor))


_SHARED = SharedServing()


def shared_pointer():
    return _SHARED


async def best_effort_publish(writer, corpus_id, index_id, actor):
    """Publish without ever failing the caller: the local pointer is already set, so a missing table
    or an unreachable database only means other machines learn about it later."""
    try:
        await _SHARED.publish(writer, corpus_id, index_id, actor)
        return True
    except Exception as exc:
        logger.warning('shared serving corpus not published: %s', type(exc).__name__)
        return False


async def refresh_loop(get_pool, interval=15.0, stop=None):
    """Keep the in-memory copy fresh until `stop` (an asyncio.Event) is set."""
    while stop is None or not stop.is_set():
        try:
            async with get_pool().acquire() as conn:
                await _SHARED.refresh(conn)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.debug('shared serving corpus refresh skipped: %s', type(exc).__name__)
        try:
            if stop is None:
                await asyncio.sleep(interval)
            else:
                await asyncio.wait_for(stop.wait(), interval)
        except asyncio.TimeoutError:
            pass
