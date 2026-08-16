from __future__ import annotations

from app.core.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(name="app.scheduler.tasks.campaign_tasks.process_scheduled_campaigns")
def process_scheduled_campaigns() -> dict:
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_process_campaigns())


async def _process_campaigns() -> dict:
    from sqlalchemy import select
    from app.core.database.base import AsyncSessionLocal
    from app.models.campaign import CampaignStatus, RecipientStatus
    from app.models.tenant import Tenant
    from app.repositories.crm import CampaignRepository, CustomerRepository
    from app.whatsapp.client import get_whatsapp_client
    from datetime import UTC, datetime

    processed = 0
    async with AsyncSessionLocal() as session:
        tenants = (
            await session.execute(select(Tenant).where(Tenant.is_active == True))
        ).scalars().all()

        # This job scans every active tenant in turn, but every repository/
        # client instance below is scoped to that one tenant's id — so a
        # campaign in tenant A can never be processed with tenant B's data,
        # recipients, or WhatsApp credentials.
        for tenant in tenants:
            repo = CampaignRepository(session, tenant_id=tenant.id)
            cust_repo = CustomerRepository(session, tenant_id=tenant.id)
            client = get_whatsapp_client(tenant)
            campaigns = await repo.get_scheduled_campaigns()

            for campaign in campaigns:
                try:
                    await repo.update(campaign, status=CampaignStatus.RUNNING, started_at=datetime.now(UTC))
                    recipients = await repo.get_pending_recipients(campaign.id, limit=100)

                    sent = 0
                    failed = 0
                    for recipient in recipients:
                        try:
                            customer = await cust_repo.get_by_id(recipient.customer_id)
                            if customer and customer.phone:
                                if campaign.whatsapp_template_name:
                                    resp = await client.send_template(to=customer.phone, template_name=campaign.whatsapp_template_name)
                                else:
                                    resp = await client.send_text(to=customer.phone, body=campaign.message_template)
                                wa_id = resp.get("messages", [{}])[0].get("id")
                                recipient.status = RecipientStatus.SENT
                                recipient.sent_at = datetime.now(UTC)
                                recipient.whatsapp_message_id = wa_id
                                session.add(recipient)
                                sent += 1
                        except Exception as e:
                            logger.error("Campaign send failed", recipient=str(recipient.id), error=str(e))
                            recipient.status = RecipientStatus.FAILED
                            recipient.error_message = str(e)
                            session.add(recipient)
                            failed += 1

                    await repo.update(campaign, sent_count=campaign.sent_count + sent, failed_count=campaign.failed_count + failed)
                    processed += 1
                except Exception as e:
                    logger.error("Campaign processing error", campaign_id=str(campaign.id), tenant_id=str(tenant.id), error=str(e))

        await session.commit()
    return {"processed": processed}


@celery_app.task(name="app.scheduler.tasks.campaign_tasks.nurture_leads")
def nurture_leads() -> dict:
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_nurture_leads())


async def _nurture_leads() -> dict:
    return {"nurtured": 0}
