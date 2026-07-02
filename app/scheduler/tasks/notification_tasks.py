from __future__ import annotations

from app.core.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(name="app.scheduler.tasks.notification_tasks.send_email_notification")
def send_email_notification(to: str, subject: str, html_body: str, plain_body: str | None = None) -> dict:
    from app.notifications.channels.email_channel import get_email_channel
    channel = get_email_channel()
    try:
        return channel.send(to, subject, html_body, plain_body)
    except Exception as e:
        logger.error("Celery email task failed", to=to, error=str(e))
        return {"status": "failed", "error": str(e)}


@celery_app.task(name="app.scheduler.tasks.notification_tasks.send_sms_notification")
def send_sms_notification(to: str, body: str) -> dict:
    import asyncio
    from app.notifications.channels.sms_channel import get_sms_channel
    channel = get_sms_channel()
    try:
        return asyncio.get_event_loop().run_until_complete(channel.send(to, body))
    except Exception as e:
        logger.error("Celery SMS task failed", to=to, error=str(e))
        return {"status": "failed", "error": str(e)}


@celery_app.task(name="app.scheduler.tasks.notification_tasks.send_templated_notification")
def send_templated_notification(
    template_key: str,
    context: dict,
    channels: list[str],
    email_to: str | None = None,
    sms_to: str | None = None,
    whatsapp_to: str | None = None,
) -> dict:
    import asyncio
    return asyncio.get_event_loop().run_until_complete(
        _send_templated(template_key, context, channels, email_to, sms_to, whatsapp_to)
    )


async def _send_templated(
    template_key: str, context: dict, channels: list[str],
    email_to: str | None, sms_to: str | None, whatsapp_to: str | None,
) -> dict:
    from app.core.database.base import AsyncSessionLocal
    from app.notifications.engine import NotificationChannel, NotificationEngine

    async with AsyncSessionLocal() as session:
        engine = NotificationEngine(session)
        channel_enums = [NotificationChannel(c) for c in channels]
        result = await engine.send_templated(
            template_key=template_key,
            context=context,
            channels=channel_enums,
            email_to=email_to,
            sms_to=sms_to,
            whatsapp_to=whatsapp_to,
        )
        await session.commit()
        return result
