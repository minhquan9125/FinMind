"""OCR every local Vietstock annual-report PDF into a consistent, resumable layout.

Run from the repository root:
    python ocr-router/run_all_reports.py --provider local
    python ocr-router/run_all_reports.py --provider openrouter --openrouter-model MODEL_ID
"""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


ROOT = Path(__file__).resolve().parents[1]
PDF_ROOT = ROOT / "data/references/vietstock/annual_reports/files_pdf"
DEFAULT_OUT = ROOT / "data/references/vietstock/annual_reports/ocr_standard"
ROUTER = Path(__file__).resolve().parent / "src/main.py"
IR_BUILDER = Path(__file__).resolve().parent / "src/buildDocumentIr.py"
sys.path.insert(0, str(ROOT / "data_pipeline" / "annual_reports"))
from drive_store import DriveStore


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def save_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_pages(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def write_pages(path: Path, pages: list[dict]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("".join(json.dumps(page, ensure_ascii=False, separators=(",", ":")) + "\n"
                                 for page in pages), encoding="utf-8")
    temporary.replace(path)


def restore_page_text(doc_dir: Path, pages: list[dict]) -> None:
    text_dir = doc_dir / "text"
    text_dir.mkdir(parents=True, exist_ok=True)
    for page in pages:
        (text_dir / f"p-{page['page']:03d}.txt").write_text(page["text"], encoding="utf-8")


def merge_pending_pages(doc_dir: Path, original: list[dict], pending: list[int]) -> None:
    """Keep successful old records after a model-only retry of pending pages."""
    retried = read_pages(doc_dir / "pages.jsonl")
    if [page["page"] for page in original] != [page["page"] for page in retried]:
        raise ValueError("Retry changed the page list")
    target = set(pending)
    merged = [new if old["page"] in target else old for old, new in zip(original, retried)]
    summary_path = doc_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["routes"] = dict(Counter(page["route"] for page in merged))
    summary["status"] = dict(Counter(page["status"] for page in merged))
    summary["flags"] = dict(Counter(flag for page in merged for flag in page["flags"]))
    summary["reviewPages"] = [page["page"] for page in merged if page["status"] == "REVIEW"]
    summary["config"]["retryPendingPages"] = pending
    write_pages(doc_dir / "pages.jsonl", merged)
    restore_page_text(doc_dir, merged)
    save_json(summary_path, summary)


def inspect_output(doc_dir: Path, source_sha256: str, provider: str,
                   model: str | None) -> dict | None:
    source_path = doc_dir / "source.json"
    summary_path = doc_dir / "summary.json"
    pages_path = doc_dir / "pages.jsonl"
    if not all(path.is_file() for path in (source_path, summary_path, pages_path)):
        return None
    try:
        source = json.loads(source_path.read_text(encoding="utf-8"))
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        pages = read_pages(pages_path)
    except (OSError, ValueError):
        return None
    if (source.get("sha256") != source_sha256 or source.get("provider") != provider
            or (model is not None and source.get("model") != model) or not pages
            or len(pages) != summary.get("pages")
            or [page.get("page") for page in pages] != list(range(1, len(pages) + 1))):
        return None
    failed = [page["page"] for page in pages if "GEMINI_FAILED" in page.get("flags", [])]
    review = [page["page"] for page in pages if page.get("status") == "REVIEW"]
    return {"status": "MODEL_PENDING" if failed else "COMPLETE",
            "pages": len(pages), "model_failed_pages": failed, "review_pages": review,
            "routes": summary.get("routes", {})}


def discover_pdfs(symbols: set[str] | None, years: set[str] | None) -> list[Path]:
    if not PDF_ROOT.is_dir():
        raise FileNotFoundError(PDF_ROOT)
    paths = []
    for pdf in PDF_ROOT.rglob("*.pdf"):
        relative = pdf.relative_to(PDF_ROOT)
        if len(relative.parts) < 3:
            continue
        symbol, year = relative.parts[:2]
        if len(year) != 4 or not year.isascii() or not year.isdigit():
            raise ValueError(
                f"Invalid annual-report path {relative.as_posix()}: "
                "expected SYMBOL/YYYY/.../file.pdf"
            )
        if symbols and symbol.upper() not in symbols:
            continue
        if years and year not in years:
            continue
        paths.append(pdf)
    return sorted(paths, key=lambda path: str(path.relative_to(PDF_ROOT)).casefold())


@contextmanager
def staged_drive_pdf_root(symbols: set[str] | None, years: set[str] | None) -> Iterator[Path]:
    """Build a temporary PDF tree from verified Drive entries for the batch router."""
    manifest_path = ROOT / "data/references/vietstock/annual_reports/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    selected = [row for row in manifest.get("documents", [])
                if row.get("status") == "DOWNLOADED"
                and (not symbols or str(row.get("symbol", "")).upper() in symbols)
                and (not years or str(row.get("year")) in years)]
    if not selected or not any(row.get("pdf_paths") for row in selected):
        raise FileNotFoundError("No Drive PDFs match the filters")
    store = DriveStore.from_oauth()
    with tempfile.TemporaryDirectory(prefix="finmind-ocr-drive-", dir=ROOT) as directory:
        staged = Path(directory).resolve()
        for row in selected:
            for relative in row.get("pdf_paths") or []:
                parts = Path(relative).parts
                if "files" not in parts:
                    raise ValueError(f"Invalid manifest PDF path: {relative}")
                tail = parts[parts.index("files") + 1:]
                if (len(tail) < 3 or tail[0].upper() != str(row["symbol"]).upper()
                        or tail[1] != str(row["year"])):
                    raise ValueError(f"Invalid manifest PDF path: {relative}")
                destination = staged.joinpath(*tail).resolve()
                if staged not in destination.parents or destination.suffix.casefold() != ".pdf":
                    raise ValueError(f"Unsafe manifest PDF path: {relative}")
                entry = (row.get("drive_files") or {}).get(relative)
                if not entry:
                    raise ValueError(f"Drive metadata missing for {relative}")
                destination.parent.mkdir(parents=True, exist_ok=True)
                with store.temporary_pdf(entry, destination.name, temp_root=staged) as downloaded:
                    shutil.copyfile(downloaded, destination)
        yield staged


def summarize_results(pdfs_discovered: int, documents: list[dict]) -> dict:
    pending = sum(len(item["model_failed_pages"]) for item in documents)
    review = sum(len(item["review_pages"]) for item in documents)
    review_only = sum(len(set(item["review_pages"]) - set(item["model_failed_pages"]))
                      for item in documents)
    complete = sum(item["status"] == "COMPLETE" for item in documents)
    return {"pdfs_discovered": pdfs_discovered, "pdfs_attempted": len(documents),
            "complete": complete, "pending_or_failed": len(documents) - complete,
            "pages": sum(item["pages"] for item in documents),
            "model_pending_pages": pending,
            "review_pages": review,
            "review_without_model_failure_pages": review_only}


def _main(argv: list[str] | None = None) -> int:
    if (sys.stdout.encoding or "").lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    from dotenv import dotenv_values
    configured = dotenv_values(ROUTER.parents[1] / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("local", "gemini", "openrouter", "codecraft", "omniroute", "ollama", "auto"), default="local")
    parser.add_argument("--model", default="gemini-3.8-flash", help="Gemini model")
    parser.add_argument("--openrouter-model", help="OpenRouter model ID; defaults to OPENROUTER_MODEL")
    parser.add_argument("--codecraft-model", help="CodeCraft model ID; defaults to CODECRAFT_MODEL")
    parser.add_argument("--omniroute-model", help="Exact OmniRoute combo name; defaults to OMNIROUTE_MODEL")
    parser.add_argument("--ollama-model", default="qwen3-vl:4b-instruct", help="Local vision model")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Local Ollama API")
    parser.add_argument("--symbols", help="Comma-separated ticker symbols")
    parser.add_argument("--years", help="Comma-separated report years")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--batch", type=int, default=1, help="Image pages per model request")
    parser.add_argument("--model-timeout", type=int, default=180, help="Seconds allowed per model request")
    parser.add_argument("--force", action="store_true", help="Rebuild completed PDF outputs")
    parser.add_argument("--pending-only", action="store_true",help="Retry only GEMINI_FAILED pages in existing Gemini outputs")
    parser.add_argument("--ir-only", action="store_true",
                        help="Build annual_ir from existing completed OCR without rerunning OCR")
    parser.add_argument("--with-ir", action="store_true",
                        help="Build annual_ir for completed PDFs after the OCR batch")
    parser.add_argument("--dry-run", action="store_true", help="List local PDFs without OCR")
    args = parser.parse_args(argv)
    args.openrouter_model = (args.openrouter_model or os.environ.get("OPENROUTER_MODEL")
                             or configured.get("OPENROUTER_MODEL"))
    if args.openrouter_model == "qwen3.8-27b":
        args.openrouter_model = "qwen/qwen3.8-27b"
    args.codecraft_model = (args.codecraft_model or os.environ.get("CODECRAFT_MODEL")
                            or configured.get("CODECRAFT_MODEL") or "qwen3.8-27b")
    args.omniroute_model = (args.omniroute_model or os.environ.get("OMNIROUTE_MODEL")
                            or configured.get("OMNIROUTE_MODEL") or "gemini")
    if args.batch < 1 or args.model_timeout < 1:
        parser.error("--batch and --model-timeout must be at least 1")
    if args.provider == "openrouter" and not args.openrouter_model:
        parser.error("--openrouter-model is required with --provider openrouter")
    if args.pending_only and args.provider not in ("gemini", "openrouter", "codecraft", "omniroute", "ollama"):
        parser.error("--pending-only requires --provider gemini, openrouter, codecraft, omniroute, or ollama")
    if args.pending_only and args.force:
        parser.error("--pending-only cannot be combined with --force")
    if args.ir_only and (args.pending_only or args.force):
        parser.error("--ir-only cannot be combined with --pending-only or --force")
    if args.ir_only and args.with_ir:
        parser.error("--ir-only cannot be combined with --with-ir")
    symbols = {item.strip().upper() for item in args.symbols.split(",")} if args.symbols else None
    years = {item.strip() for item in args.years.split(",")} if args.years else None
    try:
        pdfs = discover_pdfs(symbols, years)
    except ValueError as exc:
        parser.error(str(exc))
    if not pdfs:
        parser.error("No local PDFs match the filters")
    output_root = args.out.resolve()
    selected_model = (args.openrouter_model if args.provider == "openrouter"
                      else args.codecraft_model if args.provider == "codecraft"
                      else args.omniroute_model if args.provider == "omniroute"
                      else args.ollama_model if args.provider == "ollama"
                      else args.model if args.provider in ("gemini", "auto") else "")
    if args.ir_only:
        eligible = 0
        missing = 0
        failed = 0
        for index, pdf in enumerate(pdfs, start=1):
            relative = pdf.relative_to(PDF_ROOT)
            doc_dir = output_root / relative.parts[0] / relative.parts[1] / pdf.stem
            try:
                source = json.loads((doc_dir / "source.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                source = {}
            prior = (inspect_output(doc_dir, sha256_file(pdf), source.get("provider"), None)
                     if source.get("provider") else None)
            if not prior:
                missing += 1
                print(f"[{index}/{len(pdfs)}] SKIP {relative.as_posix()}: valid OCR output missing", flush=True)
                continue
            if prior["status"] != "COMPLETE":
                missing += 1
                pages = read_pages(doc_dir / "pages.jsonl")
                errors = [f"p-{page['page']:03d}: {page.get('gemini', {}).get('error', 'model failed')}"
                          for page in pages if page["page"] in prior["model_failed_pages"]]
                print(f"[{index}/{len(pdfs)}] SKIP {relative.as_posix()}: MODEL_PENDING; "
                      + "; ".join(errors), flush=True)
                continue
            eligible += 1
            print(f"[{index}/{len(pdfs)}] IR {relative.as_posix()} ({prior['pages']} pages)", flush=True)
            if args.dry_run:
                continue
            command = [sys.executable, str(IR_BUILDER), str(pdf),
                       "--pages-jsonl", str(doc_dir / "pages.jsonl"),
                       "--out", str(doc_dir / "annual_ir")]
            completed = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                       errors="replace", check=False)
            (doc_dir / "ir.log").write_text(completed.stdout, encoding="utf-8")
            if completed.returncode:
                failed += 1
                print(f"  FAILED: see {doc_dir / 'ir.log'}", flush=True)
            else:
                print(f"  OK: {doc_dir / 'annual_ir'}", flush=True)
        print(f"IR eligible: {eligible}; OCR missing/pending: {missing}; IR failed: {failed}", flush=True)
        return 1 if failed else 0
    if args.dry_run and not args.pending_only:
        for pdf in pdfs:
            print(pdf.relative_to(PDF_ROOT).as_posix())
        print(f"PDFs: {len(pdfs)}")
        return 0

    if args.dry_run and args.pending_only:
        count = 0
        for pdf in pdfs:
            relative = pdf.relative_to(PDF_ROOT)
            doc_dir = output_root / relative.parts[0] / relative.parts[1] / pdf.stem
            try:
                prior_source = json.loads((doc_dir / "source.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                prior_source = {}
            prior = inspect_output(doc_dir, sha256_file(pdf), prior_source.get("provider"), None)
            if prior and prior["model_failed_pages"]:
                print(f"{relative.as_posix()}: pending pages {','.join(map(str, prior['model_failed_pages']))}")
                count += 1
        print(f"PDFs with pending model pages: {count}")
        return 0

    # The router reads its own .env. Check key names here without exposing values.
    if args.provider == "openrouter" and not (os.environ.get("OPENROUTER_API_KEY") or configured.get("OPENROUTER_API_KEY")):
        parser.error("OPENROUTER_API_KEY is missing; add it to ocr-router/.env")
    if args.provider == "gemini" and not (os.environ.get("GEMINI_API_KEY") or configured.get("GEMINI_API_KEY")):
        parser.error("GEMINI_API_KEY is missing; add it to ocr-router/.env")
    if args.provider == "codecraft" and not (os.environ.get("CODECRAFT_API_KEY") or configured.get("CODECRAFT_API_KEY")):
        parser.error("CODECRAFT_API_KEY is missing; add it to ocr-router/.env")
    if args.provider == "omniroute" and not (os.environ.get("OMNIROUTE_API_KEY") or configured.get("OMNIROUTE_API_KEY")):
        parser.error("OMNIROUTE_API_KEY is missing; add your OmniRoute API key to ocr-router/.env")

    scope = "_".join(part for part in ((args.symbols or "").replace(",", "-"),
                                       (args.years or "").replace(",", "-")) if part)
    report_path = output_root / f"batch_report_{args.provider}{'_' + scope if scope else ''}.json"
    report: dict = {"schema_name": "finmind.annual_ocr_batch", "schema_version": "1.0",
                    "updated_at": "", "provider": args.provider, "model": selected_model,
                    "pdf_root": (str(PDF_ROOT) if PDF_ROOT == ROOT / "data/references/vietstock/annual_reports/files_pdf"
                                 else "google_drive"), "documents": []}
    failures = 0
    for index, pdf in enumerate(pdfs, start=1):
        relative = pdf.relative_to(PDF_ROOT)
        symbol, year = relative.parts[:2]
        doc_dir = output_root / symbol / year / pdf.stem
        digest = sha256_file(pdf)
        if args.pending_only:
            try:
                prior_source = json.loads((doc_dir / "source.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                prior_source = {}
            prior_provider = prior_source.get("provider")
            prior = inspect_output(doc_dir, digest, prior_provider, None) if prior_provider else None
        else:
            prior = inspect_output(doc_dir, digest, args.provider, selected_model)
        if args.pending_only and (not prior or not prior["model_failed_pages"]):
            continue
        original_pages = read_pages(doc_dir / "pages.jsonl") if args.pending_only else None
        original_summary = (doc_dir / "summary.json").read_text(encoding="utf-8") if args.pending_only else None
        model_target_pages: list[int] | None = None
        if args.provider in ("openrouter", "codecraft", "omniroute", "ollama"):
            source_path = doc_dir / "source.json"
            try:
                existing_source = json.loads(source_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                existing_source = {}
            if (existing_source.get("sha256") == digest
                    and isinstance(existing_source.get("model_target_pages"), list)):
                model_target_pages = existing_source["model_target_pages"]
            else:
                baseline = inspect_output(doc_dir, digest, "local", "")
                if baseline:
                    model_target_pages = baseline["review_pages"]
        if prior and prior["status"] == "COMPLETE" and not args.force:
            result = {"symbol": symbol, "year": year, "pdf": relative.as_posix(),
                      "output": str(doc_dir), "sha256": digest, **prior, "skipped": True}
        else:
            command = [sys.executable, str(ROUTER), str(pdf), "--out", str(doc_dir.parent),
                       "--provider", args.provider, "--gemini", "always" if args.pending_only else "auto", "--model", args.model,
                       "--batch", str(args.batch),
                       "--gemini-concurrency", "1", "--gemini-timeout", str(args.model_timeout),
                       "--tess-workers", "2"]
            if args.openrouter_model:
                command.extend(("--openrouter-model", args.openrouter_model))
            if args.provider == "codecraft":
                command.extend(("--codecraft-model", args.codecraft_model))
            if args.provider == "omniroute":
                command.extend(("--omniroute-model", args.omniroute_model))
            if args.provider in ("ollama", "auto"):
                command.extend(("--ollama-model", args.ollama_model,
                                "--ollama-url", args.ollama_url))
            if args.provider in ("openrouter", "codecraft", "omniroute", "ollama"):
                command.extend(("--ai-output", "text"))
                if model_target_pages is not None:
                    command.extend(("--model-pages", ",".join(map(str, model_target_pages)) or "none"))
            if args.pending_only:
                command.extend(("--model-pages", ",".join(map(str, prior["model_failed_pages"]))))
            print(f"[{index}/{len(pdfs)}] {relative.as_posix()}", flush=True)
            completed = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                       errors="replace", check=False)
            doc_dir.mkdir(parents=True, exist_ok=True)
            (doc_dir / "run.log").write_text(completed.stdout, encoding="utf-8")
            if args.pending_only:
                if completed.returncode == 0:
                    try:
                        merge_pending_pages(doc_dir, original_pages, prior["model_failed_pages"])
                    except (OSError, ValueError, KeyError, TypeError) as exc:
                        completed = subprocess.CompletedProcess(command, 1, completed.stdout + f"\nMerge failed: {exc}\n")
                if completed.returncode != 0:
                    write_pages(doc_dir / "pages.jsonl", original_pages)
                    (doc_dir / "summary.json").write_text(original_summary, encoding="utf-8")
                    restore_page_text(doc_dir, original_pages)
                    (doc_dir / "run.log").write_text(completed.stdout, encoding="utf-8")
            if completed.returncode == 0:
                save_json(doc_dir / "source.json", {"symbol": symbol, "year": int(year),
                          "pdf": relative.as_posix(), "sha256": digest,
                          "provider": args.provider, "model": selected_model,
                          "model_target_pages": prior["model_failed_pages"] if args.pending_only else model_target_pages,
                          "previous_model": (json.loads((doc_dir / "source.json").read_text(encoding="utf-8")).get("model")
                                             if args.pending_only else None)})
            inspected = inspect_output(doc_dir, digest, args.provider, selected_model)
            result = {"symbol": symbol, "year": year, "pdf": relative.as_posix(),
                      "output": str(doc_dir), "sha256": digest,
                      **(inspected or {"status": "FAILED", "pages": 0,
                                        "model_failed_pages": [], "review_pages": []}),
                      "exit_code": completed.returncode, "skipped": False}
            if completed.returncode != 0:
                result["status"] = "FAILED"
            print(f"  {result['status']}: {result['pages']} pages; "
                  f"model pending {len(result['model_failed_pages'])}; "
                  f"review {len(result['review_pages'])}", flush=True)
        failures += result["status"] != "COMPLETE"
        report["documents"].append(result)
        report["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        save_json(report_path, report)
        if (not args.pending_only and args.provider in ("openrouter", "codecraft", "omniroute", "ollama")
                and result["status"] == "MODEL_PENDING"):
            report["stopped_reason"] = "Model failed on a page; review run.log before retrying."
            break
    report["summary"] = summarize_results(len(pdfs), report["documents"])
    save_json(report_path, report)
    print(json.dumps(report["summary"], ensure_ascii=False), flush=True)
    print(f"Report: {report_path}", flush=True)
    ir_result = 0
    if args.with_ir:
        ir_args = ["--ir-only", "--out", str(output_root)]
        if args.symbols:
            ir_args.extend(("--symbols", args.symbols))
        if args.years:
            ir_args.extend(("--years", args.years))
        ir_result = main(ir_args)
    return 1 if failures or ir_result else 0


def main(argv: list[str] | None = None) -> int:
    """Use local PDFs when available, or stage Drive PDFs for this invocation."""
    global PDF_ROOT
    arguments = list(sys.argv[1:] if argv is None else argv)
    if "-h" in arguments or "--help" in arguments:
        return _main(argv)
    filters = argparse.ArgumentParser(add_help=False)
    filters.add_argument("--symbols")
    filters.add_argument("--years")
    selected, _ = filters.parse_known_args(arguments)
    symbols = {part.strip().upper() for part in selected.symbols.split(",")} if selected.symbols else None
    years = {part.strip() for part in selected.years.split(",")} if selected.years else None
    try:
        local = discover_pdfs(symbols, years)
    except FileNotFoundError:
        local = []
    except ValueError:
        return _main(argv)
    if local:
        return _main(argv)
    original_root = PDF_ROOT
    with staged_drive_pdf_root(symbols, years) as staged:
        PDF_ROOT = staged
        try:
            return _main(argv)
        finally:
            PDF_ROOT = original_root


if __name__ == "__main__":
    raise SystemExit(main())
