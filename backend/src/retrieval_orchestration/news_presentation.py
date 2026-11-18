"""Attribute feed headlines without turning them into FinMind advice.

Labels describe explicit wording in a headline, not an endorsement or an
inference about an article's author or original publisher.
"""
import re
from datetime import datetime, timezone, timedelta
from .retrieval_flow.intent import _fold


def has_recommendation_headline(title):
    return bool(re.search(
        r'\b(?:khuyen nghi\s+(?:mua|ban|nam giu|tich luy|dau tu|co phieu)|'
        r'gia muc tieu|nen mua|nen ban)\b', _fold(title or '')))


def render_news_list(items, *, stale=False):
    lines = ['Tin tức mới nhất trong nguồn đang có:']
    recommendation = False
    for number, item in enumerate(items, 1):
        snapshot = item.get('snapshot') or {}
        title = item['title']
        stamp = datetime.fromisoformat(snapshot['published_at'])
        if stamp.tzinfo is not None:
            stamp = stamp.astimezone(timezone(timedelta(hours=7)))
        # Provider is the feed used, not necessarily the original publisher.
        provider = {'fireant': 'FireAnt', 'cafef': 'CafeF'}.get(snapshot.get('provider'), 'nguồn tin bên ngoài')
        flagged = has_recommendation_headline(title)
        recommendation |= flagged
        label = 'Bài có tiêu đề về nhận định/khuyến nghị đầu tư' if flagged else 'Bài báo'
        lines.append(f'{number}. {label}: “{title}”\nNguồn lấy tin: {provider} · Ngày đăng: {stamp:%d/%m/%Y} [{number}]')
    if recommendation:
        lines.append('Nội dung khuyến nghị là tiêu đề/nhận định từ bài báo bên ngoài, không phải lời khuyên mua bán của FinMind.')
    if stale:
        lines.append('Đây là các tin đã lưu gần nhất; lần lấy tin mới vừa thất bại.')
    return '\n\n'.join(lines)
