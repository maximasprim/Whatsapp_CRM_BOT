from __future__ import annotations

import uuid
from typing import Annotated, AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers import get_ai_provider
from app.ai.providers.base import Message, MessageRole
from app.auth.dependencies import get_current_user
from app.core.database.base import get_db
from app.models.auth import User
from app.schemas.common import SuccessResponse

router = APIRouter(prefix="/ai", tags=["AI"])


class ChatRequest(BaseModel):
    message: str
    conversation_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    history: list[dict] | None = None


class SuggestReplyRequest(BaseModel):
    conversation_id: uuid.UUID
    context: str = ""


@router.post("/chat")
async def ai_chat(
    data: ChatRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    provider = get_ai_provider()
    messages = []
    if data.history:
        for h in data.history:
            role = MessageRole.USER if h.get("role") == "user" else MessageRole.ASSISTANT
            messages.append(Message(role=role, content=h.get("content", "")))
    messages.append(Message(role=MessageRole.USER, content=data.message))

    response = await provider.complete(messages=messages)
    return {"reply": response.content, "usage": {"total_tokens": response.usage.total_tokens}}


@router.post("/chat/stream")
async def ai_chat_stream(
    data: ChatRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    provider = get_ai_provider()
    messages = [Message(role=MessageRole.USER, content=data.message)]

    async def token_generator() -> AsyncGenerator[str, None]:
        async for token in provider.stream(messages=messages):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(token_generator(), media_type="text/event-stream")


@router.post("/suggest-reply")
async def suggest_reply(
    data: SuggestReplyRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    from sqlalchemy import select
    from app.models.conversation import Conversation, ConversationMessage
    from app.models.customer import Customer

    conv = await session.get(Conversation, data.conversation_id)
    if not conv:
        return {"reply": ""}
    customer = await session.get(Customer, conv.customer_id)
    if not customer:
        return {"reply": ""}

    stmt = select(ConversationMessage).where(
        ConversationMessage.conversation_id == data.conversation_id
    ).order_by(ConversationMessage.created_at.desc()).limit(15)
    result = await session.execute(stmt)
    history = list(reversed(result.scalars().all()))

    from app.ai.crm_engine import AICRMEngine
    engine = AICRMEngine(session)
    reply = await engine.generate_suggested_reply(customer, history, context=data.context)
    return {"reply": reply}


@router.post("/qualify-lead/{customer_id}")
async def qualify_lead(
    customer_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    from sqlalchemy import select
    from app.models.conversation import Conversation, ConversationMessage
    from app.models.customer import Customer

    customer = await session.get(Customer, customer_id)
    if not customer:
        return {}

    stmt = select(ConversationMessage).join(
        Conversation, Conversation.id == ConversationMessage.conversation_id
    ).where(Conversation.customer_id == customer_id).order_by(
        ConversationMessage.created_at.desc()
    ).limit(50)
    result = await session.execute(stmt)
    messages = result.scalars().all()
    conversation_text = "\n".join([m.content or "" for m in messages if m.content])

    from app.ai.crm_engine import AICRMEngine
    engine = AICRMEngine(session)
    qualification = await engine.qualify_lead(customer, conversation_text)
    return qualification
