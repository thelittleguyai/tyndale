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
      explicit.

CO-15 — the hook spine is wired into this loop:
  * Before each tool call: PreToolUse (sync ``pre_tool_use_hook`` decision; the
    audited ``guard_send_email`` path for send_email when a session is present,
    per DL-65). A block skips the call and feeds the reason back to the model.
  * After each executed tool: PostToolUse (``post_tool_use_hook`` writes a
    tool_invocation audit row) when a session is available.
  * After the run produces final text: the Stop citation ship-gate
    (``stop_hook``) — ungrounded citations trigger a regenerate (≤3 attempts)
    then human_review.
The deep hook implementations (Presidio scrubbing, AES-GCM audit encryption)
remain the security/HIPAA contact's Phase-4 drop-in behind these call sites.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm_health import (
    ProviderUnavailableError,
    claude_path_label,
    record_claude_call,
)
from app.config import get_settings
from app.hooks.contracts import PostToolUseInput, PreToolUseInput, StopInput
from app.hooks.post_tool_use import post_tool_use_hook
from app.hooks.pre_tool_use import guard_send_email, pre_tool_use_hook
from app.agents.audit_budget import current_audit_budget
from app.hooks.stop import stop_hook
from app.tools import call_tool

log = structlog.get_logger(__name__)

# Re-cite nudge appended when the Stop gate asks for a regenerate (unresolved
# citation markers). Keeps the conversation; tells the model to ground or drop.
_REGEN_NUDGE = (
    "Some citations in your previous answer did not resolve to a source you "
    "retrieved this session. Regenerate the answer and cite ONLY sources you "
    "actually retrieved, in [authority §section, src_id] form. Drop any legal or "
    "coverage claim you cannot ground in a retrieved source."
)

# Tool-result keys that carry a list of retrieved chunks (qdrant_search_* return
# {"hits": [...]}). Each chunk is normalized so the Stop hook can resolve a
# [authority §sec, src_id] marker against its source_id / src_id / id.
_RETRIEVED_CHUNK_KEYS = ("hits", "results", "chunks", "matches")


@dataclass
class RunResult:
    """Output of a single agent run."""

    final_text: str
    messages: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)  # {name, input, result}
    usage: dict[str, int] = field(default_factory=dict)  # input_tokens, output_tokens
    stop_reason: str | None = None
    # CO-15 — Stop ship-gate outcome for this run.
    stop_action: str = "ship"  # ship | regenerate | human_review
    human_review_needed: bool = False
    # Item 1 — True when the Stop gate wanted another regeneration but the audit's
    # wall-clock / per-run regen budget was spent, so this run shipped early.
    budget_stopped: bool = False


def _client():
    """The single Claude client factory (CO-18). Lazy-imports the SDK so importing
    this module doesn't require it. Precedence:

      1. Foundry (use_foundry + endpoint) — the BAA path: Anthropic Messages API at
         {endpoint}/anthropic, authenticated with the runtime's managed identity
         (Entra bearer token, NO api_key; the two are mutually exclusive in the SDK).
      2. LiteLLM proxy (litellm_proxy_url) — legacy/dev proxy.
      3. Anthropic-direct (api_key) — dev/emergency fallback.

    All Claude callers (orchestrator via run_agent, greeting, conversation_title)
    route through here, so Foundry vs direct is one switch."""
    settings = get_settings()
    if settings.use_foundry and settings.foundry_endpoint:
        from anthropic import AsyncAnthropicFoundry
        from azure.identity import (
            DefaultAzureCredential,
            get_bearer_token_provider,
        )

        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(), settings.foundry_token_scope
        )
        base_url = settings.foundry_endpoint.rstrip("/") + "/anthropic"
        return AsyncAnthropicFoundry(
            base_url=base_url,
            azure_ad_token_provider=token_provider,
        )

    from anthropic import AsyncAnthropic

    if settings.litellm_proxy_url:
        return AsyncAnthropic(
            api_key=(settings.anthropic_api_key or "via-litellm-proxy"),
            base_url=settings.litellm_proxy_url,
        )
    return AsyncAnthropic(api_key=settings.anthropic_api_key)


def has_real_anthropic_creds(settings) -> bool:
    """True when there is a usable LLM path — Foundry (managed identity), a real
    ``sk-...`` Anthropic key, or a LiteLLM proxy URL. Placeholder strings ('<from
    terraform output>', empty, unset) return False so callers fall back to fixtures
    instead of hitting the API with an invalid key. Mirrors the orchestrator's gate."""
    if settings.use_foundry and settings.foundry_endpoint:
        return True  # managed identity — no API key needed
    if settings.litellm_proxy_url:
        return True
    key = (settings.anthropic_api_key or "").strip()
    return bool(key) and not key.startswith("<") and key.startswith("sk-")


def real_claude_enabled() -> bool:
    """Whether to use the real LLM (vs deterministic fixtures). Tests + local dev
    run with ``use_real_claude=False`` → fixtures; same switch the orchestrator
    uses."""
    settings = get_settings()
    return bool(settings.use_real_claude) and has_real_anthropic_creds(settings)


def _collect_retrieved_chunks(tool_calls: list[dict]) -> list[dict]:
    """Pull retrieved chunk dicts out of this run's tool results so the Stop hook
    can resolve citation markers. Qdrant tools return
    ``{"hits": [{"id", "score", "payload"}], ...}`` — expose the qdrant point id
    plus any source ids inside the payload (the Stop hook resolves on
    source_id / src_id / id)."""
    chunks: list[dict] = []
    for tc in tool_calls:
        result = tc.get("result")
        if not isinstance(result, dict):
            continue
        for key in _RETRIEVED_CHUNK_KEYS:
            items = result.get(key)
            if not isinstance(items, list):
                continue
            for it in items:
                if not isinstance(it, dict):
                    continue
                payload = it.get("payload") if isinstance(it.get("payload"), dict) else {}
                chunks.append({**payload, "id": it.get("id", payload.get("id"))})
    return chunks


async def _decide_pre_tool_use(inp: PreToolUseInput, session: AsyncSession | None):
    """PreToolUse decision (DL-65 split): the audited ``guard_send_email`` path
    for send_email when a session is available (it writes the phi_block row),
    else the pure sync ``pre_tool_use_hook`` decision."""
    if inp.tool_name == "send_email" and session is not None:
        return await guard_send_email(inp, session)
    return pre_tool_use_hook(inp)


async def run_agent(
    *,
    model: str,
    system_blocks: list[dict],
    tool_names: list[str],
    initial_user_message: str,
    case_file_id: str,
    actor: str,
    session: AsyncSession | None = None,
    max_iterations: int = 12,
    max_tokens_per_call: int = 4096,
    max_attempts: int = 3,
) -> RunResult:
    """Run a Claude session with tool use until the model emits end_turn, with the
    CO-15 hook spine wired in.

    ``case_file_id`` / ``actor`` identify the run for the audit trail; ``session``
    (when supplied — the orchestrator opens one and commits) persists the
    PreToolUse phi_block + PostToolUse tool_invocation audit rows. With no session
    the decision hooks still run (PreToolUse gates, Stop gate) but audit WRITES are
    skipped with a warning — never a crash.

    Returns a ``RunResult`` with the final assistant text, the full message
    history, aggregate token usage, and the Stop ship-gate outcome
    (``stop_action`` / ``human_review_needed``).
    """
    from app.tools import get_anthropic_tools

    client = _client()
    tools = get_anthropic_tools(tool_names)
    path = claude_path_label(get_settings())

    if session is None:
        log.warning(
            "runner.no_session",
            actor=actor,
            note="audit writes skipped; decision hooks still run",
        )

    messages: list[dict] = [{"role": "user", "content": initial_user_message}]
    tool_calls: list[dict] = []
    total_input = 0
    total_output = 0
    stop_reason: str | None = None
    final_text: str = ""
    stop_action: str = "ship"
    human_review_needed = False
    budget_stopped = False

    for attempt in range(1, max_attempts + 1):
        # ---- one generation attempt: the tool-use loop ----
        for _iteration in range(max_iterations):
            try:
                response = await client.messages.create(
                    model=model,
                    max_tokens=max_tokens_per_call,
                    system=system_blocks,
                    tools=tools if tools else None,
                    messages=messages,
                )
            except Exception as exc:  # noqa: BLE001 — never surface a raw provider error
                log.error(
                    "runner.claude_call_failed",
                    actor=actor,
                    case_file_id=case_file_id,
                    path=path,
                    error_class=type(exc).__name__,
                    exc_info=True,
                )
                record_claude_call(ok=False, path=path, detail=type(exc).__name__)
                raise ProviderUnavailableError() from exc
            total_input += response.usage.input_tokens
            total_output += response.usage.output_tokens
            stop_reason = response.stop_reason

            # Capture text deltas into final_text in case the run ends here.
            text_blocks = [b for b in response.content if getattr(b, "type", None) == "text"]
            if text_blocks:
                final_text = "\n\n".join(b.text for b in text_blocks)

            # Append the assistant message verbatim (required for tool_use roundtrips).
            messages.append(
                {"role": "assistant", "content": [_block_to_dict(b) for b in response.content]}
            )

            if response.stop_reason != "tool_use":
                break  # end_turn / max_tokens / stop_sequence

            # Execute each tool_use block (PreToolUse → call → PostToolUse) and
            # assemble a single user message of tool_results.
            tool_use_blocks = [
                b for b in response.content if getattr(b, "type", None) == "tool_use"
            ]
            tool_result_content: list[dict] = []
            for tu in tool_use_blocks:
                tool_input = tu.input if isinstance(tu.input, dict) else {}
                pre = await _decide_pre_tool_use(
                    PreToolUseInput(
                        case_file_id=case_file_id,
                        actor=actor,
                        tool_name=tu.name,
                        tool_args=tool_input,
                    ),
                    session,
                )
                if not pre.approved:
                    # Blocked by policy — do NOT call the tool; surface the reason
                    # so the model can adapt. (The phi_block path already audited
                    # this via guard_send_email.)
                    err = {"error": "blocked_by_policy", "reason": pre.block_reason}
                    tool_calls.append({"name": tu.name, "input": tool_input, "result": err})
                    tool_result_content.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tu.id,
                            "content": json.dumps(err),
                            "is_error": True,
                        }
                    )
                    log.info(
                        "runner.pre_tool_use.blocked",
                        actor=actor,
                        tool=tu.name,
                        reason=pre.block_reason,
                    )
                    continue

                args = pre.sanitized_args
                t0 = time.monotonic()
                result = await call_tool(tu.name, args)
                duration_ms = int((time.monotonic() - t0) * 1000)
                tool_calls.append({"name": tu.name, "input": args, "result": result})
                tool_result_content.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": json.dumps(result, default=str),
                    }
                )

                # PostToolUse audit write — only when a session is available.
                if session is not None:
                    is_err = isinstance(result, dict) and "error" in result
                    try:
                        await post_tool_use_hook(
                            PostToolUseInput(
                                case_file_id=case_file_id,
                                actor=actor,
                                tool_name=tu.name,
                                tool_args_scrubbed=args,
                                tool_result=result
                                if isinstance(result, dict)
                                else {"value": result},
                                duration_ms=duration_ms,
                                outcome="error" if is_err else "success",
                                error_details=(result.get("error") if is_err else None),
                            ),
                            session,
                        )
                    except Exception as exc:  # noqa: BLE001 — audit never breaks the run
                        log.warning(
                            "runner.post_tool_use.failed", actor=actor, tool=tu.name, error=str(exc)
                        )
            messages.append({"role": "user", "content": tool_result_content})
        else:
            log.warning("runner.max_iterations_reached", iterations=max_iterations)

        # ---- Stop citation ship-gate ----
        stop = stop_hook(
            StopInput(
                case_file_id=case_file_id,
                actor=actor,
                generated_output=final_text,
                retrieved_chunks=_collect_retrieved_chunks(tool_calls),
                attempt=attempt,
            )
        )
        stop_action = stop.action
        if stop.action == "ship":
            break
        if stop.action == "human_review":
            human_review_needed = True
            log.warning(
                "runner.stop.human_review",
                actor=actor,
                attempt=attempt,
                unresolved=stop.unresolved_citations,
            )
            break
        # regenerate — UNLESS the audit's budget (wall-clock ceiling or per-run regen cap)
        # is spent. When it is, ship the current output and flag it so the orchestrator marks
        # the run audit_incomplete (budget_exceeded) rather than burning another full pass.
        budget = current_audit_budget()
        if budget is not None and not budget.take_regen():
            budget_stopped = True
            log.warning(
                "runner.stop.budget_exhausted",
                actor=actor,
                attempt=attempt,
                unresolved=stop.unresolved_citations,
            )
            break
        log.info(
            "runner.stop.regenerate",
            actor=actor,
            attempt=attempt,
            unresolved=stop.unresolved_citations,
        )
        messages.append({"role": "user", "content": _REGEN_NUDGE})

    record_claude_call(ok=True, path=path)
    return RunResult(
        final_text=final_text,
        messages=messages,
        tool_calls=tool_calls,
        usage={"input_tokens": total_input, "output_tokens": total_output},
        stop_reason=stop_reason,
        stop_action=stop_action,
        human_review_needed=human_review_needed,
        budget_stopped=budget_stopped,
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
