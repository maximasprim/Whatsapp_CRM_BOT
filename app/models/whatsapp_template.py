from __future__ import annotations

import enum

from sqlalchemy import Enum as SAEnum, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import BaseModel


class TemplateStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAUSED = "paused"


class WhatsAppTemplate(BaseModel):
    __tablename__ = "whatsapp_templates"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[TemplateStatus] = mapped_column(
        SAEnum(TemplateStatus, name="templatestatus", values_callable=lambda x: [e.value for e in x]), default=TemplateStatus.PENDING, nullable=False
    )
    header_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    header_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    footer: Mapped[str | None] = mapped_column(Text, nullable=True)
    buttons: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    components: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    whatsapp_template_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
