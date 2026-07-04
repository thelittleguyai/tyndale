"""AES-GCM audit-log encryption round-trip (security spine).

No DB needed — exercises app.security.audit_crypto directly with a monkeypatched
key on the Settings singleton.
"""

from __future__ import annotations

import base64
import json
import os

import pytest

from app.config import get_settings
from app.security.audit_crypto import (
    AuditCryptoError,
    CLEARTEXT_KEY_VERSION,
    decrypt_payload,
    encrypt_payload,
    encryption_enabled,
)


def _set_key(monkeypatch, key_bytes: bytes | None) -> None:
    s = get_settings()
    monkeypatch.setattr(
        s, "audit_log_enc_key", base64.b64encode(key_bytes).decode() if key_bytes else None
    )
    monkeypatch.setattr(s, "audit_log_key_version", 1)


def test_encrypt_decrypt_roundtrip(monkeypatch):
    _set_key(monkeypatch, os.urandom(32))
    payload = json.dumps({"actor": "x", "tool": "y", "amount": 560}).encode("utf-8")

    stored, key_version = encrypt_payload(payload)
    assert key_version == 1
    assert stored != payload  # ciphertext, not plaintext
    assert len(stored) > len(payload)  # nonce + tag overhead

    assert decrypt_payload(stored, key_version) == payload
    assert encryption_enabled() is True


def test_cleartext_passthrough_when_no_key(monkeypatch):
    _set_key(monkeypatch, None)
    payload = b'{"clear": true}'

    stored, key_version = encrypt_payload(payload)
    assert key_version == CLEARTEXT_KEY_VERSION
    assert stored == payload  # unchanged in dev (no key)
    assert decrypt_payload(stored, key_version) == payload
    assert encryption_enabled() is False


def test_version_0_rows_decode_even_with_key_set(monkeypatch):
    # Backward-compat: a legacy clear-text (key_version 0) row still decodes when a
    # key is later configured.
    _set_key(monkeypatch, os.urandom(32))
    legacy = b'{"legacy": "cleartext"}'
    assert decrypt_payload(legacy, CLEARTEXT_KEY_VERSION) == legacy


def test_tampered_ciphertext_raises(monkeypatch):
    _set_key(monkeypatch, os.urandom(32))
    stored, key_version = encrypt_payload(b"sensitive")
    tampered = stored[:-1] + bytes([stored[-1] ^ 0x01])
    with pytest.raises(AuditCryptoError):
        decrypt_payload(tampered, key_version)


def test_encrypted_row_without_key_raises(monkeypatch):
    # A row stamped as encrypted but no key available → loud failure, not silent.
    _set_key(monkeypatch, os.urandom(32))
    stored, key_version = encrypt_payload(b"data")
    _set_key(monkeypatch, None)  # key removed
    with pytest.raises(AuditCryptoError):
        decrypt_payload(stored, key_version)


def test_bad_key_length_raises(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "audit_log_enc_key", base64.b64encode(os.urandom(16)).decode())
    with pytest.raises(AuditCryptoError):
        encrypt_payload(b"x")
