"""Real-path chat citation/tier contract (Phase 3.1): [authority §sec, src_id] markers are
parsed, resolved against the session's retrieved chunks into citation objects, split into tiered
content_chunks, and ungrounded markers (src_id not retrieved) are stripped from the displayed
text — the Stop citation gate's 'degrade honestly' for the streaming path."""

from __future__ import annotations

from app.agents.chat import _chunks_and_citations


def test_resolves_grounded_and_strips_ungrounded():
    retrieved = [
        {
            "source_id": "src_abc123",
            "title": "ERISA",
            "url": "https://law/erisa",
            "chunk_text": "You have 180 days to appeal an adverse benefit determination.",
            "effective_date": "2024-01-01",
        }
    ]
    full = (
        "You have a right to appeal [ERISA §503, src_abc123].\n\n"
        "Also [MedicareManual §1, src_deadbeef] might apply here."
    )
    chunks, citations, unresolved = _chunks_and_citations(full, retrieved)

    # Grounded citation resolved into a full object.
    assert len(citations) == 1
    assert citations[0]["source_id"] == "src_abc123"
    assert citations[0]["title"] == "ERISA"
    assert citations[0]["url"] == "https://law/erisa"

    # Ungrounded marker stripped from the displayed text + flagged unresolved.
    joined = "\n\n".join(c["text"] for c in chunks)
    assert "src_deadbeef" not in joined
    assert unresolved and "src_deadbeef" in unresolved[0]
    # The grounded marker stays in the text so its card anchors.
    assert "src_abc123" in joined

    # Tier B for the paragraph carrying a citation; A for the (now citationless) other one.
    assert chunks[0]["tier"] == "B"
    assert chunks[0]["citations"][0]["source_id"] == "src_abc123"
    assert chunks[1]["tier"] == "A"
    assert chunks[1]["citations"] == []


def test_no_markers_yields_plain_tier_a():
    chunks, citations, unresolved = _chunks_and_citations("Just a plain factual answer.", [])
    assert citations == []
    assert unresolved == []
    assert len(chunks) == 1
    assert chunks[0]["tier"] == "A"


def test_empty_text():
    assert _chunks_and_citations("", []) == ([], [], [])
