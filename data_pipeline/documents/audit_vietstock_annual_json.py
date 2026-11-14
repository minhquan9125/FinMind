"""Audit text-only annual-report JSON against the downloaded PDF manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data" / "references" / "vietstock" / "annual_reports"
MANIFEST = BASE / "manifest.json"
EXTRACTED = BASE / "extracted"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit_file(record: dict, relative_pdf: str) -> dict:
    source = (ROOT / relative_pdf).resolve()
    if source != ROOT and ROOT not in source.parents:
        return {"status": "FAIL", "source_pdf": relative_pdf, "issues": ["PDF_PATH_ESCAPES_REPOSITORY"]}
    output = EXTRACTED / str(record.get("symbol", "UNKNOWN")).upper() / str(record.get("year", "UNKNOWN")) / f"{source.stem}.json"
    issues: list[str] = []
    if not source.is_file():
        return {"status": "FAIL", "source_pdf": relative_pdf, "json_file": output.relative_to(ROOT).as_posix(), "issues": ["PDF_MISSING"]}
    if not output.is_file():
        return {"status": "FAIL", "source_pdf": relative_pdf, "json_file": output.relative_to(ROOT).as_posix(), "issues": ["JSON_MISSING"]}

    try:
        data = json.loads(output.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "FAIL", "source_pdf": relative_pdf, "json_file": output.relative_to(ROOT).as_posix(), "issues": [f"JSON_INVALID: {exc}"]}

    document = data.get("document") or {}
    extraction = data.get("extraction") or {}
    pages = data.get("pages")
    summary = data.get("summary") or {}
    source_hash = sha256_file(source)
    schema_version = str(data.get("schema_version", ""))
    combined_schema = data.get("schema_name") == "finmind.annual_report_extraction" and schema_version == "2.0"
    legacy_schema = data.get("schema_name") == "finmind.annual_report_text_extraction" and schema_version == "1.1"
    if not (combined_schema or legacy_schema):
        issues.append("SCHEMA_VERSION_MISMATCH")
    if document.get("sha256") != source_hash:
        issues.append("SOURCE_HASH_MISMATCH")
    if document.get("symbol", "").upper() != str(record.get("symbol", "")).upper():
        issues.append("SYMBOL_MISMATCH")
    if document.get("year") != record.get("year"):
        issues.append("YEAR_MISMATCH")
    if not isinstance(pages, list):
        pages = []
        issues.append("PAGES_NOT_A_LIST")
    if legacy_schema and (extraction.get("ocr_used") is not False or (data.get("ocr") or {}).get("requested") is not False):
        issues.append("UNEXPECTED_OCR_IN_LEGACY_JSON")
    if legacy_schema and extraction.get("method") != "PDF_TEXT_LAYER":
        issues.append("EXTRACTION_METHOD_MISMATCH")
    if combined_schema and document.get("page_count") != len(pages or []):
        issues.append("DOCUMENT_PAGE_COUNT_MISMATCH")

    expected_count = summary.get("page_count", document.get("page_count"))
    page_numbers = [page.get("page_number", page.get("page")) for page in pages]
    if expected_count != len(pages):
        issues.append("PAGE_COUNT_MISMATCH")
    if page_numbers != list(range(1, len(pages) + 1)):
        issues.append("PAGE_NUMBER_SEQUENCE_INVALID")
    no_text_pages = []
    for page in pages:
        number = page.get("page_number", page.get("page"))
        text = page.get("text_clean", page.get("text"))
        has_text = bool(text.strip()) if isinstance(text, str) else False
        if legacy_schema:
            has_text = isinstance(text, str) and len(text.strip()) >= 40
        if "has_text" in page and bool(page.get("has_text")) != has_text:
            issues.append(f"PAGE_TEXT_FLAG_MISMATCH:{number}")
        if not has_text:
            no_text_pages.append(number)
            if page.get("status") not in ("NO_TEXT_LAYER", "OCR_NO_TEXT", "OCR_FAILED"):
                issues.append(f"UNMARKED_NO_TEXT_PAGE:{number}")
    expected_missing = summary.get("pages_without_text", extraction.get("pages_without_text"))
    if expected_missing != no_text_pages:
        issues.append("NO_TEXT_PAGE_SUMMARY_MISMATCH")

    warnings = []
    if len(pages) < 10:
        warnings.append("VERY_SHORT_PDF_REVIEW_IF_THIS_IS_EXPECTED_TO_BE_A_FULL_ANNUAL_REPORT")
    if combined_schema and extraction.get("review_required"):
        warnings.append("PADDLEOCR_TEXT_REQUIRES_MANUAL_REVIEW")
    status = "FAIL" if issues else ("PARTIAL" if no_text_pages or warnings else "PASS")
    return {
        "status": status,
        "symbol": document.get("symbol"),
        "year": document.get("year"),
        "source_pdf": relative_pdf,
        "json_file": output.relative_to(ROOT).as_posix(),
        "source_sha256": source_hash,
        "page_count": len(pages),
        "pages_with_text": sum(1 for page in pages if (page.get("text_clean") or page.get("text") or "").strip()),
        "pages_needing_review": sum(1 for page in pages if page.get("needs_review")),
        "pages_without_text": no_text_pages,
        "text_coverage_percent": extraction.get("text_coverage_percent"),
        "ocr_used": bool(extraction.get("pages_from_ocr", 0)) if combined_schema else extraction.get("ocr_used"),
        "pages_from_ocr": extraction.get("pages_from_ocr", 0),
        "ocr_review_required": bool(extraction.get("review_required", False)) if combined_schema else False,
        "issues": issues,
        "warnings": warnings,
    }


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    results = []
    for record in manifest.get("documents", []):
        if record.get("status") != "DOWNLOADED":
            continue
        for pdf_path in record.get("pdf_paths") or []:
            results.append(audit_file(record, pdf_path))

    counts = {status: sum(item["status"] == status for item in results) for status in ("PASS", "PARTIAL", "FAIL")}
    report = {
        "schema_name": "finmind.annual_report_json_quality_report",
        "schema_version": "1.0",
        "source_manifest": MANIFEST.relative_to(ROOT).as_posix(),
        "ocr_used": any(bool(item.get("ocr_used")) for item in results),
        "summary": {
            "source_records": sum(record.get("status") == "DOWNLOADED" for record in manifest.get("documents", [])),
            "source_pdfs": len(results),
            "pass": counts["PASS"],
            "partial": counts["PARTIAL"],
            "fail": counts["FAIL"],
            "warnings": sum(bool(item.get("warnings")) for item in results),
            "pages": sum(item.get("page_count", 0) for item in results),
            "pages_without_text": sum(len(item.get("pages_without_text", [])) for item in results),
            "pages_from_ocr": sum(item.get("pages_from_ocr", 0) for item in results),
            "ocr_review_required": sum(bool(item.get("ocr_review_required")) for item in results),
        },
        "files": results,
    }
    target = EXTRACTED / "quality_report.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Báo cáo chất lượng JSON BCTN",
        "",
        f"- Phương pháp: pypdf cho trang có lớp chữ; PaddleOCR cho {report['summary']['pages_from_ocr']} trang scan.",
        f"- Bản ghi nguồn: {report['summary']['source_records']}; tệp PDF: {report['summary']['source_pdfs']}.",
        f"- Kết quả: {counts['PASS']} đầy đủ text, {counts['PARTIAL']} một phần, {counts['FAIL']} lỗi kiểm tra.",
        f"- Tổng trang: {report['summary']['pages']}; trang không có lớp chữ: {report['summary']['pages_without_text']}.",
        "",
        "| Mã | Năm | PDF | Trang | Có chữ | Thiếu chữ | Độ phủ | Trạng thái | Lỗi | Cảnh báo |",
        "|---|---:|---|---:|---:|---:|---:|---|---|---|",
    ]
    for item in results:
        filename = Path(item.get("source_pdf", "unknown")).name
        lines.append(
            f"| {item.get('symbol', '')} | {item.get('year', '')} | {filename} "
            f"| {item.get('page_count', 0)} | {item.get('pages_with_text', 0)} "
            f"| {len(item.get('pages_without_text', []))} | {item.get('text_coverage_percent', '')}% "
            f"| {item.get('status', 'FAIL')} | {', '.join(item.get('issues', [])) or 'Không'} "
            f"| {', '.join(item.get('warnings', [])) or 'Không'} |"
        )
    lines.extend([
        "",
        "## Ghi chú",
        "",
        "`PARTIAL` nghĩa là JSON hợp lệ và hash/trang đã khớp nhưng còn trang không đọc được hoặc có nội dung PaddleOCR cần người đối chiếu.",
        "`FAIL` nghĩa là lỗi cấu trúc, metadata, hash nguồn hoặc khai báo OCR; cần xử lý trước khi nhập corpus.",
        "Kiểm tra này xác nhận tính toàn vẹn cấu trúc và nguồn, không bảo đảm bảng/đoạn văn trích xuất đúng thứ tự hoặc nội dung đã được người kiểm duyệt xác nhận.",
        "",
    ])
    markdown_target = EXTRACTED / "quality_report.md"
    markdown_target.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    print(f"Reports: {target.relative_to(ROOT).as_posix()}, {markdown_target.relative_to(ROOT).as_posix()}")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
