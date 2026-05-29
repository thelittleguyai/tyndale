"""Seed dev dashboard data.

Creates the Phase 2H dev user (idempotent), attaches a coverage record
with the screenshot values (Deductible $1,750/$2,000, OOP Max $3,200/
$6,500, copays $25/$250/$50), creates one open case file with a sample
payer-side finding (so amount-saved-YTD has a value), and seeds one
pending deadline (so the lead-with-status greeting has something to
render).

Usage:
    uv run python runtime/scripts/seed_dev_dashboard.py

Safe to run multiple times — the dev user / case / finding are all
matched by stable UUIDs so re-runs no-op on the duplicate.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import date, datetime, timezone, timedelta

from sqlalchemy import select

# Allow running from repo root: `uv run python runtime/scripts/seed_dev_dashboard.py`
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from app.auth.dev_user import _DEV_USER_EMAIL, _DEV_USER_ID  # noqa: E402
from app.db.base import AsyncSessionLocal  # noqa: E402
from app.db.models.case_files import CaseFile  # noqa: E402
from app.db.models.deadlines import Deadline  # noqa: E402
from app.db.models.findings import Finding  # noqa: E402
from app.db.models.users import User  # noqa: E402

_DEV_CASE_ID = uuid.UUID("00000000-0000-0000-0000-00000000ca5e")
_DEV_FINDING_ID = uuid.UUID("00000000-0000-0000-0000-0000000f1d11")
_DEV_DEADLINE_ID = uuid.UUID("00000000-0000-0000-0000-0000000dead1")

# Screenshot reference values
_COVERAGE = {
    "plan_name": "Sample PPO",
    "payer_name": "UnitedHealthcare",
    "member_id": "DEV-0001",
    "deductible_amount": 2000.0,
    "deductible_met": 1750.0,
    "oop_max_amount": 6500.0,
    "oop_max_met": 3200.0,
    "copay_pcp": 25.0,
    "copay_er": 250.0,
    "copay_specialist": 50.0,
    "network_tier": "in-network",
    "coverage_terms_confidence": {"overall": 0.95, "notes": "Dev seed — deterministic values"},
}


async def go() -> None:
    async with AsyncSessionLocal() as s:
        # Dev user --------------------------------------------------------
        row = (await s.execute(select(User).where(User.user_id == _DEV_USER_ID))).scalar_one_or_none()
        if row is None:
            s.add(
                User(
                    user_id=_DEV_USER_ID,
                    email=_DEV_USER_EMAIL,
                    service_consent=True,
                    improvement_consent=False,
                )
            )
            print(f"+ user {_DEV_USER_ID}")
        else:
            print(f"= user {_DEV_USER_ID} (exists)")

        # Dev case --------------------------------------------------------
        case = (await s.execute(select(CaseFile).where(CaseFile.case_file_id == _DEV_CASE_ID))).scalar_one_or_none()
        if case is None:
            created_at = datetime.now(timezone.utc) - timedelta(days=9)
            s.add(
                CaseFile(
                    case_file_id=_DEV_CASE_ID,
                    user_id=_DEV_USER_ID,
                    status="in_progress",
                    documents=[
                        {
                            "document_id": str(uuid.uuid4()),
                            "filename": "uhc_eob_2026-05-12.pdf",
                            "document_type": "eob",
                            "byte_count": 142_336,
                            "uri": "/tmp/tyndale_uploads/seed_eob.pdf",
                        }
                    ],
                    coverage=_COVERAGE,
                    eobs=[],
                    created_at=created_at,
                    updated_at=created_at,
                )
            )
            print(f"+ case {_DEV_CASE_ID}")
        else:
            print(f"= case {_DEV_CASE_ID} (exists)")
            # Backfill coverage on re-runs so screenshot values stay synced.
            case.coverage = _COVERAGE

        await s.flush()

        # Dev finding (payer-side, contributes to Amount Saved YTD) -------
        finding = (
            await s.execute(select(Finding).where(Finding.finding_id == _DEV_FINDING_ID))
        ).scalar_one_or_none()
        if finding is None:
            s.add(
                Finding(
                    finding_id=_DEV_FINDING_ID,
                    case_file_id=_DEV_CASE_ID,
                    finding_type="payer_side",
                    category="cost_sharing_miscalculation",
                    subagent_source="math_person",
                    voice_tier="B",
                    facts={
                        "provider_billed": 1200.0,
                        "eob_member_responsibility": 1200.0,
                        "tyndale_computed": 560.0,
                        "gap": 1482.0,  # demo value matches the dashboard screenshot's $1,482 amount-saved
                        "cpt_code": "70553",
                    },
                    legal_claim={
                        "claim": "Payer appears to have miscalculated member cost-sharing.",
                        "marker": "[PLACEHOLDER §000, src_seed_001]",
                        "citations": [
                            {
                                "authority": "PLACEHOLDER",
                                "section": "§000",
                                "src_id": "src_seed_001",
                                "marker": "[PLACEHOLDER §000, src_seed_001]",
                            }
                        ],
                    },
                    recommendation={
                        "action": "Call UnitedHealthcare member services and request a corrected EOB.",
                        "reasoning": "Tyndale's independent figure ($560) is below the EOB's claimed $1,200.",
                    },
                )
            )
            print(f"+ finding {_DEV_FINDING_ID}")
        else:
            print(f"= finding {_DEV_FINDING_ID} (exists)")

        # Dev deadline (pending) ------------------------------------------
        deadline = (
            await s.execute(select(Deadline).where(Deadline.deadline_id == _DEV_DEADLINE_ID))
        ).scalar_one_or_none()
        if deadline is None:
            s.add(
                Deadline(
                    deadline_id=_DEV_DEADLINE_ID,
                    case_file_id=_DEV_CASE_ID,
                    deadline_date=date.today() + timedelta(days=12),
                    deadline_type="payer_response_expected",
                    description="Insurer response expected",
                )
            )
            print(f"+ deadline {_DEV_DEADLINE_ID}")
        else:
            print(f"= deadline {_DEV_DEADLINE_ID} (exists)")

        await s.commit()
        print("seed complete")


if __name__ == "__main__":
    asyncio.run(go())
