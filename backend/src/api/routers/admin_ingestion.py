"""Admin collection/review/index actions; each request rechecks server grants."""
import uuid
import asyncio
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from ...documents.admin_ingestion import DEFAULT
from starlette.concurrency import run_in_threadpool

from ...auth.authorization import require_roles
from ...core.config import get_settings
from ...documents.admin_ingestion import Queue, crawl_job
from ...documents.admin_news_index import index_job, activate

access = require_roles('ADMINISTRATOR')
router = APIRouter(prefix='/api/v1/admin/ingestion', tags=['admin-ingestion'], dependencies=[Depends(access)])


def queue():
    return Queue(get_settings().admin_ingestion_directory)


def operation(fn):
    try: return fn()
    except ValueError as exc:
        raise HTTPException(409, detail=str(exc)) from None


@router.get('/overview')
async def overview(request: Request):
    from ...core.db import get_pool
    settings = get_settings()
    data = await run_in_threadpool(lambda: queue().overview(settings.research_corpus_version_id))
    from ...documents.research_metrics import ResearchMetrics
    try:
        data['telemetry'] = await run_in_threadpool(lambda: ResearchMetrics(settings.admin_ingestion_directory).summary())
    except Exception:
        data['telemetry'] = {'status': 'unavailable'}
    from ...documents.api_budget import ApiBudget
    try:data['api_budget']=await run_in_threadpool(lambda:ApiBudget(settings.admin_ingestion_directory).snapshot())
    except Exception:data['api_budget']={'status':'unavailable'}
    # Warmup only proves local initialization, not the availability of the LLM provider.
    data['initialization'] = {
        key: getattr(request.app.state, key + '_warmup', {}).get('status', 'not_started')
        for key in ('research', 'router')
    }
    async def inspect():
        async with get_pool().acquire() as conn:
            return await conn.fetchrow('''SELECT cv.status AS corpus_status,iv.status AS index_status,
                iv.index_version_id::text AS index_id,
                (SELECT count(*) FROM public.corpus_documents cd WHERE cd.corpus_version_id=cv.corpus_version_id) AS documents,
                (SELECT count(*) FROM public.text_chunks t WHERE t.index_version_id=iv.index_version_id
                    AND t.superseded_at IS NULL) AS chunks
                FROM public.corpus_versions cv JOIN public.index_versions iv USING(index_version_id)
                WHERE cv.corpus_version_id=$1::uuid''', uuid.UUID(data['corpus_id']))
    try:
        row = await asyncio.wait_for(inspect(), timeout=5)
        data['storage'] = {'status': 'available' if row else 'missing', **(dict(row) if row else {})}
    except Exception:
        # Do not expose connection strings or provider errors to the browser.
        data['storage'] = {'status': 'unavailable'}
    return data


@router.get('/audit')
async def audit_events(offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=100),
                       category: Literal['operation', 'review'] | None = None):
    return await run_in_threadpool(lambda: queue().audit_page(offset, limit, category))


class SourceConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provider: Literal['fireant'] = 'fireant'
    enabled: bool = False
    hour: int = Field(7, ge=0, le=23)
    limit: int = Field(100, ge=1, le=500)
    symbols: list[str] = Field(default_factory=lambda: list(DEFAULT['symbols']), max_length=30)
    max_pages: int = Field(5, ge=1, le=20)
    include_market: bool = True
    auto_approve: bool = False
    auto_index: bool = False
    auto_activate: bool = False

    @model_validator(mode='after')
    def activation_needs_index(self):
        if self.auto_activate and not self.auto_index:
            raise ValueError('auto_activate requires auto_index')
        return self

    @field_validator('symbols')
    @classmethod
    def tickers(cls, values):
        import re
        if any(not re.fullmatch('[A-Z]{3}', v) for v in values): raise ValueError('Ticker must have 3 uppercase letters')
        return list(dict.fromkeys(values))

    @model_validator(mode='after')
    def scope_required(self):
        if not self.symbols and not self.include_market: raise ValueError('Select tickers or market news')
        return self


class ModelRate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    model: str=Field(min_length=1,max_length=100,pattern=r'^[a-zA-Z0-9_.:/@-]+$')
    input_per_million: Decimal=Field(ge=0,le=1000000,max_digits=14,decimal_places=6,allow_inf_nan=False)
    output_per_million: Decimal=Field(ge=0,le=1000000,max_digits=14,decimal_places=6,allow_inf_nan=False)


class BudgetConfig(BaseModel):
    model_config=ConfigDict(extra='forbid')
    mode: Literal['unconfigured','free','paid']
    period: Literal['day','month']
    limit_usd: Decimal=Field(gt=0,le=1000000,max_digits=14,decimal_places=6,allow_inf_nan=False)
    warn_at: int=Field(ge=1,le=100)
    rates: list[ModelRate]=Field(default_factory=list,max_length=30)
    reason: str=Field(min_length=3,max_length=1000)
    expected_version: uuid.UUID | None=None

    @model_validator(mode='after')
    def valid_rates(self):
        if len({r.model for r in self.rates})!=len(self.rates):raise ValueError('Duplicate model')
        if self.mode=='paid' and not self.rates:raise ValueError('Paid mode requires prices')
        if len(self.reason.strip())<3:raise ValueError('Reason required')
        return self


@router.get('/budget')
async def budget():
    from ...documents.api_budget import ApiBudget
    return await run_in_threadpool(lambda:ApiBudget(get_settings().admin_ingestion_directory).snapshot())


@router.put('/budget')
async def configure_budget(payload: BudgetConfig,principal=Depends(access)):
    from ...documents.api_budget import ApiBudget
    def save():
        cfg=payload.model_dump(mode='json',exclude={'reason','expected_version'})
        store=ApiBudget(get_settings().admin_ingestion_directory)
        version=operation(lambda:store.save(cfg,str(principal.user_id),payload.reason.strip(),str(payload.expected_version) if payload.expected_version else None))
        queue().audit(str(principal.user_id),'BUDGET_CONFIG',version)
        return store.snapshot()
    return await run_in_threadpool(save)


@router.get('/traces')
async def traces(offset: int=Query(0,ge=0),limit: int=Query(30,ge=1,le=100),
    outcome: Literal['SUCCESS','ERROR','INSUFFICIENT_EVIDENCE','CLARIFICATION','OTHER'] | None=None,
    company: str | None=Query(None,pattern=r'^[A-Z0-9]{1,15}$'),day: date | None=None):
    from ...documents.research_metrics import ResearchMetrics
    return await run_in_threadpool(lambda:ResearchMetrics(get_settings().admin_ingestion_directory).list(
        offset,limit,outcome_filter=outcome,company=company,day=day.isoformat() if day else None))


@router.get('/traces/{trace_id}')
async def trace_detail(trace_id: uuid.UUID):
    from ...documents.research_metrics import ResearchMetrics
    item=await run_in_threadpool(lambda:ResearchMetrics(get_settings().admin_ingestion_directory).detail(str(trace_id)))
    if not item:raise HTTPException(404,detail='TRACE_NOT_FOUND')
    return item


class Review(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: Literal['APPROVED', 'REJECTED', 'QUARANTINED']
    note: str = Field(min_length=3, max_length=2000)


class Selection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    article_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)


class Deletion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    article_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)


class Search(BaseModel):
    question: str = Field(min_length=3, max_length=500)


@router.get('/source')
async def source():
    return await run_in_threadpool(lambda: queue().config())


@router.put('/source')
async def configure(payload: SourceConfig, principal=Depends(access)):
    def save():
        q = queue(); value = q.config(payload.model_dump())
        q.audit(str(principal.user_id), 'SOURCE_CONFIG', 'fireant')
        return value
    return await run_in_threadpool(save)


@router.post('/crawl', status_code=202)
async def crawl(tasks: BackgroundTasks, principal=Depends(access)):
    q = queue(); ident, _ = operation(lambda: q.create_job('CRAWL', str(principal.user_id)))
    tasks.add_task(crawl_job, q, ident)
    return {'job_id': ident, 'status': 'QUEUED'}


@router.get('/corpus')
async def corpus_versions():
    """Read-only list of corpus versions in the shared DB and which one chat is serving."""
    from ...core.db import get_pool
    from ...documents.admin_corpus import list_versions
    settings = get_settings()
    serving = await run_in_threadpool(lambda: queue().serving_corpus(settings.research_corpus_version_id))
    try:
        async with get_pool().acquire() as conn:
            return await list_versions(conn, serving)
    except Exception:
        raise HTTPException(503, detail='CORPUS_UNAVAILABLE') from None


@router.get('/corpus/{corpus_id}/documents')
async def corpus_documents(corpus_id: uuid.UUID, offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=100),
                           doc_type: str | None = Query(None, pattern='^[A-Z_]{1,40}$')):
    from ...core.db import get_pool
    from ...documents.admin_corpus import list_documents
    try:
        async with get_pool().acquire() as conn:
            page = await list_documents(conn, corpus_id, offset=offset, limit=limit, doc_type=doc_type)
    except Exception:
        raise HTTPException(503, detail='CORPUS_UNAVAILABLE') from None
    if page is None:
        raise HTTPException(404, detail='CORPUS_NOT_FOUND')
    return page


def _corpus_action_error(exc):
    code = str(exc)
    raise HTTPException(404 if code == 'CORPUS_NOT_FOUND' else 409, detail=code) from None


@router.post('/corpus/{corpus_id}/serve')
async def serve_corpus(corpus_id: uuid.UUID, principal=Depends(access)):
    """Switch Chat to an existing frozen corpus. Only moves the serving pointer; nothing is rewritten."""
    from ...core.db import get_pool
    from ...documents.admin_corpus import CorpusActionError, switch_serving
    settings = get_settings()
    async def publish(cid, index_id, actor):
        # Share the choice with the other machines; the local switch has already happened.
        from ...documents.admin_news_index import connect_writer
        from ...documents.shared_serving import best_effort_publish
        if not settings.admin_ingest_database_url: return False
        try:
            writer = await connect_writer(settings)
        except Exception:
            return False
        try:
            return await best_effort_publish(writer, cid, index_id, actor)
        finally:
            await writer.close()
    try:
        async with get_pool().acquire() as conn:
            return await switch_serving(conn, queue(), corpus_id, settings.research_corpus_version_id, str(principal.user_id), publish)
    except CorpusActionError as exc:
        _corpus_action_error(exc)
    except Exception:
        raise HTTPException(503, detail='CORPUS_UNAVAILABLE') from None


async def _archive(corpus_id, principal, archived):
    from ...documents.admin_corpus import CorpusActionError, set_archived
    from ...documents.admin_news_index import connect_writer
    settings = get_settings()
    if not settings.admin_ingest_database_url:
        raise HTTPException(503, detail='ADMIN_INGEST_DATABASE_URL_REQUIRED')
    try:
        writer = await connect_writer(settings)
        try:
            return await set_archived(writer, queue(), corpus_id, archived, settings.research_corpus_version_id, str(principal.user_id))
        finally:
            await writer.close()
    except CorpusActionError as exc:
        _corpus_action_error(exc)
    except Exception:
        raise HTTPException(503, detail='CORPUS_UNAVAILABLE') from None


@router.post('/corpus/{corpus_id}/archive')
async def archive_corpus(corpus_id: uuid.UUID, principal=Depends(access)):
    return await _archive(corpus_id, principal, True)


@router.post('/corpus/{corpus_id}/restore')
async def restore_corpus(corpus_id: uuid.UUID, principal=Depends(access)):
    return await _archive(corpus_id, principal, False)


def _key_store():
    from ...b1_answering.providers.key_store import KeyStore
    settings = get_settings()
    return KeyStore(settings.admin_ingestion_directory, settings.gemini_keys_secret.get_secret_value())


def _env_key_fingerprints():
    from ...b1_answering.providers.key_pool import parse_keys
    from ...b1_answering.providers.key_store import fingerprint
    settings = get_settings()
    return {fingerprint(k) for k in parse_keys(settings.gemini_api_key.get_secret_value(), settings.gemini_api_keys.get_secret_value())}


def _key_error(exc):
    code = str(exc)
    status = {'KEY_NOT_FOUND': 404, 'KEY_STORE_DISABLED': 503}.get(code, 422 if code in ('KEY_FORMAT_INVALID', 'KEY_LABEL_INVALID') else 409)
    raise HTTPException(status, detail=code) from None


async def _json_body(request: Request):
    """Parse the body by hand: validation errors from a model would echo the submitted key back."""
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(422, detail='KEY_BODY_INVALID') from None
    if not isinstance(data, dict):
        raise HTTPException(422, detail='KEY_BODY_INVALID')
    return data


def _key_view():
    from ...b1_answering.providers.key_pool import active_status
    from ...b1_answering.providers.key_store import MAX_KEYS
    store = _key_store()
    return {**active_status(), 'managed': store.list() if store.usable else [],
            'store': {'usable': store.usable, 'limit': MAX_KEYS}}


@router.get('/gemini-keys')
async def gemini_keys():
    """Key rotation state and the keys managed on the admin page. Never returns a key."""
    return await run_in_threadpool(_key_view)


@router.post('/gemini-keys', status_code=201)
async def add_gemini_key(request: Request, principal=Depends(access)):
    """Add a key. It is checked with Google first (no content is generated), then stored encrypted."""
    from ...b1_answering.providers.gemini import probe_key
    from ...b1_answering.providers.key_pool import active_status
    from ...b1_answering.providers.key_store import LABEL_FORMAT, refresh_active_source, validate_key
    data = await _json_body(request)
    label, key = data.get('label'), data.get('key')
    store = _key_store()
    try:
        if not store.usable: raise ValueError('KEY_STORE_DISABLED')
        validate_key(key)
        if not isinstance(label, str) or not LABEL_FORMAT.fullmatch(label.strip()): raise ValueError('KEY_LABEL_INVALID')
    except ValueError as exc:
        _key_error(exc)
    outcome = await probe_key(key.strip())
    if outcome == 'INVALID':
        raise HTTPException(409, detail='KEY_REJECTED')
    try:
        item = await run_in_threadpool(lambda: store.add(label, key, str(principal.user_id),
                                                        verified=outcome in ('OK', 'QUOTA'), extra_fingerprints=_env_key_fingerprints()))
    except ValueError as exc:
        _key_error(exc)
    queue().audit(str(principal.user_id), 'GEMINI_KEY_ADD', item['label'])
    refresh_active_source()
    return {'item': item, 'verification': outcome, 'restart_needed': not active_status()['configured']}


@router.post('/gemini-keys/{key_id}/test')
async def test_gemini_key(key_id: uuid.UUID):
    """Ask Google whether a stored key still works. Reads the key inside the backend only."""
    from ...b1_answering.providers.gemini import probe_key
    store = _key_store()
    secret = await run_in_threadpool(lambda: store.secret(str(key_id)))
    if secret is None:
        raise HTTPException(404, detail='KEY_NOT_FOUND')
    outcome = await probe_key(secret)
    await run_in_threadpool(lambda: store.mark_verified(str(key_id), outcome in ('OK', 'QUOTA')))
    return {'result': outcome}


@router.patch('/gemini-keys/{key_id}')
async def toggle_gemini_key(key_id: uuid.UUID, request: Request, principal=Depends(access)):
    from ...b1_answering.providers.key_store import refresh_active_source
    data = await _json_body(request)
    if not isinstance(data.get('enabled'), bool):
        raise HTTPException(422, detail='KEY_BODY_INVALID')
    try:
        item = await run_in_threadpool(lambda: _key_store().set_enabled(str(key_id), data['enabled']))
    except ValueError as exc:
        _key_error(exc)
    queue().audit(str(principal.user_id), 'GEMINI_KEY_ENABLE' if data['enabled'] else 'GEMINI_KEY_DISABLE', item['label'])
    refresh_active_source()
    return {'item': item}


@router.delete('/gemini-keys/{key_id}')
async def delete_gemini_key(key_id: uuid.UUID, principal=Depends(access)):
    from ...b1_answering.providers.key_store import refresh_active_source
    try:
        label = await run_in_threadpool(lambda: _key_store().delete(str(key_id)))
    except ValueError as exc:
        _key_error(exc)
    queue().audit(str(principal.user_id), 'GEMINI_KEY_DELETE', label)
    refresh_active_source()
    return {'deleted': True}


class LimitsUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    values: dict[str, int] = Field(default_factory=dict, max_length=10)
    reason: str = Field(min_length=3, max_length=500)
    expected_version: str | None = None


def _limits_view(root):
    from ...b1_answering.core.policy import Limits
    from ...documents.limit_overrides import EDITABLE, LimitOverrides, apply
    store = LimitOverrides(root)
    version, overrides = store.current()
    base = Limits.load()
    fields = tuple(EDITABLE)
    return {'version': version, 'overrides': overrides,
            'defaults': {k: getattr(base, k) for k in fields},
            'effective': {k: getattr(apply(base, overrides), k) for k in fields},
            'bounds': {k: {'min': lo, 'max': hi} for k, (lo, hi) in EDITABLE.items()},
            'locked': {'model': base.model, 'max_cost_usd': base.max_cost_usd},
            'history': store.history()}


@router.get('/limits')
async def limits():
    return await run_in_threadpool(lambda: _limits_view(get_settings().admin_ingestion_directory))


@router.put('/limits')
async def update_limits(payload: LimitsUpdate, principal=Depends(access)):
    """Save a new version of the answering limits. Applied from the next question, no restart."""
    from ...documents.limit_overrides import LimitOverrides
    root = get_settings().admin_ingestion_directory

    def save():
        LimitOverrides(root).save(payload.values, str(principal.user_id), payload.reason, payload.expected_version)
        queue().audit(str(principal.user_id), 'LIMITS_CONFIG', 'b1-limits')
        return _limits_view(root)
    return await run_in_threadpool(lambda: operation(save))


class EvaluationRun(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question_ids: list[str] = Field(min_length=1, max_length=40)


@router.get('/evaluation/questions')
async def evaluation_questions():
    from ...documents.evaluation_set import load_golden
    items = await run_in_threadpool(load_golden)
    return {'items': items, 'available': bool(items)}


@router.post('/evaluation/runs', status_code=202)
async def start_evaluation(payload: EvaluationRun, tasks: BackgroundTasks, principal=Depends(access)):
    """Ask the chosen golden questions through the live chat. Each one is a real chat request."""
    from ...documents.evaluation_runner import EvaluationStore, run_evaluation
    from ...documents.evaluation_set import load_golden
    from .research_chat import get_store
    golden = {item['id']: item for item in await run_in_threadpool(load_golden)}
    chosen = list(dict.fromkeys(payload.question_ids))
    if not golden: raise HTTPException(404, detail='EVALUATION_SET_NOT_FOUND')
    if any(qid not in golden for qid in chosen): raise HTTPException(422, detail='EVALUATION_UNKNOWN_QUESTION')
    try:
        engine = get_store().engine
    except Exception:
        raise HTTPException(503, detail='EVALUATION_ENGINE_UNAVAILABLE') from None
    if engine is None: raise HTTPException(503, detail='EVALUATION_ENGINE_UNAVAILABLE')
    store = EvaluationStore(get_settings().admin_ingestion_directory)
    ident = operation(lambda: store.create(str(principal.user_id), len(chosen)))
    queue().audit(str(principal.user_id), 'EVALUATION_RUN', ident)
    tasks.add_task(run_evaluation, store, engine, ident, [golden[qid] for qid in chosen])
    return {'run_id': ident, 'status': 'RUNNING', 'total': len(chosen)}


@router.get('/evaluation/runs')
async def evaluation_runs():
    from ...documents.evaluation_runner import EvaluationStore
    store = EvaluationStore(get_settings().admin_ingestion_directory)
    return {'items': await run_in_threadpool(store.list)}


@router.get('/evaluation/runs/{run_id}')
async def evaluation_run(run_id: uuid.UUID):
    from ...documents.evaluation_runner import EvaluationStore
    run = await run_in_threadpool(lambda: EvaluationStore(get_settings().admin_ingestion_directory).get(str(run_id)))
    if run is None: raise HTTPException(404, detail='EVALUATION_NOT_FOUND')
    return run


@router.post('/evaluation/runs/{run_id}/interrupt')
async def interrupt_evaluation(run_id: uuid.UUID, principal=Depends(access)):
    from ...documents.evaluation_runner import EvaluationStore
    store = EvaluationStore(get_settings().admin_ingestion_directory)
    try:
        await run_in_threadpool(lambda: store.interrupt(str(run_id)))
    except ValueError as exc:
        raise HTTPException(404 if str(exc) == 'EVALUATION_NOT_FOUND' else 409, detail=str(exc)) from None
    return {'run_id': str(run_id), 'status': 'INTERRUPTED'}


@router.post('/pipeline', status_code=202)
async def pipeline(tasks: BackgroundTasks, principal=Depends(access)):
    """Crawl now, then run the stages enabled in the source config (review, DB index, corpus switch)."""
    from ...documents.admin_pipeline import run_full
    settings = get_settings(); q = queue()
    if q.config()['auto_index'] and not settings.admin_ingest_database_url:
        raise HTTPException(503, detail='ADMIN_INGEST_DATABASE_URL_REQUIRED')
    ident, _ = operation(lambda: q.create_job('CRAWL', str(principal.user_id)))
    tasks.add_task(run_full, q, ident, settings)
    return {'job_id': ident, 'status': 'QUEUED'}


@router.get('/jobs')
async def jobs():
    return {'items': await run_in_threadpool(lambda: queue().jobs())}


@router.post('/jobs/{job_id}/interrupt')
async def interrupt(job_id: uuid.UUID, principal=Depends(access)):
    return await run_in_threadpool(lambda: operation(lambda: queue().interrupt(str(job_id), str(principal.user_id))))


@router.get('/articles')
async def articles(status: Literal['PENDING', 'APPROVED', 'REJECTED', 'QUARANTINED', 'INDEXED'] | None = None,
                   offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    def page():
        q = queue()
        return {'items':q.articles(status,offset,limit),'total':q.article_count(status),'offset':offset,'limit':limit}
    return await run_in_threadpool(page)


@router.post('/articles/delete')
async def delete_articles(payload: Deletion, principal=Depends(access)):
    """Delete approved articles in bulk (one id works too). Indexed articles are refused."""
    return await run_in_threadpool(lambda: operation(
        lambda: queue().delete_articles(str(principal.user_id), [str(i) for i in payload.article_ids])))


@router.delete('/articles/{article_id}')
async def delete_article(article_id: uuid.UUID, principal=Depends(access)):
    result = await run_in_threadpool(lambda: operation(
        lambda: queue().delete_articles(str(principal.user_id), [str(article_id)])))
    if result['skipped']:
        reason = result['skipped'][0]['reason']
        raise HTTPException(404 if reason == 'NOT_FOUND' else 409, detail='ARTICLE_' + reason)
    return result


@router.post('/auto-review')
async def auto_review(principal=Depends(access)):
    return await run_in_threadpool(lambda: queue().auto_review(str(principal.user_id)))


@router.post('/auto-review/recheck', status_code=202)
async def recheck_review(tasks: BackgroundTasks, principal=Depends(access)):
    from ...documents.admin_news_ocr import recheck_job
    q = queue()
    ident, _ = operation(lambda: q.create_job('RECHECK', str(principal.user_id)))
    tasks.add_task(recheck_job, q, ident)
    return {'job_id': ident, 'status': 'QUEUED'}


@router.get('/articles/selection')
async def article_selection():
    return await run_in_threadpool(lambda: queue().selection())


@router.get('/articles/{article_id}/chunks')
async def article_chunks(article_id: uuid.UUID, offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=100)):
    from ...core.db import get_pool
    from ...documents.admin_news_index import prepare
    from ...documents.repository import resolve_result_rows
    q = queue(); record = operation(lambda: q.article(str(article_id)))
    versions = q.processed_jobs(str(article_id))
    if record['status'] != 'INDEXED' or not versions:
        raise HTTPException(409, detail='ARTICLE_NOT_INDEXED')
    _, _, _, doc, _ = prepare({**record, 'status':'APPROVED'})
    version_ids = [uuid.UUID(j['id']) for j in versions]
    try:
        async with get_pool().acquire() as conn:
            async with conn.transaction(readonly=True, isolation='repeatable_read'):
                total = await conn.fetchval('''SELECT count(*) FROM public.text_chunks
                    WHERE document_id=$1 AND index_version_id=ANY($2::uuid[]) AND superseded_at IS NULL''', uuid.UUID(doc.document_id), version_ids)
                rows = await conn.fetch('''SELECT t.chunk_id::text,t.document_id::text,t.index_version_id::text,
                    t.chunk_index,t.token_count,t.content_hash,t.locator_json,i.chunker_version
                    FROM public.text_chunks t JOIN public.index_versions i USING(index_version_id)
                    WHERE t.document_id=$1 AND t.index_version_id=ANY($2::uuid[]) AND t.superseded_at IS NULL
                    ORDER BY t.index_version_id,t.chunk_index LIMIT $3 OFFSET $4''',uuid.UUID(doc.document_id),version_ids,limit,offset)
                rebuilt = await resolve_result_rows(conn,rows)
        return {'article_id':str(article_id),'total':total,'offset':offset,'limit':limit,
                'versions':[{'index_version_id':j['id'],'status':j['status'],'corpus_version_id':j['details'].get('corpus_version_id')} for j in versions],
                'items':[{'chunk_id':r['chunk_id'],'index_version_id':r['index_version_id'],
                          'position':r['chunk_index'],'token_count':r['token_count'],
                          'content_hash':r['content_hash'].strip(),'text':r['text']} for r in rebuilt]}
    except Exception:
        raise HTTPException(503, detail='PROCESSED_CHUNKS_UNAVAILABLE') from None


@router.get('/articles/{article_id}')
async def article(article_id: uuid.UUID):
    return await run_in_threadpool(lambda: operation(lambda: queue().article(str(article_id))))


@router.post('/articles/{article_id}/review')
async def review(article_id: uuid.UUID, payload: Review, principal=Depends(access)):
    return await run_in_threadpool(lambda: operation(lambda: _review(str(article_id), payload, str(principal.user_id))))


@router.post('/articles/{article_id}/ocr', status_code=202)
async def extract_source(article_id: uuid.UUID, tasks: BackgroundTasks, principal=Depends(access)):
    from ...documents.admin_news_ocr import ocr_job
    q = queue()
    ident, _ = operation(lambda: q.create_job('OCR', str(principal.user_id), article_ids=[str(article_id)]))
    tasks.add_task(ocr_job, q, ident)
    return {'job_id': ident, 'status': 'QUEUED'}


def _review(ident, payload, actor):
    q = queue(); q.review(ident, payload.decision, payload.note, actor)
    return q.article(ident)


@router.post('/index', status_code=202)
async def index(payload: Selection, tasks: BackgroundTasks, principal=Depends(access)):
    settings = get_settings()
    if not settings.admin_ingest_database_url:
        raise HTTPException(503, detail='ADMIN_INGEST_DATABASE_URL_REQUIRED')
    q = queue()
    ident, _ = operation(lambda: q.create_job('INDEX', str(principal.user_id), article_ids=[str(i) for i in payload.article_ids]))
    tasks.add_task(index_job, q, ident, settings)
    return {'job_id': ident, 'status': 'QUEUED'}


@router.post('/jobs/{job_id}/activate')
async def publish(job_id: uuid.UUID, principal=Depends(access)):
    q = queue()
    try:
        await activate(q, str(job_id), get_settings())
        q.update_job(str(job_id), 'ACTIVE', activated_by=str(principal.user_id))
        return q.get_job(str(job_id))
    except ValueError as exc:
        raise HTTPException(409, detail=str(exc)) from None
    except Exception:
        raise HTTPException(503, detail='INDEX_ACTIVATION_UNAVAILABLE') from None


@router.post('/jobs/{job_id}/retry', status_code=202)
async def retry_index(job_id: uuid.UUID, tasks: BackgroundTasks, principal=Depends(access)):
    q=queue()
    ident=operation(lambda: q.retry_index(str(job_id),str(principal.user_id)))
    tasks.add_task(index_job,q,ident,get_settings())
    return {'job_id':ident,'status':q.get_job(ident)['status']}


@router.post('/jobs/{job_id}/resume',status_code=202)
async def resume_job(job_id: uuid.UUID,tasks: BackgroundTasks,principal=Depends(access)):
    from ...documents.admin_news_ocr import ocr_job,recheck_job
    q=queue();ident=operation(lambda:q.resume_job(str(job_id),str(principal.user_id)))
    kind=q.get_job(ident)['kind']
    if kind=='INDEX':tasks.add_task(index_job,q,ident,get_settings())
    else:tasks.add_task({'CRAWL':crawl_job,'OCR':ocr_job,'RECHECK':recheck_job}[kind],q,ident)
    return {'job_id':ident,'status':q.get_job(ident)['status']}


@router.post('/jobs/{job_id}/search')
async def search(job_id: uuid.UUID, payload: Search):
    from ...core.db import get_pool
    from ...documents.embeddings import get_embedding_service
    from ...vector_retrieval.backend import HybridRetriever
    q = queue(); job = operation(lambda: q.get_job(str(job_id)))
    if job['status'] != 'ACTIVE': raise HTTPException(409, detail='INDEX_NOT_ACTIVE')
    try:
        retriever = HybridRetriever(get_pool(), get_embedding_service(), corpus_version_id=job['details']['corpus_version_id'],max_cache_age=7*24*3600)
        path = (Path(__file__).resolve().parents[2]/'vector_retrieval'/'.cache'/
                ('corpus-'+job['details']['corpus_version_id']+'.json')) if job['details'].get('shared_base_corpus') else q.root / ('search-' + str(job_id) + '.json')
        await retriever.prepare_cache(str(job_id), path)
        result = await retriever.search(payload.question, str(job_id), str(path), doc_type='NEWS', top_k=5)
        return {'corpus_version_id': job['details']['corpus_version_id'],
                'items': [{'chunk_id': r['chunk_id'], 'title': r['title'], 'text': r['text'],
                           'source_url': (r.get('locator') or {}).get('url'), 'content_hash': r['content_hash']}
                          for r in result.get('results', [])]}
    except Exception:
        raise HTTPException(503, detail='NEW_CORPUS_SEARCH_UNAVAILABLE') from None
