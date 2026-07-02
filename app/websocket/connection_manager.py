from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import WebSocket

from app.core.logging import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections for real-time chat.

    Connections are grouped by:
    - user_connections: agent/user dashboards (receive all conversation updates they're subscribed to)
    - conversation_subscribers: clients watching a specific conversation_id
    """

    def __init__(self) -> None:
        self.user_connections: dict[uuid.UUID, set[WebSocket]] = {}
        self.conversation_subscribers: dict[uuid.UUID, set[WebSocket]] = {}
        self.connection_user_map: dict[WebSocket, uuid.UUID] = {}

    async def connect(self, websocket: WebSocket, user_id: uuid.UUID) -> None:
        await websocket.accept()
        self.user_connections.setdefault(user_id, set()).add(websocket)
        self.connection_user_map[websocket] = user_id
        logger.info("WebSocket connected", user_id=str(user_id))

    def disconnect(self, websocket: WebSocket) -> None:
        user_id = self.connection_user_map.pop(websocket, None)
        if user_id and user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

        # Remove from any conversation subscriptions
        for conv_id, subscribers in list(self.conversation_subscribers.items()):
            subscribers.discard(websocket)
            if not subscribers:
                del self.conversation_subscribers[conv_id]

        logger.info("WebSocket disconnected", user_id=str(user_id) if user_id else None)

    def subscribe_to_conversation(self, websocket: WebSocket, conversation_id: uuid.UUID) -> None:
        self.conversation_subscribers.setdefault(conversation_id, set()).add(websocket)

    def unsubscribe_from_conversation(self, websocket: WebSocket, conversation_id: uuid.UUID) -> None:
        if conversation_id in self.conversation_subscribers:
            self.conversation_subscribers[conversation_id].discard(websocket)

    async def send_to_user(self, user_id: uuid.UUID, message: dict[str, Any]) -> None:
        connections = self.user_connections.get(user_id, set())
        payload = json.dumps(message, default=str)
        dead_connections = set()
        for ws in connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead_connections.add(ws)
        for ws in dead_connections:
            self.disconnect(ws)

    async def broadcast_to_conversation(
        self, conversation_id: uuid.UUID, message: dict[str, Any], exclude: WebSocket | None = None
    ) -> None:
        subscribers = self.conversation_subscribers.get(conversation_id, set())
        payload = json.dumps(message, default=str)
        dead_connections = set()
        for ws in subscribers:
            if ws is exclude:
                continue
            try:
                await ws.send_text(payload)
            except Exception:
                dead_connections.add(ws)
        for ws in dead_connections:
            self.disconnect(ws)

    async def broadcast_to_all(self, message: dict[str, Any]) -> None:
        payload = json.dumps(message, default=str)
        dead_connections = set()
        for connections in self.user_connections.values():
            for ws in connections:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead_connections.add(ws)
        for ws in dead_connections:
            self.disconnect(ws)


manager = ConnectionManager()
