"""Gemini API keys added from the admin page, encrypted at rest in the local admin database.

Security rules this module enforces:
  * A key is write-only: no function returns it except `active_keys()` for the key pool and
    `secret()` for a connectivity test, and nothing here logs, prints or stores it in clear text.
  * Everything the admin page can see is a label, the last 4 characters and a state.
  * Encryption needs a dedicated secret (GEMINI_KEYS_SECRET). The JWT secret is deliberately not
    reused: its default value is public in the source code.
"""
from __future__ import annotations

import base64
import hashlib
import re
import time
import uuid
from typing import Callable, List, Optional, Tuple

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from ...documents.research_metrics import ResearchMetrics, utc_now

MIN_SECRET_LENGTH = 16
MAX_KEYS = 20
# Google issues two shapes: the classic "AIza..." and the newer "AQ.xxxx" keys (note the dot).
KEY_FORMAT = re.compile(r'^(?:AIza[0-9A-Za-z_\-]{30,60}|AQ\.[0-9A-Za-z_.\-]{30,100})$')
LABEL_FORMAT = re.compile(r'^[^\x00-\x1f\x7f]{1,60}$')


def fingerprint(key: str) -> str:
    """Stable, non-reversible identity of a key (high-entropy input), used to refuse duplicates."""
    return hashlib.sha256(key.encode('utf-8')).hexdigest()


def _cipher(secret: str) -> Fernet:
    material = HKDF(algorithm=hashes.SHA256(), length=32, salt=b'finmind-gemini-keys-v1', info=b'fernet').derive(secret.encode('utf-8'))
    return Fernet(base64.urlsafe_b64encode(material))


def validate_key(key) -> str:
    if not isinstance(key, str) or not KEY_FORMAT.fullmatch(key.strip()):
        raise ValueError('KEY_FORMAT_INVALID')
    return key.strip()


class KeyStore:
    def __init__(self, root, secret: Optional[str]):
        self.metrics = ResearchMetrics(root)
        self._cipher = _cipher(secret) if isinstance(secret, str) and len(secret) >= MIN_SECRET_LENGTH else None
        with self.metrics.connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS gemini_keys(
                id TEXT PRIMARY KEY,label TEXT NOT NULL,secret_enc TEXT NOT NULL,fingerprint TEXT NOT NULL UNIQUE,
                last4 TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,verified INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,actor TEXT NOT NULL)''')

    @property
    def usable(self) -> bool:
        """False when no encryption secret is configured: keys cannot be added or read."""
        return self._cipher is not None

    def _need_cipher(self):
        if self._cipher is None:
            raise ValueError('KEY_STORE_DISABLED')

    def add(self, label, key, actor, *, verified=False, extra_fingerprints=()):
        self._need_cipher()
        key = validate_key(key)
        if not isinstance(label, str) or not LABEL_FORMAT.fullmatch(label.strip()):
            raise ValueError('KEY_LABEL_INVALID')
        digest = fingerprint(key)
        if digest in extra_fingerprints:
            raise ValueError('KEY_DUPLICATE')
        ident = str(uuid.uuid4())
        with self.metrics.connect() as conn:
            if conn.execute('SELECT count(*) FROM gemini_keys').fetchone()[0] >= MAX_KEYS:
                raise ValueError('KEY_LIMIT_REACHED')
            if conn.execute('SELECT 1 FROM gemini_keys WHERE fingerprint=?', (digest,)).fetchone():
                raise ValueError('KEY_DUPLICATE')
            conn.execute('INSERT INTO gemini_keys VALUES(?,?,?,?,?,?,?,?,?)',
                         (ident, label.strip(), self._cipher.encrypt(key.encode('utf-8')).decode('ascii'), digest,
                          key[-4:], 1, int(bool(verified)), utc_now(), str(actor)))
        return self._item(ident)

    def _item(self, ident):
        return next((i for i in self.list() if i['id'] == ident), None)

    def list(self) -> List[dict]:
        """What the admin page may see. `readable` is False when the secret changed and the key can no longer be decrypted."""
        with self.metrics.connect() as conn:
            rows = conn.execute('SELECT * FROM gemini_keys ORDER BY created_at,id').fetchall()
        return [{'id': r['id'], 'label': r['label'], 'last4': r['last4'], 'enabled': bool(r['enabled']),
                 'verified': bool(r['verified']), 'created_at': r['created_at'], 'actor': r['actor'],
                 'readable': self._decrypt(r['secret_enc']) is not None} for r in rows]

    def _decrypt(self, token) -> Optional[str]:
        if self._cipher is None:
            return None
        try:
            return self._cipher.decrypt(token.encode('ascii')).decode('utf-8')
        except (InvalidToken, ValueError):
            return None

    def secret(self, ident) -> Optional[str]:
        """The clear key, only for a connectivity test inside the backend. Never send it anywhere else."""
        with self.metrics.connect() as conn:
            row = conn.execute('SELECT secret_enc FROM gemini_keys WHERE id=?', (ident,)).fetchone()
        return self._decrypt(row['secret_enc']) if row else None

    def set_enabled(self, ident, enabled):
        with self.metrics.connect() as conn:
            done = conn.execute('UPDATE gemini_keys SET enabled=? WHERE id=?', (int(bool(enabled)), ident)).rowcount
        if not done:
            raise ValueError('KEY_NOT_FOUND')
        return self._item(ident)

    def mark_verified(self, ident, verified=True):
        with self.metrics.connect() as conn:
            conn.execute('UPDATE gemini_keys SET verified=? WHERE id=?', (int(bool(verified)), ident))

    def delete(self, ident):
        with self.metrics.connect() as conn:
            row = conn.execute('SELECT label FROM gemini_keys WHERE id=?', (ident,)).fetchone()
            if not row:
                raise ValueError('KEY_NOT_FOUND')
            conn.execute('DELETE FROM gemini_keys WHERE id=?', (ident,))
        return row['label']

    def fingerprints(self):
        with self.metrics.connect() as conn:
            return {r[0] for r in conn.execute('SELECT fingerprint FROM gemini_keys')}

    def active_keys(self) -> Tuple[List[str], List[dict]]:
        """Decrypted enabled keys with their metadata, for the key pool only."""
        if self._cipher is None:
            return [], []
        with self.metrics.connect() as conn:
            rows = conn.execute('SELECT * FROM gemini_keys WHERE enabled=1 ORDER BY created_at,id').fetchall()
        keys, meta = [], []
        for row in rows:
            key = self._decrypt(row['secret_enc'])
            if key:
                keys.append(key)
                meta.append({'label': row['label'], 'source': 'web', 'id': row['id']})
        return keys, meta


class CachedKeys:
    """Callable for the provider: env keys first, then the enabled web keys, re-read at most every `ttl` seconds."""

    def __init__(self, env_keys, store: Optional[KeyStore], ttl: float = 5.0, clock: Callable[[], float] = time.monotonic):
        self.env_keys, self.store, self.ttl, self.clock = list(env_keys), store, ttl, clock
        self._value, self._at = None, None

    def __call__(self):
        now = self.clock()
        if self._at is None or now - self._at >= self.ttl:
            store_keys, store_meta = self.store.active_keys() if self.store else ([], [])
            keys = self.env_keys + [k for k in store_keys if k not in self.env_keys]
            meta = [{'label': None, 'source': 'env', 'id': None}] * len(self.env_keys) + \
                   [m for k, m in zip(store_keys, store_meta) if k not in self.env_keys]
            self._value, self._at = (keys, meta), now
        return self._value

    def refresh(self):
        """Forget the cache so the next request sees keys added or removed a moment ago."""
        self._at = None


_ACTIVE_SOURCE: Optional[CachedKeys] = None


def set_key_source(source: Optional[CachedKeys]) -> None:
    global _ACTIVE_SOURCE
    _ACTIVE_SOURCE = source


def refresh_active_source() -> None:
    """Make the running chat pick up a key change on its next request."""
    if _ACTIVE_SOURCE is not None:
        _ACTIVE_SOURCE.refresh()
