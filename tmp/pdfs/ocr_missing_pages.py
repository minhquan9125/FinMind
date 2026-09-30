import json
import os
import subprocess
import tempfile
from pathlib import Path

import pypdfium2 as pdfium

ROOT = Path.cwd()
BASE = ROOT / "data/references/vietstock/annual_reports"
REPORT = BASE / "extracted/extraction_report.json"
OUT = BASE / "extracted/page_ocr_fallback.json"
TESSERACT = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Tesseract-OCR/tesseract.exe"

report = json.loads(REPORT.read_text(encoding="utf-8"))
results = []
failed_pages = []
with tempfile.TemporaryDirectory(prefix="finmind_page_ocr_") as temp_dir:
    temp_dir = Path(temp_dir)
    for document in report.get("processed_documents", []):
        for file_result in document.get("files", []):
            if not file_result.get("pages_without_text"):
                continue
            extracted_json = ROOT / file_result["output"]
            detail = json.loads(extracted_json.read_text(encoding="utf-8"))
            pdf_path = ROOT / detail["document"]["relative_path"]
            if not pdf_path.is_file():
                failed_pages.append({"ticker": detail["document"]["symbol"], "year": detail["document"]["year"], "pdf": str(pdf_path), "error": "source PDF not found"})
                continue
            pdf = pdfium.PdfDocument(str(pdf_path))
            try:
                for page_num in file_result["pages_without_text"]:
                    image_path = temp_dir / f"{detail['document']['symbol']}_{detail['document']['year']}_{page_num}.png"
                    try:
                        page = pdf[int(page_num) - 1]
                        page.render(scale=2.0).to_pil().save(image_path)
                        proc = subprocess.run(
                            [str(TESSERACT), str(image_path), "stdout", "-l", "vie+eng", "--psm", "6"],
                            capture_output=True,
                            text=True,
                            encoding="utf-8",
                            errors="replace",
                            check=False,
                        )
                        results.append({
                            "ticker": detail["document"]["symbol"],
                            "year": detail["document"]["year"],
                            "document": detail["document"]["title"],
                            "pdf": detail["document"]["relative_path"],
                            "page": int(page_num),
                            "ocr_engine": "Tesseract 5.5.3 direct page-image OCR",
                            "status": "COMPLETED" if proc.returncode == 0 else "FAILED",
                            "text": proc.stdout.strip(),
                            "error": proc.stderr[-1000:] if proc.returncode else None,
                        })
                    except Exception as exc:
                        failed_pages.append({"ticker": detail["document"]["symbol"], "year": detail["document"]["year"], "pdf": detail["document"]["relative_path"], "page": int(page_num), "error": f"{type(exc).__name__}: {exc}"})
            finally:
                pdf.close()

payload = {
    "schema_version": "1.0",
    "purpose": "Direct page-image OCR fallback for OCRmyPDF-failed annual-report pages. Verify against source PDF before using any numbers.",
    "source_report": REPORT.relative_to(ROOT).as_posix(),
    "completed_pages": sum(row["status"] == "COMPLETED" for row in results),
    "failed_pages": len(failed_pages) + sum(row["status"] == "FAILED" for row in results),
    "results": results,
    "errors": failed_pages,
}
OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"output": OUT.relative_to(ROOT).as_posix(), "candidate_pages": len(results) + len(failed_pages), "completed": payload["completed_pages"], "failed": payload["failed_pages"]}, ensure_ascii=False))
