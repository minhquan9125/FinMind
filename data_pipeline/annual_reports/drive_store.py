"""Store annual-report PDFs in a user-authorized Google Drive folder."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator


DEFAULT_FOLDER_ID = "1B-sy-qNIAJOJaQLYv84ezf5Zgp8EjTRA"
SCOPES = ["https://www.googleapis.com/auth/drive"]
MediaFileUpload = None
MediaIoBaseDownload = None


def hash_file(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _media_classes():
    if MediaFileUpload is not None and MediaIoBaseDownload is not None:
        return MediaFileUpload, MediaIoBaseDownload
    from googleapiclient.http import MediaFileUpload as Upload, MediaIoBaseDownload as Download
    return MediaFileUpload or Upload, MediaIoBaseDownload or Download


class DriveStore:
    def __init__(self, service, folder_id: str = DEFAULT_FOLDER_ID) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", folder_id):
            raise ValueError("Invalid Google Drive folder ID")
        self.service = service
        self.folder_id = folder_id
        self._folders: dict[tuple[str, str], str] = {}

    @classmethod
    def from_oauth(cls, folder_id: str = DEFAULT_FOLDER_ID) -> "DriveStore":
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise RuntimeError("Install google-api-python-client and google-auth-oauthlib first") from exc

        secret = os.environ.get("FINMIND_DRIVE_CLIENT_SECRET")
        if not secret or not Path(secret).is_file():
            raise RuntimeError("Set FINMIND_DRIVE_CLIENT_SECRET to your Google OAuth desktop client JSON path")
        token_path = Path(os.environ.get("FINMIND_DRIVE_TOKEN_FILE", Path(__file__).resolve().parents[2] / ".drive-token.json"))
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES) if token_path.is_file() else None
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                creds = InstalledAppFlow.from_client_secrets_file(secret, SCOPES).run_local_server(port=0)
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(creds.to_json(), encoding="utf-8")
        return cls(build("drive", "v3", credentials=creds, cache_discovery=False), folder_id)

    def upload_pdf(self, path: Path, symbol: str, year: int) -> dict:
        with path.open("rb") as stream:
            signature = stream.read(5)
        if path.suffix.casefold() != ".pdf" or signature != b"%PDF-":
            raise ValueError(f"Invalid PDF: {path}")
        name = f"{symbol}_{year}_{path.name}"
        parent_id = self.report_folder(symbol, year)
        upload_class, _ = _media_classes()
        media = upload_class(str(path), mimetype="application/pdf", resumable=True)
        created = self.service.files().create(
            body={"name": name, "parents": [parent_id], "mimeType": "application/pdf"},
            media_body=media, fields="id",
        ).execute()
        file_id = created["id"]
        remote = self.service.files().get(fileId=file_id, fields="id,name,size,md5Checksum,parents").execute()
        size = path.stat().st_size
        if (remote.get("name") != name or parent_id not in remote.get("parents", [])
                or int(remote.get("size", -1)) != size or remote.get("md5Checksum") != hash_file(path, "md5")):
            raise ValueError(f"Google Drive upload could not be verified: {name}")
        return {"id": file_id, "name": name, "size_bytes": size,
                "md5": remote["md5Checksum"], "sha256": hash_file(path, "sha256"),
                "parent_id": parent_id}

    def ensure_folder(self, name: str, parent_id: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,16}", name):
            raise ValueError(f"Invalid Drive folder name: {name!r}")
        key = (parent_id, name)
        if key in self._folders:
            return self._folders[key]
        query = (f"trashed = false and mimeType = 'application/vnd.google-apps.folder' "
                 f"and name = '{name}' and '{parent_id}' in parents")
        found = self.service.files().list(q=query, fields="nextPageToken,files(id,name,mimeType,parents)",
                                          pageSize=100).execute().get("files", [])
        if found:
            folder_id = found[0]["id"]
        else:
            folder_id = self.service.files().create(
                body={"name": name, "parents": [parent_id],
                      "mimeType": "application/vnd.google-apps.folder"}, fields="id",
            ).execute()["id"]
        self._folders[key] = folder_id
        return folder_id

    def report_folder(self, symbol: str, year: int) -> str:
        if not re.fullmatch(r"[A-Z0-9]{2,8}", symbol) or not 1990 <= int(year) <= 2100:
            raise ValueError("Invalid symbol or report year")
        ticker_id = self.ensure_folder(symbol, self.folder_id)
        return self.ensure_folder(str(year), ticker_id)

    def ensure_ticker_folders(self, symbols: list[str]) -> None:
        for symbol in symbols:
            if not re.fullmatch(r"[A-Z0-9]{2,8}", symbol):
                raise ValueError(f"Invalid ticker: {symbol!r}")
            self.ensure_folder(symbol, self.folder_id)

    def place_entry(self, entry: dict, symbol: str, year: int) -> dict:
        """Move an already verified flat PDF into its ticker/year folder."""
        remote = self.service.files().get(
            fileId=entry["id"], fields="id,name,size,md5Checksum,parents,mimeType",
        ).execute()
        if (remote.get("name") != entry.get("name")
                or remote.get("mimeType") != "application/pdf"
                or int(remote.get("size", -1)) != int(entry.get("size_bytes", -2))
                or not entry.get("md5") or remote.get("md5Checksum") != entry["md5"]):
            raise ValueError(f"Drive file cannot be verified before move: {entry.get('name')}")
        target_id = self.report_folder(symbol, year)
        parents = remote.get("parents", [])
        if target_id in parents:
            return {**entry, "parent_id": target_id}
        if self.folder_id not in parents:
            raise ValueError("Drive PDF is outside the configured source folder")
        self.service.files().update(fileId=entry["id"], addParents=target_id,
                                    removeParents=self.folder_id, fields="id,parents").execute()
        moved = {**entry, "parent_id": target_id}
        if not self.verify_entry(moved):
            raise ValueError(f"Drive file move could not be verified: {entry.get('name')}")
        return moved

    def verify_entry(self, entry: dict) -> bool:
        try:
            remote = self.service.files().get(fileId=entry["id"], fields="id,name,size,md5Checksum,parents").execute()
        except Exception:
            return False
        return (remote.get("name") == entry.get("name")
                and entry.get("parent_id", self.folder_id) in remote.get("parents", [])
                and int(remote.get("size", -1)) == int(entry.get("size_bytes", -2))
                and bool(entry.get("md5")) and remote.get("md5Checksum") == entry["md5"])

    @contextmanager
    def temporary_pdf(self, entry: dict, filename: str, *, temp_root: Path | None = None) -> Iterator[Path]:
        if Path(filename).name != filename or not filename.lower().endswith(".pdf"):
            raise ValueError("Unsafe PDF filename")
        _, download_class = _media_classes()
        with tempfile.TemporaryDirectory(prefix="finmind-drive-", dir=temp_root) as directory:
            target = Path(directory) / filename
            with target.open("wb") as stream:
                request = self.service.files().get_media(fileId=entry["id"])
                downloader = download_class(stream, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
            with target.open("rb") as stream:
                signature = stream.read(5)
            if (target.stat().st_size != int(entry["size_bytes"])
                    or hash_file(target, "sha256") != entry["sha256"]
                    or signature != b"%PDF-"):
                raise ValueError(f"Google Drive PDF differs from manifest: {filename}")
            yield target


@contextmanager
def resolve_pdf(record: dict, relative_pdf: str, local_resolver: Callable[[str], Path],
                store_factory: Callable[[], DriveStore] | None = None) -> Iterator[Path]:
    """Use the local PDF if present, otherwise fetch a verified temporary copy."""
    try:
        local = local_resolver(relative_pdf)
    except FileNotFoundError:
        entry = (record.get("drive_files") or {}).get(relative_pdf)
        if not entry:
            raise
        with (store_factory or DriveStore.from_oauth)().temporary_pdf(entry, Path(relative_pdf).name) as pdf:
            yield pdf
    else:
        yield local
