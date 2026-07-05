"""Streaming message route (Phase CO-10).

POST /v1/conversations/{id}/messages streams a chat turn as Server-Sent Events.
The pre-stream work (ownership check, rate-limit + cost-cap, persisting the user
message, auto-title, creating the streaming assistant row) runs on the request
session; the SSE generator then runs the agent and finalizes the assistant row
on its OWN session (the request session is gone once streaming starts).

Caps (both DB-derived so they survive replica restarts):
  - rate limit: 30 user messages / rolling hour  → 429 RATE_LIMIT_REACHED
  - cost cap:   $10 estimated / rolling 24h       → 429 COST_CAP_REACHED

SSE events (see docs/chat.md): user_message_persisted, assistant_message_started,
tool_call_started, tool_call_completed, token, citation_added,
assistant_message_completed, error, done.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator

import structlog
from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat import estimate_cost_usd, stream_chat_turn
from app.agents.llm_health import CLAUDE_UNAVAILABLE_MESSAGE
from app.auth import CurrentUser, current_user
from app.db.base import AsyncSessionLocal
from app.db.models.conversations import Conversation
from app.db.models.messages import Message
from app.db.session import get_session
from app.routes.conversations import owned_conversation
from app.schemas.chat import MessageCreate
from app.security.audit_writer import build_audit_event
from app.services.conversation_title import auto_generate_title

log = structlog.get_logger(__name__)
router = APIRouter(tags=["v1"])

RATE_LIMIT_PER_HOUR = 30
COST_CAP_USD_PER_DAY = 10.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


async def _user_msg_count_last_hour(session: AsyncSession, uid: uuid.UUID) -> int:
    since = _now() - timedelta(hours=1)
    return (
        await session.scalar(
            select(func.count())
            .select_from(Message)
            .join(Conversation, Message.conversation_id == Conversation.conversation_id)
            .where(
                Conversation.user_id == uid,
                Message.role == "user",
                Message.created_at >= since,
            )
        )
    ) or 0


async def _user_cost_last_day(session: AsyncSession, uid: uuid.UUID) -> float:
    since = _now() - timedelta(hours=24)
    val = await session.scalar(
        select(func.coalesce(func.sum(Message.estimated_cost_usd), 0))
        .select_from(Message)
        .join(Conversation, Message.conversation_id == Conversation.conversation_id)
        .where(Conversation.user_id == uid, Message.created_at >= since)
    )
    return float(val or 0)


async def _load_history(session: AsyncSession, conv_id: uuid.UUID) -> list[dict]:
    rows = (
        (
            await session.execute(
                select(Message)
                .where(Message.conversation_id == conv_id)
                .order_by(Message.sequence_number)
            )
        )
        .scalars()
        .all()
    )
    return [
        {"role": m.role, "content": m.content or ""}
        for m in rows
        if m.role in ("user", "assistant") and m.content
    ]


async def _next_seq(session: AsyncSession, conv_id: uuid.UUID) -> int:
    mx = await session.scalar(
        select(func.max(Message.sequence_number)).where(Message.conversation_id == conv_id)
    )
    return (mx or 0) + 1


async def _finalize_assistant(
    message_id: uuid.UUID,
    conversation_id: uuid.UUID,
    *,
    status: str,
    final: dict | None = None,
    cost: float = 0.0,
    error: str | None = None,
) -> None:
    """Update the streaming assistant row + bump the conversation counters. Runs
    on its own session because the request session is closed once streaming
    begins."""
    async with AsyncSessionLocal() as s:
        m = await s.get(Message, message_id)
        if m is not None:
            m.status = status
            m.completed_at = _now()
            if status == "complete" and final is not None:
                m.content = final.get("content")
                m.content_chunks = final.get("content_chunks")
                m.citations = final.get("citations")
                m.tool_calls = final.get("tool_calls")
                m.confidence_overall = final.get("confidence_overall")
                usage = final.get("usage") or {}
                m.token_usage_input = usage.get("input_tokens")
                m.token_usage_output = usage.get("output_tokens")
                m.estimated_cost_usd = cost
            elif error is not None:
                m.error_message = error[:1000]
        conv = await s.get(Conversation, conversation_id)
        if conv is not None:
            conv.message_count = (conv.message_count or 0) + 1
            conv.last_message_at = _now()
            conv.updated_at = _now()
        await s.commit()


async def _audit_turn(
    *,
    actor: str,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    mode: str,
    usage: dict,
    cost: float,
    tool_calls: list | None,
    outcome: str,
    error: str | None = None,
) -> None:
    async with AsyncSessionLocal() as s:
        names = [
            tc.get("tool_name")
            for tc in (tool_calls or [])
            if isinstance(tc, dict) and tc.get("tool_name")
        ]
        payload = {
            "action": "chat_turn",
            "conversation_id": str(conversation_id),
            "message_id": str(message_id),
            "mode": mode,
            "token_usage": usage,
            "estimated_cost_usd": cost,
            "tool_calls": names,
            "error": error,
        }
        s.add(
            build_audit_event(
                event_type="model_call",
                actor=actor,
                user_id=user_id,
                payload=payload,
                tools_invoked=names or None,
                outcome=outcome,
            )
        )
        await s.commit()


@router.post("/conversations/{conversation_id}/messages")
async def post_message(
    conversation_id: uuid.UUID,
    body: MessageCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
):
    conv = await owned_conversation(session, conversation_id, user)

    # Caps — checked before any persistence so a capped turn costs nothing.
    if await _user_msg_count_last_hour(session, user.user_id) >= RATE_LIMIT_PER_HOUR:
        return JSONResponse(
            status_code=429,
            content={
                "code": "RATE_LIMIT_REACHED",
                "resets_at": (_now() + timedelta(hours=1)).isoformat(),
            },
            headers={"Retry-After": "3600"},
        )
    if await _user_cost_last_day(session, user.user_id) >= COST_CAP_USD_PER_DAY:
        return JSONResponse(
            status_code=429,
            content={
                "code": "COST_CAP_REACHED",
                "resets_at": (_now() + timedelta(hours=24)).isoformat(),
            },
        )

    mode = "freeform" if conv.case_id is None else "per_case"
    history = await _load_history(session, conv.conversation_id)
    seq = await _next_seq(session, conv.conversation_id)
    now = _now()

    user_msg = Message(
        conversation_id=conv.conversation_id,
        sequence_number=seq,
        role="user",
        content=body.content,
        status="complete",
        completed_at=now,
    )
    session.add(user_msg)

    # Auto-title the first user message (DL-47 PHI-guarded inside the service).
    if conv.title is None and not history:
        conv.title = await auto_generate_title(body.content)
    conv.message_count = (conv.message_count or 0) + 1
    conv.last_message_at = now
    conv.updated_at = now

    assistant_msg = Message(
        conversation_id=conv.conversation_id,
        sequence_number=seq + 1,
        role="assistant",
        status="streaming",
    )
    session.add(assistant_msg)
    await session.commit()
    await session.refresh(user_msg)
    await session.refresh(assistant_msg)

    # Capture scalars — the ORM objects are bound to the request session, which
    # is gone once the generator runs.
    conv_id = conv.conversation_id
    case_id = conv.case_id
    uid = user.user_id
    # Audit actor = the user UUID, never the email (Phase 2.2). The email is PII and belongs
    # in the encrypted payload / user_id FK, not the clear-text actor column.
    actor = str(uid)
    content = body.content
    user_msg_id = user_msg.message_id
    user_seq = user_msg.sequence_number
    asst_id = assistant_msg.message_id

    async def gen() -> AsyncIterator[str]:
        yield _sse(
            "user_message_persisted",
            {"message_id": str(user_msg_id), "sequence_number": user_seq},
        )
        yield _sse("assistant_message_started", {"message_id": str(asst_id)})
        final: dict | None = None
        try:
            events_seen = 0
            async for ev in stream_chat_turn(
                mode=mode,
                case_id=case_id,
                user_id=uid,
                history=history,
                user_message=content,
            ):
                # Cancellation (Phase 3.4): POST /conversations/{id}/stop flips this assistant
                # row to 'stopped'. Poll it every ~20 events so a long stream actually halts
                # (within ~1s) instead of running to completion. DB-backed = cross-replica
                # reliable (the stop request may land on a different replica than this stream);
                # returning closes the upstream generator, abandoning the Claude stream.
                events_seen += 1
                if events_seen % 20 == 0:
                    async with AsyncSessionLocal() as check_s:
                        stopped = await check_s.get(Message, asst_id)
                    if stopped is not None and stopped.status == "stopped":
                        log.info("chat.stream_cancelled", conversation_id=str(conv_id))
                        yield _sse("done", {})
                        return
                if ev["event"] == "complete":
                    final = ev["data"]
                    continue
                if ev["event"] == "error":
                    # The chat path already sanitized the message + logged/recorded the
                    # real provider error server-side. Persist failed by CODE (never raw
                    # text), forward the generic event, and stop — do NOT fall through to
                    # the success finalization below.
                    code = ev["data"].get("code") or "STREAM_FAILED"
                    log.warning("chat.stream_error_event", conversation_id=str(conv_id), code=code)
                    await _finalize_assistant(asst_id, conv_id, status="failed", error=code)
                    await _audit_turn(
                        actor=actor,
                        user_id=uid,
                        conversation_id=conv_id,
                        message_id=asst_id,
                        mode=mode,
                        usage={},
                        cost=0.0,
                        tool_calls=None,
                        outcome="error",
                        error=code,
                    )
                    yield _sse("error", ev["data"])
                    yield _sse("done", {})
                    return
                yield _sse(ev["event"], ev["data"])

            final = final or {
                "content": "",
                "content_chunks": [],
                "citations": [],
                "usage": {},
            }
            usage = final.get("usage") or {}
            cost = estimate_cost_usd(usage.get("input_tokens", 0), usage.get("output_tokens", 0))
            await _finalize_assistant(asst_id, conv_id, status="complete", final=final, cost=cost)
            await _audit_turn(
                actor=actor,
                user_id=uid,
                conversation_id=conv_id,
                message_id=asst_id,
                mode=mode,
                usage=usage,
                cost=cost,
                tool_calls=final.get("tool_calls"),
                outcome="success",
            )
            yield _sse(
                "assistant_message_completed",
                {
                    "message_id": str(asst_id),
                    "content_chunks": final.get("content_chunks"),
                    "citations": final.get("citations"),
                    "confidence_overall": final.get("confidence_overall"),
                    "token_usage_input": usage.get("input_tokens"),
                    "token_usage_output": usage.get("output_tokens"),
                    "estimated_cost_usd": cost,
                },
            )
            yield _sse("done", {})
        except Exception as exc:  # noqa: BLE001 — surface as an error event, persist failed
            log.warning("chat.stream_failed", error=str(exc), conversation_id=str(conv_id))
            await _finalize_assistant(asst_id, conv_id, status="failed", error=str(exc))
            await _audit_turn(
                actor=actor,
                user_id=uid,
                conversation_id=conv_id,
                message_id=asst_id,
                mode=mode,
                usage={},
                cost=0.0,
                tool_calls=None,
                outcome="error",
                error=str(exc),
            )
            # Generic user-facing message only — the real error is in the log (above)
            # + the failed audit row. Never str(exc) here (it can carry raw provider text).
            yield _sse("error", {"code": "STREAM_FAILED", "message": CLAUDE_UNAVAILABLE_MESSAGE})
            yield _sse("done", {})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/conversations/{conversation_id}/stop", status_code=204)
async def stop_stream(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> Response:
    conv = await owned_conversation(session, conversation_id, user)
    await session.execute(
        update(Message)
        .where(
            Message.conversation_id == conv.conversation_id,
            Message.status == "streaming",
        )
        .values(status="stopped", completed_at=_now())
    )
    await session.commit()
    return Response(status_code=204)
