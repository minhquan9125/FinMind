"""Content-bound snapshots from the application's shared public market feeds.

These are feed observations, not registered corpus documents or independent
verification of a publisher's claims. No invented database/page locators.
"""
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import re
from urllib.parse import urlsplit
import uuid

from .citations import CitationError


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def feed_item(snapshot):
    """Reconstruct all visible source fields from one canonical observation."""
    if not isinstance(snapshot, dict) or not re.fullmatch(r'[A-Z]{3}', snapshot.get('symbol', '')):
        raise CitationError('INVALID_EVIDENCE')
    for key in ('observed_at',):
        try:
            stamp = datetime.fromisoformat(snapshot[key].replace('Z', '+00:00'))
            if stamp.tzinfo is None: raise ValueError()
        except (KeyError, TypeError, ValueError, AttributeError):
            raise CitationError('INVALID_EVIDENCE') from None
    kind, provider = snapshot.get('kind'), snapshot.get('provider')
    symbol = snapshot['symbol']
    locator = {'provider': provider, 'symbol': symbol, 'observed_at': snapshot['observed_at']}
    if kind == 'NEWS' and provider == 'fireant':
        url = urlsplit(snapshot.get('url', ''))
        if (url.scheme != 'https' or url.hostname not in ('fireant.vn', 'www.fireant.vn')
                or url.username or url.password or url.port not in (None, 443)
                or not url.path.startswith('/bai-viet/')):
            raise CitationError('INVALID_EVIDENCE')
        title, description = snapshot.get('title'), snapshot.get('description')
        if not isinstance(title, str) or not title.strip() or len(title) > 1000:
            raise CitationError('INVALID_EVIDENCE')
        if not isinstance(description, str) or len(description) > 4000:
            raise CitationError('INVALID_EVIDENCE')
        published = snapshot.get('published_at')
        if not isinstance(published, str) or not published or len(published) > 80:
            raise CitationError('INVALID_EVIDENCE')
        content = snapshot.get('content', '')
        if not isinstance(content, str) or len(content) > 7000:
            raise CitationError('INVALID_EVIDENCE')
        passage = f"{title}\n{content or description}\nNgày đăng: {published}"
        locator.update(url=snapshot['url'], published_at=published,
                       section=f'FireAnt · {symbol} · Đăng {published}')
    elif kind == 'PRICE' and provider == 'vnstock_kbs':
        from decimal import Decimal, InvalidOperation
        try:
            price = Decimal(snapshot['price_vnd'])
            if not price.is_finite() or price <= 0: raise ValueError()
            datetime.strptime(snapshot['trading_day'], '%Y-%m-%d')
        except (KeyError, TypeError, ValueError, InvalidOperation):
            raise CitationError('INVALID_EVIDENCE') from None
        title = f'Giá cổ phiếu {symbol} · vnstock/KBS'
        passage = (f"Giá gần nhất của {symbol}: {price:,.0f} VND. "
                   f"Ngày giao dịch: {snapshot['trading_day']}. "
                   f"Lấy dữ liệu lúc {snapshot['observed_at']}.")
        locator.update(trading_day=snapshot['trading_day'],
                       section=f"vnstock/KBS · {symbol} · {snapshot['trading_day']}")
    elif kind == 'PRICE_TREND' and provider == 'finmind_db':
        # The passage is generated from the stored-price trend, so the model cites exactly the computed labels.
        from ...market_data.trend import trend_passage
        trend, as_of = snapshot.get('trend'), snapshot.get('as_of')
        try:
            if not isinstance(as_of, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', as_of):
                raise ValueError()
            datetime.strptime(as_of, '%Y-%m-%d')
            if not isinstance(trend, dict) or trend.get('as_of') != as_of or set(trend['horizons']) != {'20', '60', '200'}:
                raise ValueError()
            passage = trend_passage(symbol, trend)
        except (KeyError, TypeError, ValueError, AttributeError):
            raise CitationError('INVALID_EVIDENCE') from None
        title = f'Xu hướng giá {symbol} · dữ liệu FinMind'
        locator.update(trading_day=as_of, section=f'FinMind DB · {symbol} · {as_of}')
    elif kind == 'FINANCIAL_HEALTH' and provider == 'finmind_db':
        # Verified BCTC signals; the passage is code-generated and links only to Vietstock BCTC PDFs.
        from ...financial.health_passage import NAMES, PERIOD, financial_health_passage
        health = snapshot.get('health')
        try:
            if (not isinstance(health, dict) or not isinstance(health.get('period'), str)
                    or not PERIOD.match(health['period']) or not isinstance(health.get('signals'), dict)
                    or not health['signals'] or set(health['signals']) - set(NAMES)):
                raise ValueError()
            citations = health.get('citations') or []
            if not isinstance(citations, list) or len(citations) > 5:
                raise ValueError()
            for cite in citations:
                url = urlsplit(cite['url'])
                if (url.scheme != 'https' or not (url.hostname or '').endswith('vietstock.vn') or url.username
                        or not isinstance(cite['title'], str) or not cite['title'].strip()
                        or type(cite['page']) is not int or cite['page'] < 1):
                    raise ValueError()
            passage = financial_health_passage(symbol, health)
        except (KeyError, TypeError, ValueError, AttributeError):
            raise CitationError('INVALID_EVIDENCE') from None
        first = citations[0] if citations else None
        title = first['title'] if first else f'Tình hình tài chính {symbol} · dữ liệu FinMind'
        locator.update(period=health['period'], section=f'BCTC FinMind · {symbol} · {health["period"]}')
        if first:
            locator.update(url=first['url'], page=first['page'])
    else:
        raise CitationError('INVALID_EVIDENCE')
    sha = digest(snapshot)
    return dict(evidence_id='feed-'+sha, source_id=provider+':'+symbol,
                chunk_id='snapshot-'+sha, source_type=kind, title=title, passage=passage,
                source_sha256=sha, content_sha256=hashlib.sha256(passage.encode('utf-8')).hexdigest(),
                source_verified=True, verification_basis='FEED_SNAPSHOT_BINDING',
                locator=locator, snapshot=deepcopy(snapshot))


def feed_pack(snapshots):
    items = [feed_item(snapshot) for snapshot in snapshots]
    return dict(schema_version='1.2', query_id=str(uuid.uuid4()),
                data_version={'kind': 'MARKET_FEED_SNAPSHOT', 'id': digest(items)}, items=items)


def prepare_market_evidence(pack):
    try:
        uuid.UUID(pack['query_id'])
        items = pack['items']
        if not isinstance(items, list) or not 1 <= len(items) <= 10: raise ValueError()
        out = {}
        for item in items:
            expected = feed_item(item['snapshot'])
            if item != expected or item['evidence_id'] in out: raise ValueError()
            out[item['evidence_id']] = deepcopy(item)
        if pack['data_version'] != {'kind': 'MARKET_FEED_SNAPSHOT', 'id': digest(items)}:
            raise ValueError()
        return out
    except (KeyError, ValueError, TypeError, AttributeError, OverflowError):
        raise CitationError('INVALID_EVIDENCE') from None
