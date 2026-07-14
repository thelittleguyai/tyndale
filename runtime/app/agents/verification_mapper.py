"""Free-text → verification-answer mapper (chat-first Phase B, D4b — DL-91).

Maps a user's free-text reply during encounter verification to the card(s) they addressed and the
answer they intended, so the UI can PRE-SELECT and ask for a confirming tap. It never writes state
— the tap does (the invariant lives in the caller). Two layers, same shape as the crisis
classifier: a precision-first DETERMINISTIC layer (ordinals, code/description refs, amounts,
universals, negations) that wins when it fires, then a Haiku call for the rest. Anything ambiguous,
partial, or low-confidence degrades to `mappable=False` so the caller shows the tap nudge — a
half-right pre-selection teaches distrust, so we never pre-select a subset silently.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

CONF_HIGH = 0.95
CONF_THRESHOLD = 0.7  # below this, no pre-selection


@dataclass
class Card:
    line_item_id: str
    ordinal: int  # 1-based position in the pending set
    code: str | None = None
    description: str | None = None
    amount: float | None = None


@dataclass
class Mapping:
    line_item_id: str
    intended_answer: str  # yes | no | unsure
    confidence: float


@dataclass
class MapperResult:
    mappings: list[Mapping] = field(default_factory=list)
    mappable: bool = False  # high-confidence + complete → pre-select
    partial: bool = False  # addressed more than we could confidently map → partial fallback
    method: str = "none"  # deterministic | haiku | none


# --- polarity + universal keyword sets (substring, lowercased) --------------
_UNSURE = ("not sure", "unsure", "don't know", "dont know", "no idea", "can't remember",
           "cant remember", "not certain", "i'm not sure", "im not sure")
_NO = ("didn't happen", "did not happen", "never happened", "not right", "isn't right",
       "is wrong", "are wrong", "was wrong", "were wrong", "wrong", "incorrect", "not mine",
       "not me", "didn't get", "did not get", "never got", "never had", "didn't have", "not real")
_YES = ("is right", "are right", "was right", "were right", "that's right", "thats right",
        "correct", "did happen", "happened", "accurate", "is fine", "are fine", "looks right",
        "that's mine", "thats mine", "yes", "right")

_UNIVERSAL_YES = ("all correct", "all right", "all of those are right", "all of them are right",
                  "all of these are right", "yes to all", "they're all right", "theyre all right",
                  "everything is right", "everything's right", "all happened", "those all happened",
                  "these all happened", "all good", "all of that is right", "that all happened",
                  "they all happened")
_UNIVERSAL_NO = ("none happened", "none of that happened", "none of those", "none of these",
                 "none of them", "all wrong", "all incorrect", "no to all", "everything is wrong",
                 "everything's wrong", "none of that is right", "none of it happened",
                 "none of that is mine")

_ORDINAL_WORDS = {
    "first": 1, "1st": 1, "one": 1, "second": 2, "2nd": 2, "two": 2, "third": 3, "3rd": 3,
    "three": 3, "fourth": 4, "4th": 4, "four": 4, "fifth": 5, "5th": 5, "last": -1,
}

_STOP = {"the", "and", "with", "your", "brain", "scan", "test", "visit", "you", "were", "for",
         "of", "a", "an", "both", "w/o", "w/"}


def _polarity(text: str) -> str | None:
    """yes | no | unsure | None for a clause (unsure wins, then no, then yes)."""
    t = text.lower()
    if any(k in t for k in _UNSURE):
        return "unsure"
    if any(k in t for k in _NO):
        return "no"
    if any(k in t for k in _YES):
        return "yes"
    return None


def _universal(text: str) -> str | None:
    t = text.lower()
    if any(k in t for k in _UNIVERSAL_NO):
        return "no"
    if any(k in t for k in _UNIVERSAL_YES):
        return "yes"
    return None


def _desc_tokens(description: str | None) -> list[str]:
    """Distinctive lowercase tokens from a card description (MRI, contrast, …) for keyword refs."""
    toks = re.findall(r"[a-z0-9]+", (description or "").lower())
    return [w for w in toks if len(w) >= 3 and w not in _STOP]


def _match_precise(text: str, card: Card) -> bool:
    """Unambiguous references: the CPT code or the dollar amount."""
    t = text.lower()
    if card.code and card.code.lower() in t:
        return True
    if card.amount is not None:
        amt = f"{card.amount:,.0f}"
        if amt in t or amt.replace(",", "") in t or f"{card.amount:,.2f}" in t:
            return True
    return False


def _match_desc(text: str, card: Card) -> bool:
    """A distinctive description word (MRI, contrast, …). Ambiguous by nature — only resolved when
    it identifies exactly one card (see _resolve)."""
    t = text.lower()
    return any(tok in t for tok in _desc_tokens(card.description))


def _ordinals_in(text: str, n_cards: int) -> list[int]:
    """1-based ordinals the utterance mentions (resolving 'last'), in mention order, deduped."""
    out: list[int] = []
    for m in re.findall(r"\b(first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th|last)\b", text.lower()):
        idx = _ORDINAL_WORDS[m]
        idx = n_cards if idx == -1 else idx
        if 1 <= idx <= n_cards and idx not in out:
            out.append(idx)
    return out


def _deterministic(utterance: str, cards: list[Card]) -> MapperResult | None:
    """Precision-first. Returns a result only when confident; None → defer to Haiku."""
    if not cards:
        return None
    u = utterance.strip()

    # 1. universals → every card, one answer.
    uni = _universal(u)
    if uni is not None:
        return MapperResult(
            mappings=[Mapping(c.line_item_id, uni, CONF_HIGH) for c in cards],
            mappable=True, method="deterministic",
        )

    # 2. compound "X … but not/except Y" → split polarity across the two sides.
    split = re.split(r"\bbut\b|\bexcept\b|\bhowever\b", u, maxsplit=1)
    if len(split) == 2:
        left, right = split
        lp, rp = _polarity(left), _polarity(right)
        # "…right but not the second" → the right side often only carries "not" → flip the left.
        if rp is None and lp is not None and re.search(r"\bnot\b|n't\b", right.lower()):
            rp = "no" if lp == "yes" else "yes"
        if lp and rp:
            by_id: dict[str, Mapping] = {}
            for side_text, pol in ((left, lp), (right, rp)):
                for c in _resolve(side_text, cards):
                    by_id[c.line_item_id] = Mapping(c.line_item_id, pol, CONF_HIGH)
            if by_id:
                addressed = len(_ordinals_in(u, len(cards))) or len(by_id)
                return _finalize(list(by_id.values()), addressed, "deterministic")

    # 3. single polarity over the referents the utterance names.
    pol = _polarity(u)
    referents = _resolve(u, cards)
    if pol is not None and referents:
        # A conjunction implies ≥2 referents; if we resolved fewer, the utterance addressed
        # something we couldn't place → defer rather than silently pre-select a subset.
        if " and " in u.lower() and len(referents) < 2:
            return None
        addressed = _addressed_count(u, cards)
        maps = [Mapping(c.line_item_id, pol, CONF_HIGH) for c in referents]
        return _finalize(maps, addressed, "deterministic")

    # nothing confident — let Haiku try (or fall back).
    return None


def _resolve(text: str, cards: list[Card]) -> list[Card]:
    """The cards the text names. Precise refs (ordinal / code / amount) resolve directly; a
    description keyword resolves ONLY when it uniquely identifies one not-yet-named card (an
    ambiguous keyword like 'MRI' across two MRI lines is left unresolved → the caller defers)."""
    n = len(cards)
    by_ord = {c.ordinal: c for c in cards}
    out: list[Card] = []
    for idx in _ordinals_in(text, n):
        if by_ord.get(idx) and by_ord[idx] not in out:
            out.append(by_ord[idx])
    for c in cards:
        if c not in out and _match_precise(text, c):
            out.append(c)
    desc = [c for c in cards if c not in out and _match_desc(text, c)]
    if len(desc) == 1:  # unambiguous description reference
        out.append(desc[0])
    return out


def _addressed_count(utterance: str, cards: list[Card]) -> int:
    """A conservative count of distinct things the utterance seems to address, to detect a partial
    mapping (mentioned more than we resolved)."""
    ords = len(_ordinals_in(utterance, len(cards)))
    codes = len(re.findall(r"\b\d{4,5}\b", utterance))  # CPT-shaped tokens
    amounts = len(re.findall(r"\$\s?\d", utterance))
    return max(ords, codes, amounts, 1)


def _finalize(mappings: list[Mapping], addressed: int, method: str) -> MapperResult:
    """Apply the confidence + completeness policy: all-high AND not partial → mappable."""
    mappings = [m for m in mappings if m.confidence >= CONF_THRESHOLD]
    if not mappings:
        return MapperResult(mappable=False, partial=False, method=method)
    partial = addressed > len(mappings)
    return MapperResult(
        mappings=mappings, mappable=not partial, partial=partial, method=method
    )


# --- Haiku layer (mirrors crisis_classifier) --------------------------------
def _haiku_enabled() -> bool:
    settings = get_settings()
    if not getattr(settings, "use_real_claude", False):
        return False
    from app.agents.runner import has_real_anthropic_creds

    return has_real_anthropic_creds(settings) or bool(settings.litellm_proxy_url)


_HAIKU_SYSTEM = (
    "You map a patient's free-text reply during medical-bill verification to the line items they "
    "addressed and the answer they intend. Answer ONLY with a compact JSON object: "
    '{"mappings":[{"n":<1-based item number>,"answer":"yes|no|unsure","confidence":0..1}],'
    '"addressed":<how many distinct items they seemed to address>}. '
    "yes = the charge is right / it happened; no = it did not happen / is wrong; unsure = they are "
    "not sure. Only include an item when you are confident. If you cannot tell, return an empty "
    "mappings list."
)


async def _haiku(utterance: str, cards: list[Card]) -> MapperResult:
    from app.agents.runner import _client

    settings = get_settings()
    listing = "\n".join(
        f"{c.ordinal}. {c.description or ''} (code {c.code or '—'}, ${c.amount or 0:,.2f})"
        for c in cards
    )
    try:
        resp = await asyncio.wait_for(
            _client().messages.create(
                model=settings.resolved_model(settings.claude_default_model_haiku),
                max_tokens=250,
                system=_HAIKU_SYSTEM,
                messages=[{"role": "user", "content": f"Items:\n{listing}\n\nReply: {utterance}"}],
            ),
            timeout=6.0,
        )
        import json

        text = "".join(
            getattr(b, "text", "") for b in resp.content if getattr(b, "type", None) == "text"
        )
        data = json.loads(re.search(r"\{.*\}", text, re.DOTALL).group(0))
        by_ord = {c.ordinal: c for c in cards}
        maps = [
            Mapping(by_ord[m["n"]].line_item_id, m["answer"], float(m.get("confidence", 0)))
            for m in data.get("mappings", [])
            if m.get("n") in by_ord and m.get("answer") in {"yes", "no", "unsure"}
        ]
        addressed = int(data.get("addressed", len(maps)) or len(maps))
        return _finalize(maps, addressed, "haiku")
    except Exception as exc:  # noqa: BLE001 — the mapper must never break the chat turn
        log.warning("verification_mapper.haiku_fallback", error=str(exc))
        return MapperResult(mappable=False, method="none")


async def map_verification(utterance: str, cards: list[Card]) -> MapperResult:
    """Map a free-text verification reply. Deterministic layer wins; else Haiku; else nudge."""
    det = _deterministic(utterance, cards)
    if det is not None:
        return det
    if not _haiku_enabled():
        return MapperResult(mappable=False, method="none")
    return await _haiku(utterance, cards)


_ORDINAL_NAME = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth"}
_ANSWER_PHRASE = {"yes": "correct", "no": "didn't happen", "unsure": "not sure"}


def summarize_mappings(mappings: list[Mapping], cards: list[Card]) -> str:
    """A plain phrase of what was mapped, for the confirm prompt's {{summary}} slot."""
    by_id = {c.line_item_id: c for c in cards}
    if len(mappings) == len(cards) and len({m.intended_answer for m in mappings}) == 1:
        return f"all of them as '{_ANSWER_PHRASE[mappings[0].intended_answer]}'"
    parts: list[str] = []
    for m in mappings:
        c = by_id.get(m.line_item_id)
        name = _ORDINAL_NAME.get(c.ordinal, f"#{c.ordinal}") if c else "that"
        parts.append(f"the {name} charge as '{_ANSWER_PHRASE[m.intended_answer]}'")
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]
