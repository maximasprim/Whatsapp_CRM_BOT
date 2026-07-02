from __future__ import annotations

import uuid
import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class FollowUpStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class FollowUpType(str, enum.Enum):
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    CALL = "call"
    SMS = "sms"
    TASK = "task"


class FollowUp(BaseModel):
    __tablename__ = "follow_ups"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True
    )

    follow_up_type: Mapped[FollowUpType] = mapped_column(
        SAEnum(FollowUpType, name="followuptype", values_callable=lambda x: [e.value for e in x]), default=FollowUpType.WHATSAPP, nullable=False
    )
    status: Mapped[FollowUpStatus] = mapped_column(
        SAEnum(FollowUpStatus, name="followupstatus", values_callable=lambda x: [e.value for e in x]), default=FollowUpStatus.PENDING, nullable=False, index=True
    )

    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ai_generated: Mapped[bool] = mapped_column(default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_followups_scheduled_status", "scheduled_at", "status"),)
