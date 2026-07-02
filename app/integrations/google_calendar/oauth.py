from __future__ import annotations

import uuid
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import get_logger

logger = get_logger(__name__)

GOOGLE_AUTH_BASE = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"


class GoogleOAuthException(AppException):
    status_code = 502
    error_code = "GOOGLE_OAUTH_ERROR"
    message = "Google Calendar authentication failed."


def build_authorization_url(user_id: uuid.UUID, state_secret: str = "") -> str:
    """Build the URL the user visits to grant calendar access."""
    state = f"{user_id}:{state_secret}" if state_secret else str(user_id)
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": GOOGLE_CALENDAR_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_AUTH_BASE}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str) -> dict[str, Any]:
    """Exchange the OAuth authorization code for access + refresh tokens."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        if resp.status_code != 200:
            logger.error("Google token exchange failed", status=resp.status_code, body=resp.text)
            raise GoogleOAuthException(f"Token exchange failed: {resp.text}")
        return resp.json()


async def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    """Exchange a stored refresh token for a fresh access token."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "grant_type": "refresh_token",
            },
        )
        if resp.status_code != 200:
            logger.error("Google token refresh failed", status=resp.status_code, body=resp.text)
            raise GoogleOAuthException(f"Token refresh failed: {resp.text}")
        return resp.json()
