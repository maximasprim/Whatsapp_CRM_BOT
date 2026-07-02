from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedMessage:
    message_id: str
    from_number: str
    timestamp: str
    message_type: str
    text: str | None = None
    media_id: str | None = None
    media_mime_type: str | None = None
    caption: str | None = None
    filename: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    location_name: str | None = None
    button_reply_id: str | None = None
    button_reply_title: str | None = None
    list_reply_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class StatusUpdate:
    message_id: str
    from_number: str
    status: str
    timestamp: str
    error_code: str | None = None
    error_title: str | None = None


def parse_webhook_payload(payload: dict[str, Any]) -> tuple[list[ParsedMessage], list[StatusUpdate]]:
    messages: list[ParsedMessage] = []
    statuses: list[StatusUpdate] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "messages":
                continue
            value = change.get("value", {})
            for msg in value.get("messages", []):
                parsed = _parse_message(msg)
                if parsed:
                    messages.append(parsed)
            for status in value.get("statuses", []):
                su = _parse_status(status)
                if su:
                    statuses.append(su)
    return messages, statuses


def _parse_message(msg: dict[str, Any]) -> ParsedMessage | None:
    try:
        msg_type = msg.get("type", "text")
        parsed = ParsedMessage(
            message_id=msg["id"], from_number=msg["from"],
            timestamp=msg.get("timestamp", ""), message_type=msg_type, raw=msg,
        )
        if msg_type == "text":
            parsed.text = msg.get("text", {}).get("body", "")
        elif msg_type in ("image", "audio", "video", "sticker"):
            media = msg.get(msg_type, {})
            parsed.media_id = media.get("id")
            parsed.media_mime_type = media.get("mime_type")
            parsed.caption = media.get("caption")
        elif msg_type == "document":
            doc = msg.get("document", {})
            parsed.media_id = doc.get("id")
            parsed.media_mime_type = doc.get("mime_type")
            parsed.filename = doc.get("filename")
        elif msg_type == "location":
            loc = msg.get("location", {})
            parsed.latitude = loc.get("latitude")
            parsed.longitude = loc.get("longitude")
            parsed.location_name = loc.get("name")
        elif msg_type == "interactive":
            interactive = msg.get("interactive", {})
            itype = interactive.get("type")
            if itype == "button_reply":
                reply = interactive.get("button_reply", {})
                parsed.button_reply_id = reply.get("id")
                parsed.button_reply_title = reply.get("title")
                parsed.text = reply.get("title")
            elif itype == "list_reply":
                reply = interactive.get("list_reply", {})
                parsed.list_reply_id = reply.get("id")
                parsed.text = reply.get("title")
        return parsed
    except (KeyError, IndexError):
        return None


def _parse_status(status: dict[str, Any]) -> StatusUpdate | None:
    try:
        errors = status.get("errors", [])
        error = errors[0] if errors else {}
        return StatusUpdate(
            message_id=status["id"], from_number=status.get("recipient_id", ""),
            status=status["status"], timestamp=status.get("timestamp", ""),
            error_code=str(error.get("code")) if error else None,
            error_title=error.get("title") if error else None,
        )
    except (KeyError, IndexError):
        return None
