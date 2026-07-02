from __future__ import annotations

import uuid
import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import BaseModel

if TYPE_CHECKING:
    from app.models.customer import Customer


class ConversationStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    RESOLVED = "resolved"
    CLOSED = "closed"
    BOT_HANDLING = "bot_handling"
    ESCALATED = "escalated"


class MessageDirection(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    LOCATION = "location"
    CONTACT = "contact"
    STICKER = "sticker"
    INTERACTIVE = "interactive"
    TEMPLATE = "template"
    SYSTEM = "system"
    REACTION = "reaction"
    UNSUPPORTED = "unsupported"


class Conversation(BaseModel):
    __tablename__ = "conversations"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    whatsapp_conversation_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone_number: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    status: Mapped[ConversationStatus] = mapped_column(
        SAEnum(ConversationStatus, name="conversationstatus", values_callable=lambda x: [e.value for e in x]),
        default=ConversationStatus.OPEN, nullable=False, index=True
    )
    is_bot_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_message_preview: Mapped[str | None] = mapped_column(String(255), nullable=True)
    unread_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # AI analysis
    sentiment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    intent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    urgency: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="conversations")
    messages: Mapped[list["ConversationMessage"]] = relationship(
        "ConversationMessage", back_populates="conversation", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_conversations_customer_status", "customer_id", "status"),)


class ConversationMessage(BaseModel):
    __tablename__ = "conversation_messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    whatsapp_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True, index=True)
    direction: Mapped[MessageDirection] = mapped_column(
        SAEnum(MessageDirection, name="messagedirection", values_callable=lambda x: [e.value for e in x]), nullable=False, index=True
    )
    message_type: Mapped[MessageType] = mapped_column(
        SAEnum(MessageType, name="messagetype", values_callable=lambda x: [e.value for e in x]), default=MessageType.TEXT, nullable=False
    )

    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_delivered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_failed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # AI
    ai_processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extracted_entities: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    intent: Mapped[str | None] = mapped_column(String(100), nullable=True)

    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="messages")
    attachments: Mapped[list["MessageAttachment"]] = relationship(
        "MessageAttachment", back_populates="message", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_conv_messages_conv_direction", "conversation_id", "direction"),)


class MessageAttachment(BaseModel):
    __tablename__ = "message_attachments"

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation_messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    whatsapp_media_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    message: Mapped[ConversationMessage] = relationship("ConversationMessage", back_populates="attachments")
