"""Run the existing image OCR router on the 2024 pilot's Tesseract pages."""

from __future__ import annotations

import json
import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "tmp/ocr-pilot-2024"
OUTPUT = ROOT / "tmp/ocr-router-model-batch-2024"
ROUTER = ROOT / "ocr-router/src/main.py"
MODEL = "gemini-3.8-flash"
UNRESOLVED_FROM: list[Path] = []


def job_for(json_path: Path) -> tuple[str, Path, list[int]] | None:
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    pages = [page["page_number"] for page in payload["pages"]
             if page.get("extraction_method") == "tesseract"]
    for earlier in UNRESOLVED_FROM:
        previous = earlier / payload["document"]["filename"].removesuffix(".pdf") / "pages.jsonl"
        if previous.is_file():
            completed = {item["page"] for line in previous.read_text(encoding="utf-8").splitlines()
                         if (item := json.loads(line)).get("route", "").startswith("tesseract+gemini")}
            pages = [page for page in pages if page not in completed]
    if not pages:
        return None
    relative = payload["document"]["relative_path"]
    pdf = ROOT / relative
    if not pdf.is_file():
        pdf = ROOT / relative.replace("/files/", "/files_pdf/", 1)
    if not pdf.is_file():
        raise FileNotFoundError(relative)
    return payload["document"]["symbol"], pdf, pages


def run_one(job: tuple[str, Path, list[int]]) -> dict:
    symbol, pdf, pages = job
    command = [sys.executable, str(ROUTER), str(pdf), "--pages",
               ",".join(map(str, pages)), "--gemini", "always", "--model",
               MODEL, "--min-chars", "999999", "--batch", "4",
               "--gemini-concurrency", "1", "--tess-workers", "2",
               "--long-side", "2200", "--out", str(OUTPUT)]
    result = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", check=False)
    log = OUTPUT / "logs" / f"{symbol}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stdout, encoding="utf-8")
    return {"symbol": symbol, "pages": pages, "exit_code": result.returncode,
            "log": str(log)}


def main() -> int:
    global OUTPUT, MODEL, UNRESOLVED_FROM
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    parser.add_argument("--unresolved-from", type=Path, action="append")
    args = parser.parse_args()
    OUTPUT = args.out.resolve()
    MODEL = args.model
    UNRESOLVED_FROM = [path.resolve() for path in args.unresolved_from or []]
    jobs = [job for path in sorted(PILOT.glob("*/2024/*.json"))
            if (job := job_for(path)) is not None]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    print(json.dumps({"documents": len(jobs), "pages": sum(len(job[2]) for job in jobs)}), flush=True)
    results = []
    with ThreadPoolExecutor(max_workers=1 if UNRESOLVED_FROM else 2) as pool:
        for future in as_completed([pool.submit(run_one, job) for job in jobs]):
            result = future.result()
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
    (OUTPUT / "batch_result.json").write_text(
        json.dumps(sorted(results, key=lambda item: item["symbol"]), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return int(any(item["exit_code"] for item in results))


if __name__ == "__main__":
    raise SystemExit(main())
