"""Read-only, authenticated WBS16 report browser. Does not start or approve jobs."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, StrictInt, ValidationError, model_validator
from starlette.concurrency import run_in_threadpool

from ...auth.authorization import require_roles
from ...core.config import get_settings

router = APIRouter(prefix='/api/v1/admin/jobs', tags=['admin-jobs'],
                  dependencies=[Depends(require_roles('ADMINISTRATOR'))])
STATUSES = ('PENDING_REVIEW', 'QUARANTINED', 'NO_CANDIDATE', 'ERROR', 'MISSING_SOURCE', 'UNPROCESSED')
JOB_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}')
MAX_REPORT_BYTES = 10 * 1024 * 1024


class Issue(BaseModel):
    article_id: str = Field(min_length=1, max_length=200)
    status: Literal['PENDING_REVIEW', 'QUARANTINED', 'ERROR', 'MISSING_SOURCE', 'UNPROCESSED']
    reason: str | None = None


class Report(BaseModel):
    schema_version: Literal['wbs16-staging-v1']
    mode: Literal['fixture', 'full']
    pins: dict
    total_manifest_news: StrictInt = Field(ge=0)
    counts: dict[str, StrictInt]
    staging_complete: bool
    acceptance_status: Literal['NOT_EVALUATED']
    database_reconciliation: dict
    unresolved: list[Issue]

    @model_validator(mode='after')
    def reconcile_counts(self):
        if (set(self.counts) != set(STATUSES) or any(n < 0 for n in self.counts.values())
                or sum(self.counts.values()) != self.total_manifest_news
                or len(self.unresolved) != self.total_manifest_news - self.counts['NO_CANDIDATE']
                or len({i.article_id for i in self.unresolved}) != len(self.unresolved)
                or any(sum(i.status == status for i in self.unresolved) != self.counts[status]
                       for status in STATUSES if status != 'NO_CANDIDATE')
                or self.staging_complete != (not any(self.counts[s] for s in ('ERROR', 'MISSING_SOURCE', 'UNPROCESSED')))
                or self.database_reconciliation.get('status') not in {'PASS', 'FAIL', 'NOT_READY'}
                or not isinstance(self.pins.get('corpus_version_id'), str)
                or not re.fullmatch('[a-f0-9]{64}', self.pins.get('manifest_sha256', ''))):
            raise ValueError('Invalid report accounting')
        return self


def reports_root():
    return Path(get_settings().admin_jobs_directory).resolve()


def load_report(root, job_id):
    if not JOB_ID.fullmatch(job_id):
        raise HTTPException(404, detail='Không tìm thấy job.')
    directory = root / job_id
    path = directory / 'report.json'
    # Never follow junctions/symlinks to reports outside the configured directory.
    if (directory.is_symlink() or directory.resolve() != directory
            or path.resolve().parent != directory):
        raise HTTPException(404, detail='Không tìm thấy job.')
    try:
        with path.open('rb') as stream:
            raw = stream.read(MAX_REPORT_BYTES + 1)
        if len(raw) > MAX_REPORT_BYTES:
            raise ValueError('Report too large')
        report = Report.model_validate(json.loads(raw))
        updated = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
    except FileNotFoundError:
        raise HTTPException(404, detail='Không tìm thấy báo cáo job.') from None
    except (OSError, ValueError, TypeError, ValidationError):
        raise HTTPException(409, detail='Báo cáo job chưa hợp lệ hoặc chưa đọc được.') from None
    return report, updated


def summary(job_id, report, updated):
    return {'job_id': job_id, 'status': 'STAGED' if report.staging_complete
            and report.database_reconciliation['status'] != 'FAIL' else 'ATTENTION',
            'mode': report.mode, 'reported_at': updated, 'total_articles': report.total_manifest_news,
            'counts': report.counts, 'corpus_version_id': report.pins['corpus_version_id'],
            'manifest_sha256': report.pins['manifest_sha256'],
            'database_reconciliation': report.database_reconciliation['status'],
            'acceptance_status': report.acceptance_status}


def list_reports(offset, limit):
    root = reports_root()
    if not root.exists():
        return {'items': [], 'total': 0, 'offset': offset, 'limit': limit}
    try:
        # Reports are snapshots. Sorting is deterministic; no claim of live progress.
        directories = sorted(p for p in root.iterdir() if JOB_ID.fullmatch(p.name) and p.is_dir())
        items = []
        for path in directories:
            try:
                report, updated = load_report(root, path.name)
                items.append(summary(path.name, report, updated))
            except HTTPException as exc:
                if exc.status_code == 404:
                    continue
                items.append({'job_id': path.name, 'status': 'INVALID_REPORT'})
        return {'items': items[offset:offset + limit], 'total': len(items), 'offset': offset, 'limit': limit}
    except OSError:
        raise HTTPException(503, detail='Chưa đọc được kho báo cáo job.') from None


@router.get('')
async def jobs(offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    return await run_in_threadpool(list_reports, offset, limit)


@router.get('/{job_id}')
async def job(job_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    def detail():
        report, updated = load_report(reports_root(), job_id)
        issues = [{'article_id': i.article_id, 'status': i.status,
                   'reason': i.reason if i.reason and re.fullmatch('[A-Z0-9_]{1,100}', i.reason) else None}
                  for i in report.unresolved[offset:offset + limit]]
        return {**summary(job_id, report, updated), 'items': issues,
                'total_issues': len(report.unresolved), 'offset': offset, 'limit': limit}
    return await run_in_threadpool(detail)
