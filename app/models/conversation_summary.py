from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String

from app.core.database.base import BaseModel


class ConversationSummary(BaseModel):
    __tablename__ = "conversation_summaries"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    key_points: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    action_items: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    entities_extracted: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    intent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    embedding: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # stored as JSON array
