from __future__ import annotations

import uuid
import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel


class AppointmentStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    RESCHEDULED = "rescheduled"


class AppointmentType(str, enum.Enum):
    CALL = "call"
    VIDEO_CALL = "video_call"
    IN_PERSON = "in_person"
    DEMO = "demo"
    CONSULTATION = "consultation"
    FOLLOW_UP = "follow_up"
    OTHER = "other"


class Appointment(BaseModel):
    __tablename__ = "appointments"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    appointment_type: Mapped[AppointmentType] = mapped_column(
        SAEnum(AppointmentType, name="appointmenttype", values_callable=lambda x: [e.value for e in x]), default=AppointmentType.CALL, nullable=False
    )
    status: Mapped[AppointmentStatus] = mapped_column(
        SAEnum(AppointmentStatus, name="appointmentstatus", values_callable=lambda x: [e.value for e in x]), default=AppointmentStatus.SCHEDULED, nullable=False, index=True
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC", nullable=False)

    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    meeting_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    reminder_sent: Mapped[bool] = mapped_column(default=False, nullable=False)
    reminder_minutes_before: Mapped[int] = mapped_column(default=30, nullable=False)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_appointments_start_status", "start_time", "status"),)
