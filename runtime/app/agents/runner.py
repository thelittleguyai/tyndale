"""Shared Claude tool_use loop for all V1-Lite agents.

Encapsulates the Anthropic Messages API pattern of:
  1. Send user message + tools
  2. If response is end_turn, done
  3. If response contains tool_use blocks, execute each via the registry
     and append tool_results, loop

Uses the *direct Anthropic SDK* rather than the Claude Agent SDK because:
  (a) the Agent SDK adds another layer of abstraction over the same Messages
      API the V1-Lite walking skeleton needs,
  (b) the Tool registry + dispatch is already first-class here, and
  (c) keeping the loop transparent makes the Stop/PreToolUse hook integration
      explicit in Phase 4.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.config import get_settings
from app.tools import call_tool

log = structlog.get_logger(__name__)


@dataclass
class RunResult:
    """Output of a single agent run."""

    final_text: str
    messages: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)  # {name, input, result}
    usage: dict[str, int] = field(default_factory=dict)  # input_tokens, output_tokens
    stop_reason: str | None = None


def _client():
    """Lazy-import the Anthropic SDK so importing this module doesn't require it."""
    from anthropic import AsyncAnthropic

    settings = get_settings()
    if settings.litellm_proxy_url:
        return AsyncAnthropic(
            api_key=(settings.anthropic_api_key or "via-litellm-proxy"),
            base_url=settings.litellm_proxy_url,
        )
    return AsyncAnthropic(api_key=settings.anthropic_api_key)


async def run_agent(
    *,
    model: str,
    system_blocks: list[dict],
    tool_names: list[str],
    initial_user_message: str,
    max_iterations: int = 12,
    max_tokens_per_call: int = 4096,
) -> RunResult:
    """Run a Claude session with tool use until the model emits end_turn.

    Returns a ``RunResult`` with the final assistant text, the full message
    history (useful for debugging + audit), and aggregate token usage.
    """
    from app.tools import get_anthropic_tools

    client = _client()
    tools = get_anthropic_tools(tool_names)

    messages: list[dict] = [{"role": "user", "content": initial_user_message}]
    tool_calls: list[dict] = []
    total_input = 0
    total_output = 0
    stop_reason: str | None = None
    final_text: str = ""

    for iteration in range(max_iterations):
        response = await client.messages.create(
            model=model,
            max_tokens=max_tokens_per_call,
            system=system_blocks,
            tools=tools if tools else None,
            messages=messages,
        )
        total_input += response.usage.input_tokens
        total_output += response.usage.output_tokens
        stop_reason = response.stop_reason

        # Capture text deltas into final_text in case the run ends here.
        text_blocks = [b for b in response.content if getattr(b, "type", None) == "text"]
        if text_blocks:
            final_text = "\n\n".join(b.text for b in text_blocks)

        # Append the assistant message verbatim (required for tool_use roundtrips).
        messages.append({"role": "assistant", "content": [_block_to_dict(b) for b in response.content]})

        if response.stop_reason != "tool_use":
            break  # end_turn / max_tokens / stop_sequence

        # Execute each tool_use block and assemble a single user message of tool_results.
        tool_use_blocks = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
        tool_result_content: list[dict] = []
        for tu in tool_use_blocks:
            tool_input = tu.input if isinstance(tu.input, dict) else {}
            result = await call_tool(tu.name, tool_input)
            tool_calls.append({"name": tu.name, "input": tool_input, "result": result})
            tool_result_content.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": json.dumps(result, default=str),
                }
            )
        messages.append({"role": "user", "content": tool_result_content})
    else:
        log.warning("runner.max_iterations_reached", iterations=max_iterations)

    return RunResult(
        final_text=final_text,
        messages=messages,
        tool_calls=tool_calls,
        usage={"input_tokens": total_input, "output_tokens": total_output},
        stop_reason=stop_reason,
    )


def _block_to_dict(b) -> dict:
    """Convert an Anthropic SDK content block to a plain dict for round-tripping."""
    t = getattr(b, "type", None)
    if t == "text":
        return {"type": "text", "text": b.text}
    if t == "tool_use":
        return {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
    if t == "tool_result":
        return {"type": "tool_result", "tool_use_id": b.tool_use_id, "content": b.content}
    if t == "thinking":
        return {"type": "thinking", "thinking": getattr(b, "thinking", "")}
    return {"type": t or "unknown", "raw": str(b)}
