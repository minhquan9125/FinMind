"""Authenticated WBS16 report browser, plus a fixture-only launcher. Never approves candidates."""
import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError, model_validator
from starlette.concurrency import run_in_threadpool

from ...auth.authorization import require_roles
from ...core.config import get_settings

access = require_roles('ADMINISTRATOR')
router = APIRouter(prefix='/api/v1/admin/jobs', tags=['admin-jobs'], dependencies=[Depends(access)])
STATUSES = ('PENDING_REVIEW', 'QUARANTINED', 'NO_CANDIDATE', 'ERROR', 'MISSING_SOURCE', 'UNPROCESSED')
JOB_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}')
MAX_REPORT_BYTES = 10 * 1024 * 1024
LAUNCH_FILE = 'launch.json'
MAX_INPUT_BYTES = 8 * 1024 * 1024
LAUNCH_STALE_SECONDS = 1800


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
                launch = read_launch(path)
                if exc.status_code == 404 and launch is None:
                    continue
                items.append(launch_item(path.name, launch) if launch and exc.status_code == 404
                             else {'job_id': path.name, 'status': 'INVALID_REPORT'})
        return {'items': items[offset:offset + limit], 'total': len(items), 'offset': offset, 'limit': limit}
    except OSError:
        raise HTTPException(503, detail='Chưa đọc được kho báo cáo job.') from None


def _write_launch(directory, state):
    temp = directory / (LAUNCH_FILE + '.tmp')
    temp.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
    temp.replace(directory / LAUNCH_FILE)


def read_launch(directory):
    """State written by the launcher; None for runner-made directories. A silent stale run shows as failed."""
    path = directory / LAUNCH_FILE
    try:
        if directory.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
            return None
        state = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(state, dict) or state.get('status') not in ('RUNNING', 'COMPLETED', 'FAILED'):
            return None
    except (OSError, ValueError):
        return None
    if state['status'] == 'RUNNING':
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(state['updated_at'])).total_seconds()
        if age > LAUNCH_STALE_SECONDS:
            return {**state, 'status': 'FAILED', 'reason': 'WORKER_STOPPED'}
    return state


def launch_item(job_id, state):
    status = {'RUNNING': 'RUNNING', 'FAILED': 'LAUNCH_FAILED', 'COMPLETED': 'INVALID_REPORT'}[state['status']]
    reason = state.get('reason') if isinstance(state.get('reason'), str) and re.fullmatch('[A-Z0-9_]{1,100}', state['reason']) else None
    return {'job_id': job_id, 'status': status, 'mode': 'fixture', 'reported_at': state.get('updated_at'), 'reason': reason}


class LaunchRequest(BaseModel):
    """Inputs of a fixture staging run. Paths are never accepted: the server chooses the directory."""
    model_config = ConfigDict(extra='forbid')
    manifest: dict
    articles: list[dict] = Field(max_length=5000)


def _running_launch(root):
    if not root.exists():
        return None
    for path in root.iterdir():
        state = read_launch(path) if path.is_dir() and JOB_ID.fullmatch(path.name) else None
        if state and state['status'] == 'RUNNING':
            return path.name
    return None


def _execute_launch(directory, manifest, articles):
    from ...documents.news_batch_runner import run
    state = {'mode': 'fixture', 'started_at': datetime.now(timezone.utc).isoformat()}
    try:
        run(manifest, articles, directory, mode='fixture')
        outcome = {'status': 'COMPLETED'}
    except (ValueError, KeyError, TypeError, OSError) as exc:
        reason = str(exc) if re.fullmatch('[A-Z0-9_]{1,100}', str(exc)) else 'INPUT_VALIDATION_OR_IO_FAILED'
        outcome = {'status': 'FAILED', 'reason': reason}
    except Exception:
        outcome = {'status': 'FAILED', 'reason': 'UNEXPECTED_ERROR'}
    _write_launch(directory, {**state, **outcome, 'updated_at': datetime.now(timezone.utc).isoformat()})


@router.post('/runs', status_code=202)
async def launch_run(payload: LaunchRequest, tasks: BackgroundTasks, principal=Depends(access)):
    """Start a fixture staging run (no DB writes, no review decisions). Full runs stay command-line only."""
    if len(json.dumps(payload.model_dump(), ensure_ascii=False).encode('utf-8')) > MAX_INPUT_BYTES:
        raise HTTPException(413, detail='JOB_INPUT_TOO_LARGE')
    root = reports_root()
    busy = await run_in_threadpool(_running_launch, root)
    if busy:
        raise HTTPException(409, detail='JOB_ALREADY_RUNNING')
    job_id = f"web-fixture-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"
    directory = root / job_id
    directory.mkdir(parents=True, exist_ok=False)
    now = datetime.now(timezone.utc).isoformat()
    _write_launch(directory, {'status': 'RUNNING', 'mode': 'fixture', 'actor': str(principal.user_id),
                              'started_at': now, 'updated_at': now})
    tasks.add_task(run_in_threadpool, _execute_launch, directory, payload.manifest, payload.articles)
    return {'job_id': job_id, 'status': 'RUNNING', 'mode': 'fixture'}


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
