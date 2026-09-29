"""Extract selectable text from CafeF PDFs without image recognition.

This intentionally does not infer financial metrics from table coordinates.
It preserves page-level text and source provenance so the next mapping/QA
stage can review figures against the original PDF.

Run from the repository root:
    python backend/scripts/extract_cafef_pdfs.py
    python backend/scripts/extract_cafef_pdfs.py --symbols BID,CTG,TCB
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[2]
PDF_ROOT = ROOT / "data" / "pdfs" / "cafef"
OUTPUT_ROOT = ROOT / "data" / "extracted" / "cafef"
MIN_TEXT_CHARS = 40


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".extract.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        Path(temporary).replace(path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def output_path(pdf_path: Path) -> Path:
    return OUTPUT_ROOT / pdf_path.parent.name / f"{pdf_path.stem}.json"


def extract_one(
    pdf_path: Path,
    manifest_records: dict[str, dict],
    refresh: bool,
) -> dict:
    out_path = output_path(pdf_path)
    source_hash = sha256_file(pdf_path)
    if out_path.exists() and not refresh:
        try:
            old = json.loads(out_path.read_text(encoding="utf-8"))
            if old.get("source_pdf", {}).get("sha256") == source_hash:
                return {"status": "SKIPPED_EXISTING", **old.get("summary", {})}
        except (OSError, json.JSONDecodeError):
            pass

    metadata = manifest_records.get(f"{pdf_path.parent.name}/{pdf_path.name}", {})
    pages = []
    with pdf_path.open("rb") as stream:
        reader = PdfReader(stream, strict=False)
        if reader.is_encrypted:
            raise ValueError("PDF is encrypted and cannot be extracted without a password")
        for page_number, page in enumerate(reader.pages, start=1):
            text = " ".join((page.extract_text() or "").split())
            pages.append(
                {
                    "page": page_number,
                    "text": text,
                    "char_count": len(text),
                    "has_text_layer": len(text) >= MIN_TEXT_CHARS,
                    "extraction_method": "pypdf_text_layer" if len(text) >= MIN_TEXT_CHARS else "no_usable_text",
                }
            )

    pages_without_text = [page["page"] for page in pages if not page["has_text_layer"]]
    summary = {
        "symbol": pdf_path.parent.name,
        "filename": pdf_path.name,
        "page_count": len(pages),
        "pages_with_text": len(pages) - len(pages_without_text),
        "pages_without_text_layer": pages_without_text,
    }
    payload = {
        "schema_version": "1.0",
        "source": "CAFEF",
        "source_pdf": {
            "relative_path": str(pdf_path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": source_hash,
            "document_id": metadata.get("cafef_document_id"),
            "title": metadata.get("title", pdf_path.stem),
            "period_label": metadata.get("period_label"),
            "source_page_url": metadata.get("source_page_url"),
            "source_file_url": metadata.get("source_file_url"),
        },
        "extracted_at": utc_now(),
        "extraction": {
            "method": "pypdf text layer",
            "image_recognition": False,
            "note": "Pages without selectable text are listed for manual review.",
        },
        "summary": summary,
        "pages": pages,
    }
    write_json_atomic(out_path, payload)
    return {"status": "EXTRACTED", **summary, "output": str(out_path.relative_to(ROOT)).replace("\\", "/")}


def load_manifest() -> dict[str, dict]:
    manifest_path = PDF_ROOT / "manifest.json"
    if not manifest_path.exists():
        return {}
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        item.get("local_path", ""): item
        for item in raw.get("documents", [])
        if item.get("local_path")
    }


def is_target_report(pdf_path: Path, records: dict[str, dict]) -> bool:
    """Keep financial statements and annual reports; exclude by-laws and other notices."""
    relative = str(pdf_path.relative_to(PDF_ROOT)).replace("\\", "/")
    record = records.get(relative)
    if not record:
        return True
    title = str(record.get("title") or "").casefold()
    category = record.get("category")
    if category == "financial":
        return any(term in title for term in ("báo cáo tài chính", "bctc", "financial statement"))
    if category == "annual":
        return any(term in title for term in ("báo cáo thường niên", "bctn", "annual report"))
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract selectable text pages from CafeF PDFs.")
    parser.add_argument("--symbols", help="Comma-separated company symbols; default processes all downloaded PDFs")
    parser.add_argument("--refresh", action="store_true", help="Re-extract PDFs even when source hash is unchanged")
    args = parser.parse_args()

    selected = {item.strip().upper() for item in args.symbols.split(",") if item.strip()} if args.symbols else None
    manifest = load_manifest()
    pdf_files = sorted(PDF_ROOT.glob("*/*.pdf"))
    if selected is not None:
        pdf_files = [path for path in pdf_files if path.parent.name.upper() in selected]
    in_scope = [path for path in pdf_files if is_target_report(path, manifest)]
    out_of_scope_count = len(pdf_files) - len(in_scope)
    pdf_files = in_scope
    if not pdf_files:
        print(f"No PDFs found under {PDF_ROOT}")
        return 1

    counts = {"EXTRACTED": 0, "SKIPPED_EXISTING": 0, "FAILED": 0}
    failures = []
    pages_without_text = 0
    for index, pdf_path in enumerate(pdf_files, start=1):
        relative = str(pdf_path.relative_to(PDF_ROOT)).replace("\\", "/")
        try:
            result = extract_one(pdf_path, manifest, args.refresh)
            counts[result["status"]] += 1
            pages_without_text += len(result.get("pages_without_text_layer", []))
            print(
                f"[{result['status']}] {index}/{len(pdf_files)} {relative} "
                f"pages={result.get('page_count', 0)} "
                f"without_text={len(result.get('pages_without_text_layer', []))}"
            )
        except Exception as exc:
            counts["FAILED"] += 1
            failures.append({"source_pdf": relative, "error": str(exc)})
            print(f"[FAIL] {index}/{len(pdf_files)} {relative}: {exc}")

    report = {
        "schema_version": "1.0",
        "completed_at": utc_now(),
        "source": "CAFEF",
        "processed_pdf_count": len(pdf_files),
        "out_of_scope_pdf_count": out_of_scope_count,
        "counts": counts,
        "pages_without_text_layer": pages_without_text,
        "failures": failures,
    }
    write_json_atomic(OUTPUT_ROOT / "extraction_report.json", report)
    print(
        f"Extraction complete: {counts['EXTRACTED']} extracted, "
        f"{counts['SKIPPED_EXISTING']} unchanged, {counts['FAILED']} failed; "
        f"{pages_without_text} pages have no selectable text; "
        f"{out_of_scope_count} non-report PDFs skipped. "
        f"Report: data/extracted/cafef/extraction_report.json"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
