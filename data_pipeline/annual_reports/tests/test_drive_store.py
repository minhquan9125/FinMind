"""Drive PDF storage keeps verified remote copies and temporary OCR inputs."""

import hashlib
import json
from argparse import Namespace
from contextlib import contextmanager
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import drive_store
import vietstock_download_annual as collector
import OCR_annuals as ocr
import check_vietstock_annual_json as audit


class FakeFiles:
    def __init__(self):
        self.items = {}
        self.next_id = 1

    def create(self, *, body, media_body=None, fields):
        file_id = str(self.next_id)
        self.next_id += 1
        data = Path(media_body.filename).read_bytes() if media_body is not None else b""
        self.items[file_id] = {"name": body["name"], "parents": body["parents"],
                               "mimeType": body["mimeType"], "bytes": data}
        return FakeRequest({"id": file_id})

    def list(self, *, q, fields, pageSize):
        import re
        parent = re.search(r"'([^']+)' in parents", q).group(1)
        name = re.search(r"name = '([^']+)'", q).group(1)
        items = [{"id": file_id, "name": item["name"], "parents": item["parents"],
                  "mimeType": item["mimeType"]} for file_id, item in self.items.items()
                 if item["name"] == name and parent in item["parents"]]
        return FakeRequest({"files": items})

    def update(self, *, fileId, addParents, removeParents, fields):
        item = self.items[fileId]
        item["parents"] = [p for p in item["parents"] if p != removeParents] + [addParents]
        return FakeRequest({"id": fileId, "parents": item["parents"]})

    def get(self, *, fileId, fields):
        item = self.items[fileId]
        return FakeRequest({"id": fileId, "name": item["name"], "mimeType": item["mimeType"],
                            "size": str(len(item["bytes"])),
                            "md5Checksum": hashlib.md5(item["bytes"]).hexdigest(), "parents": item["parents"]})

    def get_media(self, *, fileId):
        return FakeMediaRequest(self.items[fileId]["bytes"])


class FakeRequest:
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value


class FakeMediaRequest:
    def __init__(self, data):
        self.data = data


class FakeService:
    def __init__(self):
        self.file_api = FakeFiles()

    def files(self):
        return self.file_api


class DriveStoreTests(unittest.TestCase):
    def test_upload_creates_ticker_and_year_folders(self):
        service = FakeService()
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / "report.pdf"
            pdf.write_bytes(b"%PDF- sample")
            with patch.object(drive_store, "MediaFileUpload", lambda filename, mimetype, resumable: type("Media", (), {"filename": filename})()), \
                 patch.object(drive_store, "MediaIoBaseDownload", FakeDownloader):
                store = drive_store.DriveStore(service, "folder123")
                entry = store.upload_pdf(pdf, "FPT", 2024)
            year = service.file_api.items[entry["parent_id"]]
            ticker = service.file_api.items[year["parents"][0]]
            self.assertEqual((ticker["name"], year["name"]), ("FPT", "2024"))
            self.assertEqual(ticker["parents"], ["folder123"])
            self.assertTrue(store.verify_entry(entry))

    def test_existing_flat_pdf_moves_into_ticker_year_folder(self):
        service = FakeService()
        data = b"%PDF- old"
        service.file_api.items["legacy"] = {"name": "FPT_2024_report.pdf", "parents": ["folder123"],
                                            "mimeType": "application/pdf", "bytes": data}
        entry = {"id": "legacy", "name": "FPT_2024_report.pdf", "size_bytes": len(data),
                 "md5": hashlib.md5(data).hexdigest(), "sha256": hashlib.sha256(data).hexdigest()}
        store = drive_store.DriveStore(service, "folder123")
        moved = store.place_entry(entry, "FPT", 2024)
        self.assertTrue(store.verify_entry(moved))
        self.assertNotEqual(moved["parent_id"], "folder123")

    def test_move_recovers_if_remote_moved_before_manifest_save(self):
        service = FakeService()
        store = drive_store.DriveStore(service, "folder123")
        target_id = store.report_folder("FPT", 2024)
        data = b"%PDF- old"
        service.file_api.items["legacy"] = {"name": "FPT_2024_report.pdf", "parents": [target_id],
                                            "mimeType": "application/pdf", "bytes": data}
        stale = {"id": "legacy", "name": "FPT_2024_report.pdf", "size_bytes": len(data),
                 "md5": hashlib.md5(data).hexdigest(), "sha256": hashlib.sha256(data).hexdigest()}
        moved = store.place_entry(stale, "FPT", 2024)
        self.assertEqual(moved["parent_id"], target_id)

    def test_text_cleaner_can_identify_drive_pdf_without_download(self):
        record = {"drive_files": {"reports/report.pdf": {"sha256": "abc123"}}}
        with patch.object(ocr, "safe_repo_file", side_effect=FileNotFoundError):
            self.assertEqual(ocr.pdf_identity(record, "reports/report.pdf"), ("report.pdf", "abc123"))

    def test_sync_existing_persists_drive_id_before_pruning(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf = root / "data/references/vietstock/annual_reports/files_pdf/FPT/2024/report.pdf"
            pdf.parent.mkdir(parents=True)
            pdf.write_bytes(b"%PDF- existing")
            relative = pdf.relative_to(root).as_posix().replace("files_pdf/", "files/")
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps({"documents": [{"symbol": "FPT", "year": 2024,
                "provider_file_id": "1", "file_url": "https://example.test/1", "status": "DOWNLOADED",
                "pdf_paths": [relative], "archive_path": relative}]}), encoding="utf-8")
            store = drive_store.DriveStore(FakeService(), "folder123")
            args = Namespace(symbols="FPT", years="2024", drive_folder_id="folder123", drive_prune_local=True)
            with patch.object(collector, "ROOT", root), patch.object(collector, "MANIFEST_PATH", manifest_path), \
                 patch.object(collector.DriveStore, "from_oauth", return_value=store), \
                 patch.object(drive_store, "MediaFileUpload", lambda filename, mimetype, resumable: type("Media", (), {"filename": filename})()), \
                 patch.object(drive_store, "MediaIoBaseDownload", FakeDownloader):
                self.assertEqual(collector.sync_existing_to_drive(args), 0)
                self.assertEqual(collector.sync_existing_to_drive(args), 0)
            self.assertFalse(pdf.exists())
            saved = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertIn(relative, saved["documents"][0]["drive_files"])

    def test_ocr_process_document_uses_remote_pdf_when_local_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / "report.pdf"
            pdf.write_bytes(b"%PDF- remote")
            record = {"pdf_paths": ["report.pdf"], "drive_files": {"report.pdf": {"id": "remote"}}}

            class Store:
                @contextmanager
                def temporary_pdf(self, entry, filename):
                    assert entry["id"] == "remote" and filename == "report.pdf"
                    yield pdf

            def fake_process(record, tesseract, *, pdf_resolver, **kwargs):
                resolved = pdf_resolver("report.pdf")
                return resolved.read_bytes()

            with patch.object(ocr, "safe_repo_file", side_effect=FileNotFoundError), \
                 patch.object(ocr, "_process_document", side_effect=fake_process), \
                 patch.object(drive_store.DriveStore, "from_oauth", return_value=Store()):
                self.assertEqual(ocr.process_document(record, "tesseract", dpi=300, pdftoppm="poppler", force=False,
                                                      ocr_all=False), b"%PDF- remote")

    def test_ocr_writes_json_from_remote_pdf(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf = root / "report.pdf"
            pdf.write_bytes(b"%PDF- remote")
            store = drive_store.DriveStore(FakeService(), "folder123")
            with patch.object(drive_store, "MediaFileUpload", lambda filename, mimetype, resumable: type("Media", (), {"filename": filename})()), \
                 patch.object(drive_store, "MediaIoBaseDownload", FakeDownloader):
                entry = store.upload_pdf(pdf, "FPT", 2024)
                pdf.unlink()
                record = {"symbol": "FPT", "year": 2024, "pdf_paths": ["report.pdf"],
                          "drive_files": {"report.pdf": entry}}
                with patch.object(ocr, "safe_repo_file", side_effect=FileNotFoundError), \
                     patch.object(ocr, "extract_native_pages", return_value=["Annual report " * 20]), \
                     patch.object(drive_store.DriveStore, "from_oauth", return_value=store):
                    result = ocr.process_document(record, "tesseract", dpi=300, pdftoppm="poppler", force=False,
                                                  ocr_all=False, output_root=root / "extracted", save_review_images=False)
            self.assertEqual(len(result["files"]), 1)
            output = json.loads((root / "extracted/FPT/2024/report.json").read_text(encoding="utf-8"))
            self.assertEqual(output["document"]["sha256"], entry["sha256"])
            audited = audit.audit_file(record, "report.pdf", root / "extracted")
            self.assertEqual(audited["source_sha256"], entry["sha256"])
            self.assertNotIn("MANIFEST_PDF_NOT_LOCAL", audited["warnings"])

    def test_collector_uploads_pdf_and_only_prunes_after_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf = root / "data/references/vietstock/annual_reports/files/FPT/2024/FPT_2024_1.pdf"
            pdf.parent.mkdir(parents=True)
            pdf.write_bytes(b"%PDF- sample")
            relative = pdf.relative_to(root).as_posix()
            document = {"symbol": "FPT", "year": 2024, "pdf_paths": [relative], "archive_path": relative}
            service = FakeService()
            store = drive_store.DriveStore(service, "folder123")
            with patch.object(collector, "ROOT", root), \
                 patch.object(drive_store, "MediaFileUpload", lambda filename, mimetype, resumable: type("Media", (), {"filename": filename})()), \
                 patch.object(drive_store, "MediaIoBaseDownload", FakeDownloader):
                collector.upload_document_pdfs(document, store)
                self.assertTrue(pdf.exists())
                collector.prune_verified_local(document)
            self.assertFalse(pdf.exists())
            self.assertIn(relative, document["drive_files"])

    def test_collector_keeps_pdf_on_upload_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf = root / "report.pdf"
            pdf.write_bytes(b"%PDF- sample")
            document = {"symbol": "FPT", "year": 2024, "pdf_paths": ["report.pdf"], "archive_path": "report.pdf"}

            class BrokenStore:
                def upload_pdf(self, *args):
                    raise RuntimeError("upload failed")

            with patch.object(collector, "ROOT", root), self.assertRaises(RuntimeError):
                collector.upload_document_pdfs(document, BrokenStore())
            self.assertTrue(pdf.exists())

    def test_prune_checks_both_local_copies_before_removing_either(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report_root = root / "data/references/vietstock/annual_reports"
            pdf = report_root / "files/FPT/2024/report.pdf"
            mirror = report_root / "files_pdf/FPT/2024/report.pdf"
            pdf.parent.mkdir(parents=True)
            mirror.parent.mkdir(parents=True)
            pdf.write_bytes(b"%PDF- verified")
            mirror.write_bytes(pdf.read_bytes())
            relative = pdf.relative_to(root).as_posix()
            document = {"pdf_paths": [relative], "drive_files": {
                relative: {"sha256": hashlib.sha256(pdf.read_bytes()).hexdigest()}}}
            with patch.object(collector, "ROOT", root):
                mirror.write_bytes(b"%PDF- changed")
                with self.assertRaises(ValueError):
                    collector.prune_verified_local(document)
                self.assertTrue(pdf.exists())
                self.assertTrue(mirror.exists())
                mirror.write_bytes(pdf.read_bytes())
                collector.prune_verified_local(document)
            self.assertFalse(pdf.exists())
            self.assertFalse(mirror.exists())

    def test_prune_rejects_archive_outside_report_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf = root / "data/references/vietstock/annual_reports/files/FPT/2024/report.pdf"
            pdf.parent.mkdir(parents=True)
            pdf.write_bytes(b"%PDF- sample")
            important = root / "important.py"
            important.write_text("keep me", encoding="utf-8")
            relative = pdf.relative_to(root).as_posix()
            document = {"pdf_paths": [relative], "archive_path": "important.py",
                        "drive_files": {relative: {"sha256": hashlib.sha256(pdf.read_bytes()).hexdigest()}}}
            with patch.object(collector, "ROOT", root), self.assertRaises(ValueError):
                collector.prune_verified_local(document)
            self.assertTrue(pdf.exists())
            self.assertTrue(important.exists())

    def test_fresh_download_keeps_matching_drive_metadata(self):
        entry = {"id": "remote", "sha256": "same"}
        old = {"symbol": "FPT", "year": 2024, "provider_file_id": "1", "file_url": "https://example.test/a",
               "status": "DOWNLOADED", "sha256": "same", "pdf_paths": ["report.pdf"],
               "drive_files": {"report.pdf": entry}}
        new = {"symbol": "FPT", "year": 2024, "provider_file_id": "1", "file_url": "https://example.test/a",
               "status": "DOWNLOADED", "sha256": "same", "pdf_paths": ["report.pdf"]}
        with tempfile.TemporaryDirectory() as directory, patch.object(collector, "MANIFEST_PATH", Path(directory) / "manifest.json"):
            collector.save_document({"documents": [old]}, new)
            saved = json.loads(collector.MANIFEST_PATH.read_text(encoding="utf-8"))["documents"][0]
        self.assertEqual(saved["drive_files"], {"report.pdf": entry})

    def test_crawl_prunes_existing_verified_drive_pdf(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files_root = root / "data/references/vietstock/annual_reports/files"
            pdf = files_root / "FPT/2024/FPT_2024_1.pdf"
            pdf.parent.mkdir(parents=True)
            pdf.write_bytes(b"%PDF- existing")
            relative = pdf.relative_to(root).as_posix()
            store = drive_store.DriveStore(FakeService(), "folder123")
            url = "https://static2.vietstock.vn/report.pdf"
            manifest_path = root / "manifest.json"

            class Client:
                def __init__(self, *, delay):
                    pass

                def bootstrap(self):
                    pass

                def report_years(self):
                    return [{"YearPeriod": 2024}]

                def reports_for(self, symbol, year):
                    return [{"Url": url, "FileInfoID": "1", "Title": "FPT"}]

            with patch.object(drive_store, "MediaFileUpload", lambda filename, mimetype, resumable: type("Media", (), {"filename": filename})()), \
                 patch.object(drive_store, "MediaIoBaseDownload", FakeDownloader):
                entry = store.upload_pdf(pdf, "FPT", 2024)
                old = {"symbol": "FPT", "year": 2024, "provider_file_id": "1", "file_url": url,
                       "status": "DOWNLOADED", "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
                       "pdf_paths": [relative], "archive_path": relative, "drive_files": {relative: entry}}
                manifest_path.write_text(json.dumps({"documents": [old]}), encoding="utf-8")
                args = Namespace(symbols="FPT", years="2024", download=True, delay=0, force=False,
                                 drive_upload=True, drive_folder_id="folder123", drive_prune_local=True)
                with patch.object(collector, "ROOT", root), patch.object(collector, "FILES_ROOT", files_root), \
                     patch.object(collector, "MANIFEST_PATH", manifest_path), \
                     patch.object(collector, "VietstockAnnualClient", Client), \
                     patch.object(collector.DriveStore, "from_oauth", return_value=store):
                    self.assertEqual(collector.catalog_and_download(args), 0)
            self.assertFalse(pdf.exists())

    def test_resolve_pdf_uses_local_before_drive(self):
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / "report.pdf"
            pdf.write_bytes(b"%PDF- local")
            record = {"drive_files": {"reports/report.pdf": {"id": "remote"}}}
            with drive_store.resolve_pdf(record, "reports/report.pdf", lambda _: pdf,
                                         lambda: self.fail("Drive should not be used")) as result:
                self.assertEqual(result, pdf)

    def test_resolve_pdf_downloads_when_local_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / "report.pdf"
            pdf.write_bytes(b"%PDF- remote")
            record = {"drive_files": {"reports/report.pdf": {"id": "remote"}}}

            class Store:
                @contextmanager
                def temporary_pdf(self, entry, filename):
                    self_entry = entry
                    assert self_entry["id"] == "remote" and filename == "report.pdf"
                    yield pdf

            with drive_store.resolve_pdf(record, "reports/report.pdf", lambda _: (_ for _ in ()).throw(FileNotFoundError()), Store) as result:
                self.assertEqual(result, pdf)

    def test_upload_verifies_file_and_temporary_pdf_is_removed(self):
        service = FakeService()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf = root / "report.pdf"
            pdf.write_bytes(b"%PDF- sample")
            store = drive_store.DriveStore(service, "folder123")
            with patch.object(drive_store, "MediaFileUpload", lambda filename, mimetype, resumable: type("Media", (), {"filename": filename})()), \
                 patch.object(drive_store, "MediaIoBaseDownload", FakeDownloader):
                entry = store.upload_pdf(pdf, "FPT", 2024)
                self.assertEqual(entry["sha256"], hashlib.sha256(pdf.read_bytes()).hexdigest())
                self.assertEqual(entry["size_bytes"], pdf.stat().st_size)
                pdf.unlink()
                with store.temporary_pdf(entry, "report.pdf", temp_root=root) as restored:
                    self.assertEqual(restored.read_bytes(), b"%PDF- sample")
                    self.assertTrue(restored.is_file())
                self.assertFalse(restored.exists())

    def test_download_rejects_corrupt_remote_copy(self):
        service = FakeService()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf = root / "report.pdf"
            pdf.write_bytes(b"%PDF- original")
            store = drive_store.DriveStore(service, "folder123")
            with patch.object(drive_store, "MediaFileUpload", lambda filename, mimetype, resumable: type("Media", (), {"filename": filename})()), \
                 patch.object(drive_store, "MediaIoBaseDownload", FakeDownloader):
                entry = store.upload_pdf(pdf, "FPT", 2024)
                service.file_api.items[entry["id"]]["bytes"] = b"%PDF- changed"
                with self.assertRaises(ValueError):
                    with store.temporary_pdf(entry, "report.pdf", temp_root=root):
                        pass
                self.assertEqual(list(root.glob("finmind-drive-*")), [])


class FakeDownloader:
    def __init__(self, stream, request):
        self.stream = stream
        self.request = request

    def next_chunk(self):
        self.stream.write(self.request.data)
        return None, True


if __name__ == "__main__":
    unittest.main()
