"""Read-only hybrid retrieval, with a rebuildable, verified lexical cache."""
import asyncio
import hashlib
import json
import math
import os
import re
import tempfile
import time
import uuid
from collections import defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from .ranking import BM25Index, TOKENIZER_VERSION, rrf, tokenize

MAX_CACHE_BYTES = 64 * 1024 * 1024
CACHE_BATCH_SIZE = 500
MODEL = 'BAAI/bge-m3@5617a9f61b02'
JOIN = '''FROM public.text_chunks t
JOIN public.index_versions i USING(index_version_id)
JOIN public.documents d USING(document_id)
LEFT JOIN public.companies c USING(company_id)
LEFT JOIN public.reporting_periods p USING(period_id)
LEFT JOIN public.news_articles n ON t.locator_json->>'source_table'='news_articles'
 AND n.article_id::text=t.locator_json->>'source_id'
WHERE t.index_version_id=$1::uuid AND t.superseded_at IS NULL'''
FIELDS = '''t.chunk_id::text,t.document_id::text,t.chunk_index,t.page_number AS page,
t.index_version_id::text,i.chunker_version,d.sha256 AS source_sha256,
t.content_hash,t.locator_json,d.title,d.doc_type,
coalesce(c.symbol,t.locator_json->>'symbol') AS company,
coalesce(p.period_code,t.locator_json->>'period_code',
t.locator_json->>'published_at',t.locator_json->>'section') AS period,
coalesce(t.locator_json->>'published_at',t.locator_json->>'period_code',t.locator_json->>'section') AS published_date,
coalesce(t.locator_json->>'url','') AS source_url,n.symbols'''
ROWS = 'SELECT ' + FIELDS + ' ' + JOIN
FINGERPRINT = '''SELECT md5(coalesce(string_agg(md5(ROW(t.chunk_id,t.content_hash,
t.locator_json,d.company_id,d.period_id,d.doc_type,c.symbol,p.period_code,n.symbols)::text),
'' ORDER BY t.chunk_id),'')) ''' + JOIN


class RetrievalError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def _uuid(value):
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise RetrievalError('INVALID_INDEX_ID') from None


def _period(value):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}(?:-Q[1-4]|-\d{2}(?:-\d{2})?)?', value):
        raise RetrievalError('INVALID_PERIOD')
    try:
        date.fromisoformat(value if len(value) == 10 else value + '-01' if len(value) == 7 and '-Q' not in value else value[:4] + '-01-01')
    except ValueError:
        raise RetrievalError('INVALID_PERIOD') from None
    return value


def _publisher(value):
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise RetrievalError('INVALID_PUBLISHER')
    raw = value.strip().casefold()
    # allow 'cafef', 'cafef.vn', 'fireant', 'fireant.vn' and minor separators
    host = raw.split('/')[0]
    host = host.replace('-', '').replace('_', '')
    if host in ('cafef', 'cafef.vn', 'cafefvn'):
        return 'cafef'
    if host in ('fireant', 'fireant.vn', 'fireantvn'):
        return 'fireant'
    raise RetrievalError('INVALID_PUBLISHER')


def _published_date(value):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise RetrievalError('INVALID_PUBLISHED_DATE')
    try:
        date.fromisoformat(value)
    except ValueError:
        raise RetrievalError('INVALID_PUBLISHED_DATE') from None
    return value


def _derive_publisher(row):
    """Derive publisher from frozen locator URL, not from live DB state."""
    url = row.get('source_url') or ''
    if isinstance(row.get('locator_json'), dict):
        url = row['locator_json'].get('url') or url
    try:
        host = (urlparse(url).hostname or '').casefold()
    except Exception:
        host = ''
    if 'cafef.vn' in host:
        return 'cafef'
    if 'fireant.vn' in host:
        return 'fireant'
    return None


def _derive_published_date(row):
    """Derive frozen published date from locator, matching snapshot provenance."""
    if isinstance(row.get('locator_json'), dict):
        value = row['locator_json'].get('published_at')
        if isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            try:
                date.fromisoformat(value)
                return value
            except ValueError:
                pass
    stored = row.get('published_date')
    if isinstance(stored, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', stored):
        try:
            date.fromisoformat(stored)
            return stored
        except ValueError:
            pass
    return None


def _scope(company, period, doc_type):
    values = []
    for value, pattern, code in ((company, r'[A-Z0-9]{1,16}', 'INVALID_COMPANY'),
                                 (doc_type, r'[A-Z_]{1,40}', 'INVALID_DOCUMENT_TYPE')):
        if value is not None and (not isinstance(value, str) or not re.fullmatch(pattern, value.strip().upper())):
            raise RetrievalError(code)
        values.append(value.strip().upper() if value is not None else None)
    return values[0], _period(period), values[1]


def _matches(row, company, period, doc_type, publisher=None, published_date=None):
    symbols = {s.upper() for s in row['symbols']}
    if row['company']:
        symbols.add(row['company'].upper())
    stored = row['period'] or ''
    derived_publisher = _derive_publisher(row)
    derived_date = _derive_published_date(row)
    return ((company is None or company in symbols)
            and (doc_type is None or doc_type == row['doc_type'].upper())
            and (period is None or stored == period or
                 (stored.startswith(period) and stored[len(period):len(period)+1] in ('-', 'T', ' ')))
            and (publisher is None or derived_publisher == publisher)
            and (published_date is None or derived_date == published_date))


def _metadata(row):
    return dict(chunk_id=row['chunk_id'], content_hash=row['content_hash'].strip(),
                company=row['company'], symbols=list(row['symbols'] or []),
                period=row['period'], doc_type=row['doc_type'],
                published_date=_derive_published_date(row),
                publisher=_derive_publisher(row),
                source_url=row.get('source_url') or (row.get('locator_json', {}).get('url') if isinstance(row.get('locator_json'), dict) else None))


def _source_code(exc):
    code = getattr(exc, 'reason_code', getattr(exc, 'code', 'SOURCE_UNAVAILABLE'))
    return code if code in {'SOURCE_CHANGED', 'SOURCE_MISSING', 'HASH_MISMATCH', 'INVALID_LOCATOR'} else 'SOURCE_UNAVAILABLE'


def _write_cache(path, payload):
    body = _canonical(dict(payload=payload, sha256=hashlib.sha256(_canonical(payload)).hexdigest()))
    if len(body) > MAX_CACHE_BYTES:
        raise RetrievalError('CACHE_TOO_LARGE')
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.cache-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _validate_cache(payload, index_id, model, now, max_age):
    if not isinstance(payload, dict) or set(payload) != {'version','tokenizer','index_id','model','built_at','fingerprint','rows'}:
        raise RetrievalError('INVALID_CACHE')
    if payload['version'] != 2 or type(payload['version']) is not int or payload['tokenizer'] != TOKENIZER_VERSION:
        raise RetrievalError('CACHE_VERSION_MISMATCH')
    if payload['index_id'] != index_id or payload['model'] != model:
        raise RetrievalError('CACHE_INDEX_MISMATCH')
    stamp = payload['built_at']
    if type(stamp) not in (int,float) or not math.isfinite(stamp) or not 0 <= now - stamp <= max_age:
        raise RetrievalError('CACHE_EXPIRED')
    if not isinstance(payload['fingerprint'],str) or not re.fullmatch('[a-f0-9]{32}',payload['fingerprint']):
        raise RetrievalError('INVALID_CACHE')
    rows = payload['rows']
    if not isinstance(rows,list) or len(rows)>100000:
        raise RetrievalError('INVALID_CACHE')
    seen = set()
    for row in rows:
        if not isinstance(row,dict) or set(row) != {'chunk_id','content_hash','company','symbols','period','doc_type','tokens','published_date','publisher','source_url'}:
            raise RetrievalError('INVALID_CACHE')
        cid = _uuid(row['chunk_id'])
        if cid != row['chunk_id'] or cid in seen:
            raise RetrievalError('INVALID_CACHE')
        seen.add(cid)
        if (not isinstance(row['content_hash'],str) or not re.fullmatch('[a-f0-9]{64}',row['content_hash'])
                or any(row[k] is not None and not isinstance(row[k],str) for k in ('company','period'))
                or not isinstance(row['doc_type'],str) or not row['doc_type']
                or not isinstance(row['symbols'],list) or any(not isinstance(s,str) for s in row['symbols'])
                or not isinstance(row['tokens'],list) or len(row['tokens'])>4096
                or any(not isinstance(t,str) or not 0<len(t)<=512 for t in row['tokens'])
                or (row['published_date'] is not None and (not isinstance(row['published_date'],str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', row['published_date'])))
                or (row['publisher'] is not None and row['publisher'] not in ('cafef','fireant'))
                or (row['source_url'] is not None and not isinstance(row['source_url'],str))):
            raise RetrievalError('INVALID_CACHE')
        if row['published_date'] is not None:
            try:
                date.fromisoformat(row['published_date'])
            except ValueError:
                raise RetrievalError('INVALID_CACHE') from None
    return payload


class HybridRetriever:
    def __init__(self, pool, embedder, *, resolver=None, clock=time.time, max_cache_age=3600, corpus_version_id=None):
        if isinstance(max_cache_age,bool) or not isinstance(max_cache_age,(int,float)) or not math.isfinite(max_cache_age) or max_cache_age <= 0:
            raise RetrievalError('INVALID_CACHE_AGE')
        self._default_resolver = resolver is None
        if resolver is None:
            from ..documents.repository import resolve_result_rows
            resolver = resolve_result_rows
        self.pool, self.embedder, self.resolver = pool, embedder, resolver
        self.clock, self.max_cache_age = clock, max_cache_age
        self._loaded = None
        self.corpus_version_id = _uuid(corpus_version_id) if corpus_version_id is not None else None

    def _statement(self, sql, args):
        """Bind the same document/hash membership in every cache and ranking query."""
        if self.corpus_version_id is None:
            return sql, args
        membership = (
            ' AND EXISTS (SELECT 1 FROM public.corpus_documents cd '
            f'WHERE cd.corpus_version_id=${len(args)+1}::uuid '
            'AND cd.document_id=t.document_id AND cd.document_hash=d.sha256)'
        )
        return sql.replace(JOIN, JOIN + membership), (*args, uuid.UUID(self.corpus_version_id))

    async def _fetch(self, conn, sql, *args):
        sql, args = self._statement(sql, args)
        return await conn.fetch(sql, *args)

    async def _value(self, conn, sql, *args):
        sql, args = self._statement(sql, args)
        return await conn.fetchval(sql, *args)

    async def _index(self, conn, index_id, allow_building):
        row = await conn.fetchrow('SELECT embedding_model,status FROM public.index_versions WHERE index_version_id=$1::uuid',index_id)
        if row is None:
            raise RetrievalError('INDEX_NOT_FOUND')
        if row['status'] != 'ACTIVE' and not (allow_building is True and row['status']=='BUILDING'):
            raise RetrievalError('INDEX_NOT_ACTIVE')
        if self.corpus_version_id is not None:
            corpus = await conn.fetchrow('SELECT index_version_id::text,status FROM public.corpus_versions '
                                         'WHERE corpus_version_id=$1::uuid', self.corpus_version_id)
            if not corpus or corpus['status'] != 'FROZEN':
                raise RetrievalError('CORPUS_NOT_READY')
            if corpus['index_version_id'] != index_id:
                raise RetrievalError('CORPUS_INDEX_MISMATCH')
        model = self.embedder.model_name + '@' + self.embedder.revision[:12]
        if model != MODEL or row['embedding_model'] != model:
            raise RetrievalError('MODEL_MISMATCH')
        kind = await conn.fetchval("SELECT format_type(atttypid,atttypmod) FROM pg_attribute WHERE attrelid='public.text_chunks'::regclass AND attname='embedding'")
        if kind != 'vector(1024)':
            raise RetrievalError('DIMENSION_MISMATCH')
        return dict(row)

    def _cache(self, path, index_id, model):
        path = Path(path)
        try:
            stat = path.stat()
            key = (str(path.resolve()),stat.st_mtime_ns,stat.st_size)
            if self._loaded is not None and self._loaded[0]==key:
                payload, index = self._loaded[1:]
                _validate_cache(payload,index_id,model,self.clock(),self.max_cache_age)
                return payload,index
            with path.open('rb') as stream:
                data = stream.read(MAX_CACHE_BYTES+1)
            if len(data)>MAX_CACHE_BYTES:
                raise RetrievalError('CACHE_TOO_LARGE')
            envelope = json.loads(data)
            if not isinstance(envelope,dict) or set(envelope)!={'payload','sha256'}:
                raise RetrievalError('INVALID_CACHE')
            payload=envelope['payload']
            if envelope['sha256'] != hashlib.sha256(_canonical(payload)).hexdigest():
                raise RetrievalError('CACHE_CHECKSUM_MISMATCH')
            _validate_cache(payload,index_id,model,self.clock(),self.max_cache_age)
            index=BM25Index({r['chunk_id']:r['tokens'] for r in payload['rows']})
            self._loaded=(key,payload,index)
            return payload,index
        except FileNotFoundError:
            raise RetrievalError('CACHE_BUILD_REQUIRED') from None
        except RetrievalError:
            raise
        except Exception:
            raise RetrievalError('INVALID_CACHE') from None

    async def prepare_cache(self, index_id, cache_path):
        """Validate/rebuild the lexical cache and load BM25 without a user search."""
        index_id = _uuid(index_id)

        async def load():
            async with self.pool.acquire() as conn:
                async with conn.transaction(readonly=True, isolation='repeatable_read'):
                    info = await self._index(conn, index_id, False)
                    payload, _ = self._cache(cache_path, index_id, info['embedding_model'])
                    if await self._value(conn, FINGERPRINT, index_id) != payload['fingerprint']:
                        raise RetrievalError('CACHE_STALE')
                    return {'status': 'CACHE_READY', 'chunks': len(payload['rows'])}

        try:
            return await load()
        except RetrievalError as exc:
            if exc.code not in ('CACHE_BUILD_REQUIRED', 'CACHE_EXPIRED', 'CACHE_STALE', 'CACHE_VERSION_MISMATCH'):
                raise
        await self.build_cache(index_id, cache_path)
        return await load()

    async def build_cache(self,index_id,cache_path,allow_building=False):
        index_id=_uuid(index_id)
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction(readonly=True,isolation='repeatable_read'):
                    info=await self._index(conn,index_id,allow_building)
                    fingerprint=await self._value(conn,FINGERPRINT,index_id)
                    rows = []
                    last_id = None
                    seen_ids = set()
                    while True:
                        if last_id is None:
                            page = await self._fetch(conn,ROWS + ' ORDER BY t.chunk_id LIMIT $2', index_id, CACHE_BATCH_SIZE)
                        else:
                            page = await self._fetch(conn,ROWS + ' AND t.chunk_id > $2::uuid ORDER BY t.chunk_id LIMIT $3', index_id, last_id, CACHE_BATCH_SIZE)
                        if not page:
                            break
                        for row in page:
                            cid = row['chunk_id']
                            if cid in seen_ids or (last_id is not None and cid <= last_id):
                                raise RetrievalError('CACHE_BUILD_FAILED')
                            seen_ids.add(cid)
                        rows.extend(page)
                        if len(page) < CACHE_BATCH_SIZE:
                            break
                        last_id = page[-1]['chunk_id']
                    if not rows:
                        raise RetrievalError('INDEX_EMPTY')
                    groups=defaultdict(list)
                    for row in rows:
                        groups[row['document_id']].append(row)
                    prepared=[]
                    # The default reader caches release/source bindings within one call.
                    # Resolve the bounded corpus together to avoid rereading its release per document.
                    for group in ([rows] if self._default_resolver else groups.values()):
                        try:
                            resolved=await self.resolver(conn,group)
                        except Exception as exc:
                            raise RetrievalError(_source_code(exc)) from None
                        by_id={r['chunk_id']:r for r in resolved}
                        if set(by_id)!={r['chunk_id'] for r in group}:
                            raise RetrievalError('SOURCE_UNAVAILABLE')
                        for row in group:
                            text=by_id[row['chunk_id']]['text']
                            if hashlib.sha256(text.encode('utf-8')).hexdigest()!=row['content_hash'].strip():
                                raise RetrievalError('HASH_MISMATCH')
                            meta = _metadata(row)
                            prepared.append(dict(meta,tokens=tokenize(text)))
            payload=dict(version=2,tokenizer=TOKENIZER_VERSION,index_id=index_id,
                         model=info['embedding_model'],built_at=self.clock(),fingerprint=fingerprint,rows=prepared)
            _validate_cache(payload,index_id,info['embedding_model'],self.clock(),self.max_cache_age)
            _write_cache(cache_path,payload)
            self._loaded=None
            return dict(status='CACHE_READY',chunks=len(prepared),index_version_id=index_id,index_status=info['status'],
                        scope_mode='CORPUS' if self.corpus_version_id else 'INDEX',
                        **({'corpus_version_id':self.corpus_version_id} if self.corpus_version_id else {}))
        except RetrievalError:
            raise
        except Exception:
            raise RetrievalError('CACHE_BUILD_FAILED') from None

    async def search(self,question,index_id,cache_path,*,company=None,period=None,doc_type=None,publisher=None,published_date=None,top_k=5,candidates=50,allow_building=False,exact_period=False):
        index_id=_uuid(index_id)
        if not isinstance(question,str) or not question.strip() or len(question)>4000:
            raise RetrievalError('INVALID_QUESTION')
        if type(top_k) is not int or type(candidates) is not int or not 1<=top_k<=20 or not top_k<=candidates<=200:
            raise RetrievalError('INVALID_LIMITS')
        company,period,doc_type=_scope(company,period,doc_type)
        publisher=_publisher(publisher)
        published_date=_published_date(published_date)
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction(readonly=True,isolation='repeatable_read'):
                    info=await self._index(conn,index_id,allow_building)
                    payload,lexical_index=self._cache(cache_path,index_id,info['embedding_model'])
                    if await self._value(conn,FINGERPRINT,index_id)!=payload['fingerprint']:
                        raise RetrievalError('CACHE_STALE')
                    allowed={r['chunk_id'] for r in payload['rows'] if _matches(r,company,period,doc_type,publisher,published_date)
                             and (not exact_period or r['period']==period)}
                    lexical=lexical_index.search(question,limit=candidates,allowed_ids=allowed)
                    dense=[]
                    if allowed:
                        vector=await asyncio.to_thread(self.embedder.embed_query,question)
                        if len(vector)!=1024 or any(type(x) not in (int,float) or not math.isfinite(x) for x in vector) or not any(vector):
                            raise RetrievalError('INVALID_QUERY_VECTOR')
                        ranked=await self._fetch(conn,'SELECT t.chunk_id::text,1-(t.embedding <=> $2::vector) AS score '+JOIN+
                            ' AND t.chunk_id=ANY($3::uuid[]) ORDER BY t.embedding <=> $2::vector LIMIT $4',
                            index_id,vector,[uuid.UUID(cid) for cid in sorted(allowed)],candidates)
                        dense=[(r['chunk_id'],float(r['score'])) for r in ranked]
                    fused=rrf(dense,lexical,limit=top_k)
                    if fused:
                        selected=await self._fetch(conn,ROWS+' AND t.chunk_id=ANY($2::uuid[])',index_id,[uuid.UUID(r['chunk_id']) for r in fused])
                        try:
                            verified=await self.resolver(conn,selected)
                        except Exception as exc:
                            raise RetrievalError(_source_code(exc)) from None
                        by_id={r['chunk_id']:r for r in verified}
                        for item in fused:
                            row=by_id.get(item['chunk_id'])
                            if row is None or row['chunk_id'] not in allowed or not _matches(_metadata(row),company,period,doc_type,publisher,published_date):
                                raise RetrievalError('SOURCE_UNAVAILABLE')
                            if exact_period and _metadata(row)['period'] != period:
                                raise RetrievalError('SOURCE_UNAVAILABLE')
                            if hashlib.sha256(row['text'].encode('utf-8')).hexdigest()!=row['content_hash'].strip():
                                raise RetrievalError('HASH_MISMATCH')
                            item.update(document_id=row['document_id'],locator=row['locator_json'],content_hash=row['content_hash'].strip(),text=row['text'],
                                        title=row['title'],source_sha256=row.get('source_sha256'))
            return dict(index_version_id=index_id,index_status=info['status'],scope_mode='CORPUS' if self.corpus_version_id else 'INDEX',
                        **({'corpus_version_id':self.corpus_version_id} if self.corpus_version_id else {}),
                        scope=dict(company=company,period=period,doc_type=doc_type,publisher=publisher,published_date=published_date),results=fused)
        except RetrievalError:
            raise
        except Exception:
            raise RetrievalError('SEARCH_UNAVAILABLE') from None
