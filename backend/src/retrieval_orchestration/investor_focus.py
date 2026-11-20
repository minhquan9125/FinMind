"""The user's investing style (short-term/technical or long-term/fundamental) for chat analysis.

The style only changes which analysis groups are emphasized; it never turns into buy/sell advice.
Words are matched on folded text (no diacritics), so unaccented typing works. Ambiguous words are
only accepted inside a phrase ("đầu tư giá trị", never "giá trị" alone).
"""
import re

from .retrieval_flow.intent import _fold

FOCUS_LABEL = {'TECHNICAL': 'ngắn hạn (kỹ thuật)', 'FINANCIAL': 'dài hạn (cơ bản)'}

_WORDS = {
    'TECHNICAL': (
        r'luot song', r'ngan han', r'trading', r'trade', r'swing', r'dau co', r'danh nhanh', r'an nhanh',
        r'chot loi nhanh', r't\+\d?', r'ky thuat', r'phan tich ky thuat', r'chart', r'do thi gia', r'bieu do gia',
        # "nến" folds to "nen" like "nên"/"nền": only candle phrases count.
        r'bieu do nen', r'mo hinh nen', r'cay nen', r'nen (?:ngay|tuan|xanh|do|nhat)', r'mau hinh', r'vung ho tro', r'nguong ho tro', r'khang cu', r'diem vao', r'diem ra', r'breakout',
        r'but pha', r'momentum', r'da tang', r'da giam', r'dong tien ngan han', r'rsi', r'macd', r'bollinger',
        r'sma\d*', r'ema\d*', r'duong trung binh',
    ),
    'FINANCIAL': (
        r'dai han', r'trung dai han', r'dau tu gia tri', r'dau tu tang truong', r'nam giu', r'giu lau',
        r'buy and hold', r'tich san', r'tich luy dai han', r'phan tich co ban', r'yeu to co ban',
        r'nen tang doanh nghiep', r'suc khoe doanh nghiep', r'suc khoe tai chinh', r'co tuc', r'dividend',
        r'dinh gia', r'p/?e', r'p/?b', r'tang truong ben vung', r'loi nhuan ben vung', r'bien loi nhuan',
        r'dong tien kinh doanh', r'don bay', r'no vay', r'an toan von', r'chat luong tai san', r'no xau',
    ),
}
_PATTERNS = {focus: re.compile(r'(?<![\w+/])(?:' + '|'.join(words) + r')(?![\w+/])') for focus, words in _WORDS.items()}
# A stated style is "<I> [a few habit words] <style phrase>": metric words ("cổ tức", "nợ xấu") are questions,
# not styles, and any other word in between (không, muốn biết, theo dõi, hãy phân tích) means it is no statement.
_SELF = r'\b(?:toi|minh|em|anh)'
_GAP = r'(?:\s+(?:dang|thuong|hay|chu yeu|chi|van|luon|la|nha|nguoi|kieu|thich|choi|uu tien|chuyen|von))*'
_STATED = {
    'TECHNICAL': r'(?:dau tu |choi )?ngan han|luot song|trade|trading|swing|dau co|danh nhanh|an nhanh|'
                 r'theo phan tich ky thuat',
    'FINANCIAL': r'(?:dau tu |choi )?(?:trung )?dai han|dau tu gia tri|dau tu tang truong|dau tu co tuc|tich san|'
                 r'tich luy dai han|buy and hold|giu lau|theo phan tich co ban',
}
_STATEMENT = {focus: re.compile(_SELF + _GAP + r'\s+(?:' + phrase + r')\b') for focus, phrase in _STATED.items()}
_COMMAND = re.compile(r'\bphan tich theo huong (?:ngan han|ky thuat|dai han|co ban)\b')
_RESET = re.compile(r'\b(?:phan tich chung(?! khoan)|bo huong dau tu|khong theo huong nao|bo phong cach dau tu)\b')
_FILLER = {'nhe', 'nha', 'a', 'oi', 'thoi', 'nhe', 'ha', 'day', 'roi', 'vay', 'thi', 'va', 'con', 'di', 'nua', 'u', 'vang'}


def focus_from_words(norm):
    """'TECHNICAL', 'FINANCIAL' or None (no style word, or words of both styles) for folded text."""
    found = [focus for focus, pattern in _PATTERNS.items() if pattern.search(norm)]
    return found[0] if len(found) == 1 else None


def _only_filler(norm):
    return set(re.findall(r'[a-z0-9]+', norm)) <= _FILLER


def parse_statement(text):
    """(style, rest): style is 'TECHNICAL', 'FINANCIAL', 'RESET' or None; rest is the message without the
    clauses that only state the style ('' when nothing else was asked). A reset inside a longer question
    ("phân tích chung VCB") is 'RESET' with the whole question kept as rest."""
    norm = _fold(text)
    reset = _RESET.search(norm)
    if reset:
        return 'RESET', '' if _only_filler(norm[:reset.start()] + norm[reset.end():]) else text.strip()
    clauses = re.split(r'(?<=[,.;!?\n])', text)
    found, rest = set(), []
    for clause in clauses:
        folded = _fold(clause)
        command = _COMMAND.search(folded)
        hits = ([(focus_from_words(command[0]), command)] if command else
                [(focus, match) for focus, pattern in _STATEMENT.items() for match in [pattern.search(folded)] if match])
        if len(hits) == 1 and hits[0][0]:
            focus, match = hits[0]
            found.add(focus)
            if _only_filler(folded[:match.start()] + folded[match.end():]):
                continue                     # this clause only states the style
        rest.append(clause)
    if len(found) != 1:
        return None, text.strip()
    return found.pop(), ''.join(rest).strip(' ,.;\n')


def stated_focus(text):
    """The style the user states about themself, 'RESET', or None. A question using a style word states nothing."""
    return parse_statement(text)[0]


def is_focus_only(text):
    """True when the message only states a style, so there is nothing to look up."""
    focus, rest = parse_statement(text)
    return focus in _STATED and not rest
