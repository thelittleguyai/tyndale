"""Prose grounding — the finding/summary seam (2026-08-18, Phil's ruling).

The translate guard stops fabricated LINE ITEMS; this stops the same prompt-example bleed
one layer up, where it reaches AUDIT PROSE (a finding's narrative, the LP summary). Rules:

  * BASIS: a code the finding structurally depends on (code-named keys in facts /
    legal_claim / recommendation) that appears in NO document's stored OCR text → the
    finding DROPS. A claim built on a code the documents never contained is not a finding.
  * INCIDENTAL: a code mentioned only in prose while the finding stands on real, grounded
    structure → the reference is STRIPPED AT SPAN LEVEL — and only spans that strip
    cleanly (parenthesized references like "(70553)") qualify. An inline load-bearing
    mention ("billed CPT 70553 twice") cannot be removed without hand-editing agent text
    into Franken-prose, so per the ruling it is treated as basis and the finding drops.
  * Conviction rules carried from the translate guard: strong evidence only — no full
    document text stored → no conviction; sub-4-char tokens always keep; prose tokens
    count ONLY in explicit code contexts ("CPT 70553", "code: A9579", "(70553)") so a zip
    code or a dollar figure in prose can never convict a finding.

The canary codes (70553 / A9579 / 36000 — see intelligence-layer/prompts/README.md) are
the tripwire this exists for; tests use them exactly as the e2e harness does.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Prose mentions count only in explicit code contexts — never bare numbers. Code shapes:
# CPT = 5 digits; HCPCS = one letter + 4 digits (so `[A-Z]?\d{5}` would MISS every HCPCS).
_CODE_SHAPE = r"(?:[A-Z]\d{4}|\d{4,5})"
_CONTEXT_RE = re.compile(rf"(?i)\b(?:cpt|hcpcs|procedure code|code)\s*[:#]?\s*({_CODE_SHAPE})\b")
_PAREN_RE = re.compile(r"\(\s*([A-Z]\d{4}|\d{5})\s*\)")

# Structured keys that make a value a CODE CLAIM by construction (substring match).
_CODE_KEY_HINTS = ("code", "cpt", "hcpcs", "procedure")
_CODE_SHAPE_RE = re.compile(r"\A[A-Z]?\d{4,5}\Z")

# REFERENCE context (2026-08-18, the unbundled_panel false positive): a finding may cite a
# code that is DELIBERATELY absent from the documents — the panel code the components
# should have been billed as, the NCCI-correct code, the MUE comparison. Those are the
# finding's argument, not a claim about what the documents contain, so they are exempt
# from basis conviction. Key markers below flag reference context; recommendation and
# legal_claim payloads are reference context wholesale (they argue — the DOCUMENT claims
# live in facts). Residual accepted with eyes open: an agent could launder a fabricated
# code through a reference key; a wrong reference is a lesser harm than dropping every
# legitimate unbundling finding, and the recommendation text still passes the DL-47/PHI
# gates downstream.
_REFERENCE_KEY_MARKERS = (
    "correct", "should", "expected", "recommend", "instead", "bundl", "panel",
    "replace", "reference", "comparison",
)


def _grounded(code: str, haystack: str) -> bool:
    base = code.strip().upper().split("-", 1)[0]
    return len(base) < 4 or base in haystack


def structured_code_claims(
    facts: dict | None, legal_claim: dict | None = None, recommendation: dict | None = None
) -> tuple[set[str], set[str]]:
    """(presence_claims, reference_codes).

    Presence claims: code-shaped values under code-named keys in the FACTS tree with no
    reference marker on the path — the finding says the documents contain this code.
    Reference codes: code-shaped values under reference-marked keys anywhere, plus every
    code in legal_claim/recommendation — the finding cites them as its argument."""
    presence: set[str] = set()
    reference: set[str] = set()

    def walk(node, key_hint: bool, is_reference: bool) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                key = str(k).lower()
                hinted = key_hint or any(h in key for h in _CODE_KEY_HINTS)
                ref = is_reference or any(m in key for m in _REFERENCE_KEY_MARKERS)
                walk(v, hinted, ref)
        elif isinstance(node, list):
            for v in node:
                walk(v, key_hint, is_reference)
        elif key_hint and isinstance(node, (str, int)):
            s = str(node).strip().upper()
            if _CODE_SHAPE_RE.match(s):
                (reference if is_reference else presence).add(s)

    walk(facts or {}, False, False)
    walk(legal_claim or {}, False, True)
    walk(recommendation or {}, False, True)
    return presence, reference


def prose_mentions(text: str) -> list[tuple[int, int, str, bool]]:
    """(start, end, code, cleanly_strippable) for context-anchored code mentions.
    Parenthesized spans strip cleanly; inline context forms do not."""
    out: list[tuple[int, int, str, bool]] = []
    for m in _PAREN_RE.finditer(text):
        out.append((m.start(), m.end(), m.group(1).upper(), True))
    for m in _CONTEXT_RE.finditer(text):
        # Skip mentions already covered by a parenthesized span.
        if any(s <= m.start() and m.end() <= e for s, e, _, _ in out):
            continue
        out.append((m.start(), m.end(), m.group(1).upper(), False))
    return out


def strip_spans(text: str, spans: list[tuple[int, int]]) -> str:
    """Remove spans (already verified cleanly strippable) and tidy the whitespace left."""
    for start, end in sorted(spans, reverse=True):
        text = text[:start] + text[end:]
    return re.sub(r"[ \t]{2,}", " ", text).replace(" .", ".").replace(" ,", ",").strip()


@dataclass
class GroundingVerdict:
    action: str  # "keep" | "drop"
    dropped_codes: list[str] = field(default_factory=list)
    scrubbed: dict[str, dict] = field(default_factory=dict)  # field name -> cleaned payload


def ground_finding(
    facts: dict | None,
    legal_claim: dict | None,
    recommendation: dict | None,
    haystack: str,
) -> GroundingVerdict:
    """Apply drop-if-basis / scrub-if-incidental to one finding's payloads."""
    payloads = {"facts": facts, "legal_claim": legal_claim, "recommendation": recommendation}

    presence, reference = structured_code_claims(facts, legal_claim, recommendation)
    ungrounded_claims = sorted(c for c in presence if not _grounded(c, haystack))
    if ungrounded_claims:
        return GroundingVerdict("drop", dropped_codes=ungrounded_claims)

    has_real_grounding = any(_grounded(c, haystack) and len(c) >= 4 for c in presence) or bool(
        (facts or {}).get("line_item_id") or (facts or {}).get("line_item_refs")
    )
    # A code the finding cites as its ARGUMENT (the correct panel code, the NCCI reference)
    # is vouched: it may legitimately be absent from the documents, so its prose mentions
    # are never convicted or scrubbed.
    vouched = {c for c in reference}

    scrubbed: dict[str, dict] = {}
    for name, payload in payloads.items():
        if not payload:
            continue
        changed = False

        def clean(node):
            nonlocal changed
            if isinstance(node, dict):
                return {k: clean(v) for k, v in node.items()}
            if isinstance(node, list):
                return [clean(v) for v in node]
            if isinstance(node, str):
                mentions = [
                    m for m in prose_mentions(node)
                    if not _grounded(m[2], haystack) and m[2] not in vouched
                ]
                if not mentions:
                    return node
                if not has_real_grounding or any(not strippable for *_, strippable in mentions):
                    # No real grounding, or an inline load-bearing mention: basis treatment.
                    raise _Basis(sorted({m[2] for m in mentions}))
                changed = True
                return strip_spans(node, [(s, e) for s, e, _, _ in mentions])
            return node

        try:
            cleaned = clean(payload)
        except _Basis as b:
            return GroundingVerdict("drop", dropped_codes=b.codes)
        if changed:
            scrubbed[name] = cleaned

    return GroundingVerdict("keep", dropped_codes=[], scrubbed=scrubbed)


class _Basis(Exception):
    def __init__(self, codes: list[str]):
        self.codes = codes


def summary_ungrounded_codes(
    text: str, haystack: str, vouched: set[str] | frozenset[str] = frozenset()
) -> list[str]:
    """Context-anchored codes in the LP summary that no document contains — excluding codes
    the KEPT findings vouch for as their argument (the unbundling summary legitimately
    cites the correct panel code)."""
    return sorted({
        m[2] for m in prose_mentions(text or "")
        if not _grounded(m[2], haystack) and m[2] not in vouched
    })


def regeneration_instruction(codes: list[str]) -> str:
    """The §3.10-style inline correction for the ONE compose retry (engineering interim
    until Brock's grounding line lands in the skill itself)."""
    return (
        "GROUNDING CORRECTION: your previous summary referenced procedure code(s) "
        f"{', '.join(codes)} that appear in NONE of the user's documents. Codes that appear "
        "in skill examples are teaching material, never case data. Rewrite the summary "
        "citing only codes present in the documents — or describe the service without a "
        "code. Do not mention this correction."
    )
