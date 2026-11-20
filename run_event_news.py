r"""Runner tự động chạy event_news từ Database PostgreSQL (public.news_articles) hoặc thư mục cào sang data/news/{MÃ}.

Cách dùng:
  # Lấy trực tiếp từ Database PostgreSQL (Dữ liệu sạch, không trùng):
  backend\.venv\Scripts\python.exe run_event_news.py --symbol FPT
  backend\.venv\Scripts\python.exe run_event_news.py --all

  # WBS16: chỉ một lô News thuộc danh sách chọn từ corpus, không chạy --all:
  python run_event_news.py --manifest backend\.tmp\wbs16-vps-all-news-selection.json ^
    --offset 5 --batch-size 5 --output-dir backend\.tmp\event-news-vps-all-batch-001

  # Hoặc lấy từ file cào crawler:
  backend\.venv\Scripts\python.exe run_event_news.py --from-files --symbol FPT
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit
import asyncpg
from dotenv import load_dotenv

from backend.src.documents.event_news import (
    WBS16EventExtractor,
    deduplicate_events,
    reconcile,
    _atomic_write_jsonl,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("run_event_news")

SCRAPED_DIR = Path("data_pipeline/scrapers/data/tin_tuc_theo_ma")
OUTPUT_BASE = Path("data/news")

def database_url() -> str:
    load_dotenv(Path(__file__).parent / "backend" / ".env")
    load_dotenv(Path(__file__).parent / ".env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL chưa được cấu hình")
    return url


TARGET_10_SYMBOLS = [
    "BID", "CTG", "MBB", "TCB", "VCB",  # Ngân hàng (BANK)
    "CMG", "ELC", "FPT", "ICT", "ITD",  # Công nghệ (TECH)
]


def manifest_news_ids(manifest: dict) -> dict[str, str]:
    """Chỉ lấy article_id News từ manifest đã kiểm tra hash."""
    payload = manifest.get("manifest", manifest)
    expected = manifest.get("manifest_sha256")
    if expected:
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                               separators=(",", ":"), allow_nan=False).encode("utf-8")
        if hashlib.sha256(canonical).hexdigest() != expected:
            raise ValueError("Manifest hash không khớp")
    result = {}
    for doc in payload["documents"]:
        if doc.get("doc_type") != "NEWS":
            continue
        ids = {str(chunk["locator"]["source_id"])
               for chunk in doc["chunks"]
               if chunk["locator"].get("source_table") == "news_articles"}
        if len(ids) != 1:
            raise ValueError(f"Locator News không rõ: {doc['document_id']}")
        article_id = ids.pop()
        if article_id in result:
            raise ValueError(f"article_id trùng trong manifest: {article_id}")
        result[article_id] = str(doc["document_id"])
    return result


def load_articles_from_json(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "articles" in raw:
        return raw["articles"]
    elif isinstance(raw, list):
        return raw
    return []


async def fetch_articles_from_db(symbol: Optional[str] = None,
                                 article_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Truy vấn tin tức trực tiếp từ bảng public.news_articles trong Postgres."""
    url = database_url()
    ssl_mode = False if urlsplit(url).hostname in {"127.0.0.1", "localhost", "::1"} else "require"
    conn = await asyncpg.connect(url, ssl=ssl_mode, statement_cache_size=0, timeout=25)
    try:
        if article_ids is not None:
            rows = await conn.fetch("""
                SELECT article_id, source, url, title, description, content as body,
                       published_at, symbols
                FROM public.news_articles
                WHERE article_id = ANY($1::uuid[])
            """, [uuid.UUID(article_id) for article_id in article_ids])
            by_id = {str(row["article_id"]): row for row in rows}
            missing = sorted(set(article_ids) - set(by_id))
            if missing:
                raise ValueError(f"Bài trong manifest không còn trong news_articles: {missing}")
            rows = [by_id[article_id] for article_id in article_ids]
        elif symbol:
            query = """
                SELECT article_id, source, url, title, description, content as body, 
                       published_at, symbols
                FROM public.news_articles
                WHERE $1 = ANY(symbols)
                ORDER BY published_at DESC;
            """
            rows = await conn.fetch(query, symbol.upper())
        else:
            query = """
                SELECT article_id, source, url, title, description, content as body, 
                       published_at, symbols
                FROM public.news_articles
                ORDER BY published_at DESC;
            """
            rows = await conn.fetch(query)

        articles = []
        for r in rows:
            articles.append({
                "article_id": str(r["article_id"]),
                "source_name": r["source"],
                "url": r["url"],
                "title": r["title"],
                "description": r["description"],
                "body": r["body"],
                "publish_date": r["published_at"].isoformat() if r["published_at"] else None,
                "symbols": list(r["symbols"]) if r["symbols"] else [],
            })
        return articles
    finally:
        await conn.close()


def process_articles_for_symbol(symbol: str, articles: List[Dict[str, Any]],
                                out_dir: Optional[Path] = None) -> None:
    if not articles:
        log.warning(f"Không có bài báo nào cho mã {symbol}")
        return

    out_dir = out_dir or OUTPUT_BASE / symbol
    out_dir.mkdir(parents=True, exist_ok=True)

    log.info(f"=== Đang xử lý mã {symbol}: tổng cộng {len(articles)} bài báo ===")

    # 1. Trích xuất bằng extractor
    extractor = WBS16EventExtractor()
    extracted_records = []
    for art in articles:
        try:
            rec = extractor.extract_article(art)
            extracted_records.append(rec)
        except Exception as e:
            log.exception(f"Lỗi bài {art.get('article_id')}: {e}")

    # Ghi file batch_extracted
    _atomic_write_jsonl(out_dir / "batch_extracted.jsonl", extracted_records)
    (out_dir / "batch_extracted.json").write_text(
        json.dumps(extracted_records, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 2. Gộp sự kiện trùng & reconcile
    events = deduplicate_events(extracted_records)
    report = reconcile(extracted_records, events)

    # Ghi events.jsonl và events.json (thụt dòng để dễ đọc)
    _atomic_write_jsonl(out_dir / "events.jsonl", events)
    (out_dir / "events.json").write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "reconcile.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    log.info(f"Hoàn thành mã {symbol}: {report['events_out']} sự kiện duy nhất được xuất vào {out_dir}")


def process_symbol_from_files(symbol: str) -> None:
    sym_dir = SCRAPED_DIR / symbol
    if not sym_dir.exists():
        log.warning(f"Không tìm thấy thư mục tin cào cho mã {symbol} tại {sym_dir}")
        return

    json_files = list(sym_dir.glob("*/*.json"))
    if not json_files:
        log.warning(f"Không có file json tin tức nào cho mã {symbol}")
        return

    all_articles = []
    seen_ids = set()
    for jf in json_files:
        arts = load_articles_from_json(jf)
        for a in arts:
            aid = str(a.get("id") or a.get("article_id") or a.get("url"))
            if aid not in seen_ids:
                seen_ids.add(aid)
                all_articles.append(a)

    process_articles_for_symbol(symbol, all_articles)


def main():
    parser = argparse.ArgumentParser(description="Chạy event_news tự động từ Database hoặc data cào")
    parser.add_argument("--symbol", help="Mã cổ phiếu cần chạy (ví dụ: FPT, BID...)")
    parser.add_argument("--all", action="store_true", help="Chạy cho toàn bộ các mã")
    parser.add_argument("--from-files", action="store_true", help="Lấy nguồn từ các file cào trong data_pipeline/scrapers (Mặc định lấy từ DB)")
    parser.add_argument("--manifest", type=Path, help="Manifest News đã chọn; chỉ đọc đúng ID của một lô từ DB")
    parser.add_argument("--offset", type=int, default=0, help="Vị trí bắt đầu trong danh sách ID đã sắp xếp")
    parser.add_argument("--batch-size", type=int, default=50, help="Số bài trong lô, 1..100")
    parser.add_argument("--output-dir", type=Path, help="Thư mục kết quả cho lô manifest")
    args = parser.parse_args()

    if args.manifest:
        if args.from_files or args.symbol or args.all:
            parser.error("--manifest chỉ dùng riêng cho một lô từ DB")
        if args.offset < 0 or not 1 <= args.batch_size <= 100:
            parser.error("--offset phải >= 0 và --batch-size phải trong 1..100")
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        ids = sorted(manifest_news_ids(manifest))
        batch_ids = ids[args.offset:args.offset + args.batch_size]
        if not batch_ids:
            parser.error(f"Không có bài News tại offset {args.offset}; manifest có {len(ids)} bài")
        articles = asyncio.run(fetch_articles_from_db(article_ids=batch_ids))
        out_dir = args.output_dir or OUTPUT_BASE / f"batch_{args.offset:08d}"
        process_articles_for_symbol(f"lô {args.offset}", articles, out_dir=out_dir)
        return

    use_db = not args.from_files

    if use_db:
        log.info(f"Đang kết nối Database PostgreSQL (public.news_articles) để lấy tin tức...")
        if args.symbol:
            arts = asyncio.run(fetch_articles_from_db(args.symbol.upper()))
            process_articles_for_symbol(args.symbol.upper(), arts)
        elif args.all:
            # Chỉ lấy đúng 10 mã mục tiêu chính của dự án (BANK & TECH)
            for sym in TARGET_10_SYMBOLS:
                arts = asyncio.run(fetch_articles_from_db(sym))
                process_articles_for_symbol(sym, arts)
        else:
            parser.print_help()
    else:
        log.info(f"Đang lấy tin tức từ các file cào trong data_pipeline/scrapers...")
        if args.symbol:
            process_symbol_from_files(args.symbol.upper())
        elif args.all:
            for sym in TARGET_10_SYMBOLS:
                process_symbol_from_files(sym)
        else:
            parser.print_help()


if __name__ == "__main__":
    main()
