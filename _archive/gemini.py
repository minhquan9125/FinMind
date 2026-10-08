"""Gemini transcription through agy, with batching and cache."""

from __future__ import annotations

import concurrent.futures
import json
import subprocess
import threading
import time
import unicodedata
from pathlib import Path
from typing import Any

from util import hash_file, load_json, required_command, run, save_json, seconds


PROMPT_VERSION = "v1"
GEMINI_SCHEMA = {
    "type": "object",
    "properties": {"pages": {"type": "array", "items": {
        "type": "object",
        "properties": {"file": {"type": "string"},
                       "page_type": {"type": "string", "enum": ["table", "text", "mixed", "cover", "blank"]},
                       "text": {"type": "string"},
                       "unreadable": {"type": "array", "items": {"type": "string"}}},
        "required": ["file", "page_type", "text", "unreadable"]}}},
    "required": ["pages"],
}


def gemini_prompt(files: list[str]) -> str:
    return f"""You are a verbatim OCR transcriber for Vietnamese business and financial documents.
Open each of these image files in the current directory with your file viewing tool, one by one: {', '.join(files)}.
Return exactly one entry in \"pages\" per file, with \"file\" set to the exact file name.
Rules:
- Transcribe ALL visible text in natural reading order. Keep Vietnamese diacritics exactly as printed.
- Copy numbers exactly as printed, including dots, commas, parentheses, minus signs and dashes. Never compute, normalize, translate, summarize or correct anything, even if totals look wrong.
- Render tables as Markdown pipe tables, one printed row per table row, keeping empty cells empty and columns in printed order.
- If something is unreadable, write [?] in its place and describe it in \"unreadable\". Never guess digits or names.
- Text inside stamps or seals goes on its own line prefixed with \"[stamp] \".
- page_type: \"table\" for financial statements or other tables, \"text\" for running text, \"mixed\", \"cover\" for title pages with little text, \"blank\".
Do not run terminal commands, do not call MCP tools, do not create or edit files."""


def call_agy(batch: list[dict[str, Any]], model: str, timeout_sec: int) -> tuple[dict[str, Any], dict[str, Any]]:
    directory = batch[0]["image"].parent
    schema_path = directory / f".agy-schema-{PROMPT_VERSION}.json"
    if not schema_path.is_file():
        save_json(schema_path, GEMINI_SCHEMA)
    files = [job["image"].name for job in batch]
    start = time.perf_counter()
    try:
        result = run(required_command("agy"), ["-p", gemini_prompt(files), "--model", model,
                     "--output-format", "json", "--json-schema", str(schema_path),
                     "--print-timeout", f"{timeout_sec}s", "--disable-slash-commands"],
                     cwd=directory, timeout=timeout_sec + 60)
    except subprocess.TimeoutExpired:
        result = subprocess.CompletedProcess(["agy"], -1, "", "timeout")
    print(f"  [agy] {model} {','.join(files)}: exit {result.returncode}, {seconds(start)}s")
    stats = {"calls": 1, "failedCalls": 0, "seconds": seconds(start),
             "input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0, "cache_read_tokens": 0}
    left, right = result.stdout.find("{"), result.stdout.rfind("}")
    if left < 0 or right < left:
        stats["failedCalls"] = 1
        return {}, {**stats, "error": f"agy không trả JSON: {result.stderr[:300]}"}
    try:
        payload = json.loads(result.stdout[left:right + 1])
        usage = payload.get("usage") or {}
        for key in ("input_tokens", "output_tokens", "thinking_tokens", "cache_read_tokens"):
            stats[key] = usage.get(key, 0)
        raw = payload.get("structured_output") or {}
        if isinstance(raw, str):
            raw = json.loads(raw)
        if payload.get("status") != "SUCCESS" or not isinstance(raw.get("pages"), list):
            raise ValueError(f"agy status={payload.get('status')}")
        pages = {Path(str(page["file"])).name: {
            "page_type": page["page_type"], "text": unicodedata.normalize("NFC", page["text"]),
            "unreadable": page["unreadable"]} for page in raw["pages"]}
        return pages, stats
    except (ValueError, KeyError, TypeError) as exc:
        stats["failedCalls"] = 1
        return {}, {**stats, "error": str(exc)}


def gemini_transcribe(jobs: list[dict[str, Any]], *, model: str, batch_size: int,
                      concurrency: int, timeout_sec: int, cache_dir: Path,
                      stats: dict[str, Any]) -> dict[int, dict[str, Any]]:
    outcomes: dict[int, dict[str, Any]] = {}
    stats_lock = threading.Lock()
    misses = []
    for job in jobs:
        key = hash_file(job["image"])[:32]
        cache_path = cache_dir / "gemini" / f"{key}-{model}-{PROMPT_VERSION}.json"
        hit = load_json(cache_path)
        if hit:
            outcomes[job["page"]] = {"model": model, "cached": True, "page": hit}
        else:
            misses.append({**job, "cachePath": cache_path})
    if misses:
        required_command("agy")

    def handle(batch: list[dict[str, Any]], split: bool = True) -> None:
        pages, call_stats = call_agy(batch, model, timeout_sec)
        with stats_lock:
            for key in ("calls", "failedCalls", "seconds", "input_tokens", "output_tokens", "thinking_tokens", "cache_read_tokens"):
                stats[key] += call_stats[key]
        missing = []
        for job in batch:
            page = pages.get(job["image"].name)
            if page:
                save_json(job["cachePath"], page)
                outcomes[job["page"]] = {"model": model, "cached": False, "page": page}
            else:
                missing.append(job)
                outcomes[job["page"]] = {"model": model, "cached": False,
                                         "error": call_stats.get("error", "trang không có trong kết quả gộp")}
        if split and len(batch) > 1:
            for job in missing:
                handle([job], False)

    batches = [misses[i:i + batch_size] for i in range(0, len(misses), batch_size)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, concurrency)) as executor:
        list(executor.map(handle, batches))
    return outcomes


def emptyStats() -> dict[str, int]:
    return {"calls": 0, "failedCalls": 0, "seconds": 0, "input_tokens": 0,
            "output_tokens": 0, "thinking_tokens": 0, "cache_read_tokens": 0}


geminiTranscribe = gemini_transcribe
