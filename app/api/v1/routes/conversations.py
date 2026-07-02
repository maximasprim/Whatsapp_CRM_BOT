from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.database.base import get_db
from app.models.auth import User
from app.models.conversation import Conversation, ConversationMessage, ConversationStatus
from app.schemas.common import PaginatedResponse, SuccessResponse

router = APIRouter(prefix="/conversations", tags=["Conversations"])


class ConversationMessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    direction: str
    message_type: str
    content: str | None
    media_url: str | None
    is_read: bool
    is_delivered: bool
    created_at: str

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    assigned_to: uuid.UUID | None
    phone_number: str
    status: str
    is_bot_active: bool
    unread_count: int
    last_message_preview: str | None
    last_message_at: str | None
    sentiment: str | None
    intent: str | None
    urgency: str | None

    model_config = {"from_attributes": True}


@router.get("", response_model=PaginatedResponse[ConversationResponse])
async def list_conversations(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    status: str | None = Query(None),
    assigned_to: uuid.UUID | None = Query(None),
    unread_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[ConversationResponse]:
    conditions = []
    if status:
        conditions.append(Conversation.status == status)
    if assigned_to:
        conditions.append(Conversation.assigned_to == assigned_to)
    if unread_only:
        conditions.append(Conversation.unread_count > 0)

    where = and_(*conditions) if conditions else True
    offset = (page - 1) * page_size

    count = (await session.execute(select(func.count()).select_from(Conversation).where(where))).scalar_one()
    result = await session.execute(
        select(Conversation)
        .where(where)
        .order_by(Conversation.last_message_at.desc().nullslast())
        .offset(offset)
        .limit(page_size)
    )
    items = result.scalars().all()

    data = [
        ConversationResponse(
            id=c.id, customer_id=c.customer_id, assigned_to=c.assigned_to,
            phone_number=c.phone_number, status=c.status, is_bot_active=c.is_bot_active,
            unread_count=c.unread_count, last_message_preview=c.last_message_preview,
            last_message_at=c.last_message_at.isoformat() if c.last_message_at else None,
            sentiment=c.sentiment, intent=c.intent, urgency=c.urgency,
        )
        for c in items
    ]
    return PaginatedResponse.create(data=data, total=count, page=page, page_size=page_size)


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ConversationResponse:
    from app.core.exceptions import NotFoundException
    conv = await session.get(Conversation, conversation_id)
    if not conv:
        raise NotFoundException("Conversation not found.")
    return ConversationResponse(
        id=conv.id, customer_id=conv.customer_id, assigned_to=conv.assigned_to,
        phone_number=conv.phone_number, status=conv.status, is_bot_active=conv.is_bot_active,
        unread_count=conv.unread_count, last_message_preview=conv.last_message_preview,
        last_message_at=conv.last_message_at.isoformat() if conv.last_message_at else None,
        sentiment=conv.sentiment, intent=conv.intent, urgency=conv.urgency,
    )


@router.get("/{conversation_id}/messages", response_model=PaginatedResponse[ConversationMessageResponse])
async def get_conversation_messages(
    conversation_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> PaginatedResponse[ConversationMessageResponse]:
    offset = (page - 1) * page_size
    count = (await session.execute(
        select(func.count()).select_from(ConversationMessage).where(ConversationMessage.conversation_id == conversation_id)
    )).scalar_one()
    result = await session.execute(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = list(reversed(result.scalars().all()))
    data = [
        ConversationMessageResponse(
            id=m.id, conversation_id=m.conversation_id, direction=m.direction,
            message_type=m.message_type, content=m.content, media_url=m.media_url,
            is_read=m.is_read, is_delivered=m.is_delivered, created_at=m.created_at.isoformat(),
        )
        for m in items
    ]
    return PaginatedResponse.create(data=data, total=count, page=page, page_size=page_size)


@router.put("/{conversation_id}/assign", response_model=SuccessResponse)
async def assign_conversation(
    conversation_id: uuid.UUID,
    agent_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SuccessResponse:
    from app.core.exceptions import NotFoundException
    conv = await session.get(Conversation, conversation_id)
    if not conv:
        raise NotFoundException("Conversation not found.")
    conv.assigned_to = agent_id
    conv.status = ConversationStatus.IN_PROGRESS
    session.add(conv)
    await session.commit()
    return SuccessResponse(message="Conversation assigned.")


@router.put("/{conversation_id}/toggle-bot", response_model=SuccessResponse)
async def toggle_bot(
    conversation_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SuccessResponse:
    from app.core.exceptions import NotFoundException
    conv = await session.get(Conversation, conversation_id)
    if not conv:
        raise NotFoundException("Conversation not found.")
    conv.is_bot_active = not conv.is_bot_active
    session.add(conv)
    await session.commit()
    return SuccessResponse(message=f"Bot {'activated' if conv.is_bot_active else 'deactivated'}.")


@router.put("/{conversation_id}/resolve", response_model=SuccessResponse)
async def resolve_conversation(
    conversation_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SuccessResponse:
    from datetime import UTC, datetime
    from app.core.exceptions import NotFoundException
    conv = await session.get(Conversation, conversation_id)
    if not conv:
        raise NotFoundException("Conversation not found.")
    conv.status = ConversationStatus.RESOLVED
    conv.resolved_at = datetime.now(UTC)
    session.add(conv)
    await session.commit()
    return SuccessResponse(message="Conversation resolved.")


@router.put("/{conversation_id}/escalate", response_model=SuccessResponse)
async def escalate_conversation(
    conversation_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SuccessResponse:
    from app.core.exceptions import NotFoundException
    conv = await session.get(Conversation, conversation_id)
    if not conv:
        raise NotFoundException("Conversation not found.")
    conv.status = ConversationStatus.ESCALATED
    conv.is_bot_active = False
    session.add(conv)
    await session.commit()
    return SuccessResponse(message="Conversation escalated to human agent.")
