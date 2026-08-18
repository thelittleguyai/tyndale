"""Every message kind the thread bridge writes must exist in the MessageKind Literal.

The bug this pins (2026-08-18): the bridge had written `attest_request` entries since CS1,
but MessageKind didn't know the kind — and the FIRST time a thread actually contained one
(the e2e identity fix made the attest gate fire), GET /v1/conversations/{id} 500'd on a
pydantic ValidationError. The kind was invisible until the state it belongs to was
reachable. Source-scan (the RENDER_PATH_KEYS pattern): a new bridge-written kind that
isn't in the Literal fails HERE, before any thread can reach the state that would 500.
"""

from __future__ import annotations

import pathlib
import re
from typing import get_args

from app.schemas.chat import MessageKind, MessageOut

_BRIDGE = pathlib.Path(__file__).resolve().parents[1] / "app" / "agents" / "thread_bridge.py"

# The shapes a kind literal appears in inside the bridge:
#   kind="x"                        (_post/_insert keyword form)
#   _insert(session, conv, "x", …)  (positional form)
#   ensure("key", "x", …)  /  await ensure(\n "key",\n "x", …   (the ensure callback)
_KIND_PATTERNS = (
    re.compile(r'kind="([a-z_]+)"'),
    re.compile(r'_insert\(\s*session,\s*conv,\s*"([a-z_]+)"'),
    re.compile(r'ensure\(\s*"[^"]+",\s*"([a-z_]+)"'),
)


def _bridge_written_kinds() -> set[str]:
    src = _BRIDGE.read_text()
    found: set[str] = set()
    for rx in _KIND_PATTERNS:
        found.update(rx.findall(src))
    return found


def test_every_bridge_written_kind_is_in_the_message_kind_literal():
    kinds = _bridge_written_kinds()
    # Sanity: the scan actually sees the bridge (an empty set would vacuously pass).
    assert {"system_message", "moment_card", "attest_request"} <= kinds, (
        f"scan lost the bridge's kinds — patterns need updating (saw: {sorted(kinds)})"
    )
    missing = kinds - set(get_args(MessageKind))
    assert not missing, (
        f"bridge writes kinds the API cannot serialize (the attest_request 500 class): {missing}"
    )


def test_attest_request_serializes_through_message_out():
    """The exact 2026-08-18 regression: a MessageOut with the attest kind must validate."""
    import datetime
    import uuid

    out = MessageOut(
        message_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        sequence_number=3,
        role="system",
        kind="attest_request",
        payload={"relationships": ["spouse_partner"], "patient_name_as_extracted": "M. O."},
        content="Before we go on — whose bill is this?",
        content_chunks=None,
        tool_calls=None,
        citations=None,
        confidence_overall=None,
        status="complete",
        created_at=datetime.datetime.now(datetime.timezone.utc),
        updated_at=datetime.datetime.now(datetime.timezone.utc),
    )
    assert out.kind == "attest_request"
