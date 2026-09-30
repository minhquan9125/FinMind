"""Extract selectable text from Vietstock annual-report PDFs; OCR is opt-in.

Text extraction runs first. With --ocr, OCRmyPDF processes only pages without
an existing text layer and writes a separate searchable PDF, preserving the
original downloaded source. OCR output is evidence for review, never canonical
financial data.

Run from the repository root:
    python backend/scripts/extract_vietstock_annuals.py --symbols BID,VCB
    python backend/scripts/extract_vietstock_annuals.py --symbols BID,VCB --ocr
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / "data" / "references" / "vietstock" / "annual_reports"
MANIFEST_PATH = SOURCE_ROOT / "manifest.json"
OUTPUT_ROOT = SOURCE_ROOT / "extracted"
SEARCHABLE_ROOT = SOURCE_ROOT / "searchable"
MIN_TEXT_CHARS = 40


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def repo_path(relative: str) -> Path:
    candidate = (ROOT / relative).resolve()
    if candidate != ROOT and ROOT not in candidate.parents:
        raise ValueError(f"Manifest path escapes repository root: {relative!r}")
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def page_texts(path: Path) -> list[str]:
    with path.open("rb") as stream:
        reader = PdfReader(stream, strict=False)
        if reader.is_encrypted:
            raise ValueError("Encrypted PDF cannot be extracted without a password")
        return [" ".join((page.extract_text() or "").split()) for page in reader.pages]


def run_ocr(source: Path, searchable_pdf: Path, language: str, jobs: int) -> None:
    executable = shutil.which("ocrmypdf")
    if not executable:
        raise RuntimeError("--ocr needs OCRmyPDF on PATH; install OCRmyPDF and Tesseract with the vie language data")
    searchable_pdf.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{searchable_pdf.stem}.", suffix=".pdf", dir=searchable_pdf.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    temporary.unlink(missing_ok=True)  # OCRmyPDF requires a destination that does not exist.
    command = [
        executable, "--skip-text", "--rotate-pages", "--deskew",
        "--output-type", "pdf", "--jobs", str(max(1, jobs)),
        "--language", language, str(source), str(temporary),
    ]
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        if completed.returncode:
            detail = (completed.stderr or completed.stdout)[-3000:]
            raise RuntimeError(f"OCRmyPDF exited {completed.returncode}: {detail}")
        if not temporary.is_file() or temporary.stat().st_size == 0:
            raise RuntimeError("OCRmyPDF reported success but produced no PDF")
        temporary.replace(searchable_pdf)
    finally:
        temporary.unlink(missing_ok=True)


def validate_ocr_runtime(language: str) -> None:
    if not shutil.which("ocrmypdf"):
        raise RuntimeError("OCRmyPDF is not installed or not on PATH")
    tesseract = shutil.which("tesseract")
    if not tesseract:
        raise RuntimeError("Tesseract is not installed or not on PATH")
    result = subprocess.run([tesseract, "--list-langs"], check=False, capture_output=True, text=True)
    installed = set(result.stdout.splitlines()[1:])
    requested = {item.strip() for item in language.split("+") if item.strip()}
    missing = sorted(requested - installed)
    if result.returncode or missing:
        raise RuntimeError(f"Tesseract language data missing: {', '.join(missing) or language}")


def process_document(record: dict, *, use_ocr: bool, force: bool, language: str, jobs: int) -> dict:
    symbol = str(record.get("symbol", "")).upper()
    year = int(record.get("year", 0))
    pdf_rel = record.get("pdf_paths") or []
    if not pdf_rel:
        return {"symbol": symbol, "year": year, "status": "NO_PDF", "pages": 0, "ocr_pages": 0}

    results = []
    for relative in pdf_rel:
        source = repo_path(relative)
        digest = sha256_file(source)
        stem = source.stem
        target_json = OUTPUT_ROOT / symbol / str(year) / f"{stem}.json"
        searchable_pdf = SEARCHABLE_ROOT / symbol / str(year) / f"{stem}.searchable.pdf"
        if target_json.exists() and not force:
            try:
                previous = json.loads(target_json.read_text(encoding="utf-8"))
                if previous.get("source_pdf", {}).get("sha256") == digest and (
                    not use_ocr or previous.get("ocr", {}).get("status") in ("COMPLETED", "NOT_NEEDED")
                ):
                    results.append(previous["summary"] | {"status": "SKIPPED_EXISTING", "output": target_json.relative_to(ROOT).as_posix()})
                    continue
            except (OSError, json.JSONDecodeError, KeyError):
                pass

        original_texts = page_texts(source)
        needs_ocr = [index for index, text in enumerate(original_texts) if len(text) < MIN_TEXT_CHARS]
        extracted_pdf = source
        ocr_status = "NOT_REQUESTED"
        ocr_error = None
        if use_ocr and needs_ocr:
            try:
                run_ocr(source, searchable_pdf, language, jobs)
                extracted_pdf = searchable_pdf
                ocr_status = "COMPLETED"
            except Exception as exc:
                ocr_status = "FAILED"
                ocr_error = f"{type(exc).__name__}: {exc}"
        elif use_ocr:
            ocr_status = "NOT_NEEDED"

        final_texts = page_texts(extracted_pdf)
        pages = []
        for page_number, text in enumerate(final_texts, start=1):
            original_has_text = page_number <= len(original_texts) and len(original_texts[page_number - 1]) >= MIN_TEXT_CHARS
            has_text = len(text) >= MIN_TEXT_CHARS
            pages.append({
                "page": page_number,
                "text": text,
                "char_count": len(text),
                "has_text": has_text,
                "extraction_method": "pypdf_text_layer" if original_has_text else ("ocrmypdf_text_layer" if has_text and ocr_status == "COMPLETED" else "no_usable_text"),
            })
        still_missing = [page["page"] for page in pages if not page["has_text"]]
        summary = {
            "symbol": symbol,
            "year": year,
            "page_count": len(pages),
            "pages_with_text": len(pages) - len(still_missing),
            "pages_without_text": still_missing,
            "ocr_pages_requested": len(needs_ocr),
            "ocr_status": ocr_status,
        }
        payload = {
            "schema_version": "1.0",
            "source": "VIETSTOCK_FINANCE",
            "document": {
                "symbol": symbol,
                "year": year,
                "document_type": "annual_report",
                "title": record.get("title"),
                "source_page_url": record.get("source_page_url"),
                "source_file_url": record.get("file_url"),
                "provider_file_id": record.get("provider_file_id"),
                "relative_path": source.relative_to(ROOT).as_posix(),
                "sha256": digest,
            },
            "extracted_at": utc_now(),
            "ocr": {
                "requested": use_ocr,
                "engine": "OCRmyPDF/Tesseract" if use_ocr else None,
                "language": language if use_ocr else None,
                "status": ocr_status,
                "searchable_pdf": searchable_pdf.relative_to(ROOT).as_posix() if ocr_status == "COMPLETED" else None,
                "error": locals().get("ocr_error"),
                "note": "OCR text is extracted for review; validate figures against the original PDF.",
            },
            "summary": summary,
            "pages": pages,
        }
        atomic_json(target_json, payload)
        results.append(summary | {"status": "EXTRACTED", "output": target_json.relative_to(ROOT).as_posix()})
    return {
        "symbol": symbol,
        "year": year,
        "status": "OCR_REQUIRED" if any(row.get("pages_without_text") for row in results) else "TEXT_READY",
        "pages": sum(row.get("page_count", 0) for row in results),
        "ocr_pages": sum(row.get("ocr_pages_requested", 0) for row in results),
        "files": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract and optionally OCR Vietstock annual reports.")
    parser.add_argument("--symbols", help="Comma-separated ticker filter; default processes all downloaded reports")
    parser.add_argument("--years", help="Comma-separated report-year filter")
    parser.add_argument("--ocr", action="store_true", help="OCR pages lacking a text layer using OCRmyPDF/Tesseract")
    parser.add_argument("--language", default="vie+eng", help="Tesseract language pack(s), e.g. vie+eng")
    parser.add_argument("--jobs", type=int, default=2, help="Maximum OCRmyPDF worker count")
    parser.add_argument("--force", action="store_true", help="Reprocess even if the PDF hash has not changed")
    args = parser.parse_args()
    if not MANIFEST_PATH.is_file():
        parser.error(f"Vietstock manifest not found: {MANIFEST_PATH}")
    if args.ocr:
        try:
            validate_ocr_runtime(args.language)
        except RuntimeError as exc:
            parser.error(str(exc))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    symbols = {value.strip().upper() for value in args.symbols.split(",")} if args.symbols else None
    years = {int(value.strip()) for value in args.years.split(",")} if args.years else None
    records = [item for item in manifest.get("documents", []) if item.get("status") == "DOWNLOADED"]
    if symbols:
        records = [item for item in records if str(item.get("symbol", "")).upper() in symbols]
    if years:
        records = [item for item in records if int(item.get("year", 0)) in years]
    report = {
        "schema_version": "1.0",
        "source": "VIETSTOCK_FINANCE",
        "started_at": utc_now(),
        "ocr_requested": args.ocr,
        "processed_documents": [],
        "failures": [],
    }
    for index, record in enumerate(records, start=1):
        label = f"{record.get('symbol')} {record.get('year')}"
        try:
            result = process_document(record, use_ocr=args.ocr, force=args.force, language=args.language, jobs=args.jobs)
            report["processed_documents"].append(result)
            print(f"[{index}/{len(records)}] {label}: {result['status']} pages={result['pages']} OCR-candidates={result['ocr_pages']}")
        except Exception as exc:
            report["failures"].append({"symbol": record.get("symbol"), "year": record.get("year"), "error": f"{type(exc).__name__}: {exc}"})
            print(f"[FAILED] {label}: {exc}", file=sys.stderr)
    report["completed_at"] = utc_now()
    report["summary"] = {
        "documents": len(report["processed_documents"]),
        "failures": len(report["failures"]),
        "pages": sum(row.get("pages", 0) for row in report["processed_documents"]),
        "ocr_candidate_pages": sum(row.get("ocr_pages", 0) for row in report["processed_documents"]),
    }
    atomic_json(OUTPUT_ROOT / "extraction_report.json", report)
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
