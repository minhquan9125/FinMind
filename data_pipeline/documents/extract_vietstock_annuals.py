"""Read Vietstock annual-report PDFs into one page-addressable JSON per PDF.

Pages with a usable native PDF text layer use that text. Image-only pages are
rendered and read with PaddleOCR (Vietnamese); both methods are stored in the
same JSON document. This script does not chunk text or create embeddings.

Run from the repository root:
    .\\.venv-paddleocr\\Scripts\\python.exe data_pipeline/documents/extract_vietstock_annuals.py
    .\\.venv-paddleocr\\Scripts\\python.exe data_pipeline/documents/extract_vietstock_annuals.py --symbols BID,VCB
    .\\.venv-paddleocr\\Scripts\\python.exe data_pipeline/documents/extract_vietstock_annuals.py --symbols FPT --ocr-all
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / "data" / "references" / "vietstock" / "annual_reports"
MANIFEST_PATH = SOURCE_ROOT / "manifest.json"
OUTPUT_ROOT = SOURCE_ROOT / "extracted"
MIN_NATIVE_TEXT_CHARS = 40
OCR_VERSION = "PP-OCRv5"
TEXT_DET_BOX_THRESH = 0.3
TEXT_DET_UNCLIP_RATIO = 1.8
OCR_REVIEW_PATTERNS = [
    (re.compile(r"\bĐNG\s+NI\s+BT\b", re.IGNORECASE), "UNRESOLVED_OCR_FRAGMENT"),
    (re.compile(r"\bHOAT\b", re.IGNORECASE), "POSSIBLE_MISSING_VIETNAMESE_DIACRITICS"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def clean_ocr_text(value: str) -> str:
    """Apply only safe Unicode and whitespace cleanup before Gemini processing."""
    text = unicodedata.normalize("NFC", value)
    text = text.replace("\u00a0", " ").replace("\u200b", "").replace("\ufeff", "")
    return re.sub(r"\s+", " ", text).strip()


def review_items(value: str) -> list[dict[str, str]]:
    items = []
    for pattern, reason in OCR_REVIEW_PATTERNS:
        for match in pattern.finditer(value):
            items.append({"text": match.group(0), "reason": reason})
    return items


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
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


def safe_repo_file(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if path != ROOT and ROOT not in path.parents:
        raise ValueError(f"Manifest PDF path escapes repository: {relative!r}")
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def extract_native_pages(pdf: Path) -> list[str]:
    with pdf.open("rb") as stream:
        reader = PdfReader(stream, strict=False)
        if reader.is_encrypted:
            raise ValueError("Encrypted PDF cannot be read without a password")
        texts = []
        for page_number, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception as exc:
                print(f"[WARN] Native text extraction failed on page {page_number}: {type(exc).__name__}: {exc}")
                text = ""
            texts.append("\n".join(text.splitlines()).strip())
        return texts


def count_pdf_pages(pdf: Path) -> int:
    with pdf.open("rb") as stream:
        reader = PdfReader(stream, strict=False)
        if reader.is_encrypted:
            raise ValueError("Encrypted PDF cannot be read without a password")
        return len(reader.pages)


def to_plain(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, (list, tuple)):
        return [to_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: to_plain(item) for key, item in value.items()}
    return value


def unpack_ocr(prediction: Any) -> dict[str, Any]:
    raw = getattr(prediction, "json", None)
    if callable(raw):
        raw = raw()
    if raw is None and isinstance(prediction, dict):
        raw = prediction
    raw = to_plain(raw)
    result = raw.get("res", raw) if isinstance(raw, dict) else None
    if not isinstance(result, dict):
        raise TypeError("Unexpected PaddleOCR result schema")
    texts = result.get("rec_texts") or []
    scores = result.get("rec_scores") or []
    boxes = result.get("rec_polys") or result.get("dt_polys") or []
    lines = []
    for index, text in enumerate(texts):
        if not isinstance(text, str) or not text.strip():
            continue
        score = scores[index] if index < len(scores) else None
        box = boxes[index] if index < len(boxes) else None
        lines.append({"text": text.strip(), "confidence": float(score) if score is not None else None, "bbox": box})

    def line_order(line: dict[str, Any]) -> tuple[float, float]:
        try:
            points = line["bbox"]
            return (sum(float(point[1]) for point in points) / len(points), sum(float(point[0]) for point in points) / len(points))
        except (TypeError, ValueError, KeyError, IndexError, ZeroDivisionError):
            return (float(len(lines)), 0.0)

    lines.sort(key=line_order)
    return {"text": "\n".join(line["text"] for line in lines)}


def render_page(pdf: Path, page_number: int, dpi: int, pdftoppm: str, directory: Path) -> Path:
    prefix = directory / f"page-{page_number:04d}"
    command = [pdftoppm, "-f", str(page_number), "-l", str(page_number), "-singlefile", "-r", str(dpi), "-png", str(pdf), str(prefix)]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    image = prefix.with_suffix(".png")
    if completed.returncode or not image.is_file() or image.stat().st_size == 0:
        raise RuntimeError(f"Cannot render PDF page {page_number}: {(completed.stderr or completed.stdout)[-1500:]}")
    return image


def make_document(record: dict[str, Any], pdf: Path, relative_pdf: str, digest: str, pages: list[dict[str, Any]], *, ocr_all: bool) -> dict[str, Any]:
    missing = [item["page_number"] for item in pages if not (item.get("text_clean") or item.get("text") or "").strip()]
    native_count = sum(item["extraction_method"] == "pdf_text_layer" for item in pages)
    ocr_count = sum(item["extraction_method"] == "paddleocr" for item in pages)
    return {
        "schema_name": "finmind.annual_report_extraction",
        "schema_version": "2.0",
        "source": "VIETSTOCK_FINANCE",
        "document": {
            "symbol": str(record.get("symbol", "")).upper(),
            "year": int(record.get("year", 0)),
            "document_type": record.get("document_type", "annual_report"),
            "title": record.get("title"),
            "source_page_url": record.get("source_page_url"),
            "source_file_url": record.get("file_url") or record.get("provider_file_url"),
            "provider_file_id": record.get("provider_file_id"),
            "downloaded_at": record.get("downloaded_at"),
            "filename": pdf.name,
            "relative_path": relative_pdf,
            "sha256": digest,
            "page_count": len(pages),
        },
        "extracted_at": utc_now(),
        "extraction": {
            "methods": (["PADDLEOCR"] if ocr_all else ["PDF_TEXT_LAYER"] + (["PADDLEOCR"] if ocr_count else [])),
            "ocr_scope": "ALL_PAGES" if ocr_all else "PAGES_WITHOUT_TEXT_LAYER",
            "ocr_engine": "PaddleOCR" if ocr_count else None,
            "ocr_model": OCR_VERSION if ocr_count else None,
            "ocr_language": "vi" if ocr_count else None,
            "text_cleaning": {
                "version": "safe-v2-basic",
                "steps": ["Unicode NFC", "hidden-character removal", "whitespace collapse"],
                "numeric_bearing_tokens_preserved": True,
                "decorative_symbols_removed": [],
            } if ocr_count else None,
            "text_detection": {
                "box_threshold": TEXT_DET_BOX_THRESH,
                "unclip_ratio": TEXT_DET_UNCLIP_RATIO,
            } if ocr_count else None,
            "pages_from_pdf_text_layer": native_count,
            "pages_from_ocr": ocr_count,
            "pages_without_text": missing,
            "status": "COMPLETE" if not missing and not any(item.get("status") == "OCR_FAILED" for item in pages) else "PARTIAL",
            "review_required": bool(ocr_count),
        },
        "pages": pages,
    }


def process_document(record: dict[str, Any], ocr: Any, *, dpi: int, pdftoppm: str, force: bool, ocr_all: bool) -> dict[str, Any]:
    symbol = str(record.get("symbol", "")).upper()
    year = int(record.get("year", 0))
    outputs = []
    for relative_pdf in record.get("pdf_paths") or []:
        pdf = safe_repo_file(relative_pdf)
        digest = sha256_file(pdf)
        target = OUTPUT_ROOT / symbol / str(year) / f"{pdf.stem}.json"
        previous: dict[str, Any] = {}
        if target.is_file() and not force:
            try:
                previous = json.loads(target.read_text(encoding="utf-8"))
                if previous.get("document", {}).get("sha256") != digest:
                    previous = {}
            except (OSError, json.JSONDecodeError):
                previous = {}

        native_texts = [""] * count_pdf_pages(pdf) if ocr_all else extract_native_pages(pdf)
        old_pages = previous.get("pages", [])
        pages: list[dict[str, Any]] = []
        missing_indices = []
        for index, native_text in enumerate(native_texts):
            page_number = index + 1
            native_has_text = len(native_text.strip()) >= MIN_NATIVE_TEXT_CHARS
            old_page = old_pages[index] if index < len(old_pages) else {}
            if not ocr_all and native_has_text:
                pages.append({
                    "page_number": page_number,
                    "text": native_text,
                    "status": "TEXT_EXTRACTED",
                    "extraction_method": "pdf_text_layer",
                })
            elif not force and old_page.get("extraction_method") == "paddleocr" and (old_page.get("text_raw") or old_page.get("text_clean") or old_page.get("text", "")).strip():
                raw_text = old_page.get("text_raw") or old_page.get("text_clean") or old_page.get("text", "")
                cleaned_text = clean_ocr_text(raw_text)
                reviews = review_items(raw_text)
                pages.append({
                    "page_number": page_number,
                    "text_raw": raw_text,
                    "text_clean": cleaned_text,
                    "needs_review": bool(reviews),
                    "review_items": reviews,
                    "status": old_page.get("status", "OCR_EXTRACTED"),
                    "extraction_method": "paddleocr",
                })
            else:
                pages.append({"page_number": page_number, "text_raw": "", "text_clean": "", "needs_review": False, "review_items": [], "status": "NO_TEXT_LAYER", "extraction_method": "pending"})
                missing_indices.append(index)

        with tempfile.TemporaryDirectory(prefix="finmind-paddleocr-") as temp:
            temp_dir = Path(temp)
            for index in missing_indices:
                page_number = index + 1
                try:
                    prediction = None
                    used_dpi = dpi
                    last_error = None
                    attempts = [dpi] + ([180] if dpi > 180 else [])
                    for attempt_dpi in attempts:
                        try:
                            image_path = render_page(pdf, page_number, attempt_dpi, pdftoppm, temp_dir)
                            predictions = ocr.predict(str(image_path))
                            if not predictions:
                                raise RuntimeError("PaddleOCR returned no result")
                            prediction = predictions[0]
                            used_dpi = attempt_dpi
                            break
                        except Exception as exc:
                            last_error = exc
                    if prediction is None:
                        raise RuntimeError(f"OCR failed at {attempts} DPI: {last_error}") from last_error
                    result = unpack_ocr(prediction)
                    recognized = result["text"].strip()
                    cleaned_text = clean_ocr_text(recognized)
                    reviews = review_items(recognized)
                    pages[index] = {
                        "page_number": page_number,
                        "text_raw": recognized,
                        "text_clean": cleaned_text,
                        "needs_review": bool(reviews),
                        "review_items": reviews,
                        "status": "OCR_EXTRACTED" if recognized else "OCR_NO_TEXT",
                        "extraction_method": "paddleocr",
                    }
                except Exception as exc:
                    pages[index] = {"page_number": page_number, "text_raw": "", "text_clean": "", "needs_review": True, "review_items": [{"reason": "OCR_FAILED"}], "status": "OCR_FAILED", "extraction_method": "paddleocr"}

                # Save after every page so an interrupted run can safely resume.
                payload = make_document(record, pdf, relative_pdf, digest, pages, ocr_all=ocr_all)
                atomic_json(target, payload)

        payload = make_document(record, pdf, relative_pdf, digest, pages, ocr_all=ocr_all)
        atomic_json(target, payload)
        outputs.append({
            "pdf": relative_pdf,
            "json": target.relative_to(ROOT).as_posix(),
            "pages": len(pages),
            "native_text_pages": payload["extraction"]["pages_from_pdf_text_layer"],
            "ocr_pages": payload["extraction"]["pages_from_ocr"],
            "missing_pages": len(payload["extraction"]["pages_without_text"]),
            "status": payload["extraction"]["status"],
        })
    return {"symbol": symbol, "year": year, "files": outputs}


def reclean_existing_json(records: list[dict[str, Any]]) -> tuple[int, int]:
    """Refresh text_clean from preserved OCR text without invoking PaddleOCR."""
    updated_pages = 0
    updated_files = 0
    for record in records:
        symbol = str(record.get("symbol", "")).upper()
        year = str(record.get("year", ""))
        for relative_pdf in record.get("pdf_paths") or []:
            pdf = safe_repo_file(relative_pdf)
            target = OUTPUT_ROOT / symbol / year / f"{pdf.stem}.json"
            if not target.is_file():
                continue
            try:
                payload = json.loads(target.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                print(f"[SKIP] {target.relative_to(ROOT)}: invalid JSON ({exc})")
                continue
            if payload.get("document", {}).get("sha256") != sha256_file(pdf):
                print(f"[SKIP] {target.relative_to(ROOT)}: PDF hash differs")
                continue

            changed = 0
            for page in payload.get("pages", []):
                if page.get("extraction_method") != "paddleocr":
                    continue
                raw_text = page.get("text_raw") or ""
                if not raw_text.strip():
                    continue
                page["text_clean"] = clean_ocr_text(raw_text)
                page.pop("correction_rules_applied", None)
                reviews = review_items(raw_text)
                page["needs_review"] = bool(reviews)
                page["review_items"] = reviews
                page.pop("corrections_applied", None)
                changed += 1

            if not changed:
                continue
            payload.setdefault("extraction", {})["text_cleaning"] = {
                "version": "safe-v2-basic",
                "steps": ["Unicode NFC", "hidden-character removal", "whitespace collapse"],
                "numeric_bearing_tokens_preserved": True,
                "decorative_symbols_removed": [],
            }
            atomic_json(target, payload)
            updated_pages += changed
            updated_files += 1
            print(f"[UPDATED] {target.relative_to(ROOT)}: cleaned {changed} OCR page(s)")
    return updated_files, updated_pages


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert annual-report PDFs into one JSON per PDF using native text and PaddleOCR.")
    parser.add_argument("--symbols", help="Comma-separated ticker filter")
    parser.add_argument("--years", help="Comma-separated year filter")
    parser.add_argument("--dpi", type=int, default=300, help="Render resolution for scanned pages (150-400); retries at 180 DPI if PaddleOCR fails")
    parser.add_argument("--pdftoppm", default=shutil.which("pdftoppm"), help="Path to Poppler pdftoppm")
    parser.add_argument("--force", action="store_true", help="Re-run OCR even if this PDF's JSON already exists")
    parser.add_argument("--ocr-all", action="store_true", help="Run PaddleOCR on every page, including pages with selectable PDF text")
    parser.add_argument("--reclean-existing-json", action="store_true", help="Rebuild text_clean from existing text_raw without running OCR")
    args = parser.parse_args()
    if not MANIFEST_PATH.is_file():
        parser.error(f"Manifest not found: {MANIFEST_PATH}")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    symbols = {item.strip().upper() for item in args.symbols.split(",") if item.strip()} if args.symbols else None
    years = {int(item.strip()) for item in args.years.split(",") if item.strip()} if args.years else None
    records = [item for item in manifest.get("documents", []) if item.get("status") == "DOWNLOADED"]
    if symbols:
        records = [item for item in records if str(item.get("symbol", "")).upper() in symbols]
    if years:
        records = [item for item in records if int(item.get("year", 0)) in years]
    if args.reclean_existing_json:
        files, pages = reclean_existing_json(records)
        print(json.dumps({"updated_files": files, "updated_ocr_pages": pages}, ensure_ascii=False))
        return 0

    if not 150 <= args.dpi <= 400:
        parser.error("--dpi must be between 150 and 400")
    if not args.pdftoppm:
        parser.error("pdftoppm is required to render scanned pages; install Poppler or pass --pdftoppm")
    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        parser.error(f"PaddleOCR is missing from this Python environment: {exc}")

    ocr = PaddleOCR(
        lang="vi",
        ocr_version=OCR_VERSION,
        device="cpu",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        text_det_box_thresh=TEXT_DET_BOX_THRESH,
        text_det_unclip_ratio=TEXT_DET_UNCLIP_RATIO,
    )
    failures = []
    for index, record in enumerate(records, start=1):
        label = f"{record.get('symbol')} {record.get('year')}"
        try:
            result = process_document(record, ocr, dpi=args.dpi, pdftoppm=args.pdftoppm, force=args.force, ocr_all=args.ocr_all)
            for file_result in result["files"]:
                print(f"[{index}/{len(records)}] {label}: {file_result['status']} native={file_result['native_text_pages']} OCR={file_result['ocr_pages']} missing={file_result['missing_pages']} -> {file_result['json']}")
        except Exception as exc:
            failures.append({"symbol": record.get("symbol"), "year": record.get("year"), "error": f"{type(exc).__name__}: {exc}"})
            print(f"[FAILED] {label}: {exc}")
    print(json.dumps({"records": len(records), "failures": failures, "json_files": sum(len(item.get('pdf_paths') or []) for item in records)}, ensure_ascii=False))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
