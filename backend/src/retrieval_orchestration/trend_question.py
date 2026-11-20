"""Answer "xu hướng ngắn/trung/dài hạn của X", "X tăng hay giảm", "trên hay dưới đường trung bình" from stored prices.

The labels and numbers come from market_data.trend (computed on the daily price bars), so no model writes them
and they cannot drop or change. A full "phân tích", a named period or other topics keep their own paths.
"""
import re
from decimal import Decimal

from ..market_data.trend import DISCLAIMER, HORIZON_NAMES, LABELS_VI, _vi, _vnd
from .retrieval_flow.intent import _fold

_TREND = re.compile(r'\b(?:xu huong|tang hay giam|giam hay tang|(?:di )?len hay (?:di )?xuong|(?:di )?xuong hay (?:di )?len|'
                    r'tren hay duoi|duoi hay tren|duong trung binh|sma ?(?:20|60|200))\b')
# Other topics, a full analysis or a named period (exact arithmetic in price_analytics) are not this question.
_OTHER = re.compile(r'\b(?:phan tich|tin|tin tuc|bctc|bctn|bao cao|loi nhuan|doanh thu|tai chinh|co dong|khoi ngoai|'
                    r'chi tiet|thang \d+|nam \d{4}|quy \d|tuan|ngay \d+|tu dau nam|hom nay|hom qua)\b|\d{1,2}/\d{1,4}')
_FOLLOWUP = re.compile(r'^(?:the |vay )?con\b|\bthi sao$')
_PREMISE = re.compile(r'\b(?:dung khong|phai khong|co phai|dung chua|phai ko|dung ko)\b')
_HORIZON_WORDS = (('ngan han', 20), ('trung han', 60), ('dai han', 200))


def _horizons(norm):
    found = {days for word, days in _HORIZON_WORDS if word in norm}
    for pair in re.findall(r'\b(?:sma|trung binh|mua)\s*(20|60|200)\b|\b(20|60|200) phien\b', norm):
        found |= {int(x) for x in pair if x}
    return sorted(found)


def _companies(norm, symbols):
    from .hybrid_router.decision_engine import DEFAULT_COMPANIES
    hits = {}
    for symbol in symbols:
        match = re.search(r'\b' + symbol.lower() + r'\b', norm)
        if match:
            hits.setdefault(symbol, match.start())
    for alias, targets in DEFAULT_COMPANIES.items():
        match = re.search(r'\b' + re.escape(_fold(alias)) + r'\b', norm)
        for symbol in targets if match else ():
            if symbol in symbols:
                hits[symbol] = min(hits.get(symbol, match.start()), match.start())
    return sorted(hits, key=hits.get)


def _claim(norm):
    if not _PREMISE.search(norm):
        return None
    stated = _TREND.sub(' ', norm)
    for pattern, label in ((r'\b(?:tang|di len)\b', 'UP'), (r'\b(?:giam|di xuong)\b', 'DOWN'),
                           (r'\b(?:di ngang|tich luy)\b', 'SIDEWAYS')):
        if re.search(pattern, stated):
            return label
    return None


def trend_request(text, context, symbols):
    """{'symbols', 'horizons', 'claim'} for a trend question about named (or continued) companies, else None."""
    norm = _fold(text).strip(' .?!')
    if _OTHER.search(norm):
        return None
    previous = (context or {}).get('_trend_request')
    named = _companies(norm, symbols)
    horizons = _horizons(norm)
    if _TREND.search(norm):
        companies = named or ([c for c in (context or {}).get('companies') or [] if c in symbols] if previous else [])
        if not companies:
            return None
        return {'symbols': companies, 'horizons': horizons or [20, 60, 200], 'claim': _claim(norm)}
    # "Còn BID?" / "còn trung hạn thì sao" right after a trend answer keeps the other slot.
    if previous and _FOLLOWUP.search(norm) and (named or horizons):
        return {'symbols': named or list(context.get('companies') or []),
                'horizons': horizons or list(previous.get('horizons') or [20, 60, 200]), 'claim': None}
    return None


def _day(iso):
    return '/'.join(reversed(iso.split('-')))


def _line(h, item, scale):
    parts = []
    if item.get('return_percent') is None:
        parts.append('chưa đủ số phiên giao dịch đã lưu' if item['label'] == 'INSUFFICIENT_DATA' else
                     'chưa tính mức tăng/giảm vì có phiên biến động vượt biên độ sàn (có thể do chia tách hoặc '
                     'cổ tức bằng cổ phiếu)')
    else:
        ret = Decimal(item['return_percent'])
        parts.append(f'giá {"tăng" if ret > 0 else "giảm"} {_vi(abs(ret))}% so với {h} phiên trước' if ret
                     else f'giá không đổi so với {h} phiên trước')
    if item.get('close_vs_sma_percent') is not None and item.get('sma') is not None:
        vs = Decimal(item['close_vs_sma_percent'])
        parts.append(f'giá đóng cửa nằm {"trên" if vs >= 0 else "dưới"} đường trung bình {h} phiên '
                     f'({_vnd(item["sma"], scale)} đồng), {"cao" if vs >= 0 else "thấp"} hơn {_vi(abs(vs))}%')
    return f'• {HORIZON_NAMES[h]} ({h} phiên): {LABELS_VI[item["label"]]} — ' + '; '.join(parts) + '.'


def render_trend(trends, horizons, claim):
    """The answer: an optional verdict on the user's claim, then one block per company, one line per horizon."""
    blocks, labels = [], []
    for symbol, trend in trends.items():
        scale = (trend.get('source') or {}).get('price_scale') or 1
        lines = [f'Xu hướng giá {symbol} tính đến phiên {_day(trend["as_of"])}:']
        for h in horizons:
            item = trend['horizons'][str(h)]
            labels.append(item['label'])
            lines.append(_line(h, item, scale))
        blocks.append('\n'.join(lines))
    if claim:
        verdict = ('Đúng.' if all(label == claim for label in labels) else
                   'Không đúng.' if all(label != claim for label in labels) else 'Chỉ đúng một phần.')
        blocks.insert(0, f'{verdict} Theo dữ liệu giá đã lưu, xu hướng hiện là {LABELS_VI[labels[0]].lower()}'
                         + (' ở khung được hỏi.' if len(labels) == 1 else ' (chi tiết từng khung bên dưới).'))
    blocks.append('Cách đọc: so giá đóng cửa phiên gần nhất với số phiên trước và với giá trung bình của số phiên đó; '
                  'nhãn Tăng/Giảm khi giá, đường trung bình và mức thay đổi cùng chiều. '
                  f'Nguồn: giá giao dịch hằng ngày trong cơ sở dữ liệu FinMind. {DISCLAIMER}')
    return '\n\n'.join(blocks)
