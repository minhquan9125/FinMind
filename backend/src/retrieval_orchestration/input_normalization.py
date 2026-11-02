"""Conservative, deterministic normalization of user text only, never evidence.

Aliases are configurable. Telex is decoded only into known Vietnamese domain
words; identifiers, money, dates, URLs and explicitly placed tickers are protected.
This is not an unrestricted spellchecker or an LLM call.
"""
from functools import lru_cache
import json
from pathlib import Path
import re

from .retrieval_flow.intent import _fold, TICKERS

TOKEN = re.compile(r'https?://[^\s]+|\b\w[\w.+-]*@[\w.-]+\.[a-z]{2,}|\b\w+\b', re.UNICODE | re.IGNORECASE)
KNOWN_TICKERS = set(TICKERS) | {'SSI', 'CTR', 'VNM', 'MSN', 'NLG', 'LAF', 'DDC', 'FTS'}
ENGLISH_TERMS = {'bar', 'cash', 'assets', 'profit', 'after', 'before', 'tax', 'revenue', 'total',
                 'ratio', 'news', 'source', 'market', 'price', 'close', 'open', 'volume', 'index', 'year', 'quarter'}


@lru_cache(maxsize=1)
def _rules():
    data = json.loads((Path(__file__).parent/'config/input_aliases.json').read_text('utf-8'))
    vocabulary = set(data['telex_vocabulary'].split())
    vocabulary.update(word for phrase in data['aliases'].values() for word in phrase.split())
    vocabulary.update(word for variants in data['contextual_aliases'].values() for phrase in variants for word in phrase.split())
    vocabulary.update(word for phrase in data.get('domain_phrases', []) for word in phrase.split())
    return data, vocabulary


def _shape(word):
    for source, target in (('dd', 'd'), ('uow', 'uo'), ('uw', 'u'), ('ow', 'o'),
                           ('aw', 'a'), ('aa', 'a'), ('ee', 'e'), ('oo', 'o')):
        word = word.replace(source, target)
    return word


@lru_cache(maxsize=8192)
def _telex_candidates(word):
    """Handle vowel shapes and one tone key in either Vietnamese typing order.

    Try tone removal before AND after shape decoding: tone keys may interrupt
    a vowel cluster (chuwsng) or sit at the end of the syllable (chuwngs).
    This is bounded transliteration, never edit-distance correction of tickers.
    """
    candidates = {_shape(word)}
    for candidate in (word, _shape(word)):
        for index, letter in enumerate(candidate):
            if (letter in 'sfrxj' and index > 0
                    and (index == len(candidate)-1 or candidate[index-1] in 'aeiouyw')):
                candidates.add(_shape(candidate[:index]+candidate[index+1:]))
    return tuple(sorted(candidates))


def _telex(word, vocabulary):
    if len(word) > 32 or not re.fullmatch('[a-z]+', word) or word in vocabulary:
        return word
    decoded = [candidate for candidate in _telex_candidates(word)
               if candidate in vocabulary and candidate != word]
    # Ambiguous reductions are left alone rather than selecting an arbitrary word.
    return decoded[0] if len(decoded) == 1 else word


def normalize_user_text(text, context=None):
    data, vocabulary = _rules()
    aliases = data['aliases']
    protected = KNOWN_TICKERS | set(data.get('protected_identifiers', []))
    prefix = []
    folded = _fold(text)
    price_context = (context or {}).get('source_type') == 'PRICE' or bool(re.search(r'\b(?:gia|giaf|co phieu)\b', folded))
    pending_company = str(((context or {}).get('_clarification_state') or {}).get('id', '')).startswith('company:')
    def replace(match):
        token = match[0]
        if token.lower().startswith(('http://', 'https://')) or '@' in token or '_' in token: return token
        compact = re.fullmatch(r'([a-z]+)(\d{1,4})', token)
        if compact:
            stem = aliases.get(compact[1], _telex(compact[1], vocabulary))
            if stem in ('ngay', 'hom', 'thang', 'nam'):
                prefix.extend((stem, compact[2]))
                return stem+' '+compact[2]
        if any(c.isdigit() for c in token): return token
        key = _fold(token)
        decoded = _telex(key, vocabulary)
        if key in ('k', 'tr', 'b', 'm') and re.search(r'\d[\d.,]*\s*$', text[:match.start()]):
            return token  # money/quantity suffix, not conversational shorthand
        explicit_ticker = len(token) == 3 and token.isascii() and token.isalpha() and (
            (prefix and prefix[-1] in ('gia', 'ma', 'cua', 'phieu', 'ck'))
            or re.match(r'^(?:gia|co gia|hom|hoom|quy|nam)\b', _fold(text[match.end():]))
            or (pending_company and text.strip() == token))
        if (token.isascii() and token.isupper() and token in protected
                or token.upper() in protected and key not in aliases and key not in vocabulary and decoded == key
                or token.isascii() and token.isupper() and 3 <= len(token) <= 5 and decoded == key
                or explicit_ticker and _shape(key) == key):
            result = token
        elif key == 'cp':
            if re.search(r'\bcp\s+(?:ban|quan|lai|thue)\b', folded): result = 'chi phi'
            elif price_context or 'gia' in prefix or 'phieu' in prefix or re.search(r'\bcp\s+[A-Z]{3}\b', text): result = 'co phieu'
            else: result = token
        elif key == 'hn':
            result = 'ha noi' if prefix and prefix[-1] in ('o', 'tai', 'tp', 'ubnd') else ('hom nay' if price_context or 'gia' in prefix or 'phieu' in prefix or 'tin' in folded else token)
        elif key == 'dt':
            if re.search(r'\b(?:dong tien|hoat dong|du an)\s+dt\b', folded): result = 'dau tu'
            elif re.search(r'\bdt\s+[A-Za-z]{3}\s+(?:quy|q\d|nam)', text, re.I): result = 'doanh thu'
            else: result = token
        elif key in ('dk', 'đk'):
            if re.match(r'^(?:doanh nghiep|kinh doanh|tai khoan)', _fold(text[match.end():])): result = 'dang ky'
            elif prefix and prefix[-1] in ('khong', 'co', 'chua'): result = 'duoc'
            else: result = token
        elif key == 'bh':
            result = 'bay gio' if price_context else token
        elif key == 'tr':
            result = token  # triệu/trước is ambiguous; trc is unambiguous
        elif key in aliases:
            result = aliases[key]
        elif key in ENGLISH_TERMS:
            result = token
        elif token.isascii():
            result = decoded
        else:
            result = token
        prefix.extend(_fold(result).split())
        del prefix[:-5]
        return result
    result = TOKEN.sub(replace, text)
    return result if len(result) <= 8000 else text  # never truncate user words or numbers
