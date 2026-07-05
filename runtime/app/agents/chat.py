"""Streaming chat turn (Phase CO-10).

A chat turn is the existing Lead Planner posture run multi-turn: the conversation
history is fed in as prior turns, the mode selects the system prompt + the tool
allowlist, and the agent streams its answer.

Two paths, switched by ``real_claude_enabled()`` (same switch the orchestrator
uses):

  * **fixture** (tests + local dev, ``use_real_claude=False``) — a deterministic
    event sequence so the SSE contract + persistence are testable without an LLM.
  * **real** — ``client.messages.stream()`` with the tool_use loop, emitting
    token / tool-call / citation events live.

The function yields ``{"event", "data"}`` dicts for the CONTENT events
(tool_call_started/completed, token, citation_added) plus a terminal
``complete`` event carrying the final content_chunks / citations / usage. The
route (``app/routes/messages.py``) owns the envelope events
(user_message_persisted, assistant_message_started, assistant_message_completed,
done) + persistence, because those need the DB row ids.

Mode distinction is enforced at the TOOL level too: freeform mode gets ONLY the
knowledge-base tools (no case-file access), per-case mode gets case tools.
"""

from __future__ import annotations

import json
import re
import time
from typing import AsyncIterator

import structlog

from app.agents.context_loader import compose_chat_system_prompt
from app.agents.llm_health import (
    CLAUDE_UNAVAILABLE_MESSAGE,
    claude_path_label,
    record_claude_call,
)
from app.agents.runner import _block_to_dict, _client, _collect_retrieved_chunks, real_claude_enabled
from app.config import get_settings
from app.hooks.contracts import (
    CrisisClassifierInput,
    PreToolUseInput,
    StopInput,
    UserPromptSubmitInput,
)
from app.hooks.crisis_classifier import crisis_classifier_async
from app.hooks.pre_tool_use import pre_tool_use_hook
from app.hooks.stop import _CITATION_RE, stop_hook
from app.hooks.user_prompt_submit import user_prompt_submit_hook
from app.tools import call_tool, get_anthropic_tools
from app.tools.log_knowledge_gap import log_knowledge_gap

log = structlog.get_logger(__name__)

# DL-04 Category-2 clean decline (refusals.md) — the ENTIRE response. No 988, no
# routing, no follow-up. Wired at chat ingress; bypasses the Lead Planner.
_CRISIS_DECLINE = "This isn't something I'm equipped to help with."
# Shown when UserPromptSubmit blocks a message (prompt-injection / policy).
_BLOCKED_NOTICE = (
    "I can't process that message as written. Please rephrase your billing or "
    "coverage question and I'll help."
)

# Claude pricing (USD per 1M tokens) — Sonnet tier; rough by design.
_COST_IN_PER_M = 3.0
_COST_OUT_PER_M = 15.0

_PER_CASE_TOOLS = [
    "pg_case_file_get",
    "qdrant_search_billing_codes",
    "qdrant_search_error_detection_rules",
    "qdrant_search_laws_regulations",
    "qdrant_search_payer_policies",
    "cost_estimate_medicare_rvu",
    "log_knowledge_gap",
]
# Freeform: knowledge base ONLY — no case-file tools (no PHI/case context).
_FREEFORM_TOOLS = [
    "qdrant_search_billing_codes",
    "qdrant_search_error_detection_rules",
    "qdrant_search_laws_regulations",
    "qdrant_search_payer_policies",
    "log_knowledge_gap",
]


def tool_names_for(mode: str) -> list[str]:
    return list(_PER_CASE_TOOLS if mode == "per_case" else _FREEFORM_TOOLS)


def estimate_cost_usd(input_tokens: int, output_tokens: int) -> float:
    return round(
        (input_tokens or 0) / 1_000_000 * _COST_IN_PER_M
        + (output_tokens or 0) / 1_000_000 * _COST_OUT_PER_M,
        6,
    )


# --- heuristics (shared by fixture + as a real-path guardrail) ---------------

_DOLLAR_RE = re.compile(r"\$\s?\d[\d,]*(?:\.\d{2})?")
_SITUATION_WORDS = (
    "bill",
    "billed",
    "paid",
    "charged",
    "charge",
    "owe",
    "claim",
    "denied",
    "deductible",
    "coinsurance",
    "copay",
    "eob",
    "covered",
    "reimburse",
)
_GAP_WORDS = ("rare", "experimental", "investigational", "unusual", "uncommon")


def looks_like_specific_situation(text: str) -> bool:
    """True when a freeform message describes a SPECIFIC bill/claim that needs
    case-level analysis (→ create_case_cta). A dollar amount plus billing
    language is the signal."""
    low = (text or "").lower()
    if not _DOLLAR_RE.search(low):
        return False
    return any(w in low for w in _SITUATION_WORDS)


def _fixture_should_log_gap(text: str) -> bool:
    """Deterministic stand-in for 'a subagent self-reported a data gap': the
    fixture flags queries about rare/experimental things the KB plausibly lacks."""
    low = (text or "").lower()
    return any(w in low for w in _GAP_WORDS)


def _tokenize(text: str) -> list[str]:
    """Chunk text into word-ish pieces for a believable token stream."""
    return [w + " " for w in text.split()]


# --- fixture path ------------------------------------------------------------


async def _fixture_stream(*, mode: str, case_id, user_id, user_message: str) -> AsyncIterator[dict]:
    # Freeform: a specific situation → redirect to case creation (no speculation).
    if mode == "freeform" and looks_like_specific_situation(user_message):
        text = (
            "It looks like you're describing a specific bill or claim. To analyze it "
            "properly, I'd need you to upload the documents. Would you like to create a case?"
        )
        for tok in _tokenize(text):
            yield {"event": "token", "data": {"delta": tok, "tier": "C"}}
        cta = {"action_type": "create_case_cta", "title": "Create a case"}
        usage = {"input_tokens": 60, "output_tokens": 40}
        yield {
            "event": "complete",
            "data": {
                "content": text,
                "content_chunks": [
                    {"tier": "C", "text": text, "citations": [], "confidence": None}
                ],
                "citations": [cta],
                "confidence_overall": None,
                "usage": usage,
            },
        }
        return

    # Self-reported knowledge gap (deterministic trigger).
    if _fixture_should_log_gap(user_message):
        try:
            await log_knowledge_gap(
                agent_name=f"chat:{mode}",
                gap_type="no_data",
                query=user_message[:500],
                case_id=case_id,
                user_id=user_id,
                context_summary="chat turn could not ground an answer from available data",
            )
        except Exception as exc:  # noqa: BLE001 — gap logging is best-effort
            log.warning("chat.fixture.gap_log_failed", error=str(exc))

    if mode == "per_case":
        tool = {
            "tool_name": "pg_case_file_get",
            "subagent": "Bill Detective",
            "input_summary": "load case file + encounters",
        }
        a_text = "Based on your case, the provider billed $1,200 and the EOB lists $1,200 as your responsibility, while Tyndale independently computes $560."
        b_text = "Under the No Surprises Act, certain out-of-network charges for this setting are restricted. [PLACEHOLDER_AUTHORITY §000]"
        c_text = "I'd recommend calling the payer to dispute the cost-sharing math and requesting a corrected EOB; keep a written record of the call."
        citation = {
            "source_id": "src_demo_nsa",
            "title": "No Surprises Act — balance billing protections",
            "url": "https://www.cms.gov/nosurprises",
            "snippet": "Protects against certain out-of-network balance billing.",
            "effective_date": "2022-01-01",
        }
    else:
        tool = {
            "tool_name": "qdrant_search_billing_codes",
            "subagent": "Knowledge",
            "input_summary": user_message[:60],
        }
        a_text = "That code refers to a specific medical procedure. Here's the general meaning and how it's typically billed."
        b_text = "Whether it's covered depends on your plan's terms and medical-necessity policy. [PLACEHOLDER_AUTHORITY §000]"
        c_text = "If you want this checked against an actual bill, upload the documents to open a case and I'll analyze it directly."
        citation = {
            "source_id": "src_demo_cpt",
            "title": "Procedure code reference",
            "url": "https://www.cms.gov/medicare/coding",
            "snippet": "General procedure-code reference (descriptor omitted per licensing).",
            "effective_date": "2024-01-01",
            "cpt_code": "27447",
        }

    yield {"event": "tool_call_started", "data": dict(tool)}
    yield {
        "event": "tool_call_completed",
        "data": {"tool_name": tool["tool_name"], "output_summary": "ok", "duration_ms": 12},
    }

    for tier, txt in (("A", a_text), ("B", b_text), ("C", c_text)):
        for tok in _tokenize(txt):
            yield {"event": "token", "data": {"delta": tok, "tier": tier}}

    yield {"event": "citation_added", "data": dict(citation)}

    full = "\n\n".join([a_text, b_text, c_text])
    usage = {"input_tokens": 120, "output_tokens": 90}
    yield {
        "event": "complete",
        "data": {
            "content": full,
            "content_chunks": [
                {"tier": "A", "text": a_text, "citations": [], "confidence": 0.9},
                {"tier": "B", "text": b_text, "citations": [citation], "confidence": 0.7},
                {"tier": "C", "text": c_text, "citations": [], "confidence": None},
            ],
            "citations": [citation],
            "confidence_overall": 0.8,
            "usage": usage,
        },
    }


# --- real path ---------------------------------------------------------------


def _summarize(obj) -> str:
    try:
        s = json.dumps(obj, default=str) if not isinstance(obj, str) else obj
    except Exception:  # noqa: BLE001
        s = str(obj)
    return s[:200]


def _build_messages(history: list[dict], user_message: str) -> list[dict]:
    """Prior turns as alternating user/assistant messages, then the new turn."""
    messages: list[dict] = []
    for h in history:
        role = h.get("role")
        content = h.get("content") or ""
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})
    return messages


def _resolve_citation(src_id: str, retrieved: list[dict]) -> dict | None:
    """Match a marker's src_id to a chunk retrieved THIS session; build a chat Citation dict
    from its payload. None if the src_id wasn't retrieved (ungrounded)."""
    for ch in retrieved:
        cid = str(ch.get("source_id") or ch.get("src_id") or ch.get("id") or "")
        if cid == src_id:
            snippet = ch.get("snippet") or ch.get("chunk_text") or ch.get("text") or ""
            return {
                "source_id": cid,
                "title": ch.get("title") or ch.get("authority") or ch.get("statute"),
                "url": ch.get("url"),
                "snippet": (snippet[:280] or None),
                "effective_date": ch.get("effective_date") or ch.get("effective_date_start"),
                "payer": ch.get("payer"),
                "cpt_code": ch.get("cpt_code") or ch.get("code"),
                "action_type": None,
                # laws_regulations X6 fields (DL-84): let the card show CATEGORICAL vs
                # CONDITIONAL and the classification's as-of date. Null for non-law hits.
                "as_of": ch.get("as_of"),
                "x6_classification": ch.get("x6_classification"),
            }
    return None


def _chunks_and_citations(full: str, retrieved: list[dict]) -> tuple[list[dict], list[dict], list[str]]:
    """Parse [authority §sec, src_id] markers out of the assembled text, resolve them against the
    session's retrieved chunks, and split the text into tiered content_chunks matching the shared
    contract (fixture parity). Markers whose src_id was NOT retrieved (ungrounded) are STRIPPED
    from the displayed text — the Stop citation gate's 'degrade honestly' for the streaming path.
    Returns (content_chunks, turn_citations, unresolved_labels)."""
    if not full:
        return [], [], []
    resolved: dict[str, dict] = {}
    unresolved: list[str] = []
    for authority, src_id in _CITATION_RE.findall(full):
        if src_id in resolved:
            continue
        cit = _resolve_citation(src_id, retrieved)
        if cit is not None:
            resolved[src_id] = cit
        else:
            unresolved.append(f"{authority.strip()} ({src_id})")

    # Keep resolved markers in the text (cards anchor to them); drop ungrounded ones.
    display = _CITATION_RE.sub(lambda m: m.group(0) if m.group(2) in resolved else "", full)

    chunks: list[dict] = []
    for para in (p.strip() for p in re.split(r"\n\n+", display)):
        if not para:
            continue
        para_cits = [
            resolved[sid] for _a, sid in _CITATION_RE.findall(para) if sid in resolved
        ]
        # Tier B = a paragraph carrying a legal/coverage citation; else Tier A (plain fact).
        chunks.append(
            {
                "tier": "B" if para_cits else "A",
                "text": para,
                "citations": para_cits,
                "confidence": None,
            }
        )
    return chunks, list(resolved.values()), unresolved


async def _real_stream(
    *, mode: str, case_id, user_id, history: list[dict], user_message: str
) -> AsyncIterator[dict]:
    settings = get_settings()
    client = _client()
    system_blocks = compose_chat_system_prompt(mode)
    tools = get_anthropic_tools(tool_names_for(mode))
    messages = _build_messages(history, user_message)
    model = settings.claude_model_for("lead_planner")
    path = claude_path_label(settings)

    text_parts: list[str] = []
    tool_calls_made: list[dict] = []
    retrieved_results: list[dict] = []  # raw tool results, for citation-chunk resolution (3.1)
    total_in = total_out = 0

    for _ in range(8):  # bounded tool rounds
        try:
            async with client.messages.stream(
                model=model,
                max_tokens=2048,
                system=system_blocks,
                tools=tools or None,
                messages=messages,
            ) as stream:
                async for event in stream:
                    if (
                        event.type == "content_block_delta"
                        and getattr(event.delta, "type", None) == "text_delta"
                    ):
                        yield {"event": "token", "data": {"delta": event.delta.text}}
                final = await stream.get_final_message()
        except Exception as exc:  # noqa: BLE001 — never stream a raw provider error to the user
            log.error(
                "chat.claude_call_failed",
                path=path,
                error_class=type(exc).__name__,
                mode=mode,
                exc_info=True,
            )
            record_claude_call(ok=False, path=path, detail=type(exc).__name__)
            yield {
                "event": "error",
                "data": {
                    "code": "CLAUDE_UNAVAILABLE",
                    "message": CLAUDE_UNAVAILABLE_MESSAGE,
                    "retryable": True,
                },
            }
            return

        total_in += final.usage.input_tokens
        total_out += final.usage.output_tokens
        text_parts.extend(b.text for b in final.content if getattr(b, "type", None) == "text")
        messages.append(
            {"role": "assistant", "content": [_block_to_dict(b) for b in final.content]}
        )

        if final.stop_reason != "tool_use":
            break

        tool_use = [b for b in final.content if getattr(b, "type", None) == "tool_use"]
        results: list[dict] = []
        for tu in tool_use:
            tool_input = tu.input if isinstance(tu.input, dict) else {}
            yield {
                "event": "tool_call_started",
                "data": {"tool_name": tu.name, "input_summary": _summarize(tool_input)},
            }
            # PreToolUse gate (CO-15): the date-filter / approval-token rules apply
            # to chat tool calls too. Chat tools are knowledge reads (no send_email),
            # so the sync decision is sufficient — no audited session path here.
            pre = pre_tool_use_hook(
                PreToolUseInput(
                    case_file_id=(str(case_id) if case_id else ""),
                    actor="lead_planner",
                    tool_name=tu.name,
                    tool_args=tool_input,
                )
            )
            if not pre.approved:
                blocked = {"error": "blocked_by_policy", "reason": pre.block_reason}
                yield {
                    "event": "tool_call_completed",
                    "data": {
                        "tool_name": tu.name,
                        "output_summary": _summarize(blocked),
                        "duration_ms": 0,
                    },
                }
                tool_calls_made.append(
                    {
                        "tool_name": tu.name,
                        "input_summary": _summarize(tool_input),
                        "output_summary": _summarize(blocked),
                        "duration_ms": 0,
                    }
                )
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": json.dumps(blocked),
                        "is_error": True,
                    }
                )
                continue
            tool_input = pre.sanitized_args
            t0 = time.monotonic()
            result = await call_tool(tu.name, tool_input)
            retrieved_results.append({"result": result})  # for citation resolution (3.1)
            dur = int((time.monotonic() - t0) * 1000)
            yield {
                "event": "tool_call_completed",
                "data": {
                    "tool_name": tu.name,
                    "output_summary": _summarize(result),
                    "duration_ms": dur,
                },
            }
            tool_calls_made.append(
                {
                    "tool_name": tu.name,
                    "input_summary": _summarize(tool_input),
                    "output_summary": _summarize(result),
                    "duration_ms": dur,
                }
            )
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": json.dumps(result, default=str),
                }
            )
        messages.append({"role": "user", "content": results})

    record_claude_call(ok=True, path=path)
    full = "\n\n".join(p for p in text_parts if p).strip()

    # 3.1: parse citations + tiers out of the real stream to match the fixture/shared contract,
    # and apply the Stop citation gate. retrieved chunks come from the raw tool results.
    retrieved = _collect_retrieved_chunks(retrieved_results)
    chunks, citations, unresolved = _chunks_and_citations(full, retrieved)
    if unresolved:
        # An ungrounded citation slipped through. On the AUDIT (batch) path run_agent regenerates
        # up to 3x; on this LIVE-STREAMING path a re-run would re-stream tokens, so we DEGRADE
        # HONESTLY instead — _chunks_and_citations already stripped the ungrounded markers from
        # the displayed text so the turn never shows a citation it can't back.
        stop = stop_hook(
            StopInput(
                case_file_id=(str(case_id) if case_id else ""),
                actor="lead_planner",
                generated_output=full,
                retrieved_chunks=retrieved,
                attempt=1,
            )
        )
        log.info("chat.stop_gate.degraded", mode=mode, action=stop.action, unresolved=unresolved)

    display = "\n\n".join(c["text"] for c in chunks)
    yield {
        "event": "complete",
        "data": {
            "content": display or full,
            "content_chunks": chunks,
            "citations": citations,
            "confidence_overall": None,
            "usage": {"input_tokens": total_in, "output_tokens": total_out},
            "tool_calls": tool_calls_made,
        },
    }


async def _decline_stream(text: str) -> AsyncIterator[dict]:
    """Emit a terminal decline as a minimal token + complete stream so the route
    persists it as the assistant message (no tools, no Lead Planner)."""
    for tok in _tokenize(text):
        yield {"event": "token", "data": {"delta": tok, "tier": "C"}}
    yield {
        "event": "complete",
        "data": {
            "content": text,
            "content_chunks": [{"tier": "C", "text": text, "citations": [], "confidence": None}],
            "citations": [],
            "confidence_overall": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        },
    }


async def stream_chat_turn(
    *,
    mode: str,
    case_id,
    user_id,
    history: list[dict],
    user_message: str,
) -> AsyncIterator[dict]:
    """Yield content events for one chat turn. Fixture path when real Claude is
    disabled (tests/dev); real streaming + tool loop otherwise.

    CO-15 — chat ingress runs BEFORE any dispatch (both paths): the DL-04 crisis
    screen (a positive signal returns the clean decline, bypassing the Lead
    Planner entirely) and UserPromptSubmit (injection framing + block)."""
    # Crisis screen (DL-04). Real Haiku classifier with a deterministic keyword
    # fallback (crisis_classifier_async is failure-safe: on any classifier error /
    # timeout / missing-creds it degrades to the keyword screen, never fails open).
    # A positive signal returns the Category-2 clean decline and NEVER reaches the
    # Lead Planner / fixture stream.
    if (
        await crisis_classifier_async(CrisisClassifierInput(raw_message=user_message))
    ).crisis_detected:
        log.info("chat.crisis_decline", mode=mode)
        async for ev in _decline_stream(_CRISIS_DECLINE):
            yield ev
        return

    # UserPromptSubmit — prompt-injection framing + block (stub: pass-through).
    ups = user_prompt_submit_hook(
        UserPromptSubmitInput(
            user_id=str(user_id),
            case_file_id=(str(case_id) if case_id else None),
            raw_message=user_message,
            attached_documents=[],
        )
    )
    if ups.block:
        log.info("chat.prompt_blocked", mode=mode, signals=ups.injection_signals)
        async for ev in _decline_stream(_BLOCKED_NOTICE):
            yield ev
        return
    user_message = ups.scrubbed_message  # use the scrubbed text downstream

    if not real_claude_enabled():
        async for ev in _fixture_stream(
            mode=mode, case_id=case_id, user_id=user_id, user_message=user_message
        ):
            yield ev
        return
    async for ev in _real_stream(
        mode=mode,
        case_id=case_id,
        user_id=user_id,
        history=history,
        user_message=user_message,
    ):
        yield ev
