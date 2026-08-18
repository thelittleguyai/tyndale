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


def _grounded(code: str, haystack: str) -> bool:
    base = code.strip().upper().split("-", 1)[0]
    return len(base) < 4 or base in haystack


def structured_code_claims(*payloads: dict | None) -> set[str]:
    """Code-shaped values under code-named keys, anywhere in the finding's structured data."""
    claims: set[str] = set()

    def walk(node, key_hint: bool) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                hinted = key_hint or any(h in str(k).lower() for h in _CODE_KEY_HINTS)
                walk(v, hinted)
        elif isinstance(node, list):
            for v in node:
                walk(v, key_hint)
        elif key_hint and isinstance(node, (str, int)):
            s = str(node).strip().upper()
            if _CODE_SHAPE_RE.match(s):
                claims.add(s)

    for p in payloads:
        walk(p or {}, False)
    return claims


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

    claims = structured_code_claims(facts, legal_claim, recommendation)
    ungrounded_claims = sorted(c for c in claims if not _grounded(c, haystack))
    if ungrounded_claims:
        return GroundingVerdict("drop", dropped_codes=ungrounded_claims)

    has_real_grounding = any(_grounded(c, haystack) and len(c) >= 4 for c in claims) or bool(
        (facts or {}).get("line_item_id") or (facts or {}).get("line_item_refs")
    )

    scrubbed: dict[str, dict] = {}
    offenders: list[str] = []
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
                mentions = [m for m in prose_mentions(node) if not _grounded(m[2], haystack)]
                if not mentions:
                    return node
                offenders.extend(m[2] for m in mentions)
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


def summary_ungrounded_codes(text: str, haystack: str) -> list[str]:
    """Context-anchored codes in the LP summary that no document contains."""
    return sorted({m[2] for m in prose_mentions(text or "") if not _grounded(m[2], haystack)})


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
