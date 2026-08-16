"""
Usage tracker — records and enforces limits per tenant.
Call these functions in your routes and Celery tasks.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.billing import UsageRecord
from app.models.tenant import Tenant

logger = get_logger(__name__)


class UsageTracker:
    def __init__(self, session: AsyncSession, tenant: Tenant) -> None:
        self.session = session
        self.tenant = tenant

    def _current_period(self) -> tuple[int, int]:
        now = datetime.now(timezone.utc)
        return now.year, now.month

    async def _get_or_create_record(self) -> UsageRecord:
        year, month = self._current_period()
        result = await self.session.execute(
            select(UsageRecord).where(
                UsageRecord.tenant_id == self.tenant.id,
                UsageRecord.year == year,
                UsageRecord.month == month,
            )
        )
        record = result.scalars().first()
        if not record:
            record = UsageRecord(
                tenant_id=self.tenant.id,
                year=year,
                month=month,
            )
            self.session.add(record)
            await self.session.flush()
        return record

    async def get_current_usage(self) -> dict:
        """Get current month usage for this tenant."""
        record = await self._get_or_create_record()
        return {
            "messages_sent": record.messages_sent,
            "messages_received": record.messages_received,
            "ai_calls": record.ai_calls,
            "active_customers": record.active_customers,
            "active_users": record.active_users,
            "campaigns_sent": record.campaigns_sent,
            "limits": {
                "max_messages_per_month": self.tenant.max_messages_per_month,
                "max_ai_calls_per_month": self.tenant.max_ai_calls_per_month,
                "max_customers": self.tenant.max_customers,
                "max_users": self.tenant.max_users,
            },
            "period": {
                "year": record.year,
                "month": record.month,
            },
        }

    async def track_message_sent(self) -> bool:
        """
        Track an outbound message.
        Returns False if the tenant has exceeded their limit.
        """
        record = await self._get_or_create_record()
        limit = self.tenant.max_messages_per_month

        if limit != 999999 and record.messages_sent >= limit:
            logger.warning(
                "Message limit exceeded",
                tenant_slug=self.tenant.slug,
                sent=record.messages_sent,
                limit=limit,
            )
            return False

        record.messages_sent += 1
        await self.session.flush()
        return True

    async def track_message_received(self) -> None:
        """Track an inbound message."""
        record = await self._get_or_create_record()
        record.messages_received += 1
        await self.session.flush()

    async def track_ai_call(self) -> bool:
        """
        Track an AI API call.
        Returns False if the tenant has exceeded their AI limit.
        """
        record = await self._get_or_create_record()
        limit = self.tenant.max_ai_calls_per_month

        if limit != 999999 and record.ai_calls >= limit:
            logger.warning(
                "AI call limit exceeded",
                tenant_slug=self.tenant.slug,
                calls=record.ai_calls,
                limit=limit,
            )
            return False

        record.ai_calls += 1
        await self.session.flush()
        return True

    async def track_campaign_sent(self, message_count: int) -> bool:
        """
        Track a campaign send.
        Returns False if sending would exceed message limits.
        """
        record = await self._get_or_create_record()
        limit = self.tenant.max_messages_per_month

        if limit != 999999 and (record.messages_sent + message_count) > limit:
            logger.warning(
                "Campaign would exceed message limit",
                tenant_slug=self.tenant.slug,
                current=record.messages_sent,
                additional=message_count,
                limit=limit,
            )
            return False

        record.messages_sent += message_count
        record.campaigns_sent += 1
        await self.session.flush()
        return True

    async def check_customer_limit(self, current_count: int) -> bool:
        """Check if tenant can add more customers."""
        limit = self.tenant.max_customers
        if limit == 999999:
            return True
        return current_count < limit

    async def check_user_limit(self, current_count: int) -> bool:
        """Check if tenant can add more users."""
        limit = self.tenant.max_users
        if limit == 9999:
            return True
        return current_count < limit

    async def get_usage_percentage(self) -> dict:
        """Get usage as percentage of limits for dashboard display."""
        usage = await self.get_current_usage()
        limits = usage["limits"]

        def pct(used: int, limit: int) -> float:
            if limit >= 999999:
                return 0.0
            return round((used / limit) * 100, 1) if limit > 0 else 0.0

        return {
            "messages": {
                "used": usage["messages_sent"],
                "limit": limits["max_messages_per_month"],
                "percentage": pct(usage["messages_sent"], limits["max_messages_per_month"]),
                "unlimited": limits["max_messages_per_month"] >= 999999,
            },
            "ai_calls": {
                "used": usage["ai_calls"],
                "limit": limits["max_ai_calls_per_month"],
                "percentage": pct(usage["ai_calls"], limits["max_ai_calls_per_month"]),
                "unlimited": limits["max_ai_calls_per_month"] >= 999999,
            },
            "customers": {
                "used": usage["active_customers"],
                "limit": limits["max_customers"],
                "percentage": pct(usage["active_customers"], limits["max_customers"]),
                "unlimited": limits["max_customers"] >= 999999,
            },
        }
