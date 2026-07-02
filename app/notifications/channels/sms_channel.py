from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import get_logger

logger = get_logger(__name__)

TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"


class SMSSendException(AppException):
    status_code = 502
    error_code = "SMS_SEND_ERROR"
    message = "Failed to send SMS."


class SMSChannel:
    """Twilio-backed SMS channel. Swap the implementation here if using a
    different SMS provider (Africa's Talking, Vonage, etc.) — the interface
    (send) stays the same for the rest of the app."""

    def __init__(self) -> None:
        self._account_sid = settings.TWILIO_ACCOUNT_SID
        self._auth_token = settings.TWILIO_AUTH_TOKEN
        self._from_number = settings.TWILIO_PHONE_NUMBER

    @retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3), reraise=True)
    async def send(self, to: str, body: str) -> dict[str, Any]:
        if not self._account_sid or not self._auth_token:
            logger.warning("SMS channel not configured, skipping send", to=to)
            return {"status": "skipped", "reason": "SMS provider not configured"}

        url = f"{TWILIO_API_BASE}/Accounts/{self._account_sid}/Messages.json"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                url,
                auth=(self._account_sid, self._auth_token),
                data={"From": self._from_number, "To": to, "Body": body},
            )
            if resp.status_code not in (200, 201):
                logger.error("SMS send failed", to=to, status=resp.status_code, body=resp.text)
                raise SMSSendException(f"Twilio error {resp.status_code}: {resp.text}")

            data = resp.json()
            logger.info("SMS sent", to=to, sid=data.get("sid"))
            return {"status": "sent", "to": to, "sid": data.get("sid")}


_sms_channel: SMSChannel | None = None


def get_sms_channel() -> SMSChannel:
    global _sms_channel
    if _sms_channel is None:
        _sms_channel = SMSChannel()
    return _sms_channel
