"""Sparse Okapi BM25 and reciprocal-rank fusion; no I/O or model loading."""
import math
import re
import unicodedata
from collections import Counter, defaultdict

TOKENIZER_VERSION = 'vi-fold-v1'


def tokenize(text):
    if not isinstance(text, str):
        raise TypeError('text must be a string')
    folded = unicodedata.normalize('NFKC', text).casefold().replace('đ', 'd')
    folded = ''.join(c for c in unicodedata.normalize('NFKD', folded)
                     if not unicodedata.combining(c))
    return re.findall(r'[^\W_]+', folded, flags=re.UNICODE)


def _number(value, low, high):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError('numeric parameter required')
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError('numeric parameter out of range')
    return float(value)


def _limit(value):
    if type(value) is not int or not 1 <= value <= 10000:
        raise ValueError('limit must be an integer between 1 and 10000')


class BM25Index:
    def __init__(self, documents, k1=1.5, b=0.75):
        self.k1 = _number(k1, 1e-9, 100)
        self.b = _number(b, 0, 1)
        if not isinstance(documents, dict):
            raise TypeError('documents must map IDs to token lists')
        self.lengths = {}
        self.postings = defaultdict(dict)
        for cid, tokens in documents.items():
            if not isinstance(cid, str) or not cid.strip():
                raise ValueError('document IDs must be nonblank strings')
            if not isinstance(tokens, list) or any(not isinstance(t, str) or not t for t in tokens):
                raise ValueError('tokens must be lists of nonempty strings')
            self.lengths[cid] = len(tokens)
            for term, frequency in Counter(tokens).items():
                self.postings[term][cid] = frequency
        n = len(self.lengths)
        self.average_length = sum(self.lengths.values()) / n if n else 0
        self.idf = {term: math.log1p((n - len(posting) + .5) / (len(posting) + .5))
                    for term, posting in self.postings.items()}

    def search(self, query, limit=50, allowed_ids=None):
        _limit(limit)
        if allowed_ids is not None and (not isinstance(allowed_ids, set)
                or any(not isinstance(cid, str) for cid in allowed_ids)):
            raise ValueError('allowed_ids must be a set of string IDs')
        scores = defaultdict(float)
        for term in sorted(set(tokenize(query))):
            for cid, tf in self.postings.get(term, {}).items():
                if allowed_ids is not None and cid not in allowed_ids:
                    continue
                norm = self.k1 * (1 - self.b + self.b * self.lengths[cid] / self.average_length)
                scores[cid] += self.idf[term] * tf * (self.k1 + 1) / (tf + norm)
        return sorted(((cid, score) for cid, score in scores.items() if score > 0),
                      key=lambda item: (-item[1], item[0]))[:limit]


def rrf(dense, lexical, limit=10, k=60.0, dense_weight=1.0, lexical_weight=1.0):
    _limit(limit)
    k = _number(k, 1e-9, 1e6)
    weights = [_number(w, 0, 1e6) for w in (dense_weight, lexical_weight)]
    if not any(weights):
        raise ValueError('at least one branch must have positive weight')
    results = {}
    for branch, items, weight in zip(('dense', 'bm25'), (dense, lexical), weights):
        if not isinstance(items, list):
            raise TypeError('rankings must be lists of (ID, score) pairs')
        seen = set()
        for item in items:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                raise ValueError('invalid ranked item')
            cid, score = item
            if not isinstance(cid, str) or not cid.strip():
                raise ValueError('chunk ID must be a nonblank string')
            score = _number(score, -1e300, 1e300)
            if cid in seen:
                continue
            seen.add(cid)
            result = results.setdefault(cid, dict(chunk_id=cid, rrf_score=0.0,
                dense_score=None, bm25_score=None, dense_rank=None, bm25_rank=None))
            result[branch + '_score'] = score
            result[branch + '_rank'] = len(seen)
            result['rrf_score'] += weight / (k + len(seen))
    return sorted((r for r in results.values() if r['rrf_score'] > 0),
                  key=lambda r: (-r['rrf_score'], r['chunk_id']))[:limit]
