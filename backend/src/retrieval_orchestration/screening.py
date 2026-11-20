"""Answer "mã/doanh nghiệp/công ty nào đang tăng/phát triển/ngon" with a fact-based list, straight from the DB.

No model writes this answer: every number comes from the stored price trend or the verified BCTC health,
so nothing can be invented. It lists what the data shows; it does not score or recommend.
"""
import re

from .retrieval_flow.intent import _fold, _has

HORIZONS = (('20', 'ngắn hạn'), ('60', 'trung hạn'), ('200', 'dài hạn'))
# "nào", "gì", "mô" (miền Trung) and "j" (viết tắt) ask the same thing.
_SUBJECT = re.compile(r'\b(?:(?:ma|co phieu|doanh nghiep|cong ty)\s+(?:nao|gi|mo|j)|nhung ma|cac ma)\b')
_STATE = re.compile(r'\b(?:dang tang|xu huong|phat trien|tang truong|ngon|tot|manh|khoe|dang dau tu|'
                    r'nen dau tu|trien vong)\b')


def is_screening_question(text, symbols=()):
    """True for a question that asks which companies look good, without naming one."""
    norm = _fold(text)
    if not (_SUBJECT.search(norm) and _STATE.search(norm)):
        return False
    from .hybrid_router.decision_engine import DEFAULT_COMPANIES
    words = {word.upper() for word in re.findall(r'[a-z0-9]+', norm)}
    return not (words.intersection(symbols) or any(_has(norm, alias) for alias in DEFAULT_COMPANIES))


def _pct(value):
    return f'{float(value):+.1f}'.replace('.', ',')


def _period(code):
    match = re.fullmatch(r'(\d{4})(?:-Q([1-4])|-YEAR)?', code or '')
    if not match:
        return code or ''
    return f'quý {match[2]}/{match[1]}' if match[2] else f'năm {match[1]}'


def _trend_section(trends, days, name):
    rising = []
    for symbol, trend in trends.items():
        horizon = ((trend or {}).get('horizons') or {}).get(days) or {}
        if horizon.get('label') == 'UP' and horizon.get('return_percent') is not None:
            rising.append((float(horizon['return_percent']), symbol, horizon))
    if not rising:
        return f'Chưa có mã nào có xu hướng tăng {name} ({days} phiên) theo dữ liệu.'
    items = []
    for _, symbol, horizon in sorted(rising, key=lambda item: (-item[0], item[1])):
        detail = f'{_pct(horizon["return_percent"])}% trong {days} phiên'
        if horizon.get('close_vs_sma_percent') is not None:
            vs = float(horizon['close_vs_sma_percent'])
            detail += f', giá {"trên" if vs >= 0 else "dưới"} SMA{days} {abs(vs):.1f}%'.replace('.', ',')
        items.append(f'{symbol} ({detail})')
    return f'Xu hướng tăng {name} ({days} phiên): ' + ', '.join(items) + '.'


def _growth_section(healths):
    rows = []
    for symbol, health in sorted(healths.items()):
        signals = (health or {}).get('signals') or {}
        parts = []
        for key, word in (('profit_yoy_percent', 'lợi nhuận'), ('revenue_yoy_percent', 'doanh thu')):
            signal = signals.get(key) or {}
            if (signal.get('status') in ('complete', 'provisional') and signal.get('value') is not None
                    and float(signal['value']) > 0):
                parts.append(f'{word} {_pct(signal["value"])}%')
        if parts:
            rows.append(f'{symbol} ({", ".join(parts)} so với cùng kỳ, {_period(health.get("period"))})')
    if not rows:
        return 'Chưa đủ số liệu BCTC đã đối chiếu để so sánh tăng trưởng cùng kỳ.'
    return 'Tăng trưởng so với cùng kỳ (BCTC đã đối chiếu): ' + ', '.join(rows) + '.'


def render_screen(trends, healths, as_of, focus, skipped=0):
    """The screening answer: one line per group, long-term style puts verified growth first."""
    day = '/'.join(reversed(as_of.split('-'))) if as_of else 'gần nhất'
    trend_lines = [_trend_section(trends, days, name) for days, name in HORIZONS]
    growth = _growth_section(healths)
    body = [growth, *trend_lines] if focus == 'FINANCIAL' else [*trend_lines, growth]
    lines = [f'Lọc theo dữ kiện đến ngày {day}:', *('• ' + line for line in body)]
    if skipped:
        lines.append(f'(Bỏ qua {skipped} mã do chưa đọc được dữ liệu.)')
    lines.append('Nguồn: giá giao dịch hằng ngày và BCTC đã đối chiếu trong cơ sở dữ liệu FinMind.')
    return '\n\n'.join(lines)
