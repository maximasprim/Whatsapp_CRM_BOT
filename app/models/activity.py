from __future__ import annotations

import uuid
import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel

if TYPE_CHECKING:
    from app.models.customer import Customer


class ActivityType(str, enum.Enum):
    CALL = "call"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    MEETING = "meeting"
    NOTE = "note"
    TASK = "task"
    LEAD_CREATED = "lead_created"
    LEAD_UPDATED = "lead_updated"
    ORDER_PLACED = "order_placed"
    PAYMENT_RECEIVED = "payment_received"
    TICKET_OPENED = "ticket_opened"
    TICKET_RESOLVED = "ticket_resolved"
    CAMPAIGN_SENT = "campaign_sent"
    AI_INTERACTION = "ai_interaction"
    STATUS_CHANGE = "status_change"
    OTHER = "other"


class Activity(BaseModel):
    __tablename__ = "activities"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    activity_type: Mapped[ActivityType] = mapped_column(
        SAEnum(ActivityType, name="activitytype", values_callable=lambda x: [e.value for e in x]), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="activities")

    __table_args__ = (Index("ix_activities_customer_type", "customer_id", "activity_type"),)
