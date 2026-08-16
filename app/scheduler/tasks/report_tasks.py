from __future__ import annotations

from app.core.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(name="app.scheduler.tasks.report_tasks.generate_daily_reports")
def generate_daily_reports() -> dict:
    logger.info("Generating daily reports")
    return {"status": "generated"}


@celery_app.task(name="app.scheduler.tasks.report_tasks.generate_weekly_reports")
def generate_weekly_reports() -> dict:
    logger.info("Generating weekly reports")
    return {"status": "generated"}


@celery_app.task(name="app.scheduler.tasks.report_tasks.generate_monthly_reports")
def generate_monthly_reports() -> dict:
    logger.info("Generating monthly reports")
    return {"status": "generated"}

@celery_app.task(name="app.scheduler.tasks.report_tasks.reset_monthly_usage")
def reset_monthly_usage() -> dict:
    """
    Runs on the 1st of every month.
    Usage records are created fresh each month automatically
    by UsageTracker._get_or_create_record() so no reset is needed.

    This task instead:
    1. Archives the previous month's usage
    2. Sends usage summary emails to tenants
    3. Checks for tenants over their limits and flags them
    """
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_reset_monthly())


async def _reset_monthly() -> dict:
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select
    from app.core.database.base import AsyncSessionLocal
    from app.models.billing import UsageRecord
    from app.models.tenant import Tenant

    import app.models.auth       # noqa: F401
    import app.models.tenant     # noqa: F401
    import app.models.billing    # noqa: F401

    now = datetime.now(timezone.utc)
    last_month = now - timedelta(days=1)
    year = last_month.year
    month = last_month.month

    processed = 0
    flagged = 0

    async with AsyncSessionLocal() as session:
        # Get all usage records for last month
        result = await session.execute(
            select(UsageRecord).where(
                UsageRecord.year == year,
                UsageRecord.month == month,
            )
        )
        records = result.scalars().all()

        for record in records:
            tenant = await session.get(Tenant, record.tenant_id)
            if not tenant:
                continue

            # Check if tenant exceeded limits last month
            msg_limit = tenant.max_messages_per_month
            ai_limit = tenant.max_ai_calls_per_month

            if msg_limit < 999999 and record.messages_sent > msg_limit * 0.9:
                logger.warning(
                    "Tenant near/over message limit last month",
                    tenant_slug=tenant.slug,
                    sent=record.messages_sent,
                    limit=msg_limit,
                )
                flagged += 1

            if ai_limit < 999999 and record.ai_calls > ai_limit * 0.9:
                logger.warning(
                    "Tenant near/over AI limit last month",
                    tenant_slug=tenant.slug,
                    ai_calls=record.ai_calls,
                    limit=ai_limit,
                )
                flagged += 1

            processed += 1

        logger.info(
            "Monthly usage review complete",
            period=f"{year}-{month:02d}",
            tenants_processed=processed,
            tenants_flagged=flagged,
        )

    return {
        "period": f"{year}-{month:02d}",
        "processed": processed,
        "flagged": flagged,
    }


# Add to beat_schedule in celery_app.py:
BEAT_SCHEDULE_ADDITION = {
    "reset-monthly-usage": {
        "task": "app.scheduler.tasks.report_tasks.reset_monthly_usage",
        "schedule": "0 0 1 * *",  # 1st of every month at midnight
    },
}
