"""50-state + DC surprise-billing seed gate (DL-81).

This is the "complete and passing retrieval checks" launch gate that must be GREEN
before NSA / state-balance-billing checks ship to users (ENABLE_NSA_CHECKS stays false
until then). Run it against a LIVE Qdrant that has been seeded with the real
``laws_regulations`` jurisdiction content (Brock/Josh's seed — TODO(brock-content)).

It asserts, over the ``laws_regulations`` collection:

  1. One entry per state + DC (51 jurisdictions present).
  2. Every jurisdiction record is schema-valid against laws_regulations.json.
  3. Each jurisdiction carries an ``x6_classification`` and a NON-NULL
     ``scope.ground_ambulance_covered`` (the ground-ambulance answer is never implicit).
  4. Retrieval smoke: a balance-billing query naming each state returns that state's
     own entry within top-k (proves the vector actually retrieves, not just that the
     row exists).

Exit status: 0 only when the gate is fully met. ``--allow-partial`` always exits 0
(informational mode — used by the optional CI job so it surfaces the gate status
without blocking PRs until the real seed lands). ``--no-retrieval`` runs structural
checks only (e.g. where Voyage embeddings are unavailable).

Usage:
    uv run python scripts/check_state_seed.py
    uv run python scripts/check_state_seed.py --allow-partial   # CI informational
    uv run python scripts/check_state_seed.py --no-retrieval
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))  # runtime/

from jsonschema import Draft7Validator  # noqa: E402

from app.knowledge.client import get_client  # noqa: E402
from app.knowledge.search import search_and_rerank  # noqa: E402

_IL_ROOT = os.environ.get("TYNDALE_INTELLIGENCE_LAYER_ROOT")
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_IL_DIR = pathlib.Path(_IL_ROOT) if _IL_ROOT else REPO_ROOT / "intelligence-layer"
SCHEMA_PATH = _IL_DIR / "collections" / "schemas" / "laws_regulations.json"

# 50 states + DC. Jurisdiction field is ``state_<XX>`` (DC is ``state_DC``).
STATES: dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
    "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "DC": "District of Columbia",
}
EXPECTED = {f"state_{code}" for code in STATES}


async def _scroll_all(collection: str) -> list[dict]:
    """Page every stored payload out of the collection."""
    client = get_client()
    out: list[dict] = []
    offset = None
    while True:
        points, offset = await client.scroll(
            collection_name=collection, limit=256, offset=offset, with_payload=True, with_vectors=False
        )
        out.extend(p.payload or {} for p in points)
        if offset is None:
            break
    return out


def _ground_ambulance_answered(rec: dict) -> bool:
    scope = rec.get("scope")
    return isinstance(scope, dict) and scope.get("ground_ambulance_covered") is not None


async def _retrieval_smoke(code: str, name: str, effective_date: str, top_k: int, top_n: int) -> bool:
    """A state's own balance-billing query should surface that state's entry in top-k."""
    query = f"{name} out-of-network surprise balance billing at an in-network facility; ground ambulance"
    hits = await search_and_rerank(
        collection="laws_regulations",
        query=query,
        effective_date=effective_date,
        top_k=top_k,
        top_n=top_n,
    )
    return any((h.payload or {}).get("jurisdiction") == f"state_{code}" for h in hits)


async def run(args: argparse.Namespace) -> int:
    validator = Draft7Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
    effective_date = args.effective_date or datetime.date.today().isoformat()

    try:
        records = await _scroll_all("laws_regulations")
    except Exception as exc:  # noqa: BLE001 — connection/collection problems are a hard gate failure
        print(f"FAIL: could not read laws_regulations from Qdrant ({type(exc).__name__}: {exc})")
        return 0 if args.allow_partial else 1

    by_juris: dict[str, list[dict]] = {}
    for rec in records:
        j = rec.get("jurisdiction")
        if isinstance(j, str) and j.startswith("state_"):
            by_juris.setdefault(j, []).append(rec)

    present = set(by_juris)
    missing = sorted(EXPECTED - present)
    unexpected = sorted(present - EXPECTED)

    invalid: list[str] = []
    no_x6: list[str] = []
    no_ground: list[str] = []
    fehb_on_state: list[str] = []  # HARD RULE (Brock 2026-07-06): state law never binds fehb_pshb
    for juris in sorted(present & EXPECTED):
        recs = by_juris[juris]
        for rec in recs:
            if list(validator.iter_errors(rec)):
                first = next(iter(validator.iter_errors(rec)))
                invalid.append(f"{juris}[{rec.get('chunk_id', '?')}]: {first.message}")
            # FEHBA preempts state insurance law (5 U.S.C. 8902(m)(1)) — a state-jurisdiction entry
            # (jurisdiction != 'US') binding fehb_pshb is a wrong-answer error, not a warning.
            bound = ((rec.get("scope") or {}).get("plan_types_bound")) or []
            if rec.get("jurisdiction") != "US" and "fehb_pshb" in bound:
                fehb_on_state.append(f"{juris}[{rec.get('chunk_id', '?')}]")
        if not any(r.get("x6_classification") for r in recs):
            no_x6.append(juris)
        if not any(_ground_ambulance_answered(r) for r in recs):
            no_ground.append(juris)

    # --- retrieval smoke ---
    retrieval_failures: list[str] = []
    retrieval_ran = False
    if not args.no_retrieval and (present & EXPECTED):
        for juris in sorted(present & EXPECTED):
            code = juris.removeprefix("state_")
            try:
                ok = await _retrieval_smoke(code, STATES[code], effective_date, args.top_k, args.top_n)
                retrieval_ran = True
            except Exception as exc:  # noqa: BLE001 — embeddings/rerank unavailable (e.g. no Voyage key)
                print(f"SKIP retrieval smoke: embeddings/rerank unavailable ({type(exc).__name__}: {exc})")
                retrieval_failures = []
                retrieval_ran = False
                break
            if not ok:
                retrieval_failures.append(juris)

    # --- report ---
    print("=" * 68)
    print("50-state + DC surprise-billing seed gate (DL-81)")
    print("=" * 68)
    print(f"jurisdictions present : {len(present & EXPECTED)}/51")
    if missing:
        print(f"  MISSING ({len(missing)}): {', '.join(missing)}")
    if unexpected:
        print(f"  UNEXPECTED jurisdiction codes: {', '.join(unexpected)}")
    print(f"schema-invalid records: {len(invalid)}")
    for line in invalid[:20]:
        print(f"  - {line}")
    print(f"missing x6_classification    : {len(no_x6)}" + (f" ({', '.join(no_x6)})" if no_x6 else ""))
    print(f"null ground-ambulance answer : {len(no_ground)}" + (f" ({', '.join(no_ground)})" if no_ground else ""))
    print(f"state law binding fehb_pshb  : {len(fehb_on_state)}" + (
        f" ({', '.join(fehb_on_state)})" if fehb_on_state else "") + "  [must be 0 — FEHBA preempts state law]")
    if args.no_retrieval:
        print("retrieval smoke       : skipped (--no-retrieval)")
    elif not retrieval_ran:
        print("retrieval smoke       : skipped (embeddings unavailable)")
    else:
        print(f"retrieval smoke       : {len(retrieval_failures)} state(s) failed to self-retrieve")
        for juris in retrieval_failures[:20]:
            print(f"  - {juris}")

    gate_met = (
        not missing
        and not unexpected
        and not invalid
        and not no_x6
        and not no_ground
        and not fehb_on_state
        and (args.no_retrieval or not retrieval_ran or not retrieval_failures)
    )
    strict_retrieval_gap = args.strict and (args.no_retrieval or not retrieval_ran)
    print("-" * 68)
    if gate_met and not strict_retrieval_gap:
        print("GATE: PASS — NSA / state balance-billing checks may ship (flip ENABLE_NSA_CHECKS).")
        return 0
    if strict_retrieval_gap:
        print("GATE: FAIL — --strict requires a live retrieval smoke, which did not run.")
    else:
        print("GATE: NOT MET — seed is incomplete or failing checks; keep ENABLE_NSA_CHECKS=false.")
    return 0 if args.allow_partial else 1


def main() -> None:
    p = argparse.ArgumentParser(description="50-state + DC surprise-billing seed gate (DL-81)")
    p.add_argument("--no-retrieval", action="store_true", help="structural checks only (skip the vector smoke)")
    p.add_argument("--strict", action="store_true", help="require the retrieval smoke to actually run")
    p.add_argument(
        "--allow-partial",
        action="store_true",
        help="always exit 0 (informational CI mode — reports the gate status without failing the build)",
    )
    p.add_argument("--effective-date", default=None, help="ISO date for the point-in-time query (default: today)")
    p.add_argument("--top-k", type=int, default=30)
    p.add_argument("--top-n", type=int, default=8)
    args = p.parse_args()
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
