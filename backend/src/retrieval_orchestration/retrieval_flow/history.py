"""Validate local chat documents and rebuild fixture context from user text only."""
from __future__ import annotations

import copy
from datetime import date, datetime, timedelta, timezone
import json
import math
from pathlib import Path

from .conversation import ChatSession

MAX_BYTES = 2 * 1024 * 1024
MAX_MESSAGES = 2000
VIETNAM = timezone(timedelta(hours=7))


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not 1 <= len(value) <= 64:
        raise ValueError('Thời gian trong lịch sử không hợp lệ.')
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError()
        return parsed
    except (ValueError, OverflowError) as error:
        raise ValueError('Thời gian cần đúng ISO và có múi giờ.') from error


def _reference(value: object) -> date:
    try:
        if not isinstance(value, str) or len(value) != 10:
            raise ValueError()
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError()
        return parsed
    except ValueError as error:
        raise ValueError('Ngày tham chiếu trong lịch sử không hợp lệ.') from error


def _validate(history: object) -> dict:
    if not isinstance(history, dict) or history.get('schema_version') != '1.0':
        raise ValueError('Định dạng lịch sử chưa được hỗ trợ.')
    identity = history.get('session_id')
    if not isinstance(identity, str) or not identity.strip() or len(identity) > 128:
        raise ValueError('Mã phiên trong lịch sử không hợp lệ.')
    for name in ('started_at', 'saved_at'):
        _timestamp(history.get(name))
    rows = history.get('messages')
    if not isinstance(rows, list) or len(rows) > MAX_MESSAGES:
        raise ValueError('Lịch sử phải là danh sách tối đa 2000 tin nhắn.')
    if 'reference_date' in history:
        _reference(history['reference_date'])
    for row in rows:
        if (not isinstance(row, dict) or row.get('role') not in ('user', 'assistant')
                or not isinstance(row.get('content'), str) or len(row['content']) > 40000):
            raise ValueError('Một tin nhắn trong lịch sử không hợp lệ.')
        _timestamp(row.get('timestamp'))
        if 'reference_date' in row:
            _reference(row['reference_date'])
    return copy.deepcopy(history)


def _link(path: Path) -> bool:
    return path.is_symlink() or getattr(path, 'is_junction', lambda: False)()


def _safe_file(filename: str, directory: Path) -> Path:
    if (not isinstance(filename, str) or not filename or len(filename) > 255
            or not filename.lower().endswith('.json')
            or any(c in filename for c in ('/', '\\', ':'))
            or any(ord(c) < 32 for c in filename) or Path(filename).name != filename):
        raise ValueError('Chỉ mở tên file JSON nằm trong thư mục lịch sử.')
    root = Path(directory)
    candidate = root / filename
    if _link(root) or _link(candidate) or candidate.resolve().parent != root.resolve():
        raise ValueError('Không mở liên kết hoặc file ngoài thư mục lịch sử.')
    if not candidate.is_file():
        raise ValueError('Không tìm thấy file lịch sử này.')
    return candidate


def _unique_keys(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('JSON có trường bị trùng.')
        result[key] = value
    return result


def _bad_number(value: str) -> None:
    raise ValueError('JSON chứa giá trị số không hợp lệ.')


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError('JSON chứa giá trị số vượt phạm vi hỗ trợ.')
    return parsed


def load_history(filename: str, directory: Path) -> dict:
    target = _safe_file(filename, directory)
    with target.open('rb') as stream:
        payload = stream.read(MAX_BYTES + 1)
    if len(payload) > MAX_BYTES:
        raise ValueError('File lịch sử vượt quá 2 MiB.')
    try:
        decoded = json.loads(payload.decode('utf-8-sig'), object_pairs_hook=_unique_keys,
                             parse_constant=_bad_number, parse_float=_finite_float)
        return _validate(decoded)
    except (UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError('Không đọc được cấu trúc JSON của lịch sử.') from error


def list_histories(directory: Path) -> list[dict]:
    root = Path(directory)
    if _link(root):
        raise ValueError('Thư mục lịch sử không được là liên kết.')
    if not root.exists():
        return []
    descriptors = []
    for target in root.glob('*.json'):
        try:
            history = load_history(target.name, root)
        except (ValueError, OSError):
            continue
        users = [row for row in history['messages']
                 if row['role'] == 'user' and not row['content'].startswith('/')]
        preview = ''.join(c for c in users[0]['content'] if c.isprintable())[:80] if users else ''
        descriptors.append({'name': target.name, 'saved_at': history['saved_at'],
                            'session_id': history['session_id'], 'turns': len(users), 'preview': preview})
    return sorted(descriptors, key=lambda item: (-_timestamp(item['saved_at']).timestamp(), item['name']))


async def restore_session(history: dict, today: date | None = None) -> ChatSession:
    checked = _validate(history)
    current = today if today is not None else datetime.now(VIETNAM).date()
    if type(current) is not date:
        raise ValueError('Ngày hiện tại phải là ngày hợp lệ.')
    session = ChatSession(today=current)
    for row in checked['messages']:
        if row['role'] != 'user':
            continue
        text = row['content'].strip()
        if text.lower() == '/moi':
            session.reset()
        elif text and not text.startswith('/'):
            try:
                reference = (_reference(row['reference_date']) if 'reference_date' in row
                             else _timestamp(row['timestamp']).astimezone(VIETNAM).date())
            except OverflowError as error:
                raise ValueError('Ngày của lượt chat nằm ngoài phạm vi hỗ trợ.') from error
            session.today = reference
            await session.ask(text)
    session.today = current
    return session
