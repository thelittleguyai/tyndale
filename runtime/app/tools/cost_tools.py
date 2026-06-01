"""Cost-estimation tools (Phase CO-3A).

Backed by the transparency_rates table + the estimate_cost() query layer:
  - cost_estimate_combined   — the working path: confidence-banded estimate
                               combining Medicare baseline + hospital MRF + TiC.
  - cost_estimate_medicare_rvu — Medicare allowable for a code (PFS baseline;
                               hand-coded fallback while the table fills).
  - cost_estimate_hospital_mrf — negotiated rates for a specific hospital.
  - cost_estimate_tic        — negotiated rates for a specific payer.
  - cost_estimate_trilliant  — stub (DL-50 hands-off; raises NotImplementedError).
  - cost_estimate_fair_health — DEPRECATED (replaced by cost_estimate_combined).

DL-54: these return code NUMBERS + dollar bands only; never a CPT descriptor.
CO-002 Item 3: always a confidence band, never a point estimate.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select

from app.db.base import AsyncSessionLocal
from app.db.models.transparency_rates import TransparencyRate
from app.knowledge.cost_estimation import estimate_cost
from app.tools import register_tool

log = structlog.get_logger(__name__)

# Hand-coded fallback used only until the PFS table is populated.
_MEDICARE_BENCHMARK: dict[str, dict[str, float]] = {
    "70553": {"national_avg_allowed": 560.0, "rvu_total": 19.28},
}


async def _query_rates(source: str, code: str, **filters) -> list[TransparencyRate]:
    q = select(TransparencyRate).where(
        TransparencyRate.source == source, TransparencyRate.code == code
    )
    for k, v in filters.items():
        if v is not None:
            q = q.where(getattr(TransparencyRate, k) == v)
    async with AsyncSessionLocal() as s:
        return list((await s.execute(q)).scalars().all())


# --------------------------------------------------------------------------- #
# Combined (the working path)
# --------------------------------------------------------------------------- #
async def _cost_estimate_combined(args: dict[str, Any]) -> dict[str, Any]:
    code = str(args.get("code") or args.get("cpt_code") or "").strip()
    if not code:
        return {"error": "code required"}
    async with AsyncSessionLocal() as s:
        est = await estimate_cost(
            s,
            code=code,
            location_zip3=args.get("location_zip3"),
            payer=args.get("payer"),
            hospital_id=args.get("hospital_id"),
        )
    return est.to_dict()


register_tool(
    "cost_estimate_combined",
    {
        "description": (
            "Confidence-banded cost estimate for a procedure code at a location, combining the "
            "Medicare baseline with hospital-MRF + TiC negotiated rates. ALWAYS returns a "
            "low/central/high band (never a point number) per the No Surprises Act good-faith "
            "framing. This is the primary cost tool — prefer it over the per-source tools."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "location_zip3": {"type": "string"},
                "payer": {"type": "string"},
                "hospital_id": {"type": "string"},
            },
            "required": ["code"],
        },
    },
    _cost_estimate_combined,
)


# --------------------------------------------------------------------------- #
# Medicare PFS baseline
# --------------------------------------------------------------------------- #
async def _cost_estimate_medicare_rvu(args: dict[str, Any]) -> dict[str, Any]:
    code = str(args.get("cpt_code") or args.get("code") or "").strip()
    if not code:
        return {"error": "cpt_code required"}
    rows = await _query_rates("medicare_pfs", code)
    if rows:
        r = rows[0]
        return {
            "code": code,
            "available": True,
            "medicare_allowable": float(r.rate),
            "effective_year": r.effective_year,
            "source": "CMS PFS (transparency_rates source=medicare_pfs)",
        }
    bench = _MEDICARE_BENCHMARK.get(code)
    if bench:
        return {
            "code": code,
            "available": True,
            "benchmark": bench,
            "source": "hand-coded fallback (PFS table not yet ingested)",
        }
    return {
        "code": code,
        "available": False,
        "note": "No Medicare baseline ingested for this code yet.",
    }


register_tool(
    "cost_estimate_medicare_rvu",
    {
        "description": (
            "Medicare allowable (PFS baseline) for a CPT/HCPCS code — the independent fair-price "
            "anchor Math Person uses. Queries transparency_rates(source=medicare_pfs); falls back "
            "to a small hand-coded table until the PFS bulk ingest runs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"cpt_code": {"type": "string"}},
            "required": ["cpt_code"],
        },
    },
    _cost_estimate_medicare_rvu,
)


# --------------------------------------------------------------------------- #
# Hospital MRF
# --------------------------------------------------------------------------- #
async def _cost_estimate_hospital_mrf(args: dict[str, Any]) -> dict[str, Any]:
    code = str(args.get("code", "")).strip()
    hospital_id = args.get("hospital_id")
    if not code or not hospital_id:
        return {"error": "code and hospital_id required"}
    rows = await _query_rates("hospital_mrf", code, hospital_id=hospital_id)
    return {
        "code": code,
        "hospital_id": hospital_id,
        "rates": [
            {
                "payer": r.payer,
                "rate": float(r.rate),
                "rate_type": r.rate_type,
                "confidence": float(r.confidence_score),
            }
            for r in rows
        ],
    }


register_tool(
    "cost_estimate_hospital_mrf",
    {
        "description": "Negotiated/cash/gross rates a specific hospital published for a code (CMS hospital MRF).",
        "input_schema": {
            "type": "object",
            "properties": {"code": {"type": "string"}, "hospital_id": {"type": "string"}},
            "required": ["code", "hospital_id"],
        },
    },
    _cost_estimate_hospital_mrf,
)


# --------------------------------------------------------------------------- #
# TiC
# --------------------------------------------------------------------------- #
async def _cost_estimate_tic(args: dict[str, Any]) -> dict[str, Any]:
    code = str(args.get("code", "")).strip()
    payer = args.get("payer")
    if not code or not payer:
        return {"error": "code and payer required"}
    rows = await _query_rates("tic_mrf", code, payer=payer)
    return {
        "code": code,
        "payer": payer,
        "rates": [
            {
                "rate": float(r.rate),
                "rate_type": r.rate_type,
                "confidence": float(r.confidence_score),
            }
            for r in rows
        ],
    }


register_tool(
    "cost_estimate_tic",
    {
        "description": "A specific commercial payer's negotiated rates for a code (Transparency-in-Coverage MRF, ghost-filtered).",
        "input_schema": {
            "type": "object",
            "properties": {"code": {"type": "string"}, "payer": {"type": "string"}},
            "required": ["code", "payer"],
        },
    },
    _cost_estimate_tic,
)


# --------------------------------------------------------------------------- #
# Stubs
# --------------------------------------------------------------------------- #
async def _cost_estimate_trilliant(args: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError(
        "Trilliant integration pending per DL-50; hands-off pattern — Brock surfaces "
        "when the contract is live. Use cost_estimate_combined for the working path."
    )


register_tool(
    "cost_estimate_trilliant",
    {
        "description": "STUB — Trilliant procedure-price vendor (DL-50, contract pending). Not wired; use cost_estimate_combined.",
        "input_schema": {"type": "object", "properties": {"code": {"type": "string"}}},
    },
    _cost_estimate_trilliant,
)


async def _cost_estimate_fair_health(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "error": "DEPRECATED — FAIR Health was replaced by Trilliant (DL-50). Use cost_estimate_combined.",
        "deprecated": True,
    }


register_tool(
    "cost_estimate_fair_health",
    {
        "description": "DEPRECATED — replaced by Trilliant (DL-50). Use cost_estimate_combined.",
        "input_schema": {"type": "object", "properties": {"cpt_code": {"type": "string"}}},
    },
    _cost_estimate_fair_health,
)
