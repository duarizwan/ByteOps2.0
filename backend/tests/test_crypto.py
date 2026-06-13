"""EncryptedString round-trips and stays backward-compatible."""

import app.core.crypto as crypto
from app.core.crypto import _PREFIX, EncryptedString


def test_passthrough_when_no_key(monkeypatch):
    monkeypatch.setattr(crypto, "_fernet", lambda: None)
    col = EncryptedString()
    stored = col.process_bind_param("secret-token", None)
    assert stored == "secret-token"  # plaintext (legacy)
    assert col.process_result_value(stored, None) == "secret-token"


def test_encrypts_and_decrypts_with_key(monkeypatch):
    from cryptography.fernet import Fernet

    fernet = Fernet(Fernet.generate_key())
    monkeypatch.setattr(crypto, "_fernet", lambda: fernet)
    col = EncryptedString()

    stored = col.process_bind_param("secret-token", None)
    assert stored.startswith(_PREFIX)
    assert "secret-token" not in stored  # ciphertext, not plaintext
    assert col.process_result_value(stored, None) == "secret-token"


def test_legacy_plaintext_still_readable_with_key(monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setattr(crypto, "_fernet", lambda: Fernet(Fernet.generate_key()))
    col = EncryptedString()
    # A row written before encryption was enabled (no prefix) must read through.
    assert col.process_result_value("old-plaintext-token", None) == "old-plaintext-token"


def test_none_is_preserved(monkeypatch):
    monkeypatch.setattr(crypto, "_fernet", lambda: None)
    col = EncryptedString()
    assert col.process_bind_param(None, None) is None
    assert col.process_result_value(None, None) is None
