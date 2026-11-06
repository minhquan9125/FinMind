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
