"""Human Review Phase 1 — the reviewer queue + workspace + verdicts (doc 39 §1–§2 as
amended by §7, Brock 2026-09-17; built 2026-09-18).

Admin only (DL-60: non-admin → 404). Every workspace VIEW writes an audit-log event; every
verdict is append-only with the reviewer's UUID as actor. The queue policy itself lives in
app.review.queue (hooked from the orchestrator's status chokepoint) — these routes only read
rows and record decisions.

The workspace assembles its four tabs from EXISTING data only. Anything Phase 2 will add
(API pulls, live lookups, Missing / Retrieval-misses) is returned as a labeled placeholder,
never faked.
"""

from __future__ import annotations

import datetime
import re
import uuid
from typing import Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.db.models.admin_verdicts import AdminVerdict
from app.db.models.case_files import CaseFile
from app.db.models.case_reviews import CONFIDENCE_BANDS, REVIEW_STATES, CaseReview
from app.db.models.conversations import Conversation
from app.db.models.deadlines import Deadline
from app.db.models.feedback import FeedbackEvent
from app.db.models.findings import Finding
from app.db.models.messages import Message
from app.db.session import get_session
from app.review import queue as review_queue
from app.review.verdicts import DISAPPROVAL_TYPES, VerdictInput, VerdictRejected, record_verdict  # noqa: F401
from app.routes.admin._deps import admin_user, audit_admin_action
from app.routes.admin._deps import iso as _iso
from app.routes.admin.cases import _finding_dict, _load_case, case_provenance
from app.schemas.case_file import as_dict

log = structlog.get_logger()
router = APIRouter(tags=["v1-admin"])

_PHASE2_PLACEHOLDER = {"status": "coming_in_phase_2", "label": "Coming in Phase 2"}
_DOC_TEXT_KEYS = ("ocr_text", "full_text", "text_preview", "preview", "text")


def _mask(uid: uuid.UUID | str | None) -> str | None:
    """Masked user id for the queue (mockup: `u·8c41`) — never an email on the list page."""
    return f"u·{str(uid)[-4:]}" if uid else None


def _age_hours(t: datetime.datetime | None, now: datetime.datetime) -> float | None:
    if t is None:
        return None
    return round(max(0.0, (now - t).total_seconds() / 3600.0), 1)


def _document_set(cf: CaseFile) -> list[str]:
    """The queue row's document-set chip — the distinct classified types on the case, in upload
    order, cased by the Record's own label map ('Itemized bill', 'EOB', 'SBC'). A structured
    `eobs` row counts as an EOB even when it carries no document_type; an unclassified upload
    is listed LAST, because the reviewer should know it is there."""
    from app.routes.record import _doc_type_label

    labels: list[str] = []
    unclassified = False
    for kind, rows in (("document", cf.documents), ("eob", cf.eobs)):
        for d in rows or []:
            if not isinstance(d, dict):
                continue
            dt = d.get("document_type")
            if not isinstance(dt, str) or not dt or dt == "unclassified":
                if kind == "eob":
                    dt = "eob"
                else:
                    unclassified = True
                    continue
            label = _doc_type_label(dt)
            if label not in labels:
                labels.append(label)
    return [*labels, "Unclassified"] if unclassified else labels


def _case_line(cf: CaseFile | None) -> dict[str, Any]:
    """What makes a queue row findable. ONE source with the user's own Record row — the
    plausibility-gated provider (statement-ledger furniture never becomes a title) and the
    extracted service date — so the reviewer and the user are looking at the same label.
    There is deliberately no free-text 'service description': nothing gated produces one."""
    if cf is None:
        return {"provider": None, "service_date": None, "document_set": [], "intake_mode": None}
    from app.routes.record import _row_provider, _row_service_date

    return {
        "provider": _row_provider(cf),
        "service_date": _row_service_date(cf),
        "document_set": _document_set(cf),
        # doc 40 §D: both front doors are measured in ONE queue — this is the route that
        # opened the case ('guided' | 'chat_first'), and the queue filters on it.
        "intake_mode": cf.intake_mode,
    }


def _review_dict(
    r: CaseReview,
    *,
    now: datetime.datetime,
    verdict: AdminVerdict | None = None,
    user_id: uuid.UUID | None = None,
    case_file: CaseFile | None = None,
) -> dict[str, Any]:
    return {
        "review_id": str(r.review_id),
        "case_file_id": str(r.case_file_id),
        "user_masked": _mask(user_id),
        **_case_line(case_file),
        "run_seq": r.run_seq,
        "state": r.state,
        "terminal_status": r.terminal_status,
        "incomplete_reason": r.incomplete_reason,
        "confidence_band": r.confidence_band,
        "findings_count": r.findings_count,
        "net_finding_usd": float(r.net_finding_usd) if r.net_finding_usd is not None else None,
        "sampled": r.sampled,
        "triggers": list(r.triggers or []),
        "flags": {
            "first_case": r.first_case,
            "system_error": r.system_error,
            "canary": r.canary_flag,
            "guard_drop": bool(getattr(r, "guard_drop_flag", False)),
            "material_disagreement": r.material_disagreement,
        },
        "enqueued_at": _iso(r.enqueued_at),
        "age_hours": _age_hours(r.enqueued_at, now),
        "in_review_at": _iso(r.in_review_at),
        "decided_at": _iso(r.decided_at),
        "reviewer_masked": _mask(r.reviewer_id),
        "prior_review_id": str(r.prior_review_id) if r.prior_review_id else None,
        "verdict": (
            {
                "verdict_id": str(verdict.verdict_id),
                "verdict": verdict.verdict,
                "cause": verdict.cause,
            }
            if verdict is not None
            else None
        ),
    }


def _verdict_dict(v: AdminVerdict) -> dict[str, Any]:
    return {
        "verdict_id": str(v.verdict_id),
        "verdict": v.verdict,
        "notes": v.notes,
        "cause": v.cause,
        "structured_note": v.structured_note,
        "target_findings": v.target_findings,
        "target_response": v.target_response,
        "missed_findings": v.missed_findings,
        "hallucinated_claims": v.hallucinated_claims,
        "reviewer_masked": _mask(v.admin_user_id),
        "captured_at": _iso(v.captured_at),
    }


# ── queue ───────────────────────────────────────────────────────────────────────────────


@router.get("/admin/review/queue")
async def review_queue_list(
    state: str | None = Query(None, description="comma-separated review states"),
    verdict: str | None = Query(None, description="verdict type of decided rows"),
    confidence: str | None = Query(None, description="comma-separated bands"),
    has_system_error: bool | None = Query(None),
    canary: bool | None = Query(None, description="a planted fixture marker leaked (M6)"),
    guard_drop: bool | None = Query(None, description="a fabrication guard removed/downgraded something (M6)"),
    intake_mode: str | None = Query(None, description="guided | chat_first — the case's front door"),
    since: datetime.datetime | None = Query(None, description="enqueued_at >= (ISO)"),
    until: datetime.datetime | None = Query(None, description="enqueued_at < (ISO)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """The reviewer queue. Default order: pending rows first (unreviewed / re_review / in_review),
    oldest enqueued first — the mockup's 'oldest unreviewed at the top'."""
    now = datetime.datetime.now(datetime.timezone.utc)
    states: list[str] = []
    if state:
        states = [s.strip() for s in state.split(",") if s.strip()]
        bad = [s for s in states if s not in REVIEW_STATES]
        if bad:
            raise HTTPException(status_code=422, detail=f"unknown review state(s): {bad}")
    # Every filter EXCEPT state — shared by the page and by the pill counts, so a pill's N is
    # exactly the number of rows clicking it would list under the filters already applied.
    conds = []
    if verdict:
        conds.append(AdminVerdict.verdict == verdict)
    if confidence:
        bands = [b.strip() for b in confidence.split(",") if b.strip()]
        bad = [b for b in bands if b not in CONFIDENCE_BANDS]
        if bad:
            raise HTTPException(status_code=422, detail=f"unknown confidence band(s): {bad}")
        conds.append(CaseReview.confidence_band.in_(bands))
    if has_system_error is not None:
        conds.append(CaseReview.system_error.is_(has_system_error))
    if canary is not None:
        conds.append(CaseReview.canary_flag.is_(canary))
    if guard_drop is not None:
        conds.append(CaseReview.guard_drop_flag.is_(guard_drop))
    if intake_mode:
        from app.intake.mode import INTAKE_MODES

        if intake_mode not in INTAKE_MODES:
            raise HTTPException(status_code=422, detail=f"unknown intake_mode: {intake_mode!r}")
        conds.append(CaseFile.intake_mode == intake_mode)
    if since is not None:
        conds.append(CaseReview.enqueued_at >= since)
    if until is not None:
        conds.append(CaseReview.enqueued_at < until)

    q = (
        select(CaseReview, AdminVerdict, CaseFile)
        .join(CaseFile, CaseFile.case_file_id == CaseReview.case_file_id)
        .outerjoin(AdminVerdict, AdminVerdict.verdict_id == CaseReview.verdict_id)
        .where(*conds)
    )
    if states:
        q = q.where(CaseReview.state.in_(states))
    pending_first = case((CaseReview.state.in_(review_queue.PENDING_STATES), 0), else_=1)
    rows = (
        await session.execute(
            q.order_by(pending_first, CaseReview.enqueued_at.asc()).limit(limit).offset(offset)
        )
    ).all()
    items = [
        _review_dict(r, now=now, verdict=v, user_id=cf.user_id, case_file=cf) for r, v, cf in rows
    ]
    counted = (
        await session.execute(
            select(CaseReview.state, func.count())
            .join(CaseFile, CaseFile.case_file_id == CaseReview.case_file_id)
            .outerjoin(AdminVerdict, AdminVerdict.verdict_id == CaseReview.verdict_id)
            .where(*conds)
            .group_by(CaseReview.state)
        )
    ).all()
    state_counts = {s: 0 for s in REVIEW_STATES}  # every pill renders, zero included
    state_counts.update({s: int(n) for s, n in counted})
    return {
        "items": items,
        "count": len(items),
        "limit": limit,
        "offset": offset,
        "state_counts": state_counts,
        "health": await review_queue.health(session, now=now),
    }


# ── settings (the dial) ──────────────────────────────────────────────────────────────────


class ReviewSettingsRequest(BaseModel):
    review_sample_pct: int = Field(ge=0, le=100)


@router.get("/admin/review/settings")
async def review_settings(
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    from app.config import get_settings

    s = get_settings()
    return {
        "review_sample_pct": await review_queue.effective_sample_pct(session),
        "env_default_pct": s.review_sample_pct,
        "triggers": {
            "first_case": s.review_trigger_first_case,
            "low_confidence": s.review_trigger_low_confidence,
            "system_error": s.review_trigger_system_error,
            "canary": s.review_trigger_canary,
            "guard_drop": s.review_trigger_guard_drop,
            "material_disagreement": s.review_trigger_material_disagreement,
        },
    }


@router.put("/admin/review/settings")
async def update_review_settings(
    body: ReviewSettingsRequest,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    pct = await review_queue.set_sample_pct(session, body.review_sample_pct, admin_id=admin.user_id)
    await audit_admin_action(
        session, admin=admin, action="review_settings", extra={"review_sample_pct": pct}
    )
    await session.commit()
    return {"review_sample_pct": pct}


# ── workspace ────────────────────────────────────────────────────────────────────────────


def _codes_in(obj: Any) -> list[str]:
    """Code-like strings a finding's facts already name (BASIS codes) — collected from the
    keys the agents write today; nothing is inferred."""
    out: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("code", "cpt", "cpt_code", "hcpcs", "procedure_code") and isinstance(v, str):
                out.append(v)
            elif k in ("codes", "reference_codes", "cpt_codes", "basis_codes") and isinstance(
                v, list
            ):
                out.extend(str(x) for x in v if isinstance(x, (str, int)))
            elif isinstance(v, (dict, list)):
                out.extend(_codes_in(v))
    elif isinstance(obj, list):
        for x in obj:
            out.extend(_codes_in(x))
    seen: set[str] = set()
    return [c for c in out if not (c in seen or seen.add(c))]


def _first_str(d: dict, *keys: str) -> str | None:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _rule_effective_date(facts: dict, claim: dict) -> str | None:
    """When the rule the finding rests on took effect — from the finding's own facts/claim, else
    from the first citation that carries one (retrieval stamps effective_date on its chunks)."""
    direct = _first_str(facts, "rule_effective_date", "effective_date") or _first_str(
        claim, "rule_effective_date", "effective_date", "effective_date_start"
    )
    if direct:
        return direct
    raw = claim.get("citations") or claim.get("citation") or []
    for c in raw if isinstance(raw, list) else [raw]:
        if isinstance(c, dict):
            found = _first_str(c, "effective_date", "effective_date_start", "rule_effective_date")
            if found:
                return found
    return None


def _confidence_of(facts: dict, claim: dict, rec: dict) -> float | str | None:
    for src in (facts, claim, rec):
        v = src.get("confidence")
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _why_lines(f: Finding) -> list[dict[str, Any]]:
    """The per-finding 'why' expander: each line read from a field the agents already persist.
    A missing field is null — the console renders 'not recorded'. Never synthesized. The rule's
    effective date and the confidence are the two lines that let a reviewer tell
    stale_data_source from reasoning_error (deep review)."""
    facts = as_dict(f.facts) or {}
    claim = as_dict(f.legal_claim) or {}
    rec = as_dict(f.recommendation) or {}
    numbers = {
        k: facts[k]
        for k in ("billed_amount", "allowed_amount", "eob_member_responsibility", "computed", "gap")
        if isinstance(facts.get(k), (int, float))
    }
    return [
        {
            "key": "observed",
            "label": "What the documents show",
            "value": _first_str(facts, "observation", "description", "evidence", "notes"),
        },
        {
            "key": "rule",
            "label": "Rule applied",
            "value": _first_str(claim, "claim", "rule", "text"),
        },
        {"key": "numbers", "label": "Numbers compared", "value": numbers or None},
        {
            "key": "action",
            "label": "Recommended action",
            "value": _first_str(rec, "action", "reasoning"),
        },
        {
            "key": "producer",
            "label": "Produced by",
            "value": f"{f.subagent_source} · tier {f.voice_tier}" if f.subagent_source else None,
        },
        {
            "key": "rule_effective_date",
            "label": "Rule effective date",
            "value": _rule_effective_date(facts, claim),
        },
        {"key": "confidence", "label": "Confidence", "value": _confidence_of(facts, claim, rec)},
    ]


_CHUNK_TEXT_KEYS = ("text", "content", "chunk_text", "body", "passage")
_CHUNK_ID_KEYS = ("src_id", "source_id", "id", "chunk_id")
_CHUNK_TEXT_CAP = 1600


def _chunk_index(chunks: list[Any]) -> dict[str, dict]:
    """Retrieved knowledge chunks (from the run's audit events) keyed by every id a citation may
    use — the Stop hook resolves markers on src_id / source_id / id, so the same keys here."""
    index: dict[str, dict] = {}
    for c in chunks:
        if isinstance(c, dict):
            for k in _CHUNK_ID_KEYS:
                if c.get(k) not in (None, ""):
                    index.setdefault(str(c[k]), c)
    return index


def _citation_source(src_id: str, chunks: dict[str, dict], doc_cards: list[dict]) -> dict[str, Any]:
    """What a citation chip opens (doc 39 §2: 'tap to open the cited source'): one of the CASE'S
    documents when the id names one, else the knowledge chunk the run retrieved — its text is
    corpus content, not PHI. 'unresolved' is said plainly; nothing is fetched or guessed."""
    for card in doc_cards:
        did = card.get("document_id")
        if did and (src_id == did or src_id.startswith(f"{did}:") or src_id.startswith(f"doc:{did}")):
            page = re.search(r"(?:^|[:#])p(?:age)?[=:]?(\d+)", src_id)
            return {"kind": "document", "doc_index": card["doc_index"], "document_id": did,
                    "page": int(page.group(1)) if page else None}
    chunk = chunks.get(src_id)
    if chunk is None:
        return {"kind": "unresolved"}
    text = next((chunk[k] for k in _CHUNK_TEXT_KEYS if isinstance(chunk.get(k), str) and chunk[k].strip()), None)
    return {
        "kind": "chunk",
        "collection": _first_str(chunk, "collection", "collection_name", "corpus"),
        "title": _first_str(chunk, "title", "authority", "heading", "section"),
        "effective_date": _first_str(chunk, "effective_date", "effective_date_start"),
        "last_verified": _first_str(chunk, "last_verified", "verified_at", "as_of"),
        "text": text[:_CHUNK_TEXT_CAP] if text else None,
        "truncated": bool(text and len(text) > _CHUNK_TEXT_CAP),
    }


def _citations_of(f: Finding, chunks: dict[str, dict], doc_cards: list[dict]) -> list[dict]:
    from app.agents.orchestrator import _project_citations

    claim = as_dict(f.legal_claim) or {}
    raw = claim.get("citations") or claim.get("citation") or []
    try:
        projected = [c.model_dump() for c in _project_citations(raw)]
    except Exception:  # noqa: BLE001 — a malformed citation renders as none, not a 500
        return []
    for c in projected:
        c["source"] = _citation_source(str(c.get("src_id") or ""), chunks, doc_cards)
    return projected


def _analysis_finding(f: Finding, chunks: dict[str, dict], doc_cards: list[dict]) -> dict[str, Any]:
    facts = as_dict(f.facts) or {}
    d = _finding_dict(f)
    d.update(
        {
            "responsible_party": facts.get("responsible_party") or "either",
            "amount_usd": facts.get("gap") if isinstance(facts.get("gap"), (int, float)) else None,
            "basis_codes": _codes_in(facts),
            "citations": _citations_of(f, chunks, doc_cards),
            "confidence": _confidence_of(
                facts, as_dict(f.legal_claim) or {}, as_dict(f.recommendation) or {}
            ),
            # The ANALYST'S internal reasoning (Bill Detective / Math Person write it to
            # facts.notes) — what the "Analyst notes · internal" card is for. Null = the agent
            # recorded none; the console says "not recorded". A REVIEWER'S verdict note is a
            # different thing and lives only in the verdict history.
            "analyst_notes": _first_str(facts, "analyst_notes", "notes", "reasoning"),
            "why": _why_lines(f),
            "created_at": _iso(f.created_at),
        }
    )
    return d


# ── the provenance sections that were silently absent ────────────────────────────────────
_PRICING_TOOL = re.compile(r"cost_estimate|pricing|fee_schedule|medicare_pfs|_mrf|tic_|benchmark", re.I)


def _user_answers(cf: CaseFile) -> list[dict[str, Any]]:
    """What the USER told us (doc 39 §7-2a: 'user answers/attestations (timestamped)'): encounter
    confirmations, checklist values they typed (with the provenance stamp the coverage-input
    route writes), and the name-mismatch attestation. A timestamp we never stored is null."""
    items = {str(li.get("line_item_id")): li for li in (cf.line_items or []) if isinstance(li, dict)}
    out: list[dict[str, Any]] = []
    for c in getattr(cf, "encounter_confirmations", None) or []:
        if not isinstance(c, dict):
            continue
        li = items.get(str(c.get("line_item_id")), {})
        out.append({
            "kind": "encounter_confirmation",
            "label": _first_str(li, "plain_language_translation", "raw_description") or "line item",
            "code": _first_str(li, "code"),
            "value": c.get("response"),
            "note": c.get("user_note"),
            "at": c.get("confirmed_at") or c.get("at"),
        })
    coverage = cf.coverage if isinstance(cf.coverage, dict) else {}
    for field, prov in (coverage.get("user_input_provenance") or {}).items():
        if isinstance(prov, dict):
            out.append({
                "kind": "coverage_input",
                "label": field,
                "code": None,
                "value": "not sure" if prov.get("not_sure") else coverage.get(field),
                "note": prov.get("source"),
                "at": prov.get("at"),
            })
    status = getattr(cf, "attest_status", None)
    if status and status != "not_required":
        attested_at = getattr(cf, "attested_at", None)
        out.append({"kind": "attestation", "label": "patient-name attestation", "code": None,
                    "value": status, "note": None, "at": _iso(attested_at) if attested_at else None})
    return out


def _priors_applied(audit: dict | None) -> list[dict[str, Any]]:
    """Priors the rung-2 engine swept for inputs the documents did not state — value · tier ·
    resulting range (doc 39 §7-2a). Deterministic: the missing inputs come from the disclosure,
    the priors from the table the engine itself reads."""
    from app.sources.missing_data_priors import MISSING_DATA_PRIORS

    disclosure = (audit or {}).get("disclosure") or {}
    three = (audit or {}).get("audit") or {}
    low, high = three.get("tyndale_computed_low"), three.get("tyndale_computed_high")
    out: list[dict[str, Any]] = []
    for key in disclosure.get("missing_inputs") or []:
        prior = MISSING_DATA_PRIORS.get(key)
        if prior is None:
            continue
        out.append({
            "input": key, "low": prior.low, "base": prior.base, "high": prior.high, "unit": prior.unit,
            "source": prior.source, "as_of": prior.as_of, "placeholder": prior.placeholder,
            "tier": disclosure.get("tier"),
            "resulting_range": {"low": low, "high": high} if low is not None and high is not None else None,
        })
    return out


def _pricing_reference(tools_called: list[dict]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for tc in tools_called:
        names = [n for n in (tc.get("tools_invoked") or []) if isinstance(n, str) and _PRICING_TOOL.search(n)]
        if not names:
            continue
        result = tc.get("result") if isinstance(tc.get("result"), dict) else {}
        out.append({
            "tool": names[0], "outcome": tc.get("outcome"), "at": tc.get("timestamp"),
            "source": _first_str(result, "source", "dataset", "data_source"),
            "as_of": _first_str(result, "as_of", "effective_date", "data_as_of"),
        })
    return out


def _document_cards(cf: CaseFile) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(documents, eobs) as cards sharing ONE doc_index namespace."""
    docs = [d for d in (cf.documents or []) if isinstance(d, dict)]
    eobs = [d for d in (cf.eobs or []) if isinstance(d, dict)]
    doc_cards = [_document_card(i, d, kind="document", doc_index=i) for i, d in enumerate(docs)]
    eob_cards = [
        _document_card(i, d, kind="eob", doc_index=len(docs) + i) for i, d in enumerate(eobs)
    ]
    return doc_cards, eob_cards


def _document_card(i: int, d: dict, *, kind: str, doc_index: int) -> dict[str, Any]:
    """A text-free view of one stored document. ``doc_index`` is unique across documents AND
    eobs (the two lists used to number from 0 independently, so documents[0] and eobs[0]
    collided on `index`); ``index`` stays the position within its own list."""
    text_len = next((len(d[k]) for k in _DOC_TEXT_KEYS if isinstance(d.get(k), str)), 0)
    if not text_len and isinstance(d.get("ocr_text_chars"), int):
        text_len = d["ocr_text_chars"]
    return {
        "doc_index": doc_index,
        "kind": kind,  # document | eob
        "index": i,
        "document_id": d.get("document_id"),
        "has_text": text_len > 0,
        "document_type": d.get("document_type"),
        "filename": d.get("filename") or d.get("name"),
        "uploaded_at": d.get("uploaded_at") or d.get("created_at"),
        "page_count": d.get("page_count") or d.get("pages"),
        "text_chars": text_len,
        "claim_number": d.get("claim_number"),
        "account_number": d.get("account_number"),
        "extraction_status": d.get("extraction_status") or d.get("status"),
    }


async def _journey(session: AsyncSession, cf: CaseFile) -> list[dict[str, Any]]:
    """The user's journey as the server knows it: the audit-lifecycle analytics events for
    this case (emitted from the status chokepoint), oldest first. Enum/number only by
    construction of the analytics registry."""
    from app.db.models.analytics_events import AnalyticsEvent

    rows = (
        (
            await session.execute(
                select(AnalyticsEvent)
                .where(AnalyticsEvent.case_file_id == cf.case_file_id)
                .order_by(AnalyticsEvent.occurred_at.asc())
            )
        )
        .scalars()
        .all()
    )
    return [
        {"event": r.event_name, "at": _iso(r.occurred_at), "properties": r.properties or {}}
        for r in rows
    ]


@router.get("/admin/review/cases/{case_file_id}")
async def review_workspace(
    case_file_id: str,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """The three-pane workspace. READ-ONLY with respect to the review row: a GET (a view, a
    prefetch, a second reviewer glancing at a case) must not claim it — that is
    POST …/claim, called on intent. Every open still writes a review_view audit event."""
    from app.agents.orchestrator import _assemble_result, tripwire_entries
    from app.routes.conversations import message_to_out
    from app.sources.call_identifiers import of_case
    from app.sources.gameplan import build_gameplan

    cf = await _load_case(session, case_file_id)
    now = datetime.datetime.now(datetime.timezone.utc)
    review = await review_queue.latest_review(session, cf.case_file_id)
    await audit_admin_action(
        session,
        admin=admin,
        action="review_view",
        target_user_id=cf.user_id,
        case_file_id=cf.case_file_id,
        extra={
            "review_id": str(review.review_id) if review else None,
            "state": review.state if review else None,
        },
    )
    await session.commit()

    findings = (
        (
            await session.execute(
                select(Finding)
                .where(Finding.case_file_id == cf.case_file_id)
                .order_by(Finding.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    messages = (
        (
            await session.execute(
                select(Message)
                .join(Conversation, Message.conversation_id == Conversation.conversation_id)
                .where(Conversation.case_id == cf.case_file_id)
                .order_by(Message.created_at.asc(), Message.sequence_number.asc())
            )
        )
        .scalars()
        .all()
    )
    deadlines = (
        (await session.execute(select(Deadline).where(Deadline.case_file_id == cf.case_file_id)))
        .scalars()
        .all()
    )
    feedback = (
        (
            await session.execute(
                select(FeedbackEvent)
                .where(FeedbackEvent.case_file_id == cf.case_file_id)
                .order_by(FeedbackEvent.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    verdicts = (
        (
            await session.execute(
                select(AdminVerdict)
                .where(AdminVerdict.case_file_id == cf.case_file_id)
                .order_by(AdminVerdict.captured_at.desc())
            )
        )
        .scalars()
        .all()
    )
    chain = (
        (
            await session.execute(
                select(CaseReview)
                .where(CaseReview.case_file_id == cf.case_file_id)
                .order_by(CaseReview.run_seq.asc())
            )
        )
        .scalars()
        .all()
    )

    audit: dict | None = None
    try:
        audit = (await _assemble_result(str(cf.case_file_id), composed="")).model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001 — the rest of the workspace still renders
        log.warning("review.workspace.assemble_failed", case_file_id=case_file_id, error=str(exc))

    ids = of_case(cf)
    doc_cards, eob_cards = _document_cards(cf)
    provenance = await case_provenance(case_file_id, admin=admin, session=session)
    # The legacy provenance route returns the raw document entries — OCR text included. The
    # workspace's contract is "never the OCR text": the reviewer's viewer fetches text
    # explicitly (prompt 3/3), so here the documents are the same text-free cards as the left
    # pane (char counts + has_text).
    provenance["documents"] = [*doc_cards, *eob_cards]
    chunks = _chunk_index(provenance.get("qdrant_chunks_retrieved") or [])
    provenance.update(
        {
            "tripwires": tripwire_entries(cf),
            "research_log": cf.research_log or [],
            # Three sections doc 39 §7-2a lists that were neither rendered nor placeholdered.
            # All three come from data that IS persisted, so an empty list means "none on this
            # run" — different from the four below, which are not collected at all yet.
            "user_answers": _user_answers(cf),
            "priors_applied": _priors_applied(audit),
            "pricing_reference": _pricing_reference(provenance.get("tools_called") or []),
            "api_pulls": _PHASE2_PLACEHOLDER,
            "live_lookups": _PHASE2_PLACEHOLDER,
            "missing_data": _PHASE2_PLACEHOLDER,
            "retrieval_misses": _PHASE2_PLACEHOLDER,
        }
    )
    outcomes = [
        {
            "feedback_type": fb.feedback_type,
            "created_at": _iso(fb.created_at),
            "payload": fb.payload,
        }
        for fb in feedback
        if fb.feedback_type == "outcome_report"
        or (isinstance(fb.payload, dict) and fb.payload.get("call_outcome"))
    ]
    verdict_by_id = {v.verdict_id: v for v in verdicts}
    return {
        "viewer": {"masked": _mask(admin.user_id)},
        "case": {
            "case_file_id": str(cf.case_file_id),
            "user_masked": _mask(cf.user_id),
            **_case_line(cf),  # the same provider · service date · document set the queue row shows
            "status": cf.status,
            "incomplete_reason": cf.audit_incomplete_reason,
            "intake_status": getattr(cf, "intake_status", None),
            "created_at": _iso(cf.created_at),
            "updated_at": _iso(cf.updated_at),
        },
        "review": _review_dict(
            review,
            now=now,
            verdict=verdict_by_id.get(review.verdict_id),
            user_id=cf.user_id,
            case_file=cf,
        )
        if review
        else None,
        "review_chain": [
            _review_dict(
                r,
                now=now,
                verdict=verdict_by_id.get(r.verdict_id),
                user_id=cf.user_id,
                case_file=cf,
            )
            for r in chain
        ],
        "left": {
            "documents": doc_cards,
            "eobs": eob_cards,
            "extraction": {
                "line_items": cf.line_items or [],
                "coverage": cf.coverage or {},
                "encounter_confirmations": getattr(cf, "encounter_confirmations", None) or [],
            },
            "journey": await _journey(session, cf),
        },
        "tabs": {
            "analysis": {
                "three_numbers": (audit or {}).get("audit"),
                "disclosure": (audit or {}).get("disclosure"),
                "summary": (audit or {}).get("summary") or "",
                # e2e re-test 2026-09-23 item 1: a complete audit whose summary is still owed
                # (the audit_retry cron writes it) — attempts spent so far, next attempt due.
                "summary_pending": bool(getattr(cf, "summary_pending", False)),
                "summary_retry_attempts": int(getattr(cf, "summary_retry_attempts", 0) or 0),
                "summary_retry_after": _iso(getattr(cf, "summary_retry_after", None)),
                "result_status": (audit or {}).get("status"),
                "documents_needed": (audit or {}).get("documents_needed") or [],
                "findings": [
                    _analysis_finding(f, chunks, [*doc_cards, *eob_cards]) for f in findings
                ],
            },
            "conversation": [message_to_out(m).model_dump(mode="json") for m in messages],
            "results": {
                "gameplan": [g.model_dump(mode="json") for g in build_gameplan(findings, ids)],
                "identifiers": {
                    "claim_number": ids.claim_number,
                    "account_number": ids.account_number,
                    "provider_phone": ids.provider_phone,
                    "payer_phone": ids.payer_phone,
                },
                "tiers": [
                    {
                        "finding_id": str(f.finding_id),
                        "voice_tier": f.voice_tier,
                        "tier_a_facts": as_dict(f.facts) or {},
                        "tier_b_claim": f.legal_claim,
                        "tier_c_recommendation": f.recommendation,
                    }
                    for f in findings
                ],
                "deadlines": [
                    {
                        "deadline_id": str(d.deadline_id),
                        "deadline_date": d.deadline_date.isoformat() if d.deadline_date else None,
                        "deadline_type": d.deadline_type,
                        "status": d.status,
                    }
                    for d in deadlines
                ],
                "outcomes": outcomes,
            },
            "provenance": provenance,
        },
        "verdicts": [_verdict_dict(v) for v in verdicts],
    }


# ── document viewer ──────────────────────────────────────────────────────────────────────
# Doc 39 §2: the source documents are "the reviewer's ground truth" — a verdict without seeing
# the document isn't a review. READS only (no new storage of PHI), admin-gated like everything
# here, and every open is its own audit event: looking at a patient's bill is an access that
# must be accountable separately from opening the case.


def _find_document(cf: CaseFile, doc_key: str) -> tuple[dict, dict] | None:
    """(raw entry, its card) for a document on THIS case — by document_id, or `idx-<doc_index>`
    for entries older than document_id. The key never reaches storage; only the entry's own
    uri does, and read_stored refuses anything outside our store."""
    docs = [d for d in (cf.documents or []) if isinstance(d, dict)]
    eobs = [d for d in (cf.eobs or []) if isinstance(d, dict)]
    doc_cards, eob_cards = _document_cards(cf)
    for entry, card in zip([*docs, *eobs], [*doc_cards, *eob_cards], strict=True):
        if doc_key == f"idx-{card['doc_index']}" or (entry.get("document_id") and doc_key == entry["document_id"]):
            return entry, card
    return None


async def _audit_document_view(session, admin, cf: CaseFile, card: dict, part: str) -> None:
    await audit_admin_action(
        session,
        admin=admin,
        action="review_document_view",
        target_user_id=cf.user_id,
        case_file_id=cf.case_file_id,
        extra={"document_id": card.get("document_id"), "doc_index": card["doc_index"],
               "kind": card["kind"], "part": part},
    )
    await session.commit()


@router.get("/admin/review/cases/{case_file_id}/documents/{doc_key}")
async def review_document(
    case_file_id: str,
    doc_key: str,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """The stored file itself, served inline with the content-type its magic bytes give it."""
    from app.routes.upload import read_stored, stored_media_type

    cf = await _load_case(session, case_file_id)
    found = _find_document(cf, doc_key)
    if found is None:
        raise HTTPException(status_code=404, detail="no such document on this case")
    entry, card = found
    content = await read_stored(entry.get("uri"))
    if content is None:
        raise HTTPException(status_code=404, detail="the stored file is unavailable")
    await _audit_document_view(session, admin, cf, card, "file")
    return Response(
        content=content,
        media_type=stored_media_type(content),
        headers={
            "Content-Disposition": "inline",
            "Cache-Control": "no-store",  # PHI: never in a shared or disk cache
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/admin/review/cases/{case_file_id}/documents/{doc_key}/text")
async def review_document_text(
    case_file_id: str,
    doc_key: str,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """The OCR text the audit actually read — the viewer's toggle. The workspace payload never
    carries it ('never the OCR text'); it is fetched here, explicitly, and audited."""
    cf = await _load_case(session, case_file_id)
    found = _find_document(cf, doc_key)
    if found is None:
        raise HTTPException(status_code=404, detail="no such document on this case")
    entry, card = found
    text = next((entry[k] for k in _DOC_TEXT_KEYS if isinstance(entry.get(k), str) and entry[k]), "")
    await _audit_document_view(session, admin, cf, card, "text")
    return {**card, "text": text, "chars": len(text)}


# ── claim ────────────────────────────────────────────────────────────────────────────────


class ClaimRequest(BaseModel):
    # "Claimed by u·8c41 — take over?" The default never steals; a take-over is a deliberate,
    # audited reassignment (doc 39 §7-2e: two reviewers at launch, no assignment machinery).
    take_over: bool = False


@router.post("/admin/review/cases/{case_file_id}/claim")
async def review_claim(
    case_file_id: str,
    body: ClaimRequest | None = None,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Take a pending run for review — explicit, and idempotent. A pending unclaimed row
    (unreviewed / re_review) becomes in_review under the caller; calling again is a no-op; a
    row another reviewer holds is NOT stolen (``claimed`` false, their masked id returned); a
    decided row is never downgraded. Always returns the current state and reviewer."""
    cf = await _load_case(session, case_file_id)
    await review_queue.lock_case(session, cf.case_file_id)
    review = await review_queue.latest_review(session, cf.case_file_id, for_update=True)
    if review is None:
        raise HTTPException(status_code=404, detail="no review row for this case")
    claimed = False
    if review.state in ("unreviewed", "re_review"):
        review.state = "in_review"
        review.reviewer_id = admin.user_id
        review.in_review_at = datetime.datetime.now(datetime.timezone.utc)
        claimed = True
        await audit_admin_action(
            session,
            admin=admin,
            action="review_claim",
            target_user_id=cf.user_id,
            case_file_id=cf.case_file_id,
            extra={"review_id": str(review.review_id)},
        )
    elif (
        review.state == "in_review"
        and review.reviewer_id != admin.user_id
        and body is not None
        and body.take_over
    ):
        previous = review.reviewer_id
        review.reviewer_id = admin.user_id
        review.in_review_at = datetime.datetime.now(datetime.timezone.utc)
        claimed = True
        await audit_admin_action(
            session,
            admin=admin,
            action="review_claim_takeover",
            target_user_id=cf.user_id,
            case_file_id=cf.case_file_id,
            extra={"review_id": str(review.review_id), "from_reviewer": _mask(previous)},
        )
    mine = review.reviewer_id == admin.user_id
    await session.commit()
    return {
        "review_id": str(review.review_id),
        "state": review.state,
        "claimed": claimed,
        "held_by_me": bool(mine and review.state == "in_review"),
        "reviewer_masked": _mask(review.reviewer_id),
    }


# ── verdicts ─────────────────────────────────────────────────────────────────────────────


class StructuredNote(BaseModel):
    concluded: str
    should_have_concluded: str
    input_or_rule: str


class ReviewVerdictRequest(BaseModel):
    action: Literal["approve", "disapprove", "cant_verify"]
    note: str | None = None
    verdict_type: str | None = None  # disapprove only — one of DISAPPROVAL_TYPES
    scope: Literal["whole_case", "findings"] | None = None  # disapprove only
    target_findings: list[str] | None = None  # scope == findings
    cause: str | None = None  # disapprove only — exactly one of CAUSES
    structured_note: StructuredNote | None = None  # disapprove only


@router.post("/admin/review/cases/{case_file_id}/verdict")
async def review_verdict(
    case_file_id: str,
    body: ReviewVerdictRequest,
    admin: CurrentUser = Depends(admin_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Approve (optional note) / Disapprove… (type + scope + one cause + structured note) /
    Can't verify (unable_to_verify — excluded from the approval rate). Append-only: a new
    admin_verdicts row every time, the review row moves to the decided state. The work lives in
    app.review.verdicts.record_verdict — the legacy cases route is a strict alias of it."""
    cf = await _load_case(session, case_file_id)
    try:
        return await record_verdict(
            session,
            admin=admin,
            cf=cf,
            via="review",
            v=VerdictInput(
                action=body.action,
                note=body.note,
                verdict_type=body.verdict_type,
                scope=body.scope,
                target_findings=body.target_findings,
                cause=body.cause,
                structured_note=body.structured_note.model_dump() if body.structured_note else None,
            ),
        )
    except VerdictRejected as exc:
        raise HTTPException(status_code=422, detail=exc.problems) from exc
