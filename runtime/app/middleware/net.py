"""Trusted client-IP resolution behind the Container Apps load balancer.

X-Forwarded-For is a left-to-right chain "origClient, proxy1, ... , lastProxy".
The infra in front of us appends `trust_hops` entries on the RIGHT, so the
furthest IP we can trust is `trust_hops` from the right. We never trust an
unbounded chain — anything a client prepends on the left is ignored. Falls back
to the socket peer when XFF is absent (e.g. local dev / tests without the header).
"""

from __future__ import annotations

from starlette.requests import Request


def client_ip(request: Request, trust_hops: int = 1) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if parts:
            idx = len(parts) - 1 - max(0, trust_hops)
            if idx < 0:
                idx = 0
            return parts[idx]
    if request.client and request.client.host:
        return request.client.host
    return "unknown"
