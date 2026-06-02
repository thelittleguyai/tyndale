"""Conversation CRUD routes (Phase CO-10).

Per-case (case_id NOT NULL) and freeform (case_id NULL) threads. Every route is
scoped to the authenticated user; a non-owner gets 403. DELETE is a soft delete
(is_archived=TRUE) — hard delete only rides admin user-soft-delete (CO-9).
"""

from __future__ import annotations

import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, current_user
from app.db.models.case_files import CaseFile
from app.db.models.conversations import Conversation
from app.db.models.messages import Message
from app.db.session import get_session
from app.schemas.chat import (
    ConversationCreate,
    ConversationDetail,
    ConversationList,
    ConversationOut,
    ConversationPatch,
    MessageOut,
)

router = APIRouter(tags=["v1"])


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def conversation_to_out(c: Conversation) -> ConversationOut:
    return ConversationOut(
        conversation_id=c.conversation_id,
        user_id=c.user_id,
        case_id=c.case_id,
        mode="freeform" if c.case_id is None else "per_case",
        title=c.title,
        is_archived=c.is_archived,
        message_count=c.message_count,
        last_message_at=c.last_message_at,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


def message_to_out(m: Message) -> MessageOut:
    return MessageOut(
        message_id=m.message_id,
        conversation_id=m.conversation_id,
        sequence_number=m.sequence_number,
        role=m.role,
        content=m.content,
        content_chunks=m.content_chunks,
        tool_calls=m.tool_calls,
        citations=m.citations,
        confidence_overall=(
            float(m.confidence_overall) if m.confidence_overall is not None else None
        ),
        status=m.status,
        error_message=m.error_message,
        token_usage_input=m.token_usage_input,
        token_usage_output=m.token_usage_output,
        estimated_cost_usd=(
            float(m.estimated_cost_usd) if m.estimated_cost_usd is not None else None
        ),
        created_at=m.created_at,
        completed_at=m.completed_at,
    )


async def owned_conversation(
    session: AsyncSession, conversation_id: uuid.UUID, user: CurrentUser
) -> Conversation:
    """Fetch a conversation the user owns, else 404 (missing) / 403 (not owner)."""
    conv = await session.get(Conversation, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    if conv.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="forbidden")
    return conv


@router.get("/conversations", response_model=ConversationList)
async def list_conversations(
    case_id: uuid.UUID | None = None,
    mode: str | None = Query(default=None, pattern="^(per_case|freeform|all)$"),
    include_archived: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> ConversationList:
    filters = [Conversation.user_id == user.user_id]
    if case_id is not None:
        filters.append(Conversation.case_id == case_id)
    if mode == "per_case":
        filters.append(Conversation.case_id.isnot(None))
    elif mode == "freeform":
        filters.append(Conversation.case_id.is_(None))
    if not include_archived:
        filters.append(Conversation.is_archived.is_(False))

    total = await session.scalar(
        select(func.count()).select_from(Conversation).where(*filters)
    )
    rows = (
        (
            await session.execute(
                select(Conversation)
                .where(*filters)
                .order_by(
                    Conversation.last_message_at.desc().nullslast(),
                    Conversation.created_at.desc(),
                )
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return ConversationList(
        conversations=[conversation_to_out(c) for c in rows],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.post("/conversations", response_model=ConversationOut, status_code=201)
async def create_conversation(
    body: ConversationCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> ConversationOut:
    if body.case_id is not None:
        cf = await session.get(CaseFile, body.case_id)
        if cf is None or cf.user_id != user.user_id:
            raise HTTPException(status_code=404, detail="case file not found")
    conv = Conversation(user_id=user.user_id, case_id=body.case_id)
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    return conversation_to_out(conv)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> ConversationDetail:
    conv = await owned_conversation(session, conversation_id, user)
    msgs = (
        (
            await session.execute(
                select(Message)
                .where(Message.conversation_id == conv.conversation_id)
                .order_by(Message.sequence_number)
            )
        )
        .scalars()
        .all()
    )
    return ConversationDetail(
        **conversation_to_out(conv).model_dump(),
        messages=[message_to_out(m) for m in msgs],
    )


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
async def patch_conversation(
    conversation_id: uuid.UUID,
    body: ConversationPatch,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> ConversationOut:
    conv = await owned_conversation(session, conversation_id, user)
    if body.title is not None:
        conv.title = body.title
    if body.is_archived is not None:
        conv.is_archived = body.is_archived
    conv.updated_at = _now()
    await session.commit()
    await session.refresh(conv)
    return conversation_to_out(conv)


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(current_user),
) -> Response:
    conv = await owned_conversation(session, conversation_id, user)
    conv.is_archived = True
    conv.updated_at = _now()
    await session.commit()
    return Response(status_code=204)
