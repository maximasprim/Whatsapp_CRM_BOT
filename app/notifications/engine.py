from __future__ import annotations

import uuid
from enum import Enum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.notification import NotificationType
from app.notifications.channels.email_channel import get_email_channel
from app.notifications.channels.push_channel import get_push_channel
from app.notifications.channels.sms_channel import get_sms_channel
from app.notifications.templates.registry import render_subject, render_template
from app.services.crm import NotificationService

logger = get_logger(__name__)


class NotificationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    PUSH = "push"
    INTERNAL = "internal"


class NotificationEngine:
    """Single entry point for sending notifications across every channel.
    Each send_* call is independent and failures in one channel never block
    the others — every attempt is logged."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.email = get_email_channel()
        self.sms = get_sms_channel()
        self.push = get_push_channel()
        self.internal_repo = NotificationService(session)

    async def send_templated(
        self,
        template_key: str,
        context: dict[str, Any],
        channels: list[NotificationChannel],
        *,
        email_to: str | None = None,
        sms_to: str | None = None,
        whatsapp_to: str | None = None,
        push_token: str | None = None,
        internal_user_id: uuid.UUID | None = None,
        internal_entity_type: str | None = None,
        internal_entity_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        results: dict[str, Any] = {}

        if NotificationChannel.EMAIL in channels and email_to:
            try:
                subject = render_subject(template_key, context)
                body = render_template(template_key, "email", context)
                results["email"] = await self.email.send_async(email_to, subject, body)
            except Exception as exc:
                logger.error("Email notification failed", template=template_key, error=str(exc))
                results["email"] = {"status": "failed", "error": str(exc)}

        if NotificationChannel.SMS in channels and sms_to:
            try:
                body = render_template(template_key, "sms", context)
                results["sms"] = await self.sms.send(sms_to, body)
            except Exception as exc:
                logger.error("SMS notification failed", template=template_key, error=str(exc))
                results["sms"] = {"status": "failed", "error": str(exc)}

        if NotificationChannel.WHATSAPP in channels and whatsapp_to:
            try:
                from app.whatsapp.client import get_whatsapp_client
                body = render_template(template_key, "whatsapp", context)
                client = get_whatsapp_client()
                wa_result = await client.send_text(to=whatsapp_to, body=body)
                results["whatsapp"] = {"status": "sent", "response": wa_result}
            except Exception as exc:
                logger.error("WhatsApp notification failed", template=template_key, error=str(exc))
                results["whatsapp"] = {"status": "failed", "error": str(exc)}

        if NotificationChannel.PUSH in channels and push_token:
            try:
                subject = render_subject(template_key, context)
                body = render_template(template_key, "sms", context)  # push uses short body
                results["push"] = await self.push.send(push_token, subject, body)
            except Exception as exc:
                logger.error("Push notification failed", template=template_key, error=str(exc))
                results["push"] = {"status": "failed", "error": str(exc)}

        if NotificationChannel.INTERNAL in channels and internal_user_id:
            try:
                subject = render_subject(template_key, context)
                body = render_template(template_key, "sms", context)
                notif = await self.internal_repo.create(
                    user_id=internal_user_id,
                    title=subject,
                    body=body,
                    notification_type=self._map_notification_type(template_key),
                    entity_type=internal_entity_type,
                    entity_id=internal_entity_id,
                )
                results["internal"] = {"status": "created", "id": str(notif.id)}
            except Exception as exc:
                logger.error("Internal notification failed", template=template_key, error=str(exc))
                results["internal"] = {"status": "failed", "error": str(exc)}

        return results

    @staticmethod
    def _map_notification_type(template_key: str) -> NotificationType:
        mapping = {
            "appointment_confirmation": NotificationType.APPOINTMENT,
            "appointment_reminder": NotificationType.APPOINTMENT,
            "ticket_created": NotificationType.TICKET,
            "ticket_resolved": NotificationType.TICKET,
            "lead_assigned": NotificationType.LEAD,
            "order_confirmation": NotificationType.SUCCESS,
        }
        return mapping.get(template_key, NotificationType.INFO)
