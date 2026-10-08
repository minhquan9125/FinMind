"""Shared subprocess, cache, hashing, timing and page utilities."""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, TypeVar


def run(cmd: str, args: list[str], *, cwd: Path | None = None,
        env: dict[str, str] | None = None, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([cmd, *args], cwd=cwd, env=env, timeout=timeout,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)


def find_command(name: str) -> str | None:
    found = shutil.which(name)
    if not found and name == "tesseract" and platform.system() == "Windows":
        for root in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"),
                     r"C:\Program Files"):
            if root:
                candidate = Path(root) / "Tesseract-OCR" / "tesseract.exe"
                if candidate.is_file():
                    return str(candidate)
    return found


def required_command(name: str) -> str:
    found = find_command(name)
    if not found:
        raise RuntimeError(f"Thiếu lệnh {name}. Xem README để cài công cụ OCR.")
    return found


def load_json(path: Path) -> Any | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def seconds(start: float) -> float:
    return round(time.perf_counter() - start, 3)


def js_round(value: float, places: int = 0) -> int | float:
    scale = 10 ** places
    result = math.floor(value * scale + 0.5) / scale
    return int(result) if result.is_integer() else result


def parse_pages(spec: str | None, maximum: int) -> list[int]:
    if not spec:
        return list(range(1, maximum + 1))
    pages: set[int] = set()
    for part in spec.split(","):
        match = re.fullmatch(r"\s*(\d+)(?:\s*-\s*(\d+))?\s*", part)
        if not match:
            raise ValueError(f"Khoảng trang không hợp lệ: {part!r}")
        first, last = int(match[1]), int(match[2] or match[1])
        if first > last or first < 1 or last > maximum:
            raise ValueError(f"Trang ngoài phạm vi 1–{maximum}: {part!r}")
        pages.update(range(first, last + 1))
    return sorted(pages)


def count(values: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        result[value] = result.get(value, 0) + 1
    return result


T = TypeVar("T")
R = TypeVar("R")


def pool(items: list[T], size: int, fn: Callable[[T, int], R]) -> list[R]:
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, size)) as executor:
        return list(executor.map(lambda pair: fn(pair[1], pair[0]), enumerate(items)))


def sha256(data: bytes | str) -> str:
    return hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()


def readJson(path: str | Path) -> Any | None:
    return load_json(Path(path))


def writeJson(path: str | Path, value: Any) -> None:
    save_json(Path(path), value)


def stopwatch() -> Callable[[], float]:
    started = time.perf_counter()
    return lambda: round(time.perf_counter() - started, 3)


parsePages = parse_pages
hasCommand = lambda name: find_command(name) is not None
