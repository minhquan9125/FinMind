"""On-demand chat adapter; shares the web's cache, source locks and quotas."""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import re
import time

from ..b1_answering.evidence.market_contract import feed_pack
from ..b1_answering.evidence.citations import prepare_evidence
from ..market_data.live import BusyError
from .market_dialogue import matching_articles

VN = timezone(timedelta(hours=7))


def publication_time(raw):
    """Unzoned timestamps cannot safely establish a Vietnamese publication day."""
    if not isinstance(raw, str): return None
    try:
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw):
            return datetime.combine(date.fromisoformat(raw), datetime.min.time(), VN)
        value = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        return value.astimezone(VN) if value.tzinfo else None
    except ValueError:
        return None


def unavailable(reason='MARKET_UNAVAILABLE'):
    return dict(status='SYSTEM_UNAVAILABLE', reason_code=reason,
                message='Nguồn giá hoặc tin tức tạm thời chưa khả dụng. Vui lòng thử lại sau.')


class MarketResearch:
    def __init__(self, repository, *, services, now=None):
        self.repository, self.services = repository, services
        self.now = now or (lambda: datetime.now(VN))

    async def lookup(self, scope, *, previous_pack=None):
        """No background subscriptions, extra SDK processes or quota bypasses."""
        try:
            return await asyncio.to_thread(self._lookup, scope, previous_pack)
        except BusyError as exc:
            result = unavailable('MARKET_BUSY')
            result['message'] = 'Nguồn dữ liệu đang bận hoặc đến hạn mức. Vui lòng thử lại sau ít giây.'
            result['retry_after'] = exc.wait_seconds
            return result
        except Exception:
            return unavailable()

    def _lookup(self, scope, previous_pack):
        symbols = scope.get('companies', [])
        if len(symbols) != 1 or not re.fullmatch(r'[A-Z]{3}', symbols[0]):
            return dict(status='ASK_CLARIFICATION', reason_code='MARKET_SYMBOL_REQUIRED',
                        message='Vui lòng chọn một mã cổ phiếu gồm 3 chữ cái cho mỗi lần tra cứu.')
        live, news = self.services()
        return self._quote(symbols[0], scope, live) if scope['source_type'] == 'PRICE' else self._news(symbols[0], scope, news, previous_pack)

    def _quote(self, symbol, scope, live):
        failed = False
        requested = (scope.get('_market_request') or {}).get('day')
        historical = requested is not None and date.fromisoformat(requested) < self.now().astimezone(VN).date()
        if requested and date.fromisoformat(requested) > self.now().astimezone(VN).date():
            return dict(status='NO_DATA', reason_code='FUTURE_PRICE', message='Chưa có giá giao dịch cho ngày trong tương lai.')
        if historical:
            payload = live.stock_history(symbol) if live is not None else self.repository.get_ohlcv(symbol, 250)
            bars = [bar for bar in payload.get('bars', []) if bar.get('date') == requested]
            if not bars and hasattr(self.repository, 'runtime_read'):
                runtime = self.repository.runtime_read(symbol, 'history') or {}
                bars = [bar for bar in runtime.get('bars', []) if bar.get('date') == requested]
            if not bars:
                return dict(status='NO_DATA', reason_code='NO_TRADING_DAY',
                            message=f'Chưa có dữ liệu phiên giao dịch của {symbol} ngày {date.fromisoformat(requested):%d/%m/%Y}.')
            if not bars[0].get('price_unit') and hasattr(self.repository, 'runtime_read'):
                runtime = self.repository.runtime_read(symbol, 'history') or {}
                declared = [bar for bar in runtime.get('bars', []) if bar.get('date') == requested and bar.get('price_unit')]
                if declared: bars = declared
            payload = {**payload, 'bars': bars}
        elif live is not None:
            try:
                payload = live.refresh(symbol)
            except BusyError:
                raise
            except Exception:
                failed = True
                payload = live.read(symbol, 1)
        else:
            payload = self.repository.get_ohlcv(symbol, 1)
        bars = payload.get('bars') or []
        if not bars:
            return unavailable('PRICE_UNAVAILABLE')
        bar = max(bars, key=lambda item: item.get('date', ''))
        now = self.now().astimezone(VN)
        trading = date.fromisoformat(bar['date'])
        observed = publication_time(payload.get('fetched_at'))
        if trading > now.date() or observed is None or observed > now:
            return unavailable('INVALID_PRICE_TIME')
        # Only normalize_quote's valid RAM overlay has the documented /1000 scale.
        overlay = payload.get('live') or {}
        known_scale = (not historical and live is not None and payload.get('source') == 'vnstock_kbs'
                       and bar.get('source') == 'vnstock_kbs' and overlay.get('last_success_at')
                       and overlay['last_success_at'] == payload.get('fetched_at'))
        historical_unit = (bar.get('price_unit') if historical and bar.get('source') == 'vnstock_kbs'
                           and payload.get('source') == 'vnstock_kbs' else None)
        if not known_scale and historical_unit not in ('thousand_vnd', 'VND'):
            return dict(status='NO_DATA', reason_code='PRICE_UNIT_UNVERIFIED',
                        message='Chưa xác minh được đơn vị giá trong dữ liệu lưu; chưa thể báo giá VND chính xác.')
        try:
            value = Decimal(str(bar['close'])) * (1 if historical_unit == 'VND' else 1000)
            if not value.is_finite() or value <= 0 or value != value.to_integral_value(): raise ValueError()
        except (KeyError, InvalidOperation, ValueError):
            return unavailable('INVALID_PRICE')
        pack = feed_pack([dict(kind='PRICE', provider='vnstock_kbs', symbol=symbol,
                               observed_at=observed.isoformat(), trading_day=trading.isoformat(), price_vnd=str(value))])
        old_day = requested is not None and trading.isoformat() != requested
        draft = f"Giá{' đóng cửa' if historical else ''} {symbol} ngày {trading:%d/%m/%Y}: {value:,.0f} VND."
        if old_day:
            draft = f'Chưa có giá giao dịch ngày {requested} từ nguồn này. '+draft
        stale = bool(failed or overlay.get('stale') or (now-observed).total_seconds() > 60)
        return dict(status='PRICE_READY', reason_code='STALE_PRICE' if old_day else 'PRICE_READY',
                    message='Giá từ nguồn vnstock/KBS, kèm ngày giao dịch và thời điểm lấy dữ liệu.',
                    draft=draft, evidence_pack=pack, freshness={'stale': stale, 'observed_at': observed.isoformat()})

    def _news(self, symbol, scope, news, previous_pack):
        if scope.get('publisher') not in (None, 'fireant'):
            return dict(status='NO_DATA', reason_code='LIVE_PUBLISHER_UNAVAILABLE',
                        message='Nguồn tin đang cập nhật hiện hỗ trợ FireAnt; chưa hỗ trợ lấy tin mới từ nguồn bạn chọn.')
        if news is None: return unavailable('NEWS_UNAVAILABLE')
        selected_urls = scope.get('_article_urls')
        if selected_urls:
            evidence = prepare_evidence(previous_pack)
            articles = [item['snapshot'] for item in evidence.values()
                        if item.get('source_type') == 'NEWS' and item['snapshot']['symbol'] == symbol
                        and item['locator']['url'] in selected_urls]
            if len(articles) != len(selected_urls): return unavailable('ARTICLE_NOT_FOUND')
            payload = {'articles': articles, 'refresh': {'stale': False}}
        else:
            payload = news.refresh(symbol)
        stale = bool((payload.get('refresh') or {}).get('stale'))
        now = self.now().astimezone(VN)
        requested = (scope.get('_market_request') or {}).get('day')
        snapshots, seen = [], set()
        for item in payload.get('articles', []):
            published = publication_time(item.get('published_at'))
            if not published or published > now: continue
            if requested and published.date().isoformat() != requested: continue
            if item.get('url') in seen: continue
            seen.add(item.get('url'))
            snapshots.append(dict(kind='NEWS', provider='fireant', symbol=symbol,
                                  observed_at=now.isoformat(), title=item.get('title'),
                                  description=item.get('description') or '', url=item.get('url'),
                                  published_at=published.isoformat()))
        snapshots.sort(key=lambda item: item['published_at'], reverse=True)
        query = (scope.get('_market_request') or {}).get('query')
        if query:
            matches = matching_articles(query, snapshots)
            if len(matches) != 1:
                return dict(status='NO_DATA', reason_code='ARTICLE_NOT_FOUND',
                            message='Chưa xác định được một bài khớp nội dung bạn hỏi trong các tin mới nguồn trả về. '
                                    'Bạn có thể bổ sung tiêu đề chính xác hoặc hỏi danh sách tin của mã này.')
            snapshots = matches
        if not snapshots:
            if stale: return unavailable('NEWS_REFRESH_FAILED')
            return dict(status='NO_DATA', reason_code='NO_CURRENT_NEWS',
                        message=f'Chưa thấy tin của {symbol}'+(f' đăng ngày {requested}' if requested else '')+
                        ' trong các bài mới nhất nguồn FireAnt trả về. Nguồn này không bao phủ toàn bộ tin tức.')
        action = (scope.get('_market_request') or {}).get('action', 'LIST')
        if action in ('SUMMARY', 'DETAIL'):
            hydrated = []
            for snapshot in snapshots[:2]:
                try:
                    try:
                        detail = news.article(snapshot['url'])
                    except BusyError as exc:
                        # One short spacing wait, never loop through an exhausted minute quota.
                        if exc.wait_seconds > 2: raise
                        time.sleep(exc.wait_seconds)
                        detail = news.article(snapshot['url'])
                    if detail.get('url') != snapshot['url'] or not str(detail.get('content') or '').strip():
                        continue
                    content = detail['content']
                    hydrated.append({**snapshot, 'content': content[:7000], 'content_truncated': len(content) > 7000})
                except BusyError:
                    if not hydrated: raise
                    break
                except Exception:
                    continue
            if not hydrated:
                return dict(status='SYSTEM_UNAVAILABLE', reason_code='ARTICLE_CONTENT_UNAVAILABLE',
                            message='Chưa tải được nội dung bài để tóm tắt. Bạn có thể mở bài gốc hoặc thử lại sau.')
            snapshots = hydrated
        pack = feed_pack(snapshots[:3])
        return dict(status='EVIDENCE_READY', reason_code='EVIDENCE_READY',
                    evidence_pack=pack, freshness={'stale': stale, 'provider': 'fireant'},
                    message='Tin mới nhất do FireAnt cung cấp, có ngày đăng và liên kết gốc.')
