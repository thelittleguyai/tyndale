"""Auth layer.

Phase 2H shipped a dev-mode stub (every request resolved to a fixed admin
user). Phase 2K swaps in real auth: ``current_user`` now validates a session
cookie when USE_REAL_AUTH=true, and falls back to the seeded dev user when
false (local dev without Google creds). The ``CurrentUser`` return shape is
unchanged, so route code didn't change.

Import surface:
  from app.auth import CurrentUser, current_user
"""

from app.auth.current_user import current_user  # noqa: F401
from app.auth.dev_user import CurrentUser  # noqa: F401
