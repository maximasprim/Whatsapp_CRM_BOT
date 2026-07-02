from __future__ import annotations

from app.core.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(name="app.scheduler.tasks.summary_tasks.summarize_long_conversations")
def summarize_long_conversations() -> dict:
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_summarize_conversations())


async def _summarize_conversations() -> dict:
    from sqlalchemy import func, select
    from app.core.database.base import AsyncSessionLocal
    from app.models.conversation import Conversation, ConversationMessage, ConversationStatus
    from app.models.conversation_summary import ConversationSummary
    from app.models.customer import Customer
    from app.ai.crm_engine import AICRMEngine

    summarized = 0
    async with AsyncSessionLocal() as session:
        stmt = (
            select(Conversation)
            .where(Conversation.status.notin_([ConversationStatus.CLOSED]))
            .join(ConversationMessage, ConversationMessage.conversation_id == Conversation.id)
            .group_by(Conversation.id)
            .having(func.count(ConversationMessage.id) >= 20)
        )
        result = await session.execute(stmt)
        conversations = result.scalars().all()

        for conv in conversations:
            try:
                existing = await session.get(ConversationSummary, conv.id)
                if existing:
                    continue
                msg_stmt = select(ConversationMessage).where(
                    ConversationMessage.conversation_id == conv.id
                ).order_by(ConversationMessage.created_at)
                msgs = (await session.execute(msg_stmt)).scalars().all()
                customer = await session.get(Customer, conv.customer_id)
                if not customer:
                    continue
                engine = AICRMEngine(session)
                summary_text = await engine.summarize_conversation(list(msgs), customer)
                summary = ConversationSummary(
                    conversation_id=conv.id,
                    customer_id=conv.customer_id,
                    summary=summary_text,
                    message_count=len(msgs),
                )
                session.add(summary)
                summarized += 1
            except Exception as e:
                logger.error("Summarization failed", conv_id=str(conv.id), error=str(e))

        await session.commit()
    return {"summarized": summarized}


@celery_app.task(name="app.scheduler.tasks.summary_tasks.process_inbound_message")
def process_inbound_message(message_id: str) -> dict:
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_process_inbound(message_id))


async def _process_inbound(message_id: str) -> dict:
    import uuid
    from sqlalchemy import select
    from app.core.database.base import AsyncSessionLocal
    from app.models.conversation import Conversation, ConversationMessage
    from app.models.customer import Customer
    from app.ai.crm_engine import AICRMEngine

    async with AsyncSessionLocal() as session:
        try:
            msg_id = uuid.UUID(message_id)
            message = await session.get(ConversationMessage, msg_id)
            if not message:
                return {"error": "message not found"}
            conv = await session.get(Conversation, message.conversation_id)
            if not conv:
                return {"error": "conversation not found"}
            customer = await session.get(Customer, conv.customer_id)
            if not customer:
                return {"error": "customer not found"}

            history_stmt = select(ConversationMessage).where(
                ConversationMessage.conversation_id == conv.id
            ).order_by(ConversationMessage.created_at.desc()).limit(20)
            history = list(reversed((await session.execute(history_stmt)).scalars().all()))

            engine = AICRMEngine(session)
            analysis = await engine.process_message(message, customer, history)

            # Auto-reply if bot is active
            if conv.is_bot_active and analysis.get("suggested_reply"):
                from app.whatsapp.conversation_service import WhatsAppConversationService
                wa_service = WhatsAppConversationService(session)
                await wa_service.send_reply(conv.id, analysis["suggested_reply"])

            await session.commit()
            return {"status": "processed", "intent": analysis.get("intent")}
        except Exception as e:
            logger.error("Inbound processing failed", message_id=message_id, error=str(e))
            return {"error": str(e)}
