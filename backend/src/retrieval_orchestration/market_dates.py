"""Complete price-date slots from explicit replies and a known prior date."""
import copy
from datetime import date, timedelta
import re


def relative_market_range(norm, today):
    """Resolve Vietnamese calendar ranges using the caller's fixed VN date."""
    if re.search(r'\bthang nay\b', norm):
        start, end, granularity = today.replace(day=1), today, 'MONTH'
    elif re.search(r'\bthang truoc\b', norm):
        previous_end = today.replace(day=1) - timedelta(days=1)
        start = previous_end.replace(day=1)
        end, granularity = previous_end, 'MONTH'
    elif re.search(r'\btuan nay\b', norm):
        start = today - timedelta(days=today.weekday())
        end, granularity = today, 'WEEK'
    elif re.search(r'\btuan truoc\b', norm):
        this_monday = today - timedelta(days=today.weekday())
        start = this_monday - timedelta(days=7)
        end, granularity = this_monday - timedelta(days=1), 'WEEK'
    else:
        return None
    quarter = (end.month - 1) // 3 + 1
    return {
        'kind': 'QUOTE', 'day': None, 'action': 'RANGE',
        'start_day': start.isoformat(), 'end_day': end.isoformat(),
        'granularity': granularity, 'quarter': f'{end.year}-Q{quarter}',
        'period_label': f'{start:%d/%m/%Y}–{end:%d/%m/%Y}',
    }


def temporal_reply(norm):
    return bool(re.fullmatch(r'(?:(?:con|ngay|hom|thang|nam|qua|kia|nay|thi|sao)\b\s*|[\d/\s-])+', norm.strip(' .?!')))


def price_date_request(norm, prior, *, explicit_price=False):
    prior = prior or {}
    if prior.get('kind') != 'QUOTE' and not explicit_price: return None
    norm = norm.strip(' .?!')
    day = re.search(r'\b(?:ngay|hom)\s+(\d{1,2})(?:\s*/\s*(\d{1,2}))?(?:\s*/\s*(\d{4}))?\b', norm)
    if not day and prior.get('kind') == 'QUOTE':
        day = re.fullmatch(r'(?:con\s+)?(\d{1,2})(?:/(\d{1,2}))?(?:/(\d{4}))?(?:\s+thi sao)?', norm)
    month = re.search(r'\bthang\s+(\d{1,2})(?:\s*/\s*(\d{4})|\s+nam\s+(\d{4}))?\b', norm)
    year = re.search(r'\bnam\s+((?:19|20|21)\d{2})\b', norm)
    if not any((day, month, year)):
        if re.fullmatch(r'(?:con\s+)?hom truoc(?:\s+thi sao)?', norm):
            return {'kind': 'QUOTE', 'day': None, 'action': 'LIST', '_calendar_issue': 'MISSING_MARKET_DATE',
                    '_calendar_message': 'Bạn muốn xem giá vào ngày cụ thể nào? Ví dụ: ngày 15/10/2026.'}
        return None
    request = {key: copy.deepcopy(value) for key, value in prior.items()
               if key not in ('day', '_pending_date', '_calendar_issue', '_calendar_message')}
    request.update(kind='QUOTE', action='LIST', day=None)
    parts = copy.deepcopy(prior.get('_pending_date') or {})
    if day:
        parts['day'] = int(day[1])
        if day[2]: parts['month'] = int(day[2])
        if day[3]: parts['year'] = int(day[3])
        try: anchor = date.fromisoformat(prior.get('day') or prior.get('anchor_day') or '')
        except ValueError: anchor = None
        if anchor:
            parts.setdefault('month', anchor.month)
            parts.setdefault('year', anchor.year)
    if month:
        parts['month'] = int(month[1])
        if month[2] or month[3]: parts['year'] = int(month[2] or month[3])
    if year: parts['year'] = int(year[1])
    missing = [name for name in ('day', 'month', 'year') if name not in parts]
    invalid = (not 1 <= parts.get('day', 1) <= 31 or not 1 <= parts.get('month', 1) <= 12
               or not 1900 <= parts.get('year', 2026) <= 2199)
    if not missing and not invalid:
        try: request['day'] = date(parts['year'], parts['month'], parts['day']).isoformat()
        except ValueError: invalid = True
    if invalid or missing:
        request['_pending_date'] = parts
        request['_calendar_issue'] = 'INVALID_DATE' if invalid else 'MISSING_MARKET_DATE'
        labels = {'day': 'ngày', 'month': 'tháng', 'year': 'năm'}
        request['_calendar_message'] = ('Ngày chưa hợp lệ. Vui lòng nhập ngày đúng, ví dụ 15/10/2026.' if invalid else
                                        'Bạn muốn xem giá vào '+', '.join(labels[name] for name in missing)+' nào? '
                                        'Có thể nhập đầy đủ ngày/tháng/năm, ví dụ 15/10/2026.')
    else:
        request['anchor_day'] = request['day']
    return request
