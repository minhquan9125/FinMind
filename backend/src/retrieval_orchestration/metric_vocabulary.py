"""The metric vocabulary of the chat parser.

Two sources, in this order:
  1. curated aliases: how users actually name the common metrics;
  2. the catalog used at ingestion (`financial.mapping`): the label printed on every statement row.

So any labelled row that exists in the data can be asked for by its label, without adding code per metric.
A phrase inside a longer recognized phrase is ignored ("vốn chủ sở hữu" inside "tỷ suất lợi nhuận trên
vốn chủ sở hữu"), which keeps a short alias from answering a question about a different, longer metric.
"""
from functools import lru_cache
import re

from ..financial.mapping import METRIC_LABELS_VI, SECTION_MAPS, INDUSTRY_SECTION_MAPS
from .retrieval_flow.intent import _fold

# Explicit semantic aliases; unrelated financial rows must never stand in for a metric.
CURATED = {
    'TOTAL_ASSETS': ('tổng tài sản', 'total assets'),
    'CASH_AND_CASH_EQUIVALENTS': ('tiền và các khoản tương đương tiền', 'tiền và tương đương tiền', 'cash and cash equivalents'),
    'SHORT_TERM_LOANS_AND_FINANCE_LEASES': ('vay và nợ thuê tài chính ngắn hạn', 'nợ vay ngắn hạn'),
    'LONG_TERM_LOANS_AND_FINANCE_LEASES': ('vay và nợ thuê tài chính dài hạn', 'nợ vay dài hạn'),
    'CURRENT_LIABILITIES': ('nợ ngắn hạn', 'current liabilities'),
    'NON_CURRENT_LIABILITIES': ('nợ dài hạn', 'non-current liabilities'),
    'RETAINED_EARNINGS': ('lợi nhuận sau thuế chưa phân phối', 'lợi nhuận chưa phân phối', 'retained earnings'),
    'NET_REVENUE': ('doanh thu thuần', 'net revenue'),
    'GROSS_REVENUE': ('doanh thu bán hàng và cung cấp dịch vụ', 'doanh thu trước giảm trừ', 'gross revenue'),
    'PROFIT_BEFORE_TAX': ('lợi nhuận trước thuế', 'profit before tax', 'LNTT'),
    'PROFIT_AFTER_TAX': ('lợi nhuận sau thuế', 'profit after tax', 'LNST'),
    'PARENT_NET_PROFIT': ('lợi nhuận sau thuế thuộc cổ đông công ty mẹ',
                          'lợi nhuận sau thuế của cổ đông công ty mẹ',
                          'LNST cổ đông công ty mẹ', 'LNST thuộc cổ đông công ty mẹ', 'LNST công ty mẹ', 'parent net profit'),
    'CASH_FLOW_OPERATING': ('lưu chuyển tiền thuần từ hoạt động kinh doanh', 'dòng tiền hoạt động kinh doanh', 'cash flow from operating activities'),
    'CASH_FLOW_INVESTING': ('lưu chuyển tiền thuần từ hoạt động đầu tư', 'dòng tiền hoạt động đầu tư', 'cash flow from investing activities'),
    'CASH_FLOW_FINANCING': ('lưu chuyển tiền thuần từ hoạt động tài chính', 'dòng tiền hoạt động tài chính', 'cash flow from financing activities'),
    'CHARTER_CAPITAL': ('vốn điều lệ', 'charter capital'),
    'TOTAL_LIABILITIES': ('tổng nợ phải trả', 'nợ phải trả'),
    # The data names this row OWNERS_EQUITY; a code that no statement row carries can never be answered.
    'OWNERS_EQUITY': ('tổng vốn chủ sở hữu', 'vốn chủ sở hữu'),
}

# Names and abbreviations users say for catalog rows whose printed label is different or missing.
COMMON_NAMES = {
    'BASIC_EARNINGS_PER_SHARE': ('EPS', 'lãi cơ bản trên mỗi cổ phiếu', 'thu nhập trên mỗi cổ phiếu'),
    'ROE': ('ROE', 'tỷ suất sinh lời trên vốn chủ sở hữu', 'tỷ suất sinh lợi trên vốn chủ sở hữu'),
    'ROA': ('ROA', 'tỷ suất sinh lời trên tổng tài sản', 'tỷ suất sinh lời trên tài sản', 'tỷ suất lợi nhuận trên tổng tài sản'),
    'GROSS_MARGIN': ('biên lợi nhuận gộp', 'gross margin'),
    'PURCHASE_FIXED_ASSETS': ('tiền chi để mua sắm xây dựng tài sản cố định', 'tiền chi mua sắm xây dựng tài sản cố định',
                              'chi mua sắm xây dựng tài sản cố định', 'mua sắm xây dựng tài sản cố định',
                              'chi mua sắm tài sản cố định', 'mua sắm tài sản cố định', 'capex'),
}

# A metric named by words that may sit apart: "lợi nhuận sau thuế ... phân bổ cho cổ đông của công ty mẹ".
PATTERNS = {
    'PARENT_NET_PROFIT': r'(?:loi nhuan|lnst)\b[a-z ]{0,60}?\bco dong (?:cua )?cong ty me\b',
}

_PUNCTUATION = re.compile(r'[,;:()\[\]"\'?!–—]+')


def plain(norm):
    """Folded text with punctuation as spaces, so "mua sắm, xây dựng" matches "mua sắm xây dựng"."""
    return ' '.join(_PUNCTUATION.sub(' ', norm).split())


@lru_cache(maxsize=1)
def vocabulary():
    """code -> aliases (unfolded). Curated first; a catalog label joins only when no other code owns that phrase."""
    words = {code: list(aliases) for code, aliases in CURATED.items()}
    for code, aliases in COMMON_NAMES.items():
        words.setdefault(code, []).extend(aliases)
    owned = {plain(_fold(alias)) for aliases in words.values() for alias in aliases}
    for code, label in METRIC_LABELS_VI.items():
        phrase = plain(_fold(label))
        if phrase and phrase not in owned and phrase != plain(_fold(code)) and len(phrase.split()) >= 2:
            words.setdefault(code, []).append(label)
            owned.add(phrase)
    return {code: tuple(aliases) for code, aliases in words.items()}


@lru_cache(maxsize=1)
def _matchers():
    matchers = []
    for code, aliases in vocabulary().items():
        phrases = sorted({plain(_fold(alias)) for alias in (*aliases, code)}, key=len, reverse=True)
        parts = [re.escape(phrase) for phrase in phrases]
        if code in PATTERNS:
            parts.insert(0, PATTERNS[code])
        matchers.append((code, re.compile(r'\b(?:' + '|'.join(parts) + r')\b')))
    return matchers


def metric_spans(norm):
    """(start, end, code) of every recognized metric phrase in the plain folded text, without nested ones."""
    text = plain(norm)
    spans = [(m.start(), m.end(), code) for code, pattern in _matchers() for m in pattern.finditer(text)]
    return sorted(s for s in spans if not any(
        o is not s and o[0] <= s[0] and s[1] <= o[1] and o[1] - o[0] > s[1] - s[0] for o in spans))


def find_metrics(norm):
    """Metric codes named in the folded question, in order of appearance."""
    return list(dict.fromkeys(code for _, _, code in metric_spans(norm)))


def without_metrics(norm):
    """The plain folded text with every recognized metric phrase removed."""
    text, out, at = plain(norm), [], 0
    for start, end, _ in metric_spans(norm):
        if start >= at:
            out.append(text[at:start])
            at = end
    out.append(text[at:])
    return ' '.join(' '.join(out).split())


@lru_cache(maxsize=1)
def vocabulary_words():
    """Every word used by a metric name; such a word is never a ticker by itself."""
    return frozenset(word for aliases in vocabulary().values() for alias in aliases for word in plain(_fold(alias)).split())


@lru_cache(maxsize=1)
def point_in_time_codes():
    """Balance-sheet rows and ratios describe a date, not a flow over the period."""
    codes = set()
    for maps in (SECTION_MAPS, *INDUSTRY_SECTION_MAPS.values()):
        for section in ('balance_sheet', 'ratios'):
            codes |= set((maps.get(section) or {}).values())
    return frozenset(codes)


def label(code):
    """A Vietnamese display name for a metric code."""
    if code in CURATED:
        return CURATED[code][0]
    if code in METRIC_LABELS_VI:
        return METRIC_LABELS_VI[code]
    names = [name for name in COMMON_NAMES.get(code, ()) if ' ' in name]
    return names[0] if names else code
