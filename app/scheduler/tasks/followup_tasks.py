from __future__ import annotations

from app.core.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(name="app.scheduler.tasks.followup_tasks.process_due_followups")
def process_due_followups() -> dict:
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_process_due_followups())


async def _process_due_followups() -> dict:
    from app.core.database.base import AsyncSessionLocal
    from app.repositories.crm import FollowUpRepository
    from app.whatsapp.client import get_whatsapp_client
    from app.models.followup import FollowUpStatus

    processed = 0
    async with AsyncSessionLocal() as session:
        repo = FollowUpRepository(session)
        due = await repo.get_due_followups()
        client = get_whatsapp_client()

        for followup in due:
            try:
                from app.repositories.crm import CustomerRepository
                cust_repo = CustomerRepository(session)
                customer = await cust_repo.get_by_id(followup.customer_id)
                if customer and customer.phone:
                    await client.send_text(to=customer.phone, body=followup.message or followup.subject)
                    from datetime import UTC, datetime
                    await repo.update(followup, status=FollowUpStatus.SENT, sent_at=datetime.now(UTC))
                    processed += 1
            except Exception as e:
                logger.error("Failed to send followup", followup_id=str(followup.id), error=str(e))

        await session.commit()
    return {"processed": processed}


@celery_app.task(name="app.scheduler.tasks.followup_tasks.remind_inactive_customers")
def remind_inactive_customers() -> dict:
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_remind_inactive_customers())


async def _remind_inactive_customers() -> dict:
    from app.core.database.base import AsyncSessionLocal
    from app.repositories.crm import CustomerRepository
    from app.whatsapp.client import get_whatsapp_client

    reminded = 0
    async with AsyncSessionLocal() as session:
        repo = CustomerRepository(session)
        inactive = await repo.get_inactive_customers(days=30)
        client = get_whatsapp_client()

        for customer in inactive:
            if customer.phone:
                try:
                    await client.send_text(
                        to=customer.phone,
                        body=f"Hi {customer.first_name}, we miss you! Is there anything we can help you with today?",
                    )
                    reminded += 1
                except Exception as e:
                    logger.error("Reminder failed", customer_id=str(customer.id), error=str(e))

        await session.commit()
    return {"reminded": reminded}
