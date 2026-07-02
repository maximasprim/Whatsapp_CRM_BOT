from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.conversation import (
    Conversation, ConversationMessage, ConversationStatus,
    MessageDirection, MessageType,
)
from app.repositories.crm import CustomerRepository
from app.services.crm import CustomerService
from app.whatsapp.client import WhatsAppClient, get_whatsapp_client
from app.whatsapp.webhook_parser import ParsedMessage, StatusUpdate

logger = get_logger(__name__)


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_conversation(self, customer_id: uuid.UUID, phone: str) -> tuple[Conversation, bool]:
        from sqlalchemy import and_, select
        stmt = select(Conversation).where(
            and_(Conversation.customer_id == customer_id, Conversation.status.notin_([ConversationStatus.CLOSED]))
        ).order_by(Conversation.created_at.desc())
        result = await self.session.execute(stmt)
        existing = result.scalars().first()
        if existing:
            return existing, False
        conv = Conversation(customer_id=customer_id, phone_number=phone, status=ConversationStatus.OPEN)
        self.session.add(conv)
        await self.session.flush()
        await self.session.refresh(conv)
        return conv, True

    async def get_by_id(self, conv_id: uuid.UUID) -> Conversation | None:
        return await self.session.get(Conversation, conv_id)

    async def add_message(
        self, conversation_id: uuid.UUID, direction: MessageDirection,
        message_type: MessageType, content: str | None = None,
        whatsapp_message_id: str | None = None, media_url: str | None = None,
        media_mime_type: str | None = None, caption: str | None = None,
        raw_payload: dict | None = None, sender_id: uuid.UUID | None = None,
    ) -> ConversationMessage:
        msg = ConversationMessage(
            conversation_id=conversation_id, direction=direction,
            message_type=message_type, content=content,
            whatsapp_message_id=whatsapp_message_id, media_url=media_url,
            media_mime_type=media_mime_type, caption=caption,
            raw_payload=raw_payload, sender_id=sender_id,
        )
        self.session.add(msg)

        conv = await self.get_by_id(conversation_id)
        if conv:
            conv.last_message_at = datetime.now(UTC)
            conv.last_message_preview = (content or caption or "")[:255]
            if direction == MessageDirection.INBOUND:
                conv.unread_count = (conv.unread_count or 0) + 1
            self.session.add(conv)

        await self.session.flush()
        await self.session.refresh(msg)
        return msg

    async def update_message_status(self, whatsapp_message_id: str, status: str) -> None:
        from sqlalchemy import select
        stmt = select(ConversationMessage).where(ConversationMessage.whatsapp_message_id == whatsapp_message_id)
        result = await self.session.execute(stmt)
        msg = result.scalars().first()
        if msg:
            if status == "delivered":
                msg.is_delivered = True
                msg.delivered_at = datetime.now(UTC)
            elif status == "read":
                msg.is_read = True
                msg.read_at = datetime.now(UTC)
            elif status == "failed":
                msg.is_failed = True
            self.session.add(msg)
            await self.session.flush()


class WhatsAppConversationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.conv_repo = ConversationRepository(session)
        self.customer_service = CustomerService(session)
        self.client: WhatsAppClient = get_whatsapp_client()

    async def handle_inbound_message(self, parsed: ParsedMessage) -> ConversationMessage:
        customer, created = await self.customer_service.get_or_create_by_whatsapp(
            whatsapp_id=parsed.from_number,
            phone=parsed.from_number,
        )
        conversation, conv_created = await self.conv_repo.get_or_create_conversation(
            customer_id=customer.id, phone=parsed.from_number
        )

        msg_type_map = {
            "text": MessageType.TEXT, "image": MessageType.IMAGE,
            "audio": MessageType.AUDIO, "video": MessageType.VIDEO,
            "document": MessageType.DOCUMENT, "location": MessageType.LOCATION,
            "contacts": MessageType.CONTACT, "interactive": MessageType.INTERACTIVE,
            "sticker": MessageType.STICKER,
        }
        msg_type = msg_type_map.get(parsed.message_type, MessageType.UNSUPPORTED)

        message = await self.conv_repo.add_message(
            conversation_id=conversation.id,
            direction=MessageDirection.INBOUND,
            message_type=msg_type,
            content=parsed.text,
            whatsapp_message_id=parsed.message_id,
            media_url=None,
            media_mime_type=parsed.media_mime_type,
            caption=parsed.caption,
            raw_payload=parsed.raw,
        )

        # Mark as read
        try:
            await self.client.mark_as_read(parsed.message_id)
        except Exception:
            pass

        return message

    async def handle_status_update(self, status: StatusUpdate) -> None:
        await self.conv_repo.update_message_status(status.message_id, status.status)

    async def send_reply(
        self, conversation_id: uuid.UUID, text: str, sender_id: uuid.UUID | None = None
    ) -> ConversationMessage:
        conv = await self.conv_repo.get_by_id(conversation_id)
        if not conv:
            raise ValueError(f"Conversation {conversation_id} not found")

        response = await self.client.send_text(to=conv.phone_number, body=text)
        wa_message_id = response.get("messages", [{}])[0].get("id")

        return await self.conv_repo.add_message(
            conversation_id=conversation_id,
            direction=MessageDirection.OUTBOUND,
            message_type=MessageType.TEXT,
            content=text,
            whatsapp_message_id=wa_message_id,
            sender_id=sender_id,
        )
