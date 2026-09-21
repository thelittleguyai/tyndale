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
Humana, Aetna, Mayo) are REFERENCES for drawing our own and are never embedded — the five
drawn, de-branded illustrations come from Brock's sources file, which is not in the repo yet.
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
    callout_keys: tuple[str, ...]  # 4–6 numbered "look for this" callouts
    asset: ExampleAsset | None
    pending: str | None = None  # what the missing asset is waiting on

    @property
    def renderable(self) -> bool:
        return self.asset is not None and bool(self.callout_keys)


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
    ),
    # Present in the registry, NOT renderable: each waits on a drawn, de-branded illustration
    # (research_companions/example_documents_sources_2026-09-17.md — ANNOTATION SPEC).
    "itemized_bill": Example("itemized_bill", None, (), None, "drawn illustration (Mayo layout reference)"),
    "summary_vs_itemized": Example("summary_vs_itemized", None, (), None, "drawn illustration"),
    "insurance_card": Example("insurance_card", None, (), None, "drawn illustration (CARIN card anatomy)"),
    "eob": Example("eob", None, (), None, "drawn illustration (CMS generic EOB + reader guides)"),
    "accumulators": Example("accumulators", None, (), None, "drawn composite (FEP Blue / Humana dashboards)"),
}


def example_for(ask: str | None) -> Example | None:
    """The example to OFFER for an ask — None unless it can actually be shown."""
    ex = EXAMPLES.get(ask or "")
    return ex if ex is not None and ex.renderable else None
