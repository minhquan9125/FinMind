"""Image transcription through Gemini API with an optional OpenRouter fallback."""

from __future__ import annotations

import concurrent.futures
import base64
import json
import mimetypes
import os
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from jsonschema import Draft202012Validator
from util import hash_file, load_json, save_json, seconds




PROMPT_VERSION = "api-ir-v2"


def _capacity_error(message: str) -> bool:
    detail = message.lower()
    return any(marker in detail for marker in ("http 402", "http 429", "resource_exhausted",
                                               "quota exceeded", "rate limit exceeded",
                                               "daily limit", "insufficient credits"))
_BOX = {"type": ["array", "null"], "items": {"type": "number", "minimum": 0, "maximum": 1000},
        "minItems": 4, "maxItems": 4}
_AI_CELL = {"type": "object", "additionalProperties": False,
            "properties": {"column_key": {"type": "string"}, "raw": {"type": ["string", "null"]},
                           "box_2d": _BOX}, "required": ["column_key", "raw", "box_2d"]}
_AI_ROW = {"type": "object", "additionalProperties": False,
           "properties": {"code": {"type": ["string", "null"]}, "label_raw": {"type": "string"},
                          "note": {"type": ["string", "null"]}, "box_2d": _BOX,
                          "cells": {"type": "array", "items": _AI_CELL}},
           "required": ["code", "label_raw", "note", "box_2d", "cells"]}
_AI_COLUMN = {"type": "object", "additionalProperties": False,
              "properties": {"key": {"type": "string"}, "header_lines": {"type": "array", "items": {"type": "string"}},
                             "box_2d": _BOX}, "required": ["key", "header_lines", "box_2d"]}
_AI_BLOCK = {"type": "object", "additionalProperties": False,
             "properties": {"type": {"type": "string", "enum": ["heading", "paragraph", "table", "stamp",
                          "signature", "form_code", "toc", "furniture", "kpi"]},
                            "text": {"type": ["string", "null"]}, "box_2d": _BOX,
                            "title": {"type": ["string", "null"]},
                            "unit_text": {"type": ["string", "null"]},
                            "columns": {"type": "array", "items": _AI_COLUMN},
                            "rows": {"type": "array", "items": _AI_ROW}},
             "required": ["type", "text", "box_2d", "title", "unit_text", "columns", "rows"]}
GEMINI_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"pages": {"type": "array", "items": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "file": {"type": "string"},
            "page_type": {"type": "string", "enum": ["table", "text", "mixed", "cover", "blank"]},
            "blocks": {"type": "array", "items": _AI_BLOCK},
            "unreadable": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["file", "page_type", "blocks", "unreadable"],
    }}},
    "required": ["pages"],
}

SYSTEM_INSTRUCTION = """You are a verbatim OCR transcriber for Vietnamese business and financial documents.
Transcribe all visible text in each supplied image in natural reading order. Preserve Vietnamese diacritics and copy numbers exactly, including separators, parentheses, minus signs and dashes. Never calculate, normalize, translate, summarize or correct printed content.
Return blocks in reading order. Text blocks use text and box_2d; table blocks use title, unit_text, columns and rows, with one printed row per row and one value per cell. Use c1, c2, ... for value columns from left to right; code, label_raw and note belong to the row. Omit a cell when nothing is printed. Preserve every printed number exactly. Do not render Markdown tables. Give box_2d as [y0, x0, y1, x1] on a 0-1000 scale relative to the supplied image. Use null only when the box cannot be located; do not guess coordinates. Set irrelevant text/title/unit_text to null and irrelevant columns/rows to empty arrays. Mark unreadable content as [?] and report it in unreadable; never guess digits or names. Classify each page as table, text, mixed, cover or blank.
Return one result for every image, using its exact filename from the accompanying label."""

TEXT_INSTRUCTION = """Read every visible word and number in each supplied annual-report page image.
Return plain transcription in natural reading order with line breaks. Preserve Vietnamese accents,
names, dates, codes, punctuation, decimal and thousands separators exactly as printed. Do not
summarize, translate, calculate, correct financial values, or invent unreadable digits. Use [?]
for a word or number that cannot be read. Return JSON with a pages array; each item has only
file (the exact image filename), text (the transcription), and unreadable (a list of uncertain
fragments). Do not describe tables, coordinates, blocks, or images."""


def _page_text(blocks: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for block in blocks:
        if block["type"] != "table":
            if block["text"]:
                lines.append(block["text"])
            continue
        if block["title"]:
            lines.append(block["title"])
        if block["unit_text"]:
            lines.append(block["unit_text"])
        for column in block["columns"]:
            lines.extend(column["header_lines"])
        for row in block["rows"]:
            values = [row["code"], row["label_raw"], row["note"]]
            values.extend(cell["raw"] for cell in row["cells"])
            lines.append(" ".join(value for value in values if value))
    return unicodedata.normalize("NFC", "\n".join(lines))


def _validated_pages(payload: dict[str, Any], names: list[str]) -> dict[str, dict[str, Any]]:
    errors = list(Draft202012Validator(GEMINI_SCHEMA).iter_errors(payload))
    if errors:
        raise ValueError(f"AI trả sai schema blocks/rows: {errors[0].message}")
    pages: dict[str, dict[str, Any]] = {}
    for page in payload["pages"]:
        filename = Path(page["file"]).name
        if filename not in names or filename in pages:
            raise ValueError(f"AI trả tên trang thiếu/trùng/không hợp lệ: {filename}")
        for block in page["blocks"]:
            if block["type"] == "table":
                keys = [column["key"] for column in block["columns"]]
                if block["text"] is not None or not block["rows"] or keys != [f"c{i}" for i in range(1, len(keys) + 1)]:
                    raise ValueError(f"Bảng AI thiếu dòng hoặc key cột sai: {filename}")
                for row in block["rows"]:
                    cell_keys = [cell["column_key"] for cell in row["cells"]]
                    if len(cell_keys) != len(set(cell_keys)) or any(key not in keys for key in cell_keys):
                        raise ValueError(f"Ô AI trùng key hoặc không thuộc columns: {filename}")
                    if any(cell["raw"] == "" for cell in row["cells"]):
                        raise ValueError(f"Ô AI rỗng phải được bỏ khỏi cells: {filename}")
            elif ((block["text"] is None and block["type"] not in ("stamp", "signature", "furniture"))
                  or block["columns"] or block["rows"]):
                raise ValueError(f"Khối chữ AI không có text: {filename}")
            for item in ([block] + block["columns"] + block["rows"]
                         + [cell for row in block["rows"] for cell in row["cells"]]):
                box = item["box_2d"]
                if box is not None and (box[0] > box[2] or box[1] > box[3]):
                    raise ValueError(f"box_2d ngược chiều: {filename}")
        pages[filename] = {"page_type": page["page_type"], "blocks": page["blocks"],
                           "text": _page_text(page["blocks"]), "unreadable": page["unreadable"]}
    if set(pages) != set(names):
        raise ValueError("AI không trả đủ trang trong batch")
    return pages


def _validated_text_pages(payload: dict[str, Any], names: list[str]) -> dict[str, dict[str, Any]]:
    items = payload.get("pages") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        if len(names) == 1 and isinstance(payload, dict) and isinstance(payload.get("text"), str):
            items = [{"file": names[0], "text": payload["text"],
                      "unreadable": payload.get("unreadable", [])}]
        else:
            raise ValueError("AI không trả về danh sách pages chứa text.")
    pages: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("AI trả trang không phải JSON object.")
        filename = Path(str(item.get("file", item.get("filename", "")))).name
        value = item.get("text")
        if filename not in names or filename in pages or not isinstance(value, str):
            raise ValueError(f"AI trả tên trang hoặc text không hợp lệ: {filename}")
        unreadable = item.get("unreadable", [])
        if not isinstance(unreadable, list) or not all(isinstance(part, str) for part in unreadable):
            unreadable = []
        clean = unicodedata.normalize("NFC", value.strip())
        pages[filename] = {"page_type": "blank" if not clean else "text",
                           "text": clean, "unreadable": unreadable}
    if set(pages) != set(names):
        raise ValueError("AI không trả đủ trang trong batch")
    return pages


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
        pages = _validated_pages(payload, names)
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
        if isinstance(hit, dict) and isinstance(hit.get("blocks"), list) and isinstance(hit.get("text"), str):
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
        if split and len(batch) > 1 and missing and not _capacity_error(call_stats.get("error", "")):
            for job in missing:
                handle([job], False)

    batches = [misses[i:i + batch_size] for i in range(0, len(misses), batch_size)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, concurrency)) as executor:
        list(executor.map(handle, batches))
    return outcomes


def empty_stats() -> dict[str, int]:
    return {"calls": 0, "failedCalls": 0, "seconds": 0, "input_tokens": 0,
            "output_tokens": 0, "thinking_tokens": 0, "cache_read_tokens": 0}


def _message_text(content: Any) -> str:
    """OpenRouter providers may return content as a string or text parts."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [item.get("text", "") for item in content
                 if isinstance(item, dict) and item.get("type", "text") in ("text", "output_text")]
        if parts and all(isinstance(part, str) for part in parts):
            return "".join(parts)
    raise ValueError("OpenRouter trả về message.content không phải văn bản JSON.")

# ----OPENROUTER---
def _call_openrouter(batch: list[dict[str, Any]], model: str,
                     timeout_sec: int, text_only: bool = False,
                     provider: str = "openrouter", base_url: str = "https://openrouter.ai/api/v1",
                     api_key_env: str = "OPENROUTER_API_KEY") -> tuple[dict[str, Any], dict[str, Any]]:
    stats: dict[str, Any] = empty_stats()
    stats["calls"] = 1
    key = os.environ.get(api_key_env)
    if not key:
        return {}, {**stats, "failedCalls": 1, "error": f"Thiếu {api_key_env}."}
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
        response_format = ({"type": "json_object"}
                           if text_only or model.startswith("minimax/minimax-m3.1-flash")
                           else {"type": "json_schema", "json_schema": {
                               "name": "ocr_pages", "strict": True, "schema": GEMINI_SCHEMA}})
        body = {
            "model": model,
            "messages": [{"role": "system", "content": TEXT_INSTRUCTION if text_only else SYSTEM_INSTRUCTION},
                         {"role": "user", "content": content}],
            "response_format": response_format,
            "temperature": 0,
        }
        request = urllib.request.Request(
            f"{base_url.rstrip('/')}/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            result = json.load(response)
        usage = result.get("usage") or {}
        stats["input_tokens"] = usage.get("prompt_tokens") or 0
        stats["output_tokens"] = usage.get("completion_tokens") or 0
        message = _message_text(result["choices"][0]["message"]["content"])
        if not message.strip():
            raise ValueError("OpenRouter trả về nội dung rỗng.")
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            # Some OmniRoute combos return the requested OCR as plain text or
            # wrap their JSON in a Markdown fence despite response_format.
            fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", message, flags=re.IGNORECASE | re.DOTALL)
            if fenced:
                payload = json.loads(fenced.group(1))
            elif text_only and len(names) == 1:
                payload = {"pages": [{"file": names[0], "text": message.strip(), "unreadable": []}]}
            else:
                raise
        pages = _validated_text_pages(payload, names) if text_only else _validated_pages(payload, names)
        stats["seconds"] = seconds(started)
        print(f"  [{provider}] {model} {','.join(names)}: OK, {stats['seconds']}s")
        return pages, stats
    except Exception as exc:
        stats["failedCalls"] = 1
        stats["seconds"] = seconds(started)
        if isinstance(exc, urllib.error.HTTPError):
            message = f"HTTP {exc.code}: {exc.reason}"
        else:
            message = str(exc)
        stats["error"] = message.replace(key, "[REDACTED]")[:1000]
        print(f"  [{provider}] {model}: lỗi: {stats['error']}")
        return {}, stats


def openrouter_transcribe(jobs: list[dict[str, Any]], *, model: str, batch_size: int,
                          concurrency: int, timeout_sec: int, cache_dir: Path,
                          stats: dict[str, Any], text_only: bool = False,
                          provider: str = "openrouter", base_url: str = "https://openrouter.ai/api/v1",
                          api_key_env: str = "OPENROUTER_API_KEY") -> dict[int, dict[str, Any]]:
    """Transcribe only jobs not satisfied by Gemini; keep provider caches separate."""
    outcomes: dict[int, dict[str, Any]] = {}
    lock = threading.Lock()
    capacity_error: str | None = None
    misses = []
    for job in jobs:
        key = hash_file(job["image"])[:32]
        safe_model = model.replace("/", "-").replace(":", "-")
        version = f"{PROMPT_VERSION}-text-v1" if text_only else PROMPT_VERSION
        cache_path = cache_dir / provider / f"{key}-{safe_model}-{version}.json"
        hit = load_json(cache_path)
        if isinstance(hit, dict) and isinstance(hit.get("text"), str) and (text_only or isinstance(hit.get("blocks"), list)):
            outcomes[job["page"]] = {"provider": provider, "model": model,
                                     "cached": True, "page": hit}
        else:
            misses.append({**job, "cachePath": cache_path})

    def handle(batch: list[dict[str, Any]], split: bool = True) -> None:
        nonlocal capacity_error
        with lock:
            unavailable = capacity_error
        if unavailable:
            for job in batch:
                outcomes[job["page"]] = {"provider": provider, "model": model,
                                         "cached": False, "error": unavailable}
            return
        pages, call_stats = _call_openrouter(batch, model, timeout_sec, text_only=text_only,
                                              provider=provider, base_url=base_url,
                                              api_key_env=api_key_env)
        with lock:
            for key in ("calls", "failedCalls", "seconds", "input_tokens", "output_tokens",
                        "thinking_tokens", "cache_read_tokens"):
                stats[key] += call_stats[key]
            if _capacity_error(call_stats.get("error", "")):
                capacity_error = call_stats["error"]
        missing = []
        for job in batch:
            page = pages.get(job["image"].name)
            if page:
                save_json(job["cachePath"], page)
                outcomes[job["page"]] = {"provider": provider, "model": model,
                                         "cached": False, "page": page}
            else:
                missing.append(job)
                outcomes[job["page"]] = {"provider": provider, "model": model,
                                         "cached": False,
                                         "error": call_stats.get("error", "OpenRouter thiếu trang này.")}
        if split and len(batch) > 1 and missing and not _capacity_error(call_stats.get("error", "")):
            for job in missing:
                handle([job], False)

    batches = [misses[i:i + batch_size] for i in range(0, len(misses), batch_size)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, concurrency)) as executor:
        list(executor.map(handle, batches))
    return outcomes


def _call_ollama(job: dict[str, Any], model: str, base_url: str,
                 timeout_sec: int) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Read one image with a local vision model, using Ollama's chat API."""
    stats: dict[str, Any] = {**empty_stats(), "calls": 1}
    started = time.perf_counter()
    image = Path(job["image"])
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": TEXT_INSTRUCTION},
            {"role": "user", "content": f"Transcribe this page. Filename: {image.name}",
             "images": [base64.b64encode(image.read_bytes()).decode("ascii")]},
        ],
        "format": "json",
        "stream": False,
        "options": {"temperature": 0},
    }
    try:
        request = urllib.request.Request(
            base_url.rstrip("/") + "/api/chat",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            result = json.load(response)
        stats["input_tokens"] = result.get("prompt_eval_count") or 0
        stats["output_tokens"] = result.get("eval_count") or 0
        payload = json.loads(result["message"]["content"])
        page = _validated_text_pages(payload, [image.name])[image.name]
        stats["seconds"] = seconds(started)
        print(f"  [ollama] {model} {image.name}: OK, {stats['seconds']}s")
        return page, stats
    except Exception as exc:
        stats["failedCalls"] = 1
        stats["seconds"] = seconds(started)
        stats["error"] = (f"HTTP {exc.code}: {exc.reason}" if isinstance(exc, urllib.error.HTTPError)
                          else str(exc))[:1000]
        print(f"  [ollama] {model}: lỗi: {stats['error']}")
        return None, stats


def ollama_transcribe(jobs: list[dict[str, Any]], *, model: str, base_url: str,
                      timeout_sec: int, cache_dir: Path,
                      stats: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Cache local vision OCR by image and model; continue after page errors."""
    outcomes: dict[int, dict[str, Any]] = {}
    safe_model = model.replace("/", "-").replace(":", "-")
    for job in jobs:
        key = hash_file(job["image"])[:32]
        cache_path = cache_dir / "ollama" / f"{key}-{safe_model}-{PROMPT_VERSION}-text-v1.json"
        hit = load_json(cache_path)
        if isinstance(hit, dict) and isinstance(hit.get("text"), str):
            outcomes[job["page"]] = {"provider": "ollama", "model": model,
                                     "cached": True, "page": hit}
            continue
        page, call_stats = _call_ollama(job, model, base_url, timeout_sec)
        for field in ("calls", "failedCalls", "seconds", "input_tokens", "output_tokens",
                      "thinking_tokens", "cache_read_tokens"):
            stats[field] += call_stats[field]
        if page is not None:
            save_json(cache_path, page)
        outcomes[job["page"]] = {"provider": "ollama", "model": model,
                                 "cached": False, "page": page,
                                 **({"error": call_stats["error"]} if not page else {})}
    return outcomes
