"""Document upload/processing and chunk/vocabulary inspection endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile

from .. import repository
from ..chunking import build_chunks, extract_pages
from ..config import Settings, get_settings
from ..db import get_pool
from ..embeddings import EmbeddingService, get_embedding_service
from ..schemas import ChunkDetailOut, DocumentOut, TraceWordOut, VocabResponse, VocabRowOut
from ..text_analysis import (
    idf_weights,
    term_frequencies,
    tokenize_with_trace,
    top_terms_for_chunk,
)

router = APIRouter(prefix="/api/documents", tags=["documents"])


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
    raw_chunks = build_chunks(pages, settings.chunk_words, settings.chunk_stride)
    if not raw_chunks:
        raise HTTPException(
            status_code=422,
            detail="No extractable text found in this PDF (it may be a scanned image without OCR).",
        )

    chunk_texts = [c.text for c in raw_chunks]
    tf_list, df, _ttf = term_frequencies(chunk_texts)

    # Ranking now comes from BAAI/bge-m3 dense embeddings (ADR04), not TF-IDF.
    embeddings = embedder.embed_texts(chunk_texts)

    pool = get_pool()
    document_id = await repository.create_document(pool, file.filename or "document.pdf", len(pages))
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
        filename=file.filename or "document.pdf",
        page_count=len(pages),
        chunk_count=len(raw_chunks),
        vocab_size=len(df),
        total_tokens=total_tokens,
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
