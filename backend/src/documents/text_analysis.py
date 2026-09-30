"""Lexical analysis helpers: tokenization, stopword filtering and the
TF/DF/IDF bookkeeping used to power the "chunk detail" and "vocabulary"
panels in the UI.

These utilities are display/explainability aids only (they reproduce the
walkthrough the original TF-IDF browser demo showed the user). They are NOT
used to score search results anymore - ranking now comes from BAAI/bge-m3
dense embeddings compared with pgvector cosine distance (see embeddings.py
and repository.py), per ADR04 in the project proposal. Keeping this module
lets the UI still show "why this word matters" without re-introducing a
second, competing retrieval method.
"""

from collections import Counter
from dataclasses import dataclass
import math

# Same stopword list as the original demo (VectorRAG_Demo.html), kept
# unchanged so the "words removed" trace shown to the user does not change.
STOPWORDS: set[str] = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with",
    "is", "are", "was", "were", "be", "been", "this", "that", "it", "as", "by",
    "at", "from", "which", "also", "not",
    "có", "là", "và", "của", "cho", "được", "trong", "một", "các", "những",
    "này", "đó", "khi", "đã", "sẽ", "với", "để", "về", "theo", "như", "nên",
    "thì", "mà", "hay", "hoặc", "tại", "trên", "dưới", "ra", "vào", "đến",
    "từ", "nhưng", "nếu", "vì", "do", "bị", "bởi", "họ", "tôi", "chúng", "ta", "nó",
}


def raw_words(text: str) -> list[str]:
    """Split text into maximal runs of unicode letters/digits, equivalent to
    the JS regex /[\\p{L}\\p{N}]+/gu used in the original demo."""
    text = text.lower()
    words: list[str] = []
    current: list[str] = []
    for ch in text:
        if ch.isalnum():
            current.append(ch)
        elif current:
            words.append("".join(current))
            current = []
    if current:
        words.append("".join(current))
    return words


def tokenize(text: str) -> list[str]:
    return [w for w in raw_words(text) if len(w) > 1 and w not in STOPWORDS]


@dataclass
class TraceWord:
    word: str
    kept: bool
    reason: str | None = None


def tokenize_with_trace(text: str) -> list[TraceWord]:
    out: list[TraceWord] = []
    for w in raw_words(text):
        if len(w) <= 1:
            out.append(TraceWord(word=w, kept=False, reason="too short (1 character)"))
        elif w in STOPWORDS:
            out.append(TraceWord(word=w, kept=False, reason="stopword"))
        else:
            out.append(TraceWord(word=w, kept=True))
    return out


def term_frequencies(chunk_texts: list[str]) -> tuple[list[Counter], Counter, Counter]:
    """Return (per-chunk TF counters, document-frequency counter, total-term-
    frequency counter) across all chunks of a document."""
    tf_list: list[Counter] = []
    df: Counter = Counter()
    ttf: Counter = Counter()
    for text in chunk_texts:
        tokens = tokenize(text)
        tf = Counter(tokens)
        tf_list.append(tf)
        for token, freq in tf.items():
            df[token] += 1
            ttf[token] += freq
    return tf_list, df, ttf


def idf_weights(df: Counter, doc_count: int) -> dict[str, float]:
    """Smoothed IDF, same formula as the demo: ln((1+N)/(1+df)) + 1."""
    return {token: math.log((1 + doc_count) / (1 + freq)) + 1 for token, freq in df.items()}


def top_terms_for_chunk(tf: Counter, idf: dict[str, float], limit: int = 6) -> list[tuple[str, float]]:
    """TF*IDF weighted keywords for one chunk, used only as a human-readable
    summary in the "chunk detail" panel (not for ranking)."""
    weighted = [(token, freq * idf.get(token, 0.0)) for token, freq in tf.items()]
    weighted.sort(key=lambda pair: pair[1], reverse=True)
    return weighted[:limit]
