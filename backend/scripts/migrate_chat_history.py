"""Admin migration/import. Default is read-only; old files are never changed.

Run from the repository root with the existing backend Python environment.
--apply-schema applies only the pinned additive chat migration.
--import-json imports validated, existing owners' web histories idempotently.
"""
import argparse
import asyncio
from datetime import timezone
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import asyncpg

from src.core.config import get_settings
from src.retrieval_orchestration.chat_repository import ChatRepository
from src.retrieval_orchestration.chat_types import ChatError, validate_uuid
from src.retrieval_orchestration.chat_logic import validate_size
from src.retrieval_orchestration.retrieval_flow.history import load_history, _timestamp

ROOT = Path(__file__).resolve().parents[2]
VERSION = '20261024000100'
MIGRATION = ROOT/'supabase/migrations/20261024000100_research_chat_history.sql'
LEGACY = ROOT/'backend/src/retrieval_orchestration/chat_history/web'


def fingerprint(doc):
    doc = dict(doc)
    for field in ('started_at', 'saved_at'):
        doc[field] = _timestamp(doc[field]).astimezone(timezone.utc).isoformat()
    return hashlib.sha256(json.dumps(doc, sort_keys=True, ensure_ascii=False, allow_nan=False).encode('utf8')).hexdigest()


def legacy_documents(root, owners):
    counts = dict(valid=0, unknown_owner=0, invalid=0)
    docs = []
    if not root.exists(): return docs, counts
    if any(path.is_symlink() or getattr(path, 'is_junction', lambda: False)() for path in (root, *root.parents)):
        raise ValueError('Unsafe history root')
    for directory in root.iterdir():
        if not directory.is_dir() or directory.is_symlink() or getattr(directory, 'is_junction', lambda: False)(): continue
        try: owner = validate_uuid(directory.name, 'Owner ID')
        except ChatError:
            counts['invalid'] += 1
            continue
        for path in directory.glob('*.json'):
            if owner not in owners:
                counts['unknown_owner'] += 1
                continue
            try:
                sid = validate_uuid(path.stem, 'Session ID')
                doc = load_history(path.name, directory)
                if (doc.get('owner') != owner or doc['session_id'] != sid
                        or type(doc.get('revision')) is not int or doc['revision'] < 0
                        or not isinstance(doc.get('metadata'), dict)):
                    raise ValueError('Invalid owner/history')
                if doc['metadata'].get('execution_mode') == 'LIVE' and not isinstance(doc['metadata'].get('live_context', {}), dict):
                    raise ValueError('Invalid live context')
                validate_size(doc)
            except (OSError, ValueError, ChatError, TypeError):
                counts['invalid'] += 1
                continue
            docs.append(doc)
            counts['valid'] += 1
    return docs, counts


async def apply_schema(pool):
    sql = MIGRATION.read_text('utf8')
    checksum = hashlib.sha256(sql.encode('utf8')).hexdigest()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended('finmind:research-chat-migration',0))")
            exists = await conn.fetchval("SELECT to_regclass('research_chat.schema_migrations') IS NOT NULL")
            old = await conn.fetchval('SELECT sha256 FROM research_chat.schema_migrations WHERE version=$1', VERSION) if exists else None
            if old and old != checksum: raise ValueError('Migration checksum changed; do not modify an applied migration')
            if not old:
                await conn.execute(sql)
                await conn.execute('INSERT INTO research_chat.schema_migrations(version,sha256) VALUES($1,$2)', VERSION, checksum)
    return {'version': VERSION, 'applied': not bool(old)}


async def import_documents(repository, documents):
    counts = dict(imported=0, already_present=0, kept_existing=0)
    for doc in documents:
        owner, sid = doc['owner'], doc['session_id']
        try:
            existing = await repository.get(owner, sid)
        except ChatError as exc:
            if exc.status != 404: raise
            try:
                await repository.create(owner, doc)
                counts['imported'] += 1
            except ChatError as conflict:
                if conflict.status != 409: raise
                counts['kept_existing'] += 1
        else:
            key = 'already_present' if fingerprint(existing) == fingerprint(doc) else 'kept_existing'
            counts[key] += 1
    return counts


async def run(args):
    pool = await asyncpg.create_pool(get_settings().database_url, ssl='require', min_size=1, max_size=2,
                                    timeout=10, command_timeout=30, statement_cache_size=0)
    try:
        async with pool.acquire() as conn:
            async with conn.transaction(readonly=True):
                owners = {str(row['user_id']) for row in await conn.fetch('SELECT user_id FROM public.users')}
                ready = await conn.fetchval("SELECT to_regclass('research_chat.conversations') IS NOT NULL")
        documents, legacy = legacy_documents(LEGACY, owners)
        report = {'legacy': legacy, 'database_ready': ready}
        if args.apply_schema:
            report['migration'] = await apply_schema(pool)
            ready = True
        if args.import_json:
            if not ready: raise ValueError('Apply the schema before importing histories')
            report['import'] = await import_documents(ChatRepository(pool), documents)
        report['database_ready'] = ready
        if ready:
            async with pool.acquire() as conn:
                async with conn.transaction(readonly=True):
                    report['database'] = dict(conversations=await conn.fetchval('SELECT count(*) FROM research_chat.conversations'),
                                              messages=await conn.fetchval('SELECT count(*) FROM research_chat.messages'))
        print(json.dumps(report, ensure_ascii=False))
    finally:
        await pool.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply-schema', action='store_true')
    parser.add_argument('--import-json', action='store_true')
    options = parser.parse_args()
    try: asyncio.run(run(options))
    except Exception as exc:
        # Never emit DSNs, credentials, messages, user names or raw DB errors.
        print(json.dumps({'migration_failed': type(exc).__name__}), file=sys.stderr)
        raise SystemExit(1)
