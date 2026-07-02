from __future__ import annotations
from typing import Any
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from app.core.config import settings
from app.core.exceptions import WhatsAppException
from app.core.logging import get_logger

logger = get_logger(__name__)

class WhatsAppClient:
    def __init__(self) -> None:
        self._base_url = f"{settings.WHATSAPP_API_BASE_URL}/{settings.WHATSAPP_PHONE_NUMBER_ID}"
        self._headers = {
            "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }

    @retry(wait=wait_exponential(min=1, max=30), stop=stop_after_attempt(3), reraise=True)
    async def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{self._base_url}/{endpoint}", headers=self._headers, json=payload)
            if resp.status_code not in (200, 201):
                raise WhatsAppException(f"WhatsApp API error {resp.status_code}: {resp.text}")
            return resp.json()

    async def send_text(self, to: str, body: str, preview_url: bool = False) -> dict[str, Any]:
        return await self._post("messages", {
            "messaging_product": "whatsapp", "recipient_type": "individual",
            "to": to, "type": "text", "text": {"preview_url": preview_url, "body": body},
        })

    async def send_image(self, to: str, image_url: str, caption: str = "") -> dict[str, Any]:
        return await self._post("messages", {
            "messaging_product": "whatsapp", "to": to, "type": "image",
            "image": {"link": image_url, "caption": caption},
        })

    async def send_document(self, to: str, doc_url: str, filename: str, caption: str = "") -> dict[str, Any]:
        return await self._post("messages", {
            "messaging_product": "whatsapp", "to": to, "type": "document",
            "document": {"link": doc_url, "filename": filename, "caption": caption},
        })

    async def send_audio(self, to: str, audio_url: str) -> dict[str, Any]:
        return await self._post("messages", {
            "messaging_product": "whatsapp", "to": to, "type": "audio", "audio": {"link": audio_url},
        })

    async def send_location(self, to: str, lat: float, lon: float, name: str = "", address: str = "") -> dict[str, Any]:
        return await self._post("messages", {
            "messaging_product": "whatsapp", "to": to, "type": "location",
            "location": {"latitude": lat, "longitude": lon, "name": name, "address": address},
        })

    async def send_interactive_buttons(self, to: str, body: str, buttons: list[dict]) -> dict[str, Any]:
        return await self._post("messages", {
            "messaging_product": "whatsapp", "to": to, "type": "interactive",
            "interactive": {
                "type": "button", "body": {"text": body},
                "action": {"buttons": [{"type": "reply", "reply": {"id": b["id"], "title": b["title"]}} for b in buttons]},
            },
        })

    async def send_interactive_list(self, to: str, body: str, button_text: str, sections: list[dict]) -> dict[str, Any]:
        return await self._post("messages", {
            "messaging_product": "whatsapp", "to": to, "type": "interactive",
            "interactive": {
                "type": "list", "body": {"text": body},
                "action": {"button": button_text, "sections": sections},
            },
        })

    async def send_template(self, to: str, template_name: str, language: str = "en", components: list[dict] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp", "to": to, "type": "template",
            "template": {"name": template_name, "language": {"code": language}},
        }
        if components:
            payload["template"]["components"] = components
        return await self._post("messages", payload)

    async def send_reaction(self, to: str, message_id: str, emoji: str) -> dict[str, Any]:
        return await self._post("messages", {
            "messaging_product": "whatsapp", "to": to, "type": "reaction",
            "reaction": {"message_id": message_id, "emoji": emoji},
        })

    async def mark_as_read(self, message_id: str) -> dict[str, Any]:
        return await self._post("messages", {
            "messaging_product": "whatsapp", "status": "read", "message_id": message_id,
        })

    async def get_media_url(self, media_id: str) -> str:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{settings.WHATSAPP_API_BASE_URL}/{media_id}", headers=self._headers)
            if resp.status_code != 200:
                raise WhatsAppException(f"Failed to get media URL: {resp.text}")
            return resp.json().get("url", "")


_client: WhatsAppClient | None = None

def get_whatsapp_client() -> WhatsAppClient:
    global _client
    if _client is None:
        _client = WhatsAppClient()
    return _client
