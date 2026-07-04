"""AES-GCM encryption for audit-log payloads (Phase 4 / DL — HIPAA at rest).

The audit_events.payload_encrypted column holds either:

  * AES-256-GCM ciphertext, when ``AUDIT_LOG_ENC_KEY`` is set (Key Vault-backed
    env, base64 of 32 raw bytes). Stored layout is ``nonce(12) || ciphertext||tag``.
  * clear-text JSON bytes, in dev when no key is configured — a startup warning is
    logged once so this is never silently the case in a real deployment.

``key_version`` on the row records which key encrypted it, so a future key rotation
can decrypt historical rows. Version 0 is reserved for the legacy clear-text rows
written before this landed; the configured key writes ``audit_log_key_version``.

Readers call ``decrypt_payload`` which is backward-compatible: it transparently
returns clear-text bytes for key_version==0 rows (or when no key is configured),
so mixed old/new rows both decode.
"""

from __future__ import annotations

import base64
import os

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

_NONCE_BYTES = 12  # AES-GCM standard nonce length
# key_version marking a clear-text (unencrypted) legacy row.
CLEARTEXT_KEY_VERSION = 0


class AuditCryptoError(Exception):
    """Raised on a malformed key or an undecryptable ciphertext."""


def _load_key() -> bytes | None:
    """Return the 32-byte AES key from config, or None when unset. Raises
    AuditCryptoError if the configured value is not base64 of exactly 32 bytes."""
    settings = get_settings()
    raw = (settings.audit_log_enc_key or "").strip()
    if not raw:
        return None
    try:
        key = base64.b64decode(raw, validate=True)
    except Exception as exc:  # noqa: BLE001
        raise AuditCryptoError("AUDIT_LOG_ENC_KEY is not valid base64") from exc
    if len(key) != 32:
        raise AuditCryptoError(
            f"AUDIT_LOG_ENC_KEY must decode to 32 bytes (AES-256); got {len(key)}"
        )
    return key


def encryption_enabled() -> bool:
    """True when a usable audit encryption key is configured."""
    return _load_key() is not None


def configured_key_version() -> int:
    """The key_version to stamp on newly written rows: the configured version when a
    key is set, else the clear-text marker (0)."""
    if encryption_enabled():
        return int(get_settings().audit_log_key_version)
    return CLEARTEXT_KEY_VERSION


def warn_if_unencrypted() -> None:
    """Startup hook: warn (once) when audit encryption is not configured, so a dev
    default never silently ships to a real environment. Safe to call from lifespan."""
    if not encryption_enabled():
        log.warning(
            "audit_crypto.unencrypted",
            note="AUDIT_LOG_ENC_KEY unset — audit payloads stored as clear-text JSON "
            "(dev only). Configure a Key Vault-backed 32-byte base64 key in prod.",
        )


def encrypt_payload(plaintext: bytes) -> tuple[bytes, int]:
    """Encrypt ``plaintext`` for storage. Returns ``(stored_bytes, key_version)``.

    With a key configured: ``stored_bytes`` = ``nonce || ciphertext`` (AES-256-GCM,
    tag appended by the library), key_version = configured version.
    Without a key (dev): returns the plaintext unchanged with key_version 0."""
    key = _load_key()
    if key is None:
        return plaintext, CLEARTEXT_KEY_VERSION
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = os.urandom(_NONCE_BYTES)
    ct = AESGCM(key).encrypt(nonce, plaintext, None)
    return nonce + ct, int(get_settings().audit_log_key_version)


def decrypt_payload(stored: bytes, key_version: int) -> bytes:
    """Inverse of ``encrypt_payload``. Backward-compatible:

    * key_version == 0 → the row is clear-text; return the bytes unchanged.
    * key_version != 0 → AES-256-GCM decrypt with the configured key.

    Raises AuditCryptoError if a ciphertext row can't be decrypted (missing key or
    tampered data)."""
    if key_version == CLEARTEXT_KEY_VERSION:
        return bytes(stored)
    key = _load_key()
    if key is None:
        raise AuditCryptoError(
            f"row has key_version={key_version} (encrypted) but AUDIT_LOG_ENC_KEY is unset"
        )
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    blob = bytes(stored)
    if len(blob) <= _NONCE_BYTES:
        raise AuditCryptoError("ciphertext too short to contain a nonce")
    nonce, ct = blob[:_NONCE_BYTES], blob[_NONCE_BYTES:]
    try:
        return AESGCM(key).decrypt(nonce, ct, None)
    except InvalidTag as exc:
        raise AuditCryptoError("audit payload failed authentication (wrong key or tampered)") from exc
