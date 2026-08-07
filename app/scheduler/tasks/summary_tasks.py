from __future__ import annotations

import json
import re

from app.core.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger(__name__)


def safe_parse_ai_json(response_text: str) -> dict:
    """Extract JSON from AI response even if it contains extra text or markdown."""
    if not response_text:
        return {}

    # Remove markdown code blocks if present
    cleaned = re.sub(r'```json\s*|\s*```', '', response_text).strip()

    # Try direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object within the text
    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Log what we got so we can debug further
    logger.warning(
        "Could not parse AI JSON response",
        response_preview=response_text[:200],
    )

    # Return safe defaults if all parsing fails
    return {
        "intent": "unknown",
        "sentiment": "neutral",
        "urgency": "low",
        "entities": [],
        "should_escalate": False,
        "suggested_reply": None,
    }


@celery_app.task(name="app.scheduler.tasks.summary_tasks.summarize_long_conversations")
def summarize_long_conversations() -> dict:
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_summarize_conversations())


async def _summarize_conversations() -> dict:
    # ── Import ALL models first so SQLAlchemy resolves all foreign keys ──────
    import app.models.auth                # noqa: F401
    import app.models.customer            # noqa: F401
    import app.models.company             # noqa: F401
    import app.models.lead                # noqa: F401
    import app.models.conversation        # noqa: F401
    import app.models.conversation_summary  # noqa: F401
    import app.models.activity            # noqa: F401
    import app.models.note                # noqa: F401
    import app.models.task                # noqa: F401
    import app.models.notification        # noqa: F401
    import app.models.whatsapp_template   # noqa: F401
    import app.models.appointment         # noqa: F401
    import app.models.order               # noqa: F401
    import app.models.product             # noqa: F401
    import app.models.ticket              # noqa: F401
    import app.models.campaign            # noqa: F401
    import app.models.followup            # noqa: F401
    import app.models.tag                 # noqa: F401
    # ─────────────────────────────────────────────────────────────────────────

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
                # existing = await session.get(ConversationSummary, conv.id)
                existing = await session.scalar(
                    select(ConversationSummary).where(ConversationSummary.conversation_id == conv.id)
                )
                
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

    # ── Import ALL models first so SQLAlchemy resolves all foreign keys ──────
    import app.models.auth                # noqa: F401
    import app.models.customer            # noqa: F401
    import app.models.company             # noqa: F401
    import app.models.lead                # noqa: F401
    import app.models.conversation        # noqa: F401
    import app.models.conversation_summary  # noqa: F401
    import app.models.activity            # noqa: F401
    import app.models.note                # noqa: F401
    import app.models.task                # noqa: F401
    import app.models.notification        # noqa: F401
    import app.models.whatsapp_template   # noqa: F401
    import app.models.appointment         # noqa: F401
    import app.models.order               # noqa: F401
    import app.models.product             # noqa: F401
    import app.models.ticket              # noqa: F401
    import app.models.campaign            # noqa: F401
    import app.models.followup            # noqa: F401
    import app.models.tag                 # noqa: F401
    # ─────────────────────────────────────────────────────────────────────────

    from app.core.database.base import AsyncSessionLocal
    from app.models.conversation import Conversation, ConversationMessage
    from app.models.customer import Customer
    from app.ai.crm_engine import AICRMEngine

    async with AsyncSessionLocal() as session:
        try:
            msg_id = uuid.UUID(message_id)
            message = await session.get(ConversationMessage, msg_id)
            if not message:
                logger.warning("Message not found", message_id=message_id)
                return {"error": "message not found"}

            conv = await session.get(Conversation, message.conversation_id)
            if not conv:
                logger.warning("Conversation not found", message_id=message_id)
                return {"error": "conversation not found"}

            customer = await session.get(Customer, conv.customer_id)
            if not customer:
                logger.warning("Customer not found", message_id=message_id)
                return {"error": "customer not found"}

            history_stmt = (
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == conv.id)
                .order_by(ConversationMessage.created_at.desc())
                .limit(20)
            )
            history = list(
                reversed((await session.execute(history_stmt)).scalars().all())
            )

            engine = AICRMEngine(session)

            # ── Call AI and handle errors gracefully ──────────────────────
            try:
                analysis = await engine.process_message(message, customer, history)
            except Exception as ai_error:
                logger.error(
                    "AI processing failed",
                    message_id=message_id,
                    error=str(ai_error),
                    error_type=type(ai_error).__name__,
                )
                analysis = safe_parse_ai_json("")
            # ─────────────────────────────────────────────────────────────

            # If analysis came back as a string instead of dict, parse it
            if isinstance(analysis, str):
                analysis = safe_parse_ai_json(analysis)

            logger.info(
                "AI analysis complete",
                message_id=message_id,
                intent=analysis.get("intent"),
                sentiment=analysis.get("sentiment"),
                should_escalate=analysis.get("should_escalate"),
            )

            # Update conversation urgency
            if analysis.get("urgency"):
                conv.urgency = analysis["urgency"]

            # Auto-reply if bot is active and we have a suggested reply
            if conv.is_bot_active and analysis.get("suggested_reply"):
                try:
                    from app.whatsapp.conversation_service import WhatsAppConversationService
                    wa_service = WhatsAppConversationService(session)
                    await wa_service.send_reply(conv.id, analysis["suggested_reply"])
                    logger.info(
                        "AI auto-reply sent",
                        message_id=message_id,
                        conversation_id=str(conv.id),
                    )
                except Exception as reply_error:
                    logger.error(
                        "Failed to send auto-reply",
                        message_id=message_id,
                        error=str(reply_error),
                    )

            await session.commit()
            return {
                "status": "processed",
                "intent": analysis.get("intent"),
                "sentiment": analysis.get("sentiment"),
                "should_escalate": analysis.get("should_escalate"),
            }

        except Exception as e:
            logger.error(
                "Inbound processing failed",
                message_id=message_id,
                error=str(e),
            )
            return {"error": str(e)}