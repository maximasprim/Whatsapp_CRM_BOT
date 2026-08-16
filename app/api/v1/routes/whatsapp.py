"""
Updated whatsapp.py — tenant-aware webhook routing.
Each tenant gets their own webhook URL:
  /api/whatsapp/webhook/{tenant_slug}

The old /api/whatsapp/webhook still works for backward compatibility
and routes to the default tenant.
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database.base import get_db
from app.core.logging import get_logger
from app.models.tenant import Tenant
from app.schemas.common import SuccessResponse
from app.whatsapp.conversation_service import WhatsAppConversationService
from app.whatsapp.webhook_parser import parse_webhook_payload
from app.auth.dependencies import get_current_user
from app.models.auth import User

logger = get_logger(__name__)
router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])


class SendTextRequest(BaseModel):
    to: str
    body: str
    preview_url: bool = False


def _verify_signature(body: bytes, signature: str, app_secret: str) -> bool:
    """Verify HMAC-SHA256 webhook signature."""
    if not app_secret:
        return True
    if not signature.startswith("sha256="):
        return False
    expected = hmac.new(
        app_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature[7:])


async def _get_tenant_by_slug(slug: str, session: AsyncSession) -> Tenant:
    """Look up a tenant by slug — raise 404 if not found or inactive."""
    result = await session.execute(
        select(Tenant).where(Tenant.slug == slug, Tenant.is_active == True)
    )
    tenant = result.scalars().first()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Tenant '{slug}' not found.")
    return tenant


async def _process_webhook(
    request: Request,
    session: AsyncSession,
    tenant: Tenant,
    x_hub_signature_256: str,
) -> SuccessResponse:
    """Shared webhook processing logic for all tenants."""
    body = await request.body()

    logger.info(
        "Webhook POST received",
        tenant_slug=tenant.slug,
        content_length=len(body),
        signature_present=bool(x_hub_signature_256),
    )

    # Verify signature using tenant's app secret
    app_secret = tenant.whatsapp_app_secret or settings.WHATSAPP_APP_SECRET or ""
    if app_secret and not _verify_signature(body, x_hub_signature_256, app_secret):
        logger.error("Webhook signature failed", tenant_slug=tenant.slug)
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")

    try:
        payload = await request.json()
    except Exception as e:
        logger.error("Failed to parse webhook JSON", error=str(e))
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    logger.info(
        "Webhook payload",
        tenant_slug=tenant.slug,
        object_type=payload.get("object"),
        entry_count=len(payload.get("entry", [])),
    )

    messages, statuses = parse_webhook_payload(payload)

    logger.info(
        "Webhook parsed",
        tenant_slug=tenant.slug,
        message_count=len(messages),
        status_count=len(statuses),
    )

    service = WhatsAppConversationService(session, tenant=tenant)

    for parsed_msg in messages:
        try:
            logger.info(
                "Processing inbound message",
                tenant_slug=tenant.slug,
                from_number=parsed_msg.from_number,
                message_id=parsed_msg.message_id,
            )
            msg = await service.handle_inbound_message(parsed_msg)
            await session.commit()
            logger.info("Message saved", db_message_id=str(msg.id))

            from app.core.celery_app import celery_app
            celery_app.send_task(
                "app.scheduler.tasks.summary_tasks.process_inbound_message",
                args=[str(msg.id), str(tenant.id)],
            )
            logger.info("Celery task queued", db_message_id=str(msg.id))

        except Exception as exc:
            logger.error(
                "Error handling inbound message",
                error=str(exc),
                message_id=parsed_msg.message_id,
                tenant_slug=tenant.slug,
            )

    for status in statuses:
        try:
            await service.handle_status_update(status)
            await session.commit()
        except Exception as exc:
            logger.error("Error handling status update", error=str(exc))

    return SuccessResponse(message="OK")


# ── Per-tenant webhook routes ─────────────────────────────────────────────────

@router.get("/webhook/{tenant_slug}")
async def verify_webhook_tenant(
    tenant_slug: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> PlainTextResponse:
    """Webhook verification for a specific tenant."""
    tenant = await _get_tenant_by_slug(tenant_slug, session)

    # Use tenant's verify token or fall back to global setting
    expected_token = (
        tenant.whatsapp_webhook_verify_token
        or settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN
    )

    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        logger.info("Webhook verified", tenant_slug=tenant_slug)
        return PlainTextResponse(content=hub_challenge)

    raise HTTPException(status_code=403, detail="Webhook verification failed.")


@router.post("/webhook/{tenant_slug}")
async def receive_webhook_tenant(
    tenant_slug: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    x_hub_signature_256: str = Header(default=""),
) -> SuccessResponse:
    """Receive inbound WhatsApp messages for a specific tenant."""
    tenant = await _get_tenant_by_slug(tenant_slug, session)
    return await _process_webhook(request, session, tenant, x_hub_signature_256)


# ── Backward-compatible default webhook (routes to default tenant) ─────────────

@router.get("/webhook")
async def verify_webhook_default(
    session: Annotated[AsyncSession, Depends(get_db)],
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> PlainTextResponse:
    """Webhook verification — backward compatible, routes to default tenant."""
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN:
        logger.info("Default webhook verified")
        return PlainTextResponse(content=hub_challenge)
    raise HTTPException(status_code=403, detail="Webhook verification failed.")


@router.post("/webhook")
async def receive_webhook_default(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    x_hub_signature_256: str = Header(default=""),
) -> SuccessResponse:
    """Receive webhook — backward compatible, routes to default tenant."""
    tenant = await _get_tenant_by_slug("default", session)
    return await _process_webhook(request, session, tenant, x_hub_signature_256)


# ── Send message ──────────────────────────────────────────────────────────────

@router.post("/send-text")
async def send_text_message(
    data: SendTextRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SuccessResponse:
    """Send a text message using the current tenant's WhatsApp credentials."""
    from app.whatsapp.client import WhatsAppClient

    # Get tenant from current user
    tenant = await session.get(Tenant, current_user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")

    # Use tenant credentials or fall back to global settings
    phone_number_id = (
        tenant.whatsapp_phone_number_id or settings.WHATSAPP_PHONE_NUMBER_ID
    )
    access_token = (
        tenant.whatsapp_access_token or settings.WHATSAPP_ACCESS_TOKEN
    )

    client = WhatsAppClient(
        phone_number_id=phone_number_id,
        access_token=access_token,
    )
    await client.send_text(to=data.to, body=data.body, preview_url=data.preview_url)
    return SuccessResponse(message="Message sent.")



# from __future__ import annotations

# import hashlib
# import hmac
# from typing import Annotated, Any

# from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.auth.dependencies import get_current_user
# from app.core.config import settings
# from app.core.database.base import get_db
# from app.core.logging import get_logger
# from app.models.auth import User
# from app.schemas.common import SuccessResponse
# from app.whatsapp.conversation_service import WhatsAppConversationService
# from app.whatsapp.webhook_parser import parse_webhook_payload
# from fastapi.responses import PlainTextResponse
# from pydantic import BaseModel

# logger = get_logger(__name__)
# router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])


# def _verify_signature(body: bytes, signature: str) -> bool:
#     if not signature.startswith("sha256="):
#         return False
#     expected = hmac.new(
#         settings.WHATSAPP_APP_SECRET.encode(), body, hashlib.sha256
#     ).hexdigest()
#     return hmac.compare_digest(expected, signature[7:])


# @router.get("/webhook")
# async def verify_webhook(
#     hub_mode: str = Query(alias="hub.mode"),
#     hub_verify_token: str = Query(alias="hub.verify_token"),
#     hub_challenge: str = Query(alias="hub.challenge"),
# ) -> PlainTextResponse:
#     if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN:
#         logger.info("WhatsApp webhook verified")
#         return PlainTextResponse(content=hub_challenge)
#     raise HTTPException(status_code=403, detail="Webhook verification failed.")


# @router.post("/webhook")
# async def receive_webhook(
#     request: Request,
#     session: Annotated[AsyncSession, Depends(get_db)],
#     x_hub_signature_256: str = Header(default=""),
# ) -> SuccessResponse:
#     body = await request.body()

#     # ── Debug logging ─────────────────────────────────────────────────────
#     logger.info(
#         "Webhook POST received",
#         content_length=len(body),
#         signature_present=bool(x_hub_signature_256),
#         user_agent=request.headers.get("user-agent", "unknown"),
#         content_type=request.headers.get("content-type", "unknown"),
#     )
#     # ─────────────────────────────────────────────────────────────────────

#     if settings.WHATSAPP_APP_SECRET and not _verify_signature(body, x_hub_signature_256):
#         logger.error(
#             "Webhook signature verification failed",
#             signature=x_hub_signature_256[:20] if x_hub_signature_256 else "none",
#         )
#         raise HTTPException(status_code=401, detail="Invalid webhook signature.")

#     try:
#         payload = await request.json()
#     except Exception as e:
#         logger.error("Failed to parse webhook JSON", error=str(e), body=body[:200].decode())
#         raise HTTPException(status_code=400, detail="Invalid JSON payload.")

#     # ── Debug — log the full payload ──────────────────────────────────────
#     logger.info(
#         "Webhook payload received",
#         object_type=payload.get("object"),
#         entry_count=len(payload.get("entry", [])),
#         payload_preview=str(payload)[:500],
#     )
#     # ─────────────────────────────────────────────────────────────────────

#     messages, statuses = parse_webhook_payload(payload)

#     logger.info(
#         "Webhook parsed",
#         message_count=len(messages),
#         status_count=len(statuses),
#     )

#     service = WhatsAppConversationService(session)

#     for parsed_msg in messages:
#         try:
#             logger.info(
#                 "Processing inbound message",
#                 from_number=parsed_msg.from_number,
#                 message_id=parsed_msg.message_id,
#                 message_type=parsed_msg.message_type,
#                 content=parsed_msg.text[:100] if parsed_msg.text else None,
#             )
#             msg = await service.handle_inbound_message(parsed_msg)
#             logger.info("Message saved to DB", db_message_id=str(msg.id))

#             from app.core.celery_app import celery_app
#             celery_app.send_task(
#                 "app.scheduler.tasks.summary_tasks.process_inbound_message",
#                 args=[str(msg.id)],
#             )
#             logger.info("Celery task queued", db_message_id=str(msg.id))

#         except Exception as exc:
#             logger.error(
#                 "Error handling inbound message",
#                 error=str(exc),
#                 message_id=parsed_msg.message_id,
#             )

#     for status in statuses:
#         try:
#             await service.handle_status_update(status)
#         except Exception as exc:
#             logger.error("Error handling status update", error=str(exc))

#     return SuccessResponse(message="OK")

# class SendTextRequest(BaseModel):
#     to: str
#     body: str
#     preview_url: bool = False

# @router.post("/send-text")
# async def send_text_message(
#     data: SendTextRequest,
#     session: Annotated[AsyncSession, Depends(get_db)],
#     current_user: Annotated[User, Depends(get_current_user)],
# ) -> SuccessResponse:
#     from app.whatsapp.client import get_whatsapp_client
#     client = get_whatsapp_client()
#     await client.send_text(to=data.to, body=data.body, preview_url=data.preview_url)
#     return SuccessResponse(message="Message sent.")
