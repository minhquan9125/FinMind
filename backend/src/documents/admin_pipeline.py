"""Optional automation after a News crawl: index into the DB, then switch the corpus.

Each stage is opt-in in the admin source config and off by default:

* ``auto_approve``  duplicate of the existing crawl-time source-quality review.
* ``auto_index``    chunk + embed the APPROVED articles and write them to the shared DB.
                    The new index version is left BUILDING/INDEXED, so the serving corpus
                    does not change until someone presses "Chuyen corpus".
* ``auto_activate`` also switch the serving corpus right after the DB write. Requires auto_index.

Articles that still need OCR are never indexed: they stay held for a human check, exactly as
in the manual flow.
"""
from __future__ import annotations

import asyncio

from .admin_ingestion import auto_review_reasons, crawl_job
from .admin_news_index import build, index_job

OCR_HOLDS = {'OCR_REQUIRED', 'ATTACHMENT_TEXT_REQUIRED'}
ACTOR = 'scheduler'


def build_only_job(queue, ident, settings):
    """Chunk, embed and store in the DB without activating (mirrors index_job's error handling)."""
    try:
        asyncio.run(build(queue, ident, settings, publish=False))
    except Exception as exc:
        code = 'ADMIN_INGEST_DATABASE_URL_REQUIRED' if str(exc) == 'ADMIN_INGEST_DATABASE_URL_REQUIRED' else type(exc).__name__
        if queue.get_job(ident)['status'] != 'INTERRUPTED':
            queue.update_job(ident, 'FAILED', error=code)


def _indexable(queue, ids):
    keep = []
    for ident in ids:
        record = queue.article(ident)
        if not OCR_HOLDS & set(auto_review_reasons(record['payload'])):
            keep.append(ident)
    return keep


def follow_up(queue, crawl_ident, settings, *, index_fn=index_job, build_fn=build_only_job):
    """Run the stages after a finished crawl according to the saved config. Never raises."""
    summary = {'crawl_job_id': crawl_ident, 'stage': 'CRAWL'}
    try:
        cfg = queue.config()
        if queue.get_job(crawl_ident)['status'] not in ('COMPLETED', 'PARTIAL'):
            summary['skipped'] = 'CRAWL_NOT_COMPLETED'
        elif not cfg['auto_index']:
            summary['skipped'] = 'AUTO_INDEX_OFF'
        elif not getattr(settings, 'admin_ingest_database_url', None):
            summary['skipped'] = 'ADMIN_INGEST_DATABASE_URL_REQUIRED'
        else:
            ids = _indexable(queue, queue.selection()['approved_ids'])
            if not ids:
                summary['skipped'] = 'NO_APPROVED_ARTICLES'
            else:
                ident, _ = queue.create_job('INDEX', ACTOR, article_ids=ids)
                summary.update(stage='INDEX', index_job_id=ident, articles=len(ids),
                               auto_activate=bool(cfg['auto_activate']))
                (index_fn if cfg['auto_activate'] else build_fn)(queue, ident, settings)
                summary['index_status'] = queue.get_job(ident)['status']
    except ValueError as exc:  # e.g. ANOTHER_JOB_IS_RUNNING: leave everything as it was
        summary['skipped'] = str(exc)
    except Exception as exc:
        summary['error'] = type(exc).__name__
    _record(queue, crawl_ident, summary)
    return summary


def _record(queue, crawl_ident, summary):
    try:
        job = queue.get_job(crawl_ident)
        queue.update_job(crawl_ident, job['status'], pipeline=summary)
        queue.audit(ACTOR, 'AUTO_PIPELINE', crawl_ident)
    except Exception:
        pass  # Reporting must never undo or mask a finished stage.


def run_full(queue, crawl_ident, settings, *, collector=None, **hooks):
    """Crawl (job already created), then continue with the configured stages."""
    crawl_job(queue, crawl_ident, collector)
    return follow_up(queue, crawl_ident, settings, **hooks)
