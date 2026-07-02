from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel


class WSEventType(str, Enum):
    # Client -> Server
    SUBSCRIBE_CONVERSATION = "subscribe_conversation"
    UNSUBSCRIBE_CONVERSATION = "unsubscribe_conversation"
    SEND_MESSAGE = "send_message"
    TYPING_START = "typing_start"
    TYPING_STOP = "typing_stop"
    MARK_READ = "mark_read"
    PING = "ping"

    # Server -> Client
    NEW_MESSAGE = "new_message"
    MESSAGE_STATUS_UPDATE = "message_status_update"
    CONVERSATION_UPDATED = "conversation_updated"
    TYPING_INDICATOR = "typing_indicator"
    AI_PROCESSING = "ai_processing"
    AI_SUGGESTION_READY = "ai_suggestion_ready"
    NOTIFICATION = "notification"
    ERROR = "error"
    PONG = "pong"
    CONNECTED = "connected"


class WSMessage(BaseModel):
    event: WSEventType
    data: dict[str, Any] = {}
    timestamp: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat()


def build_event(event: WSEventType, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return WSMessage(event=event, data=data or {}).model_dump(mode="json")
