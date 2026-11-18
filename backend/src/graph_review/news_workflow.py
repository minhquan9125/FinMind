"""Authenticated NEWS review persistence. No implicit approval or source repair."""
from pathlib import Path
from uuid import UUID
from .engine import IdentityRegistry, ReviewEngine
from .models import Candidate
from .repository import PostgresReviewStore, evaluate_with_peers, require_role, ReviewConflict
from .sources import PostgresSourceReader
import json

REGISTRY = Path(__file__).resolve().parents[1] / 'sprint4_runtime/company.registry.20261030.r1.json'


def review_engine(connection):
    registry = IdentityRegistry(json.loads(REGISTRY.read_text('utf8')))
    return ReviewEngine(PostgresSourceReader(connection), registry)


def news_candidate(raw):
    candidate = Candidate.model_validate(raw).model_dump(mode='json')
    candidate['temporal'] = dict(as_of=None, valid_from=None, valid_to=None) | candidate['temporal']
    # The WBS03 envelope has no empty conflict field. Keep real conflicts so the
    # review engine blocks them; omit only this model default for exact export.
    if not candidate['conflicts']:
        candidate.pop('conflicts')
    return candidate


async def evaluate_news(connection, actor, graph_id, raw):
    require_role(actor, 'ADMINISTRATOR')
    candidate = news_candidate(raw)
    if not candidate['evidence'] or any(e['locator'].get('source_table') != 'news_articles'
            or e['locator'].get('doc_type') != 'NEWS' for e in candidate['evidence']):
        raise ValueError('VERIFIED_NEWS_EVIDENCE_REQUIRED')
    return await evaluate_with_peers(PostgresReviewStore(connection), review_engine(connection), graph_id, candidate)


async def approve_news(connection, actor, graph_id, raw, note):
    require_role(actor, 'ADMINISTRATOR')
    if not isinstance(note, str) or not note.strip():
        raise ValueError('REVIEW_NOTE_REQUIRED')
    candidate = news_candidate(raw)
    refs = candidate['evidence']
    if not refs or any(e['locator'].get('source_table') != 'news_articles' or e['locator'].get('doc_type') != 'NEWS' for e in refs):
        raise ValueError('VERIFIED_NEWS_EVIDENCE_REQUIRED')
    if len({(e['corpus_id'], e['index_version_id']) for e in refs}) != 1:
        raise ValueError('MIXED_SOURCE_VERSIONS')
    engine = review_engine(connection)
    store = PostgresReviewStore(connection)
    async with connection.transaction(isolation='repeatable_read'):
        # Existing publication versions are immutable. Row lock serializes
        # concurrent reviews of the same graph, including peer-conflict checks.
        await connection.execute("INSERT INTO graph_versions(graph_version_id,status) VALUES($1,'DRAFT') ON CONFLICT DO NOTHING", UUID(str(graph_id)))
        status = await connection.fetchval('SELECT status FROM graph_versions WHERE graph_version_id=$1 FOR UPDATE', UUID(str(graph_id)))
        if status not in ('DRAFT', 'REVIEW'):
            raise ReviewConflict('GRAPH_VERSION_NOT_REVIEWABLE')
        fresh = await evaluate_with_peers(store, engine, graph_id, candidate)
        # Unresolved identity, time, plans and stale source hashes cannot be
        # turned into a completed relation by a generic approval click.
        if fresh.status != 'APPROVED' or not fresh.load_allowed:
            raise ValueError('NEWS_REVIEW_NOT_READY:' + ','.join(fresh.reasons))
        row = await store.save(candidate, fresh, graph_id, actor)
        if row['result']['status'] == 'REJECTED':
            raise ReviewConflict('REJECTED_CANDIDATE_IS_TERMINAL')
        # Persist the authenticated reviewer and audit via the existing store.
        return await store.review(row['review_id'], 'APPROVED', fresh, actor,
                                  note.strip(), row['revision'], evidence_confirmed=False)


async def publish_news(connection, actor, graph_id, graph_store_factory):
    """Stored attributed approval -> fresh gate -> immutable Neo4j publication."""
    import asyncio
    from datetime import datetime, timezone
    from .repository import approved_records
    from .gate import build_gate
    from .export import make_envelope
    from ..graph.wbs09_pipeline import build_graph_version
    require_role(actor, 'ADMINISTRATOR')
    async with connection.transaction(isolation='repeatable_read'):
        status = await connection.fetchval('SELECT status FROM graph_versions WHERE graph_version_id=$1 FOR UPDATE', UUID(str(graph_id)))
        if status not in ('DRAFT', 'REVIEW', 'READY'):
            raise ReviewConflict('GRAPH_VERSION_NOT_REVIEWABLE')
        store = PostgresReviewStore(connection); engine = review_engine(connection)
        records = await approved_records(store, engine, graph_id)
        if not records or any(not r['candidate']['evidence'] or any(
                e['locator'].get('source_table') != 'news_articles' or e['locator'].get('doc_type') != 'NEWS'
                for e in r['candidate']['evidence']) for r in records):
            raise ValueError('NO_APPROVED_NEWS_RELATIONS')
        envelope = await make_envelope(connection, records, engine.reader)
        gate = await build_gate(store, engine, graph_id, envelope)
        graph_store = graph_store_factory()
        receipt = await asyncio.to_thread(build_graph_version, graph_store, [envelope],
            graph_version_id=str(graph_id), approve=lambda _: gate)
        if receipt['status'] != 'READY':
            raise ReviewConflict('NEWS_GRAPH_NOT_READY')
        await connection.execute('''UPDATE graph_versions SET status='READY',node_count=$2,edge_count=$3,built_at=$4
            WHERE graph_version_id=$1''', UUID(str(graph_id)),len(envelope['entities']),
            receipt['counts']['loaded'],datetime.now(timezone.utc))
        return receipt
