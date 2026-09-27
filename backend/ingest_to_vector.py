"""Vector Ingestion Pipeline for FinMind.

Ingests normalized financial JSON files and BCTC PDF files into Supabase Postgres
with pgvector embeddings powered by BAAI/bge-m3.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Final

import asyncpg
from dotenv import load_dotenv
from pgvector.asyncpg import register_vector
import pypdf
import torch
from sentence_transformers import SentenceTransformer

# Reconfigure console output encoding for Windows
if sys.platform == "win32":
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure backend root is on sys.path
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Load environment variables
load_dotenv(BASE_DIR / ".env")
load_dotenv(PROJECT_ROOT / ".env")

from src.json_ingest import chunk_text, json_to_text

MODEL_NAME: Final[str] = "BAAI/bge-m3"
VECTOR_DIM: Final[int] = 1024
TARGET_SYMBOLS: Final[set[str]] = {
    "BID", "CTG", "MBB", "TCB", "VCB",  # Banking
    "CMG", "ELC", "FPT", "ICT", "ITD",  # Tech
}


def compute_sha256(file_path: Path) -> str:
    """Compute sha256 hash of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def find_input_files() -> tuple[list[Path], list[Path]]:
    """Locate all JSON and PDF files in standard workspace directories."""
    json_dirs = [
        PROJECT_ROOT / "data" / "normalized",
        BASE_DIR / "data" / "normalized",
    ]
    pdf_dirs = [
        PROJECT_ROOT / "docs",
        BASE_DIR / "docs",
    ]

    json_files: list[Path] = []
    for d in json_dirs:
        if d.is_dir():
            for p in sorted(d.glob("*.json")):
                if p not in json_files:
                    json_files.append(p)

    pdf_files: list[Path] = []
    for d in pdf_dirs:
        if d.is_dir():
            for p in sorted(d.glob("*.pdf")):
                if p not in pdf_files:
                    pdf_files.append(p)

    return json_files, pdf_files


def extract_symbol_from_name(name: str) -> str | None:
    """Attempt to detect one of the 10 target symbols from filename."""
    name_upper = name.upper()
    for s in TARGET_SYMBOLS:
        if s in name_upper:
            return s
    return None


async def ingest_file(
    conn: asyncpg.Connection,
    file_path: Path,
    file_type: str,
    model: SentenceTransformer,
    index: int,
    total: int,
) -> tuple[int, int]:
    """Ingest a single JSON or PDF file into Supabase vector database.

    Returns:
        tuple (chunk_count, embedding_count)
    """
    file_name = file_path.name
    file_size = file_path.stat().st_size
    sha256_hash = compute_sha256(file_path)

    # 1. Check for duplicates
    existing_id = await conn.fetchval(
        "SELECT document_id FROM documents WHERE sha256_hash = $1",
        sha256_hash,
    )
    if existing_id:
        print(f"[{index}/{total}] ⏩ {file_name} → SKIP (Đã tồn tại trong documents)")
        return 0, 0

    print(f"[{index}/{total}] 📥 Ingesting {file_name}...")

    # 2. Extract and chunk text
    chunks_to_process: list[dict] = []
    page_count = 1
    symbol = extract_symbol_from_name(file_name)

    if file_type == "json":
        text = json_to_text(file_path)
        if not text:
            print(f"   ⚠️ Không có nội dung text hợp lệ trong {file_name}")
            return 0, 0

        raw_chunks = chunk_text(text, chunk_size=500, overlap=50)
        for i, c in enumerate(raw_chunks):
            chunks_to_process.append({
                "chunk_id": uuid.uuid4(),
                "chunk_index": i,
                "page_number": 1,
                "text": c,
            })
    elif file_type == "pdf":
        try:
            reader = pypdf.PdfReader(str(file_path))
            page_count = len(reader.pages)
            chunk_idx = 0
            for page_idx, page in enumerate(reader.pages, start=1):
                raw_text = page.extract_text() or ""
                clean_text = " ".join(raw_text.split())
                if not clean_text:
                    continue
                page_chunks = chunk_text(clean_text, chunk_size=500, overlap=50)
                for c in page_chunks:
                    chunks_to_process.append({
                        "chunk_id": uuid.uuid4(),
                        "chunk_index": chunk_idx,
                        "page_number": page_idx,
                        "text": c,
                    })
                    chunk_idx += 1
        except Exception as e:
            print(f"   ❌ Lỗi khi đọc file PDF {file_name}: {e}")
            return 0, 0

    if not chunks_to_process:
        print(f"   ⚠️ Không có chunk nào được trích xuất từ {file_name} (có thể là file scan dạng ảnh)")
        # Still record document entry so it's tracked
        doc_id = uuid.uuid4()
        await conn.execute("""
            INSERT INTO documents (document_id, symbol, title, file_type, file_path, page_count, file_size, sha256_hash)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """, doc_id, symbol, file_name, file_type, str(file_path), page_count, file_size, sha256_hash)
        return 0, 0

    # 3. Create embeddings with BAAI/bge-m3
    chunk_texts = [c["text"] for c in chunks_to_process]
    raw_vectors = model.encode(
        chunk_texts,
        batch_size=32,
        show_progress_bar=False,
        normalize_embeddings=True,
    )

    # 4. Insert into Supabase in an atomic transaction
    doc_id = uuid.uuid4()
    async with conn.transaction():
        # Insert document
        await conn.execute("""
            INSERT INTO documents (document_id, symbol, title, file_type, file_path, page_count, file_size, sha256_hash)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """, doc_id, symbol, file_name, file_type, str(file_path), page_count, file_size, sha256_hash)

        # Insert text_chunks
        chunk_records = [
            (
                c["chunk_id"],
                doc_id,
                symbol,
                c["chunk_index"],
                c["page_number"],
                c["text"],
                len(c["text"].split()),
                len(c["text"]),
                len(set(c["text"].split())),
            )
            for c in chunks_to_process
        ]
        await conn.executemany("""
            INSERT INTO text_chunks
                (chunk_id, document_id, symbol, chunk_index, page_number, chunk_text, word_count, token_count, unique_count)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """, chunk_records)

        # Insert embeddings
        emb_records = [
            (
                uuid.uuid4(),
                c["chunk_id"],
                MODEL_NAME,
                "v1",
                VECTOR_DIM,
                vec.tolist() if hasattr(vec, "tolist") else list(vec),
            )
            for c, vec in zip(chunks_to_process, raw_vectors)
        ]
        await conn.executemany("""
            INSERT INTO embeddings
                (embedding_id, chunk_id, model_name, model_version, vector_dim, embedding)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, emb_records)

    chunk_count = len(chunks_to_process)
    print(f"   → {chunk_count} chunks → {chunk_count} embeddings ✅")
    return chunk_count, chunk_count


async def main():
    print("🔌 Kết nối Supabase...")
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("❌ Lỗi: DATABASE_URL không được tìm thấy trong .env")
        return

    conn = await asyncpg.connect(db_url, ssl="require", statement_cache_size=0)
    await register_vector(conn)
    print("🔌 Kết nối Supabase... ✅")

    json_files, pdf_files = find_input_files()
    total_files = len(json_files) + len(pdf_files)
    print(f"📄 Tìm thấy {len(json_files)} file JSON, {len(pdf_files)} file PDF")

    print(f"🧠 Khởi tạo mô hình embedding '{MODEL_NAME}'...")
    t0 = time.time()
    model = SentenceTransformer(MODEL_NAME)
    model.max_seq_length = 512
    print(f"🧠 Mô hình tải hoàn tất trong {time.time()-t0:.1f}s ✅\n")

    total_chunks = 0
    total_embeddings = 0

    all_files = [(p, "json") for p in json_files] + [(p, "pdf") for p in pdf_files]

    for idx, (p, ftype) in enumerate(all_files, start=1):
        try:
            c_cnt, e_cnt = await ingest_file(conn, p, ftype, model, idx, total_files)
            total_chunks += c_cnt
            total_embeddings += e_cnt
        except Exception as e:
            print(f"[{idx}/{total_files}] ❌ Lỗi khi ingest file {p.name}: {e}")

    await conn.close()

    print("\n" + "=" * 50)
    print(f"🎉 HOÀN TẤT: {total_chunks} chunks, {total_embeddings} embeddings")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
