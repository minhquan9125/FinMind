"""Web chat session JSON persistence per UUID owner with revisions and atomic writes."""
from __future__ import annotations

from contextlib import contextmanager
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import asyncio
import uuid

from .retrieval_flow.conversation import ChatSession, render_response
from .retrieval_flow.history import VIETNAM, _timestamp, load_history, restore_session

MAX_BYTES = 2 * 1024 * 1024
MAX_MESSAGES = 2000
MAX_TEXT_LEN = 4000
LOCK_TIMEOUT_SECONDS = 5.0
LOCK_RETRY_INTERVAL_SECONDS = 0.05


class ChatError(Exception):
    """Domain chat error with HTTP-equivalent status code."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def _validate_uuid(val: str, name: str) -> str:
    if not isinstance(val, str) or not val.strip():
        raise ChatError(422, f"{name} không hợp lệ.")
    val_str = val.strip().lower()
    try:
        parsed = uuid.UUID(val_str)
        if str(parsed) != val_str:
            raise ValueError()
        return val_str
    except (ValueError, AttributeError):
        raise ChatError(422, f"{name} phải là chuỗi UUID chuẩn.")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_link(path: Path) -> bool:
    return path.is_symlink() or getattr(path, "is_junction", lambda: False)()


class SessionStore:
    """Persists web chat sessions per owner UUID in JSON files."""

    def __init__(self, root: Path, *, engine=None) -> None:
        self.root = Path(root)
        self.engine = engine

    def _live_summary(self, doc):
        from .live_research import METRIC_ALIASES
        scope = doc.get('metadata', {}).get('live_context', {})
        if not scope:
            return 'Nhập mã công ty, kỳ và chỉ tiêu hoặc chủ đề tin tức cần tra cứu.'
        return ' | '.join(filter(None, (
            'Công ty: ' + ', '.join(scope.get('companies', [])) if scope.get('companies') else '',
            'Kỳ: ' + ', '.join(scope.get('periods', [])) if scope.get('periods') else '',
            'Chỉ tiêu: ' + METRIC_ALIASES.get(scope['metric_code'], (scope['metric_code'],))[0] if scope.get('metric_code') else '',
            'Nguồn: ' + scope['source_type'] if scope.get('source_type') else '',
        )))

    async def _summary(self, doc):
        if doc.get('metadata', {}).get('execution_mode') == 'LIVE':
            return self._live_summary(doc)
        return (await restore_session(doc)).context_summary()

    def _check_root_safe(self) -> None:
        if any(_is_link(path) for path in (self.root, *self.root.parents)):
            raise ChatError(503, "Thư mục lưu trữ không hợp lệ.")

    def _resolve_owner_dir(self, owner: str) -> Path:
        self._check_root_safe()
        owner_id = _validate_uuid(owner, "Owner ID")
        owner_dir = self.root / owner_id
        if _is_link(owner_dir):
            raise ChatError(503, "Thư mục người dùng không hợp lệ.")
        try:
            owner_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ChatError(503, "Không thể tạo thư mục người dùng.") from exc
        if _is_link(owner_dir):
            raise ChatError(503, "Thư mục người dùng không hợp lệ.")
        return owner_dir

    def _resolve_session_path(self, owner: str, session_id: str, must_exist: bool = True) -> Path:
        session_uuid = _validate_uuid(session_id, "Session ID")
        owner_dir = self._resolve_owner_dir(owner)
        target = owner_dir / f"{session_uuid}.json"
        if _is_link(target):
            raise ChatError(404, "Phiên không tồn tại.")
        try:
            target_resolved = target.resolve()
            owner_resolved = owner_dir.resolve()
            if target_resolved.parent != owner_resolved:
                raise ChatError(404, "Phiên không tồn tại.")
        except OSError:
            raise ChatError(404, "Phiên không tồn tại.")
        if must_exist and not target.is_file():
            raise ChatError(404, "Phiên không tồn tại.")
        return target

    @contextmanager
    def _exclusive_lock(self, target_path: Path):
        lock_path = target_path.with_suffix(".lock")
        acquired = False
        fd = -1
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
            acquired = True
        except FileExistsError as exc:
            raise ChatError(409, "Phiên đang được xử lý. Vui lòng thử lại.") from exc
        except OSError as exc:
            raise ChatError(503, "Không thể khóa tài nguyên ghi.") from exc
        try:
            yield
        finally:
            if acquired:
                try:
                    os.close(fd)
                except OSError:
                    pass
                try:
                    lock_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def _atomic_write_json(self, target_path: Path, doc: dict) -> None:
        serialized = json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8")
        if len(serialized) > MAX_BYTES:
            raise ChatError(422, "Kích thước phiên vượt quá 2 MiB.")
        tmp_path = target_path.with_suffix(f".tmp.{uuid.uuid4().hex}")
        try:
            with open(tmp_path, "xb") as fp:
                fp.write(serialized)
                fp.flush()
                os.fsync(fp.fileno())
            tmp_path.replace(target_path)
        except ChatError:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise
        except OSError as exc:
            if tmp_path.exists():
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise ChatError(503, "Lỗi hệ thống khi ghi dữ liệu phiên.") from exc

    def _load_raw_doc(self, target: Path) -> dict:
        try:
            doc = load_history(target.name, target.parent)
            if (doc['session_id'] != target.stem or doc.get('owner') != target.parent.name
                    or type(doc.get('revision')) is not int or doc['revision'] < 0):
                raise ValueError('Invalid stored identity or revision')
            return doc
        except ValueError as exc:
            raise ChatError(503, "Dữ liệu phiên không hợp lệ.") from exc
        except OSError as exc:
            raise ChatError(503, "Không thể đọc dữ liệu phiên.") from exc

    async def create(self, owner: str) -> dict:
        owner_id = _validate_uuid(owner, "Owner ID")
        session_id = str(uuid.uuid4())
        target_path = self._resolve_session_path(owner_id, session_id, must_exist=False)
        now = _now_iso()
        doc = {
            "schema_version": "1.0",
            "session_id": session_id,
            "owner": owner_id,
            "revision": 0,
            "started_at": now,
            "saved_at": now,
            "messages": [],
            "metadata": {"execution_mode": "LIVE" if self.engine else "FIXTURE"},
        }
        with self._exclusive_lock(target_path):
            self._atomic_write_json(target_path, doc)
        return {
            "session_id": session_id,
            "revision": 0,
            "messages": [],
            "context": await self._summary(doc),
            "execution_mode": doc['metadata']['execution_mode'],
        }

    async def list(self, owner: str) -> list[dict]:
        owner_dir = self._resolve_owner_dir(owner)
        items: list[dict] = []
        for file_path in owner_dir.glob("*.json"):
            if _is_link(file_path):
                continue
            try:
                doc = self._load_raw_doc(file_path)
            except (ChatError, ValueError, OSError):
                continue
            user_msgs = [
                m for m in doc.get("messages", [])
                if m.get("role") == "user" and not m.get("content", "").startswith("/")
            ]
            preview = ""
            if user_msgs:
                preview = "".join(c for c in user_msgs[0]["content"] if c.isprintable())[:80]
            items.append({
                "session_id": doc.get("session_id", file_path.stem),
                "preview": preview,
                "saved_at": doc.get("saved_at", ""),
                "turns": len(user_msgs),
            })
        def _sort_key(item: dict) -> tuple[float, str]:
            try:
                t = _timestamp(item["saved_at"]).timestamp()
            except Exception:
                t = 0.0
            return (-t, item["session_id"])
        return sorted(items, key=_sort_key)

    async def get(self, owner: str, session_id: str) -> dict:
        target = self._resolve_session_path(owner, session_id, must_exist=True)
        doc = self._load_raw_doc(target)
        return {
            "session_id": doc["session_id"],
            "revision": doc.get("revision", 0),
            "messages": doc.get("messages", []),
            "context": await self._summary(doc),
            "execution_mode": doc.get('metadata', {}).get('execution_mode', 'FIXTURE'),
        }

    async def send(self, owner: str, session_id: str, text: str, revision: int) -> dict:
        if not isinstance(text, str):
            raise ChatError(422, "Nội dung tin nhắn phải là chuỗi ký tự.")
        cleaned_text = text.strip()
        if not (1 <= len(cleaned_text) <= MAX_TEXT_LEN):
            raise ChatError(422, f"Tin nhắn phải có độ dài từ 1 đến {MAX_TEXT_LEN} ký tự sau khi loại bỏ khoảng trắng.")
        if type(revision) is not int or revision < 0:
            raise ChatError(422, "Revision phải là số nguyên không âm.")

        target = self._resolve_session_path(owner, session_id, must_exist=True)
        with self._exclusive_lock(target):
            doc = self._load_raw_doc(target)
            current_rev = doc.get("revision", 0)
            if current_rev != revision:
                raise ChatError(409, f"Xung đột revision (hiện tại: {current_rev}, yêu cầu: {revision}).")
            if len(doc.get("messages", [])) + 2 > MAX_MESSAGES:
                raise ChatError(422, f"Số lượng tin nhắn vượt quá giới hạn {MAX_MESSAGES}.")

            try:
                if self.engine is not None:
                    from .live_research import render_live_response
                    live_context = doc.get('metadata', {}).get('live_context', {})
                    previous_result = None
                    for message in reversed(doc.get('messages', [])):
                        if message.get('role') == 'user' and message.get('content', '').strip().lower() in ('/moi', '/new'):
                            break
                        candidate = message.get('result') or {}
                        if ((candidate.get('answering') or {}).get('status') == 'DRAFT_READY'
                                or (candidate.get('scope', {}).get('source_type') == 'NEWS'
                                    and (candidate.get('evidence_pack') or {}).get('schema_version') == '1.2')):
                            previous_result = candidate
                            break
                    chat_response = await asyncio.wait_for(
                        self.engine.answer(cleaned_text, doc['session_id'], live_context, previous_result=previous_result),
                        self.engine.retrieval_timeout + self.engine.limits.read_timeout_seconds + 5,
                    )
                    content = render_live_response(chat_response)
                else:
                    reconstructed = await restore_session(doc)
                    reconstructed.session_id = doc['session_id']
                    chat_response = await asyncio.wait_for(reconstructed.ask(cleaned_text), timeout=10)
                    content = render_response(chat_response)
            except (TimeoutError, OSError) as exc:
                raise ChatError(503, "Xử lý tạm thời không thành công. Vui lòng thử lại.") from exc

            now_dt = datetime.now(timezone.utc)
            now_str = now_dt.isoformat()
            now_ref = now_dt.astimezone(VIETNAM).date().isoformat()

            user_msg = {
                "role": "user",
                "content": cleaned_text,
                "timestamp": now_str,
                "reference_date": now_ref,
            }
            assistant_msg = {
                "role": "assistant",
                "content": content,
                "timestamp": now_str,
                "result": chat_response,
            }

            updated_doc = copy.deepcopy(doc)
            updated_doc["revision"] = current_rev + 1
            updated_doc["saved_at"] = now_str
            updated_doc.setdefault("messages", []).extend([user_msg, assistant_msg])
            if self.engine is not None:
                updated_doc.setdefault('metadata', {}).update(
                    execution_mode='LIVE', live_context=copy.deepcopy(chat_response['scope']))
            self._atomic_write_json(target, updated_doc)

            return {
                "session_id": updated_doc["session_id"],
                "revision": updated_doc["revision"],
                "messages": updated_doc["messages"],
                "context": await self._summary(updated_doc),
                "execution_mode": updated_doc.get('metadata', {}).get('execution_mode', 'FIXTURE'),
            }

    async def resume(self, owner: str, session_id: str) -> dict:
        target = self._resolve_session_path(owner, session_id, must_exist=True)
        source_doc = self._load_raw_doc(target)

        new_session_id = str(uuid.uuid4())
        new_target = self._resolve_session_path(owner, new_session_id, must_exist=False)
        now = _now_iso()

        new_doc = {
            "schema_version": "1.0",
            "session_id": new_session_id,
            "owner": _validate_uuid(owner, "Owner ID"),
            "revision": 0,
            "started_at": now,
            "saved_at": now,
            "messages": copy.deepcopy(source_doc.get("messages", [])),
            "metadata": {
                **copy.deepcopy(source_doc.get('metadata', {})),
                "parent_session_id": source_doc["session_id"]
            },
        }

        with self._exclusive_lock(new_target):
            self._atomic_write_json(new_target, new_doc)

        return {
            "session_id": new_session_id,
            "revision": 0,
            "messages": new_doc["messages"],
            "context": await self._summary(new_doc),
            "execution_mode": new_doc['metadata'].get('execution_mode', 'FIXTURE'),
        }
