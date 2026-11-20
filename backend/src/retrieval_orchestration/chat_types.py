"""Persistence-independent web chat limits and errors."""
from datetime import datetime, timezone
import uuid

MAX_BYTES = 2 * 1024 * 1024
MAX_MESSAGES = 2000
MAX_TEXT_LEN = 4000


class ChatError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status, self.message = status, message


def validate_uuid(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ChatError(422, f'{name} không hợp lệ.')
    normalized = value.strip().lower()
    try:
        if str(uuid.UUID(normalized)) != normalized: raise ValueError()
    except (ValueError, AttributeError):
        raise ChatError(422, f'{name} phải là chuỗi UUID chuẩn.') from None
    return normalized


def now_iso():
    return datetime.now(timezone.utc).isoformat()
