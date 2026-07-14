"""Sub-case summary view shapes (D5, Phase C §2 — DL-91). The permanent /case/{id} view:
status banner + response-deadline clock, the three-number moment (re-hosted from Phase A),
the findings list, the recovered-so-far tally (CONFIRMED) and identified estimate (labeled
separately), the needs-documents have/need checklist, the next check-in, and the gameplan
(biggest-dollar-first per-call scripts). Mirrors packages/shared/src/case-summary.ts."""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.case_file import DocumentNeed
from app.schemas.record import DeadlineInfo, ThreeNumberBrief


class StatusBanner(BaseModel):
    status: str
    label: str
    # The response-deadline clock, from the deadline engine's PERSISTED rows only (shadow-mode
    # data is fine to display as informational). None when the case has no pending deadline.
    response_deadline: DeadlineInfo | None = None


class FindingBrief(BaseModel):
    finding_id: str
    finding_type: str  # payer_side | provider_side | encounter_mismatch
    category: str
    title: str
    claim: str | None = None  # Tier-B claim (agent-authored)
    dollar_impact: float | None = None  # facts['gap'] — an ESTIMATE, labeled in the view
    recommendation: str | None = None  # Tier-C action (agent-authored)


class CallScript(BaseModel):
    """The four beats of one phone call. `when_they_pick_up`/`get_it_in_writing`/`if_they_push_back`
    are Brock's connective copy (D1); `the_problem`/`the_ask` are the finding's own claim/action."""

    when_they_pick_up: str
    the_problem: str
    the_ask: str
    get_it_in_writing: str
    if_they_push_back: list[str]


class GameplanStep(BaseModel):
    index: int  # 1-based, biggest-dollar-first
    finding_id: str
    title: str
    party: str  # 'payer' | 'provider' — who to call
    party_label: str  # plain-language ("your insurance company")
    dollar_impact: float | None = None  # ESTIMATE for this item
    script: CallScript


class CaseSummaryPayload(BaseModel):
    case_file_id: str
    status_banner: StatusBanner
    provider: str | None = None  # best-effort; null until a structured provider is extracted
    service_date: str | None = None
    # The three-number moment card (re-hosted from Phase A). None → the view shows needs-documents,
    # never {0,0,0} (the CO-15 rule extends here).
    three_number: ThreeNumberBrief | None = None
    identified_estimate: float = 0.0  # audit ESTIMATE (finding gaps) — labeled, never "recovered"
    recovered_so_far: float = 0.0  # CONFIRMED outcome data only
    findings: list[FindingBrief]
    open_items: list[DocumentNeed]  # needs-documents have/need checklist (empty unless blocked)
    next_check_in_date: str | None = None
    gameplan: list[GameplanStep]
    # Call-mode framing (D1) — the full-screen step-through's intro + close.
    call_mode_intro: str
    call_mode_outro: str
