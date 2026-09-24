"""The example registry (doc 40 §A3) — "a real example on every ask". Structure now, content
when it lands.

One entry per ask. An entry with an ``asset`` renders a "See an example" affordance; an entry
with ``asset=None`` renders NOTHING — no empty sheet, no "coming soon" (the CO-1A placeholder
this replaces said exactly that). Phase 1 ships the only two assets that may be shown directly:
the federal samples. Both URLs were fetched and read on 2026-09-21, and each callout below
names something that is actually printed on that document:

  * CMS "Summary of Benefits and Coverage — Completed Example" (coverage period 01/01/2025–
    12/31/2025, OMB 0938-1146): p.1 "Coverage Period", "What is the overall deductible?",
    "Are there other deductibles for specific services?", "What is the out-of-pocket limit for
    this plan?"; p.2 "Network Provider" / "Out-of-Network Provider"; p.5 "About these
    Coverage Examples" (Peg / Joe / Mia).
  * CMS "What is in your Medicare Summary Notice? — Part B": p.1 "THIS IS NOT A BILL",
    "Your Deductible Status", "Total You May Be Billed"; p.3 "Your Claims for Part B" with the
    "Maximum You May Be Billed" column; last page "How to Handle Denied Claims or File an Appeal".

Copyright rule (§A3): federal works may be shown directly. Payer-branded guide images (UHC,
Humana, Aetna, Mayo) are REFERENCES for drawing our own and are never embedded.

Phase 2 (Brock 2026-09-21, decision 8 — docs/build-kit/41_example_illustrations_spec.md): every
ask also gets an AI-GENERATED, de-branded illustration with numbered badges, and Brock's grade-5
LEGEND (`intake.example.<doc>.<n>`, verbatim from doc 41) rendered by the app beside or below it
— screen-reader readable and localizable, never baked into the image. The images are bundled
with the app at ``apps/mobile/assets/examples/<slot>@2x.png`` (1560×1950 portrait; 1560×975 for
the card and the side-by-side). Phil generates them from doc 41's prompts; until a file lands its
entry is ``pending_asset`` and offers NOTHING new — the SBC and MSN screens keep showing the CMS
samples directly. tests/test_example_manifest.py keeps each flag in step with the file on disk.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExampleAsset:
    kind: str  # "external_pdf" — opened in the browser / in-app viewer; nothing is bundled
    url: str
    publisher: str
    license: str  # why we may show it
    verified_on: str  # the day the URL was fetched and the callouts checked against it


@dataclass(frozen=True)
class Example:
    ask: str
    title_key: str | None
    callout_keys: tuple[str, ...]  # the FEDERAL sample's 4–6 numbered "look for this" callouts
    asset: ExampleAsset | None  # the federal sample, shown directly (SBC, MSN)
    pending: str | None = None  # what the missing piece is waiting on
    # doc 41: the drawn illustration — its bundled image slot, Brock's legend (one line per badge,
    # in badge order), whether the file is still to come, and its frame.
    illustration: str | None = None
    legend_keys: tuple[str, ...] = ()
    pending_asset: bool = True
    aspect: str = "portrait"  # portrait 1560×1950 · landscape 1560×975

    @property
    def illustrated(self) -> bool:
        """The drawn illustration can be shown: its image is in the app bundle."""
        return bool(self.illustration) and not self.pending_asset and bool(self.legend_keys)

    @property
    def renderable(self) -> bool:
        return self.illustrated or (self.asset is not None and bool(self.callout_keys))


def _legend(doc: str, n: int) -> tuple[str, ...]:
    return tuple(f"intake.example.{doc}.{i}" for i in range(1, n + 1))


def _drawn(ask: str, section: str, n: int, *, aspect: str = "portrait") -> Example:
    """An ask whose only example is a doc 41 illustration (no federal sample exists)."""
    return Example(
        ask, f"intake.example.{ask}_title", (), None,
        f"AI-generated illustration, doc 41 {section} — drop {ask}@2x.png into apps/mobile/assets/examples",
        illustration=ask, legend_keys=_legend(ask, n), pending_asset=True, aspect=aspect,
    )


_FEDERAL = "U.S. federal government work — public domain"

EXAMPLES: dict[str, Example] = {
    "sbc": Example(
        ask="sbc",
        title_key="intake.example.sbc_title",
        callout_keys=tuple(f"intake.example.sbc_{n}" for n in range(1, 7)),
        asset=ExampleAsset(
            kind="external_pdf",
            url="https://www.cms.gov/cciio/resources/forms-reports-and-other-resources/downloads/english-sample-completed-sbc-accessible-format-012825.pdf",
            publisher="CMS / CCIIO",
            license=_FEDERAL,
            verified_on="2026-09-21",
        ),
        illustration="sbc", legend_keys=_legend("sbc", 6), pending_asset=True,  # doc 41 §5
    ),
    "msn": Example(
        ask="msn",
        title_key="intake.example.msn_title",
        callout_keys=tuple(f"intake.example.msn_{n}" for n in range(1, 6)),
        asset=ExampleAsset(
            kind="external_pdf",
            url="https://www.cms.gov/Medicare/Medicare-General-Information/MSN/Downloads/Sample-Part-B-Medicare-Summary-Notice.pdf",
            publisher="CMS",
            license=_FEDERAL,
            verified_on="2026-09-21",
        ),
        illustration="msn", legend_keys=_legend("msn", 5), pending_asset=True,  # doc 41 §4
    ),
    # Only an illustration (doc 41), each pending until its image lands — offered nowhere until then.
    "itemized_bill": _drawn("itemized_bill", "§1", 6),
    "summary_vs_itemized": _drawn("summary_vs_itemized", "§1 (companion)", 1, aspect="landscape"),
    "insurance_card": _drawn("insurance_card", "§2", 6, aspect="landscape"),
    "eob": _drawn("eob", "§3", 6),
    "accumulators": _drawn("accumulators", "§6 (the portal deductible screen)", 6),
    "eob_timeline": _drawn("eob_timeline", "§7 (the timeline helper)", 2),
}


def example_for(ask: str | None) -> Example | None:
    """The example to OFFER for an ask — None unless it can actually be shown."""
    ex = EXAMPLES.get(ask or "")
    return ex if ex is not None and ex.renderable else None
