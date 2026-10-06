
from __future__ import annotations
import argparse
import json
import os
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from OCR_annuals import (
    MANIFEST_PATH,
    OUTPUT_ROOT,
    ROOT,
    atomic_json,
    safe_repo_file,
    sha256_file,
)


DEFAULT_MODEL = "gemini-3.8-flash"
FALLBACK_MODELS = ("gemini-3.6-flash", "gemini-3.5-flash")
PROMPT_VERSION = "ocr-text-clean-v1"
RETRY_DELAYS_SECONDS = (2, 4, 8, 16, 30)
MAX_GEMINI_ATTEMPTS = 6
TEMPORARY_ERROR_MARKERS = (
    "503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "OVERLOADED", "TIMEOUT", "DEADLINE"
)
NUMBER_RE = re.compile(r"(?<!\w)[+-]?\d+(?:[.,:/]\d+)*(?:%|‰)?")
GEMINI_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {"text_clean": {"type": "STRING"}},
    "required": ["text_clean"],
}
OLLAMA_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {"text_clean": {"type": "string"}},
    "required": ["text_clean"],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_config_value(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value and value.strip():
        return value.strip()
    for env_file in (ROOT / ".env.local", ROOT / ".env"):
        if not env_file.is_file():
            continue
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, separator, configured_value = line.partition("=")
            if separator and key.strip() == name:
                configured_value = configured_value.strip().strip("\"'")
                if configured_value:
                    return configured_value
    return default


def numeric_tokens(text: str) -> Counter[str]:
    return Counter(NUMBER_RE.findall(text))


def clean_prompt(raw_text: str) -> str:
    return f"""Clean this Tesseract OCR transcription into readable Vietnamese/English text.

Rules:
- Use only the supplied OCR text. Do not use outside knowledge or invent missing content.
- Correct clear OCR character and spacing errors; preserve the original wording, language, reading order, and paragraph meaning.
- If a word cannot be determined from this text alone, keep its OCR form rather than guessing.
- Preserve every number, date, percentage, amount, code, URL, and email exactly. Do not add, remove, or change digits.
- Remove only obvious OCR layout noise such as duplicated whitespace or isolated decorative symbols. Keep meaningful labels and signature names.
- Return a JSON object with exactly one field named "text_clean" containing the cleaned transcription.
- Do not summarize, explain, translate, or add headings.

Tesseract text_raw:
{raw_text}"""


def parse_text_clean_json(content: str, provider: str) -> str:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{provider} response is not valid JSON") from exc
    text_clean = parsed.get("text_clean") if isinstance(parsed, dict) else None
    if not isinstance(text_clean, str) or not text_clean.strip():
        raise ValueError(f"{provider} response has no non-empty text_clean field")
    return text_clean.strip()


def request_gemini_text_clean(client: Any, model: str, raw_text: str) -> str:
    from google.genai import types

    response = client.models.generate_content(
        model=model,
        contents=clean_prompt(raw_text),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=GEMINI_RESPONSE_SCHEMA,
        ),
    )
    if not response.text:
        raise ValueError("Gemini returned an empty response")
    return parse_text_clean_json(response.text, "Gemini")


def is_temporary_error(exc: Exception) -> bool:
    detail = f"{type(exc).__name__} {exc}".upper()
    return any(marker in detail for marker in TEMPORARY_ERROR_MARKERS)


def retry_gemini(operation: Callable[[], str], model: str, page_number: int) -> str:
    """Retry a Gemini call up to six attempts for transient service errors."""
    for attempt in range(MAX_GEMINI_ATTEMPTS):
        try:
            return operation()
        except Exception as exc:
            if not is_temporary_error(exc) or attempt == MAX_GEMINI_ATTEMPTS - 1:
                raise
            delay = RETRY_DELAYS_SECONDS[min(attempt, len(RETRY_DELAYS_SECONDS) - 1)]
            print(f"[page {page_number}] {model} temporary error; retry {attempt + 2}/{MAX_GEMINI_ATTEMPTS} in {delay}s")
            time.sleep(delay)
    raise RuntimeError(f"Gemini failed after {MAX_GEMINI_ATTEMPTS} attempts")


def request_gemini_with_model_fallback(
    client: Any, preferred_model: str, raw_text: str, page_number: int
) -> tuple[str, str]:
    errors = []
    for model in dict.fromkeys((preferred_model, *FALLBACK_MODELS)):
        try:
            text_clean = retry_gemini(
                lambda: request_gemini_text_clean(client, model, raw_text), model, page_number
            )
            return text_clean, model
        except Exception as exc:
            errors.append(f"{model}: {type(exc).__name__}: {exc}")
            if not is_temporary_error(exc):
                break
            print(f"[page {page_number}] {model} unavailable; trying the next Gemini model")
    raise RuntimeError("Gemini failed: " + " | ".join(errors))


def request_openai_compatible_text_clean(
    raw_text: str, base_url: str, model: str, api_key: str
) -> str:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": clean_prompt(raw_text)}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    request = Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=180) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI-compatible HTTP {exc.code}: {detail[:300]}") from exc
    except URLError as exc:
        raise RuntimeError(f"OpenAI-compatible endpoint is unreachable: {exc.reason}") from exc

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("OpenAI-compatible response has no choices[0].message.content") from exc
    if not isinstance(content, str):
        raise ValueError("OpenAI-compatible message content is not text")
    return parse_text_clean_json(content, "OpenAI-compatible")


def request_groq_text_clean(raw_text: str, base_url: str, model: str, api_key: str) -> str:
    """Clean OCR text through Groq's OpenAI-compatible chat completions API."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": clean_prompt(raw_text)}],
        "temperature": 0,
        "max_completion_tokens": 4096,
        "response_format": {"type": "json_object"},
    }
    request = Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=180) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Groq HTTP {exc.code}: {detail[:300]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Groq endpoint is unreachable: {exc.reason}") from exc

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Groq response has no choices[0].message.content") from exc
    if not isinstance(content, str):
        raise ValueError("Groq message content is not text")
    return parse_text_clean_json(content, "Groq")


def request_qwen_local_text_clean(raw_text: str, model: str, base_url: str) -> str:
    request = Request(
        base_url.rstrip("/") + "/api/chat",
        data=json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": clean_prompt(raw_text)}],
            "stream": False,
            "format": OLLAMA_RESPONSE_SCHEMA,
            "options": {"temperature": 0},
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=300) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama HTTP {exc.code}: {detail[:300]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Ollama is unreachable at {base_url}: {exc.reason}") from exc

    content = body.get("message", {}).get("content", "")
    return parse_text_clean_json(content, "Qwen/Ollama")


def safe_error_detail(exc: Exception, secrets: tuple[str, ...]) -> str:
    detail = str(exc)
    for secret in secrets:
        if secret:
            detail = detail.replace(secret, "[REDACTED_API_KEY]")
    return " ".join(detail.split())[:800]


def clean_with_provider_fallback(
    raw_text: str,
    page_number: int,
    gemini_client: Any,
    gemini_model: str,
    oai_config: tuple[str, str, str] | None,
    ollama_model: str,
    ollama_url: str,
    groq_config: tuple[str, str, str] | None,
) -> tuple[str, str, str]:
    """Try Gemini, Groq, another OpenAI-compatible API, then local Ollama/Qwen."""
    errors: list[str] = []
    if gemini_client is not None:
        try:
            text_clean, used_model = request_gemini_with_model_fallback(
                gemini_client, gemini_model, raw_text, page_number
            )
            if numeric_tokens(raw_text) == numeric_tokens(text_clean):
                return text_clean, "GEMINI_TEXT_ONLY", used_model
            errors.append("Gemini: numeric tokens changed")
        except Exception as exc:
            errors.append(f"Gemini: {type(exc).__name__}: {exc}")
    else:
        errors.append("Gemini: skipped (API key or SDK unavailable)")

    if groq_config is not None:
        base_url, model, api_key = groq_config
        try:
            text_clean = request_groq_text_clean(raw_text, base_url, model, api_key)
            if numeric_tokens(raw_text) == numeric_tokens(text_clean):
                return text_clean, "GROQ", model
            errors.append("Groq: numeric tokens changed")
        except Exception as exc:
            errors.append(f"Groq: {type(exc).__name__}: {exc}")
    else:
        errors.append("Groq: skipped (GROQ_API_KEY is not set)")

    if oai_config is not None:
        base_url, model, api_key = oai_config
        try:
            text_clean = request_openai_compatible_text_clean(raw_text, base_url, model, api_key)
            if numeric_tokens(raw_text) == numeric_tokens(text_clean):
                return text_clean, "OPENAI_COMPAT", model
            errors.append("OpenAI-compatible: numeric tokens changed")
        except Exception as exc:
            errors.append(f"OpenAI-compatible: {type(exc).__name__}: {exc}")
    else:
        errors.append("OpenAI-compatible: skipped (OAI_BASE_URL, OAI_MODEL, and OAI_API_KEY must all be set)")

    try:
        text_clean = request_qwen_local_text_clean(raw_text, ollama_model, ollama_url)
        if numeric_tokens(raw_text) == numeric_tokens(text_clean):
            return text_clean, "QWEN_LOCAL", ollama_model
        errors.append("Ollama/Qwen: numeric tokens changed")
    except Exception as exc:
        errors.append(f"Ollama/Qwen: {type(exc).__name__}: {exc}")

    raise RuntimeError("All text-clean providers failed: " + " | ".join(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean Tesseract OCR text_raw and write text_clean.")
    anthropic_base_url = os.environ.get("ANTHROPIC_BASE_URL", "").strip().rstrip("/")
    anthropic_model = os.environ.get("ANTHROPIC_MODEL", "").strip()
    anthropic_api_key = (
        os.environ.get("ANTHROPIC_AUTH_TOKEN", "").strip()
        or os.environ.get("ANTHROPIC_API_KEY", "").strip()
    )
    # OmniRoute accepts both Anthropic Messages and OpenAI-compatible APIs.
    # The OCR cleaner uses the latter, so derive /v1 from its Anthropic gateway URL.
    env_oai_base_url = os.environ.get("OAI_BASE_URL", "").strip()
    env_oai_model = os.environ.get("OAI_MODEL", "").strip()
    env_oai_api_key = os.environ.get("OAI_API_KEY", "").strip()
    default_oai_base_url = (
        env_oai_base_url
        or (f"{anthropic_base_url}/v1" if anthropic_base_url else load_config_value("OAI_BASE_URL"))
    )
    default_oai_model = env_oai_model or anthropic_model or load_config_value("OAI_MODEL")
    default_oai_api_key = env_oai_api_key or anthropic_api_key or load_config_value("OAI_API_KEY")
    parser.add_argument("--symbols", help="Comma-separated ticker filter")
    parser.add_argument("--years", help="Comma-separated report-year filter")
    parser.add_argument("--pages", help="Comma-separated page numbers to process")
    parser.add_argument("--model", default=load_config_value("GEMINI_MODEL", DEFAULT_MODEL), help="Preferred Gemini model")
    parser.add_argument("--oai-base-url", default=default_oai_base_url, help="OpenAI-compatible API base URL")
    parser.add_argument("--oai-model", default=default_oai_model, help="OpenAI-compatible model name")
    parser.add_argument("--oai-api-key", default=default_oai_api_key, help="OpenAI-compatible API key")
    parser.add_argument("--groq-base-url", default=load_config_value("GROQ_BASE_URL", "https://api.groq.com/openai/v1"), help="Groq-compatible API base URL")
    parser.add_argument("--groq-model", default=load_config_value("GROQ_MODEL", "openai/gpt-oss-20b"), help="Groq model ID")
    parser.add_argument("--groq-api-key", default=load_config_value("GROQ_API_KEY"), help="Groq API key")
    parser.add_argument("--ollama-url", default=load_config_value("OLLAMA_URL", "http://localhost:11434"), help="Local Ollama server URL")
    parser.add_argument("--ollama-model", default=load_config_value("OLLAMA_MODEL", "qwen2.5:7b-instruct"), help="Local Qwen model name")
    parser.add_argument("--refresh", action="store_true", help="Regenerate text_clean even when already written by a provider")
    args = parser.parse_args()

    if not MANIFEST_PATH.is_file():
        parser.error(f"Annual-report manifest not found: {MANIFEST_PATH}")

    gemini_key = load_config_value("GEMINI_API_KEY")
    gemini_client = None
    if gemini_key:
        try:
            from google import genai

            gemini_client = genai.Client(api_key=gemini_key)
        except ImportError:
            print("Gemini SDK unavailable; continuing with other configured providers")

    oai_values = (args.oai_base_url, args.oai_model, args.oai_api_key)
    oai_config = tuple(value.strip() for value in oai_values) if all(oai_values) else None
    # Reuse an existing OAI key only when its configured endpoint is explicitly Groq.
    # This keeps older project .env files working while preferring a dedicated Groq key.
    oai_points_to_groq = bool(args.oai_base_url and "api.groq.com" in args.oai_base_url.lower())
    groq_key = args.groq_api_key or (args.oai_api_key if oai_points_to_groq else None)
    groq_config = (
        ("https://api.groq.com/openai/v1", args.groq_model.strip(), groq_key.strip())
        if args.groq_model and groq_key
        else None
    )
    if oai_points_to_groq:
        # The same endpoint/key is already routed through the normalized Groq config.
        oai_config = None
    ollama_model = args.ollama_model
    ollama_url = args.ollama_url
    secrets = tuple(value for value in (gemini_key, args.oai_api_key, args.groq_api_key, groq_key) if value)

    symbols = {part.strip().upper() for part in args.symbols.split(",") if part.strip()} if args.symbols else None
    years = {int(part.strip()) for part in args.years.split(",") if part.strip()} if args.years else None
    pages_filter = {int(part.strip()) for part in args.pages.split(",") if part.strip()} if args.pages else None
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    records = [item for item in manifest.get("documents", []) if item.get("status") == "DOWNLOADED"]
    if symbols:
        records = [item for item in records if str(item.get("symbol", "")).upper() in symbols]
    if years:
        records = [item for item in records if int(item.get("year", 0)) in years]

    cleaned = 0
    failures: list[dict[str, Any]] = []
    for record in records:
        symbol = str(record.get("symbol", "")).upper()
        year = int(record.get("year", 0))
        for relative_pdf in record.get("pdf_paths") or []:
            pdf = safe_repo_file(relative_pdf)
            json_path = OUTPUT_ROOT / symbol / str(year) / f"{pdf.stem}.json"
            if not json_path.is_file():
                continue
            try:
                payload = json.loads(json_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                failures.append({"symbol": symbol, "year": year, "pdf": pdf.name, "error": f"Invalid extraction JSON: {type(exc).__name__}"})
                continue
            if payload.get("document", {}).get("sha256") != sha256_file(pdf):
                failures.append({"symbol": symbol, "year": year, "pdf": pdf.name, "error": "PDF hash differs from extraction JSON"})
                continue

            changed = False
            for page in payload.get("pages", []):
                if page.pop("gemini_review", None) is not None:
                    changed = True
                if page.pop("gemini_review_history", None) is not None:
                    changed = True

                page_number = int(page.get("page_number", 0))
                if pages_filter and page_number not in pages_filter:
                    continue
                if page.get("extraction_method") != "tesseract":
                    continue
                raw_text = page.get("text_raw") or ""
                if not raw_text.strip():
                    continue
                if page.get("text_clean_source") in {"GEMINI_TEXT_ONLY", "GROQ", "OPENAI_COMPAT", "QWEN_LOCAL"} and not args.refresh:
                    continue

                try:
                    text_clean, source, used_model = clean_with_provider_fallback(
                        raw_text=raw_text,
                        page_number=page_number,
                        gemini_client=gemini_client,
                        gemini_model=args.model,
                        oai_config=oai_config,
                        ollama_model=ollama_model,
                        ollama_url=ollama_url,
                        groq_config=groq_config,
                    )
                    page["text_clean"] = text_clean
                    page["text_clean_source"] = source
                    page["text_clean_model"] = used_model
                    page["text_clean_prompt_version"] = PROMPT_VERSION
                    page["text_clean_at"] = utc_now()
                    changed = True
                    cleaned += 1
                    print(f"[{symbol} {year} p.{page_number}] text_clean saved by {source} ({used_model})")
                except Exception as exc:
                    detail = safe_error_detail(exc, secrets)
                    failures.append({
                        "symbol": symbol,
                        "year": year,
                        "page": page_number,
                        "error": type(exc).__name__,
                        "detail": detail,
                    })
                    print(f"[{symbol} {year} p.{page_number}] failed: {type(exc).__name__}: {detail}")

            if changed:
                atomic_json(json_path, payload)

    print(json.dumps({"text_clean_pages": cleaned, "failures": failures}, ensure_ascii=False))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
