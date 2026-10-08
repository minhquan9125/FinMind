"""Bounded on-demand public news, independent of the price SDK quota."""
from collections import OrderedDict, deque
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import re
import threading
import time
import unicodedata
from urllib.parse import urljoin, urlsplit

import httpx

from .live import BusyError, stock_symbol


class Text(HTMLParser):
    def __init__(self, value):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.feed(str(value or ""))

    def handle_data(self, data):
        self.parts.append(data)

    def __str__(self):
        return " ".join(" ".join(self.parts).split())


class FireAntNews:
    def __init__(self):
        self.client = httpx.Client(timeout=12, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://fireant.vn/"})
        self.anonymous = None

    def close(self):
        self.client.close()

    def _get(self, url, **kwargs):
        with self.client.stream("GET", url, **kwargs) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > 8 * 1024 * 1024:
                    raise ValueError("Oversized source response")
                chunks.append(chunk)
            return b"".join(chunks).decode("utf-8")

    def __call__(self, symbol):
        stock_symbol(symbol)
        if self.anonymous is None:
            page = self._get("https://fireant.vn")
            scripts = re.findall(r'<script\b[^>]*\bsrc=["\']([^"\']+)["\']', page)
            for script in scripts:
                if "/chunks/pages/_app-" not in script:
                    continue
                url = urljoin("https://fireant.vn", script)
                if urlsplit(url).scheme != "https" or urlsplit(url).hostname != "fireant.vn":
                    continue
                bundle = self._get(url)
                match = re.search(r'ANONYMOUS_ACCESS_TOKEN\s*=\s*"([^"]+)"', bundle)
                if match:
                    self.anonymous = match.group(1)
                    break
            if self.anonymous is None:
                raise RuntimeError("Public news unavailable")
        try:
            rows = json.loads(self._get("https://restv2.fireant.vn/posts",
                params={"type": 1, "symbol": symbol, "offset": 0, "limit": 20},
                headers={"Authorization": "Bearer " + self.anonymous}))
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 403):
                self.anonymous = None
            raise
        if not isinstance(rows, list):
            raise ValueError("Invalid news response")
        articles = []
        for row in rows:
            if not isinstance(row, dict) or row.get("type") != 1:
                continue
            post_id = str(row.get("postID") or "")
            if not post_id.isdigit():
                continue
            title = str(Text(row.get("title")))[:1000]
            if not title:
                continue
            folded = unicodedata.normalize("NFD", title.lower().replace("đ", "d"))
            folded = "".join(letter for letter in folded if not unicodedata.combining(letter))
            slug = re.sub(r"[^a-z0-9]+", "-", folded).strip("-") or "tin-tuc"
            url = "https://fireant.vn/bai-viet/" + slug + "/" + post_id
            articles.append({"id": hashlib.sha256(url.encode()).hexdigest()[:20], "title": title,
                             "description": str(Text(row.get("description")))[:4000], "url": url,
                             "published_at": row.get("date"), "source": "fireant", "marker": "uncheck"})
            if len(articles) == 10:
                break
        return articles


class NewsService:
    def __init__(self, fetch, repository, *, clock=time.monotonic):
        self.fetch, self.repository, self.clock = fetch, repository, clock
        self.lock = threading.Lock()
        self.cache = OrderedDict()
        self.calls = deque()

    def refresh(self, symbol):
        stock_symbol(symbol)
        if not self.lock.acquire(blocking=False):
            raise BusyError(2)
        try:
            now = self.clock()
            cached = self.cache.get(symbol)
            if cached and now < cached[1]:
                self.cache.move_to_end(symbol)
                return cached[0]
            while self.calls and self.calls[0] <= now - 60:
                self.calls.popleft()
            wait = max(0, self.calls[-1] + 2 - now) if self.calls else 0
            if len(self.calls) >= 10:
                wait = max(wait, self.calls[0] + 60 - now)
            if wait > 0:
                raise BusyError(wait)
            self.calls.append(now)
            try:
                articles = self.fetch(symbol)
                payload = {"symbol": symbol, "source": "fireant", "articles": articles,
                           "fetched_at": datetime.now(timezone.utc).isoformat()}
                self.repository.runtime_write(symbol, "news", payload)
                result = {**self.repository.get_news(symbol, 10), "refresh": {"stale": False, "error": None,
                                                                                 "fetched_at": payload["fetched_at"]}}
                ttl = 60
            except Exception:
                result = {**self.repository.get_news(symbol, 10), "refresh": {"stale": True,
                    "error": "Chưa lấy được tin mới từ FireAnt; đang giữ tin đã lưu."}}
                ttl = 30
            self.cache[symbol] = (result, self.clock() + ttl)
            self.cache.move_to_end(symbol)
            while len(self.cache) > 100:
                self.cache.popitem(last=False)
            return result
        finally:
            self.lock.release()
