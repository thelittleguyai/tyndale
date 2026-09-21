"""Which front door a user gets (doc 40 §D) — and which one opened a case.

Resolution order, first hit wins:

    1. the ADMIN OVERRIDE   users.intake_mode      (support / testers / Brock and Phil)
    2. the COHORT decision  users.intake_cohort    ('guided' assigned at first sign-in)
    3. the ENV DEFAULT      settings.intake_mode_default

The cohort decision is made ONCE and stored. It is deterministic — a hash of the user id
against ``intake_mode_cohort_pct`` — so the same user always lands in the same bucket, and it
is stored so that moving the dial from 10 to 50 next month never flips someone who is halfway
through a case. Only NEW users are eligible: someone who already has cases when the decision
is first made is 'default' — they are not the cohort the dial is sampling.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Literal

IntakeMode = Literal["guided", "chat_first"]
INTAKE_MODES: tuple[str, ...] = ("guided", "chat_first")
ModeSource = Literal["override", "cohort", "default"]

# Entry points a guided user may be configured NOT to see (settings.guided_hidden_surfaces).
# A closed set: the client can only hide what it knows how to leave out, and "hidden" always
# means ABSENT — never a disabled control. Kept visible by design, and not hideable here:
# the cases list, Settings, the Record, and per-case chat after the unlock.
HIDEABLE_SURFACES: tuple[str, ...] = (
    "freeform_chat_entry",  # the home "Chat with Tyndale" tile + the floating chat pill
    "quick_actions_grid",  # the home quick-actions grid
    "connect_plan_tile",  # the coverage-connection tile (itself flag-gated)
)


def cohort_bucket(user_id: uuid.UUID | str) -> int:
    """0–99, stable for a user id forever. sha256 rather than hash(): Python salts hash()
    per process, which would re-deal the cohort on every restart."""
    digest = hashlib.sha256(f"intake-cohort:{uuid.UUID(str(user_id))}".encode()).digest()
    return int.from_bytes(digest[:4], "big") % 100


def decide_cohort(user_id: uuid.UUID | str, *, cohort_pct: int, is_new: bool) -> str:
    """'guided' | 'default'. A user who is not new is never sampled."""
    if not is_new:
        return "default"
    return "guided" if cohort_bucket(user_id) < max(0, min(100, int(cohort_pct))) else "default"


def resolve_intake_mode(user, settings) -> tuple[str, ModeSource]:
    """(mode, source) for a users row (or anything with .intake_mode / .intake_cohort)."""
    override = getattr(user, "intake_mode", None)
    if override in INTAKE_MODES:
        return override, "override"
    if getattr(user, "intake_cohort", None) == "guided":
        return "guided", "cohort"
    return settings.intake_mode_default, "default"


def ensure_cohort(user, settings, *, is_new: bool) -> bool:
    """Stamp the one-time cohort decision if it has not been made. Returns True when it just
    stamped (the caller owns the commit). Idempotent: a decided user is never re-decided."""
    if getattr(user, "intake_cohort", None) in ("guided", "default"):
        return False
    user.intake_cohort = decide_cohort(
        user.user_id, cohort_pct=settings.intake_mode_cohort_pct, is_new=is_new
    )
    return True


def hidden_surfaces(mode: str, settings) -> list[str]:
    """What THIS user's client must leave out. Chat-first users see everything; a guided user
    loses the configured surfaces — unknown names are dropped, not passed through."""
    if mode != "guided":
        return []
    return [s for s in settings.guided_hidden_surface_list if s in HIDEABLE_SURFACES]
