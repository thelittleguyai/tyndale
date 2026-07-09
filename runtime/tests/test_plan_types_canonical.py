"""Canonical plan-type vocabulary is the single source of truth (Brock 2026-07-06).

app.plan_types.PLAN_TYPES is authoritative; the laws_regulations.json schema enum and the
packages/shared TS mirror must match it exactly. These tests fail the build on any drift, so the
three surfaces can never silently diverge."""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.plan_types import (
    ATTRIBUTE_REGIME_COMPAT,
    PLAN_TYPES,
    PLAN_TYPES_WITH_ALL,
    attributes_incompatible,
    is_plan_type,
)

_REPO = Path(__file__).resolve().parents[2]
_SCHEMA = _REPO / "intelligence-layer" / "collections" / "schemas" / "laws_regulations.json"
_TS = _REPO / "packages" / "shared" / "src" / "intake.ts"


def test_exactly_14_plus_all():
    assert len(PLAN_TYPES) == 14
    assert PLAN_TYPES_WITH_ALL == (*PLAN_TYPES, "all")
    assert is_plan_type("dual_eligible") and not is_plan_type("all")  # 'all' is schema-only


def test_schema_enum_matches_canonical():
    schema = json.loads(_SCHEMA.read_text())
    enum = schema["properties"]["scope"]["properties"]["plan_types_bound"]["items"]["enum"]
    assert enum == list(PLAN_TYPES_WITH_ALL), "laws_regulations.json plan_types_bound drifted"


def test_ts_mirror_matches_canonical():
    text = _TS.read_text()
    block = re.search(r"COVERAGE_REGIMES\s*=\s*\[(.*?)\]\s*as const", text, re.S)
    assert block, "COVERAGE_REGIMES not found in intake.ts"
    ts_values = tuple(re.findall(r"'([^']+)'", block.group(1)))
    assert ts_values == PLAN_TYPES, "packages/shared intake.ts COVERAGE_REGIMES drifted"


def test_attribute_regime_compatibility():
    # qmb_status only on dual_eligible; medigap only on medicare_traditional; etc.
    assert attributes_incompatible("dual_eligible", {"qmb_status": True}) == []
    assert attributes_incompatible("medicare_advantage", {"qmb_status": True})  # wrong regime
    assert attributes_incompatible("state_regulated_commercial", {"governmental_fully_insured": True}) == []
    assert attributes_incompatible("medicare_traditional", {"medigap": True}) == []
    assert attributes_incompatible("state_regulated_commercial", {"medigap": True})  # medigap ⊄ commercial
    # a NULL attribute is 'unknown' — never a compatibility error, even on the wrong regime.
    assert attributes_incompatible("self_pay", {"qmb_status": None}) == []
    # unknown key is reported.
    assert attributes_incompatible("dual_eligible", {"bogus": True})
    # every compat regime is a real plan type.
    for allowed in ATTRIBUTE_REGIME_COMPAT.values():
        if allowed is not None:
            assert allowed <= set(PLAN_TYPES)
