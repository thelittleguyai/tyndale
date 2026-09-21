"""The payer-instructions corpus (doc 40 §A5) — "Help me find it", from the insurer's own site.

Keyed by (payer_id × document_type × screen_id). Phase 1 ships the GENERIC fallback for every
(document_type × screen) — authored as registry keys, so it is drift-guarded and graded like all
other copy — and the loader + validator that payer-specific entries will arrive through
(``intelligence-layer/reference/payer_instructions/*.json``, from
``portal_navigation_guide_2026-07-02.md`` when it lands; same receiving-dock shape as the priors
tranches: absent directory = no-op, a bad file is rejected WHOLE and by name, never half-applied,
and a malformed drop can never break the runtime).

"Help me find it" renders the payer's entry when the card identified the payer, else the generic
one. Steps are sendable by EMAIL through the one existing send path (users leave the app to go
to the portal — locked 5c). SMS is not built and is not offered.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

DOCUMENT_TYPES: tuple[str, ...] = (
    "eob", "sbc", "insurance_card", "itemized_bill", "accumulators", "plan_year",
)  # fmt: skip
GENERIC = "generic"
_DIR = "reference/payer_instructions"
_MAX_STEPS = 8
_MAX_STEP_CHARS = 240

# (document_type) -> the generic steps, as registry keys. One generic entry serves every screen
# that asks for that document type (the screen id narrows only payer-specific entries).
GENERIC_STEP_KEYS: dict[str, tuple[str, ...]] = {
    "eob": tuple(f"intake.help.eob_{n}" for n in range(1, 6)),
    "sbc": tuple(f"intake.help.sbc_{n}" for n in range(1, 5)),
    "insurance_card": tuple(f"intake.help.insurance_card_{n}" for n in range(1, 4)),
    "itemized_bill": tuple(f"intake.help.itemized_bill_{n}" for n in range(1, 5)),
    "accumulators": tuple(f"intake.help.accumulators_{n}" for n in range(1, 4)),
    "plan_year": tuple(f"intake.help.plan_year_{n}" for n in range(1, 4)),
}
assert set(GENERIC_STEP_KEYS) == set(DOCUMENT_TYPES)


@dataclass(frozen=True)
class PayerEntry:
    payer_id: str
    payer_name: str
    document_type: str
    screen_id: str | None  # None = every screen that asks for this document type
    steps: tuple[str, ...]  # authored text (Brock's), verbatim
    source: str  # where the path came from — a public help page vs a logged-in screen
    verified: bool  # §A5: a hands-on verification pass before launch; False renders a caveat
    as_of: str | None = None


# (payer_id, document_type, screen_id|None) -> entry. Filled by load_payer_entries at import.
PAYER_ENTRIES: dict[tuple[str, str, str | None], PayerEntry] = {}


def payer_id_for(name: str | None) -> str | None:
    """'UnitedHealthcare of Texas, Inc.' -> 'unitedhealthcare_of_texas_inc'. A stable slug; the
    corpus files may also list aliases. None when there is no name."""
    slug = re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")
    return slug or None


def _corpus_dir() -> Path:
    override = os.environ.get("TYNDALE_INTELLIGENCE_LAYER_ROOT")
    root = Path(override).resolve() if override else Path(__file__).resolve().parents[3] / "intelligence-layer"
    return root / _DIR


def _validate(raw: dict, *, file: str) -> list[PayerEntry]:
    payer_name = str(raw.get("payer_name") or "").strip()
    payer_id = payer_id_for(raw.get("payer_id") or payer_name)
    if not payer_id or not payer_name:
        raise ValueError("payer_id / payer_name missing")
    out: list[PayerEntry] = []
    ids = [payer_id, *[x for a in raw.get("aliases") or [] if (x := payer_id_for(a))]]
    for e in raw.get("entries") or []:
        doc = e.get("document_type")
        if doc not in DOCUMENT_TYPES:
            raise ValueError(f"unknown document_type {doc!r}")
        steps = [str(s).strip() for s in e.get("steps") or [] if str(s).strip()]
        if not 1 <= len(steps) <= _MAX_STEPS:
            raise ValueError(f"{doc}: needs 1–{_MAX_STEPS} steps, got {len(steps)}")
        if any(len(s) > _MAX_STEP_CHARS for s in steps):
            raise ValueError(f"{doc}: a step is over {_MAX_STEP_CHARS} characters")
        for pid in ids:
            out.append(
                PayerEntry(
                    payer_id=pid,
                    payer_name=payer_name,
                    document_type=doc,
                    screen_id=e.get("screen_id") or None,
                    steps=tuple(steps),
                    source=str(e.get("source") or "unspecified"),
                    verified=bool(e.get("verified", False)),
                    as_of=e.get("as_of") or raw.get("as_of"),
                )
            )
    if not out:
        raise ValueError("no entries")
    return out


def load_payer_entries(
    target: dict[tuple[str, str, str | None], PayerEntry] | None = None,
) -> dict[tuple[str, str, str | None], PayerEntry]:
    table = PAYER_ENTRIES if target is None else target
    d = _corpus_dir()
    if not d.is_dir():
        return table  # the corpus has not landed — generic fallbacks serve everyone
    for f in sorted(d.glob("*.json")):
        try:
            staged = _validate(json.loads(f.read_text(encoding="utf-8")), file=f.name)
        except Exception as e:  # noqa: BLE001 — a bad drop is rejected whole, never half-applied
            log.error("payer_instructions.file_rejected", file=f.name, error=str(e))
            continue
        table.update({(x.payer_id, x.document_type, x.screen_id): x for x in staged})
    return table


def instructions_for(
    payer_name: str | None, document_type: str, screen_id: str | None = None
) -> dict | None:
    """What "Help me find it" shows: the payer's own path when the payer is known AND the corpus
    has it (screen-specific first), else the generic steps. None for an unknown document type."""
    if document_type not in DOCUMENT_TYPES:
        return None
    pid = payer_id_for(payer_name)
    if pid:
        entry = PAYER_ENTRIES.get((pid, document_type, screen_id)) or PAYER_ENTRIES.get(
            (pid, document_type, None)
        )
        if entry is not None:
            return {
                "scope": "payer",
                "payer_name": entry.payer_name,
                "steps": list(entry.steps),
                "step_keys": [],
                "source": entry.source,
                "verified": entry.verified,
                "as_of": entry.as_of,
            }
    return {
        "scope": GENERIC,
        "payer_name": None,
        "steps": [],
        "step_keys": list(GENERIC_STEP_KEYS[document_type]),
        "source": "generic",
        "verified": True,
        "as_of": None,
    }


load_payer_entries()
