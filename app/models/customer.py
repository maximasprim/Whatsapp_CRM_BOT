from __future__ import annotations

import uuid
import enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean, Enum as SAEnum, Float, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.lead import Lead
    from app.models.conversation import Conversation
    from app.models.activity import Activity
    from app.models.note import Note


class CustomerStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"
    PROSPECT = "prospect"


class CustomerGender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    UNKNOWN = "unknown"


class Customer(BaseModel):
    __tablename__ = "customers"

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    whatsapp_id: Mapped[str | None] = mapped_column(String(30), nullable=True, unique=True, index=True)
    gender: Mapped[CustomerGender] = mapped_column(
        SAEnum(CustomerGender, name="customergender", values_callable=lambda x: [e.value for e in x]), default=CustomerGender.UNKNOWN, nullable=False
    )
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[CustomerStatus] = mapped_column(
        SAEnum(CustomerStatus, name="customerstatus", values_callable=lambda x: [e.value for e in x]), default=CustomerStatus.PROSPECT, nullable=False, index=True
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)

    job_title: Mapped[str | None] = mapped_column(String(150), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    lead_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lifetime_value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_orders: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    intent_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    custom_fields: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    company: Mapped["Company | None"] = relationship("Company", back_populates="customers")
    leads: Mapped[list["Lead"]] = relationship("Lead", back_populates="customer")
    conversations: Mapped[list["Conversation"]] = relationship("Conversation", back_populates="customer")
    activities: Mapped[list["Activity"]] = relationship("Activity", back_populates="customer")
    notes: Mapped[list["Note"]] = relationship("Note", back_populates="customer")

    __table_args__ = (
        Index("ix_customers_name", "first_name", "last_name"),
        Index("ix_customers_status_assigned", "status", "assigned_to"),
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
