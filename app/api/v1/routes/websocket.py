from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.base import get_db
from app.core.logging import get_logger
from app.core.security import decode_token
from app.core.exceptions import InvalidTokenException

logger = get_logger(__name__)
router = APIRouter(prefix="/ws", tags=["WebSocket"])


class ConnectionManager:
    """Manages active WebSocket connections per user."""

    def __init__(self) -> None:
        # user_id -> list of websockets
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        if user_id not in self._connections:
            self._connections[user_id] = []
        self._connections[user_id].append(websocket)
        logger.info("WebSocket connected", user_id=user_id, total=len(self._connections[user_id]))

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        if user_id in self._connections:
            self._connections[user_id] = [
                ws for ws in self._connections[user_id] if ws != websocket
            ]
            if not self._connections[user_id]:
                del self._connections[user_id]
        logger.info("WebSocket disconnected", user_id=user_id)

    async def send_to_user(self, user_id: str, message: dict[str, Any]) -> None:
        if user_id in self._connections:
            dead = []
            for ws in self._connections[user_id]:
                try:
                    await ws.send_text(json.dumps(message, default=str))
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._connections[user_id].remove(ws)

    async def broadcast(self, message: dict[str, Any]) -> None:
        for user_id in list(self._connections.keys()):
            await self.send_to_user(user_id, message)

    def is_connected(self, user_id: str) -> bool:
        return user_id in self._connections and bool(self._connections[user_id])

    def online_users(self) -> list[str]:
        return list(self._connections.keys())


# Global singleton — shared across the app lifetime
ws_manager = ConnectionManager()


def get_ws_manager() -> ConnectionManager:
    return ws_manager


async def _authenticate_ws(websocket: WebSocket) -> str | None:
    """Extract and verify JWT from query param or header."""
    token = websocket.query_params.get("token")
    if not token:
        headers = dict(websocket.headers)
        auth = headers.get("authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        return None
    try:
        payload = decode_token(token, expected_type="access")
        return payload.get("sub")
    except (InvalidTokenException, Exception):
        return None


@router.websocket("/chat")
async def websocket_chat(websocket: WebSocket) -> None:
    """
    Real-time WebSocket endpoint.

    Connect with: ws://host/api/v1/ws/chat?token=<JWT>

    Client sends JSON:  {"type": "message", "conversation_id": "...", "content": "..."}
    Server pushes JSON: {"type": "message" | "typing" | "status" | "notification", ...}
    """
    user_id = await _authenticate_ws(websocket)
    if not user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    manager = get_ws_manager()
    await manager.connect(websocket, user_id)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "message": "Invalid JSON"}))
                continue

            msg_type = data.get("type")

            if msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

            elif msg_type == "message":
                await _handle_ws_message(websocket, user_id, data, manager)

            elif msg_type == "typing":
                conversation_id = data.get("conversation_id")
                if conversation_id:
                    await manager.broadcast({
                        "type": "typing",
                        "conversation_id": conversation_id,
                        "user_id": user_id,
                    })

            elif msg_type == "read":
                conversation_id = data.get("conversation_id")
                await websocket.send_text(json.dumps({"type": "read_ack", "conversation_id": conversation_id}))

            else:
                await websocket.send_text(json.dumps({"type": "error", "message": f"Unknown type: {msg_type}"}))

    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
    except Exception as exc:
        logger.error("WebSocket error", user_id=user_id, error=str(exc))
        manager.disconnect(websocket, user_id)


async def _handle_ws_message(
    websocket: WebSocket,
    user_id: str,
    data: dict[str, Any],
    manager: ConnectionManager,
) -> None:
    conversation_id_str = data.get("conversation_id")
    content = data.get("content", "").strip()

    if not conversation_id_str or not content:
        await websocket.send_text(json.dumps({"type": "error", "message": "conversation_id and content required"}))
        return

    try:
        conversation_id = uuid.UUID(conversation_id_str)
    except ValueError:
        await websocket.send_text(json.dumps({"type": "error", "message": "Invalid conversation_id"}))
        return

    # Persist the outbound message via the conversation service
    from app.core.database.base import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        from app.whatsapp.conversation_service import WhatsAppConversationService
        service = WhatsAppConversationService(session)
        try:
            msg = await service.send_reply(
                conversation_id=conversation_id,
                text=content,
                sender_id=uuid.UUID(user_id),
            )
            await session.commit()

            # Echo back to sender and broadcast to others viewing same conversation
            payload = {
                "type": "message",
                "id": str(msg.id),
                "conversation_id": str(conversation_id),
                "content": content,
                "direction": "outbound",
                "sender_id": user_id,
                "created_at": msg.created_at.isoformat(),
            }
            await manager.broadcast(payload)

        except Exception as exc:
            logger.error("WS message send failed", error=str(exc))
            await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))


@router.websocket("/notifications")
async def websocket_notifications(websocket: WebSocket) -> None:
    """Dedicated channel for real-time push notifications."""
    user_id = await _authenticate_ws(websocket)
    if not user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    manager = get_ws_manager()
    await manager.connect(websocket, f"notif:{user_id}")

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            if data.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(websocket, f"notif:{user_id}")
