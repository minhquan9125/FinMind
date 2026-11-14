"""Render PDF pages and rotate them upright for OCR."""

from __future__ import annotations

import platform
import re
import shutil
import sys
from pathlib import Path

from util import required_command, run


def page_name(page: int) -> str:
    return f"p-{page:03d}"


def upright_page(pdf: Path, page: int, work_dir: Path, long_side: int,
                 env: dict[str, str]) -> tuple[Path, int]:
    raw = work_dir / f"{page_name(page)}.png"
    if not raw.is_file():
        result = run(required_command("pdftoppm"), ["-f", str(page), "-l", str(page),
                 "-scale-to", str(long_side), "-png", "-singlefile", str(pdf), str(raw.with_suffix(""))])
        if result.returncode:
            raise RuntimeError(f"pdftoppm lỗi trang {page}: {result.stderr[:300]}")
    result = run(required_command("tesseract"), [str(raw), "-", "--psm", "0"], env=env)
    log = result.stdout + result.stderr
    rotation_match = re.search(r"Rotate:\s*(\d+)", log)
    confidence_match = re.search(r"Orientation confidence:\s*([\d.]+)", log)
    rotation = int(rotation_match[1]) if rotation_match and confidence_match and float(confidence_match[1]) >= 2 else 0
    if rotation == 0:
        return raw, 0
    upright = work_dir / f"{page_name(page)}.up.png"
    if upright.is_file():
        return upright, rotation
    if platform.system() == "Darwin" and shutil.which("sips"):
        turn = run("sips", ["-r", str(rotation), str(raw), "--out", str(upright)])
    elif shutil.which("magick"):
        turn = run("magick", [str(raw), "-rotate", str(rotation), str(upright)])
    else:
        print(f"⚠ Trang {page} cần xoay {rotation}° nhưng thiếu sips/magick.", file=sys.stderr)
        return raw, 0
    return (upright, rotation) if turn.returncode == 0 else (raw, 0)


uprightPage = upright_page
