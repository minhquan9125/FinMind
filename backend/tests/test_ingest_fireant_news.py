"""Offline checks for the FireAnt-only news replacement plan."""

import asyncio
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.ingest_market_news_to_supabase import (
    PROJECT_SYMBOLS,
    SCRAPERS_DIR,
    collect_news,
    run,
)


def _article(source, url, symbols):
    return {
        "source": source,
        "url": url,
        "title": "Tin doanh nghiệp",
        "content": "Nội dung bài báo",
        "symbols": symbols,
    }


def test_collect_news_keeps_only_fireant_and_project_symbols():
    root = SCRAPERS_DIR / "fixture-only"
    fireant_path = root / "tin_tuc_theo_ma" / "FPT" / "fireant" / "27-10-2026.json"
    cafef_path = root / "tin_tuc_theo_ma" / "FPT" / "cafef" / "27-10-2026.json"
    payloads = {
        fireant_path: {"source": "fireant", "articles": [
            _article("fireant", "https://fireant.vn/bai-viet/fpt/1", ["FPT", "HPG"]),
            _article("fireant", "https://fireant.vn/bai-viet/hpg/2", ["HPG"]),
            _article("fireant", "https://example.com/not-fireant", ["FPT"]),
        ]},
        cafef_path: {"source": "cafef", "articles": [
            _article("cafef", "https://cafef.vn/fpt.chn", ["FPT"]),
        ]},
    }
    with patch.object(Path, "rglob", return_value=list(payloads)), \
         patch("scripts.ingest_market_news_to_supabase.load_json", side_effect=payloads.__getitem__):
        files, articles = collect_news(PROJECT_SYMBOLS, "fireant", root)

    assert len(files) == 1
    assert len(articles) == 1
    assert articles[0]["key"] == ("fireant", "https://fireant.vn/bai-viet/fpt/1")
    assert articles[0]["symbols"] == {"FPT"}


def test_replace_requires_isolated_fireant_crawl():
    args = Namespace(symbol=sorted(PROJECT_SYMBOLS), only="news", news_source="cafef",
                     news_dir=SCRAPERS_DIR / "fixture-only", replace_news=True, apply=False,
                     no_overwrite=False)
    with pytest.raises(ValueError, match="--replace-news requires"):
        asyncio.run(run(args))


def test_replace_refuses_empty_crawl_before_database_connection():
    args = Namespace(symbol=sorted(PROJECT_SYMBOLS), only="news", news_source="fireant",
                     news_dir=SCRAPERS_DIR / "fixture-only", replace_news=True, apply=True,
                     no_overwrite=False)
    with patch.object(Path, "is_dir", return_value=True), \
         patch("scripts.ingest_market_news_to_supabase.collect_news", return_value=([], [])):
        with pytest.raises(ValueError, match="No FireAnt articles found"):
            asyncio.run(run(args))
