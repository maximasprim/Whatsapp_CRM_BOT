from __future__ import annotations

import uuid
import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CampaignType(str, enum.Enum):
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    SMS = "sms"
    MULTI_CHANNEL = "multi_channel"


class RecipientStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    OPTED_OUT = "opted_out"


class Campaign(BaseModel):
    __tablename__ = "campaigns"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    campaign_type: Mapped[CampaignType] = mapped_column(
        SAEnum(CampaignType, name="campaigntype", values_callable=lambda x: [e.value for e in x]), default=CampaignType.WHATSAPP, nullable=False
    )
    status: Mapped[CampaignStatus] = mapped_column(
        SAEnum(CampaignStatus, name="campaignstatus", values_callable=lambda x: [e.value for e in x]), default=CampaignStatus.DRAFT, nullable=False, index=True
    )

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    message_template: Mapped[str] = mapped_column(Text, nullable=False)
    whatsapp_template_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)

    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    total_recipients: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    delivered_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    read_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    audience_filters: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    recipients: Mapped[list["CampaignRecipient"]] = relationship(
        "CampaignRecipient", back_populates="campaign", cascade="all, delete-orphan"
    )


class CampaignRecipient(BaseModel):
    __tablename__ = "campaign_recipients"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    status: Mapped[RecipientStatus] = mapped_column(
        SAEnum(RecipientStatus, name="recipientstatus", values_callable=lambda x: [e.value for e in x]), default=RecipientStatus.PENDING, nullable=False, index=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    whatsapp_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    campaign: Mapped[Campaign] = relationship("Campaign", back_populates="recipients")

    __table_args__ = (Index("ix_campaign_recipients_campaign_status", "campaign_id", "status"),)
