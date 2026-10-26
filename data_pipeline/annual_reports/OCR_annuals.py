"""Read Vietstock annual-report PDFs into one page-addressable JSON per PDF.

Pages with a usable native PDF text layer use that text. Image-only pages are
rendered and read with Tesseract OCR; both methods are stored in the
same JSON document. This script does not chunk text or create embeddings.

Run from the repository root:
    python data_pipeline/annual_reports/OCR_annuals.py
    python data_pipeline/annual_reports/OCR_annuals.py --symbols BID,VCB
    python data_pipeline/annual_reports/OCR_annuals.py --symbols FPT --ocr-all
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_lib
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
MIN_NATIVE_TEXT_CHARS = 80
BROKEN_TEXT = re.compile(
    r"[�£¶\x00-\x08\x0b\x0e-\x1f]|"
    r"Ã[\x80-\xbf]|Æ°|á»|Ä‘|"
    r"\b(?:BÉO CÉO|MÙc lÙc)\b",
    re.IGNORECASE,
)
BROKEN_TEXT_EXTRA = re.compile(r"[¬®ŸŠÞ£¤º°]{1}")
OCR_ENGINE = "Tesseract"
TESSERACT_LANGUAGE = "vie+eng"
TESSERACT_PSM = 3
TESSERACT_OEM = 1
TESSERACT_EXTRA_CONFIG = ["-c", "preserve_interword_spaces=1", "-c", "tessedit_do_invert=0"]
LOW_CONFIDENCE_THRESHOLD = 65.0
PREPROCESS_SCALE_THRESHOLD = 2200
OCR_REVIEW_PATTERNS = [
    (re.compile(r"\bĐNG\s+NI\s+BT\b", re.IGNORECASE), "UNRESOLVED_OCR_FRAGMENT"),
    (re.compile(r"\bHOAT\b", re.IGNORECASE), "POSSIBLE_MISSING_VIETNAMESE_DIACRITICS"),
    (re.compile(r"\bC[éèê]\s*ph[âa]n\b", re.IGNORECASE), "VIETNAMESE_DIACRITICS_COPHAN"),
    (re.compile(r"\bCỎ\s*PHẢN\b"), "VIETNAMESE_DIACRITICS_COPHAN"),
    (re.compile(r"\bph[ée]\s+Pham\s+Văn\b", re.IGNORECASE), "VIETNAMESE_DIACRITICS_ADDRESS"),
    (re.compile(r"\bDich\s+Vong\b"), "VIETNAMESE_DIACRITICS_ADDRESS"),
    (re.compile(r"\bĐai\s+di[êe]n\b", re.IGNORECASE), "VIETNAMESE_DIACRITICS_DAIDEN"),
    (re.compile(r"\bBao\s+cao\s+thuong\b", re.IGNORECASE), "VIETNAMESE_DIACRITICS_BAOCAO"),
    (re.compile(r"\bUy\s+ban\b", re.IGNORECASE), "VIETNAMESE_DIACRITICS_UYBAN"),
    (re.compile(r"\bCONG\s+BO\b"), "VIETNAMESE_DIACRITICS_CONGBO"),
    (re.compile(r"\bTHONG\s+TIN\b"), "VIETNAMESE_DIACRITICS_THONGTIN"),
    (re.compile(r"\bdinh\s+kem\b", re.IGNORECASE), "VIETNAMESE_DIACRITICS_DINHKEM"),
    (re.compile(r"[¬®ŸŠÞ£¤º°]\s*[;°]|¬\s*°", re.IGNORECASE), "OCR_GARBAGE_SYMBOLS"),
]

OFFLINE_FIXES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bC[éè]\s*ph[âa]n\b", re.IGNORECASE), "Cổ phần"),
    (re.compile(r"\bCỎ\s*PHẢN\b"), "CỔ PHẦN"),
    (re.compile(r"\bC[oô]ng\s+ty\s+C[éè]\b", re.IGNORECASE), "Công ty Cổ"),
    (re.compile(r"\bph[ée]\s+Pham\s+Văn\b", re.IGNORECASE), "phố Phạm Văn"),
    (re.compile(r"\bDich\s+Vong\b"), "Dịch Vọng"),
    (re.compile(r"\bĐai\s+di[êe]n\b", re.IGNORECASE), "Đại diện"),
    (re.compile(r"\bUy\s+ban\b"), "Ủy ban"),
    (re.compile(r"\bBao\s+cao\b", re.IGNORECASE), "Báo cáo"),
    (re.compile(r"\bCONG\s+BO\b"), "CÔNG BỐ"),
    (re.compile(r"\bTHONG\s+TIN\b"), "THÔNG TIN"),
    (re.compile(r"\bdinh\s+kem\b", re.IGNORECASE), "đính kèm"),
    (re.compile(r"\bthuong\s+nien\b", re.IGNORECASE), "thường niên"),
    (re.compile(r"\bChi\s+nh[áa]nh\b", re.IGNORECASE), "Chi nhánh"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def apply_offline_fixes(value: str) -> str:
    out = value
    for pattern, replacement in OFFLINE_FIXES:
        out = pattern.sub(replacement, out)
    return out


def clean_ocr_text(value: str) -> str:
    """Apply only safe Unicode and whitespace cleanup before Gemini processing."""
    text = unicodedata.normalize("NFC", value)
    text = text.replace(" ", " ").replace("​", "").replace("﻿", "")
    text = apply_offline_fixes(text)
    return re.sub(r"\s+", " ", text).strip()


def review_items(value: str) -> list[dict[str, str]]:
    items = []
    for pattern, reason in OCR_REVIEW_PATTERNS:
        for match in pattern.finditer(value):
            items.append({"text": match.group(0), "reason": reason})
    if BROKEN_TEXT_EXTRA.search(value):
        if not any(it.get("reason") == "OCR_GARBAGE_SYMBOLS" for it in items):
            m = BROKEN_TEXT_EXTRA.search(value)
            if m:
                items.append({"text": m.group(0), "reason": "OCR_GARBAGE_SYMBOLS"})
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
    if path.is_file():
        return path
    prefix = SOURCE_ROOT / "files"
    if prefix in path.parents:
        mirror = (SOURCE_ROOT / "files_pdf" / path.relative_to(prefix)).resolve()
        if ROOT in mirror.parents and mirror.is_file():
            return mirror
    raise FileNotFoundError(path)


def native_text_usable(text: str) -> bool:
    return len(text.strip()) >= MIN_NATIVE_TEXT_CHARS and not BROKEN_TEXT.search(text)


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


def preprocess_for_tesseract(image: Path) -> Path:
    """Pillow: gray + autocontrast + upsample small pages. Fallback to original."""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return image
    try:
        out = image.with_suffix(".prep.png")
        img = Image.open(image).convert("L")
        if img.width < PREPROCESS_SCALE_THRESHOLD:
            scale = 1.6
            img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
        img = ImageOps.autocontrast(img, cutoff=1)
        img = img.point(lambda p: 255 if p > 185 else int(p * 0.97))
        img.save(out, dpi=(350, 350))
        return out if out.is_file() and out.stat().st_size > 0 else image
    except Exception as exc:
        print(f"[WARN] preprocess failed for {image.name}: {exc}")
        return image


def run_tesseract(image: Path, executable: str, language: str, psm: int) -> str:
    command = [executable, str(image), "stdout", "-l", language, "--oem", str(TESSERACT_OEM), "--psm", str(psm)] + TESSERACT_EXTRA_CONFIG
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if completed.returncode:
        detail = (completed.stderr or completed.stdout)[-1500:]
        raise RuntimeError(f"Tesseract exited with code {completed.returncode}: {detail}")
    return completed.stdout.strip()


def tesseract_tsv_confidence(image: Path, executable: str, language: str, psm: int) -> float | None:
    try:
        command = [executable, str(image), "stdout", "-l", language, "--oem", str(TESSERACT_OEM), "--psm", str(psm), "tsv"] + TESSERACT_EXTRA_CONFIG
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        if completed.returncode or not completed.stdout:
            return None
        lines = completed.stdout.splitlines()
        confs: list[int] = []
        for line in lines[1:]:
            parts = line.split("\t")
            if len(parts) < 11:
                continue
            try:
                level = int(parts[0])
            except ValueError:
                continue
            if level != 5:
                continue
            cstr = parts[10].strip()
            if cstr.lstrip("-").isdigit():
                c = int(cstr)
                if 0 <= c <= 100:
                    confs.append(c)
        if not confs:
            return None
        return sum(confs) / len(confs)
    except Exception:
        return None


def render_page(pdf: Path, page_number: int, dpi: int, pdftoppm: str, directory: Path) -> Path:
    prefix = directory / f"page-{page_number:04d}"
    command = [pdftoppm, "-f", str(page_number), "-l", str(page_number), "-singlefile", "-r", str(dpi), "-png", str(pdf), str(prefix)]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    image = prefix.with_suffix(".png")
    if completed.returncode or not image.is_file() or image.stat().st_size == 0:
        raise RuntimeError(f"Cannot render PDF page {page_number}: {(completed.stderr or completed.stdout)[-1500:]}")
    return image


def _write_review_preview(pdf_stem: str, symbol: str, year: int, pages: list[dict[str, Any]], output_root: Path, preview_root: Path | None) -> Path | None:
    review_pages = [p for p in pages if p.get("needs_review") or p.get("status") in ("OCR_FAILED", "OCR_NO_TEXT")]
    if not review_pages:
        return None
    base = preview_root if preview_root is not None else (output_root / symbol / str(year) / "review")
    base.mkdir(parents=True, exist_ok=True)
    out = base / f"{pdf_stem}_review.html"
    rows = []
    for p in pages:
        pn = p.get("page_number")
        method = p.get("extraction_method", "")
        status = p.get("status", "")
        needs = p.get("needs_review", False)
        conf = p.get("ocr_confidence")
        conf_str = f"{conf:.1f}" if isinstance(conf, (int, float)) else "-"
        review_reasons = ", ".join(r.get("reason", "") for r in p.get("review_items", [])) or "-"
        img_rel = p.get("review_image") or ""
        img_href = img_rel
        if img_rel:
            try:
                img_path = output_root / img_rel if not Path(img_rel).is_absolute() else Path(img_rel)
                if img_path.is_file():
                    img_href = os.path.relpath(img_path, base).replace("\\", "/")
            except Exception:
                pass
        raw = p.get("text_raw") or p.get("text_layer_raw") or ""
        clean = p.get("text_clean") or p.get("text") or ""
        raw_short = (raw[:600] + " ...") if len(raw) > 600 else raw
        clean_short = (clean[:600] + " ...") if len(clean) > 600 else clean
        row_class = "needs" if needs else ""
        has_img = bool(img_rel and (output_root / img_rel).is_file()) if img_rel else False
        img_cell = f'<a href="{html_lib.escape(img_href)}" target="_blank"><img src="{html_lib.escape(img_href)}" style="max-width:280px;max-height:380px;border:1px solid #ccc"/></a>' if has_img else "<em style='color:#888'>no image</em>"
        raw_html = html_lib.escape(raw_short)
        clean_html = html_lib.escape(clean_short)
        raw_full = html_lib.escape(raw)
        clean_full = html_lib.escape(clean)
        rows.append(f"""
        <tr class="{row_class}">
          <td style="text-align:center">{pn}<br/><small>{html_lib.escape(method)}</small><br/><small>{html_lib.escape(status)}</small><br/><small>conf {conf_str}</small><br/><small>{html_lib.escape(review_reasons)}</small></td>
          <td>{img_cell}</td>
          <td style="max-width:420px;word-break:break-word"><div style="white-space:pre-wrap;font-size:13px">{raw_html}</div><details><summary>full text_raw</summary><pre style="white-space:pre-wrap;word-break:break-word;font-size:12px">{raw_full}</pre></details></td>
          <td style="max-width:420px;word-break:break-word"><div style="white-space:pre-wrap;font-size:13px">{clean_html}</div><details><summary>full text_clean</summary><pre style="white-space:pre-wrap;word-break:break-word;font-size:12px">{clean_full}</pre></details></td>
        </tr>""")
    html_doc = f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"/><title>Review {html_lib.escape(pdf_stem)} - {html_lib.escape(symbol)} {year}</title>
<style>
 body{{font-family:system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:16px;color:#222}}
 table{{border-collapse:collapse;width:100%}}
 th,td{{border:1px solid #ddd;padding:8px;vertical-align:top}}
 th{{background:#f5f5f5;position:sticky;top:0}}
 tr.needs{{background:#fff8e1}}
 .meta{{color:#555;margin-bottom:12px}}
</style></head><body>
<h2>OCR Review - {html_lib.escape(symbol)} {year} - {html_lib.escape(pdf_stem)}</h2>
<div class="meta">Pages needing review: {len(review_pages)} / {len(pages)} - Yellow = needs_review. Click image for full PNG. Compare raw vs clean; verify numbers/dates exactly.</div>
<table><thead><tr><th style="width:110px">Page<br/>method<br/>status<br/>conf</th><th style="width:300px">Image</th><th>text_raw</th><th>text_clean</th></tr></thead><tbody>
{''.join(rows)}
</tbody></table>
</body></html>"""
    out.write_text(html_doc, encoding="utf-8")
    return out


def make_document(record: dict[str, Any], pdf: Path, relative_pdf: str, digest: str, pages: list[dict[str, Any]], *, ocr_all: bool) -> dict[str, Any]:
    missing = [item["page_number"] for item in pages if not (item.get("text_clean") or item.get("text") or "").strip()]
    native_count = sum(item["extraction_method"] == "pdf_text_layer" for item in pages)
    ocr_count = sum(item["extraction_method"] == "tesseract" for item in pages)
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
            "methods": (["TESSERACT"] if ocr_all else ["PDF_TEXT_LAYER"] + (["TESSERACT"] if ocr_count else [])),
            "ocr_scope": "ALL_PAGES" if ocr_all else "PAGES_WITHOUT_USABLE_TEXT_LAYER",
            "ocr_engine": OCR_ENGINE if ocr_count else None,
            "ocr_model": None,
            "ocr_language": TESSERACT_LANGUAGE if ocr_count else None,
            "text_cleaning": {
                "version": "safe-v2-preprocessed",
                "steps": ["Unicode NFC", "offline Vietnamese fixes", "hidden-character removal", "whitespace collapse", "image preprocess: gray+autocontrast+upsample"],
                "numeric_bearing_tokens_preserved": True,
                "decorative_symbols_removed": [],
            } if ocr_count else None,
            "ocr_config": {"page_segmentation_mode": TESSERACT_PSM, "oem": TESSERACT_OEM, "preserve_interword_spaces": 1, "dpi": "350 default"} if ocr_count else None,
            "pages_from_pdf_text_layer": native_count,
            "pages_from_ocr": ocr_count,
            "pages_without_text": missing,
            "text_coverage_percent": round(100 * (len(pages) - len(missing)) / len(pages), 2) if pages else 0,
            "status": "COMPLETE" if not missing and not any(item.get("status") == "OCR_FAILED" for item in pages) else "PARTIAL",
            "review_required": bool(ocr_count),
        },
        "pages": pages,
    }


def process_document(record: dict[str, Any], tesseract: str, *, dpi: int, pdftoppm: str, force: bool,
                     ocr_all: bool, output_root: Path = OUTPUT_ROOT, save_review_images: bool = True, preview_root: Path | None = None,
                     no_preprocess: bool = False) -> dict[str, Any]:
    symbol = str(record.get("symbol", "")).upper()
    year = int(record.get("year", 0))
    outputs = []
    missing_files = []
    for relative_pdf in record.get("pdf_paths") or []:
        try:
            pdf = safe_repo_file(relative_pdf)
        except FileNotFoundError:
            missing_files.append(relative_pdf)
            print(f"[NOT_LOCAL] Manifest PDF path: {relative_pdf}")
            continue
        digest = sha256_file(pdf)
        target = output_root / symbol / str(year) / f"{pdf.stem}.json"
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
            native_has_text = native_text_usable(native_text)
            old_page = old_pages[index] if index < len(old_pages) else {}
            if not ocr_all and native_has_text:
                pages.append({
                    "page_number": page_number,
                    "text": native_text,
                    "status": "TEXT_EXTRACTED",
                    "extraction_method": "pdf_text_layer",
                })
            elif not force and old_page.get("extraction_method") == "tesseract" and (old_page.get("text_raw") or old_page.get("text_clean") or old_page.get("text", "")).strip():
                raw_text = old_page.get("text_raw") or old_page.get("text_clean") or old_page.get("text", "")
                cleaned_text = clean_ocr_text(raw_text)
                reviews = review_items(raw_text)
                used_psm = old_page.get("page_segmentation_mode", TESSERACT_PSM)
                if used_psm != TESSERACT_PSM:
                    reviews.append({"reason": "FALLBACK_PAGE_SEGMENTATION"})
                entry: dict[str, Any] = {
                    "page_number": page_number,
                    "text_raw": raw_text,
                    "text_clean": cleaned_text,
                    "needs_review": bool(reviews),
                    "review_items": reviews,
                    "status": old_page.get("status", "OCR_EXTRACTED"),
                    "extraction_method": "tesseract",
                    "page_segmentation_mode": used_psm,
                }
                if old_page.get("ocr_confidence") is not None:
                    entry["ocr_confidence"] = old_page.get("ocr_confidence")
                if old_page.get("review_image"):
                    entry["review_image"] = old_page.get("review_image")
                conf = entry.get("ocr_confidence")
                if isinstance(conf, (int, float)) and conf < LOW_CONFIDENCE_THRESHOLD:
                    if not any(r.get("reason") == "LOW_TESSERACT_CONFIDENCE" for r in reviews):
                        reviews.append({"reason": "LOW_TESSERACT_CONFIDENCE"})
                        entry["needs_review"] = True
                pages.append(entry)
            else:
                pages.append({"page_number": page_number, "text_raw": "", "text_clean": "", "needs_review": False, "review_items": [], "status": "NO_TEXT_LAYER", "extraction_method": "pending"})
                missing_indices.append(index)

        def preserve_broken_text_layer(index: int) -> None:
            native_text = native_texts[index]
            if len(native_text.strip()) >= MIN_NATIVE_TEXT_CHARS and not native_text_usable(native_text):
                page = pages[index]
                page["text_layer_raw"] = native_text
                page["needs_review"] = True
                page.setdefault("review_items", []).append({"reason": "BROKEN_TEXT_LAYER"})

        for index in range(len(pages)):
            preserve_broken_text_layer(index)

        output_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="finmind-tesseract-", dir=output_root) as temp:
            temp_dir = Path(temp)
            for index in missing_indices:
                page_number = index + 1
                try:
                    recognized = None
                    last_error = None
                    used_psm = TESSERACT_PSM
                    ocr_conf: float | None = None
                    prep_image: Path | None = None
                    rendered_image: Path | None = None
                    attempts = [dpi] + ([180] if dpi > 180 else [])
                    for attempt_dpi in attempts:
                        try:
                            rendered_image = render_page(pdf, page_number, attempt_dpi, pdftoppm, temp_dir)
                            image_path = rendered_image if no_preprocess else preprocess_for_tesseract(rendered_image)
                            prep_image = image_path
                            recognized = run_tesseract(image_path, tesseract, TESSERACT_LANGUAGE, TESSERACT_PSM)
                            used_psm = TESSERACT_PSM
                            ocr_conf = tesseract_tsv_confidence(image_path, tesseract, TESSERACT_LANGUAGE, TESSERACT_PSM)
                            if not recognized:
                                recognized = run_tesseract(image_path, tesseract, TESSERACT_LANGUAGE, 6)
                                used_psm = 6
                                c2 = tesseract_tsv_confidence(image_path, tesseract, TESSERACT_LANGUAGE, 6)
                                if c2 is not None:
                                    ocr_conf = c2
                            break
                        except Exception as exc:
                            last_error = exc
                    if recognized is None:
                        raise RuntimeError(f"OCR failed at {attempts} DPI: {last_error}") from last_error
                    cleaned_text = clean_ocr_text(recognized)
                    reviews = review_items(recognized)
                    if used_psm != TESSERACT_PSM and recognized:
                        reviews.append({"reason": "FALLBACK_PAGE_SEGMENTATION"})
                    if ocr_conf is not None and ocr_conf < LOW_CONFIDENCE_THRESHOLD:
                        reviews.append({"reason": "LOW_TESSERACT_CONFIDENCE"})
                    review_image_rel: str | None = None
                    needs = bool(reviews)
                    if save_review_images and (needs or not recognized.strip()):
                        src_img = prep_image if prep_image is not None else rendered_image
                        if src_img is not None and src_img.is_file():
                            work_dir = output_root / symbol / str(year) / "work" / pdf.stem
                            work_dir.mkdir(parents=True, exist_ok=True)
                            dst = work_dir / f"p-{page_number:03d}.png"
                            try:
                                shutil.copyfile(src_img, dst)
                                try:
                                    review_image_rel = dst.relative_to(output_root).as_posix()
                                except ValueError:
                                    review_image_rel = dst.as_posix()
                            except Exception:
                                pass
                    entry2: dict[str, Any] = {
                        "page_number": page_number,
                        "text_raw": recognized,
                        "text_clean": cleaned_text,
                        "needs_review": needs,
                        "review_items": reviews,
                        "status": "OCR_EXTRACTED" if recognized else "OCR_NO_TEXT",
                        "extraction_method": "tesseract",
                        "page_segmentation_mode": used_psm,
                    }
                    if ocr_conf is not None:
                        entry2["ocr_confidence"] = round(float(ocr_conf), 2)
                    if review_image_rel:
                        entry2["review_image"] = review_image_rel
                    pages[index] = entry2
                except Exception as exc:
                    pages[index] = {"page_number": page_number, "text_raw": "", "text_clean": "", "needs_review": True, "review_items": [{"reason": "OCR_FAILED"}], "status": "OCR_FAILED", "extraction_method": "tesseract"}

                preserve_broken_text_layer(index)
                payload = make_document(record, pdf, relative_pdf, digest, pages, ocr_all=ocr_all)
                atomic_json(target, payload)

        payload = make_document(record, pdf, relative_pdf, digest, pages, ocr_all=ocr_all)
        atomic_json(target, payload)
        try:
            _write_review_preview(pdf.stem, symbol, year, pages, output_root, preview_root)
        except Exception as exc:
            print(f"[WARN] Could not write review preview for {pdf.stem}: {exc}")
        outputs.append({
            "pdf": relative_pdf,
            "json": target.relative_to(ROOT).as_posix() if target.is_relative_to(ROOT) else str(target),
            "pages": len(pages),
            "native_text_pages": payload["extraction"]["pages_from_pdf_text_layer"],
            "ocr_pages": payload["extraction"]["pages_from_ocr"],
            "missing_pages": len(payload["extraction"]["pages_without_text"]),
            "status": payload["extraction"]["status"],
        })
    return {"symbol": symbol, "year": year, "files": outputs, "missing_files": missing_files}


def reclean_existing_json(records: list[dict[str, Any]], output_root: Path = OUTPUT_ROOT) -> tuple[int, int]:
    """Refresh text_clean from preserved OCR text without invoking Tesseract."""
    updated_pages = 0
    updated_files = 0
    for record in records:
        symbol = str(record.get("symbol", "")).upper()
        year = str(record.get("year", ""))
        for relative_pdf in record.get("pdf_paths") or []:
            try:
                pdf = safe_repo_file(relative_pdf)
            except FileNotFoundError:
                print(f"[NOT_LOCAL] Manifest PDF path: {relative_pdf}")
                continue
            target = output_root / symbol / year / f"{pdf.stem}.json"
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
                if page.get("extraction_method") != "tesseract":
                    continue
                raw_text = page.get("text_raw") or ""
                if not raw_text.strip():
                    continue
                page["text_clean"] = clean_ocr_text(raw_text)
                page.pop("correction_rules_applied", None)
                reviews = review_items(raw_text)
                for reason in ("BROKEN_TEXT_LAYER", "FALLBACK_PAGE_SEGMENTATION", "LOW_TESSERACT_CONFIDENCE"):
                    if any(item.get("reason") == reason for item in page.get("review_items", [])):
                        reviews.append({"reason": reason})
                conf = page.get("ocr_confidence")
                if isinstance(conf, (int, float)) and conf < LOW_CONFIDENCE_THRESHOLD and not any(r.get("reason") == "LOW_TESSERACT_CONFIDENCE" for r in reviews):
                    reviews.append({"reason": "LOW_TESSERACT_CONFIDENCE"})
                page["needs_review"] = bool(reviews)
                page["review_items"] = reviews
                page.pop("corrections_applied", None)
                changed += 1

            if not changed:
                continue
            payload.setdefault("extraction", {})["text_cleaning"] = {
                "version": "safe-v2-preprocessed",
                "steps": ["Unicode NFC", "offline Vietnamese fixes", "hidden-character removal", "whitespace collapse", "image preprocess: gray+autocontrast+upsample"],
                "numeric_bearing_tokens_preserved": True,
                "decorative_symbols_removed": [],
            }
            atomic_json(target, payload)
            updated_pages += changed
            updated_files += 1
            print(f"[UPDATED] {target}: cleaned {changed} OCR page(s)")
    return updated_files, updated_pages


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert annual-report PDFs into one JSON per PDF using native text and Tesseract OCR.")
    parser.add_argument("--symbols", help="Comma-separated ticker filter")
    parser.add_argument("--years", help="Comma-separated year filter")
    parser.add_argument("--dpi", type=int, default=350, help="Render resolution for scanned pages (150-400); retries at 180 DPI if OCR fails")
    parser.add_argument("--pdftoppm", default=shutil.which("pdftoppm"), help="Path to Poppler pdftoppm")
    parser.add_argument("--tesseract", default=shutil.which("tesseract"), help="Path to the Tesseract executable")
    parser.add_argument("--force", action="store_true", help="Re-run OCR even if this PDF's JSON already exists")
    parser.add_argument("--ocr-all", action="store_true", help="Run Tesseract on every page, including pages with selectable PDF text")
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT,
                        help="Directory for extraction JSON; defaults to the existing extracted/ corpus")
    parser.add_argument("--reclean-existing-json", action="store_true", help="Rebuild text_clean from existing text_raw without running OCR")
    parser.add_argument("--no-preprocess", action="store_true", help="Disable Pillow preprocessing (use raw rendered PNG)")
    parser.add_argument("--no-review-images", action="store_true", help="Do not save work/*.png for pages needing review")
    parser.add_argument("--preview-root", type=Path, default=None, help="Directory for HTML review previews (default: <output-root>/<symbol>/<year>/review/)")
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
        files, pages = reclean_existing_json(records, args.output_root.resolve())
        print(json.dumps({"updated_files": files, "updated_ocr_pages": pages}, ensure_ascii=False))
        return 0

    if not 150 <= args.dpi <= 400:
        parser.error("--dpi must be between 150 and 400")
    if not args.pdftoppm:
        parser.error("pdftoppm is required to render scanned pages; install Poppler or pass --pdftoppm")
    if not args.tesseract:
        parser.error("Tesseract is required for scanned pages; install it or pass --tesseract")
    tesseract = str(Path(args.tesseract).resolve())
    failures = []
    unavailable_pdfs = []
    processed_files = 0
    preview_root = args.preview_root.resolve() if args.preview_root else None
    for index, record in enumerate(records, start=1):
        label = f"{record.get('symbol')} {record.get('year')}"
        try:
            result = process_document(record, tesseract, dpi=args.dpi, pdftoppm=args.pdftoppm,
                                      force=args.force, ocr_all=args.ocr_all,
                                      output_root=args.output_root.resolve(),
                                      save_review_images=not args.no_review_images,
                                      preview_root=preview_root,
                                      no_preprocess=args.no_preprocess)
            for relative_pdf in result["missing_files"]:
                unavailable_pdfs.append({"symbol": record.get("symbol"), "year": record.get("year"),
                                         "manifest_pdf": relative_pdf})
            if not result["files"]:
                failures.append({"symbol": record.get("symbol"), "year": record.get("year"),
                                 "error": "No local PDF could be processed for this record"})
            processed_files += len(result["files"])
            for file_result in result["files"]:
                print(f"[{index}/{len(records)}] {label}: {file_result['status']} native={file_result['native_text_pages']} OCR={file_result['ocr_pages']} missing={file_result['missing_pages']} -> {file_result['json']}")
        except Exception as exc:
            failures.append({"symbol": record.get("symbol"), "year": record.get("year"), "error": f"{type(exc).__name__}: {exc}"})
            print(f"[FAILED] {label}: {exc}")
    print(json.dumps({"records": len(records), "manifest_pdf_paths": sum(len(item.get('pdf_paths') or []) for item in records),
                      "processed_files": processed_files, "unavailable_pdfs": unavailable_pdfs,
                      "failures": failures}, ensure_ascii=False))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
