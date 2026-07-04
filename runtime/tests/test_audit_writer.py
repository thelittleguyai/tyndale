"""Shared audit envelope (Phase 2.2): build_audit_event encrypts the payload when a key is
configured, decode_payload round-trips it, and the integrity hash is over clear-text. This is
the single helper every audit site (post/pre-tool-use, chat, admin, cron) now routes through,
so no site can silently bypass encryption."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import uuid

from app.config import get_settings
from app.routes.admin._deps import decode_payload
from app.security.audit_writer import build_audit_event


def _set_key(monkeypatch, key_bytes: bytes | None) -> None:
    s = get_settings()
    monkeypatch.setattr(
        s, "audit_log_enc_key", base64.b64encode(key_bytes).decode() if key_bytes else None
    )
    monkeypatch.setattr(s, "audit_log_key_version", 1)


def test_payload_encrypted_and_decode_roundtrips(monkeypatch):
    _set_key(monkeypatch, os.urandom(32))
    payload = {"action": "chat_turn", "member_email": "jane@example.com", "amount": 1200}
    ev = build_audit_event(
        event_type="model_call", actor=str(uuid.uuid4()), payload=payload, outcome="success"
    )
    # key_version reflects encryption; the stored bytes are NOT the clear-text JSON.
    assert ev.key_version == 1
    assert b"jane@example.com" not in bytes(ev.payload_encrypted)
    assert b"chat_turn" not in bytes(ev.payload_encrypted)
    # decode_payload decrypts back to the original dict.
    assert decode_payload(ev) == payload


def test_cleartext_when_no_key(monkeypatch):
    _set_key(monkeypatch, None)
    payload = {"action": "cron", "rows": 10}
    ev = build_audit_event(
        event_type="system_action", actor="cron:bulk", payload=payload, outcome="success"
    )
    assert ev.key_version == 0
    assert decode_payload(ev) == payload


def test_hash_is_over_cleartext_regardless_of_encryption(monkeypatch):
    payload = {"a": 1, "b": "x"}
    expected = hashlib.sha256(
        json.dumps(payload, default=str, sort_keys=True).encode("utf-8")
    ).digest()

    _set_key(monkeypatch, os.urandom(32))
    ev_enc = build_audit_event(
        event_type="system_action", actor="s", payload=payload, outcome="success"
    )
    _set_key(monkeypatch, None)
    ev_clear = build_audit_event(
        event_type="system_action", actor="s", payload=payload, outcome="success"
    )
    assert bytes(ev_enc.payload_hash) == expected
    assert bytes(ev_clear.payload_hash) == expected
