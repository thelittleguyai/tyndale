#!/usr/bin/env python3
"""Foundry auth + Claude reachability smoke test.

Acquires an Entra token for the configured FOUNDRY_TOKEN_SCOPE and makes a 1-token Claude
call through the SAME client factory the runtime uses (app.agents.runner._client), so it
reproduces exactly what chat/audit do. Prints OK with the resolved model + path, or a
structured error (exception class + message) so an operator can diagnose invalid_scope / 401
without digging through app logs. Records the outcome via app.agents.llm_health, so the admin
System page reflects the result too.

Run from the runtime/ directory:

    uv run python scripts/foundry_smoke.py

Exit code 0 on success, 1 on failure. This is an operator diagnostic — it prints the raw
provider error to stderr on purpose (unlike the user-facing chat path, which never does).
"""

from __future__ import annotations

import asyncio
import sys

from app.agents import llm_health
from app.agents.runner import _client
from app.config import get_settings


async def _run() -> int:
    settings = get_settings()
    path = llm_health.claude_path_label(settings)
    model = settings.resolved_model(settings.claude_default_model_haiku)

    print(f"Claude path : {path}")
    if path == "foundry":
        print(f"Endpoint    : {settings.foundry_endpoint}")
        print(f"Token scope : {settings.foundry_token_scope}")
    print(f"Model       : {model}")
    print("Calling Claude (max_tokens=1) ...")

    try:
        client = _client()
        resp = await client.messages.create(
            model=model,
            max_tokens=1,
            messages=[{"role": "user", "content": "ping"}],
        )
    except Exception as exc:  # noqa: BLE001 — operator diagnostic; surface the real error
        llm_health.record_claude_call(ok=False, path=path, detail=type(exc).__name__)
        print(f"\nERROR — {type(exc).__name__}: {exc}", file=sys.stderr)
        print(
            "\nIf this is `invalid_scope`, flip FOUNDRY_TOKEN_SCOPE to "
            "https://ai.azure.com/.default via terraform.tfvars and re-apply.",
            file=sys.stderr,
        )
        return 1

    llm_health.record_claude_call(ok=True, path=path)
    stop = getattr(resp, "stop_reason", None)
    print(f"\nOK — Claude reachable via {path} (model={model}, stop_reason={stop}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
