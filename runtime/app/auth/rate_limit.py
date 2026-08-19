"""In-memory sliding-window rate limiter (Phase 2K).

V1-Lite scope: a process-local sliding window keyed by an arbitrary string
(email or IP). Phase 4 swaps this for a Redis-backed limiter so it works
across replicas. Until then, note that with >1 Container App replica the
limit is per-replica, not global — acceptable for V1-Lite magic-link abuse
control, flagged for the Phase 4 upgrade.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class RateLimitExceeded(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"rate limit exceeded; retry after {retry_after_seconds}s")


class SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, *, limit: int, window_seconds: int, now: float | None = None) -> None:
        """Record a hit for ``key``; raise RateLimitExceeded if over ``limit``
        within ``window_seconds``."""
        t = now if now is not None else time.monotonic()
        cutoff = t - window_seconds
        with self._lock:
            dq = self._hits[key]
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) >= limit:
                retry_after = int(dq[0] + window_seconds - t) + 1
                raise RateLimitExceeded(max(1, retry_after))
            dq.append(t)

    def reset(self) -> None:
        """Test helper — clear all windows."""
        with self._lock:
            self._hits.clear()


# Module-level singleton used by the magic-link route.
magic_link_limiter = SlidingWindowRateLimiter()

# LOW-14 (2026-08-19 security review): the unauthenticated access-request intake gets its
# own TIGHT per-IP window (default 5/hour) — the global 1000/hr limit alone allowed
# PHI-row write amplification into the encrypted audit table.
access_request_limiter = SlidingWindowRateLimiter()
