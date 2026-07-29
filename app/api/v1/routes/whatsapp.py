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

    if settings.WHATSAPP_APP_SECRET and not _verify_signature(body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")

    payload = await request.json()
    messages, statuses = parse_webhook_payload(payload)

    service = WhatsAppConversationService(session)

    for parsed_msg in messages:
        try:
            msg = await service.handle_inbound_message(parsed_msg)
            # Trigger AI processing in background
            from app.core.celery_app import celery_app
            celery_app.send_task(
                "app.scheduler.tasks.summary_tasks.process_inbound_message",
                args=[str(msg.id)],
            )
        except Exception as exc:
            logger.error("Error handling inbound message", error=str(exc), message_id=parsed_msg.message_id)

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
