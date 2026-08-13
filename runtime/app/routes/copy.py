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
    "status": {
        "leave_and_return": "status_leave_and_return",  # §2.2  (D3)
        "long_wait": "long_wait",  # §2.3
    },
}


def _leave_and_return_is_honest() -> bool:
    """§2.2 promises "I'll email you the moment it's ready".

    We only make that promise if we can keep it. Today `enable_nudge_emails` is false and the
    only outbound mail is the document-chase nudge — there is no audit-ready email at all — so
    the line is WITHHELD rather than rendered as a promise we don't honour (close-the-loop/X1
    is about not stranding the user, and a false "we'll email you" strands them worse than
    silence). Flip `enable_nudge_emails` on, with an audit-ready email wired, and it appears.
    """
    return bool(get_settings().enable_nudge_emails)


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
