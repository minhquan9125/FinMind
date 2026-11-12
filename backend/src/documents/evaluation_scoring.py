"""Heuristic scoring of a chat answer against the expected answer of the golden set.

It checks facts, not wording: numbers (Vietnamese or English separators, scaled by "tỷ"/"triệu"),
dates and identifier codes found in the expected answer must appear in the chat answer.
This is an aid for a human reviewer, never a verdict on whether an answer is correct.
"""
from __future__ import annotations

import re

SCALES = {'nghìn tỷ': 1e12, 'ngàn tỷ': 1e12, 'tỷ': 1e9, 'triệu': 1e6, 'nghìn': 1e3, 'ngàn': 1e3}
TOLERANCE = 1e-3          # 0.1 %, the same tolerance the golden file states
PASS_AT, PARTIAL_AT = 0.8, 0.4

_DATE = re.compile(r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b|\b(\d{4})-(\d{2})-(\d{2})\b'
                   r'|\bngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})(?:\s+năm\s+(\d{4}))?', re.I)
_NUMBER = re.compile(r'(?<![\w.,])(\d[\d.,]*\d|\d)(?:\s*(%)|\s+(nghìn tỷ|ngàn tỷ|tỷ|triệu|nghìn|ngàn)\b)?', re.I)
_CODE = re.compile(r'\b[A-Z]{2,6}\d{3,8}\b')


def _dates(text):
    found = set()
    for m in _DATE.finditer(text):
        g = m.groups()
        if g[0]: found.add((int(g[0]), int(g[1]), int(g[2])))
        elif g[3]: found.add((int(g[5]), int(g[4]), int(g[3])))
        else: found.add((int(g[6]), int(g[7]), int(g[8]) if g[8] else None))
    return found


def _candidates(token):
    """All plausible values of one written number; ambiguity ("1,740") yields both readings."""
    token = token.strip('.,')
    if not token: return []
    both = '.' in token and ',' in token
    if both:
        last = max(token.rfind('.'), token.rfind(','))
        decimal = token[last]
        whole = token.replace('.' if decimal == ',' else ',', '')
        return [float(whole.replace(decimal, '.'))]
    out = set()
    for sep in '.,':
        if sep in token:
            parts = token.split(sep)
            grouped = all(len(p) == 3 for p in parts[1:]) and 1 <= len(parts[0]) <= 3
            if grouped:
                out.add(float(''.join(parts)))                     # "3.000" is three thousand in Vietnamese
            if len(parts) == 2 and (sep == ',' or not grouped):
                out.add(float(parts[0] + '.' + parts[1]))          # "171,4" decimal; "1,740" stays ambiguous
            return sorted(out)
    return [float(token)]


def numbers(text):
    """List of candidate-value lists, one per number found (dates removed first)."""
    cleaned = _DATE.sub(' ', text)
    result = []
    for m in _NUMBER.finditer(cleaned):
        try: values = _candidates(m.group(1))
        except ValueError: continue
        scale = SCALES.get((m.group(3) or '').lower(), 1.0)
        percent = bool(m.group(2))
        # Skip bare years and tiny counters: they carry little signal and match by accident.
        plain = [v for v in values if scale == 1.0 and not percent]
        if plain and all(1990 <= v <= 2100 or v < 10 for v in plain): continue
        result.append([v * scale for v in values])
    return result


def _close(a, b):
    return a == b or (a != 0 and abs(a - b) / abs(a) <= TOLERANCE)


def _facts(text):
    return ([('number', n) for n in numbers(text)] + [('date', d) for d in sorted(_dates(text), key=str)]
            + [('code', c) for c in sorted(set(_CODE.findall(text)))])


def _match(fact, answer_numbers, answer_dates, answer_text):
    kind, value = fact
    if kind == 'number': return any(_close(e, a) for e in value for cand in answer_numbers for a in cand)
    if kind == 'date': return any(value == d or (value[2] and d[:2] == value[:2] and d[2] is None) for d in answer_dates)
    return value.lower() in answer_text.lower()


def _label(fact):
    kind, value = fact
    if kind == 'number': return {'kind': kind, 'text': ' / '.join(f'{v:,.4g}' for v in value)}
    if kind == 'date': return {'kind': kind, 'text': '/'.join(str(p) for p in value if p)}
    return {'kind': kind, 'text': value}


def _alternatives(expected):
    """"X (hoặc Y)" gives two ways to be right; the better-matching one is used."""
    parts = re.split(r'\(\s*hoặc\s+|\bhoặc\b', expected, flags=re.I)
    return [p.strip(' )') for p in parts if p.strip(' )')] or [expected]


def refusal_expected(expected):
    """Golden answers that say the system must refuse (no evidence) instead of answering."""
    text = (expected or '').lower()
    return 'safe refusal' in text or text.startswith('không có thông tin')


def score_answer(expected, answer, *, refused=None):
    """{score, level, matched, total, facts}. level: PASS / PARTIAL / FAIL / MANUAL (no checkable fact).

    `refused` tells whether the chat declined to answer; it only matters for refusal questions."""
    answer = answer or ''
    if refusal_expected(expected):
        if refused is None:
            return {'score': None, 'level': 'MANUAL', 'matched': 0, 'total': 0, 'facts': []}
        return {'score': 1.0 if refused else 0.0, 'level': 'PASS' if refused else 'FAIL', 'matched': int(bool(refused)), 'total': 1,
                'facts': [{'kind': 'refusal', 'text': 'Từ chối khi thiếu bằng chứng', 'matched': bool(refused)}]}
    a_numbers, a_dates = numbers(answer), _dates(answer)
    best = None
    for alt in _alternatives(expected):
        facts = _facts(alt)
        if not facts: continue
        results = [(f, _match(f, a_numbers, a_dates, answer)) for f in facts]
        hit = sum(1 for _, ok in results if ok)
        candidate = (hit / len(results), hit, len(results), results)
        if best is None or candidate[:3] > best[:3]: best = candidate
    if best is None:
        return {'score': None, 'level': 'MANUAL', 'matched': 0, 'total': 0, 'facts': []}
    ratio, hit, total, results = best
    level = 'PASS' if ratio >= PASS_AT else 'PARTIAL' if ratio >= PARTIAL_AT else 'FAIL'
    return {'score': round(ratio, 3), 'level': level, 'matched': hit, 'total': total,
            'facts': [{**_label(f), 'matched': ok} for f, ok in results]}
