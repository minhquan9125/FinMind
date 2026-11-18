"""Admin-only approval of source-verified NEWS graph candidates."""
from uuid import UUID
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from ...auth.authorization import require_roles, Principal
from ...core.config import get_settings
from ...documents.admin_news_index import connect_writer
from ...graph_review.models import Candidate
from ...graph_review.repository import ReviewConflict
from ...graph_review.news_workflow import approve_news, evaluate_news, publish_news

access = require_roles('ADMINISTRATOR')
router = APIRouter(prefix='/api/v1/admin/news-graph', tags=['news-graph-review'])
logger = logging.getLogger(__name__)


def rejected(exc, fallback):
    # Only fixed application codes leave the server. Never return arbitrary
    # exception text, connection strings, SQL parameters or source bodies.
    known = {
        'Expected one existing quarantine review record': 'QUARANTINE_HISTORY_MISSING',
        'Immutable candidate ID reused with changed content': 'CANDIDATE_CONTENT_CHANGED',
        'Candidate changed during review': 'CANDIDATE_CONTENT_CHANGED',
        'Review revision changed; reload first': 'REVIEW_REVISION_CHANGED',
        'GRAPH_VERSION_NOT_REVIEWABLE': 'GRAPH_VERSION_NOT_REVIEWABLE',
        'NO_APPROVED_NEWS_RELATIONS': 'NO_APPROVED_NEWS_RELATIONS',
        'ADMIN_INGEST_DATABASE_URL_REQUIRED': 'NEWS_WRITER_NOT_CONFIGURED',
        'REJECTED_CANDIDATE_IS_TERMINAL': 'REJECTED_CANDIDATE_IS_TERMINAL',
    }
    code = known.get(str(exc), fallback)
    if str(exc).startswith('NEWS_REVIEW_NOT_READY:'):
        code = 'NEWS_REVIEW_NOT_READY'
    logger.warning('news_graph_rejected code=%s', code)
    return HTTPException(503 if code == 'NEWS_WRITER_NOT_CONFIGURED' else 409, detail={'code': code})


class ApproveNews(BaseModel):
    model_config = ConfigDict(extra='forbid')
    graph_version_id: UUID
    candidate: Candidate
    note: str = Field(min_length=1, max_length=2000)


class EvaluateNews(BaseModel):
    model_config = ConfigDict(extra='forbid')
    graph_version_id: UUID
    candidate: Candidate


@router.post('/evaluate')
async def evaluate(payload: EvaluateNews, actor: Principal = Depends(access)):
    from ...core.db import get_pool
    async with get_pool().acquire() as connection:
        async with connection.transaction(readonly=True,isolation='repeatable_read'):
            result = await evaluate_news(connection, actor, payload.graph_version_id,
                                         payload.candidate.model_dump(mode='json'))
    return result.model_dump(mode='json')


class PublishNews(BaseModel):
    model_config = ConfigDict(extra='forbid')
    graph_version_id: UUID


@router.post('/state')
async def state(payload: PublishNews, actor: Principal = Depends(access)):
    from ...core.db import get_pool
    async with get_pool().acquire() as connection:
        async with connection.transaction(readonly=True,isolation='repeatable_read'):
            status = await connection.fetchval('SELECT status FROM graph_versions WHERE graph_version_id=$1', payload.graph_version_id)
            rows = await connection.fetch('''SELECT candidate_id FROM graph_review_results
                WHERE graph_version_id=$1 AND status='APPROVED' AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL''', payload.graph_version_id)
    return dict(status=status or 'NOT_CREATED',published=status=='READY',approved_candidate_ids=[r['candidate_id'] for r in rows])


def graph_store():
    from .graph_viewer import get_graph_reader
    from ...graph.sprint4_store import Sprint4GraphStore
    reader = get_graph_reader()
    return Sprint4GraphStore(reader.driver,database=reader.database)


@router.post('/publish')
async def publish(payload: PublishNews, actor: Principal = Depends(access)):
    connection = None
    try:
        connection = await connect_writer(get_settings())
        receipt = await publish_news(connection, actor, payload.graph_version_id, graph_store)
        return dict(graph_version_id=str(payload.graph_version_id),status=receipt['status'],
                    counts=receipt['counts'],checks=receipt['checks'],published=True)
    except (ValueError,ReviewConflict,PermissionError) as exc:
        raise rejected(exc, 'NEWS_GRAPH_NOT_READY_OR_CONFLICT') from None
    finally:
        if connection is not None:
            await connection.close()


@router.post('/approve')
async def approve(payload: ApproveNews, actor: Principal = Depends(access)):
    connection = None
    try:
        connection = await connect_writer(get_settings())
        row = await approve_news(connection, actor, payload.graph_version_id,
                                 payload.candidate.model_dump(mode='json'), payload.note)
        return dict(review_id=row['review_id'], graph_version_id=str(payload.graph_version_id),
                    status=row['result']['status'], revision=row['revision'], published=False)
    except (ValueError, ReviewConflict) as exc:
        raise rejected(exc, 'NEWS_REVIEW_NOT_READY_OR_CONFLICT') from None
    finally:
        if connection is not None:
            await connection.close()
