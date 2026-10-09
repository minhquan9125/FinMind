"""Image transcription through Gemini API with an optional OpenRouter fallback."""

from __future__ import annotations

import concurrent.futures
import base64
import json
import mimetypes
import os
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from util import hash_file, load_json, save_json, seconds




PROMPT_VERSION = "api-v1"
GEMINI_SCHEMA = {
    "type": "object",
    "properties": {"pages": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "file": {"type": "string"},
            "page_type": {"type": "string", "enum": ["table", "text", "mixed", "cover", "blank"]},
            "text": {"type": "string"},
            "unreadable": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["file", "page_type", "text", "unreadable"],
    }}},
    "required": ["pages"],
}

SYSTEM_INSTRUCTION = """You are a verbatim OCR transcriber for Vietnamese business and financial documents.
Transcribe all visible text in each supplied image in natural reading order. Preserve Vietnamese diacritics and copy numbers exactly, including separators, parentheses, minus signs and dashes. Never calculate, normalize, translate, summarize or correct printed content.
Render tables as Markdown pipe tables, one printed row per table row, preserving empty cells and column order. Mark unreadable content as [?] and report it in unreadable; never guess digits or names. Put stamp text on its own line prefixed with [stamp]. Classify each page as table, text, mixed, cover or blank.
Return one result for every image, using its exact filename from the accompanying label."""


def _call_api(batch: list[dict[str, Any]], model: str, timeout_sec: int) -> tuple[dict[str, Any], dict[str, Any]]:
    stats: dict[str, Any] = {
        "calls": 1, "failedCalls": 0, "seconds": 0,
        "input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0, "cache_read_tokens": 0,
    }
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        stats["failedCalls"] = 1
        return {}, {**stats, "error": "Thiếu biến môi trường GEMINI_API_KEY."}

    client = None
    started = time.perf_counter()
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=timeout_sec * 1000),
        )
        names = [job["image"].name for job in batch]
        contents: list[Any] = [types.Part.from_text(
            text="Transcribe the attached page images. The text label immediately before each image gives its exact filename. "
                 f"Return exactly one pages entry for each of these filenames, in order: {', '.join(names)}."
        )]
        for job in batch:
            image = Path(job["image"])
            mime_type = mimetypes.guess_type(image.name)[0] or "image/png"
            contents.append(types.Part.from_text(text=f"Filename: {image.name}"))
            contents.append(types.Part.from_bytes(data=image.read_bytes(), mime_type=mime_type))

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_json_schema=GEMINI_SCHEMA,
                temperature=0,
            ),
        )
        usage = response.usage_metadata
        if usage:
            stats["input_tokens"] = getattr(usage, "prompt_token_count", 0) or 0
            stats["output_tokens"] = getattr(usage, "candidates_token_count", 0) or 0
            stats["thinking_tokens"] = getattr(usage, "thoughts_token_count", 0) or 0
            stats["cache_read_tokens"] = getattr(usage, "cached_content_token_count", 0) or 0

        if not response.text:
            raise ValueError("Gemini API trả về nội dung rỗng.")
        payload = json.loads(response.text)
        raw_pages = payload.get("pages")
        if not isinstance(raw_pages, list):
            raise ValueError("Gemini API trả JSON không có danh sách pages.")
        pages = {}
        for page in raw_pages:
            filename = Path(str(page["file"])).name
            pages[filename] = {
                "page_type": page["page_type"],
                "text": unicodedata.normalize("NFC", page["text"]),
                "unreadable": page["unreadable"],
            }
        stats["seconds"] = seconds(started)
        print(f"  [gemini-api] {model} {','.join(names)}: OK, {stats['seconds']}s")
        return pages, stats
    except Exception as exc:
        stats["failedCalls"] = 1
        stats["seconds"] = seconds(started)
        message = str(exc)
        if api_key:
            message = message.replace(api_key, "[REDACTED]")
        stats["error"] = message[:1000] or type(exc).__name__
        print(f"  [gemini-api] {model}: lỗi: {stats['error']}")
        return {}, stats
    finally:
        if client is not None:
            client.close()


def gemini_transcribe(jobs: list[dict[str, Any]], *, model: str, batch_size: int,
                      concurrency: int, timeout_sec: int, cache_dir: Path,
                      stats: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Transcribe page images with Gemini API; cache results by image and model."""
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

    def handle(batch: list[dict[str, Any]], split: bool = True) -> None:
        pages, call_stats = _call_api(batch, model, timeout_sec)
        with stats_lock:
            for key in ("calls", "failedCalls", "seconds", "input_tokens", "output_tokens",
                        "thinking_tokens", "cache_read_tokens"):
                stats[key] += call_stats[key]
        missing = []
        for job in batch:
            page = pages.get(job["image"].name)
            if page:
                save_json(job["cachePath"], page)
                outcomes[job["page"]] = {"model": model, "cached": False, "page": page}
            else:
                missing.append(job)
                outcomes[job["page"]] = {
                    "model": model, "cached": False,
                    "error": call_stats.get("error", "Gemini API không trả về trang này."),
                }
        if split and len(batch) > 1 and missing:
            for job in missing:
                handle([job], False)

    batches = [misses[i:i + batch_size] for i in range(0, len(misses), batch_size)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, concurrency)) as executor:
        list(executor.map(handle, batches))
    return outcomes


def empty_stats() -> dict[str, int]:
    return {"calls": 0, "failedCalls": 0, "seconds": 0, "input_tokens": 0,
            "output_tokens": 0, "thinking_tokens": 0, "cache_read_tokens": 0}

# ----OPENROUTER---
def _call_openrouter(batch: list[dict[str, Any]], model: str,
                     timeout_sec: int) -> tuple[dict[str, Any], dict[str, Any]]:
    stats: dict[str, Any] = empty_stats()
    stats["calls"] = 1
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        return {}, {**stats, "failedCalls": 1, "error": "Thiếu OPENROUTER_API_KEY."}
    started = time.perf_counter()
    names = [job["image"].name for job in batch]
    try:
        content: list[dict[str, Any]] = [{
            "type": "text",
            "text": "Transcribe these page images. Return exactly one pages entry for each filename, "
                    f"in order: {', '.join(names)}.",
        }]
        for job in batch:
            image = Path(job["image"])
            mime = mimetypes.guess_type(image.name)[0] or "image/png"
            encoded = base64.b64encode(image.read_bytes()).decode("ascii")
            content.extend(({"type": "text", "text": f"Filename: {image.name}"},
                            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}}))
        body = {
            "model": model,
            "messages": [{"role": "system", "content": SYSTEM_INSTRUCTION},
                         {"role": "user", "content": content}],
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "ocr_pages", "strict": True, "schema": GEMINI_SCHEMA}},
            "temperature": 0,
        }
        request = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            result = json.load(response)
        usage = result.get("usage") or {}
        stats["input_tokens"] = usage.get("prompt_tokens") or 0
        stats["output_tokens"] = usage.get("completion_tokens") or 0
        message = result["choices"][0]["message"]["content"]
        if not isinstance(message, str) or not message.strip():
            raise ValueError("OpenRouter trả về nội dung rỗng.")
        payload = json.loads(message)
        if not isinstance(payload.get("pages"), list):
            raise ValueError("OpenRouter không trả về danh sách pages.")
        pages: dict[str, Any] = {}
        for page in payload["pages"]:
            filename = Path(page["file"]).name
            if filename not in names or filename in pages:
                raise ValueError(f"OpenRouter trả về tên trang không hợp lệ: {filename}")
            if page["page_type"] not in ("table", "text", "mixed", "cover", "blank") \
                    or not isinstance(page["text"], str) \
                    or not isinstance(page["unreadable"], list):
                raise ValueError(f"OpenRouter trả về trang sai cấu trúc: {filename}")
            pages[filename] = {"page_type": page["page_type"],
                               "text": unicodedata.normalize("NFC", page["text"]),
                               "unreadable": page["unreadable"]}
        stats["seconds"] = seconds(started)
        print(f"  [openrouter] {model} {','.join(names)}: OK, {stats['seconds']}s")
        return pages, stats
    except Exception as exc:
        stats["failedCalls"] = 1
        stats["seconds"] = seconds(started)
        if isinstance(exc, urllib.error.HTTPError):
            message = f"HTTP {exc.code}: {exc.reason}"
        else:
            message = str(exc)
        stats["error"] = message.replace(key, "[REDACTED]")[:1000]
        print(f"  [openrouter] {model}: lỗi: {stats['error']}")
        return {}, stats


def openrouter_transcribe(jobs: list[dict[str, Any]], *, model: str, batch_size: int,
                          concurrency: int, timeout_sec: int, cache_dir: Path,
                          stats: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Transcribe only jobs not satisfied by Gemini; keep provider caches separate."""
    outcomes: dict[int, dict[str, Any]] = {}
    lock = threading.Lock()
    misses = []
    for job in jobs:
        key = hash_file(job["image"])[:32]
        safe_model = model.replace("/", "-").replace(":", "-")
        cache_path = cache_dir / "openrouter" / f"{key}-{safe_model}-{PROMPT_VERSION}.json"
        hit = load_json(cache_path)
        if hit:
            outcomes[job["page"]] = {"provider": "openrouter", "model": model,
                                     "cached": True, "page": hit}
        else:
            misses.append({**job, "cachePath": cache_path})

    def handle(batch: list[dict[str, Any]], split: bool = True) -> None:
        pages, call_stats = _call_openrouter(batch, model, timeout_sec)
        with lock:
            for key in ("calls", "failedCalls", "seconds", "input_tokens", "output_tokens",
                        "thinking_tokens", "cache_read_tokens"):
                stats[key] += call_stats[key]
        missing = []
        for job in batch:
            page = pages.get(job["image"].name)
            if page:
                save_json(job["cachePath"], page)
                outcomes[job["page"]] = {"provider": "openrouter", "model": model,
                                         "cached": False, "page": page}
            else:
                missing.append(job)
                outcomes[job["page"]] = {"provider": "openrouter", "model": model,
                                         "cached": False,
                                         "error": call_stats.get("error", "OpenRouter thiếu trang này.")}
        if split and len(batch) > 1 and missing:
            for job in missing:
                handle([job], False)

    batches = [misses[i:i + batch_size] for i in range(0, len(misses), batch_size)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, concurrency)) as executor:
        list(executor.map(handle, batches))
    return outcomes
