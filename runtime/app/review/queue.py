"""Human Review Phase 1 — queue policy + enqueue (doc 39 §7-2d, Brock 2026-09-17).

Every terminal audit transition passes through ``on_terminal`` (hooked from
``orchestrator._set_status``). Policy: a random ``review_sample_pct`` of completed runs is
enqueued (100 = every run — the default until volume forces sampling); the always-enqueue
TRIGGERS fire regardless of the dial. Each trigger is a Settings flag, the dial is an env
default an admin can override at runtime (admin_settings).

States per case run: unreviewed → in_review → approved | disapproved | cant_verify. A run
that completes after a DECIDED review is a ``re_review`` row linked to its predecessor — the
prior verdict is never overwritten. A run that completes while the previous one is still
pending re-stamps that pending row (one queue row per case that needs attention).
"""

from __future__ import annotations

import hashlib
import json
import statistics
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.base import AsyncSessionLocal
from app.db.models.case_files import CaseFile
from app.db.models.case_reviews import AdminSetting, CaseReview
from app.db.models.findings import Finding
from app.sources.materiality import AUDIT_FLAG, is_material

log = structlog.get_logger()

TERMINAL_STATUSES = ("audit_complete", "audit_incomplete")
PENDING_STATES = ("unreviewed", "in_review", "re_review")
DECIDED_STATES = ("approved", "disapproved", "cant_verify")
SAMPLE_PCT_KEY = "review_sample_pct"
_DOC_TEXT_KEYS = ("ocr_text", "full_text", "text_preview", "preview", "text")


@dataclass(frozen=True)
class EnqueueFacts:
    """What the policy looks at — stamped onto the review row so the queue filters read
    columns instead of re-deriving an audit per row."""

    terminal_status: str
    incomplete_reason: str | None
    confidence_band: str  # high | medium | low | unknown
    first_case: bool
    system_error: bool
    canary_flag: bool
    material_disagreement: bool
    findings_count: int
    net_finding_usd: float | None
    documents_fingerprint: str
    # A synthetic test identity (@e2e.tyndale.test …): its runs are fixtures, not reviews.
    synthetic: bool = False


@dataclass(frozen=True)
class EnqueueDecision:
    enqueue: bool
    sampled: bool
    triggers: tuple[str, ...]
    skipped: str | None = None  # "synthetic" — the policy refused before dial or triggers


def confidence_band(tier: int | None) -> str:
    """Disclosure tier → queue band. 0/1 grounded-or-noted = high, 2 disclose = medium,
    3 chase = low; no result at all = unknown."""
    if tier is None:
        return "unknown"
    if tier <= 1:
        return "high"
    if tier == 2:
        return "medium"
    return "low"


# What makes a document THAT document — never anything extraction writes or rewrites.
_DOC_IDENTITY_KEYS = (
    "document_id",
    "uri",
    "blob_name",
    "sha256",
    "content_hash",
    "byte_count",
    "uploaded_at",
)
_DOC_LEGACY_IDENTITY_KEYS = ("filename", "document_type")  # rows older than document_id


def documents_fingerprint(documents: list | None, eobs: list | None = None) -> str:
    """A stable digest of WHICH documents the case holds — ids, stored-blob names, content
    hashes/sizes, upload times. Two runs with different fingerprints are 'a re-run after
    document change'. It used to hash every non-text field, so a mutable extraction field
    (extraction_status, ocr_text_chars, page_count, a re-derived provider name…) changing
    between runs read as a document change and forced a spurious re_review (deep review)."""

    def identity(d: dict) -> dict:
        ident = {k: d[k] for k in _DOC_IDENTITY_KEYS if d.get(k) is not None}
        return ident or {k: d.get(k) for k in _DOC_LEGACY_IDENTITY_KEYS}

    idents = [identity(d) for d in [*(documents or []), *(eobs or [])] if isinstance(d, dict)]
    blob = json.dumps(
        sorted(idents, key=lambda i: json.dumps(i, sort_keys=True, default=str)),
        sort_keys=True,
        default=str,
    )
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]  # noqa: S324 — not security


def stable_roll(case_file_id: uuid.UUID | str) -> float:
    """The sampling draw for a case, in [0, 1) — a pure function of the case id. A re-run must
    not re-roll: with a random draw, a case skipped at dial 25 had a fresh 25% chance on every
    re-run, so 'sampled' meant 'eventually'. Percent granularity: hash % 100."""
    digest = hashlib.sha256(str(case_file_id).encode("utf-8")).digest()
    return (int.from_bytes(digest[:8], "big") % 100) / 100.0


def decide(facts: EnqueueFacts, *, sample_pct: int, roll: float, settings=None) -> EnqueueDecision:
    """The pure policy. ``roll`` in [0, 1) is the sampling draw — ``stable_roll(case_file_id)``
    in production, so the same case always draws the same number."""
    if facts.synthetic:
        # Deep review C5: every e2e sweep mints a synthetic user and completes ~22 audits; at
        # dial 100 that is ~22 fixtures in the reviewer's queue per run. No dial, no trigger
        # and no forced re-review overrides this.
        return EnqueueDecision(enqueue=False, sampled=False, triggers=(), skipped="synthetic")
    s = settings or get_settings()
    triggers: list[str] = []
    if s.review_trigger_first_case and facts.first_case:
        triggers.append("first_case")
    # "unknown" = the result could not even be projected (no disclosure tier to read). That is
    # the run that most needs eyes, so for TRIGGER purposes it counts as low confidence — at a
    # sampled dial it used to slip through as if it were fine. The band column still says
    # 'unknown', so the queue shows it for what it is.
    if s.review_trigger_low_confidence and facts.confidence_band in ("low", "unknown"):
        triggers.append("low_confidence")
    if s.review_trigger_system_error and facts.system_error:
        triggers.append("system_error")
    if s.review_trigger_canary and facts.canary_flag:
        triggers.append("canary")
    if s.review_trigger_material_disagreement and facts.material_disagreement:
        triggers.append("material_disagreement")
    pct = max(0, min(100, int(sample_pct)))
    sampled = pct >= 100 or (roll * 100.0) < pct
    return EnqueueDecision(
        enqueue=sampled or bool(triggers), sampled=sampled, triggers=tuple(triggers)
    )


async def effective_sample_pct(session: AsyncSession) -> int:
    """The runtime dial: the admin override when one is stored and valid, else the env default."""
    row = await session.get(AdminSetting, SAMPLE_PCT_KEY)
    if row is not None and isinstance(row.value, dict):
        try:
            pct = int(row.value.get("pct"))
            if 0 <= pct <= 100:
                return pct
        except (TypeError, ValueError):
            pass
    return max(0, min(100, int(get_settings().review_sample_pct)))


async def set_sample_pct(session: AsyncSession, pct: int, *, admin_id: uuid.UUID) -> int:
    pct = max(0, min(100, int(pct)))
    row = await session.get(AdminSetting, SAMPLE_PCT_KEY)
    if row is None:
        session.add(AdminSetting(key=SAMPLE_PCT_KEY, value={"pct": pct}, updated_by=admin_id))
    else:
        row.value = {"pct": pct}
        row.updated_by = admin_id
        row.updated_at = datetime.now(timezone.utc)
    return pct


def _net_usd(findings: list[Finding]) -> float | None:
    total, seen = 0.0, False
    for f in findings:
        facts = f.facts if isinstance(f.facts, dict) else {}
        gap = facts.get("gap")
        if isinstance(gap, (int, float)):
            total += float(gap)
            seen = True
    return round(total, 2) if seen else None


async def gather_facts(
    session: AsyncSession, case: CaseFile, status: str, incomplete_reason: str | None
) -> EnqueueFacts:
    """Assemble the enqueue facts from persisted data only (the result projection, the
    findings, the case's tripwire log, the user's case count) — never from a model."""
    from app.agents.orchestrator import _assemble_result, tripwire_entries
    from app.db.models.users import User
    from app.notify.email import is_synthetic_email

    owner_email = (
        await session.execute(select(User.email).where(User.user_id == case.user_id))
    ).scalar_one_or_none()
    # "First case" = this IS the user's earliest case (by created_at; junk uploads the member
    # removed don't count). `count <= 1` was only true while the user had exactly one case, so
    # a first case re-run after a second upload silently lost its trigger.
    earlier_cases = (
        await session.execute(
            select(func.count())
            .select_from(CaseFile)
            .where(
                CaseFile.user_id == case.user_id,
                CaseFile.case_file_id != case.case_file_id,
                CaseFile.soft_deleted_at.is_(None),
                CaseFile.created_at < case.created_at,
            )
        )
    ).scalar_one()
    findings = (
        (await session.execute(select(Finding).where(Finding.case_file_id == case.case_file_id)))
        .scalars()
        .all()
    )
    tier: int | None = None
    disagreement = False
    try:
        audit = await _assemble_result(str(case.case_file_id), composed="")
        tier = audit.disclosure.tier if audit.disclosure else None
        tn = audit.audit
        if tn is not None and tn.eob_member_responsibility is not None:
            eob, computed = float(tn.eob_member_responsibility), float(tn.tyndale_computed)
            disagreement = is_material(eob - computed, max(abs(eob), abs(computed)), AUDIT_FLAG)
    except Exception as exc:  # noqa: BLE001 — an un-projectable case still enqueues (band unknown)
        log.warning(
            "review.gather_facts.assemble_failed",
            case_file_id=str(case.case_file_id),
            error=str(exc),
        )
    return EnqueueFacts(
        terminal_status=status,
        incomplete_reason=incomplete_reason,
        confidence_band=confidence_band(tier),
        first_case=int(earlier_cases) == 0,
        system_error=(status == "audit_incomplete" and incomplete_reason == "system_error"),
        canary_flag=bool(tripwire_entries(case)),
        material_disagreement=disagreement,
        findings_count=len(findings),
        net_finding_usd=_net_usd(findings),
        documents_fingerprint=documents_fingerprint(case.documents, case.eobs),
        synthetic=is_synthetic_email(owner_email),
    )


async def lock_case(session: AsyncSession, case_file_id: uuid.UUID) -> None:
    """Serialize review-row writers for one case (row lock on case_files, held to commit). The
    latest review row can't be the lock: on a FIRST enqueue there is none to lock, and two
    concurrent terminal transitions would both insert run_seq=1 (now also a unique violation —
    uq_case_reviews_case_run)."""
    await session.execute(
        select(CaseFile.case_file_id).where(CaseFile.case_file_id == case_file_id).with_for_update()
    )


async def latest_review(
    session: AsyncSession, case_file_id: uuid.UUID, *, for_update: bool = False
) -> CaseReview | None:
    q = (
        select(CaseReview)
        .where(CaseReview.case_file_id == case_file_id)
        .order_by(CaseReview.run_seq.desc(), CaseReview.enqueued_at.desc())
        .limit(1)
    )
    if for_update:
        q = q.with_for_update()
    return (await session.execute(q)).scalar_one_or_none()


def _stamp(
    row: CaseReview, facts: EnqueueFacts, decision: EnqueueDecision, triggers: tuple[str, ...]
) -> None:
    row.terminal_status = facts.terminal_status
    row.incomplete_reason = facts.incomplete_reason
    row.confidence_band = facts.confidence_band
    row.triggers = list(triggers)
    row.sampled = decision.sampled
    row.first_case = facts.first_case
    row.system_error = facts.system_error
    row.canary_flag = facts.canary_flag
    row.material_disagreement = facts.material_disagreement
    row.findings_count = facts.findings_count
    row.net_finding_usd = facts.net_finding_usd
    row.documents_fingerprint = facts.documents_fingerprint


async def enqueue(
    session: AsyncSession,
    case: CaseFile,
    facts: EnqueueFacts,
    decision: EnqueueDecision,
) -> CaseReview | None:
    """Apply a decision to the case's review rows (see module docstring for the state rules).
    A re-run of a DECIDED case whose documents changed is always enqueued as re_review — the
    prior verdict is stale by definition, whatever the dial says."""
    if decision.skipped:
        return None  # refused by policy (synthetic identity) — not even the forced re-review
    await lock_case(session, case.case_file_id)
    latest = await latest_review(session, case.case_file_id, for_update=True)
    triggers = list(decision.triggers)
    documents_changed = (
        latest is not None and latest.documents_fingerprint != facts.documents_fingerprint
    )
    if latest is not None:
        triggers.append("re_run")
        if documents_changed:
            triggers.append("documents_changed")
    forced = latest is not None and latest.state in DECIDED_STATES and documents_changed
    if not (decision.enqueue or forced):
        return None
    now = datetime.now(timezone.utc)
    if latest is None:
        row = CaseReview(
            case_file_id=case.case_file_id, run_seq=1, state="unreviewed", enqueued_at=now
        )
        session.add(row)
    elif latest.state in DECIDED_STATES:
        row = CaseReview(
            case_file_id=case.case_file_id,
            run_seq=latest.run_seq + 1,
            state="re_review",
            prior_review_id=latest.review_id,
            enqueued_at=now,
        )
        session.add(row)
    else:
        row = latest
        row.run_seq = latest.run_seq + 1
        # A pending row that re-reviews a DECIDED predecessor stays a re_review when the case
        # runs again under it — re-stamping to 'unreviewed' erased the fact that a verdict
        # already exists upstream (and the reviewer's cue to read it).
        row.state = "re_review" if latest.prior_review_id is not None else "unreviewed"
        row.reviewer_id = None
        row.in_review_at = None
        row.enqueued_at = now
    _stamp(row, facts, decision, tuple(triggers))
    return row


async def on_terminal(case_file_id: str, status: str, incomplete_reason: str | None) -> str | None:
    """The orchestrator hook. Returns the review_id written (None when policy skipped the
    run). Never raises — a queue failure must not fail the audit that just finished."""
    if status not in TERMINAL_STATUSES:
        return None
    try:
        async with AsyncSessionLocal() as s:
            case = (
                await s.execute(
                    select(CaseFile).where(CaseFile.case_file_id == uuid.UUID(case_file_id))
                )
            ).scalar_one_or_none()
            if case is None:
                return None
            facts = await gather_facts(s, case, status, incomplete_reason)
            pct = await effective_sample_pct(s)
            decision = decide(facts, sample_pct=pct, roll=stable_roll(case.case_file_id))
            row = await enqueue(s, case, facts, decision)
            if decision.skipped == "synthetic":
                from app.analytics.emit import emit

                # Enum-only. The subject is the synthetic user itself (anonymity is reserved
                # for the statutory intake); the e2e teardown removes it with that identity.
                await emit(
                    "review_enqueue_skipped_synthetic",
                    user_id=case.user_id,
                    case_file_id=case.case_file_id,
                    properties={"terminal": status},
                )
                log.info("review.queue.skipped_synthetic", case_file_id=case_file_id)
                return None
            if row is None:
                log.info("review.queue.skipped", case_file_id=case_file_id, sample_pct=pct)
                return None
            await s.commit()
            log.info(
                "review.queue.enqueued",
                case_file_id=case_file_id,
                review_id=str(row.review_id),
                state=row.state,
                triggers=row.triggers,
                sampled=row.sampled,
            )
            return str(row.review_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("review.queue.failed", case_file_id=case_file_id, error=str(exc))
        return None


async def health(session: AsyncSession, *, now: datetime | None = None) -> dict:
    """The queue's health strip: pending count + median age, in_review count, and the
    approval rate over 7d/30d = approved / (approved + disapproved) — cant_verify is
    excluded from both sides (a null rate means nothing decided in the window)."""
    now = now or datetime.now(timezone.utc)
    pending_ages = (
        (
            await session.execute(
                select(CaseReview.enqueued_at).where(
                    CaseReview.state.in_(("unreviewed", "re_review"))
                )
            )
        )
        .scalars()
        .all()
    )
    in_review = (
        await session.execute(
            select(func.count()).select_from(CaseReview).where(CaseReview.state == "in_review")
        )
    ).scalar_one()
    ages_h = [max(0.0, (now - t).total_seconds() / 3600.0) for t in pending_ages if t is not None]
    out: dict = {
        "unreviewed": len(pending_ages),
        "in_review": int(in_review),
        "median_age_hours": round(statistics.median(ages_h), 1) if ages_h else None,
    }
    for days in (7, 30):
        since = now - timedelta(days=days)
        counts = dict(
            (
                await session.execute(
                    select(CaseReview.state, func.count())
                    .where(CaseReview.state.in_(("approved", "disapproved")))
                    .where(CaseReview.decided_at >= since)
                    .where(CaseReview.decided_at < now)
                    .group_by(CaseReview.state)
                )
            ).all()
        )
        approved, disapproved = int(counts.get("approved", 0)), int(counts.get("disapproved", 0))
        denom = approved + disapproved
        out[f"approved_{days}d"] = approved
        out[f"disapproved_{days}d"] = disapproved
        out[f"approval_rate_{days}d"] = round(approved / denom, 4) if denom else None
    return out
