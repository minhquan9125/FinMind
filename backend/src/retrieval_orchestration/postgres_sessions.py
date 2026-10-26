"""Web chat persistence in Supabase Postgres. No file writes or JSON fallback."""
import asyncio
import logging
import math
import uuid

from .chat_types import ChatError, validate_uuid
from .chat_logic import append_turn, new_document, snapshot, validate_input
from .chat_repository import ChatRepository

logger = logging.getLogger(__name__)


class PostgresSessionStore:
    def __init__(self, pool=None, *, engine=None, repository=None):
        self.engine = engine
        self.repository = repository if repository is not None else ChatRepository(pool)

    @staticmethod
    def _identity(owner, sid=None):
        return validate_uuid(owner, 'Owner ID'), validate_uuid(sid, 'Session ID') if sid is not None else None

    async def create(self, owner):
        owner, _ = self._identity(owner)
        doc = new_document(owner, str(uuid.uuid4()))
        doc['metadata']['execution_mode'] = 'LIVE' if self.engine is not None else 'FIXTURE'
        await self.repository.create(owner, doc)
        return await snapshot(doc)

    async def list(self, owner):
        owner, _ = self._identity(owner)
        return await self.repository.list(owner)

    async def get(self, owner, session_id):
        owner, sid = self._identity(owner, session_id)
        return await snapshot(await self.repository.get(owner, sid))

    async def send(self, owner, session_id, text, revision):
        owner, sid = self._identity(owner, session_id)
        text = validate_input(text, revision)
        timeout = self.engine.retrieval_timeout+self.engine.limits.read_timeout_seconds+5 if self.engine is not None else 10
        seconds = max(60, math.ceil(timeout)+30)
        doc, lease = await self.repository.claim(owner, sid, revision, seconds)
        committed = False
        try:
            updated = await append_turn(doc, text, self.engine)
            await self.repository.commit(owner, sid, lease, revision, updated)
            committed = True
            return await snapshot(updated)
        finally:
            if not committed:
                try:
                    await asyncio.shield(self.repository.release(owner, sid, lease))
                except Exception:
                    # The finite DB lease also recovers process/network failure.
                    # No raw exceptions/DSNs or fallback to local files.
                    logger.warning('Chat lease cleanup unavailable; bounded lease will expire')

    async def resume(self, owner, session_id):
        owner, sid = self._identity(owner, session_id)
        source = await self.repository.get(owner, sid)
        doc = new_document(owner, str(uuid.uuid4()), source)
        await self.repository.create(owner, doc)
        return await snapshot(doc)

    async def delete(self, owner, session_id):
        owner, sid = self._identity(owner, session_id)
        await self.repository.delete(owner, sid)
