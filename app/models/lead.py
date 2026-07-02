from __future__ import annotations

import uuid
import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel

if TYPE_CHECKING:
    from app.models.customer import Customer


class LeadStatus(str, enum.Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    WON = "won"
    LOST = "lost"
    DISQUALIFIED = "disqualified"


class LeadPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class LeadSource(str, enum.Enum):
    WHATSAPP = "whatsapp"
    WEBSITE = "website"
    REFERRAL = "referral"
    SOCIAL = "social"
    EMAIL = "email"
    COLD_CALL = "cold_call"
    EVENT = "event"
    OTHER = "other"


class Lead(BaseModel):
    __tablename__ = "leads"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    stage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lead_stages.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[LeadStatus] = mapped_column(
        SAEnum(LeadStatus, name="leadstatus", values_callable=lambda x: [e.value for e in x]), default=LeadStatus.NEW, nullable=False, index=True
    )
    priority: Mapped[LeadPriority] = mapped_column(
        SAEnum(LeadPriority, name="leadpriority", values_callable=lambda x: [e.value for e in x]), default=LeadPriority.MEDIUM, nullable=False
    )
    source: Mapped[LeadSource] = mapped_column(
        SAEnum(LeadSource, name="leadsource", values_callable=lambda x: [e.value for e in x]), default=LeadSource.WHATSAPP, nullable=False
    )

    estimated_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    probability: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100
    expected_close_date: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # AI qualification
    lead_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    buying_intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    budget_range: Mapped[str | None] = mapped_column(String(100), nullable=True)
    timeline: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_decision_maker: Mapped[bool | None] = mapped_column(nullable=True)
    purchase_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    urgency: Mapped[str | None] = mapped_column(String(50), nullable=True)

    lost_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    custom_fields: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="leads")
    stage: Mapped["LeadStage | None"] = relationship("LeadStage", back_populates="leads")

    __table_args__ = (Index("ix_leads_status_assigned", "status", "assigned_to"),)


class LeadStage(BaseModel):
    __tablename__ = "lead_stages"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_won: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_lost: Mapped[bool] = mapped_column(default=False, nullable=False)

    leads: Mapped[list[Lead]] = relationship("Lead", back_populates="stage")
