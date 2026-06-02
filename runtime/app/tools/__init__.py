"""Tool registry shared by all agents.

Pattern:
    Each tool module (db_tools, ocr_tools, knowledge_tools, …) registers its
    tools at import time via ``register_tool(name, schema, async_fn)``.
    Agents look the tools up via ``get_anthropic_tools(["name1", "name2"])``
    when building their ``tools=`` array, and the orchestrator dispatches a
    Claude tool_use block via ``call_tool(name, args)``.

    The Anthropic Messages API expects tool definitions in this shape:
        {"name": "x", "description": "...", "input_schema": {…JSON Schema…}}
    Tool functions return a JSON-serialisable dict; the orchestrator wraps
    that in a tool_result block.

The tool descriptions in intelligence-layer/tools/descriptions/<name>.md are
the authoring source of truth for what the model sees. The schema text here
is a compact restatement of the relevant fields — keep the two in sync.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

import structlog

log = structlog.get_logger(__name__)

ToolFunc = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]

# tool_name -> (anthropic_tool_schema_without_name, async_fn)
_REGISTRY: dict[str, tuple[dict[str, Any], ToolFunc]] = {}


def register_tool(name: str, schema: dict[str, Any], fn: ToolFunc) -> None:
    """Register a tool. Schema MUST include 'description' and 'input_schema'."""
    if "description" not in schema or "input_schema" not in schema:
        raise ValueError(f"tool {name} missing description or input_schema")
    if name in _REGISTRY:
        log.warning("tools.duplicate_registration", tool=name)
    _REGISTRY[name] = (schema, fn)


def get_anthropic_tools(names: list[str]) -> list[dict[str, Any]]:
    """Return the Anthropic-API-shaped tool definitions for the given names."""
    out = []
    for n in names:
        if n not in _REGISTRY:
            log.warning("tools.unknown_in_allowlist", tool=n)
            continue
        schema, _ = _REGISTRY[n]
        out.append({"name": n, **schema})
    return out


async def call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a tool_use to its registered function. Returns a dict."""
    if name not in _REGISTRY:
        return {"error": f"tool '{name}' not registered"}
    _, fn = _REGISTRY[name]
    try:
        return await fn(args or {})
    except Exception as exc:  # noqa: BLE001 — tool errors must become tool_result
        log.exception("tools.call_failed", tool=name, error=str(exc))
        return {"error": f"{type(exc).__name__}: {exc}"}


def registered_names() -> list[str]:
    """For diagnostics / tests."""
    return sorted(_REGISTRY)


# Trigger registration of all built-in tools by importing the modules.
# Order matters only insofar as duplicate-name warnings fire from later
# modules — current modules are disjoint.
from app.tools import db_tools  # noqa: E402, F401
from app.tools import ocr_tools  # noqa: E402, F401
from app.tools import knowledge_tools  # noqa: E402, F401
from app.tools import cost_tools  # noqa: E402, F401
from app.tools import code_tools  # noqa: E402, F401
from app.tools import util_tools  # noqa: E402, F401
from app.tools import log_knowledge_gap  # noqa: E402, F401
