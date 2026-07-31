"""Post-apply check that audit-log encryption is live (security-week item 1).

Read-only. Reports the newest audit_events row's key_version and, when AUDIT_LOG_ENC_KEY is
configured, decrypts it and verifies the SHA-256 integrity hash. Exit codes make it CI/exec
friendly:

  0 — newest row is encrypted and decrypts + hashes clean (or: no key configured AND the
      newest row is legacy clear-text — i.e. state is consistent)
  1 — INCONSISTENT: a key is configured but the newest row is clear-text (the envelope is
      being bypassed or the revision predates the key), or decryption/hash verification failed
  2 — no audit rows to check

Run inside the dev runtime container (the key env lives there, not on laptops):
  az containerapp exec --name tyndale-dev-runtime --resource-group tyndale-dev-rg \
    --command "python scripts/verify_audit_encryption.py"
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))  # runtime/ on the path

from sqlalchemy import func, select  # noqa: E402

from app.db.base import AsyncSessionLocal  # noqa: E402
from app.db.models.audit_events import AuditEvent  # noqa: E402
from app.security.audit_crypto import (  # noqa: E402
    CLEARTEXT_KEY_VERSION,
    decrypt_payload,
    encryption_enabled,
)


async def main() -> int:
    async with AsyncSessionLocal() as s:
        newest = (
            await s.execute(select(AuditEvent).order_by(AuditEvent.timestamp.desc()).limit(1))
        ).scalar_one_or_none()
        if newest is None:
            print("verify_audit_encryption: no audit rows yet (exit 2)")
            return 2
        counts = dict(
            (await s.execute(select(AuditEvent.key_version, func.count()).group_by(AuditEvent.key_version)))
            .tuples()
            .all()
        )

    key_set = encryption_enabled()
    encrypted = newest.key_version != CLEARTEXT_KEY_VERSION
    print(f"rows by key_version: {counts}  (0 = legacy clear-text)")
    print(
        f"newest row: id={newest.event_id} type={newest.event_type} at={newest.timestamp} "
        f"key_version={newest.key_version} encrypted={encrypted} key_configured={key_set}"
    )

    if not key_set:
        print("OK (dev-consistent): no key configured; rows are expected clear-text" if not encrypted
              else "OK: row encrypted, but no key here to decrypt-verify (run inside the runtime container)")
        return 0
    if not encrypted:
        print("FAIL: AUDIT_LOG_ENC_KEY is configured but the newest row is CLEAR-TEXT — "
              "either the revision predates the key (write one new audit event and re-run) "
              "or a write path bypasses the envelope")
        return 1
    try:
        plaintext = decrypt_payload(bytes(newest.payload_encrypted), newest.key_version)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: decryption error: {exc}")
        return 1
    if hashlib.sha256(plaintext).digest() != bytes(newest.payload_hash):
        print("FAIL: decrypted payload does not match its SHA-256 integrity hash")
        return 1
    keys = sorted(json.loads(plaintext).keys()) if plaintext.strip().startswith(b"{") else "<non-dict>"
    print(f"OK: newest audit row decrypts + hash-verifies (payload keys: {keys})")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
