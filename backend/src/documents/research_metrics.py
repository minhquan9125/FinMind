"""Durable local LIVE web-chat statistics, independently recorded for each request."""
import json
import logging
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from contextlib import contextmanager

from starlette.concurrency import run_in_threadpool

from ..core.usage_tracking import generation_calls

VN = timezone(timedelta(hours=7))


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def outcome(result):
    answer = result.get('answering') or {}
    status = answer.get('status') if answer.get('status') != 'SKIPPED' else result.get('status')
    status = status or result.get('status')
    if status == 'DRAFT_READY': return 'SUCCESS'
    if status in {'NO_DATA', 'INSUFFICIENT_EVIDENCE'}: return 'INSUFFICIENT_EVIDENCE'
    if status in {'SYSTEM_UNAVAILABLE', 'BUDGET_EXCEEDED'}: return 'ERROR'
    if status in {'ASK_CLARIFICATION', 'CLARIFY', 'CLARIFICATION_REQUIRED'}: return 'CLARIFICATION'
    return 'OTHER'


class ResearchMetrics:
    def __init__(self, root):
        self.path = Path(root) / 'research-metrics.sqlite'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript('''CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS requests(
                    id TEXT PRIMARY KEY,created_at TEXT NOT NULL,duration_ms INTEGER NOT NULL,
                    outcome TEXT NOT NULL,companies TEXT NOT NULL,response_mode TEXT,
                    calls TEXT NOT NULL,known_input INTEGER NOT NULL,known_output INTEGER NOT NULL,
                    known_total INTEGER NOT NULL,unknown_calls INTEGER NOT NULL);
                CREATE INDEX IF NOT EXISTS requests_created_at_idx ON requests(created_at);''')
            conn.execute("INSERT OR IGNORE INTO metadata VALUES('tracking_started_at',?)", (utc_now(),))
            if 'details' not in {r[1] for r in conn.execute('PRAGMA table_info(requests)')}:
                conn.execute("ALTER TABLE requests ADD COLUMN details TEXT NOT NULL DEFAULT '{}'")

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def record(self, ident, created_at, duration_ms, result, calls, *, failed=False, question=None):
        answer = result.get('answering') or {}
        # User question and source identifiers only: never the model prompt,
        # retrieved source text, generated answer, keys or raw exceptions.
        totals = [sum(c['usage'][k] for c in calls if c.get('usage') is not None)
                  for k in ('input_tokens', 'output_tokens', 'total_tokens')]
        unknown = sum(c.get('usage') is None for c in calls)
        with self.connect() as conn:
            pack=result.get('evidence_pack') or {}
            sources=[]
            from urllib.parse import urlsplit
            for cite in (answer.get('citations') or [])[:100]:
                url=cite.get('source_url') or (cite.get('locator') or {}).get('url')
                try:
                    parsed=urlsplit(url or '')
                    if parsed.scheme!='https' or parsed.username or parsed.password:url=None
                except ValueError:url=None
                sources.append({**{k:cite.get(k) for k in ('source_id','chunk_id','source_type','title')},'url':url})
            details={'question':question[:4000] if isinstance(question,str) else None,
                'reason_code':answer.get('reason_code') or result.get('reason_code'),
                'answer_status':answer.get('status'),'retrieval_backend':result.get('retrieval_backend'),
                'policy_version':(answer.get('manifest') or {}).get('config_version'),
                'corpus_version_id':pack.get('corpus_version_id') or (result.get('scope') or {}).get('_admin_news_corpus'),
                'evidence_count':len(pack.get('items') or []),'sources':sources,
                'timings':{k:v for k,v in (result.get('timings') or {}).items() if k in ('retrieval_seconds','answer_seconds','total_seconds') and type(v) in (int,float)},
                'components':{k:v for k,v in (answer.get('manifest') or {}).get('components',{}).items() if type(v) is bool}}
            conn.execute('INSERT OR IGNORE INTO requests(id,created_at,duration_ms,outcome,companies,response_mode,calls,known_input,known_output,known_total,unknown_calls,details) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                (ident, created_at, duration_ms, 'ERROR' if failed else outcome(result),
                 json.dumps((result.get('scope') or {}).get('companies', [])),
                 (answer.get('manifest') or {}).get('response_mode') or answer.get('reason_code'),
                 json.dumps(calls), *totals, unknown,json.dumps(details)))

    def summary(self, at=None):
        at = (at or datetime.now(timezone.utc)).astimezone(VN)
        start = at.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
        end = start + timedelta(days=1)
        with self.connect() as conn:
            counts = {r[0]: r[1] for r in conn.execute('''SELECT outcome,count(*) FROM requests
                WHERE created_at>=? AND created_at<? GROUP BY outcome''', (start.isoformat(), end.isoformat()))}
            usage = conn.execute('''SELECT coalesce(sum(known_input),0),coalesce(sum(known_output),0),
                coalesce(sum(known_total),0),coalesce(sum(unknown_calls),0) FROM requests
                WHERE created_at>=? AND created_at<?''', (start.isoformat(), end.isoformat())).fetchone()
            tracking = conn.execute("SELECT value FROM metadata WHERE key='tracking_started_at'").fetchone()[0]
            models = [dict(r) for r in conn.execute('''SELECT json_extract(j.value,'$.model') AS model,
                count(*) AS calls,
                sum(CASE WHEN json_extract(j.value,'$.usage') IS NULL THEN 1 ELSE 0 END) AS unknown_calls,
                coalesce(sum(json_extract(j.value,'$.usage.input_tokens')),0) AS input_tokens,
                coalesce(sum(json_extract(j.value,'$.usage.output_tokens')),0) AS output_tokens,
                coalesce(sum(json_extract(j.value,'$.usage.total_tokens')),0) AS total_tokens
                FROM requests r,json_each(r.calls) j WHERE created_at>=? AND created_at<?
                GROUP BY json_extract(j.value,'$.model') ORDER BY model''', (start.isoformat(),end.isoformat()))]
        return {'status':'available','date':at.date().isoformat(),'timezone':'Asia/Ho_Chi_Minh',
                'tracking_started_at':tracking,'total':sum(counts.values()),'outcomes':counts,
                'input_tokens':usage[0],'output_tokens':usage[1],'total_tokens':usage[2],
                'unknown_calls':usage[3], 'models':models, 'scope':'LIVE_WEB_CHAT_GEMINI_GENERATION',
                'recent':self.list(limit=5)['items']}

    def list(self, offset=0, limit=30, *, outcome_filter=None, company=None, day=None):
        where=[];args=[]
        if outcome_filter:where.append('outcome=?');args.append(outcome_filter)
        if company:where.append('EXISTS(SELECT 1 FROM json_each(requests.companies) WHERE value=?)');args.append(company)
        if day:
            start=datetime.fromisoformat(day).replace(tzinfo=VN).astimezone(timezone.utc)
            where.extend(['created_at>=?','created_at<?']);args.extend([start.isoformat(),(start+timedelta(days=1)).isoformat()])
        clause=' WHERE '+' AND '.join(where) if where else ''
        with self.connect() as conn:
            total = conn.execute('SELECT count(*) FROM requests'+clause,args).fetchone()[0]
            rows = conn.execute('SELECT * FROM requests'+clause+' ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?',
                                (*args,limit, offset)).fetchall()
        return {'total':total,'offset':offset,'limit':limit,
                'items':[self.decode(r) for r in rows]}

    @staticmethod
    def decode(row):
        return {**dict(row),'companies':json.loads(row['companies']),'calls':json.loads(row['calls']),'details':json.loads(row['details'])}

    def detail(self,ident):
        with self.connect() as conn:row=conn.execute('SELECT * FROM requests WHERE id=?',(ident,)).fetchone()
        return self.decode(row) if row else None


class ObservedResearch:
    def __init__(self, engine, metrics):
        self.engine, self.metrics = engine, metrics

    def __getattr__(self, key):
        return getattr(self.engine, key)

    async def answer(self, *args, **kwargs):
        calls = []
        token = generation_calls.set(calls)
        ident, created, started = str(uuid.uuid4()), utc_now(), time.perf_counter()
        result, failed = {}, True
        try:
            result = await self.engine.answer(*args, **kwargs)
            failed = False
            return result
        finally:
            generation_calls.reset(token)
            elapsed = round((time.perf_counter() - started) * 1000)
            try:
                await run_in_threadpool(lambda: self.metrics.record(ident, created, elapsed, result, calls, failed=failed,
                    question=args[0] if args else kwargs.get('question')))
            except Exception:
                logging.getLogger(__name__).warning('research_metrics_write_failed')
