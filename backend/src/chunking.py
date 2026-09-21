"""PDF extraction and word-window chunking.

Ported 1:1 from the original browser-only demo (VectorRAG_Demo.html) so the
chunk boundaries produced by the backend match what the team already
validated in the demo: a ~130-word window per chunk with a 100-word stride
(i.e. a 30-word overlap between consecutive chunks of the same page).
"""

from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader


@dataclass
class Page:
    page: int
    text: str


@dataclass
class RawChunk:
    page: int
    text: str


def extract_pages(pdf_bytes: bytes) -> list[Page]:
    """Extract per-page text from a PDF file, mirroring extractPages() in the
    original demo (pdf.js getTextContent + whitespace collapsing)."""
    reader = PdfReader(BytesIO(pdf_bytes))
    pages: list[Page] = []
    for index, page in enumerate(reader.pages, start=1):
        raw = page.extract_text() or ""
        text = " ".join(raw.split())
        pages.append(Page(page=index, text=text))
    return pages


def build_chunks(pages: list[Page], chunk_words: int, chunk_stride: int) -> list[RawChunk]:
    """Port of buildChunks() in the demo. A page shorter than chunk_words
    becomes a single chunk; longer pages are split into overlapping windows.
    """
    out: list[RawChunk] = []
    for page in pages:
        if not page.text:
            continue
        words = page.text.split(" ")
        if len(words) <= chunk_words:
            out.append(RawChunk(page=page.page, text=page.text))
            continue

        start = 0
        while start < len(words):
            window = words[start : start + chunk_words]
            # Drop a tail slice that is too short to be useful; it is already
            # covered by the previous overlapping window.
            if len(window) < 25 and start != 0:
                break
            out.append(RawChunk(page=page.page, text=" ".join(window)))
            if start + chunk_words >= len(words):
                break
            start += chunk_stride
    return out
