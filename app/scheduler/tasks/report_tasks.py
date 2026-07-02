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
