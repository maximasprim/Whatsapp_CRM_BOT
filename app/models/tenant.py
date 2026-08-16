from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel

if TYPE_CHECKING:
    from app.models.auth import User
    from app.models.customer import Customer
    from app.models.company import Company
    from app.models.lead import Lead
    from app.models.conversation import Conversation
    from app.models.campaign import Campaign
    from app.models.ticket import SupportTicket
    from app.models.knowledge_document import KnowledgeDocument


class Tenant(BaseModel):
    """
    Represents a business/organisation using the CRM.
    Every piece of data in the system belongs to a tenant.
    """

    __tablename__ = "tenants"

    # ── Identity ──────────────────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    domain: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )

    # ── Status ────────────────────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(50), default="starter", nullable=False)

    # ── Branding ──────────────────────────────────────────────────────────────
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    primary_color: Mapped[str | None] = mapped_column(
        String(20), default="#f97316", nullable=True
    )
    business_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    timezone: Mapped[str] = mapped_column(String(100), default="UTC", nullable=False)

    # ── WhatsApp credentials (per tenant) ─────────────────────────────────────
    whatsapp_phone_number_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    whatsapp_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    whatsapp_business_account_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    whatsapp_webhook_verify_token: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    whatsapp_app_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    whatsapp_phone_number: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )

    # ── AI settings (per tenant) ──────────────────────────────────────────────
    ai_provider: Mapped[str] = mapped_column(String(50), default="gemini", nullable=False)
    ai_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ── Plan limits ───────────────────────────────────────────────────────────
    max_users: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    max_customers: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    max_messages_per_month: Mapped[int] = mapped_column(
        Integer, default=1000, nullable=False
    )
    max_ai_calls_per_month: Mapped[int] = mapped_column(
        Integer, default=500, nullable=False
    )

    # ── Custom settings ───────────────────────────────────────────────────────
    custom_settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    users: Mapped[list["User"]] = relationship(
        "User", back_populates="tenant", lazy="select"
    )
    customers: Mapped[list["Customer"]] = relationship(
        "Customer", back_populates="tenant", lazy="select"
    )
    companies: Mapped[list["Company"]] = relationship(
        "Company", back_populates="tenant", lazy="select"
    )
    leads: Mapped[list["Lead"]] = relationship(
        "Lead", back_populates="tenant", lazy="select"
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="tenant", lazy="select"
    )
    campaigns: Mapped[list["Campaign"]] = relationship(
        "Campaign", back_populates="tenant", lazy="select"
    )
    tickets: Mapped[list["SupportTicket"]] = relationship(
        "SupportTicket", back_populates="tenant", lazy="select"
    )
    knowledge_documents: Mapped[list["KnowledgeDocument"]] = relationship(
        "KnowledgeDocument", back_populates="tenant", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Tenant {self.slug}>"

    @property
    def webhook_url_path(self) -> str:
        """The webhook URL path for this tenant."""
        return f"/api/whatsapp/webhook/{self.slug}"
