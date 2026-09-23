"""Re-parse assistant messages persisted with raw control lines — e2e re-test 2026-09-23, item 5.

Before 2ac1e47 the server honoured a control line only as the message's last line, bare; the
model put ``SUGGESTED: [...]`` above the disclaimer footer and wrapped ``CTA: create_case`` in a
code fence, and those messages were persisted with the raw syntax in them. The app now strips
them at render (apps/mobile/lib/control-lines.ts); this migration fixes the rows themselves,
once, so every other reader (the admin transcript, exports, the model's own history) sees clean
text too:

  * every control line is removed from ``content`` and from each ``content_chunks[].text``;
  * the chips a SUGGESTED line named fill ``suggested_replies`` when the row has none;
  * a ``CTA: create_case`` line becomes the ``create_case_cta`` citation when the row lacks it.

The parse is a FROZEN copy of app/agents/chat_format.py as of this migration (a migration must
not import app code that can move); runtime/tests/test_control_line_backfill.py holds it to the
shared case file. Idempotent — a row without a control line is not touched. Downgrade is a
no-op: the stripped lines were never meant to render.
"""

from __future__ import annotations

import json
import re

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None

MAX_SUGGESTED = 4
MAX_SUGGESTED_WORDS = 5
KNOWN_CTAS = {"create_case"}
CREATE_CASE_CTA = {"action_type": "create_case_cta", "title": "Create a case"}

_DECORATED_LINE_RE = re.compile(
    r"^\s*(?:`{1,3}\s*\w*\s*)?(?:\*\*)?\s*(SUGGESTED|CTA)\s*:\s*(.*?)\s*(?:\*\*)?\s*`{0,3}\s*\.?\s*$",
    re.IGNORECASE,
)
_FENCE_RE = re.compile(r"^\s*`{3,}\s*\w*\s*$")
_CONTROL_TOKEN_RE = re.compile(r"(?im)^\W{0,8}(SUGGESTED|CTA)\s*:")


def _clean_reply(value):
    if not isinstance(value, str):
        return None
    s = " ".join(value.split())
    if not s or len(s.split()) > MAX_SUGGESTED_WORDS or len(s) > 60:
        return None
    return s


def _parse_suggested(raw: str):
    raw = raw.strip().strip("`").strip()
    try:
        parsed = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(parsed, list):
        return None
    replies: list[str] = []
    for item in parsed:
        cleaned = _clean_reply(item)
        if cleaned and cleaned not in replies:
            replies.append(cleaned)
        if len(replies) >= MAX_SUGGESTED:
            break
    return replies


def _tidy(lines: list[str]) -> str:
    out: list[str] = []
    i = 0
    while i < len(lines):
        if _FENCE_RE.match(lines[i]):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and _FENCE_RE.match(lines[j]):
                i = j + 1
                continue
        out.append(lines[i])
        i += 1
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def sanitize(text: str | None) -> tuple[str | None, list[str], str | None, bool]:
    """(clean_text, replies, cta, changed) — extract_directives, then the scrub's net."""
    if not text or not _CONTROL_TOKEN_RE.search(text):
        return text, [], None, False
    kept: list[str] = []
    replies: list[str] = []
    cta = None
    for line in text.splitlines():
        m = _DECORATED_LINE_RE.match(line)
        if m:
            kind, payload = m.group(1).upper(), m.group(2)
            if kind == "SUGGESTED":
                found = _parse_suggested(payload)
                if found is not None:
                    replies = found
            else:
                name = payload.strip().strip("`").strip().rstrip(".").lower()
                if name in KNOWN_CTAS:
                    cta = name
            continue
        if _CONTROL_TOKEN_RE.match(line):
            continue
        kept.append(line)
    return _tidy(kept), replies, cta, True


def backfill(conn) -> int:
    """Re-parse every affected assistant message. Returns the number of rows rewritten."""
    rows = conn.execute(
        sa.text(
            "SELECT message_id, content, content_chunks, citations, suggested_replies FROM messages "
            "WHERE role = 'assistant' AND ("
            "  content ~* '(^|\\n)\\W{0,8}(SUGGESTED|CTA)\\s*:' "
            "  OR content_chunks::text ~* '(SUGGESTED|CTA)\\s*:'"
            ")"
        ).columns(
            sa.column("message_id", postgresql.UUID(as_uuid=True)),
            sa.column("content", sa.Text()),
            sa.column("content_chunks", postgresql.JSONB()),
            sa.column("citations", postgresql.JSONB()),
            sa.column("suggested_replies", postgresql.JSONB()),
        )
    ).mappings().all()
    update = sa.text(
        "UPDATE messages SET content = :content, content_chunks = :chunks, citations = :citations, "
        "suggested_replies = :replies WHERE message_id = :message_id"
    ).bindparams(
        sa.bindparam("chunks", type_=postgresql.JSONB),
        sa.bindparam("citations", type_=postgresql.JSONB),
        sa.bindparam("replies", type_=postgresql.JSONB),
    )
    changed_rows = 0
    for row in rows:
        content, replies, cta, changed = sanitize(row["content"])
        chunks = row["content_chunks"]
        if isinstance(chunks, list):
            new_chunks = []
            for ch in chunks:
                if isinstance(ch, dict) and isinstance(ch.get("text"), str):
                    text, c_replies, c_cta, c_changed = sanitize(ch["text"])
                    if c_changed:
                        changed = True
                        ch = {**ch, "text": text}
                        replies = replies or c_replies
                        cta = cta or c_cta
                new_chunks.append(ch)
            chunks = new_chunks
        if not changed:
            continue
        citations = list(row["citations"] or [])
        if cta == "create_case" and not any(
            isinstance(c, dict) and c.get("action_type") == "create_case_cta" for c in citations
        ):
            citations.append(dict(CREATE_CASE_CTA))
        own = [r for r in (row["suggested_replies"] or []) if isinstance(r, str) and r.strip()]
        conn.execute(
            update,
            {
                "message_id": row["message_id"],
                "content": content,
                "chunks": chunks,
                "citations": citations,
                "replies": own or replies or None,
            },
        )
        changed_rows += 1
    return changed_rows


def upgrade() -> None:
    backfill(op.get_bind())


def downgrade() -> None:
    pass  # the stripped lines were never meant to render; nothing to restore
