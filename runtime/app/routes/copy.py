"""GET /v1/copy/{surface} — authored copy for screens that have no case thread yet.

Thread strings reach the client inside message payloads, but the upload screen renders BEFORE
a case exists, so its copy had nowhere to come from — which is why Brock's §1.2/§1.3 strings sat
authored-but-unrendered. Serving them from the registry (rather than hardcoding them in the app)
keeps ONE source of truth and keeps them inside the drift guard.

Surfaces are named and closed — this is not a general "read any key" endpoint.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.agents.context_loader import PLACEHOLDER_PREFIX, orchestration_step
from app.config import get_settings

router = APIRouter(tags=["v1"])

# surface -> {client field: registry key}
_SURFACES: dict[str, dict[str, str]] = {
    "upload": {
        "record_frame": "record_first_upload_frame",  # §1.1
        "trust_microcopy": "upload_trust_microcopy",  # §1.2  (C4)
        "just_the_bill": "upload_just_the_bill",  # §1.3  (C3)
        # Camera capture (N1 · C1/C5). Unauthored today — see _is_renderable: a placeholder is
        # withheld like a missing key, so the client shows its own label instead of shipping
        # "[PLACEHOLDER-eng] Retake" to a user.
        "capture_prompt_bill": "capture.prompt_bill",
        "capture_prompt_card": "capture.prompt_card",
        "capture_looks_good": "capture.looks_good",
        "capture_retake": "capture.retake",
        "capture_add_page": "capture.add_page",
    },
    # Dashboard check-in chips (Brock mockups item 5) — client-rendered on the follow-up
    # card; the three route chips are Brock's own mockup words, seeded + PROPOSED.
    "home": {
        "checkin_fixing_it": "checkin.fixing_it",
        "checkin_pushed_back": "checkin.pushed_back",
        "checkin_left_message": "checkin.left_message",
    },
    "status": {
        "leave_and_return": "status_leave_and_return",  # §2.2  (D3)
        "long_wait": "long_wait",  # §2.3
    },
    # Settings copy (2026-08-19, item 1+): unauthored keys are simply ABSENT from the
    # registry (the capture-keys precedent — missing is withheld and the client falls back
    # to its own label; a [PLACEHOLDER-eng] seed would block the staging boot beyond the
    # deliberate §3.11 pair). Queued in the Brock asks inventory.
    "settings": {
        "notifications_email_label": "settings.notifications_email_label",
        "notifications_email_description": "settings.notifications_email_description",
        "notifications_sms_label": "settings.notifications_sms_label",
        "notifications_sms_coming_soon": "settings.notifications_sms_coming_soon",
        # Plan documents (item 5) — same absent-from-registry stance as the keys above:
        # unauthored keys are WITHHELD server-side (never [PLACEHOLDER-eng], which blocks
        # the staging boot beyond the deliberate §3.11 pair); client fallbacks render.
        "plan_documents_title": "settings.plan_documents_title",
        "plan_documents_description": "settings.plan_documents_description",
        "plan_documents_empty": "settings.plan_documents_empty",
        "plan_documents_sbc_on_file": "settings.plan_documents_sbc_on_file",
    },
    # Freeform "Ask Tyndale" opener (Brock 2026-08-22, item 4): a client-rendered scripted
    # first bubble + four choice chips. Registry keys (UNMAPPED/PROPOSED, shippable seed
    # copy) so Brock owns the words and the drift guard covers them once authored.
    "chat": {
        "opener": "freeform_opener",
        "opener_chips": "freeform_opener_chips",
    },
    # Statutory-rights intake (§A2 state 5). Served as a surface because the screen renders
    # BEFORE — and often without — a session: the person exercising the right may not have an
    # account, or may be asking us to delete it.
    "access_request": {
        "settings_label": "access_request.settings_label",
        "intro": "access_request.intro",
        "type_label": "access_request.form_type_label",
        "name_label": "access_request.form_name_label",
        "contact_label": "access_request.form_contact_label",
        "details_label": "access_request.form_details_label",
        "submit": "access_request.form_submit",
    },
}


def _leave_and_return_is_honest() -> bool:
    """§2.2 promises "I'll email you the moment it's ready".

    We only make that promise if we can keep it. The email now EXISTS
    (`app/notify/audit_ready.py`, sent on both terminal outcomes), so the gate is simply
    whether this environment sends it. Withheld while off — a false "we'll email you" strands
    the user worse than silence, which is the close-the-loop/X1 point.

    Gated on `enable_audit_ready_email`, not `enable_nudge_emails`: the nudge is a +3d
    reminder about a missing document, a different promise. Using it here would have let the
    line render off the wrong switch.
    """
    return bool(get_settings().enable_audit_ready_email)


def _is_renderable(text: str) -> bool:
    """False for anything that isn't authored copy yet.

    Two non-strings look like strings here: the loader's `<MISSING-script: key>` marker, and an
    engineering `[PLACEHOLDER-eng]` seed. Both are scaffolding — a placeholder exists so the
    staging/prod boot gate can BLOCK on it (config.assert_production_safety), not so a dev user
    reads it off a button. Withholding both lets a client fall back to its own label.
    """
    return not text.startswith("<MISSING-script:") and not text.startswith(PLACEHOLDER_PREFIX)


@router.get("/copy/{surface}")
async def get_surface_copy(surface: str) -> dict[str, str | None]:
    keys = _SURFACES.get(surface)
    if keys is None:
        raise HTTPException(status_code=404, detail="unknown copy surface")
    out: dict[str, str | None] = {}
    for field, key in keys.items():
        if field == "leave_and_return" and not _leave_and_return_is_honest():
            out[field] = None  # withheld — see _leave_and_return_is_honest
            continue
        text = orchestration_step(key)
        out[field] = text if _is_renderable(text) else None
    return out
