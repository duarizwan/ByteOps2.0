"""Transparent encryption-at-rest for sensitive string columns (OAuth tokens).

Backward-compatible by design:
  - When no TOKEN_ENCRYPTION_KEY is configured, values pass through as plaintext
    (identical to legacy behavior — nothing breaks).
  - On read, only values carrying the `enc::` prefix are decrypted, so any
    pre-existing plaintext rows keep working and migrate lazily on next write.
"""

from __future__ import annotations

import logging

from sqlalchemy.types import Text, TypeDecorator

logger = logging.getLogger(__name__)

_PREFIX = "enc::"


def _fernet():
    """Return a Fernet instance if a valid key is configured, else None."""
    from app.core.config import get_settings

    key = get_settings().token_encryption_key
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet

        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as exc:  # noqa: BLE001 - bad key must not crash the app
        logger.warning("Invalid TOKEN_ENCRYPTION_KEY; storing tokens in plaintext: %s", exc)
        return None


class EncryptedString(TypeDecorator):
    """A Text column that transparently encrypts its value with Fernet."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):  # write path
        if value is None:
            return None
        fernet = _fernet()
        if fernet is None:
            return value  # no key → plaintext (legacy)
        return _PREFIX + fernet.encrypt(value.encode()).decode()

    def process_result_value(self, value, dialect):  # read path
        if value is None:
            return None
        if not value.startswith(_PREFIX):
            return value  # legacy plaintext row
        fernet = _fernet()
        if fernet is None:
            logger.error("Encrypted token found but no TOKEN_ENCRYPTION_KEY configured.")
            return value
        try:
            return fernet.decrypt(value[len(_PREFIX):].encode()).decode()
        except Exception as exc:  # noqa: BLE001
            logger.error("Token decryption failed: %s", exc)
            return value
