import importlib.util
import json
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "run_all_reports.py"
spec = importlib.util.spec_from_file_location("annual_ocr_batch", SCRIPT)
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)


def write_output(folder: Path, pages: list[dict]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "source.json").write_text(json.dumps({
        "sha256": "known", "provider": "openrouter", "model": "vision-model"}), encoding="utf-8")
    (folder / "summary.json").write_text(json.dumps({"pages": len(pages), "routes": {}}), encoding="utf-8")
    (folder / "pages.jsonl").write_text("".join(json.dumps(page) + "\n" for page in pages), encoding="utf-8")


def test_inspect_output_requires_every_page_and_reports_pending_model(tmp_path: Path) -> None:
    folder = tmp_path / "annual"
    write_output(folder, [{"page": 1, "status": "OK", "flags": []},
                          {"page": 2, "status": "REVIEW", "flags": ["GEMINI_FAILED"]}])
    result = batch.inspect_output(folder, "known", "openrouter", "vision-model")
    assert result["status"] == "MODEL_PENDING"
    assert result["model_failed_pages"] == [2]
    assert result["review_pages"] == [2]

    write_output(folder, [{"page": 1, "status": "OK", "flags": []},
                          {"page": 3, "status": "OK", "flags": []}])
    assert batch.inspect_output(folder, "known", "openrouter", "vision-model") is None
    assert batch.inspect_output(folder, "different", "openrouter", "vision-model") is None


def test_discover_pdfs_rejects_misplaced_symbol_directory(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "files_pdf"
    misplaced = root / "TCB" / "ITD" / "2024" / "ITD_2024.pdf"
    misplaced.parent.mkdir(parents=True)
    misplaced.touch()
    monkeypatch.setattr(batch, "PDF_ROOT", root)

    with pytest.raises(ValueError, match=r"TCB/ITD/2024/ITD_2024.pdf.*SYMBOL/YYYY"):
        batch.discover_pdfs(None, None)


def test_drive_pdfs_are_staged_only_for_the_batch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(batch, "ROOT", tmp_path)
    manifest = tmp_path / "data/references/vietstock/annual_reports/manifest.json"
    manifest.parent.mkdir(parents=True)
    relative = "data/references/vietstock/annual_reports/files/FPT/2024/report.pdf"
    manifest.write_text(json.dumps({"documents": [{"symbol": "FPT", "year": 2024,
        "status": "DOWNLOADED", "pdf_paths": [relative],
        "drive_files": {relative: {"id": "remote", "sha256": "verified"}}}]}), encoding="utf-8")
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF- verified")

    class FakeStore:
        @contextmanager
        def temporary_pdf(self, entry, filename, *, temp_root=None):
            assert entry["id"] == "remote"
            assert filename == "report.pdf"
            yield source

    with patch.object(batch.DriveStore, "from_oauth", return_value=FakeStore()):
        with batch.staged_drive_pdf_root({"FPT"}, {"2024"}) as staged:
            pdf = staged / "FPT/2024/report.pdf"
            assert pdf.read_bytes() == source.read_bytes()
            assert batch.PDF_ROOT != staged
    assert not staged.exists()


def test_batch_summary_separates_model_pending_from_other_review_pages() -> None:
    documents = [
        {"status": "MODEL_PENDING", "pages": 100,
         "model_failed_pages": [2, 5], "review_pages": [2, 5, 8]},
        {"status": "COMPLETE", "pages": 50,
         "model_failed_pages": [], "review_pages": [3]},
    ]
    summary = batch.summarize_results(2, documents)
    assert summary["model_pending_pages"] == 2
    assert summary["review_pages"] == 4
    assert summary["review_without_model_failure_pages"] == 2


def test_merge_pending_pages_keeps_successful_old_pages(tmp_path: Path) -> None:
    folder = tmp_path / "annual"
    original = [
        {"page": 1, "route": "tesseract+gemini", "status": "OK", "flags": [], "text": "old good"},
        {"page": 2, "route": "tesseract", "status": "REVIEW", "flags": ["GEMINI_FAILED"], "text": "old pending"},
    ]
    retried = [
        {"page": 1, "route": "tesseract", "status": "OK", "flags": [], "text": "new fallback"},
        {"page": 2, "route": "tesseract+gemini", "status": "OK", "flags": [], "text": "new good"},
    ]
    write_output(folder, retried)
    (folder / "summary.json").write_text(json.dumps({"pages": 2, "routes": {}, "config": {}}), encoding="utf-8")
    batch.merge_pending_pages(folder, original, [2])
    pages = batch.read_pages(folder / "pages.jsonl")
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    assert [page["text"] for page in pages] == ["old good", "new good"]
    assert (folder / "text" / "p-001.txt").read_text(encoding="utf-8") == "old good"
    assert summary["routes"] == {"tesseract+gemini": 2}
    assert summary["reviewPages"] == []
    assert summary["config"]["retryPendingPages"] == [2]


def test_inspect_output_can_find_pending_after_model_switch(tmp_path: Path) -> None:
    folder = tmp_path / "annual"
    write_output(folder, [{"page": 1, "status": "REVIEW", "flags": ["GEMINI_FAILED"]}])
    assert batch.inspect_output(folder, "known", "openrouter", None)["model_failed_pages"] == [1]
    assert batch.inspect_output(folder, "known", "openrouter", "other-model") is None
