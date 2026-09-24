"""Email forwarding is dropped (Brock 2026-09-21, decision 6) — not deferred, not "coming soon".

It is an injection surface that needs its own security design before it exists at all, so the
timeline is upload-fed: no forwarding source in the typed seam, no registry string offering it,
no app copy mentioning it. If it returns, it starts with a security packet, not a string.
"""

from __future__ import annotations

import pathlib
import re
import typing

from app.agents.context_loader import load_orchestration_script
from app.intake.timeline import OFFERED_SOURCES, TIMELINE_SOURCES, TimelineSource

REPO = pathlib.Path(__file__).resolve().parents[2]
# forwarding an email/EOB/statement TO Tyndale — the feature, not the ordinary word
_OFFER = re.compile(
    r"forward(?:ing|ed)?\s+(?:your|the|an|it|them|us)?\s*(?:e-?mails?|eobs?|statements?|bills?)"
    r"|e-?mail\s+(?:your|the)\s+(?:eob|statement|bill)s?\s+to\b"
    r"|email[_ ]forward",
    re.IGNORECASE,
)


def test_the_timeline_seam_has_no_forwarding_source():
    assert TIMELINE_SOURCES == ("upload", "api")
    assert typing.get_args(TimelineSource) == ("upload", "api")
    assert OFFERED_SOURCES == ("upload",)


def test_no_registry_string_offers_forwarding():
    offending = {k: v for k, v in load_orchestration_script().items() if _OFFER.search(v or "")}
    assert offending == {}


def test_no_app_or_shared_source_mentions_forwarding():
    hits = []
    for root in ("apps/mobile/app", "apps/mobile/components", "apps/mobile/lib", "packages/shared/src"):
        for path in (REPO / root).rglob("*"):
            if path.suffix in {".ts", ".tsx"} and _OFFER.search(path.read_text(encoding="utf-8")):
                hits.append(str(path.relative_to(REPO)))
    assert hits == []
