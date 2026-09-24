"""Build the planner's snapshot from a case — every signal read from the seam that owns it.

``gather_inputs`` is the only function here that touches the database; everything it returns is
plain data, so the planner's rules stay unit-testable. ``IntakeState`` is the thin accessor over
``case_files.intake_state`` (the planner's own bookkeeping — see migration 0055).
"""

from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import encounter_facts
from app.agents.wrongdoc import AUDITABLE_TYPES, classify_wrong_document
from app.db.models.case_files import CaseFile
from app.db.models.users import User
from app.ingestion.bill_heuristics import detect_summary_bill
from app.intake.planner import (
    BILL_TYPES,
    CARD_TYPES,
    SBC_TYPES,
    PlannerInputs,
    population_of,
)
from app.intake.timeline import eob_rows, plan_year_start_from_documents
from app.sources.missing_data_priors import missing_cost_share_inputs
from app.sources.plan_docs import merge_case_coverage, plan_sbc_state

# The coverage-type ask's plain options -> the §A4-4 population. "job_or_bought" is the only one
# the Phase-1 route carries; "not_sure" keeps the user ON the route (the audit's generic rules
# ARE commercial, and it says so as an assumption) rather than exiting someone we cannot place.
COVERAGE_TYPE_OPTIONS: dict[str, str] = {
    "job_or_bought": "commercial",
    "medicare": "medicare",
    "medicaid": "medicaid",
    "military_va": "tricare_va",
    "none": "self_pay",
    "not_sure": "commercial",
}


class IntakeState:
    """Read/write view over ``case.intake_state``. Mutations REASSIGN the dict (SQLAlchemy does
    not track in-place JSONB edits)."""

    def __init__(self, case: CaseFile):
        self.case = case
        self._d: dict[str, Any] = dict(case.intake_state or {})

    def _save(self) -> None:
        self.case.intake_state = dict(self._d)

    @property
    def skipped(self) -> frozenset[str]:
        return frozenset(self._d.get("skipped") or [])

    @property
    def acked(self) -> frozenset[str]:
        return frozenset(self._d.get("acked") or [])

    @property
    def answers(self) -> dict[str, Any]:
        return dict(self._d.get("answers") or {})

    @property
    def high_water(self) -> list[str]:
        return list(self._d.get("progress_high_water") or [])

    def get(self, key: str, default: Any = None) -> Any:
        return self._d.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._d[key] = value
        self._save()

    def skip(self, screen_id: str) -> None:
        self._d["skipped"] = sorted(self.skipped | {screen_id})
        self._save()

    def unskip(self, screen_id: str) -> None:
        self._d["skipped"] = sorted(self.skipped - {screen_id})
        self._save()

    def ack(self, screen_id: str) -> None:
        self._d["acked"] = sorted(self.acked | {screen_id})
        self._save()

    def answer(self, key: str, value: Any) -> None:
        self._d["answers"] = {**self.answers, key: value}
        self._save()

    def raise_high_water(self, groups: list[str]) -> bool:
        """Persist newly filled segments. Returns True when the mark moved (never down)."""
        merged = [g for g in dict.fromkeys([*self.high_water, *groups])]
        if merged == self.high_water:
            return False
        self._d["progress_high_water"] = merged
        self._save()
        return True


def _types(case: CaseFile) -> list[str]:
    return [
        d.get("document_type")
        for d in (case.documents or [])
        if isinstance(d, dict) and d.get("document_type")
    ]


def _bill_is_summary(case: CaseFile) -> bool:
    """True when the case's bill(s) are ALL summaries. The classifier may already have typed a
    document `itemized_bill`; otherwise the existing heuristic reads the OCR text stored at
    upload (no second OCR call)."""
    bills = [
        d for d in (case.documents or []) if isinstance(d, dict) and d.get("document_type") in BILL_TYPES
    ]
    if not bills:
        return False
    for d in bills:
        if d.get("document_type") == "itemized_bill":
            return False
        if not detect_summary_bill(str(d.get("ocr_text") or ""))["is_summary"]:
            return False
    return True


def _user_provenance(cov: dict, key: str) -> dict:
    return (cov.get("user_input_provenance") or {}).get(key) or {}


async def gather_inputs(
    session: AsyncSession, case: CaseFile, *, plan_proposal: bool = False
) -> PlannerInputs:
    types = _types(case)
    case_cov = dict(case.coverage or {})
    sbc_present, plan_cov = await plan_sbc_state(session, case.user_id)
    effective = merge_case_coverage(case_cov, plan_cov) or {}
    st = IntakeState(case)

    bill_count = sum(1 for t in types if t in BILL_TYPES)
    rows = eob_rows(case)
    eob_count = len(rows)
    wrong = None
    if types and not any(t in AUDITABLE_TYPES for t in types):
        branch = classify_wrong_document(case.documents or [])
        wrong = branch.branch if branch else None

    # population: a VERIFIED regime, else the user's plain answer, else unknown (→ ask)
    detection = case.regime_detection or {}
    regime = case.coverage_regime if detection.get("verified") else None
    population = population_of(regime) or COVERAGE_TYPE_OPTIONS.get(
        st.answers.get("coverage_type") or ""
    )

    # plan-year start: the SBC's own coverage period wins; else the user's answer
    sbc_start = plan_year_start_from_documents(case.documents)
    user_start = case_cov.get("plan_effective_date")
    plan_year_start = sbc_start or (str(user_start) if user_start else None)

    # completeness is asked EVERY time — and again if the stack changed since it was confirmed
    confirmed = case_cov.get("all_plan_year_eobs_confirmed")
    if confirmed is not None and st.get("completeness_at_count") != eob_count:
        confirmed = None

    def _known(key: str) -> bool:
        p = _user_provenance(case_cov, key)
        return effective.get(key) is not None or bool(p.get("not_sure"))

    facts = encounter_facts.registry(case)  # R1: the one fact registry, keyed by fact_id
    first_name = (
        await session.execute(select(User.first_name).where(User.user_id == case.user_id))
    ).scalar_one_or_none()
    return PlannerInputs(
        bill_count=bill_count,
        bill_is_summary=_bill_is_summary(case),
        eob_count=eob_count,
        card_present=any(t in CARD_TYPES for t in types),
        wrong_document=wrong,
        payer_known=bool(effective.get("payer_name")),
        member_id_known=bool(effective.get("member_id")),
        provider=case.provider_name,
        date_of_service=case.date_of_service,
        patient_name=case.patient_name,
        account_first_name=(first_name or "").strip() or None,
        sbc_on_file=sbc_present or any(t in SBC_TYPES for t in types),
        plan_proposal=plan_proposal,
        missing_cost_share=tuple(missing_cost_share_inputs(effective)),
        coverage=effective,
        population=population,
        regime=regime,
        regime_candidate=detection.get("candidate"),
        plan_year_start=plan_year_start,
        plan_year_source="sbc" if sbc_start else ("user" if user_start else None),
        eobs_undated=sum(1 for r in rows if not r["date"]),
        completeness_confirmed=confirmed if isinstance(confirmed, bool) else None,
        deductible_met_known=_known("deductible_met"),
        oop_met_known=_known("oop_max_met"),
        attest_status=case.attest_status or "not_required",
        secondary_answered=case_cov.get("has_secondary_coverage") is not None,
        line_items=len(facts.facts),
        # done = every fact the engine emitted has an answer on file, wherever it was given
        confirmations_done=bool(facts.facts) and not facts.pending,
        case_status=case.status,
        skipped=st.skipped,
        acked=st.acked,
    )


def today() -> datetime.date:
    return datetime.datetime.now(datetime.timezone.utc).date()
