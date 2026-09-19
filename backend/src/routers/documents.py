"""Document upload/processing and chunk/vocabulary inspection endpoints."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile

from .. import repository
from ..chunking import Page, build_chunks, extract_pages
from ..config import Settings, get_settings
from ..db import get_pool
from ..embeddings import EmbeddingService, get_embedding_service
from ..json_ingest import financial_json_to_pages, generic_json_to_pages, is_normalized_financial_payload
from ..schemas import ChunkDetailOut, DocumentOut, TraceWordOut, VocabResponse, VocabRowOut
from ..text_analysis import (
    idf_weights,
    term_frequencies,
    tokenize_with_trace,
    top_terms_for_chunk,
)

router = APIRouter(prefix="/api/documents", tags=["documents"])


async def _ingest_pages(
    pages: list[Page],
    filename: str,
    settings: Settings,
    embedder: EmbeddingService,
    empty_error: str,
) -> DocumentOut:
    """Shared tail of the ingestion pipeline (chunk -> embed -> store) used by
    the PDF, JSON-upload and symbol-import entrypoints below, which only
    differ in how they produce `pages`."""
    raw_chunks = build_chunks(pages, settings.chunk_words, settings.chunk_stride)
    if not raw_chunks:
        raise HTTPException(status_code=422, detail=empty_error)

    chunk_texts = [c.text for c in raw_chunks]
    tf_list, df, _ttf = term_frequencies(chunk_texts)

    # Ranking now comes from BAAI/bge-m3 dense embeddings (ADR04), not TF-IDF.
    embeddings = embedder.embed_texts(chunk_texts)

    pool = get_pool()
    document_id = await repository.create_document(pool, filename, len(pages))
    rows = []
    total_tokens = 0
    for index, (chunk, tf, vector) in enumerate(zip(raw_chunks, tf_list, embeddings)):
        token_count = sum(tf.values())
        total_tokens += token_count
        rows.append(
            {
                "chunk_index": index,
                "page": chunk.page,
                "text": chunk.text,
                "word_count": len(chunk.text.split(" ")),
                "token_count": token_count,
                "unique_count": len(tf),
                "embedding": vector,
            }
        )
    await repository.insert_chunks(pool, document_id, rows)

    return DocumentOut(
        id=document_id,
        filename=filename,
        page_count=len(pages),
        chunk_count=len(raw_chunks),
        vocab_size=len(df),
        total_tokens=total_tokens,
    )


@router.post("", response_model=DocumentOut)
async def upload_document(
    file: UploadFile,
    settings: Settings = Depends(get_settings),
    embedder: EmbeddingService = Depends(get_embedding_service),
) -> DocumentOut:
    if file.content_type not in ("application/pdf", "application/x-pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    pdf_bytes = await file.read()
    pages = extract_pages(pdf_bytes)
    return await _ingest_pages(
        pages,
        file.filename or "document.pdf",
        settings,
        embedder,
        empty_error="No extractable text found in this PDF (it may be a scanned image without OCR).",
    )


@router.post("/json", response_model=DocumentOut)
async def upload_json_document(
    file: UploadFile,
    settings: Settings = Depends(get_settings),
    embedder: EmbeddingService = Depends(get_embedding_service),
) -> DocumentOut:
    """Upload an arbitrary JSON file. Payloads matching the data_pipeline
    normalized financial schema (data/normalized/{SYMBOL}.json) get readable
    per-period/per-month chunks; anything else falls back to a generic
    record-based flattening (see json_ingest.py)."""
    filename = file.filename or "document.json"
    if not (filename.endswith(".json") or file.content_type in ("application/json", "text/json")):
        raise HTTPException(status_code=400, detail="Only JSON files are supported.")

    raw_bytes = await file.read()
    try:
        data = json.loads(raw_bytes)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from None

    if is_normalized_financial_payload(data):
        pages = financial_json_to_pages(data.get("symbol") or "UNKNOWN", data)
    else:
        pages = generic_json_to_pages(data)

    return await _ingest_pages(
        pages,
        filename,
        settings,
        embedder,
        empty_error="No records found in this JSON payload.",
    )


@router.post("/import-symbol/{symbol}", response_model=DocumentOut)
async def import_symbol(
    symbol: str,
    settings: Settings = Depends(get_settings),
    embedder: EmbeddingService = Depends(get_embedding_service),
) -> DocumentOut:
    """Ingest one of data_pipeline's pre-scraped data/normalized/{SYMBOL}.json
    files directly from disk, without requiring a manual upload."""
    symbol = symbol.upper()
    path = Path(settings.financial_data_dir) / f"{symbol}.json"
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No normalized data file found for symbol '{symbol}' (expected {path}).",
        )

    data = json.loads(path.read_text(encoding="utf-8"))
    pages = financial_json_to_pages(symbol, data)
    return await _ingest_pages(
        pages,
        path.name,
        settings,
        embedder,
        empty_error=f"'{symbol}' normalized data file has no price/financial records.",
    )


@router.get("/{document_id}/chunks", response_model=list[ChunkDetailOut])
async def get_chunk_details(document_id: str) -> list[ChunkDetailOut]:
    pool = get_pool()
    document = await repository.get_document(pool, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    chunk_rows = await repository.get_chunks(pool, document_id)
    chunk_texts = [row["text"] for row in chunk_rows]
    tf_list, df, _ttf = term_frequencies(chunk_texts)
    idf = idf_weights(df, doc_count=len(chunk_texts))

    out: list[ChunkDetailOut] = []
    for row, tf in zip(chunk_rows, tf_list):
        out.append(
            ChunkDetailOut(
                index=row["chunk_index"],
                page=row["page"],
                text=row["text"],
                word_count=row["word_count"],
                token_count=row["token_count"],
                unique_count=row["unique_count"],
                top_terms=top_terms_for_chunk(tf, idf),
                trace=[
                    TraceWordOut(word=t.word, kept=t.kept, reason=t.reason)
                    for t in tokenize_with_trace(row["text"])
                ],
            )
        )
    return out


@router.get("/{document_id}/vocab", response_model=VocabResponse)
async def get_vocab(
    document_id: str,
    q: str | None = Query(default=None, description="Filter tokens containing this substring"),
    limit: int = Query(default=300, le=1000),
) -> VocabResponse:
    pool = get_pool()
    document = await repository.get_document(pool, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    chunk_rows = await repository.get_chunks(pool, document_id)
    chunk_texts = [row["text"] for row in chunk_rows]
    _tf_list, df, ttf = term_frequencies(chunk_texts)
    idf = idf_weights(df, doc_count=len(chunk_texts))

    needle = (q or "").strip().lower()
    tokens = [t for t in df.keys() if not needle or needle in t]
    tokens.sort(key=lambda t: df[t], reverse=True)
    truncated = len(tokens) > limit
    tokens = tokens[:limit]

    return VocabResponse(
        vocab_size=len(df),
        truncated=truncated,
        rows=[
            VocabRowOut(
                token=t,
                document_frequency=df[t],
                total_frequency=ttf[t],
                idf=idf.get(t, 0.0),
            )
            for t in tokens
        ],
    )
