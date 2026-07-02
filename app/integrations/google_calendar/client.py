from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.exceptions import AppException
from app.core.logging import get_logger
from app.integrations.google_calendar.oauth import refresh_access_token
from app.repositories.calendar_credential import CalendarCredentialRepository

logger = get_logger(__name__)

GOOGLE_CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"


class GoogleCalendarException(AppException):
    status_code = 502
    error_code = "GOOGLE_CALENDAR_ERROR"
    message = "Google Calendar API error."


class GoogleCalendarClient:
    """Authenticated client for a specific user's Google Calendar, handling
    automatic access token refresh via the stored refresh token."""

    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self.session = session
        self.user_id = user_id
        self.cred_repo = CalendarCredentialRepository(session)

    async def _get_valid_access_token(self) -> tuple[str, str]:
        tokens = await self.cred_repo.get_decrypted_tokens(self.user_id)
        if not tokens:
            raise GoogleCalendarException("User has not connected their Google Calendar.")

        if tokens["is_expired"]:
            refreshed = await refresh_access_token(tokens["refresh_token"])
            await self.cred_repo.update_access_token(
                self.user_id,
                refreshed["access_token"],
                refreshed.get("expires_in", 3600),
            )
            await self.session.flush()
            return refreshed["access_token"], tokens["calendar_id"]

        return tokens["access_token"], tokens["calendar_id"]

    @retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(2), reraise=True)
    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        access_token, calendar_id = await self._get_valid_access_token()
        url = f"{GOOGLE_CALENDAR_API_BASE}/calendars/{calendar_id}{path}"
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.request(method, url, headers=headers, **kwargs)
            if resp.status_code not in (200, 201, 204):
                logger.error("Google Calendar API error", status=resp.status_code, body=resp.text)
                raise GoogleCalendarException(f"Calendar API error {resp.status_code}: {resp.text}")
            return resp.json() if resp.content else {}

    async def create_event(
        self,
        summary: str,
        description: str,
        start_time: datetime,
        end_time: datetime,
        timezone: str = "UTC",
        location: str | None = None,
        attendee_emails: list[str] | None = None,
        add_meet_link: bool = False,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start_time.isoformat(), "timeZone": timezone},
            "end": {"dateTime": end_time.isoformat(), "timeZone": timezone},
            "reminders": {"useDefault": True},
        }
        if location:
            body["location"] = location
        if attendee_emails:
            body["attendees"] = [{"email": email} for email in attendee_emails]
        if add_meet_link:
            body["conferenceData"] = {
                "createRequest": {
                    "requestId": str(uuid.uuid4()),
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            }

        params = {"conferenceDataVersion": 1} if add_meet_link else {}
        return await self._request("POST", "/events", json=body, params=params)

    async def update_event(
        self,
        event_id: str,
        summary: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        timezone: str = "UTC",
        location: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if summary:
            body["summary"] = summary
        if start_time:
            body["start"] = {"dateTime": start_time.isoformat(), "timeZone": timezone}
        if end_time:
            body["end"] = {"dateTime": end_time.isoformat(), "timeZone": timezone}
        if location:
            body["location"] = location
        return await self._request("PATCH", f"/events/{event_id}", json=body)

    async def delete_event(self, event_id: str) -> None:
        await self._request("DELETE", f"/events/{event_id}")

    async def get_event(self, event_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/events/{event_id}")

    async def list_events(
        self, time_min: datetime, time_max: datetime
    ) -> list[dict[str, Any]]:
        access_token, calendar_id = await self._get_valid_access_token()
        url = f"{GOOGLE_CALENDAR_API_BASE}/calendars/{calendar_id}/events"
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "singleEvents": "true",
            "orderBy": "startTime",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                raise GoogleCalendarException(f"Failed to list events: {resp.text}")
            return resp.json().get("items", [])

    async def check_availability(
        self, start_time: datetime, end_time: datetime
    ) -> bool:
        """Returns True if the time slot is free (no overlapping events)."""
        events = await self.list_events(start_time, end_time)
        return len(events) == 0
