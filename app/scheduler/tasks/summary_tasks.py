"""
Updated Celery tasks — tenant-aware.
The process_inbound_message task now accepts tenant_id
so it can use the correct AI provider and WhatsApp credentials per tenant.

Replace app/scheduler/tasks/summary_tasks.py with this.
"""
from __future__ import annotations

import json
import re
import uuid

from app.core.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger(__name__)


def safe_parse_ai_json(response_text: str) -> dict:
    """Extract JSON from AI response even if it contains extra text."""
    if not response_text:
        return {}
    cleaned = re.sub(r'```json\s*|\s*```', '', response_text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    logger.warning("Could not parse AI JSON", preview=response_text[:200])
    return {
        "intent": "unknown",
        "sentiment": "neutral",
        "urgency": "low",
        "entities": [],
        "should_escalate": False,
        "suggested_reply": None,
    }


@celery_app.task(
    name="app.scheduler.tasks.summary_tasks.process_inbound_message"
)
def process_inbound_message(
    message_id: str,
    tenant_id: str | None = None,   # ← new parameter
) -> dict:
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _process_inbound(message_id, tenant_id)
    )


async def _process_inbound(
    message_id: str,
    tenant_id: str | None = None,
) -> dict:
    import uuid as _uuid
    from sqlalchemy import select

    # ── Register all models ───────────────────────────────────────────────────
    import app.models.auth                  # noqa: F401
    import app.models.tenant                # noqa: F401
    import app.models.customer              # noqa: F401
    import app.models.company               # noqa: F401
    import app.models.lead                  # noqa: F401
    import app.models.conversation          # noqa: F401
    import app.models.conversation_summary  # noqa: F401
    import app.models.activity              # noqa: F401
    import app.models.note                  # noqa: F401
    import app.models.task                  # noqa: F401
    import app.models.notification          # noqa: F401
    import app.models.whatsapp_template     # noqa: F401
    import app.models.appointment           # noqa: F401
    import app.models.order                 # noqa: F401
    import app.models.product               # noqa: F401
    import app.models.ticket                # noqa: F401
    import app.models.campaign              # noqa: F401
    import app.models.follow_up              # noqa: F401
    import app.models.tag                   # noqa: F401
    import app.models.knowledge_document    # noqa: F401
    import app.models.calendar_credential   # noqa: F401
    # ─────────────────────────────────────────────────────────────────────────

    from app.core.database.base import AsyncSessionLocal
    from app.models.conversation import Conversation, ConversationMessage
    from app.models.customer import Customer
    from app.models.tenant import Tenant

    async with AsyncSessionLocal() as session:
        try:
            msg_id = _uuid.UUID(message_id)
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

            # ── Load tenant ───────────────────────────────────────────────────
            tenant = None
            if tenant_id:
                tenant = await session.get(Tenant, _uuid.UUID(tenant_id))
            elif hasattr(conv, "tenant_id") and conv.tenant_id:
                tenant = await session.get(Tenant, conv.tenant_id)

            if tenant is None:
                logger.error("Could not resolve tenant for inbound message; skipping", message_id=message_id)
                return {"error": "tenant not found"}

            logger.info(
                "Processing inbound message",
                message_id=message_id,
                tenant_slug=tenant.slug if tenant else "default",
            )
            # ─────────────────────────────────────────────────────────────────

            history_stmt = (
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == conv.id)
                .order_by(ConversationMessage.created_at.desc())
                .limit(20)
            )
            history = list(
                reversed((await session.execute(history_stmt)).scalars().all())
            )

            # ── Use tenant-aware AI engine ────────────────────────────────────
            from app.ai.tenant_ai_engine import TenantAwareCRMEngine
            engine = TenantAwareCRMEngine(session, tenant=tenant)
            # ─────────────────────────────────────────────────────────────────

            try:
                analysis = await engine.process_message(message, customer, history)
            except Exception as ai_error:
                logger.error(
                    "AI processing failed",
                    message_id=message_id,
                    error=str(ai_error),
                )
                analysis = safe_parse_ai_json("")

            if isinstance(analysis, str):
                analysis = safe_parse_ai_json(analysis)

            logger.info(
                "AI analysis complete",
                message_id=message_id,
                intent=analysis.get("intent"),
                sentiment=analysis.get("sentiment"),
                should_escalate=analysis.get("should_escalate"),
            )

            if analysis.get("urgency"):
                conv.urgency = analysis["urgency"]

            # ── Auto-reply using tenant WhatsApp credentials ──────────────────
            if conv.is_bot_active and analysis.get("suggested_reply"):
                try:
                    from app.whatsapp.conversation_service import WhatsAppConversationService

                    wa_service = WhatsAppConversationService(
                        session, tenant=tenant
                    )
                    await wa_service.send_reply(
                        conv.id, analysis["suggested_reply"]
                    )
                    logger.info(
                        "AI auto-reply sent",
                        message_id=message_id,
                        tenant_slug=tenant.slug if tenant else "default",
                    )
                except Exception as reply_error:
                    logger.error(
                        "Failed to send auto-reply",
                        message_id=message_id,
                        error=str(reply_error),
                    )
            # ─────────────────────────────────────────────────────────────────

            await session.commit()
            return {
                "status": "processed",
                "intent": analysis.get("intent"),
                "sentiment": analysis.get("sentiment"),
                "should_escalate": analysis.get("should_escalate"),
                "tenant": tenant.slug if tenant else "default",
            }

        except Exception as e:
            logger.error(
                "Inbound processing failed",
                message_id=message_id,
                error=str(e),
            )
            return {"error": str(e)}


@celery_app.task(
    name="app.scheduler.tasks.summary_tasks.summarize_long_conversations"
)
def summarize_long_conversations() -> dict:
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _summarize_conversations()
    )


async def _summarize_conversations() -> dict:
    import app.models.auth                  # noqa: F401
    import app.models.tenant                # noqa: F401
    import app.models.customer              # noqa: F401
    import app.models.conversation          # noqa: F401
    import app.models.conversation_summary  # noqa: F401
    import app.models.activity              # noqa: F401
    import app.models.note                  # noqa: F401
    import app.models.task                  # noqa: F401

    from sqlalchemy import func, select
    from app.core.database.base import AsyncSessionLocal
    from app.models.conversation import Conversation, ConversationMessage, ConversationStatus
    from app.models.conversation_summary import ConversationSummary
    from app.models.customer import Customer
    from app.models.tenant import Tenant

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

                # Load tenant for this conversation
                tenant = None
                if hasattr(conv, "tenant_id") and conv.tenant_id:
                    tenant = await session.get(Tenant, conv.tenant_id)
                if tenant is None:
                    logger.error("Could not resolve tenant for conversation; skipping", conv_id=str(conv.id))
                    continue

                from app.ai.tenant_ai_engine import TenantAwareCRMEngine
                engine = TenantAwareCRMEngine(session, tenant=tenant)
                summary_text = await engine.summarize_conversation(
                    list(msgs), customer
                )

                from sqlalchemy.dialects.postgresql import insert as pg_insert
                stmt_insert = pg_insert(ConversationSummary).values(
                    conversation_id=conv.id,
                    customer_id=conv.customer_id,
                    tenant_id=conv.tenant_id if hasattr(conv, "tenant_id") else None,
                    summary=summary_text,
                    message_count=len(msgs),
                ).on_conflict_do_update(
                    index_elements=["conversation_id"],
                    set_={
                        "summary": summary_text,
                        "message_count": len(msgs),
                    }
                )
                await session.execute(stmt_insert)
                summarized += 1

            except Exception as e:
                logger.error(
                    "Summarization failed",
                    conv_id=str(conv.id),
                    error=str(e),
                )

        await session.commit()
    return {"summarized": summarized}
