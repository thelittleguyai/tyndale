"""IP allowlist for /v1/admin/* (Phase 2K.2 / DL-46).

Preventive — no admin routes exist yet. When they land this enforces an env
allowlist (ADMIN_ALLOWED_IPS, comma-separated CIDR) at the application layer, on
top of the user_type='admin' check already in current_user. An empty allowlist
means no restriction (V1-Lite default).

NOTE: Azure Container Apps can only IP-restrict the WHOLE environment, not a
specific path. Path-based IP rules need Application Gateway in front (Phase 4
WAF). This application-layer check is the V1-Lite bridge.
"""

from __future__ import annotations

import ipaddress

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import get_settings
from app.middleware.net import client_ip

_ADMIN_PREFIX = "/v1/admin"


def _ip_allowed(ip: str, cidrs: list[str]) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for cidr in cidrs:
        try:
            if addr in ipaddress.ip_network(cidr, strict=False):
                return True
        except ValueError:
            continue
    return False


class AdminIPAllowlistMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith(_ADMIN_PREFIX):
            settings = get_settings()
            cidrs = settings.admin_allowed_cidrs
            if cidrs:  # empty allowlist = no restriction
                ip = client_ip(request, settings.trust_forwarded_for_hops)
                if not _ip_allowed(ip, cidrs):
                    return JSONResponse(status_code=403, content={"error": "forbidden", "detail": "not authorized"})
        return await call_next(request)
