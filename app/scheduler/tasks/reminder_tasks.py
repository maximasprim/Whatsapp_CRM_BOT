from __future__ import annotations

from app.core.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(name="app.scheduler.tasks.reminder_tasks.send_appointment_reminders")
def send_appointment_reminders() -> dict:
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_send_appointment_reminders())


async def _send_appointment_reminders() -> dict:
    from app.core.database.base import AsyncSessionLocal
    from app.repositories.crm import AppointmentRepository, CustomerRepository
    from app.notifications.engine import NotificationChannel, NotificationEngine

    sent = 0
    async with AsyncSessionLocal() as session:
        appt_repo = AppointmentRepository(session)
        cust_repo = CustomerRepository(session)
        engine = NotificationEngine(session)
        upcoming = await appt_repo.get_upcoming(minutes_ahead=60)

        for appt in upcoming:
            try:
                customer = await cust_repo.get_by_id(appt.customer_id)
                if customer and customer.phone:
                    channels = [NotificationChannel.WHATSAPP]
                    if customer.email:
                        channels.append(NotificationChannel.EMAIL)
                    await engine.send_templated(
                        template_key="appointment_reminder",
                        context={
                            "first_name": customer.first_name,
                            "appointment_title": appt.title,
                            "appointment_time": appt.start_time.strftime("%H:%M"),
                        },
                        channels=channels,
                        whatsapp_to=customer.phone,
                        email_to=customer.email,
                    )
                    await appt_repo.update(appt, reminder_sent=True)
                    sent += 1
            except Exception as e:
                logger.error("Appointment reminder failed", appt_id=str(appt.id), error=str(e))

        await session.commit()
    return {"sent": sent}
