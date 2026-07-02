from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class PushChannel:
    """Firebase Cloud Messaging push notification channel.
    Lazily initializes the Firebase Admin SDK only when actually used,
    so the app can boot without Firebase credentials configured."""

    def __init__(self) -> None:
        self._initialized = False

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        try:
            import firebase_admin
            from firebase_admin import credentials
            if not firebase_admin._apps:
                cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
                firebase_admin.initialize_app(cred)
            self._initialized = True
        except Exception as exc:
            logger.warning("Firebase push notifications not configured", error=str(exc))

    async def send(self, device_token: str, title: str, body: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        self._ensure_initialized()
        if not self._initialized:
            return {"status": "skipped", "reason": "Firebase not configured"}

        try:
            from firebase_admin import messaging
            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                data={k: str(v) for k, v in (data or {}).items()},
                token=device_token,
            )
            response = messaging.send(message)
            logger.info("Push notification sent", message_id=response)
            return {"status": "sent", "message_id": response}
        except Exception as exc:
            logger.error("Push notification failed", error=str(exc))
            return {"status": "failed", "error": str(exc)}


_push_channel: PushChannel | None = None


def get_push_channel() -> PushChannel:
    global _push_channel
    if _push_channel is None:
        _push_channel = PushChannel()
    return _push_channel
