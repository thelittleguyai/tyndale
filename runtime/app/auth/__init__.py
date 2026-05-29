"""Auth layer.

V1-Lite Phase 2H ships a *dev-mode* stub — every request resolves to a fixed
hard-coded user. Real auth (Google + Email magic link, JWT validation,
session persistence) lands in Phase 2K and swaps the dependency here. The
dependency function shape — async, returns a typed ``CurrentUser`` —
stays the same across the swap so routes don't need to change.
"""

from app.auth.dev_user import CurrentUser, current_user  # noqa: F401
