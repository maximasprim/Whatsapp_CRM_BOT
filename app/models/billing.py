"""
Billing models — subscriptions, invoices, usage tracking.
Add these to your models directory.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel

if TYPE_CHECKING:
    from app.models.tenant import Tenant


class Subscription(BaseModel):
    """Tracks active subscription per tenant."""
    __tablename__ = "subscriptions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Plan details
    plan: Mapped[str] = mapped_column(String(50), default="starter", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    # active | trialing | past_due | cancelled | paused

    # Stripe integration
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_price_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Billing cycle
    current_period_start: Mapped[datetime | None] = mapped_column(nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(nullable=True)
    trial_end: Mapped[datetime | None] = mapped_column(nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Limits for this subscription
    max_users: Mapped[int] = mapped_column(Integer, default=5)
    max_customers: Mapped[int] = mapped_column(Integer, default=500)
    max_messages_per_month: Mapped[int] = mapped_column(Integer, default=1000)
    max_ai_calls_per_month: Mapped[int] = mapped_column(Integer, default=500)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", foreign_keys=[tenant_id])
    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice", back_populates="subscription"
    )


class Invoice(BaseModel):
    """Invoice record per billing cycle."""
    __tablename__ = "invoices"

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Invoice details
    stripe_invoice_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
    currency: Mapped[str] = mapped_column(String(10), default="usd")
    status: Mapped[str] = mapped_column(String(50), default="pending")
    # pending | paid | failed | void

    period_start: Mapped[datetime | None] = mapped_column(nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(nullable=True)
    invoice_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    invoice_pdf: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    subscription: Mapped["Subscription"] = relationship(
        "Subscription", back_populates="invoices"
    )
    tenant: Mapped["Tenant"] = relationship("Tenant", foreign_keys=[tenant_id])


class UsageRecord(BaseModel):
    """Tracks monthly usage per tenant."""
    __tablename__ = "usage_records"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Billing period
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)

    # Usage counts
    messages_sent: Mapped[int] = mapped_column(Integer, default=0)
    messages_received: Mapped[int] = mapped_column(Integer, default=0)
    ai_calls: Mapped[int] = mapped_column(Integer, default=0)
    active_customers: Mapped[int] = mapped_column(Integer, default=0)
    active_users: Mapped[int] = mapped_column(Integer, default=0)
    campaigns_sent: Mapped[int] = mapped_column(Integer, default=0)

    # Breakdown
    usage_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    tenant: Mapped["Tenant"] = relationship("Tenant", foreign_keys=[tenant_id])
