"""Summarize Gemini image OCR attempts against the 2024 Tesseract pilot."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "tmp/ocr-pilot-2024"
RUNS = [ROOT / "tmp/ocr-router-model-batch-2024",
        ROOT / "tmp/ocr-router-model-fallback-2024"]
OUTPUT = ROOT / "tmp/ocr-router-model-batch-2024"


def records_for(pdf_stem: str, root: Path) -> dict[int, dict]:
    path = root / pdf_stem / "pages.jsonl"
    if not path.is_file():
        return {}
    return {item["page"]: item for line in path.read_text(encoding="utf-8").splitlines()
            if (item := json.loads(line))}


def main() -> None:
    files = []
    pages = []
    for json_path in sorted(PILOT.glob("*/2024/*.json")):
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        symbol = payload["document"]["symbol"]
        source_pages = [page for page in payload["pages"]
                        if page.get("extraction_method") == "tesseract"]
        if not source_pages:
            continue
        stem = payload["document"]["filename"].removesuffix(".pdf")
        attempts = [records_for(stem, root) for root in RUNS]
        for source in source_pages:
            number = source["page_number"]
            outcomes = [run[number] for run in attempts if number in run]
            successful = next((item for item in outcomes
                               if item.get("route", "").startswith("tesseract+gemini")), None)
            selected = successful or (outcomes[-1] if outcomes else {})
            number_agreement = selected.get("crossCheck", {}).get("numberAgreement")
            numeric_disagreement = (successful is not None and number_agreement is not None
                                    and number_agreement < 0.95)
            manual_review = successful is not None and (selected.get("status") == "REVIEW"
                                                         or numeric_disagreement)
            pages.append({
                "symbol": symbol,
                "page": number,
                "model_ocr": successful is not None,
                "model": selected.get("gemini", {}).get("model") if successful else None,
                "status": selected.get("status", "NOT_RUN"),
                "manual_review": manual_review,
                "numeric_disagreement": numeric_disagreement,
                "flags": selected.get("flags", []),
                "number_agreement": number_agreement,
                "text_similarity": selected.get("crossCheck", {}).get("similarity"),
                "unreadable": selected.get("gemini", {}).get("unreadable") if successful else None,
                "tesseract_status": source.get("status"),
                "model_text_chars": len(selected.get("text", "")) if successful else 0,
            })
        these = [page for page in pages if page["symbol"] == symbol]
        files.append({
            "symbol": symbol,
            "ocr_pages": len(these),
            "model_pages": sum(page["model_ocr"] for page in these),
            "model_review": sum(page["model_ocr"] and page["status"] == "REVIEW" for page in these),
            "manual_review": sum(page["manual_review"] for page in these),
            "without_model": [page["page"] for page in these if not page["model_ocr"]],
        })

    flags = Counter(flag for page in pages if page["model_ocr"] for flag in page["flags"])
    report = {
        "summary": {
            "ocr_pages": len(pages),
            "model_pages": sum(page["model_ocr"] for page in pages),
            "without_model": sum(not page["model_ocr"] for page in pages),
            "model_review": sum(page["model_ocr"] and page["status"] == "REVIEW" for page in pages),
            "manual_review": sum(page["manual_review"] for page in pages),
            "numeric_disagreements": sum(page["numeric_disagreement"] for page in pages),
            "model_flags": dict(flags),
        },
        "files": files,
        "pages": pages,
    }
    (OUTPUT / "quality_review.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Kiểm tra OCR bằng Gemini trên báo cáo 2024",
        "",
        "Đầu vào: 46 trang mà bộ trích xuất báo cáo thường niên đã chuyển sang Tesseract.",
        "Model được gọi trên ảnh trang PDF; kết quả đối chiếu với Tesseract trong OCR router.",
        "",
        f"- Có bản đọc bằng model: {report['summary']['model_pages']}/{len(pages)} trang.",
        f"- Chưa có bản đọc bằng model: {report['summary']['without_model']} trang; giữ bản Tesseract.",
        f"- Có model nhưng cần rà soát: {report['summary']['model_review']} trang.",
        f"- Số đọc khác Tesseract trên {report['summary']['numeric_disagreements']} trang; tính cả cờ của router, {report['summary']['manual_review']} trang có model cần đối chiếu PDF.",
        f"- Cờ trên các trang có model: {dict(flags)}.",
        "",
        "| Mã | Trang cần OCR | Model đọc được | Cần đối chiếu PDF | Chưa có model |",
        "|---|---:|---:|---:|---|",
    ]
    for item in files:
        missing = ", ".join(map(str, item["without_model"])) or "—"
        lines.append(f"| {item['symbol']} | {item['ocr_pages']} | {item['model_pages']} "
                     f"| {item['manual_review']} | {missing} |")
    lines += ["", "## Trang cần rà soát", ""]
    for item in pages:
        if item["model_ocr"] and not item["manual_review"]:
            continue
        reasons = list(item["flags"])
        if item["numeric_disagreement"]:
            reasons.append(f"NUMBER_AGREEMENT={item['number_agreement']}")
        reason = ", ".join(reasons) or "MODEL_NOT_AVAILABLE"
        lines.append(f"- {item['symbol']} trang {item['page']}: {reason}")
    lines += [
        "",
        "Model 3.8 Flash gặp lỗi 503 và giới hạn 20 lượt gọi miễn phí trong ngày.",
        "Model 3.6 Flash giải quyết được một phần; các lượt còn lại có lỗi 503.",
        "Model 2.5 Flash trả 404 cho tài khoản này nên không được dùng tiếp.",
        "Báo cáo này không xác nhận toàn bộ chữ và bảng chính xác; các trang REVIEW cần đối chiếu PDF.",
        "",
    ]
    (OUTPUT / "quality_review.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
