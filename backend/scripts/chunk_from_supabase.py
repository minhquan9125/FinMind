"""Chunk financial statements and news that already live in Supabase.

Default is a dry run and READ-ONLY: it reads source rows, builds chunks with
src.documents.db_chunking, prints a summary and optionally saves the chunks to
a JSON file for inspection.

Writing to the database is WBS12 (Nhan), not part of the chunking task (WBS06).
--apply therefore refuses to run unless --confirmed-with-nhan is also given.
When allowed it embeds the chunks (BAAI/bge-m3 by default, ~2.2GB on first run)
and writes ``documents`` and ``text_chunks``. text_chunks.embedding is NOT NULL,
so embedding and writing happen together. Re-running is safe: every row is an
upsert with a stable id.

Examples (run from the FinMind root, DATABASE_URL in .env):
    py -X utf8 backend/scripts/chunk_from_supabase.py                  # tat ca nguon, tat ca ma
    py -X utf8 backend/scripts/chunk_from_supabase.py --symbol FPT VCB
    py -X utf8 backend/scripts/chunk_from_supabase.py --source news --limit 50 --out news_chunks.json
    py -X utf8 backend/scripts/chunk_from_supabase.py --symbol FPT --vectors-out backend/.tmp/fpt-vectors.json
    py -X utf8 backend/scripts/chunk_from_supabase.py --source prices --symbol FPT --apply --confirmed-with-nhan
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from src.documents.db_chunking import DEFAULT_MAX_WORDS, chunk_documents  # noqa: E402
from src.documents.db_ingest import ingest_documents  # noqa: E402
from src.documents import db_source  # noqa: E402


def summarize(label: str, docs, chunks) -> None:
    print(f"\n[{label}] {len(docs)} tai lieu -> {len(chunks)} chunk")
    if not chunks:
        return
    sizes = [c.token_count for c in chunks]
    print(f"  so tu moi chunk: nho nhat {min(sizes)}, trung vi {int(statistics.median(sizes))}, lon nhat {max(sizes)}")
    print(f"  chunk_id khong trung: {len({c.chunk_id for c in chunks}) == len(chunks)}")
    sample = chunks[0]
    print(f"  vi du: {sample.locator['source_table']} {sample.locator['source_id']} | {sample.section_label}")
    print("  " + sample.text.replace("\n", "\n  ")[:600])


async def run(args: argparse.Namespace) -> int:
    if args.apply and not args.confirmed_with_nhan:
        print("Loi: --apply (ghi documents/text_chunks vao database) la viec cua WBS12 (Nhan).\n"
              "Chi chay khi da thong nhat voi Nhan va leader, khi do them --confirmed-with-nhan.\n"
              "De chi lay chunk va vector ra file, dung --out hoac --vectors-out (khong ghi database).",
              file=sys.stderr)
        return 2
    import asyncpg
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / "backend" / ".env")
    load_dotenv(PROJECT_ROOT / ".env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("Loi: DATABASE_URL chua duoc dat trong .env", file=sys.stderr)
        return 2
    conn = await asyncpg.connect(url, ssl="require" if "supabase" in url else None, statement_cache_size=0)
    try:
        results = []
        all_docs = []
        symbols = args.symbol or None
        sources = {
            "companies": ("ho so doanh nghiep", lambda: db_source.fetch_company_documents(conn, symbols)),
            "financial": ("bao cao tai chinh", lambda: db_source.fetch_financial_documents(conn, symbols)),
            "prices": ("gia co phieu", lambda: db_source.fetch_price_documents(conn, symbols)),
            "indices": ("chi so thi truong", lambda: db_source.fetch_index_documents(conn, symbols)),
            "news": ("tin tuc", lambda: db_source.fetch_news_documents(conn, symbols, args.limit or None, args.max_words)),
        }
        failed_sources = []
        for name, (label, fetch) in sources.items():
            if args.source not in ("all", name):
                continue
            try:
                docs = await fetch()
            except Exception as exc:  # noqa: BLE001 - report which source failed, keep the others
                print(f"\n[{label}] LOI khi doc: {type(exc).__name__}: {exc}", file=sys.stderr)
                failed_sources.append(name)
                continue
            chunks = chunk_documents(docs, args.max_words)
            summarize(label, docs, chunks)
            results += chunks
            all_docs += docs
        if failed_sources:
            print(f"\nNguon doc loi: {', '.join(failed_sources)} (kiem tra bang da duoc tao chua)", file=sys.stderr)

        if args.vectors_out:
            # Supabase -> chunk -> vector -> file JSON. Khong ghi gi vao database.
            if not results:
                print("\nKhong co chunk nao de nhung vector.")
            else:
                from src.core.config import get_settings
                from src.documents.batch_embeddings import embed_chunks
                from src.documents.embeddings import EmbeddingService

                settings = get_settings()
                model = args.model or settings.embedding_model
                revision = settings.embedding_model_revision if model == settings.embedding_model else "main"
                ref = settings.embedding_model_ref if model == settings.embedding_model else f"{model}@main"
                embedder = EmbeddingService(model_name=model, revision=revision,
                                            device=settings.embedding_device, batch_size=args.batch_size)
                print(f"\nDang nhung vector cho {len(results)} chunk bang {ref} (chua ghi database)...")
                vec = embed_chunks([c.to_dict() for c in results], embedder, batch_size=args.batch_size)
                target = Path(args.vectors_out)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps({
                    "model_ref": ref, "embedding_dim": settings.embedding_dim, "input_count": len(results),
                    "succeeded_count": len(vec.succeeded), "failed_count": len(vec.failed),
                    "skipped_count": len(vec.skipped), "succeeded": vec.succeeded,
                    "failed": vec.failed, "skipped": vec.skipped,
                }, ensure_ascii=False), encoding="utf-8")
                print(f"Vector: {len(vec.succeeded)}/{len(results)} thanh cong, {len(vec.failed)} loi, "
                      f"{len(vec.skipped)} bo qua -> {target}")
                for err in vec.failed[:5]:
                    print("  LOI:", err, file=sys.stderr)

        if args.apply:
            if not results:
                print("\nKhong co chunk nao de ghi.")
            else:
                from src.core.config import get_settings
                from src.core.db import _init_connection
                from src.documents.embeddings import EmbeddingService

                settings = get_settings()
                model = args.model or settings.embedding_model
                # Dung dung revision da ghim cho bge-m3; mo hinh khac thi lay ban moi nhat.
                revision = settings.embedding_model_revision if model == settings.embedding_model else "main"
                embedder = EmbeddingService(
                    model_name=model, revision=revision, device=settings.embedding_device,
                    batch_size=settings.embedding_batch_size)
                # index_versions.embedding_model chi chua 50 ky tu: dung nhan ngan cua Settings (SHA rut gon).
                index_label = settings.embedding_model_ref if model == settings.embedding_model else f"{model}@main"
                await _init_connection(conn)  # dang ky kieu vector cua pgvector
                print(f"\nDang nhung vector bang {index_label} va ghi {len(results)} chunk (lan dau tai mo hinh se lau)...")
                outcome = await ingest_documents(
                    conn, all_docs, embedder, index_label, args.max_words, args.batch_size)
                print(f"Da ghi: {outcome.documents_ok} tai lieu, {outcome.chunks_written} chunk.")
                if outcome.documents_failed:
                    print(f"LOI: {outcome.documents_failed} tai lieu khong ghi duoc (khong ghi do dang):", file=sys.stderr)
                    for err in outcome.errors[:10]:
                        print("  -", err, file=sys.stderr)
    finally:
        await conn.close()

    if args.out:
        Path(args.out).write_text(
            json.dumps([c.to_dict() for c in results], ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nDa luu {len(results)} chunk vao {args.out}")
    if not args.apply:
        print("\nChay thu: chi doc, khong ghi gi vao database. Them --apply de ghi that.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", choices=["all", "companies", "financial", "prices", "indices", "news"],
                        default="all", help="mac dinh all: lay tat ca cac nguon")
    parser.add_argument("--symbol", nargs="*", default=[], help="gioi han theo ma, vd: --symbol FPT VCB")
    parser.add_argument("--limit", type=int, default=0, help="so bai tin toi da (0 = lay het)")
    parser.add_argument("--max-words", type=int, default=DEFAULT_MAX_WORDS, help="so tu toi da moi chunk")
    parser.add_argument("--out", help="luu danh sach chunk ra file JSON de xem")
    parser.add_argument("--vectors-out", help="nhung vector roi luu ra file JSON (chunk + vector), KHONG ghi database")
    parser.add_argument("--apply", action="store_true",
                        help="[WBS12 - Nhan] nhung vector va ghi documents + text_chunks that; can them --confirmed-with-nhan")
    parser.add_argument("--confirmed-with-nhan", action="store_true",
                        help="xac nhan da thong nhat voi Nhan va leader truoc khi ghi database")
    parser.add_argument("--model", help="mo hinh embedding (mac dinh theo EMBEDDING_MODEL, BAAI/bge-m3)")
    parser.add_argument("--batch-size", type=int, default=32, help="so chunk moi lo khi nhung vector")
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
