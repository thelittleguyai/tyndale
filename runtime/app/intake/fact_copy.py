"""The guided confirmations cards say ONE plain sentence (e2e round 3 R4).

The intake's confirmations screen rendered the translate pass's whole paragraph per charge —
"coded at the second-highest of four standard visit levels, reflecting a visit that involved…" —
far above grade 5 and uncapped: the chat-first cap (315733d, apps/mobile/lib/line-item-copy.ts)
never reached it. The card now carries the code and one sentence of at most MAX_HEADLINE_CHARS;
the rest, and the translate pass's context line, go under "Show what this usually looks like".

The sentence is engine-generated, so it goes through the same grade-5 guard as the registry's
intake copy (reading_level: ≤ 5.9 Flesch–Kincaid, or the label rule under 7 words), and it must
fit MAX_CARD_CHARS. One that fails either is replaced by the registry's fallback line and moves,
whole, under the disclosure — the user still has every word the engine wrote, one tap away.

``split_translation`` is the Python twin of the app's ``splitTranslation``;
runtime/tests/fixtures/line_item_copy_cases.json holds both to the same cases.
"""

from __future__ import annotations

import re

from app.intake.reading_level import read

MAX_HEADLINE_CHARS = 90
# the card's hard ceiling: a sentence the clause cut could not bring under it (no boundary to
# cut at) is not shown as the card's line either — the fallback is, and it moves under the fold
MAX_CARD_CHARS = 110
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")


def split_translation(translation: str | None) -> tuple[str, str | None]:
    """(headline, rest): the first sentence — cut at the last clause boundary before the cap
    when that one sentence runs long — and everything after it."""
    text = " ".join((translation or "").split())
    if not text:
        return "", None
    sentences = _SENTENCE_BREAK.split(text)
    headline = sentences[0]
    rest = " ".join(sentences[1:]).strip()
    if len(headline) > MAX_HEADLINE_CHARS:
        # JS lastIndexOf(s, n) finds a match STARTING at or before n: search [0, n + len(s))
        cut = max(headline.rfind(sep, 0, MAX_HEADLINE_CHARS + len(sep)) for sep in (", ", " — ", "; "))
        if cut > 30:
            rest = " ".join(x for x in (headline[cut + 1 :].strip(), rest) if x)
            headline = headline[:cut].strip()
    return headline, rest or None


def fact_card(fact: dict, fallback: str) -> dict:
    """{text, more} for one confirmations card: the capped sentence (or ``fallback`` when the
    sentence fails the grade-5 guard) and the long text for the disclosure (None when there is
    none)."""
    full = fact.get("plain_language_translation") or fact.get("raw_description") or ""
    headline, rest = split_translation(full)
    if not headline or len(headline) > MAX_CARD_CHARS or not read(headline).passes():
        headline, rest = fallback, " ".join(full.split()) or None
    context = " ".join((fact.get("plain_language_context") or "").split()) or None
    more = "\n\n".join(x for x in (rest, context) if x) or None
    return {"text": headline, "more": more}
