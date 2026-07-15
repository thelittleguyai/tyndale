"""Claim substantiation (Internal Analytics P0, §7).

For each PUBLIC marketing claim, evaluate its evidence gate (a minimum sample size, n) against the
aggregated analytics_daily rollups. A claim clears the gate only when its denominator meets the
threshold; otherwise the substantiation record says NOT PUBLISHABLE and by how much it falls short.
The win-rate claim hard-embeds its qualifier so the number can never be published bare.

This module is the gate LOGIC (importable + testable). ``scripts/generate_substantiation.py`` is
the CLI that writes the dated JSON + Markdown files. Nothing here publishes anything — the export
is the deliverable; publication is a later, separately-gated step.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.definitions import DEFINITIONS
from app.db.models.analytics_daily import AnalyticsDaily


@dataclass(frozen=True)
class Claim:
    key: str
    claim_text: str  # the public-facing sentence (with a {value} slot the export fills)
    metric_key: str
    min_n: int  # minimum denominator (sample size) required before the claim may be published
    qualifier: str = ""  # hard-embedded next to the number (e.g. win rate's report-basis caveat)


# The public claims. Thresholds are conservative placeholders pending Brock/counsel sign-off.
CLAIMS: dict[str, Claim] = {
    "win_rate": Claim(
        "win_rate",
        "Tyndale members resolved {value} of the billing issues they chose to pursue.",
        "win_rate",
        min_n=100,
        qualifier="Based on outcomes members reported, not all cases reviewed — resolved ÷ outcomes reported.",
    ),
    "close_the_loop_rate": Claim(
        "close_the_loop_rate",
        "{value} of members who were asked for a document came back and provided it.",
        "close_the_loop_rate",
        min_n=100,
    ),
    "audit_completion_rate": Claim(
        "audit_completion_rate",
        "{value} of started audits completed with a full result.",
        "audit_completion_rate",
        min_n=200,
    ),
}


def gate(n: float, min_n: int) -> tuple[bool, int]:
    """Pure gate: publishable when n ≥ min_n. Returns (publishable, shortfall) where shortfall is
    how many more samples are needed (0 once met)."""
    publishable = n >= min_n
    return publishable, 0 if publishable else int(min_n - n)


def _fmt_pct(value: float | None) -> str:
    return "—" if value is None else f"{round(value * 100)}%"


async def evaluate_claim(
    session: AsyncSession, claim: Claim, as_of: datetime.date | None = None
) -> dict:
    """Sum the claim's metric across all rollup days up to ``as_of`` and decide publishability.
    Returns the full substantiation record — number, definition, denominator, n, gate status,
    shortfall, qualifier, generated_at — the honest artifact counsel can inspect."""
    as_of = as_of or datetime.datetime.now(datetime.timezone.utc).date()
    num, den = (
        await session.execute(
            select(func.coalesce(func.sum(AnalyticsDaily.numerator), 0.0),
                   func.coalesce(func.sum(AnalyticsDaily.denominator), 0.0))
            .where(AnalyticsDaily.metric_key == claim.metric_key)
            .where(AnalyticsDaily.day <= as_of)
        )
    ).one()
    n = float(den)  # sample size = the denominator for a ratio
    value = (float(num) / n) if n > 0 else None
    publishable, shortfall = gate(n, claim.min_n)
    definition = DEFINITIONS[claim.metric_key].definition
    return {
        "claim_key": claim.key,
        "claim_text": claim.claim_text.format(value=_fmt_pct(value)),
        "metric_key": claim.metric_key,
        "value": value,
        "value_display": _fmt_pct(value),
        "numerator": float(num),
        "denominator": n,
        "n": n,
        "definition": definition,
        "qualifier": claim.qualifier,
        "min_n": claim.min_n,
        "gate_status": "PUBLISHABLE" if publishable else "NOT PUBLISHABLE",
        "shortfall": shortfall,
        "as_of": as_of.isoformat(),
    }


def to_markdown(record: dict) -> str:
    """Render one substantiation record as Markdown. NOT PUBLISHABLE records lead with the shortfall
    so no one mistakes an under-powered number for a cleared claim."""
    status = record["gate_status"]
    lines = [
        f"# Substantiation — {record['claim_key']}",
        "",
        f"**Status:** {status}",
    ]
    if status != "PUBLISHABLE":
        lines.append(
            f"**Shortfall:** {record['shortfall']} more samples needed "
            f"(n={int(record['n'])} / {record['min_n']} required)."
        )
    lines += [
        "",
        f"**Claim:** {record['claim_text']}",
        f"**Number:** {record['value_display']}  (n/d = {int(record['numerator'])}/{int(record['denominator'])})",
        f"**Definition:** {record['definition']}",
    ]
    if record["qualifier"]:
        lines.append(f"**Required qualifier:** {record['qualifier']}")
    lines += ["", f"_Generated {record['as_of']}. Not for publication until the gate clears and counsel signs off._"]
    return "\n".join(lines)
