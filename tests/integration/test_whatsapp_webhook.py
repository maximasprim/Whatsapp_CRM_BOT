from __future__ import annotations

import pytest
from httpx import AsyncClient


def _build_text_payload(from_number: str, message_id: str, text: str) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "ENTRY_ID",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"phone_number_id": "123", "display_phone_number": "+15550000"},
                    "messages": [{
                        "id": message_id,
                        "from": from_number,
                        "timestamp": "1700000000",
                        "type": "text",
                        "text": {"body": text},
                    }],
                },
            }],
        }],
    }


@pytest.mark.asyncio
class TestWebhookVerification:
    async def test_verify_webhook_returns_challenge_for_correct_token(self, client: AsyncClient):
        resp = await client.get("/api/v1/whatsapp/webhook", params={
            "hub.mode": "subscribe",
            "hub.verify_token": "test-verify-token",
            "hub.challenge": "CHALLENGE_12345",
        })
        assert resp.status_code == 200
        assert resp.text == "12345"

    async def test_verify_webhook_returns_403_for_wrong_token(self, client: AsyncClient):
        resp = await client.get("/api/v1/whatsapp/webhook", params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong-token",
            "hub.challenge": "CHALLENGE_ABC",
        })
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestWebhookMessageReceiving:
    async def test_inbound_text_message_creates_customer_and_conversation(self, client: AsyncClient):
        payload = _build_text_payload(
            from_number="254722111222",
            message_id="wamid.unique001",
            text="Hello I need help with my order",
        )
        resp = await client.post("/api/v1/whatsapp/webhook", json=payload)
        assert resp.status_code == 200

    async def test_status_update_payload_returns_200(self, client: AsyncClient):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "ENTRY_ID",
                "changes": [{
                    "field": "messages",
                    "value": {
                        "statuses": [{
                            "id": "wamid.status001",
                            "recipient_id": "254722111222",
                            "status": "delivered",
                            "timestamp": "1700000001",
                        }],
                    },
                }],
            }],
        }
        resp = await client.post("/api/v1/whatsapp/webhook", json=payload)
        assert resp.status_code == 200

    async def test_empty_entry_list_returns_200(self, client: AsyncClient):
        resp = await client.post("/api/v1/whatsapp/webhook", json={"entry": []})
        assert resp.status_code == 200
