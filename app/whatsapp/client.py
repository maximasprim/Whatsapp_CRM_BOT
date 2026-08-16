from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.exceptions import WhatsAppException
from app.core.logging import get_logger
from app.models.tenant import Tenant

logger = get_logger(__name__)

WHATSAPP_API_URL = f"{settings.WHATSAPP_API_BASE_URL}"


class WhatsAppClient:
    """
    Tenant-aware WhatsApp Business API client.

    Each tenant can have its own WhatsApp phone number / access token
    (see Tenant.whatsapp_*). If a tenant doesn't have credentials of its
    own yet, falls back to the platform-wide settings.
    """

    def __init__(
        self,
        phone_number_id: str | None = None,
        access_token: str | None = None,
    ) -> None:
        self.phone_number_id = phone_number_id or settings.WHATSAPP_PHONE_NUMBER_ID
        self.access_token = access_token or settings.WHATSAPP_ACCESS_TOKEN
        self._base_url = f"{WHATSAPP_API_URL}/{self.phone_number_id}"

    @classmethod
    def from_tenant(cls, tenant: Tenant) -> "WhatsAppClient":
        """Create a client using a tenant's own credentials."""
        return cls(
            phone_number_id=(
                tenant.whatsapp_phone_number_id or settings.WHATSAPP_PHONE_NUMBER_ID
            ),
            access_token=(
                tenant.whatsapp_access_token or settings.WHATSAPP_ACCESS_TOKEN
            ),
        )

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    @retry(wait=wait_exponential(min=1, max=30), stop=stop_after_attempt(3), reraise=True)
    async def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{self._base_url}/{endpoint}", headers=self._headers, json=payload)
            if resp.status_code not in (200, 201):
                logger.error(
                    "WhatsApp API error",
                    status_code=resp.status_code,
                    body=resp.text,
                    phone_number_id=self.phone_number_id,
                )
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
                "action": {"buttons": [{"type": "reply", "reply": {"id": b["id"], "title": b["title"]}} for b in buttons[:3]]},
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


def get_whatsapp_client(tenant: Tenant | None = None) -> WhatsAppClient:
    """
    Factory — returns a tenant-specific client (using that tenant's own
    WhatsApp Business number/token) if a tenant is provided, otherwise
    falls back to a client built from the platform-wide settings.

    Always pass the tenant when one is available in context: without it,
    every tenant ends up sending/receiving through the same shared
    WhatsApp number, which defeats per-tenant WhatsApp isolation.
    """
    if tenant:
        return WhatsAppClient.from_tenant(tenant)
    return WhatsAppClient()
