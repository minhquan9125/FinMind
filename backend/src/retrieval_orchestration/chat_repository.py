"""Owner-scoped Postgres operations with transaction-local identity and RLS."""
from contextlib import asynccontextmanager
from datetime import timedelta
import json
import uuid

import asyncpg

from .chat_logic import descriptor, validate_size
from .chat_types import ChatError, validate_uuid
from .retrieval_flow.history import _timestamp, _validate


def _json(value):
    return json.loads(value) if isinstance(value, str) else value


def _encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


class ChatRepository:
    def __init__(self, pool): self.pool = pool

    @asynccontextmanager
    async def transaction(self, owner, *, read_only=False):
        owner = validate_uuid(owner, 'Owner ID')
        async with self.pool.acquire() as conn:
            async with conn.transaction(isolation='repeatable_read' if read_only else 'read_committed', readonly=read_only):
                await conn.execute('SET LOCAL ROLE finmind_chat_runtime')
                await conn.fetchval("SELECT set_config('app.chat_user_id', $1, true)", owner)
                yield conn

    async def _load(self, conn, owner, sid, row=None):
        row = row or await conn.fetchrow('SELECT * FROM research_chat.conversations WHERE user_id=$1 AND conversation_id=$2',
                                        uuid.UUID(owner), uuid.UUID(sid))
        if row is None: raise ChatError(404, 'Phiên không tồn tại.')
        messages = await conn.fetch('SELECT position,payload FROM research_chat.messages WHERE user_id=$1 AND conversation_id=$2 ORDER BY position',
                                    uuid.UUID(owner), uuid.UUID(sid))
        if [m['position'] for m in messages] != list(range(len(messages))):
            raise ChatError(503, 'Dữ liệu phiên không hợp lệ.')
        doc = dict(schema_version=row['schema_version'], session_id=str(row['conversation_id']), owner=str(row['user_id']),
                   revision=row['revision'], started_at=row['started_at'].isoformat(), saved_at=row['saved_at'].isoformat(),
                   metadata=_json(row['metadata']), messages=[_json(m['payload']) for m in messages])
        if doc['owner'] != owner: raise ChatError(404, 'Phiên không tồn tại.')
        try:
            _validate(doc)
            validate_size(doc)
        except (ValueError, TypeError) as exc:
            raise ChatError(503, 'Dữ liệu phiên không hợp lệ.') from exc
        return doc

    async def get(self, owner, sid):
        async with self.transaction(owner, read_only=True) as conn:
            return await self._load(conn, owner, sid)

    async def list(self, owner):
        async with self.transaction(owner, read_only=True) as conn:
            rows = await conn.fetch('SELECT conversation_id,preview,saved_at,turns FROM research_chat.conversations '
                                    'WHERE user_id=$1 ORDER BY saved_at DESC,conversation_id', uuid.UUID(owner))
            return [dict(session_id=str(row['conversation_id']), preview=row['preview'],
                         saved_at=row['saved_at'].isoformat(), turns=row['turns']) for row in rows]

    async def _insert(self, conn, owner, doc):
        if doc.get('owner') != owner: raise ChatError(403, 'Chủ sở hữu không hợp lệ.')
        validate_size(doc)
        _validate(doc)
        item = descriptor(doc)
        await conn.execute('INSERT INTO research_chat.conversations '
            '(conversation_id,user_id,schema_version,revision,started_at,saved_at,metadata,preview,turns) '
            'VALUES($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9)',
            uuid.UUID(doc['session_id']), uuid.UUID(owner), doc['schema_version'], doc['revision'],
            _timestamp(doc['started_at']), _timestamp(doc['saved_at']), _encode(doc['metadata']), item['preview'], item['turns'])
        if doc['messages']:
            await conn.executemany('INSERT INTO research_chat.messages(conversation_id,user_id,position,payload) VALUES($1,$2,$3,$4::jsonb)',
                [(uuid.UUID(doc['session_id']), uuid.UUID(owner), index, _encode(message))
                 for index, message in enumerate(doc['messages'])])

    async def create(self, owner, doc):
        try:
            async with self.transaction(owner) as conn: await self._insert(conn, owner, doc)
        except asyncpg.UniqueViolationError as exc:
            raise ChatError(409, 'Mã phiên đã tồn tại.') from exc

    async def claim(self, owner, sid, revision, seconds):
        lease = uuid.uuid4()
        async with self.transaction(owner) as conn:
            row = await conn.fetchrow('UPDATE research_chat.conversations '
                'SET lease_id=$3,lease_expires_at=clock_timestamp()+$4::interval '
                'WHERE user_id=$1 AND conversation_id=$2 AND revision=$5 '
                'AND (lease_id IS NULL OR lease_expires_at<=clock_timestamp()) RETURNING *',
                uuid.UUID(owner), uuid.UUID(sid), lease, timedelta(seconds=seconds), revision)
            if row is None:
                exists = await conn.fetchval('SELECT 1 FROM research_chat.conversations WHERE user_id=$1 AND conversation_id=$2',
                                             uuid.UUID(owner), uuid.UUID(sid))
                if not exists: raise ChatError(404, 'Phiên không tồn tại.')
                raise ChatError(409, 'Phiên đang xử lý hoặc đã có tin nhắn mới. Vui lòng tải lại phiên.')
            doc = await self._load(conn, owner, sid, row)
        return doc, str(lease)

    async def commit(self, owner, sid, lease, revision, doc):
        if doc['owner'] != owner or doc['session_id'] != sid or doc['revision'] != revision+1:
            raise ChatError(409, 'Trạng thái phiên không hợp lệ.')
        validate_size(doc)
        item = descriptor(doc)
        async with self.transaction(owner) as conn:
            changed = await conn.fetchval('UPDATE research_chat.conversations '
                'SET revision=revision+1,saved_at=$5,metadata=$6::jsonb,preview=$7,turns=$8,lease_id=NULL,lease_expires_at=NULL '
                'WHERE user_id=$1 AND conversation_id=$2 AND lease_id=$3 AND revision=$4 '
                'AND lease_expires_at>clock_timestamp() RETURNING revision', uuid.UUID(owner), uuid.UUID(sid),
                uuid.UUID(lease), revision, _timestamp(doc['saved_at']), _encode(doc['metadata']), item['preview'], item['turns'])
            if changed is None: raise ChatError(409, 'Yêu cầu đã hết hạn hoặc phiên đã thay đổi. Vui lòng tải lại.')
            start = len(doc['messages'])-2
            await conn.executemany('INSERT INTO research_chat.messages(conversation_id,user_id,position,payload) VALUES($1,$2,$3,$4::jsonb)',
                [(uuid.UUID(sid), uuid.UUID(owner), start+index, _encode(message))
                 for index, message in enumerate(doc['messages'][-2:])])

    async def release(self, owner, sid, lease):
        async with self.transaction(owner) as conn:
            await conn.execute('UPDATE research_chat.conversations SET lease_id=NULL,lease_expires_at=NULL '
                'WHERE user_id=$1 AND conversation_id=$2 AND lease_id=$3', uuid.UUID(owner), uuid.UUID(sid), uuid.UUID(lease))

    async def delete(self, owner, sid):
        async with self.transaction(owner) as conn:
            row = await conn.fetchval('DELETE FROM research_chat.conversations WHERE user_id=$1 AND conversation_id=$2 '
                'AND (lease_id IS NULL OR lease_expires_at<=clock_timestamp()) RETURNING conversation_id', uuid.UUID(owner), uuid.UUID(sid))
            if row is None:
                exists = await conn.fetchval('SELECT 1 FROM research_chat.conversations WHERE user_id=$1 AND conversation_id=$2',
                                             uuid.UUID(owner), uuid.UUID(sid))
                raise ChatError(409 if exists else 404, 'Phiên đang xử lý.' if exists else 'Phiên không tồn tại.')
