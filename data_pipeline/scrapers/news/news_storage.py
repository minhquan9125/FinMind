"""Daily news storage, restricted to the scrapers directory."""
import json
import re
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRAPERS = Path(__file__).resolve().parents[1]
DATA_ROOT = SCRAPERS / 'data'
VIETNAM = timezone(timedelta(hours=7))


def crawl_day(value=None):
    if value is None:
        return datetime.now(VIETNAM).strftime('%d-%m-%Y')
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('crawled_at must include a timezone')
    return stamp.astimezone(VIETNAM).strftime('%d-%m-%Y')


def daily_path(root, source, scope, day):
    root = Path(root).resolve()
    if not root.is_relative_to(SCRAPERS):
        raise ValueError('Output directory must be inside scrapers')
    if source not in ('cafef', 'fireant'):
        raise ValueError('Invalid news source')
    datetime.strptime(day, '%d-%m-%Y')
    if scope in ('market', 'direct'):
        folder = root / 'tin_tuc_chung' / source
    elif re.fullmatch(r'[A-Z][A-Z0-9]{1,9}', scope):
        folder = root / 'tin_tuc_theo_ma' / scope / source
    else:
        raise ValueError('Invalid stock ticker')
    path = folder / (day + '.json')
    if not path.resolve().is_relative_to(SCRAPERS):
        raise ValueError('Output path escapes scrapers')
    return path


def merge_article(existing, incoming):
    merged = {**incoming, **existing}
    for field in ('symbols', 'matched_symbols', 'scopes', 'attachments'):
        if field in existing or field in incoming:
            merged[field] = sorted(set(existing.get(field, [])) | set(incoming.get(field, [])))
    return merged


def migrate_daily(root, legacy_paths, read_articles, write_payload, output_lock):
    """Validate all inputs first, then copy/verify before removing legacy files.

    An interrupted migration is safe to rerun: destinations merge by URL.
    """
    legacy_paths = [Path(p).resolve() for p in legacy_paths]
    if any(not p.is_relative_to(SCRAPERS) for p in legacy_paths):
        raise ValueError('Legacy files must be inside scrapers')
    with ExitStack() as stack:
        inputs = [p for p in legacy_paths if p.exists()]
        for path in sorted(inputs):
            stack.enter_context(output_lock(path))
        routed = {}
        for path in inputs:
            for article in read_articles(path).values():
                day = crawl_day(article.get('crawled_at')) if article.get('crawled_at') else None
                if day is None:
                    raise ValueError(f'{path}: missing crawled_at; cannot determine crawl day')
                scopes = set(article.get('scopes', [])) | set(article.get('matched_symbols', []))
                if not scopes:
                    scopes = {'market'}
                for scope in scopes:
                    target = daily_path(root, article['source'], scope, day)
                    bucket = routed.setdefault(target, {})
                    bucket[article['url']] = merge_article(bucket.get(article['url'], {}), article)
        merged = {}
        payloads = {}
        for target in sorted(routed):
            target.parent.mkdir(parents=True, exist_ok=True)
            stack.enter_context(output_lock(target))
            source = next(iter(routed[target].values()))['source']
            merged[target] = read_articles(target, source)
            for url, article in routed[target].items():
                merged[target][url] = merge_article(merged[target].get(url, {}), article)
            payloads[target] = json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
        for target, articles in merged.items():
            payload = payloads[target]
            payload.update({'schema_version': '1.2', 'source': next(iter(articles.values()))['source'],
                            'crawl_date': target.stem, 'timezone': 'Asia/Ho_Chi_Minh',
                            'articles': list(articles.values())})
            write_payload(target, payload)
        for target, articles in merged.items():
            if read_articles(target) != articles:
                raise ValueError('Migration verification failed; legacy files preserved')
        for path in inputs:
            path.unlink()
        if inputs:
            print(f'Migrated {len(inputs)} legacy files into {len(routed)} daily JSON files')
