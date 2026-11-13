"""Chat evidence text for verified BCTC signals. Pure: the passage is written by code, never by the model."""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
import re

NAMES = {
    'revenue_yoy_percent': 'Tăng trưởng doanh thu so với cùng kỳ',
    'profit_yoy_percent': 'Tăng trưởng lợi nhuận sau thuế so với cùng kỳ',
    'operating_cash_flow_yoy_percent': 'Tăng trưởng dòng tiền kinh doanh so với cùng kỳ',
    'net_margin_percent': 'Biên lợi nhuận ròng',
    'liabilities_to_assets_percent': 'Nợ phải trả trên tổng tài sản',
    'roe_percent': 'ROE',
    'roa_percent': 'ROA',
    'nim_percent': 'Biên lãi thuần (NIM)',
    'npl_percent': 'Tỷ lệ nợ xấu',
    'cost_to_income_percent': 'Chi phí trên thu nhập (CIR)',
}
# Plain-language meaning for readers who are not finance specialists; part of the evidence the chatbot quotes.
MEANINGS = {
    'revenue_yoy_percent': 'doanh thu kỳ này so với cùng kỳ năm trước',
    'profit_yoy_percent': 'lợi nhuận sau thuế kỳ này so với cùng kỳ năm trước',
    'operating_cash_flow_yoy_percent': 'tiền thu về từ hoạt động kinh doanh chính so với cùng kỳ năm trước',
    'net_margin_percent': 'mỗi 100 đồng doanh thu còn lại bao nhiêu đồng lợi nhuận',
    'liabilities_to_assets_percent': 'phần tài sản được tài trợ bằng nợ; càng cao càng phụ thuộc vào vay nợ',
    'roe_percent': 'mỗi 100 đồng vốn chủ sở hữu tạo ra bao nhiêu đồng lợi nhuận',
    'roa_percent': 'mỗi 100 đồng tài sản tạo ra bao nhiêu đồng lợi nhuận',
    'nim_percent': 'chênh lệch giữa lãi cho vay và lãi huy động của ngân hàng',
    'npl_percent': 'phần dư nợ cho vay khó thu hồi',
    'cost_to_income_percent': 'chi phí hoạt động trên mỗi đồng thu nhập của ngân hàng',
}
POSITION = {'above': 'cao hơn', 'below': 'thấp hơn', 'equal': 'bằng'}
PERIOD = re.compile(r'^(\d{4})-(YEAR|Q[1-4])$')
MAX_CITATIONS = 5


def _two(value) -> str | None:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return str(number.quantize(Decimal('0.01'), ROUND_HALF_UP)) if number.is_finite() else None


def compact_health(analysis: dict, peers: dict, citations: list) -> dict:
    """Keep what the passage needs: applicable signals (2 decimals), peer median/position, citations."""
    signals = {}
    for name, signal in (analysis.get('signals') or {}).items():
        if name not in NAMES or signal.get('status') == 'not_applicable':
            continue
        peer = (peers.get('metrics') or {}).get(name) or {}
        median = _two(peer.get('peer_median')) if peer.get('peer_median') is not None else None
        signals[name] = dict(value=_two(signal['value']) if signal.get('value') is not None else None,
                             status=signal.get('status'),
                             peer=dict(median=median, position=peer.get('position')) if median else None)
    return dict(period=analysis.get('period'), status=analysis.get('status'), signals=signals,
                citations=list(citations)[:MAX_CITATIONS])


def _period_text(period: str) -> str:
    year, part = PERIOD.match(period).groups()
    return f'năm {year}' if part == 'YEAR' else f'quý {part[1]}/{year}'


def _percent(text: str) -> str:
    return text.replace('.', ',') + '%'


def financial_health_passage(symbol: str, health: dict) -> str:
    lines = [f'Tình hình tài chính {symbol} kỳ {_period_text(health["period"])} '
             f'(tính từ BCTC đã đối chiếu với file BCTC gốc, dữ liệu FinMind):']
    shown, missing = 0, []
    for name, label in NAMES.items():
        signal = health['signals'].get(name)
        if signal is None:
            continue
        if signal['value'] is None:
            missing.append(label if label[:2].isupper() else label[0].lower() + label[1:])
            continue
        shown += 1
        line = f'- {label}: {_percent(signal["value"])}'
        peer = signal.get('peer')
        if peer and peer.get('position') in POSITION:
            line += f' ({POSITION[peer["position"]]} trung vị nhóm cùng ngành ({_percent(peer["median"])}))'
        if signal.get('status') == 'provisional':
            line += ' [tạm tính: nguồn chưa được duyệt]'
        lines.append(f'{line} — {MEANINGS[name]}.')
    if missing:  # one line next to the values, so one short quote covers both
        lines.append(f'- Chưa đủ dữ liệu đã xác minh: {", ".join(missing)}.')
    if not shown:
        lines.append('Chưa có chỉ số tài chính nào đủ dữ liệu đã xác minh cho kỳ này.')
    if health.get('citations'):
        sources = '; '.join(f'{c["title"]} (trang {c["page"]})' for c in health['citations'])
        lines.append(f'Nguồn: {sources}.')
    lines.append('Mô tả từ số liệu đã xác minh, không phải khuyến nghị đầu tư; không có điểm tổng hợp mạnh/yếu.')
    return '\n'.join(lines)
