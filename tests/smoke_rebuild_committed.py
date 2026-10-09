"""Rebuild two sample PDFs from fixed OCR input and compare JSON digests.

Run from any directory:
    python tests/smoke_rebuild_committed.py

The BCTN 2025 OCR input is kept as a small test fixture. Generated IR is not
committed; only normalized JSON digests are. A changed builder must deliberately
run this script with --update after reviewing the resulting diff.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from buildDocumentIr import build_document_ir  # noqa: E402
from financialContent import ACCOUNTING_TEMPLATE  # noqa: E402
from util import hash_file  # noqa: E402

SAMPLES = ("FPT_2024_498332 (1)", "BCTN_2025")
SNAPSHOT = ROOT / "tests" / "fixtures" / "document_ir_snapshot.json"


def _normalize(value: object) -> object:
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        return {key: (Path(item).name if key == "pdf" and isinstance(item, str)
                      else _normalize(item))
                for key, item in value.items() if key != "arithmetic_template_sha256"}
    return value


def _prepare_inputs(sample: str, directory: Path) -> Path:
    fixture = (ROOT / "tests" / "fixtures" / "bctn2025" if sample == "BCTN_2025"
               else ROOT / "ocr_router_out" / sample)
    input_dir = directory / "input"
    input_dir.mkdir()
    pages = (fixture / "pages.jsonl").read_bytes()
    pages_path = input_dir / "pages.jsonl"
    pages_path.write_bytes(pages)
    for line in pages.splitlines():
        record = json.loads(line)
        if record["route"] == "text_layer":
            continue
        name = f"p-{record['page']:03d}"
        image = next((path for path in (f"work/{name}.up.png", f"work/{name}.png")
                      if (fixture / path).is_file()), None)
        if image is None:
            raise FileNotFoundError(f"Thiếu ảnh OCR {sample} trang {record['page']}")
        target = input_dir / "work" / Path(image).name
        target.parent.mkdir(exist_ok=True)
        target.write_bytes((fixture / image).read_bytes())
    return pages_path


def _output_digests(output_dir: Path) -> dict[str, str]:
    digests: dict[str, str] = {}
    for path in sorted(output_dir.rglob("*.json")):
        relative = path.relative_to(output_dir).as_posix()
        normalized = _normalize(json.loads(path.read_text(encoding="utf-8")))
        canonical = json.dumps(normalized, ensure_ascii=False, sort_keys=True,
                               separators=(",", ":")).encode("utf-8")
        digests[relative] = hashlib.sha256(canonical).hexdigest()
    return digests


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true",
                        help="Ghi lại checksum sau khi đã duyệt thay đổi IR")
    args = parser.parse_args()
    if not ACCOUNTING_TEMPLATE.is_file():
        raise FileNotFoundError(ACCOUNTING_TEMPLATE)
    actual: dict[str, object] = {"template_sha256": hash_file(ACCOUNTING_TEMPLATE),
                                 "samples": {}}
    for sample in SAMPLES:
        pdf = ROOT / f"{sample}.pdf"
        if not pdf.is_file():
            raise FileNotFoundError(pdf)
        with tempfile.TemporaryDirectory(prefix="ocr-ir-smoke-") as temp:
            root = Path(temp)
            pages = _prepare_inputs(sample, root)
            output = root / "annual_ir"
            build_document_ir(pdf, pages, output, ACCOUNTING_TEMPLATE)
            table_index = json.loads((output / "table" / "index.json").read_text(encoding="utf-8"))
            if table_index["arithmetic_template_sha256"] != hash_file(ACCOUNTING_TEMPLATE):
                raise ValueError(f"{sample}: SHA-256 template sai")
            actual["samples"][sample] = {"pdf_sha256": hash_file(pdf),
                                           "files": _output_digests(output)}
    if args.update:
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(json.dumps(actual, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8", newline="\n")
        print(f"Đã cập nhật {SNAPSHOT}")
        return 0
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    differences: list[str] = []
    if expected["template_sha256"] != actual["template_sha256"]:
        differences.append("SHA-256 template đổi")
    for sample in SAMPLES:
        old = expected["samples"][sample]
        new = actual["samples"][sample]
        if old["pdf_sha256"] != new["pdf_sha256"]:
            differences.append(f"{sample}: PDF đổi")
        old_files, new_files = old["files"], new["files"]
        differences.extend(f"{sample}: thiếu {path}" for path in sorted(old_files.keys() - new_files.keys()))
        differences.extend(f"{sample}: thêm {path}" for path in sorted(new_files.keys() - old_files.keys()))
        differences.extend(f"{sample}: khác {path}" for path in sorted(old_files.keys() & new_files.keys())
                           if old_files[path] != new_files[path])
    if differences:
        print(f"FAIL: {len(differences)} khác biệt so với snapshot đã duyệt")
        for difference in differences[:30]:
            print(" -", difference)
        if len(differences) > 30:
            print(f" ... và {len(differences) - 30} khác biệt nữa")
        return 1
    print("OK: 2 PDF dựng lại khớp checksum JSON; template SHA-256 đúng")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
