from __future__ import annotations

import hashlib
import hmac
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.config import settings
from app.core.database.base import get_db
from app.core.logging import get_logger
from app.models.auth import User
from app.schemas.common import SuccessResponse
from app.whatsapp.conversation_service import WhatsAppConversationService
from app.whatsapp.webhook_parser import parse_webhook_payload
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

logger = get_logger(__name__)
router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])


def _verify_signature(body: bytes, signature: str) -> bool:
    if not signature.startswith("sha256="):
        return False
    expected = hmac.new(
        settings.WHATSAPP_APP_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature[7:])


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> PlainTextResponse:
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN:
        logger.info("WhatsApp webhook verified")
        return PlainTextResponse(content=hub_challenge)
    raise HTTPException(status_code=403, detail="Webhook verification failed.")


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    x_hub_signature_256: str = Header(default=""),
) -> SuccessResponse:
    body = await request.body()

    # ── Debug logging ─────────────────────────────────────────────────────
    logger.info(
        "Webhook POST received",
        content_length=len(body),
        signature_present=bool(x_hub_signature_256),
        user_agent=request.headers.get("user-agent", "unknown"),
        content_type=request.headers.get("content-type", "unknown"),
    )
    # ─────────────────────────────────────────────────────────────────────

    if settings.WHATSAPP_APP_SECRET and not _verify_signature(body, x_hub_signature_256):
        logger.error(
            "Webhook signature verification failed",
            signature=x_hub_signature_256[:20] if x_hub_signature_256 else "none",
        )
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")

    try:
        payload = await request.json()
    except Exception as e:
        logger.error("Failed to parse webhook JSON", error=str(e), body=body[:200].decode())
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    # ── Debug — log the full payload ──────────────────────────────────────
    logger.info(
        "Webhook payload received",
        object_type=payload.get("object"),
        entry_count=len(payload.get("entry", [])),
        payload_preview=str(payload)[:500],
    )
    # ─────────────────────────────────────────────────────────────────────

    messages, statuses = parse_webhook_payload(payload)

    logger.info(
        "Webhook parsed",
        message_count=len(messages),
        status_count=len(statuses),
    )

    service = WhatsAppConversationService(session)

    for parsed_msg in messages:
        try:
            logger.info(
                "Processing inbound message",
                from_number=parsed_msg.from_number,
                message_id=parsed_msg.message_id,
                message_type=parsed_msg.message_type,
                content=parsed_msg.text[:100] if parsed_msg.text else None,
            )
            msg = await service.handle_inbound_message(parsed_msg)
            logger.info("Message saved to DB", db_message_id=str(msg.id))

            from app.core.celery_app import celery_app
            celery_app.send_task(
                "app.scheduler.tasks.summary_tasks.process_inbound_message",
                args=[str(msg.id)],
            )
            logger.info("Celery task queued", db_message_id=str(msg.id))

        except Exception as exc:
            logger.error(
                "Error handling inbound message",
                error=str(exc),
                message_id=parsed_msg.message_id,
            )

    for status in statuses:
        try:
            await service.handle_status_update(status)
        except Exception as exc:
            logger.error("Error handling status update", error=str(exc))

    return SuccessResponse(message="OK")

class SendTextRequest(BaseModel):
    to: str
    body: str
    preview_url: bool = False

@router.post("/send-text")
async def send_text_message(
    data: SendTextRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SuccessResponse:
    from app.whatsapp.client import get_whatsapp_client
    client = get_whatsapp_client()
    await client.send_text(to=data.to, body=data.body, preview_url=data.preview_url)
    return SuccessResponse(message="Message sent.")
