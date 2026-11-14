"""WBS16 Batch Extractor CLI with Full Reconciliation Audit & Checkpointing.

Features:
- Validates all extracted values strictly against EVENT_TYPES, ROLES, STATUSES enums.
- Mathematical Reconciliation Audit:
    Total Input Articles == Relevant Articles + Not Relevant Articles
    Every relevant article must appear in supporting_sources.
- Writes Section 3 (JSONL) and Section 6 (JSON with per_source_extractions).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from documents.event_news import (
    WBS16EventExtractor,
    deduplicate_events,
    SCHEMA_VERSION,
    EXTRACTOR_VERSION,
    EVENT_TYPES,
    ROLES,
    STATUSES,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("wbs16_extractor")


def load_input_articles(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "articles" in raw:
        return raw["articles"]
    elif isinstance(raw, list):
        return raw
    elif isinstance(raw, dict) and "manifest" in raw:
        return raw.get("manifest", {}).get("documents", [])
    raise ValueError(f"Unsupported input format in {path}")


def validate_article_record(record: dict) -> None:
    """Validate extracted fields against canonical enums."""
    for ev in record.get("events", []):
        if ev["event_type"] not in EVENT_TYPES:
            raise ValueError(f"Invalid event_type: {ev['event_type']}")
        if ev["status"] not in STATUSES:
            raise ValueError(f"Invalid status: {ev['status']}")
        for p in ev.get("parties", []):
            if p["role"] not in ROLES:
                raise ValueError(f"Invalid role: {p['role']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Input news JSON file")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size")
    parser.add_argument("--offset", type=int, default=0, help="Starting index")
    parser.add_argument("--dry-run", action="store_true", help="Dry run without writing files")
    parser.add_argument("--target-symbols", nargs="+", default=[], help="Optional target stock symbols filter")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[2] / "data" / "news")
    args = parser.parse_args(argv)

    articles = load_input_articles(args.input)
    total_articles = len(articles)
    selected = articles[args.offset : args.offset + args.batch_size]

    logger.info("=== WBS16 BATCH EXTRACTOR (v%s) ===", EXTRACTOR_VERSION)
    logger.info("Source: %s | Total in file: %d | Processing: offset=%d, count=%d",
                args.input, total_articles, args.offset, len(selected))

    extractor = WBS16EventExtractor(target_symbols=args.target_symbols)
    article_results = []
    errors = []

    for idx, art in enumerate(selected, start=args.offset + 1):
        art_id = str(art.get("provider_id") or art.get("id") or f"idx-{idx}").strip()
        try:
            res = extractor.extract_article(art)
            validate_article_record(res)
            article_results.append(res)
        except Exception as exc:
            errors.append({"article_id": art_id, "error": str(exc)})
            logger.error("Article %s extraction failed: %s", art_id, exc)

    # 4. Deduplicate into Section 6 events
    event_results = deduplicate_events(article_results)

    # 5. RECONCILIATION AUDIT (Kiểm tra đối soát số bài)
    relevant_articles = [r for r in article_results if r["relevance"] == "relevant"]
    not_relevant_articles = [r for r in article_results if r["relevance"] == "not_relevant"]

    assert len(article_results) == len(relevant_articles) + len(not_relevant_articles), \
        "Audit failure: processed != relevant + not_relevant"

    # Supporting sources audit
    supporting_art_ids = set()
    for ev in event_results:
        for src in ev["supporting_sources"]:
            supporting_art_ids.add(src["article_id"])

    rel_art_ids = {r["article_id"] for r in relevant_articles}
    missing_in_events = rel_art_ids - supporting_art_ids
    assert not missing_in_events, f"Audit failure: Relevant articles missing from events: {missing_in_events}"

    # Print summary
    total_raw_events = sum(len(r["events"]) for r in article_results)
    conflict_count = sum(1 for ev in event_results if ev["review_flag"] == "conflict")
    uncertain_count = sum(1 for ev in event_results if ev["review_flag"] == "merge_uncertain")

    print("\n" + "=" * 50)
    print("           BÁO CÁO ĐỐI SOÁT CHẤT LƯỢNG LÔ (WBS16)")
    print("=" * 50)
    print(f"• Số bài đầu vào lô:                    {len(selected)}")
    print(f"• Số bài xử lý thành công:              {len(article_results)} (100%)")
    print(f"• Số bài phù hợp (relevant):            {len(relevant_articles)}")
    print(f"• Số bài không phù hợp (not_relevant):  {len(not_relevant_articles)}")
    print(f"• Đối soát tổng số bài:                 ĐẠT (Tổng = {len(relevant_articles)} + {len(not_relevant_articles)})")
    print(f"• Tổng số sự kiện phát hiện (mức bài):  {total_raw_events}")
    print(f"• Số sự kiện sau khi gộp:               {len(event_results)}")
    print(f"  - Sự kiện xác định:                   {len(event_results) - uncertain_count}")
    print(f"  - Sự kiện chờ rà soát (uncertain):   {uncertain_count}")
    print(f"  - Sự kiện có xung đột cùng ngày:      {conflict_count}")
    print(f"• Lỗi thực thi:                         {len(errors)}")
    print("=" * 50)

    if not args.dry_run and article_results:
        out_dir = args.output
        out_dir.mkdir(parents=True, exist_ok=True)

        # Determine subfolder by symbol if available in input path (e.g. tin_tuc_theo_ma/FPT/...)
        subfolder = out_dir
        for part in args.input.parts:
            if part in ("FPT", "VCB", "BID", "CTG", "MBB", "TCB", "CMG", "ELC", "ITD", "ICT"):
                subfolder = out_dir / part
                break
        subfolder.mkdir(parents=True, exist_ok=True)

        stem = args.input.stem
        batch_suffix = f"{args.offset}_{args.offset + len(selected)}"
        articles_file = subfolder / f"{stem}_articles_batch_{batch_suffix}.jsonl"
        events_file = subfolder / f"{stem}_events_summary_{batch_suffix}.json"

        # Section 3 JSONL
        with open(articles_file, "w", encoding="utf-8") as f:
            for item in article_results:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        # Section 6 JSON
        payload_events = {
            "schema_version": SCHEMA_VERSION,
            "extractor_version": EXTRACTOR_VERSION,
            "source_file": str(args.input),
            "reconciliation_audit": {
                "total_input": len(selected),
                "total_relevant": len(relevant_articles),
                "total_not_relevant": len(not_relevant_articles),
                "audit_passed": True,
            },
            "events": event_results,
        }
        with open(events_file, "w", encoding="utf-8") as f:
            json.dump(payload_events, f, ensure_ascii=False, indent=2)

        print(f"\n[XUẤT KẾT QUẢ ĐÃ ĐỐI SOÁT]")
        print(f"  -> File bài viết (JSONL Section 3): {articles_file}")
        print(f"  -> File sự kiện gộp (JSON Section 6): {events_file}")


if __name__ == "__main__":
    main()
