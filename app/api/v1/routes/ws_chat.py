from __future__ import annotations

import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.base import AsyncSessionLocal
from app.core.logging import get_logger
from app.core.security import decode_token
from app.websocket.connection_manager import manager
from app.websocket.events import WSEventType, build_event

logger = get_logger(__name__)
router = APIRouter(prefix="/ws", tags=["WebSocket"])


async def _authenticate_ws(token: str) -> uuid.UUID | None:
    try:
        payload = decode_token(token, expected_type="access")
        return uuid.UUID(payload.get("sub", ""))
    except Exception:
        return None


@router.websocket("/chat")
async def websocket_chat(websocket: WebSocket, token: str = Query(...)) -> None:
    user_id = await _authenticate_ws(token)
    if not user_id:
        await websocket.close(code=4401, reason="Invalid or missing authentication token.")
        return

    await manager.connect(websocket, user_id)
    await websocket.send_text(json.dumps(build_event(WSEventType.CONNECTED, {"user_id": str(user_id)})))

    subscribed_conversations: set[uuid.UUID] = set()

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps(build_event(WSEventType.ERROR, {"message": "Invalid JSON."})))
                continue

            event_type = payload.get("event")
            data = payload.get("data", {})

            if event_type == WSEventType.PING.value:
                await websocket.send_text(json.dumps(build_event(WSEventType.PONG)))

            elif event_type == WSEventType.SUBSCRIBE_CONVERSATION.value:
                conv_id_str = data.get("conversation_id")
                if conv_id_str:
                    conv_id = uuid.UUID(conv_id_str)
                    manager.subscribe_to_conversation(websocket, conv_id)
                    subscribed_conversations.add(conv_id)
                    await websocket.send_text(json.dumps(build_event(
                        WSEventType.CONVERSATION_UPDATED, {"conversation_id": conv_id_str, "subscribed": True}
                    )))

            elif event_type == WSEventType.UNSUBSCRIBE_CONVERSATION.value:
                conv_id_str = data.get("conversation_id")
                if conv_id_str:
                    conv_id = uuid.UUID(conv_id_str)
                    manager.unsubscribe_from_conversation(websocket, conv_id)
                    subscribed_conversations.discard(conv_id)

            elif event_type == WSEventType.SEND_MESSAGE.value:
                await _handle_send_message(websocket, user_id, data)

            elif event_type == WSEventType.TYPING_START.value:
                conv_id_str = data.get("conversation_id")
                if conv_id_str:
                    await manager.broadcast_to_conversation(
                        uuid.UUID(conv_id_str),
                        build_event(WSEventType.TYPING_INDICATOR, {"conversation_id": conv_id_str, "is_typing": True, "user_id": str(user_id)}),
                        exclude=websocket,
                    )

            elif event_type == WSEventType.TYPING_STOP.value:
                conv_id_str = data.get("conversation_id")
                if conv_id_str:
                    await manager.broadcast_to_conversation(
                        uuid.UUID(conv_id_str),
                        build_event(WSEventType.TYPING_INDICATOR, {"conversation_id": conv_id_str, "is_typing": False, "user_id": str(user_id)}),
                        exclude=websocket,
                    )

            elif event_type == WSEventType.MARK_READ.value:
                await _handle_mark_read(data)

            else:
                await websocket.send_text(json.dumps(build_event(WSEventType.ERROR, {"message": f"Unknown event: {event_type}"})))

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as exc:
        logger.error("WebSocket error", error=str(exc), user_id=str(user_id))
        manager.disconnect(websocket)


async def _handle_send_message(websocket: WebSocket, user_id: uuid.UUID, data: dict) -> None:
    conv_id_str = data.get("conversation_id")
    text = data.get("text", "")
    if not conv_id_str or not text:
        await websocket.send_text(json.dumps(build_event(WSEventType.ERROR, {"message": "conversation_id and text are required."})))
        return

    async with AsyncSessionLocal() as session:
        from app.whatsapp.conversation_service import WhatsAppConversationService
        service = WhatsAppConversationService(session)
        try:
            message = await service.send_reply(uuid.UUID(conv_id_str), text, sender_id=user_id)
            await session.commit()

            event_data = {
                "conversation_id": conv_id_str,
                "message_id": str(message.id),
                "content": message.content,
                "direction": message.direction,
                "sender_id": str(user_id),
                "created_at": message.created_at.isoformat(),
            }
            await manager.broadcast_to_conversation(uuid.UUID(conv_id_str), build_event(WSEventType.NEW_MESSAGE, event_data))
        except Exception as exc:
            logger.error("Failed to send WS message", error=str(exc))
            await websocket.send_text(json.dumps(build_event(WSEventType.ERROR, {"message": str(exc)})))


async def _handle_mark_read(data: dict) -> None:
    conv_id_str = data.get("conversation_id")
    if not conv_id_str:
        return
    async with AsyncSessionLocal() as session:
        from app.models.conversation import Conversation
        conv = await session.get(Conversation, uuid.UUID(conv_id_str))
        if conv:
            conv.unread_count = 0
            session.add(conv)
            await session.commit()


async def notify_new_inbound_message(conversation_id: uuid.UUID, message_data: dict) -> None:
    """Called from Celery tasks / webhook handler to push new inbound messages to connected clients."""
    await manager.broadcast_to_conversation(conversation_id, build_event(WSEventType.NEW_MESSAGE, message_data))


async def notify_ai_suggestion(conversation_id: uuid.UUID, suggestion: str) -> None:
    await manager.broadcast_to_conversation(
        conversation_id, build_event(WSEventType.AI_SUGGESTION_READY, {"conversation_id": str(conversation_id), "suggestion": suggestion})
    )
