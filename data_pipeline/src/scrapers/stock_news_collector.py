"""Collect public stock news into JSON with a direct, checked article URL.

Examples:
    python -m pip install "scrapling>=0.4,<1" "requests>=2.32,<3"
    python data_pipeline/src/scrapers/stock_news_collector.py --source cafef
    python data_pipeline/src/scrapers/stock_news_collector.py --source fireant
    python data_pipeline/src/scrapers/stock_news_collector.py --url https://cafef.vn/example.chn

Both sources support general market news and their public stock news tabs.
Each source merges into its own stable JSON file beside this script.
"""

import argparse
import hashlib
import json
import re
import sys
import time
import os
from contextlib import contextmanager, ExitStack
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse
from scrapling.parser import Selector
from news_sources import (cafef_candidates, fireant_candidates, fireant_json,
                          fireant_item, get, plain_text, relevant)


DEFAULT_OUTPUT = Path(__file__).resolve().parent / "stock_news.json"
SOURCE_OUTPUTS = {source: DEFAULT_OUTPUT.with_name(source + '_news.json')
                  for source in ('cafef', 'fireant')}


def read_articles(path, source=None):
    if not path.exists():
        return {}
    previous = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(previous, dict) or not isinstance(previous.get('articles'), list):
        raise ValueError(f'{path}: expected an object with an articles list')
    articles = {}
    for article in previous['articles']:
        if not isinstance(article, dict) or not isinstance(article.get('url'), str):
            raise ValueError(f'{path}: invalid article URL')
        url = clean_url(article['url'])
        actual_source = urlparse(url).hostname.split('.')[0] if url else None
        if not url or article.get('source') != actual_source or (source and source != actual_source):
            raise ValueError(f'{path}: invalid URL or article belongs to another source')
        article['url'] = url
        articles[url] = article
    return articles


def write_payload(path, payload):
    temporary = path.with_suffix(path.suffix + '.tmp')
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def migrate_legacy(legacy=DEFAULT_OUTPUT, outputs=None):
    """Idempotently split existing data; remove the old file only after verification."""
    outputs = SOURCE_OUTPUTS if outputs is None else outputs
    if not legacy.exists():
        return
    with ExitStack() as stack:
        for path in sorted([legacy, *outputs.values()]):
            stack.enter_context(output_lock(path))
        if not legacy.exists():
            return
        old = read_articles(legacy)
        # Validate both destinations before writing either one.
        merged = {source: read_articles(path, source) for source, path in outputs.items()}
        for url, article in old.items():
            source = article['source']
            existing = merged[source].get(url)
            if existing:
                for field in ('symbols', 'matched_symbols', 'scopes'):
                    existing[field] = sorted(set(existing.get(field, [])) | set(article.get(field, [])))
            else:
                merged[source][url] = article
        for source, path in outputs.items():
            payload = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
            payload.update({'schema_version': '1.1', 'source': source,
                            'articles': list(merged[source].values())})
            write_payload(path, payload)
        for source, path in outputs.items():
            saved = read_articles(path, source)
            if not {url for url, a in old.items() if a['source'] == source}.issubset(saved):
                raise ValueError('Migration verification failed; legacy file preserved')
        legacy.unlink()
        print(f'Migrated {len(old)} articles into separate CafeF/FireAnt files')


def clean_url(raw_url: str, base_url: str = "") -> str | None:
    """Return an absolute URL only for a CafeF or FireAnt article page."""
    url = urljoin(base_url, unescape(raw_url.strip()))
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/")
    if parsed.scheme not in {"http", "https"}:
        return None
    if host in {"cafef.vn", "www.cafef.vn"}:
        if not (re.search(r"-\d{10,}\.chn$", path, re.IGNORECASE)
                or re.fullmatch(r"/du-lieu/[A-Za-z0-9]+-\d+/[^/]+\.chn", path)):
            return None
        if path.startswith('/du-lieu/'):
            path = path.lower()
    elif host in {"fireant.vn", "www.fireant.vn"}:
        if not re.fullmatch(r"/bai-viet/[^/]+/\d+", path):
            return None
    else:
        return None
    return urlunparse(("https", host.removeprefix("www."), path, "", "", ""))


def first_text(page, selectors: tuple[str, ...]) -> str:
    for selector in selectors:
        matches = page.css(selector)
        node = matches[0] if matches else None
        if node is not None:
            value = " ".join(node.get_all_text().split())
            if value:
                return value
    return ""


def first_attr(page, selectors: tuple[str, ...], name: str) -> str:
    for selector in selectors:
        matches = page.css(selector)
        node = matches[0] if matches else None
        if node is not None:
            value = node.attrib.get(name, "").strip()
            if value:
                return value
    return ""


def cafef_urls(limit: int) -> list[str]:
    from itertools import islice
    return [item['url'] for item in islice(cafef_candidates(), limit)]


def fireant_urls(limit: int) -> list[str]:
    from itertools import islice
    return [item['url'] for item in islice(fireant_candidates(), limit)]


def fetch_article(url: str, candidate: dict | None = None) -> dict | None:
    source = "cafef" if urlparse(url).hostname == "cafef.vn" else "fireant"
    if source == "fireant":
        row = fireant_json('/posts/' + url.rstrip('/').split('/')[-1])
        if not isinstance(row, dict) or row.get('type') != 1 or not row.get('postID'):
            return None
        item = fireant_item(row)
        final_url = clean_url(item['url'])
        content = plain_text(row.get('content') or row.get('originalContent'))
        if not final_url or not item['title'] or not content:
            return None
        return {
            'id': hashlib.sha256(final_url.encode('utf-8')).hexdigest()[:20],
            'source': source, **item, 'url': final_url, 'content': content,
            'crawled_at': datetime.now(timezone.utc).isoformat(),
        }
    else:
        response = get(url)
        page = Selector(response.text)
    resolved_url = clean_url(str(response.url))
    if not resolved_url:
        return None

    canonical = first_attr(page, ('link[rel="canonical"]',), "href")
    if not canonical:
        canonical = first_attr(page, ('meta[property="og:url"]',), "content")
    final_url = clean_url(canonical, resolved_url) if canonical else resolved_url
    if not final_url or urlparse(final_url).hostname != urlparse(url).hostname:
        return None

    # Disclosure pages use h1 for the company name, not the news headline.
    title = first_attr(page, ('meta[property="og:title"]',), 'content') or first_text(page, ('h1',))
    description = first_attr(
        page, ('meta[name="description"]', 'meta[property="og:description"]'), "content"
    )
    published_at = first_attr(
        page,
        ('meta[property="article:published_time"]', 'meta[name="pubdate"]'),
        "content",
    ) or first_attr(page, ('time[datetime]',), "datetime")
    content = first_text(
        page,
        (
            '#newscontent', '.KenhF_Content_News3',
            ".detail-content", ".contentdetail", ".knc-content", ".news-detail-content", ".content_detail",
            "article .content", "article", '[itemprop="articleBody"]',
        ),
    )
    if not title or not content:
        return None
    return {
        "id": hashlib.sha256(final_url.encode("utf-8")).hexdigest()[:20],
        "source": source,
        "url": final_url,
        "title": title,
        "description": description,
        "content": content,
        "published_at": published_at or None,
        "crawled_at": datetime.now(timezone.utc).isoformat(),
        'attachments': [urljoin(resolved_url, node.attrib['href'])
                        for node in page.css('#newscontent a[href], .detail-content a[href]')
                        if '.pdf' in node.attrib.get('href', '').lower()],
    }


def merge_context(article, candidate, scope):
    article['symbols'] = sorted(set(article.get('symbols', [])) | set(candidate.get('symbols', [])))
    article['matched_symbols'] = sorted(set(article.get('matched_symbols', [])) | set(candidate.get('matched_symbols', [])))
    article['scopes'] = sorted(set(article.get('scopes', [])) | {scope})
    if not article.get('published_at') and candidate.get('published_at'):
        article['published_at'] = candidate['published_at']


@contextmanager
def output_lock(output):
    """Refuse concurrent writers rather than losing one scheduler's updates."""
    lock = output.with_suffix(output.suffix + '.lock')
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, str(os.getpid()).encode('ascii'))
        yield
    finally:
        os.close(fd)
        lock.unlink(missing_ok=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=("cafef", "fireant", "all"), default="cafef")
    parser.add_argument("--url", action="append", default=[], help="Direct article URL; repeatable")
    parser.add_argument('--symbols', nargs='+', default=[], help='Stock tickers, space or comma separated')
    parser.add_argument('--symbol', action='append', default=[], help='Single ticker; repeatable')
    parser.add_argument('--only-symbols', action='store_true', help='Skip general market news')
    parser.add_argument('--prune-irrelevant', action='store_true', help='Remove previously stored off-topic articles; keep symbol/direct scopes')
    parser.add_argument('--max-pages', type=int, default=5, help='Maximum discovery pages per source/symbol')
    parser.add_argument("--limit", type=int, default=10, help="Maximum valid articles per source and scope, including already stored articles")
    parser.add_argument("--output", type=Path, help='Custom JSON filename; all sources use <stem>_cafef.json and <stem>_fireant.json')
    args = parser.parse_args(argv)
    if args.limit < 1 or args.max_pages < 1:
        parser.error('--limit and --max-pages must be at least 1')
    symbols = list(dict.fromkeys(s.upper() for raw in args.symbols + args.symbol
                                for s in raw.split(',') if s))
    if any(not re.fullmatch(r'[A-Z][A-Z0-9]{1,9}', s) for s in symbols):
        parser.error('Invalid stock ticker')
    if args.only_symbols and not symbols:
        parser.error('--only-symbols requires --symbols or --symbol')
    if args.output:
        args.output = args.output.resolve()
    if args.output and (not args.output.is_relative_to(DEFAULT_OUTPUT.parent) or args.output.suffix.lower() != '.json'):
        parser.error('--output must be a JSON file inside the scrapers directory')
    groups = []
    if args.url:
        for raw_url in args.url:
            url = clean_url(raw_url)
            if not url:
                parser.error(f"Not a supported direct article URL: {raw_url}")
            groups.append((urlparse(url).hostname.split('.')[0], 'direct', iter([{'url': url}])))
    else:
        for source, discover in [('cafef', cafef_candidates), ('fireant', fireant_candidates)]:
            if args.source not in (source, 'all'):
                continue
            for symbol in ([] if args.only_symbols else [None]) + symbols:
                groups.append((source, symbol or 'market', discover(symbol, args.max_pages)))
    selected_sources = list(dict.fromkeys(source for source, _, _ in groups))
    outputs = {source: (args.output if len(selected_sources) == 1 else
                       args.output.with_name(args.output.stem + '_' + source + '.json'))
               if args.output else SOURCE_OUTPUTS[source] for source in selected_sources}
    if args.output and any(path in {DEFAULT_OUTPUT, *SOURCE_OUTPUTS.values()} and
                           path != SOURCE_OUTPUTS[source] for source, path in outputs.items()):
        parser.error('--output cannot use a legacy or another source\'s reserved filename')
    try:
        if args.output is None:
            migrate_legacy()
    except (OSError, ValueError, TypeError) as exc:
        print(f'Legacy migration failed; legacy file preserved: {exc}', file=sys.stderr)
        return 1
    status = 0
    for source, output in outputs.items():
        source_args = argparse.Namespace(**vars(args))
        source_args.output = output
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            with output_lock(output):
                status |= collect(source_args, [group for group in groups if group[0] == source])
        except FileExistsError:
            print(f'Another collector is writing {output}. If it crashed, remove its .lock file after verifying it stopped.', file=sys.stderr)
            status = 1
        except (OSError, ValueError, TypeError) as exc:
            print(f'{source} collection failed; existing output preserved: {exc}', file=sys.stderr)
            status = 1
    return status


def collect(args, groups):

    source = groups[0][0]
    articles = read_articles(args.output, source)

    if args.prune_irrelevant:
        kept = {url: article for url, article in articles.items()
                if article.get('matched_symbols') or 'direct' in article.get('scopes', []) or relevant(article)}
        print(f'Filtered {len(articles) - len(kept)} previously stored off-topic articles')
        articles = kept
    added = 0
    report = []
    fetched = {}
    for source, scope, candidates in groups:
        accepted = 0
        errors = 0
        seen = set()
        try:
            for candidate in candidates:
                url = clean_url(candidate.get('url', ''))
                if not url or url in seen:
                    continue
                seen.add(url)
                article = articles.get(url) or fetched.get(url)
                if article is None or not article.get('content'):
                    try:
                        time.sleep(0.2)
                        article = fetch_article(url, candidate)
                        if article is None:
                            errors += 1
                            print(f'Skipped unreadable article: {url}', file=sys.stderr)
                            continue
                        fetched[url] = article
                    except Exception as exc:
                        errors += 1
                        print(f'Failed to fetch {url}: {exc}', file=sys.stderr)
                        continue
                # Symbol tabs provide explicit association; direct URLs are intentional.
                if scope == 'market' and not relevant({**article, 'symbols': candidate.get('symbols', [])}):
                    continue
                merge_context(article, candidate, scope)
                if article['url'] not in articles:
                    added += 1
                articles[article['url']] = article
                accepted += 1
                if accepted >= args.limit:
                    break
        except Exception as exc:
            errors += 1
            print(f'{source}/{scope} discovery failed: {exc}', file=sys.stderr)
        report.append({'source': source, 'scope': scope, 'accepted': accepted,
                       'limit': args.limit, 'errors': errors})
        print(f'{source}/{scope}: {accepted}/{args.limit} valid articles; {errors} errors')
        if accepted < args.limit:
            print(f'{source}/{scope}: quota not filled within discovery bound (--max-pages {args.max_pages})', file=sys.stderr)

    if not articles:
        print("No valid articles found; output was not changed", file=sys.stderr)
        return 1
    if not any(row['accepted'] for row in report):
        print('No usable articles this run; output was not changed', file=sys.stderr)
        return 1
    payload = {"schema_version": "1.1", "source": source, "articles": list(articles.values()),
               'last_run': {'at': datetime.now(timezone.utc).isoformat(), 'results': report}}
    write_payload(args.output, payload)
    print(f"Saved {len(articles)} articles ({added} new) to {args.output}")
    return int(any(row['errors'] or row['accepted'] < args.limit for row in report))


if __name__ == "__main__":
    raise SystemExit(main())
