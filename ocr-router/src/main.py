"""Python OCR router POC: text layer -> Tesseract -> Gemini when needed."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from crossCheck import cross_check, number_keys
from model import empty_stats, gemini_transcribe, openrouter_transcribe, ollama_transcribe
from render import page_name, upright_page
from tesseract import tess_env, tesseract
from textLayer import page_count, read_text_layer
from util import count, find_command, hash_file, load_json, parse_pages, save_json, seconds

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

INFO_FLAGS = {"TEXT_LAYER_BROKEN", "NEAR_EMPTY", "ESCALATED"}

# Load project-local secrets regardless of the terminal's current directory.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def is_critical(text: str) -> bool:
    loose = unicodedata.normalize("NFD", text)
    loose = "".join(c for c in loose if not unicodedata.combining(c)).replace("đ", "d").replace("Đ", "D").lower()
    amounts = sum(len(d) >= 6 for d in number_keys(text))
    return bool(re.search(r"\bma so\b|bang can doi|ket qua (hoat dong )?kinh doanh|luu chuyen tien te|tinh hinh tai chinh", loose)) or amounts >= 8


def preflight(cfg: argparse.Namespace) -> dict[str, str]:
    commands = ["pdfinfo", "pdftotext"]
    provider = getattr(cfg, "provider", "auto")
    if cfg.gemini != "never" and provider != "local":
        available = {"gemini": bool(os.environ.get("GEMINI_API_KEY")),
                     "openrouter": bool(os.environ.get("OPENROUTER_API_KEY")),
                     "codecraft": bool(os.environ.get("CODECRAFT_API_KEY")),
                     "omniroute": bool(os.environ.get("OMNIROUTE_API_KEY"))}
        # Auto may finish with the local Ollama vision fallback even without API keys.
        if provider in available and not available[provider]:
            raise RuntimeError(f"Thiếu {provider.upper()}_API_KEY cho --provider {provider}.")
    missing = [command for command in commands if not find_command(command)]
    if missing:
        raise RuntimeError(f"Thiếu lệnh: {', '.join(missing)}")
    return os.environ.copy()


def process_pdf(pdf: Path, cfg: argparse.Namespace, env: dict[str, str]) -> None:
    start = time.perf_counter()
    times: dict[str, float] = {}
    gemini_api = empty_stats()
    openrouter_api = empty_stats()
    codecraft_api = empty_stats()
    omniroute_api = empty_stats()
    ollama_api = empty_stats()
    openrouter_model = getattr(cfg, "openrouter_model", os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini"))
    codecraft_model = getattr(cfg, "codecraft_model", os.environ.get("CODECRAFT_MODEL", "qwen3.8-27b"))
    codecraft_url = os.environ.get("CODECRAFT_BASE_URL", "https://codecraftapi.com/v1")
    omniroute_model = getattr(cfg, "omniroute_model", os.environ.get("OMNIROUTE_MODEL", "gemini"))
    omniroute_url = os.environ.get("OMNIROUTE_BASE_URL", "http://localhost:20128/v1")
    provider = getattr(cfg, "provider", "auto")
    doc_dir = cfg.out / pdf.stem
    work_dir, text_dir, cache_dir = doc_dir / "work", doc_dir / "text", cfg.out / ".cache"
    work_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)
    total_pages = page_count(pdf)
    pages = parse_pages(cfg.pages, total_pages)
    model_pages = (set() if getattr(cfg, "model_pages", None) == "none"
                   else set(parse_pages(cfg.model_pages, total_pages)) if getattr(cfg, "model_pages", None)
                   else None)
    print(f"\n▶ {pdf}: {len(pages)} trang")

    tick = time.perf_counter()
    layer = read_text_layer(pdf, pages[0], pages[-1], cfg.min_chars)
    times["textLayer"] = seconds(tick)
    records: dict[int, dict[str, Any]] = {}
    ocr_pages = []
    for page in pages:
        tl = layer[page]
        if tl["usable"]:
            records[page] = {"page": page, "route": "text_layer", "status": "OK", "flags": [],
                             "text": tl["text"], "textLayer": {"chars": tl["chars"], "badRatio": tl["badRatio"]}}
        else:
            ocr_pages.append(page)
    print(f"  lớp text: {len(pages) - len(ocr_pages)} trang dùng được, {len(ocr_pages)} trang cần OCR ({times['textLayer']}s)")

    if ocr_pages:
        env = tess_env(cfg.tessdata)

    tick = time.perf_counter()
    def do_ocr(page: int) -> dict[str, Any]:
        image, rotation = upright_page(pdf, page, work_dir, cfg.long_side, env)
        cache_path = cache_dir / "tess" / f"{hash_file(image)[:32]}.json"
        hit = load_json(cache_path)
        # Older cache entries have only the word count, not TSV word geometry.
        if hit is not None and not isinstance(hit.get("wordItems"), list):
            hit = None
        tess = hit if hit is not None else tesseract(image, env)
        if hit is None:
            save_json(cache_path, tess)
        elapsed = "(cache)" if hit else f"{tess['seconds']}s"
        print(f"  [tess] trang {page}: conf={tess['meanConf']} low={tess['lowConfRatio']} rot={rotation} {elapsed}")
        return {"page": page, "image": image, "rotation": rotation, "tess": tess, "cached": hit is not None}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, cfg.tess_workers)) as executor:
        ocr = list(executor.map(do_ocr, ocr_pages))
    times["renderAndTesseract"] = seconds(tick)

    critical: dict[int, bool] = {}
    reasons: dict[int, str] = {}
    jobs = []
    for item in ocr:
        tess = item["tess"]
        crit = is_critical(tess["text"])
        critical[item["page"]] = crit
        reason = None
        if provider == "local" or (model_pages is not None and item["page"] not in model_pages):
            reason = None
        elif cfg.gemini == "always":
            reason = "always"
        elif cfg.gemini == "auto" and tess["chars"] >= 20:
            if crit:
                reason = "critical_page"
            elif tess["meanConf"] < cfg.min_conf:
                reason = f"mean_conf_{tess['meanConf']}"
            elif tess["lowConfRatio"] > 0.1:
                reason = f"low_conf_words_{tess['lowConfRatio']}"
        if reason:
            reasons[item["page"]] = reason
            jobs.append({"page": item["page"], "image": item["image"]})

    tick = time.perf_counter()
    gem = (gemini_transcribe(jobs, model=cfg.model, batch_size=cfg.batch,
                            concurrency=cfg.gemini_concurrency, timeout_sec=cfg.gemini_timeout,
                            cache_dir=cache_dir, stats=gemini_api)
           if jobs and provider in ("auto", "gemini") and os.environ.get("GEMINI_API_KEY") else {})
    fallback_jobs = [job for job in jobs if not gem.get(job["page"], {}).get("page")]
    if fallback_jobs and provider in ("auto", "openrouter") and os.environ.get("OPENROUTER_API_KEY"):
        if provider == "openrouter":
            print(f"  Gửi {len(fallback_jobs)} trang sang OpenRouter")
        else:
            print(f"  Gemini chưa xử lý được {len(fallback_jobs)} trang; chuyển sang OpenRouter")
        gem.update(openrouter_transcribe(
            fallback_jobs, model=openrouter_model, batch_size=cfg.batch,
            concurrency=cfg.gemini_concurrency, timeout_sec=cfg.gemini_timeout,
            cache_dir=cache_dir, stats=openrouter_api,
            text_only=getattr(cfg, "ai_output", "structured") == "text"))
    fallback_jobs = [job for job in jobs if not gem.get(job["page"], {}).get("page")]
    if fallback_jobs and provider == "codecraft" and os.environ.get("CODECRAFT_API_KEY"):
        print(f"  Gửi {len(fallback_jobs)} trang sang CodeCraft")
        gem.update(openrouter_transcribe(
            fallback_jobs, model=codecraft_model, batch_size=cfg.batch,
            concurrency=cfg.gemini_concurrency, timeout_sec=cfg.gemini_timeout,
            cache_dir=cache_dir, stats=codecraft_api,
            text_only=getattr(cfg, "ai_output", "structured") == "text",
            provider="codecraft", base_url=codecraft_url, api_key_env="CODECRAFT_API_KEY"))
    fallback_jobs = [job for job in jobs if not gem.get(job["page"], {}).get("page")]
    if fallback_jobs and provider == "omniroute" and os.environ.get("OMNIROUTE_API_KEY"):
        print(f"  Gửi {len(fallback_jobs)} trang sang OmniRoute combo {omniroute_model}")
        gem.update(openrouter_transcribe(
            fallback_jobs, model=omniroute_model, batch_size=cfg.batch,
            concurrency=cfg.gemini_concurrency, timeout_sec=cfg.gemini_timeout,
            cache_dir=cache_dir, stats=omniroute_api,
            text_only=getattr(cfg, "ai_output", "structured") == "text",
            provider="omniroute", base_url=omniroute_url, api_key_env="OMNIROUTE_API_KEY"))
    fallback_jobs = [job for job in jobs if not gem.get(job["page"], {}).get("page")]
    if fallback_jobs and provider in ("auto", "ollama"):
        print(f"  Gửi {len(fallback_jobs)} trang sang Ollama")
        gem.update(ollama_transcribe(
            fallback_jobs, model=cfg.ollama_model, base_url=cfg.ollama_url,
            timeout_sec=cfg.gemini_timeout, cache_dir=cache_dir, stats=ollama_api))
    times["gemini"] = seconds(tick)
    tess_by_page = {item["page"]: item for item in ocr}

    def finalize(page: int, outcome: dict[str, Any] | None) -> dict[str, Any]:
        item = tess_by_page[page]
        tess = item["tess"]
        tl = layer[page]
        flags: list[str] = []
        if tl["chars"] >= cfg.min_chars:
            flags.append("TEXT_LAYER_BROKEN")
        if tess["chars"] < 20:
            flags.append("NEAR_EMPTY")
        rec: dict[str, Any] = {"page": page, "route": "tesseract", "status": "OK", "flags": flags,
                               "text": tess["text"], "textLayer": {"chars": tl["chars"], "badRatio": tl["badRatio"]},
                               "rotation": item["rotation"],
                               "tesseract": {**{k: v for k, v in tess.items() if k != "text"}, "cached": item["cached"]}}
        reason = reasons.get(page)
        if not reason:
            if tess["meanConf"] < cfg.min_conf and tess["chars"] >= 20:
                flags.append("LOW_CONF")
        elif not outcome or not outcome.get("page"):
            flags.append("GEMINI_FAILED")
            rec["gemini"] = {"provider": outcome.get("provider", "gemini") if outcome else "gemini",
                             "model": outcome.get("model", cfg.model) if outcome else cfg.model,
                             "cached": False, "reason": reason,
                             **({"error": outcome["error"]} if outcome and outcome.get("error") else {})}
        else:
            gemini_page = outcome["page"]
            provider = outcome.get("provider", "gemini")
            comparison = cross_check(gemini_page["text"], tess["text"])
            rec.update(route=f"tesseract+{provider}", text=gemini_page["text"], crossCheck=comparison,
                       aiBlocks=gemini_page.get("blocks"),
                       gemini={"provider": provider, "model": outcome["model"],
                               "cached": outcome["cached"], "reason": reason,
                               "page_type": gemini_page["page_type"], "unreadable": gemini_page["unreadable"]})
            if critical[page] and comparison["numberAgreement"] < 0.95:
                flags.append("NUMBERS_UNVERIFIED")
            tess_numbers = set(number_keys(tess["text"]))
            model_numbers = set(number_keys(gemini_page["text"]))
            if critical[page] and tess_numbers and len(tess_numbers - model_numbers) / len(tess_numbers) > 0.1:
                if "NUMBERS_UNVERIFIED" not in flags:
                    flags.append("NUMBERS_UNVERIFIED")
            if re.search(r"[\u4e00-\u9fff]", gemini_page["text"]):
                flags.append("FOREIGN_SCRIPT")
            if comparison["similarity"] < 0.6:
                flags.append("ENGINES_DISAGREE")
            if gemini_page["unreadable"]:
                flags.append("GEMINI_UNREADABLE")
        rec["status"] = "REVIEW" if any(flag not in INFO_FLAGS for flag in flags) else "OK"
        return rec

    for item in ocr:
        records[item["page"]] = finalize(item["page"], gem.get(item["page"]))

    if cfg.escalate_model and provider in ("auto", "gemini") and os.environ.get("GEMINI_API_KEY"):
        retry = [record for record in records.values() if record["route"] == "tesseract+gemini"
                 and critical.get(record["page"])
                 and record.get("crossCheck", {}).get("numberAgreement", 1) < 0.9]
        if retry:
            tick = time.perf_counter()
            again = gemini_transcribe([{"page": rec["page"], "image": tess_by_page[rec["page"]]["image"]} for rec in retry],
                                     model=cfg.escalate_model, batch_size=1,
                                     concurrency=cfg.gemini_concurrency, timeout_sec=cfg.gemini_timeout,
                                     cache_dir=cache_dir, stats=gemini_api)
            for record in retry:
                alternative = finalize(record["page"], again.get(record["page"]))
                if alternative.get("crossCheck", {}).get("numberAgreement", 0) > record.get("crossCheck", {}).get("numberAgreement", 0):
                    alternative["flags"].append("ESCALATED")
                    records[record["page"]] = alternative
            times["escalate"] = seconds(tick)

    ordered = [records[page] for page in pages]
    (doc_dir / "pages.jsonl").write_text("".join(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n" for rec in ordered), encoding="utf-8")
    for rec in ordered:
        name = page_name(rec["page"])
        (text_dir / f"{name}.txt").write_text(rec["text"], encoding="utf-8")
        if rec["route"] in ("tesseract+gemini", "tesseract+openrouter", "tesseract+codecraft", "tesseract+omniroute", "tesseract+ollama"):
            (text_dir / f"{name}.tess.txt").write_text(tess_by_page[rec["page"]]["tess"]["text"], encoding="utf-8")
    times["total"] = seconds(start)
    summary_config = {"out": str(cfg.out)}
    if cfg.pages is not None:
        summary_config["pages"] = cfg.pages
    summary_config.update({"mode": cfg.gemini, "provider": provider, "model": cfg.model,
                           "aiOutput": getattr(cfg, "ai_output", "structured")})
    if os.environ.get("OPENROUTER_API_KEY"):
        summary_config["openrouterModel"] = openrouter_model
    if provider == "codecraft":
        summary_config["codecraftModel"] = codecraft_model
    if provider == "omniroute":
        summary_config["omnirouteModel"] = omniroute_model
    if provider in ("auto", "ollama"):
        summary_config["ollamaModel"] = getattr(cfg, "ollama_model", None)
    if cfg.escalate_model is not None:
        summary_config["escalateModel"] = cfg.escalate_model
    summary_config.update({"batch": cfg.batch, "geminiConcurrency": cfg.gemini_concurrency,
                           "geminiTimeout": cfg.gemini_timeout, "tessWorkers": cfg.tess_workers,
                           "minChars": cfg.min_chars, "minConf": cfg.min_conf, "longSide": cfg.long_side})
    summary = {"pdf": str(pdf), "pages": len(pages), "routes": count([rec["route"] for rec in ordered]),
               "status": count([rec["status"] for rec in ordered]),
               "flags": count([flag for rec in ordered for flag in rec["flags"]]),
               "reviewPages": [rec["page"] for rec in ordered if rec["status"] == "REVIEW"],
               "seconds": times, "geminiApi": gemini_api, "openrouterApi": openrouter_api,
               "codecraftApi": codecraft_api,
               "omnirouteApi": omniroute_api,
               "ollamaApi": ollama_api,
               "cache": {"tesseractHits": sum(item["cached"] for item in ocr),
                         "geminiHits": sum(outcome["cached"] for outcome in gem.values()
                                           if outcome.get("provider", "gemini") == "gemini"),
                         "openrouterHits": sum(outcome["cached"] for outcome in gem.values()
                                               if outcome.get("provider") == "openrouter"),
                         "codecraftHits": sum(outcome["cached"] for outcome in gem.values()
                                              if outcome.get("provider") == "codecraft"),
                         "omnirouteHits": sum(outcome["cached"] for outcome in gem.values()
                                              if outcome.get("provider") == "omniroute")},
               "config": summary_config}
    save_json(doc_dir / "summary.json", summary)
    print(f"  tuyến: {summary['routes']}  trạng thái: {summary['status']}")
    if summary["flags"]:
        print(f"  cờ: {summary['flags']}")
    print(f"  thời gian (s): {times}")
    if gemini_api["calls"]:
        print(f"  Gemini API: {gemini_api['calls']} lần gọi ({gemini_api['failedCalls']} lỗi), token vào {gemini_api['input_tokens']}, ra {gemini_api['output_tokens']}")
    if openrouter_api["calls"]:
        print(f"  OpenRouter: {openrouter_api['calls']} lần gọi ({openrouter_api['failedCalls']} lỗi), token vào {openrouter_api['input_tokens']}, ra {openrouter_api['output_tokens']}")
    if codecraft_api["calls"]:
        print(f"  CodeCraft: {codecraft_api['calls']} lần gọi ({codecraft_api['failedCalls']} lỗi), token vào {codecraft_api['input_tokens']}, ra {codecraft_api['output_tokens']}")
    if omniroute_api["calls"]:
        print(f"  OmniRoute: {omniroute_api['calls']} lần gọi ({omniroute_api['failedCalls']} lỗi), token vào {omniroute_api['input_tokens']}, ra {omniroute_api['output_tokens']}")
    if ollama_api["calls"]:
        print(f"  Ollama: {ollama_api['calls']} lần gọi ({ollama_api['failedCalls']} lỗi), token vào {ollama_api['input_tokens']}, ra {ollama_api['output_tokens']}")
    print(f"  → {doc_dir}")


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdfs", nargs="+", type=Path, help="Một hoặc nhiều file PDF")
    parser.add_argument("--out", type=Path, default=Path("ocr_router_out"))
    parser.add_argument("--pages", help="Ví dụ: 1-5,8")
    parser.add_argument("--model-pages", help="Chỉ gửi các trang này sang model (hoặc none); vẫn xuất đủ các trang PDF")
    parser.add_argument("--gemini", choices=("auto", "always", "never"), default="auto")
    parser.add_argument("--provider", choices=("auto", "gemini", "openrouter", "codecraft", "omniroute", "ollama", "local"), default="auto",
                        help="AI OCR provider; local chỉ dùng lớp text và Tesseract")
    parser.add_argument("--ai-output", choices=("structured", "text"), default="structured",
                        help="OpenRouter output: chỉ chữ và số hoặc đầy đủ khối")
    parser.add_argument("--model", default="gemini-3.8-flash")
    parser.add_argument("--openrouter-model", default=os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
                        help="Model dự phòng có hỗ trợ ảnh trên OpenRouter")
    parser.add_argument("--codecraft-model", default=os.environ.get("CODECRAFT_MODEL", "qwen3.8-27b"),
                        help="Model vision trên CodeCraft API")
    parser.add_argument("--omniroute-model", default=os.environ.get("OMNIROUTE_MODEL", "gemini"),
                        help="Tên combo OmniRoute (khớp chính xác tên combo trong dashboard)")
    parser.add_argument("--ollama-model", default=os.environ.get("OLLAMA_VISION_MODEL", "qwen3-vl:4b-instruct"),
                        help="Model thị giác cục bộ qua Ollama")
    parser.add_argument("--ollama-url", default=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
                        help="Ollama API URL")
    parser.add_argument("--escalate-model")
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--gemini-concurrency", "--agy-concurrency", dest="gemini_concurrency", type=int, default=2)
    parser.add_argument("--gemini-timeout", "--agy-timeout", dest="gemini_timeout", type=int, default=300)
    parser.add_argument("--tess-workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    parser.add_argument("--min-chars", type=int, default=150)
    parser.add_argument("--min-conf", type=int, default=90)
    parser.add_argument("--long-side", type=int, default=3508)
    parser.add_argument("--tessdata")
    parser.add_argument("--build-document-ir", action="store_true",
                         help="Sau OCR, tạo IR cho các nội dung chính của báo cáo thường niên")
    parser.add_argument("--template", type=Path,
                        help="Template luật BCTC khi dùng --build-document-ir")
    parser.add_argument("--overrides", type=Path,
                        help="File override thường niên cho đúng PDF; mặc định không dùng")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    cfg = parser.parse_args(argv)
    if cfg.template is not None and not cfg.build_document_ir:
        parser.error("--template chỉ dùng cùng --build-document-ir")
    if cfg.overrides is not None and not cfg.build_document_ir:
        parser.error("--overrides chỉ dùng cùng --build-document-ir")
    if cfg.overrides is not None and len(cfg.pdfs) != 1:
        parser.error("--overrides chỉ nhận đúng một PDF")
    if min(cfg.batch, cfg.gemini_concurrency, cfg.tess_workers, cfg.long_side) < 1:
        parser.error("batch, concurrency, workers và long-side phải lớn hơn 0")
    cfg.out = cfg.out.resolve()
    try:
        env = preflight(cfg)
        for pdf in cfg.pdfs:
            if not pdf.is_file():
                raise FileNotFoundError(pdf)
            process_pdf(pdf.resolve(), cfg, env)
        if cfg.build_document_ir:
            from buildDocumentIr import build_document_ir
            for pdf in cfg.pdfs:
                resolved = pdf.resolve()
                doc_dir = cfg.out / resolved.stem
                result = build_document_ir(resolved, doc_dir / "pages.jsonl", doc_dir / "annual_ir",
                                           cfg.template, cfg.overrides)
                print(f"▶ IR báo cáo thường niên: {result['pages']} trang, blocks {result['blockTypes']}")
                print(f"  → {doc_dir / 'annual_ir' / 'content'}")
                if "financialStatements" in result:
                    financial = result["financialStatements"]
                    print(f"  BCTC đã kiểm toán: {financial['pages']} trang; "
                          f"{financial['structuredTablePages']} trang có bảng cấu trúc; "
                          f"{financial['notesTextOnlyPages']} trang thuyết minh chỉ có text")
                    print(f"  → {doc_dir / 'annual_ir' / 'table'}")
    except (RuntimeError, ValueError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
        print(f"✖ {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
