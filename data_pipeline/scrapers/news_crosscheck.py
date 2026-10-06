"""Compare stored news across providers; agreement is not factual verification."""
import argparse
import json
import re
import unicodedata
from collections import Counter
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path

from news_storage import SCRAPERS, daily_path

THRESHOLD = 0.8
METHOD = 'word_trigram_dice_content85_title15_v1'


def tokens(text):
    text = unicodedata.normalize('NFC', text or '').casefold()
    # Preserve Vietnamese accents and numbers, including decimal/group separators.
    return re.findall(r'\d+(?:[.,]\d+)*|[^\W\d_]+', text, re.UNICODE)


def features(words):
    size = min(3, len(words))
    return Counter(tuple(words[i:i + size]) for i in range(len(words) - size + 1)) if size else Counter()


def dice(left, right):
    total = sum(left.values()) + sum(right.values())
    return 2 * sum((left & right).values()) / total if total else 0.0


def prepare(article):
    body = tokens(article.get('content'))
    return features(tokens(article.get('title'))), features(body), len(body)


def prepared_similarity(left, right):
    if min(left[2], right[2]) < 5:
        return 0.0
    return 0.85 * dice(left[1], right[1]) + 0.15 * dice(left[0], right[0])


def article_similarity(left, right):
    """Return a 0..1 score; empty/very short bodies cannot corroborate a headline."""
    return prepared_similarity(prepare(left), prepare(right))


def crosscheck_news(root=SCRAPERS, scopes=None):
    """Mark both providers within each scope, across all stored crawl days.

    Locks match collector locks; validate the whole scope before writing it.
    No comparisons between market and a ticker, or between different tickers.
    """
    from stock_news_collector import read_articles, write_payload, output_lock
    root = Path(root).resolve()
    if not root.is_relative_to(SCRAPERS):
        raise ValueError('Cross-check root must be inside scrapers')
    if scopes is None:
        symbol_root = root / 'tin_tuc_theo_ma'
        if not symbol_root.resolve().is_relative_to(SCRAPERS):
            raise ValueError('Symbol directory escapes scrapers')
        scopes = ['market'] + ([p.name for p in symbol_root.iterdir() if p.is_dir()]
                               if symbol_root.exists() else [])
    summary = []
    for scope in sorted(set('market' if s == 'direct' else s for s in scopes)):
        with ExitStack() as stack:
            paths = []
            for source in ('cafef', 'fireant'):
                folder = daily_path(root, source, scope, '01-01-2000').parent
                for path in sorted(folder.glob('*.json')):
                    if not path.resolve().is_relative_to(SCRAPERS):
                        raise ValueError('News file escapes scrapers')
                    datetime.strptime(path.stem, '%d-%m-%Y')
                    paths.append((path, source))
            files = {}
            entries = {'cafef': [], 'fireant': []}
            for path, source in sorted(paths):
                stack.enter_context(output_lock(path))
                rows = read_articles(path, source)
                payload = json.loads(path.read_text(encoding='utf-8'))
                files[path] = payload
                payload['articles'] = list(rows.values())
                for row in payload['articles']:
                    entries[source].append((path, row, prepare(row)))
            best = {}
            for left in entries['cafef']:
                for right in entries['fireant']:
                    score = prepared_similarity(left[2], right[2])
                    for own, peer in ((left, right), (right, left)):
                        key = (own[0], own[1]['url'])
                        if key not in best or score > best[key][0]:
                            best[key] = (score, peer)
            at = datetime.now(timezone.utc).isoformat()
            checked = 0
            for source, rows in entries.items():
                for path, article, _ in rows:
                    score, peer = best.get((path, article['url']), (0.0, None))
                    article['marker'] = 'check' if score > THRESHOLD else 'uncheck'
                    assessment = {
                        'method': METHOD, 'threshold': THRESHOLD, 'score': score,
                        'matched_source': peer[1]['source'] if peer else None,
                        'matched_url': peer[1]['url'] if peer else None,
                        'matched_file': str(peer[0].relative_to(root)).replace('\\', '/') if peer else None,
                        'checked_at': at,
                    }
                    previous = article.get('cross_check', {})
                    if all(previous.get(k) == v for k, v in assessment.items() if k != 'checked_at'):
                        assessment['checked_at'] = previous.get('checked_at', at)
                    article['cross_check'] = assessment
                    checked += article['marker'] == 'check'
            for path, payload in files.items():
                write_payload(path, payload)
            total = sum(len(rows) for rows in entries.values())
            result = {'scope': scope, 'total': total, 'check': checked, 'uncheck': total - checked}
            summary.append(result)
            print(f'Cross-check {scope}: {checked} check, {total - checked} uncheck')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=SCRAPERS)
    parser.add_argument('--scopes', nargs='+')
    args = parser.parse_args()
    crosscheck_news(args.root, args.scopes)
