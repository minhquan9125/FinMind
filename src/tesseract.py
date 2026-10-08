"""Tesseract TSV OCR and Vietnamese language setup."""

from __future__ import annotations

import os
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import TypedDict

from util import js_round, required_command, run, seconds


LOW_CONF = 60


class TessResult(TypedDict):
    text: str
    chars: int
    words: int
    wordItems: list[TessWord]
    meanConf: int
    lowConfRatio: float
    seconds: float


class TessWord(TypedDict):
    text: str
    bbox: list[int]
    conf: float
    block: int
    paragraph: int
    line: int


def tess_env(tessdata: str | None) -> dict[str, str]:
    env = dict(os.environ)
    for candidate in (tessdata, env.get("TESSDATA_PREFIX"), "tessdata_best"):
        if candidate and (Path(candidate).resolve() / "vie.traineddata").is_file():
            env["TESSDATA_PREFIX"] = str(Path(candidate).resolve())
            break
    result = run(required_command("tesseract"), ["--list-langs"], env=env)
    if not re.search(r"^vie$", result.stdout + result.stderr, re.MULTILINE):
        raise RuntimeError("Tesseract chưa có ngôn ngữ 'vie'. Xem README.")
    if not re.search(r"^osd$", result.stdout + result.stderr, re.MULTILINE):
        print("⚠ Không có osd.traineddata; không tự xoay trang.", file=sys.stderr)
    return env


def tesseract(image: Path, env: dict[str, str]) -> TessResult:
    """Read Vietnamese OCR as TSV, then rebuild text by paragraph and line."""
    start = time.perf_counter()
    # Use TSV flags because tessdata_best does not include the tsv config file.
    result = run(required_command("tesseract"), [str(image), "-", "-l", "vie", "--psm", "3",
                 "--dpi", "300", "-c", "preserve_interword_spaces=1",
                 "-c", "tessedit_create_tsv=1", "-c", "tessedit_create_txt=0"],
                 env={**env, "OMP_THREAD_LIMIT": "1"})
    if result.returncode or not result.stdout.startswith("level\t"):
        raise RuntimeError(f"tesseract không ra TSV ({image}): {result.stderr[:300]}")
    lines: list[str] = []
    confidences: list[float] = []
    word_items: list[TessWord] = []
    current: list[str] = []
    line_key = paragraph_key = ""

    def flush() -> None:
        nonlocal current
        if current:
            lines.append(" ".join(current))
        current = []

    for row in result.stdout.splitlines()[1:]:
        cells = row.split("\t")
        if len(cells) < 12 or cells[0] != "5":
            continue
        word = unicodedata.normalize("NFC", cells[11].strip())
        confidence = float(cells[10])
        if not word or confidence < 0:
            continue
        left, top, width, height = (int(cells[index]) for index in (6, 7, 8, 9))
        if left < 0 or top < 0 or width <= 0 or height <= 0:
            raise RuntimeError(f"Tesseract TSV có bbox không hợp lệ ({image}): {row[:200]}")
        word_items.append({"text": word, "bbox": [left, top, left + width, top + height],
                           "conf": confidence, "block": int(cells[2]),
                           "paragraph": int(cells[3]), "line": int(cells[4])})
        paragraph = f"{cells[2]}.{cells[3]}"
        line = f"{paragraph}.{cells[4]}"
        if line != line_key:
            flush()
            if paragraph_key and paragraph != paragraph_key:
                lines.append("")
            line_key, paragraph_key = line, paragraph
        current.append(word)
        confidences.append(confidence)
    flush()
    text = unicodedata.normalize("NFC", "\n".join(lines))
    count = len(confidences)
    return {"text": text, "chars": len(re.sub(r"\s", "", text)), "words": count,
            "wordItems": word_items,
            "meanConf": int(js_round(sum(confidences) / count)) if count else 0,
            "lowConfRatio": js_round(sum(c < LOW_CONF for c in confidences) / count, 3) if count else 1,
            "seconds": seconds(start)}
