from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "whatsapp_crm",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.scheduler.tasks.followup_tasks",
        "app.scheduler.tasks.reminder_tasks",
        "app.scheduler.tasks.campaign_tasks",
        "app.scheduler.tasks.report_tasks",
        "app.scheduler.tasks.summary_tasks",
        "app.scheduler.tasks.notification_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    task_soft_time_limit=300,
    task_time_limit=600,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
)

# ── Periodic tasks (beat schedule) ────────────────────────────────────────────
celery_app.conf.beat_schedule = {
    "send-followup-reminders-every-hour": {
        "task": "app.scheduler.tasks.followup_tasks.process_due_followups",
        "schedule": crontab(minute=0),
    },
    "send-appointment-reminders-every-15min": {
        "task": "app.scheduler.tasks.reminder_tasks.send_appointment_reminders",
        "schedule": crontab(minute="*/15"),
    },
    "process-campaigns-every-5min": {
        "task": "app.scheduler.tasks.campaign_tasks.process_scheduled_campaigns",
        "schedule": crontab(minute="*/5"),
    },
    "generate-daily-reports": {
        "task": "app.scheduler.tasks.report_tasks.generate_daily_reports",
        "schedule": crontab(hour=7, minute=0),
    },
    "generate-weekly-reports": {
        "task": "app.scheduler.tasks.report_tasks.generate_weekly_reports",
        "schedule": crontab(day_of_week="monday", hour=8, minute=0),
    },
    "generate-monthly-reports": {
        "task": "app.scheduler.tasks.report_tasks.generate_monthly_reports",
        "schedule": crontab(day_of_month=1, hour=9, minute=0),
    },
    "summarize-long-conversations": {
        "task": "app.scheduler.tasks.summary_tasks.summarize_long_conversations",
        "schedule": crontab(minute=30),
    },
    "remind-inactive-customers": {
        "task": "app.scheduler.tasks.followup_tasks.remind_inactive_customers",
        "schedule": crontab(hour=10, minute=0),
    },
    "nurture-leads": {
        "task": "app.scheduler.tasks.campaign_tasks.nurture_leads",
        "schedule": crontab(hour="*/6", minute=0),
    },
}
