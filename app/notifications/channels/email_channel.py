from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmailSendException(AppException):
    status_code = 502
    error_code = "EMAIL_SEND_ERROR"
    message = "Failed to send email."


class EmailChannel:
    @retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3), reraise=True)
    def send(self, to: str, subject: str, html_body: str, plain_body: str | None = None) -> dict[str, Any]:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
            msg["To"] = to

            if plain_body:
                msg.attach(MIMEText(plain_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_FROM_EMAIL, to, msg.as_string())

            logger.info("Email sent", to=to, subject=subject)
            return {"status": "sent", "to": to, "subject": subject}
        except Exception as exc:
            logger.error("Email send failed", to=to, error=str(exc))
            raise EmailSendException(f"Failed to send email to {to}: {exc}") from exc

    async def send_async(self, to: str, subject: str, html_body: str, plain_body: str | None = None) -> dict[str, Any]:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.send, to, subject, html_body, plain_body)


_email_channel: EmailChannel | None = None


def get_email_channel() -> EmailChannel:
    global _email_channel
    if _email_channel is None:
        _email_channel = EmailChannel()
    return _email_channel
