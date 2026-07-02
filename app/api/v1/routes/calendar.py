from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.config import settings
from app.core.database.base import get_db
from app.core.security import create_verification_token, decode_verification_token
from app.integrations.google_calendar.oauth import build_authorization_url, exchange_code_for_tokens
from app.models.auth import User
from app.repositories.calendar_credential import CalendarCredentialRepository
from app.schemas.common import SuccessResponse
from app.services.appointment_calendar_sync import AppointmentCalendarSyncService

router = APIRouter(prefix="/calendar", tags=["Google Calendar"])


@router.get("/connect")
async def connect_calendar(
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Returns the Google OAuth consent URL the frontend should redirect the user to."""
    state_token = create_verification_token({"sub": str(current_user.id), "type": "calendar_connect"}, expires_hours=1)
    url = build_authorization_url(current_user.id, state_secret=state_token)
    return {"authorization_url": url}


@router.get("/callback")
async def calendar_callback(
    code: str,
    state: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RedirectResponse:
    """Google redirects here after the user grants consent."""
    try:
        user_id_str, state_token = state.split(":", 1)
        payload = decode_verification_token(state_token)
        if payload.get("type") != "calendar_connect" or payload.get("sub") != user_id_str:
            raise ValueError("State mismatch")
        user_id = uuid.UUID(user_id_str)
    except Exception:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/settings/calendar?status=error")

    try:
        tokens = await exchange_code_for_tokens(code)
        repo = CalendarCredentialRepository(session)
        await repo.store_tokens(
            user_id=user_id,
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token", ""),
            expires_in=tokens.get("expires_in", 3600),
            scope=tokens.get("scope"),
        )
        await session.commit()
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/settings/calendar?status=connected")
    except Exception:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/settings/calendar?status=error")


@router.get("/status", response_model=dict)
async def calendar_status(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    repo = CalendarCredentialRepository(session)
    cred = await repo.get_by_user(current_user.id)
    return {"connected": cred is not None, "calendar_id": cred.calendar_id if cred else None}


@router.delete("/disconnect", response_model=SuccessResponse)
async def disconnect_calendar(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SuccessResponse:
    repo = CalendarCredentialRepository(session)
    await repo.revoke(current_user.id)
    await session.commit()
    return SuccessResponse(message="Google Calendar disconnected.")


@router.get("/availability/{agent_id}")
async def get_availability(
    agent_id: uuid.UUID,
    date: datetime,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    slot_duration_minutes: int = Query(30, ge=15, le=240),
) -> dict:
    service = AppointmentCalendarSyncService(session)
    slots = await service.get_available_slots(agent_id, date, slot_duration_minutes=slot_duration_minutes)
    return {"date": date.date().isoformat(), "slots": slots}
