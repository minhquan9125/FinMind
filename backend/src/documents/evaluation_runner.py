"""Run the golden questions through the live chat and keep the scored results.

One run at a time. Each question uses a fresh chat session, counts as a real chat request
(tokens, traces) and is scored by evaluation_scoring, which is a reviewer's aid, not a verdict.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone

from .evaluation_scoring import score_answer
from .research_metrics import ResearchMetrics

STALE_SECONDS = 900          # a RUNNING run with no progress for this long is treated as interrupted
QUESTION_TIMEOUT = 150.0
MAX_QUESTIONS = 40
REFUSAL_STATUSES = {'NO_DATA', 'INSUFFICIENT_EVIDENCE', 'UNSUPPORTED', 'ASK_CLARIFICATION', 'CLARIFICATION_STALLED'}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _age(iso):
    return (datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds()


class EvaluationStore:
    def __init__(self, root):
        self.metrics = ResearchMetrics(root)
        with self.metrics.connect() as conn:
            conn.executescript('''CREATE TABLE IF NOT EXISTS eval_runs(
                id TEXT PRIMARY KEY,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,actor TEXT NOT NULL,
                status TEXT NOT NULL,total INTEGER NOT NULL,done INTEGER NOT NULL DEFAULT 0,summary TEXT NOT NULL DEFAULT '{}');
                CREATE TABLE IF NOT EXISTS eval_results(
                id INTEGER PRIMARY KEY AUTOINCREMENT,run_id TEXT NOT NULL,position INTEGER NOT NULL,qid TEXT NOT NULL,
                data TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS eval_results_run_idx ON eval_results(run_id,position);''')

    # -- runs ------------------------------------------------------------------------------
    def _effective(self, row):
        run = dict(row)
        run['summary'] = json.loads(run['summary'])
        if run['status'] == 'RUNNING' and _age(run['updated_at']) > STALE_SECONDS:
            run['status'] = 'INTERRUPTED'
        return run

    def active(self):
        with self.metrics.connect() as conn:
            rows = conn.execute("SELECT * FROM eval_runs WHERE status='RUNNING'").fetchall()
        return next((r for r in map(self._effective, rows) if r['status'] == 'RUNNING'), None)

    def create(self, actor, total):
        if self.active():
            raise ValueError('EVALUATION_ALREADY_RUNNING')
        ident = str(uuid.uuid4())
        with self.metrics.connect() as conn:
            conn.execute('INSERT INTO eval_runs(id,created_at,updated_at,actor,status,total) VALUES(?,?,?,?,?,?)',
                         (ident, _now(), _now(), actor, 'RUNNING', total))
        return ident

    def update(self, ident, **fields):
        allowed = {'status', 'done', 'summary'}
        assert set(fields) <= allowed
        values = {k: (json.dumps(v) if k == 'summary' else v) for k, v in fields.items()}
        with self.metrics.connect() as conn:
            conn.execute('UPDATE eval_runs SET updated_at=?,' + ','.join(f'{k}=?' for k in values) + ' WHERE id=?',
                         (_now(), *values.values(), ident))

    def status(self, ident):
        with self.metrics.connect() as conn:
            row = conn.execute('SELECT * FROM eval_runs WHERE id=?', (ident,)).fetchone()
        return self._effective(row)['status'] if row else None

    def interrupt(self, ident):
        with self.metrics.connect() as conn:
            row = conn.execute('SELECT status FROM eval_runs WHERE id=?', (ident,)).fetchone()
            if not row: raise ValueError('EVALUATION_NOT_FOUND')
            if row['status'] != 'RUNNING': raise ValueError('EVALUATION_NOT_RUNNING')
            conn.execute("UPDATE eval_runs SET status='INTERRUPTED',updated_at=? WHERE id=?", (_now(), ident))

    def add_result(self, ident, position, qid, data):
        with self.metrics.connect() as conn:
            conn.execute('INSERT INTO eval_results(run_id,position,qid,data) VALUES(?,?,?,?)',
                         (ident, position, qid, json.dumps(data, ensure_ascii=False)))

    def list(self, limit=20):
        with self.metrics.connect() as conn:
            rows = conn.execute('SELECT * FROM eval_runs ORDER BY created_at DESC LIMIT ?', (limit,)).fetchall()
        return [self._effective(r) for r in rows]

    def get(self, ident):
        with self.metrics.connect() as conn:
            row = conn.execute('SELECT * FROM eval_runs WHERE id=?', (ident,)).fetchone()
            results = conn.execute('SELECT qid,data FROM eval_results WHERE run_id=? ORDER BY position', (ident,)).fetchall()
        if not row: return None
        return {**self._effective(row), 'results': [{'qid': r['qid'], **json.loads(r['data'])} for r in results]}


def summarize(results):
    """Counts by level, mean score of the scored ones, latency and how many answers had sources."""
    levels = {}
    for r in results: levels[r['level']] = levels.get(r['level'], 0) + 1
    scored = [r['score'] for r in results if r.get('score') is not None]
    latencies = [r['latency_ms'] for r in results if r.get('latency_ms') is not None]
    return {'total': len(results), 'levels': levels,
            'mean_score': round(sum(scored) / len(scored), 3) if scored else None,
            'mean_latency_ms': round(sum(latencies) / len(latencies)) if latencies else None,
            'with_sources': sum(1 for r in results if r.get('citations')),
            'verified_questions': sum(1 for r in results if r.get('verified'))}


def _answer_text(result):
    answer = result.get('answering') or {}
    return answer.get('draft') or result.get('message') or ''


async def run_evaluation(store, engine, ident, items, *, timeout=QUESTION_TIMEOUT):
    """Ask each question in turn. Never raises: a failing question is recorded and the run goes on."""
    collected = []
    final = 'COMPLETED'
    try:
        for position, item in enumerate(items, 1):
            if store.status(ident) != 'RUNNING':
                final = 'INTERRUPTED'
                break
            started = time.perf_counter()
            row = {'question': item['question'], 'expected': item['expected'], 'category': item.get('category'),
                   'verified': bool(item.get('verified'))}
            try:
                result = await asyncio.wait_for(engine.answer(item['question'], f"eval-{ident[:8]}-{item['id']}"), timeout)
                answering = result.get('answering') or {}
                status = answering.get('status') if answering.get('status') not in (None, 'SKIPPED') else result.get('status')
                text = _answer_text(result)
                refused = status in REFUSAL_STATUSES
                row.update(answer=text, status=status, reason_code=answering.get('reason_code') or result.get('reason_code'),
                           route=(result.get('hybrid_router') or {}).get('route'),
                           citations=len(answering.get('citations') or []), error=None,
                           **score_answer(item['expected'], text, refused=refused))
            except asyncio.TimeoutError:
                row.update(answer='', status='TIMEOUT', reason_code=None, route=None, citations=0, error='TIMEOUT',
                           **{'score': 0.0, 'level': 'ERROR', 'matched': 0, 'total': 0, 'facts': []})
            except Exception as exc:
                row.update(answer='', status='ERROR', reason_code=None, route=None, citations=0, error=type(exc).__name__,
                           **{'score': 0.0, 'level': 'ERROR', 'matched': 0, 'total': 0, 'facts': []})
            row['latency_ms'] = round((time.perf_counter() - started) * 1000)
            collected.append(row)
            store.add_result(ident, position, item['id'], row)
            store.update(ident, done=position)
    except Exception:
        final = 'FAILED'
    finally:
        try:
            current = store.status(ident)
            store.update(ident, status=current if current == 'INTERRUPTED' else final, summary=summarize(collected))
        except Exception:
            pass
    return collected
