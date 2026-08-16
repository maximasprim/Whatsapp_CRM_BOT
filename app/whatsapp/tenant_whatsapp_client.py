"""
Updated WhatsApp client — uses tenant credentials instead of global settings.
Update app/whatsapp/client.py to use this pattern.
"""
from __future__ import annotations

import httpx
from app.core.config import settings
from app.core.logging import get_logger
from app.models.tenant import Tenant

logger = get_logger(__name__)

WHATSAPP_API_URL = "https://graph.facebook.com/v18.0"


class WhatsAppClient:
    """
    Tenant-aware WhatsApp API client.
    Uses tenant credentials if available, falls back to global settings.
    """

    def __init__(
        self,
        phone_number_id: str | None = None,
        access_token: str | None = None,
    ) -> None:
        self.phone_number_id = phone_number_id or settings.WHATSAPP_PHONE_NUMBER_ID
        self.access_token = access_token or settings.WHATSAPP_ACCESS_TOKEN
        self.base_url = f"{WHATSAPP_API_URL}/{self.phone_number_id}"

    @classmethod
    def from_tenant(cls, tenant: Tenant) -> "WhatsAppClient":
        """Create a client using a tenant's credentials."""
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

    async def send_text(
        self,
        to: str,
        body: str,
        preview_url: bool = False,
    ) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"body": body, "preview_url": preview_url},
        }
        return await self._post("messages", payload)

    async def send_template(
        self,
        to: str,
        template_name: str,
        language_code: str = "en_US",
        components: list | None = None,
    ) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": components or [],
            },
        }
        return await self._post("messages", payload)

    async def send_image(
        self,
        to: str,
        image_url: str,
        caption: str | None = None,
    ) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "image",
            "image": {"link": image_url, "caption": caption or ""},
        }
        return await self._post("messages", payload)

    async def send_document(
        self,
        to: str,
        document_url: str,
        filename: str,
        caption: str | None = None,
    ) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "document",
            "document": {
                "link": document_url,
                "filename": filename,
                "caption": caption or "",
            },
        }
        return await self._post("messages", payload)

    async def send_interactive_buttons(
        self,
        to: str,
        body_text: str,
        buttons: list[dict],
    ) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body_text},
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {"id": b["id"], "title": b["title"]},
                        }
                        for b in buttons[:3]
                    ]
                },
            },
        }
        return await self._post("messages", payload)

    async def mark_as_read(self, message_id: str) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        return await self._post("messages", payload)

    async def _post(self, endpoint: str, payload: dict) -> dict:
        url = f"{self.base_url}/{endpoint}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                json=payload,
                headers=self._headers,
            )
        if not response.is_success:
            logger.error(
                "WhatsApp API error",
                status_code=response.status_code,
                body=response.text,
                phone_number_id=self.phone_number_id,
            )
            from fastapi import HTTPException
            raise HTTPException(
                status_code=500,
                detail=f"WhatsApp API error {response.status_code}: {response.text}",
            )
        return response.json()


def get_whatsapp_client(tenant: Tenant | None = None) -> WhatsAppClient:
    """
    Factory function — returns a tenant-specific client if tenant provided,
    otherwise returns a client using global settings.
    """
    if tenant:
        return WhatsAppClient.from_tenant(tenant)
    return WhatsAppClient()
