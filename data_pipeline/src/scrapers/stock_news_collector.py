"""Collect public stock news into JSON with a direct, checked article URL.

Examples:
    python -m pip install "scrapling[fetchers]>=0.4,<1"
    scrapling install
    python data_pipeline/src/scrapers/stock_news_collector.py --source cafef
    python data_pipeline/src/scrapers/stock_news_collector.py --source fireant
    python data_pipeline/src/scrapers/stock_news_collector.py --url https://cafef.vn/example.chn

The FireAnt source uses the public "Bài viết & tin tức" section on its home
page. Since that section is rendered by JavaScript, install Scrapling's browser
dependencies first.
"""

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse
from xml.etree import ElementTree

import requests
from scrapling.fetchers import DynamicFetcher, Fetcher


DEFAULT_OUTPUT = Path(__file__).resolve().parent / "stock_news.json"
CAFEF_RSS = "https://cafef.vn/thi-truong-chung-khoan.rss"
FIREANT_HOME = "https://fireant.vn/"
USER_AGENT = "FinMind public news collector/1.0"


def clean_url(raw_url: str, base_url: str = "") -> str | None:
    """Return an absolute URL only for a CafeF or FireAnt article page."""
    url = urljoin(base_url, unescape(raw_url.strip()))
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/")
    if parsed.scheme not in {"http", "https"}:
        return None
    if host in {"cafef.vn", "www.cafef.vn"}:
        if not re.search(r"-\d{10,}\.chn$", path, re.IGNORECASE):
            return None
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
    response = requests.get(CAFEF_RSS, timeout=20, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    root = ElementTree.fromstring(response.content)
    urls = []
    for item in root.findall(".//item"):
        url = clean_url(item.findtext("link") or "")
        if url and url not in urls:
            urls.append(url)
        if len(urls) >= limit:
            break
    return urls


def fireant_urls(limit: int) -> list[str]:
    page = DynamicFetcher.fetch(FIREANT_HOME, headless=True, wait=2000, timeout=30000)
    if page.status != 200:
        raise RuntimeError(f"FireAnt home returned HTTP {page.status}")
    news_section = next(
        (section for section in page.css("section")
         if "Bài viết & tin tức" in section.css("h2::text").getall()),
        None,
    )
    if news_section is None:
        return []
    urls = []
    for node in news_section.css('a[href*="/bai-viet/"]'):
        url = clean_url(node.attrib.get("href", ""), FIREANT_HOME)
        if url and url not in urls:
            urls.append(url)
        if len(urls) >= limit:
            break
    return urls


def fetch_article(url: str) -> dict | None:
    source = "cafef" if urlparse(url).hostname == "cafef.vn" else "fireant"
    if source == "fireant":
        page = DynamicFetcher.fetch(url, headless=True, wait=1000, timeout=30000)
    else:
        page = Fetcher.get(url, timeout=20)
    if page.status != 200:
        return None
    resolved_url = clean_url(str(page.url))
    if not resolved_url:
        return None

    canonical = first_attr(page, ('link[rel="canonical"]',), "href")
    if not canonical:
        canonical = first_attr(page, ('meta[property="og:url"]',), "content")
    final_url = clean_url(canonical, resolved_url) if canonical else resolved_url
    if not final_url or urlparse(final_url).hostname != urlparse(url).hostname:
        return None

    title = first_text(page, ("h1",)) or first_attr(
        page, ('meta[property="og:title"]',), "content"
    )
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
            ".detail-content", ".contentdetail", ".knc-content", ".news-detail-content",
            "article .content", "article", '[itemprop="articleBody"]',
        ),
    )
    if not title or not (content or description):
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
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=("cafef", "fireant", "all"), default="cafef")
    parser.add_argument("--url", action="append", default=[], help="Direct article URL; repeatable")
    parser.add_argument("--limit", type=int, default=10, help="Maximum candidate links per source")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be at least 1")

    candidates = []
    if args.url:
        for raw_url in args.url:
            url = clean_url(raw_url)
            if not url:
                parser.error(f"Not a supported direct article URL: {raw_url}")
            candidates.append(url)
    else:
        if args.source in ("cafef", "all"):
            try:
                candidates.extend(cafef_urls(args.limit))
            except Exception as exc:
                print(f"CafeF discovery failed: {exc}", file=sys.stderr)
        if args.source in ("fireant", "all"):
            try:
                candidates.extend(fireant_urls(args.limit))
            except Exception as exc:
                print(f"FireAnt discovery failed: {exc}", file=sys.stderr)

    articles = {}
    if args.output.exists():
        try:
            previous = json.loads(args.output.read_text(encoding="utf-8"))
            articles = {
                article["url"]: article
                for article in previous.get("articles", [])
                if isinstance(article, dict) and article.get("url")
            }
        except (OSError, ValueError, TypeError) as exc:
            print(f"Cannot read existing output {args.output}: {exc}", file=sys.stderr)
            return 1

    added = 0
    for index, url in enumerate(dict.fromkeys(candidates)):
        if url in articles:
            continue
        if index:
            time.sleep(1)
        try:
            article = fetch_article(url)
            if article:
                articles[article["url"]] = article
                added += 1
            else:
                print(f"Skipped non-article or unreadable page: {url}", file=sys.stderr)
        except Exception as exc:
            print(f"Failed to fetch {url}: {exc}", file=sys.stderr)

    if not articles:
        print("No valid articles found; output was not changed", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": "1.0", "articles": list(articles.values())}
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(args.output)
    print(f"Saved {len(articles)} articles ({added} new) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
