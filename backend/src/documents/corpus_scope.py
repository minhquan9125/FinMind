"""Read-only, explicit corpus routing. A BUILDING index is never a fallback."""
from dataclasses import dataclass
from decimal import Decimal
import re
import uuid

from .corpus_manifest import sha256


class CorpusScopeError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CorpusScope:
    corpus_version_id: str
    index_version_id: str
    manifest_sha256: str
    version_label: str


async def load_scope(conn, corpus_id, *, model=None, expected_hash=None):
    try:version_id=uuid.UUID(str(corpus_id))
    except (ValueError,TypeError,AttributeError) as exc:
        raise CorpusScopeError('INVALID_CORPUS_ID','Corpus ID must be a UUID') from exc
    rows = await conn.fetch('''SELECT c.corpus_version_id::text,c.index_version_id::text,
        c.version_label,c.manifest_sha256,c.status AS corpus_status,c.frozen_at,
        i.status AS index_status,i.embedding_model,i.chunker_version
        FROM public.corpus_versions c JOIN public.index_versions i USING(index_version_id)
        WHERE c.corpus_version_id=$1''', version_id)
    if len(rows) != 1:
        raise CorpusScopeError('CORPUS_NOT_REGISTERED', 'Requested corpus is not registered with an index')
    row = dict(rows[0])
    if row['corpus_status'] != 'FROZEN' or not row['frozen_at'] or row['index_status'] != 'ACTIVE':
        raise CorpusScopeError('CORPUS_NOT_READY', 'Corpus must be frozen and its index ACTIVE')
    digest = (row['manifest_sha256'] or '').strip()
    if not re.fullmatch('[a-f0-9]{64}',digest):
        raise CorpusScopeError('CORPUS_MANIFEST_MISMATCH','Registered manifest hash is invalid')
    if expected_hash is not None and digest != expected_hash:
        raise CorpusScopeError('CORPUS_MANIFEST_MISMATCH', 'Configured manifest differs from registered corpus')
    if model is not None and row['embedding_model'] != model:
        raise CorpusScopeError('CORPUS_MODEL_MISMATCH', 'Query embedding model differs from corpus index')
    if row.get('chunker_version') == 'db-corpus-v2' and row['version_label'] == 'corpus-v2':
        expected_index=uuid.uuid5(uuid.UUID('b77dbd7f-5d89-479d-90a3-421e5f0981ea'),
            f'corpus-v2:index:{digest}:{row["embedding_model"]}')
        if str(expected_index)!=row['index_version_id']:
            raise CorpusScopeError('CORPUS_INDEX_MISMATCH','Corpus manifest is bound to a different vector index')
    return CorpusScope(row['corpus_version_id'],row['index_version_id'],digest,row['version_label'])


def decimal_text(value):
    if value is None:return None
    number=Decimal(str(value))
    if not number.is_finite():raise ValueError('Nonfinite source value')
    if number==0:return '0'
    text=format(number,'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def fact_value_hash(row):
    return sha256(dict(schema='corpus-fact-value-v1',observation_id=str(row['observation_id']),
        report_id=str(row['report_id']),metric_id=str(row['metric_id']),value=decimal_text(row['value']),
        unit=row['unit'],scale=decimal_text(row['scale']),currency=row['currency']))


def price_value_hash(row):
    fields=('open','high','low','close','volume','price_scale','sma20','sma50','rsi14')
    return sha256(dict(schema='corpus-price-value-v1',price_id=str(row['price_id']),
        company_id=str(row['company_id']),trade_date=str(row['trade_date']),is_adjusted=row['is_adjusted'],
        values={k:decimal_text(row.get(k)) for k in fields}))


async def read_prices(conn, scope, symbol, start_date=None, end_date=None):
    """Only corpus members can participate in counts, averages or extrema."""
    from ..core.config import get_settings
    if get_settings().source_read_backend=='supabase':
        from .shared_source import shared_price_rows
        return await shared_price_rows(conn,scope,symbol,start_date,end_date)
    rows=await conn.fetch('''SELECT p.price_id::text,p.company_id::text,p.trade_date,p.is_adjusted,
        p.open,p.high,p.low,p.close,p.volume,p.price_scale,i.sma20,i.sma50,i.rsi14,cp.value_hash
        FROM public.corpus_prices cp JOIN public.price_bars p USING(price_id)
        JOIN public.companies c ON c.company_id=p.company_id
        LEFT JOIN public.price_indicators i ON i.price_id=p.price_id
        WHERE cp.corpus_version_id=$1 AND c.symbol=$2
          AND ($3::date IS NULL OR p.trade_date >= $3) AND ($4::date IS NULL OR p.trade_date <= $4)
        ORDER BY p.trade_date,p.price_id''',uuid.UUID(scope.corpus_version_id),symbol.upper(),start_date,end_date)
    for row in rows:
        if not row['value_hash'] or price_value_hash(row)!=row['value_hash'].strip():
            raise CorpusScopeError('CORPUS_PRICE_CHANGED','Price member changed since corpus registration')
    return [dict(row) for row in rows]
