"""Discover and download Vietstock Finance annual-report PDFs.

Vietstock Finance currently loads its public annual-report table through the
same JSON endpoints used by its website. This is an adapter for that website
contract, not a documented/public partner API. Keep requests paced and retain
the source URLs and provider metadata in the manifest.

Examples (run from the repository root):
    python data_pipeline/annual_reports/vietstock_download_annual.py --catalog-only
    python data_pipeline/annual_reports/vietstock_download_annual.py --download
    python data_pipeline/annual_reports/vietstock_download_annual.py --symbols BID,VCB --years 2024,2025 --download
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import shutil
import subprocess
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


ROOT = Path(__file__).resolve().parents[2]
PAGE_URL = "https://finance.vietstock.vn/tai-lieu/bao-cao-thuong-nien.htm"
BASE_URL = "https://finance.vietstock.vn"
OUTPUT_ROOT = ROOT / "data" / "references" / "vietstock" / "annual_reports"
FILES_ROOT = OUTPUT_ROOT / "files"
MANIFEST_PATH = OUTPUT_ROOT / "manifest.json"
DEFAULT_SYMBOLS = ("VCB", "BID", "CTG", "MBB", "TCB", "FPT", "CMG", "ELC", "ITD", "ICT")
MAX_DOWNLOAD_BYTES = 200 * 1024 * 1024
MAX_ARCHIVE_BYTES = 500 * 1024 * 1024
ALLOWED_HOST_SUFFIXES = (".vietstock.vn",)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def safe_log(value: object, *, error: bool = False) -> None:
    text = str(value).encode("ascii", "backslashreplace").decode("ascii")
    stream = sys.stderr if error else sys.stdout
    try:
        stream.buffer.write(text.encode("ascii") + b"\n")
        stream.flush()
    except AttributeError:
        stream.write(text + "\n")
        stream.flush()


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=path.parent,
        prefix=f".{path.name}.", suffix=".tmp", delete=False,
    ) as stream:
        temporary = Path(stream.name)
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class TokenParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.token: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "input":
            return
        attributes = {key.casefold(): value for key, value in attrs}
        if attributes.get("name") == "__RequestVerificationToken":
            self.token = attributes.get("value")


class VietstockAnnualClient:
    """Small, rate-limited client for Vietstock Finance's annual-report page."""

    def __init__(self, *, timeout: float = 30, delay: float = 0.6) -> None:
        self.timeout = timeout
        self.delay = max(0.0, delay)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "FinMind annual-report collector/1.0",
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": PAGE_URL,
        })
        retry = Retry(
            total=4,
            connect=4,
            read=3,
            status=4,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "POST"}),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.token: str | None = None
        self.document_type_id: int | None = None

    def _pace(self) -> None:
        if self.delay:
            time.sleep(self.delay)

    def bootstrap(self) -> None:
        response = self.session.get(PAGE_URL, timeout=self.timeout)
        response.raise_for_status()
        parser = TokenParser()
        parser.feed(response.text)
        if not parser.token:
            raise RuntimeError("Vietstock page did not provide an anti-forgery token")
        self.token = parser.token

    def post(self, path: str, values: dict) -> object:
        if not self.token:
            self.bootstrap()
        self._pace()
        payload = dict(values)
        payload["__RequestVerificationToken"] = self.token
        response = self.session.post(
            f"{BASE_URL}{path}", data=payload, timeout=self.timeout
        )
        if response.status_code in (400, 403):
            # Tokens are session/page scoped; refresh once after an expired token.
            self.token = None
            self.bootstrap()
            payload["__RequestVerificationToken"] = self.token
            response = self.session.post(
                f"{BASE_URL}{path}", data=payload, timeout=self.timeout
            )
        response.raise_for_status()
        return response.json()

    def annual_report_type(self) -> int:
        if self.document_type_id is not None:
            return self.document_type_id
        data = self.post("/data/getrptdoctype", {})
        rows = data if isinstance(data, list) else []
        for row in rows:
            name = str(row.get("DocumentName", "")).strip().casefold()
            english = str(row.get("DocumentNameEN", "")).strip().casefold()
            if "thường niên" in name or "annual report" in english:
                self.document_type_id = int(row["DocumentTypeID"])
                return self.document_type_id
        raise RuntimeError("Vietstock did not return an annual-report document type")

    def report_years(self) -> list[dict]:
        document_type_id = self.annual_report_type()
        data = self.post("/data/getrptterm", {"documentTypeID": document_type_id, "top": 100})
        if not isinstance(data, list):
            raise RuntimeError("Unexpected Vietstock reporting-period response")
        return data

    def reports_for(self, symbol: str, year: int, *, page_size: int = 100) -> list[dict]:
        document_type_id = self.annual_report_type()
        request = {
            "stockCode": symbol.upper(),
            "documentTypeID": document_type_id,
            "reportTermID": 1,
            "yearPeriod": year,
            "exchangeID": 0,
            "orderBy": 2,
            "orderDir": 2,
            "page": 1,
            "pageSize": page_size,
        }
        rows: list[dict] = []
        while True:
            result = self.post("/data/getrptfile", request)
            page_rows = result if isinstance(result, list) else ([result] if isinstance(result, dict) and result else [])
            rows.extend(page_rows)
            total = max((int(row.get("TotalRow", 0) or 0) for row in page_rows), default=len(rows))
            if len(rows) >= total or len(page_rows) < page_size:
                break
            request["page"] += 1
        # The endpoint may repeat rows while paging; provider ID is stable.
        unique: dict[str, dict] = {}
        for row in rows:
            unique[str(row.get("FileInfoID") or row.get("Url"))] = row
        return list(unique.values())

    def download(self, url: str, target: Path) -> int:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not any(parsed.hostname and parsed.hostname.endswith(suffix) for suffix in ALLOWED_HOST_SUFFIXES):
            raise ValueError(f"Refusing non-Vietstock download URL: {url}")
        target.parent.mkdir(parents=True, exist_ok=True)
        self._pace()
        with self.session.get(url, timeout=self.timeout, stream=True, allow_redirects=True) as response:
            response.raise_for_status()
            final_host = urlparse(response.url).hostname or ""
            if not any(final_host.endswith(suffix) for suffix in ALLOWED_HOST_SUFFIXES):
                raise ValueError(f"Vietstock file redirected to an untrusted host: {final_host}")
            announced = int(response.headers.get("Content-Length", 0) or 0)
            if announced > MAX_DOWNLOAD_BYTES:
                raise ValueError(f"File exceeds {MAX_DOWNLOAD_BYTES} byte download limit")
            total = 0
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".download.", delete=False) as stream:
                temporary = Path(stream.name)
                try:
                    for block in response.iter_content(chunk_size=1024 * 128):
                        if not block:
                            continue
                        total += len(block)
                        if total > MAX_DOWNLOAD_BYTES:
                            raise ValueError(f"File exceeds {MAX_DOWNLOAD_BYTES} byte download limit")
                        stream.write(block)
                except Exception:
                    temporary.unlink(missing_ok=True)
                    raise
        if total == 0:
            temporary.unlink(missing_ok=True)
            raise ValueError("Downloaded file is empty")
        temporary.replace(target)
        return total


def safe_component(value: object, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "")).strip("._-")
    return cleaned[:120] or fallback


def allowed_file_url(value: object) -> str:
    url = html.unescape(str(value or "")).strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or not any(parsed.hostname.endswith(suffix) for suffix in ALLOWED_HOST_SUFFIXES):
        raise ValueError(f"Unexpected Vietstock document URL: {url!r}")
    # Vietstock's legacy report archive links use HTTP; request the same file over TLS.
    return parsed._replace(scheme="https").geturl()


def extract_zip_pdfs(archive_path: Path, target_dir: Path) -> list[str]:
    target_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[str] = []
    expanded_total = 0
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            member = PurePosixPath(info.filename.replace("\\", "/"))
            if member.is_absolute() or ".." in member.parts or not member.name:
                continue
            if info.is_dir() or member.suffix.casefold() != ".pdf":
                continue
            expanded_total += info.file_size
            if expanded_total > MAX_ARCHIVE_BYTES:
                raise ValueError(f"ZIP expands beyond {MAX_ARCHIVE_BYTES} byte limit")
            name = safe_component(member.name, "report.pdf")
            target = target_dir / name
            if target.exists() and target.stat().st_size == info.file_size:
                extracted.append(target.relative_to(ROOT).as_posix())
                continue
            with archive.open(info) as source, target.open("wb") as output:
                while block := source.read(1024 * 128):
                    output.write(block)
            with target.open("rb") as pdf:
                if not pdf.read(5).startswith(b"%PDF-"):
                    target.unlink(missing_ok=True)
                    continue
            extracted.append(target.relative_to(ROOT).as_posix())
    return extracted


def extract_rar_pdfs(archive_path: Path, target_dir: Path) -> list[str]:
    executable = shutil.which("7z") or shutil.which("7za")
    if not executable:
        raise RuntimeError("RAR report downloaded; install 7-Zip and rerun with --force to extract its PDFs")
    listing = subprocess.run([executable, "l", "-slt", str(archive_path)], check=False, capture_output=True, text=True)
    if listing.returncode:
        raise RuntimeError(f"Could not list RAR archive: {listing.stderr[-1000:]}")
    members = []
    for block in listing.stdout.split("\n\n"):
        match = re.search(r"(?m)^Path = (.+)$", block)
        if not match:
            continue
        name = match.group(1).strip().replace("\\", "/")
        member = PurePosixPath(name)
        if member.is_absolute() or ".." in member.parts or member.suffix.casefold() != ".pdf":
            continue
        members.append(name)
    target_dir.mkdir(parents=True, exist_ok=True)
    extracted = []
    for member in members:
        name = safe_component(PurePosixPath(member).name, "report.pdf")
        target = target_dir / name
        result = subprocess.run([executable, "e", "-so", str(archive_path), member], check=False, capture_output=True)
        if result.returncode or not result.stdout.startswith(b"%PDF-"):
            raise RuntimeError(f"7-Zip failed to extract PDF member {member!r}")
        if len(result.stdout) > MAX_ARCHIVE_BYTES:
            raise ValueError(f"RAR PDF member exceeds {MAX_ARCHIVE_BYTES} byte limit")
        target.write_bytes(result.stdout)
        extracted.append(target.relative_to(ROOT).as_posix())
    return extracted


def read_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        return {"schema_version": "1.0", "source": "VIETSTOCK_FINANCE", "documents": [], "updated_at": None}
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def save_document(manifest: dict, document: dict) -> None:
    key = (document.get("symbol"), document.get("year"), document.get("provider_file_id"))
    existing = manifest["documents"]
    for index, row in enumerate(existing):
        if (row.get("symbol"), row.get("year"), row.get("provider_file_id")) == key:
            updated = dict(document)
            if row.get("status") in ("DOWNLOADED", "DOWNLOADED_NON_PDF", "ARCHIVE_UNPACK_REQUIRED") and row.get("file_url") == document.get("file_url"):
                for field in ("status", "downloaded_at", "archive_path", "pdf_paths", "size_bytes", "sha256", "error"):
                    if row.get(field) is not None:
                        updated[field] = row[field]
            existing[index] = updated
            break
    else:
        existing.append(document)
    existing.sort(key=lambda row: (row.get("symbol", ""), row.get("year", 0), str(row.get("provider_file_id", ""))))
    manifest["updated_at"] = utc_now()
    atomic_json(MANIFEST_PATH, manifest)


def catalog_and_download(args: argparse.Namespace) -> int:
    symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
    if not symbols or any(not re.fullmatch(r"[A-Z0-9]{2,8}", symbol) for symbol in symbols):
        raise ValueError("--symbols must be a comma-separated list of valid ticker symbols")
    requested_years = args.years or (
        "2024,2025" if args.download else "2019,2020,2021,2022,2023,2024,2025"
    )
    years = {int(value.strip()) for value in requested_years.split(",") if value.strip()}
    if not years or any(year < 1990 or year > datetime.now().year for year in years):
        raise ValueError("--years must contain valid report years")

    client = VietstockAnnualClient(delay=args.delay)
    client.bootstrap()
    available = {int(row["YearPeriod"]): row for row in client.report_years() if row.get("YearPeriod") is not None}
    unavailable = sorted(years - set(available))
    if unavailable:
        print(f"[WARN] Vietstock period selector did not list year(s): {', '.join(map(str, unavailable))}")

    manifest = read_manifest()
    seen = downloaded = missing = failed = 0
    for symbol in symbols:
        for year in sorted(years, reverse=True):
            base = {
                "symbol": symbol,
                "year": year,
                "period_label": f"{year}-YEAR",
                "document_type": "annual_report",
                "source_page_url": PAGE_URL,
                "provider_file_id": None,
                "title": None,
                "file_url": None,
                "provider_updated_at": None,
                "downloaded_at": None,
                "archive_path": None,
                "pdf_paths": [],
                "status": "DISCOVERED",
                "error": None,
            }
            try:
                if year not in available:
                    base["status"] = "YEAR_NOT_LISTED"
                    save_document(manifest, base)
                    missing += 1
                    continue
                rows = client.reports_for(symbol, year)
                if not rows:
                    base["status"] = "NO_REPORT"
                    save_document(manifest, base)
                    missing += 1
                    print(f"[MISSING] {symbol} {year}")
                    continue
                for row in rows:
                    seen += 1
                    provider_url = html.unescape(str(row.get("Url") or "")).strip()
                    url = allowed_file_url(provider_url)
                    file_id = str(row.get("FileInfoID") or "unknown")
                    ext = Path(urlparse(url).path).suffix.casefold()
                    if ext not in (".pdf", ".zip", ".rar", ".doc", ".docx", ".xls", ".xlsx"):
                        provider_ext = str(row.get("FileExt") or "").strip().casefold()
                        ext = provider_ext if provider_ext in (".pdf", ".zip", ".rar", ".doc", ".docx", ".xls", ".xlsx") else ".bin"
                    name = safe_component(f"{symbol}_{year}_{file_id}{ext}", f"{symbol}_{year}_{file_id}.bin")
                    archive_path = FILES_ROOT / symbol / str(year) / name
                    document = {
                        **base,
                        "provider_file_id": file_id,
                        "title": str(row.get("Title") or row.get("FullName") or f"Báo cáo thường niên {year}").strip(),
                        "provider_file_url": provider_url,
                        "file_url": url,
                        "provider_updated_at": row.get("LastUpdate"),
                        "exchange": row.get("CatID"),
                        "company_name": row.get("CompanyName"),
                        "file_extension": ext,
                        "status": "CATALOGED",
                    }
                    if args.download:
                        old_doc = next((item for item in manifest["documents"] if
                                        item.get("symbol") == symbol and item.get("year") == year and
                                        str(item.get("provider_file_id")) == file_id), None)
                        can_reuse = (
                            archive_path.exists() and not args.force and old_doc and
                            old_doc.get("file_url") == url and old_doc.get("status") in (
                                "DOWNLOADED", "DOWNLOADED_NON_PDF", "ARCHIVE_UNPACK_REQUIRED"
                            )
                        )
                        if can_reuse:
                            byte_count = archive_path.stat().st_size
                            document["sha256"] = old_doc.get("sha256")
                        else:
                            byte_count = client.download(url, archive_path)
                            document["sha256"] = sha256_file(archive_path)
                        document["archive_path"] = archive_path.relative_to(ROOT).as_posix()
                        document["size_bytes"] = byte_count
                        if ext == ".zip":
                            if not zipfile.is_zipfile(archive_path):
                                archive_path.unlink(missing_ok=True)
                                raise ValueError("Provider URL did not return a valid ZIP archive")
                            document["pdf_paths"] = extract_zip_pdfs(archive_path, archive_path.parent / f"{file_id}_pdfs")
                            if not document["pdf_paths"]:
                                raise ValueError("Downloaded archive contains no valid PDF files")
                        elif ext == ".rar":
                            if not (shutil.which("7z") or shutil.which("7za")):
                                document["status"] = "ARCHIVE_UNPACK_REQUIRED"
                                document["archive_path"] = archive_path.relative_to(ROOT).as_posix()
                                document["sha256"] = document.get("sha256") or sha256_file(archive_path)
                                document["size_bytes"] = byte_count
                                document["downloaded_at"] = utc_now()
                                document["error"] = "Install 7-Zip to extract PDF files from this RAR archive."
                                save_document(manifest, document)
                                downloaded += 1
                                safe_log(f"[{document['status']}] {symbol} {year}")
                                continue
                            document["pdf_paths"] = extract_rar_pdfs(archive_path, archive_path.parent / f"{file_id}_pdfs")
                            if not document["pdf_paths"]:
                                raise ValueError("RAR archive contains no valid PDF files")
                        elif ext == ".pdf":
                            with archive_path.open("rb") as stream:
                                if not stream.read(5).startswith(b"%PDF-"):
                                    raise ValueError("Downloaded file does not have a PDF signature")
                            document["pdf_paths"] = [archive_path.relative_to(ROOT).as_posix()]
                        else:
                            document["status"] = "DOWNLOADED_NON_PDF"
                            document["downloaded_at"] = utc_now()
                            save_document(manifest, document)
                            downloaded += 1
                            safe_log(f"[{document['status']}] {symbol} {year} ({ext})")
                            continue
                        document["downloaded_at"] = utc_now()
                        document["status"] = "DOWNLOADED"
                        downloaded += 1
                    save_document(manifest, document)
                    safe_log(f"[{document['status']}] {symbol} {year}")
            except Exception as exc:
                base["status"] = "FAILED"
                base["error"] = f"{type(exc).__name__}: {exc}"
                save_document(manifest, base)
                failed += 1
                safe_log(f"[FAILED] {symbol} {year}: {type(exc).__name__}: {exc}", error=True)
    successful_periods = {
        (row.get("symbol"), int(row.get("year", 0))) for row in manifest["documents"]
        if row.get("status") not in ("FAILED", "NO_REPORT", "YEAR_NOT_LISTED")
    }
    manifest["documents"] = [
        row for row in manifest["documents"]
        if not (row.get("status") == "FAILED" and
                (row.get("symbol"), int(row.get("year", 0))) in successful_periods)
    ]
    catalog_symbols = sorted({str(row.get("symbol")) for row in manifest["documents"] if row.get("symbol")})
    catalog_years = sorted({int(row["year"]) for row in manifest["documents"] if row.get("year") is not None})
    manifest.pop("query", None)
    manifest["catalog_scope"] = {
        "symbols": catalog_symbols,
        "years": catalog_years,
        "periods": len({(row.get("symbol"), int(row["year"])) for row in manifest["documents"] if row.get("year") is not None}),
        "documents": len(manifest["documents"]),
        "checked_at": utc_now(),
        "page_url": PAGE_URL,
    }
    manifest["last_run"] = {
        "symbols": symbols,
        "years": sorted(years),
        "completed_at": utc_now(),
        "downloaded": bool(args.download),
        "page_url": PAGE_URL,
    }
    atomic_json(MANIFEST_PATH, manifest)
    safe_log(f"Done: records={seen}, downloaded={downloaded}, missing={missing}, failed={failed}")
    safe_log(f"Manifest: {MANIFEST_PATH.relative_to(ROOT).as_posix()}")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Catalog/download Vietstock annual-report documents.")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS), help="Comma-separated ticker symbols")
    parser.add_argument("--years", help="Comma-separated report years; defaults to 2019–2025 for catalog and 2024–2025 for download")
    parser.add_argument("--catalog-only", action="store_true", help="Save document URLs and metadata without downloading")
    parser.add_argument("--download", action="store_true", help="Download reported files (PDF or ZIP) and safely unpack PDFs")
    parser.add_argument("--force", action="store_true", help="Replace existing downloaded source files")
    parser.add_argument("--delay", type=float, default=0.6, help="Delay in seconds between provider requests")
    args = parser.parse_args()
    if args.catalog_only and args.download:
        parser.error("choose either --catalog-only or --download")
    if not args.catalog_only and not args.download:
        args.catalog_only = True
    try:
        return catalog_and_download(args)
    except (requests.RequestException, RuntimeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Vietstock annual-report collection failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
