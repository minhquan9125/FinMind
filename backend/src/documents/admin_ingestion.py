"""Durable local admin queue: immutable snapshots, review, then draft indexing.

SQLite is the single-machine control plane. PostgreSQL receives approved source
snapshots and vectors only. Neither collecting nor reviewing changes live corpora.
"""
import hashlib
import json
import sqlite3
import uuid
import re
import unicodedata
from urllib.parse import urlparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

TZ = timezone(timedelta(hours=7))
DEFAULT = {'enabled': False, 'hour': 7, 'limit': 100, 'provider': 'fireant',
           'symbols': ['VCB','BID','CTG','MBB','TCB','FPT','CMG','ELC','ITD','ICT'],
           'max_pages': 5, 'include_market': True, 'auto_approve': False}


def source_attachments(payload):
    raw = payload.get('raw') or {}
    files = raw.get('files') or [] if isinstance(raw, dict) else []
    result = []
    for item in files:
        if not isinstance(item, dict): continue
        url = item.get('fileContentUrl') or ''
        parsed = urlparse(url)
        if parsed.scheme == 'https' and parsed.hostname in {'fireant.vn','mobiv2.fireant.vn'}:
            result.append({'name':item.get('fileName') or 'Tệp đính kèm','url':url})
    return result


def auto_review_reasons(payload):
    """Source-quality checks only; never asserts that financial claims are true."""
    reasons = []
    if (payload.get('extraction') or {}).get('requires_review'):
        reasons.append('OCR_REVIEW_REQUIRED')
    url = urlparse(payload.get('url') or '')
    raw = payload.get('raw') or {}
    if (payload.get('source') != 'fireant' or url.scheme != 'https' or url.hostname != 'fireant.vn'
            or not isinstance(raw, dict) or raw.get('type') != 1
            or not re.fullmatch(r'/bai-viet/[^/]+/\d+', url.path)
            or not raw.get('postID') or url.path.split('/')[-1] != str(raw.get('postID'))):
        reasons.append('UNCONFIRMED_PROVIDER_SOURCE')
    if len((payload.get('title') or '').strip()) < 6: reasons.append('SHORT_TITLE')
    body = (payload.get('content') or '').strip()
    folded = ''.join(c for c in unicodedata.normalize('NFD',body.lower().replace('đ','d')) if unicodedata.category(c) != 'Mn')
    attachments = source_attachments(payload)
    raw_html = str(raw.get('content') or raw.get('originalContent') or '') if isinstance(raw, dict) else ''
    if '<img' in raw_html.lower() and not payload.get('extraction'):
        reasons.append('OCR_REQUIRED')
    elif attachments and (len(body) < 80 or (len(body) < 300 and re.search(r'nhu sau\s*[:.]?$|(?:xem|chi tiet).*(?:dinh kem|file|tai lieu)', folded))):
        reasons.append('ATTACHMENT_TEXT_REQUIRED')
    elif len(body) < 80 or len(body.split()) < 10:
        reasons.append('SHORT_OR_EMPTY_BODY')
    try:
        published = datetime.fromisoformat(payload['published_at'].replace('Z', '+00:00'))
        if not published.tzinfo or published > datetime.now(timezone.utc) + timedelta(days=1):
            reasons.append('UNCONFIRMED_PUBLICATION_DATE')
    except (KeyError, ValueError, TypeError, AttributeError): reasons.append('UNCONFIRMED_PUBLICATION_DATE')
    return reasons


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def sha(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


class Queue:
    def __init__(self, root):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / 'control.sqlite'
        with self.connect() as c:
            c.executescript('''
              CREATE TABLE IF NOT EXISTS config(id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, kind TEXT, status TEXT, actor TEXT,
                created_at TEXT, updated_at TEXT, daily_key TEXT UNIQUE, details TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS articles(id TEXT PRIMARY KEY, job_id TEXT, digest TEXT UNIQUE,
                payload TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY AUTOINCREMENT, article_id TEXT,
                actor TEXT NOT NULL, decision TEXT NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS job_articles(job_id TEXT, article_id TEXT, PRIMARY KEY(job_id,article_id));
              CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,actor TEXT,action TEXT,resource TEXT,at TEXT);
              CREATE TABLE IF NOT EXISTS serving_corpus(id INTEGER PRIMARY KEY CHECK(id=1),corpus_id TEXT NOT NULL,index_id TEXT NOT NULL);
              CREATE TRIGGER IF NOT EXISTS classify_legacy_ocr_replacement
              AFTER INSERT ON reviews
              WHEN NEW.decision='REJECTED'
                AND NEW.note LIKE 'Đã thay bằng bản trích xuất cần duyệt: %'
                AND EXISTS(SELECT 1 FROM articles child
                  WHERE json_extract(child.payload,'$.extraction.parent_article_id')=NEW.article_id
                    AND NEW.note='Đã thay bằng bản trích xuất cần duyệt: ' || child.id)
              BEGIN
                UPDATE articles SET status='SUPERSEDED' WHERE id=NEW.article_id AND status='REJECTED';
                UPDATE reviews SET decision='SUPERSEDED' WHERE id=NEW.id;
              END;
            ''')
            c.execute('INSERT OR IGNORE INTO config VALUES(1,?)', (canonical(DEFAULT),))
            # Correct only legacy OCR replacements, never a human rejection.
            old = c.execute("""SELECT a.id,child.id AS replacement_id FROM articles a
                JOIN reviews r ON r.id=(SELECT max(id) FROM reviews WHERE article_id=a.id)
                JOIN articles child ON json_extract(child.payload,'$.extraction.parent_article_id')=a.id
                WHERE a.status='REJECTED' AND r.decision='REJECTED'
                  AND r.note='Đã thay bằng bản trích xuất cần duyệt: ' || child.id""").fetchall()
            for row in old:
                c.execute("UPDATE articles SET status='SUPERSEDED' WHERE id=?", (row['id'],))
                c.execute('INSERT INTO reviews(article_id,actor,decision,note,created_at) VALUES(?,?,?,?,?)',
                          (row['id'], 'system:ocr-status-correction', 'SUPERSEDED',
                           'Đã thay bằng bản trích xuất cần duyệt: ' + row['replacement_id'], now()))

    @contextmanager
    def connect(self):
        c = sqlite3.connect(self.path, timeout=20)
        c.row_factory = sqlite3.Row
        try:
            c.execute('BEGIN IMMEDIATE')
            yield c
            c.commit()
        except BaseException:
            c.rollback(); raise
        finally: c.close()

    def config(self, value=None):
        with self.connect() as c:
            if value is not None:
                c.execute('UPDATE config SET value=? WHERE id=1', (canonical(value),))
            return {**DEFAULT, **json.loads(c.execute('SELECT value FROM config WHERE id=1').fetchone()[0])}

    def serving_corpus(self, default):
        with self.connect() as c:
            row = c.execute('SELECT corpus_id FROM serving_corpus WHERE id=1').fetchone()
            return row[0] if row else default

    def publish_corpus(self, corpus_id, index_id):
        with self.connect() as c:
            c.execute('INSERT INTO serving_corpus VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET corpus_id=excluded.corpus_id,index_id=excluded.index_id',
                      (str(uuid.UUID(corpus_id)), str(uuid.UUID(index_id))))

    def finish_index(self, ident, details, *, corpus_id=None, default_corpus=None, expected_base=None):
        """Publish the serving pointer, job completion and article states together."""
        with self.connect() as c:
            row=c.execute('SELECT status,details FROM jobs WHERE id=?',(ident,)).fetchone()
            if not row or row['status']=='INTERRUPTED': raise ValueError('JOB_INTERRUPTED')
            data=json.loads(row['details']);data.update(details)
            if corpus_id:
                current=c.execute('SELECT corpus_id FROM serving_corpus WHERE id=1').fetchone()
                current=current[0] if current else default_corpus
                if current not in (expected_base,corpus_id): raise ValueError('SHARED_BASE_CHANGED_REBUILD_REQUIRED')
                c.execute('INSERT INTO serving_corpus VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET corpus_id=excluded.corpus_id,index_id=excluded.index_id',
                          (str(uuid.UUID(corpus_id)),str(uuid.UUID(ident))))
            c.execute("UPDATE jobs SET status='ACTIVE',updated_at=?,details=? WHERE id=?",(now(),canonical(data),ident))
            for aid in data.get('article_ids',[]):
                c.execute("UPDATE articles SET status='INDEXED' WHERE id=? AND status='APPROVED'",(aid,))

    def retry_index(self, ident, actor):
        with self.connect() as c:
            row=c.execute('SELECT kind,status,details FROM jobs WHERE id=?',(ident,)).fetchone()
            if not row or row['kind']!='INDEX' or row['status'] not in ('FAILED','INDEXED'):
                raise ValueError('INDEX_RETRY_NOT_AVAILABLE')
            if c.execute("SELECT 1 FROM jobs WHERE status IN ('QUEUED','RUNNING')").fetchone():
                raise ValueError('ANOTHER_JOB_IS_RUNNING')
            data=json.loads(row['details']);data.pop('error',None)
            data.update(phase='PUBLISHING' if data.get('manifest_sha256') else 'CHUNKING',auto_publish=True)
            c.execute("UPDATE jobs SET status='QUEUED',updated_at=?,details=? WHERE id=?",(now(),canonical(data),ident))
            c.execute('INSERT INTO audit(actor,action,resource,at) VALUES(?,?,?,?)',(actor,'RETRY_INDEX',ident,now()))

    def create_job(self, kind, actor, daily_key=None, article_ids=None):
        ident = str(uuid.uuid4())
        with self.connect() as c:
            if daily_key:
                previous = c.execute('SELECT id FROM jobs WHERE daily_key=?', (daily_key,)).fetchone()
                if previous: return previous[0], False
            if c.execute("SELECT 1 FROM jobs WHERE status IN ('QUEUED','RUNNING')").fetchone():
                raise ValueError('ANOTHER_JOB_IS_RUNNING')
            ids = list(dict.fromkeys(article_ids or []))
            if kind == 'RECHECK':
                ids = [r[0] for r in c.execute("""SELECT a.id FROM articles a JOIN reviews r ON r.id=
                    (SELECT max(id) FROM reviews WHERE article_id=a.id)
                    WHERE a.status='QUARANTINED' AND r.actor LIKE 'auto:%'
                    ORDER BY a.created_at,a.id LIMIT 500""")]
                if not ids: raise ValueError('NO_AUTOMATICALLY_HELD_ARTICLES')
            if kind == 'OCR':
                if len(ids) != 1: raise ValueError('SELECT_ONE_OCR_ARTICLE')
                row = c.execute('SELECT status FROM articles WHERE id=?', (ids[0],)).fetchone()
                if not row or row[0] not in {'PENDING', 'QUARANTINED'}:
                    raise ValueError('OCR_REQUIRES_UNDECIDED_ARTICLE')
            if kind == 'INDEX':
                if not ids: raise ValueError('NO_APPROVED_ARTICLES_SELECTED')
                for aid in ids:
                    row = c.execute('SELECT status FROM articles WHERE id=?', (aid,)).fetchone()
                    if not row or row[0] != 'APPROVED': raise ValueError('ARTICLE_NOT_APPROVED')
                    payload = json.loads(c.execute('SELECT payload FROM articles WHERE id=?', (aid,)).fetchone()[0])
                    if {'OCR_REQUIRED','ATTACHMENT_TEXT_REQUIRED'} & set(auto_review_reasons(payload)):
                        raise ValueError('SOURCE_TEXT_EXTRACTION_REQUIRED')
            c.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)',
                (ident, kind, 'QUEUED', actor, now(), now(), daily_key, canonical({'article_ids': ids})))
        return ident, True

    def update_job(self, ident, status, **details):
        with self.connect() as c:
            row = c.execute('SELECT details,status FROM jobs WHERE id=?', (ident,)).fetchone()
            if not row: raise ValueError('JOB_NOT_FOUND')
            if row['status'] == 'INTERRUPTED': raise ValueError('JOB_INTERRUPTED')
            data = json.loads(row[0]); data.update(details)
            c.execute('UPDATE jobs SET status=?,updated_at=?,details=? WHERE id=?',
                      (status, now(), canonical(data), ident))

    def get_job(self, ident):
        with self.connect() as c:
            row = c.execute('SELECT * FROM jobs WHERE id=?', (ident,)).fetchone()
            if not row: raise ValueError('JOB_NOT_FOUND')
            return {**dict(row), 'details': json.loads(row['details'])}

    def jobs(self):
        with self.connect() as c:
            return [{**dict(row), 'details': json.loads(row['details'])}
                    for row in c.execute('SELECT * FROM jobs ORDER BY created_at DESC LIMIT 100')]

    def save_article(self, job_id, payload):
        # Include editorial content and metadata, exclude volatile fetch timestamps.
        stable = {k: payload.get(k) for k in ('source', 'url', 'title', 'content', 'published_at', 'symbols')}
        checksum = sha(stable); ident = str(uuid.uuid5(uuid.NAMESPACE_URL, 'finmind-news:' + checksum))
        valid = bool(payload.get('title') and payload.get('content') and payload.get('url'))
        with self.connect() as c:
            if c.execute('SELECT status FROM jobs WHERE id=?', (job_id,)).fetchone()[0] != 'RUNNING':
                raise ValueError('JOB_NOT_RUNNING')
            created = c.execute('INSERT OR IGNORE INTO articles VALUES(?,?,?,?,?,?)',
                (ident, job_id, checksum, canonical(payload), 'PENDING' if valid else 'QUARANTINED', now())).rowcount
            c.execute('INSERT OR IGNORE INTO job_articles VALUES(?,?)', (job_id, ident))
        return ident, bool(created)

    def articles(self, status=None, offset=0, limit=50):
        with self.connect() as c:
            rows = c.execute('SELECT id,status,created_at,payload FROM articles ' +
                ('WHERE status=? ' if status else '') + 'ORDER BY created_at DESC,id LIMIT ? OFFSET ?',
                ((status,) if status else ()) + (limit, offset)).fetchall()
        return [{k: row[k] for k in ('id', 'status', 'created_at')} |
                {k: json.loads(row['payload']).get(k) for k in ('title', 'url', 'source', 'published_at', 'symbols')} |
                {'quality_reasons':auto_review_reasons(json.loads(row['payload'])),
                 'attachment_count':len(source_attachments(json.loads(row['payload'])))}
                for row in rows]

    def article_count(self, status=None):
        with self.connect() as c:
            return c.execute('SELECT count(*) FROM articles' + (' WHERE status=?' if status else ''),
                             (status,) if status else ()).fetchone()[0]

    def selection(self):
        with self.connect() as c:
            counts = {r['status']:r['n'] for r in c.execute('SELECT status,count(*) AS n FROM articles GROUP BY status')}
            ids = [r[0] for r in c.execute("SELECT id FROM articles WHERE status='APPROVED' ORDER BY created_at,id LIMIT 500")]
        return {'counts':counts,'approved_ids':ids,'selection_limit':500}

    def processed_jobs(self, article_id):
        with self.connect() as c:
            rows = c.execute("SELECT * FROM jobs WHERE kind='INDEX' AND status IN ('INDEXED','ACTIVE') ORDER BY created_at DESC").fetchall()
        return [{**dict(r),'details':json.loads(r['details'])} for r in rows
                if article_id in json.loads(r['details']).get('article_ids',[])]

    def published_article_refs(self):
        with self.connect() as c:
            rows = c.execute("""SELECT a.id,json_extract(a.payload,'$.title') AS title,
                json_extract(a.payload,'$.url') AS url,json_extract(a.payload,'$.symbols') AS symbols
                FROM articles a WHERE a.status='INDEXED' AND EXISTS(
                    SELECT 1 FROM jobs j,json_each(j.details,'$.article_ids') member
                    WHERE j.kind='INDEX' AND j.status='ACTIVE' AND member.value=a.id)
                ORDER BY a.created_at DESC,a.id""").fetchall()
            return [{**dict(r),'symbols':json.loads(r['symbols'] or '[]')} for r in rows]

    def auto_review(self, actor, article_ids=None, recheck_previous=False, include_current=False):
        with self.connect() as c:
            if recheck_previous:
                rows = c.execute("""SELECT a.id,a.payload FROM articles a JOIN reviews r ON r.id=
                    (SELECT max(id) FROM reviews WHERE article_id=a.id)
                    WHERE a.status='QUARANTINED' AND r.actor LIKE 'auto:%'
                    AND (r.note LIKE 'source-quality-v1:%' OR ?) ORDER BY a.created_at LIMIT 500""", (include_current,)).fetchall()
            elif article_ids is not None:
                if not article_ids: return {'approved':0,'quarantined':0}
                ids = sorted(article_ids)
                rows = c.execute("SELECT id,payload FROM articles WHERE status='PENDING' AND id IN (" +
                                 ','.join('?' for _ in ids) + ') ORDER BY created_at LIMIT 500', ids).fetchall()
            else:
                rows = c.execute("SELECT id,payload FROM articles WHERE status='PENDING' ORDER BY created_at LIMIT 500").fetchall()
            result = {'approved': 0, 'quarantined': 0}
            for row in rows:
                if article_ids is not None and row['id'] not in article_ids: continue
                reasons = auto_review_reasons(json.loads(row['payload']))
                decision = 'QUARANTINED' if reasons else 'APPROVED'
                note = 'source-quality-v2: ' + (','.join(reasons) if reasons else 'PROVIDER_BODY_DATE_CHECKS_PASSED')
                c.execute('INSERT INTO reviews(article_id,actor,decision,note,created_at) VALUES(?,?,?,?,?)',
                          (row['id'], 'auto:' + actor, decision, note, now()))
                c.execute('UPDATE articles SET status=? WHERE id=?', (decision,row['id']))
                result['quarantined' if reasons else 'approved'] += 1
            return result

    def article(self, ident):
        with self.connect() as c:
            row = c.execute('SELECT * FROM articles WHERE id=?', (ident,)).fetchone()
            if not row: raise ValueError('ARTICLE_NOT_FOUND')
            history = [dict(r) for r in c.execute('SELECT * FROM reviews WHERE article_id=? ORDER BY id', (ident,))]
            payload = json.loads(row['payload'])
            replacement = c.execute("SELECT id FROM articles WHERE json_extract(payload,'$.extraction.parent_article_id')=? LIMIT 1", (ident,)).fetchone()
            return {**dict(row), 'payload': payload, 'reviews': history,
                    'replacement_article_id':replacement[0] if replacement else None,
                    'quality_reasons':auto_review_reasons(payload), 'attachments':source_attachments(payload),
                    'ocr_available':True}

    def save_ocr_revision(self, job_id, parent_id, payload, actor):
        checksum = sha(payload)
        ident = str(uuid.uuid5(uuid.NAMESPACE_URL, 'finmind-news-ocr:' + checksum))
        with self.connect() as c:
            job = c.execute('SELECT status FROM jobs WHERE id=?', (job_id,)).fetchone()
            parent = c.execute('SELECT status FROM articles WHERE id=?', (parent_id,)).fetchone()
            if not job or job[0] != 'RUNNING': raise ValueError('JOB_NOT_RUNNING')
            if not parent or parent[0] not in {'PENDING','QUARANTINED'}:
                raise ValueError('ARTICLE_ALREADY_DECIDED')
            c.execute('INSERT INTO articles VALUES(?,?,?,?,?,?)',
                      (ident, job_id, checksum, canonical(payload), 'PENDING', now()))
            c.execute('INSERT INTO job_articles VALUES(?,?)', (job_id, ident))
            c.execute("UPDATE articles SET status='SUPERSEDED' WHERE id=?", (parent_id,))
            c.execute('INSERT INTO reviews(article_id,actor,decision,note,created_at) VALUES(?,?,?,?,?)',
                      (parent_id, actor, 'SUPERSEDED', 'Đã thay bằng bản trích xuất cần duyệt: ' + ident, now()))
        return ident

    def review(self, ident, decision, note, actor):
        if decision not in {'APPROVED', 'REJECTED', 'QUARANTINED'} or len(note.strip()) < 3:
            raise ValueError('DECISION_AND_REASON_REQUIRED')
        with self.connect() as c:
            row = c.execute('SELECT status,payload FROM articles WHERE id=?', (ident,)).fetchone()
            if not row: raise ValueError('ARTICLE_NOT_FOUND')
            if row[0] not in {'PENDING', 'QUARANTINED'}: raise ValueError('ARTICLE_ALREADY_DECIDED')
            payload = json.loads(row['payload'])
            if decision == 'APPROVED' and not (payload.get('title') and payload.get('content') and payload.get('url')):
                raise ValueError('INCOMPLETE_SOURCE')
            if decision == 'APPROVED' and {'OCR_REQUIRED','ATTACHMENT_TEXT_REQUIRED'} & set(auto_review_reasons(payload)):
                raise ValueError('SOURCE_TEXT_EXTRACTION_REQUIRED')
            c.execute('INSERT INTO reviews(article_id,actor,decision,note,created_at) VALUES(?,?,?,?,?)',
                      (ident, actor, decision, note.strip(), now()))
            c.execute('UPDATE articles SET status=? WHERE id=?', (decision, ident))

    def due(self, at=None):
        at = (at or datetime.now(TZ)).astimezone(TZ); cfg = self.config()
        if not cfg['enabled'] or at.hour < cfg['hour']: return None
        ident, created = self.create_job('CRAWL', 'scheduler', 'fireant:' + at.date().isoformat())
        return ident if created else None

    def indexed(self, ident):
        job = self.get_job(ident)
        with self.connect() as c:
            for aid in job['details']['article_ids']:
                c.execute("UPDATE articles SET status='INDEXED' WHERE id=? AND status='APPROVED'", (aid,))

    def audit(self, actor, action, resource):
        with self.connect() as c:
            c.execute('INSERT INTO audit(actor,action,resource,at) VALUES(?,?,?,?)', (actor,action,resource,now()))

    def interrupt(self, ident, actor):
        with self.connect() as c:
            changed = c.execute("UPDATE jobs SET status='INTERRUPTED',updated_at=? WHERE id=? AND status IN ('QUEUED','RUNNING')", (now(),ident)).rowcount
            if not changed: raise ValueError('JOB_NOT_RUNNING')
            c.execute('INSERT INTO audit(actor,action,resource,at) VALUES(?,?,?,?)', (actor,'INTERRUPT',ident,now()))


def collect_fireant(limit, *, symbols=None, max_pages=5, include_market=True):
    # Only reader functions are reused. The old CLI write_payload auto-ingests.
    from collections import deque
    import sys
    root = Path(__file__).resolve().parents[3]
    scraper_root = str(root / 'data_pipeline' / 'scrapers')
    if scraper_root not in sys.path: sys.path.insert(0, scraper_root)
    from news.news_sources import fireant_candidates, fireant_json, fireant_item, plain_text
    articles, errors = [], []
    streams = deque(iter(fireant_candidates(symbol=s, max_pages=max_pages)) for s in (symbols or []))
    if include_market: streams.append(iter(fireant_candidates(max_pages=max_pages)))
    seen = set()
    def candidates():
        # Round-robin across tickers; one busy ticker cannot consume the full limit.
        while streams:
            stream = streams.popleft()
            try: candidate = next(stream)
            except StopIteration: continue
            except Exception as exc:
                errors.append({'provider_id':None,'code':type(exc).__name__,'phase':'LISTING'})
                if len(errors) >= limit: return
                continue
            streams.append(stream)
            key = candidate['provider_id']
            if key not in seen:
                seen.add(key)
                yield candidate
    for candidate in candidates():
        if len(articles) + len(errors) >= limit: break
        try:
            raw = fireant_json('/posts/' + candidate['provider_id'])
            if not isinstance(raw, dict) or raw.get('type') != 1: raise ValueError('INVALID_PROVIDER_RECORD')
            item = fireant_item(raw)
            item['symbols'] = sorted(set(item.get('symbols', [])) | set(candidate.get('symbols', [])))
            articles.append({**item, 'source': 'fireant', 'content': plain_text(raw.get('content') or raw.get('originalContent')),
                             'raw': raw, 'crawled_at': now()})
        except Exception as exc:
            errors.append({'provider_id': candidate['provider_id'], 'code': type(exc).__name__})
    return articles, errors


def crawl_job(queue, ident, collector=None):
    queue.update_job(ident, 'RUNNING', phase='COLLECTING')
    try:
        cfg = queue.config()
        articles, errors = (collector(cfg['limit']) if collector else collect_fireant(cfg['limit'],
            symbols=cfg['symbols'], max_pages=cfg['max_pages'], include_market=cfg['include_market']))
        created = 0
        new_ids = set()
        for article in articles:
            aid, fresh = queue.save_article(ident, article); created += fresh
            if fresh: new_ids.add(aid)
        auto = queue.auto_review('crawl:' + ident, new_ids) if cfg['auto_approve'] else None
        queue.update_job(ident, 'PARTIAL' if errors else 'COMPLETED', phase='WAITING_REVIEW',
                         fetched=len(articles), new_articles=created, duplicates=len(articles)-created, errors=errors,
                         auto_review=auto, scope={k:cfg[k] for k in ('provider','symbols','max_pages','include_market','limit')})
    except Exception as exc:
        if queue.get_job(ident)['status'] != 'INTERRUPTED':
            queue.update_job(ident, 'FAILED', phase='COLLECTING', error=type(exc).__name__)
