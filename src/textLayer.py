"""Read and assess the PDF text layer."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

from util import required_command, run


BAD_CHARS = re.compile(r"[\u0400-\u04ff\ue000-\uf8ff\ufffd\x00-\x08\x0b\x0e-\x1f]")
MOJIBAKE = re.compile(r"Ã[\x80-\xbf]|Æ°|á»|Ä‘")


def page_count(pdf: Path) -> int:
    result = run(required_command("pdfinfo"), [str(pdf)])
    match = re.search(r"^Pages:\s+(\d+)", result.stdout, re.MULTILINE)
    if result.returncode or not match:
        raise RuntimeError(f"pdfinfo không đọc được số trang: {pdf}: {result.stderr[:300]}")
    return int(match[1])


def read_text_layer(pdf: Path, first: int, last: int, min_chars: int) -> dict[int, dict[str, Any]]:
    result = run(required_command("pdftotext"), ["-layout", "-enc", "UTF-8", "-f", str(first),
                                                  "-l", str(last), str(pdf), "-"])
    if result.returncode:
        raise RuntimeError(f"pdftotext lỗi: {result.stderr[:300]}")
    chunks = result.stdout.split("\f")
    pages = {}
    for page in range(first, last + 1):
        text = unicodedata.normalize("NFC", chunks[page - first] if page - first < len(chunks) else "")
        chars = len(re.sub(r"\s", "", text))
        bad = len(BAD_CHARS.findall(text))
        bad_ratio = bad / chars if chars else 0
        pages[page] = {"text": text, "chars": chars, "badRatio": bad_ratio,
                       "usable": chars >= min_chars and bad_ratio < 0.002 and not MOJIBAKE.search(text)}
    return pages


pageCount = page_count
readTextLayer = read_text_layer
