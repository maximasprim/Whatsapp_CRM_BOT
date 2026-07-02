from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.database.base import get_db
from app.models.auth import User

router = APIRouter(prefix="/rag", tags=["RAG"])


class RAGQueryRequest(BaseModel):
    question: str
    top_k: int = 5
    min_similarity: float = 0.3
    conversation_context: str = ""


class RAGCitationResponse(BaseModel):
    document_id: str
    document_title: str
    chunk_id: str
    similarity: float


class RAGQueryResponse(BaseModel):
    answer: str
    citations: list[RAGCitationResponse]
    context_found: bool
    confidence: float
    should_escalate: bool


@router.post("/query", response_model=RAGQueryResponse)
async def rag_query(
    data: RAGQueryRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RAGQueryResponse:
    from app.ai.knowledge_base.rag_pipeline import RAGPipeline
    pipeline = RAGPipeline(session)
    response, should_escalate = await pipeline.answer_with_fallback_to_human(data.question)

    return RAGQueryResponse(
        answer=response.answer,
        citations=[
            RAGCitationResponse(
                document_id=c.document_id, document_title=c.document_title,
                chunk_id=c.chunk_id, similarity=c.similarity,
            )
            for c in response.citations
        ],
        context_found=response.context_found,
        confidence=response.confidence,
        should_escalate=should_escalate,
    )


@router.post("/conversations/{conversation_id}/auto-reply")
async def rag_auto_reply(
    conversation_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Generate a RAG-grounded reply for the latest customer message in a conversation,
    and send it via WhatsApp if confidence is high enough."""
    from sqlalchemy import select
    from app.models.conversation import Conversation, ConversationMessage, MessageDirection
    from app.ai.knowledge_base.rag_pipeline import RAGPipeline

    conv = await session.get(Conversation, conversation_id)
    if not conv:
        return {"error": "Conversation not found."}

    stmt = select(ConversationMessage).where(
        ConversationMessage.conversation_id == conversation_id,
        ConversationMessage.direction == MessageDirection.INBOUND,
    ).order_by(ConversationMessage.created_at.desc()).limit(1)
    result = await session.execute(stmt)
    last_message = result.scalars().first()

    if not last_message or not last_message.content:
        return {"error": "No customer question found."}

    pipeline = RAGPipeline(session)
    rag_response, should_escalate = await pipeline.answer_with_fallback_to_human(last_message.content)

    if should_escalate:
        from app.models.conversation import ConversationStatus
        conv.status = ConversationStatus.ESCALATED
        conv.is_bot_active = False
        session.add(conv)
        await session.commit()
        return {
            "escalated": True,
            "reason": "Low confidence or no relevant knowledge base content found.",
        }

    from app.whatsapp.conversation_service import WhatsAppConversationService
    wa_service = WhatsAppConversationService(session)
    await wa_service.send_reply(conversation_id, rag_response.answer)
    await session.commit()

    return {
        "escalated": False,
        "answer": rag_response.answer,
        "confidence": rag_response.confidence,
        "sources": [c.document_title for c in rag_response.citations],
    }
