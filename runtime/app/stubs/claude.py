"""Stubbed Claude Agent SDK orchestration (Phase 1C).

Returns canned outputs while USE_REAL_CLAUDE is false. Phase 2 replaces these with
real Lead Planner + Bill Detective + Math Person invocations via the LiteLLM proxy.
"""

from __future__ import annotations

from typing import Any

from app.stubs.fixtures import mri_audit_fixture


def stub_lead_planner(case_file_id: str, message: str) -> dict[str, Any]:
    """Canned Lead Planner response — returns the MRI audit fixture."""
    result = mri_audit_fixture(case_file_id)
    return {
        "actor": "lead_planner",
        "stub": True,
        "result": result.model_dump(),
    }


def stub_bill_detective(case_file_id: str) -> dict[str, Any]:
    return {
        "actor": "bill_detective",
        "stub": True,
        "findings": [{"category": "cost_sharing_miscalculation", "finding_type": "payer_side"}],
    }


def stub_math_person(case_file_id: str) -> dict[str, Any]:
    return {
        "actor": "math_person",
        "stub": True,
        "three_numbers": {
            "provider_billed": 1200.0,
            "eob_member_responsibility": 1200.0,
            "tyndale_computed": 560.0,
        },
    }
