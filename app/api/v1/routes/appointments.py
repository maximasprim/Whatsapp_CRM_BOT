# pyright: reportMissingImports=false
from __future__ import annotations

import datetime
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_tenant_from_user, get_current_user
from app.core.database.base import get_db
from app.models.auth import User
from app.schemas.crm import AppointmentCreate, AppointmentResponse, AppointmentUpdate
from app.services.crm import AppointmentService
from app.services.appointment_calendar_sync import AppointmentCalendarSyncService

router = APIRouter(prefix="/appointments", tags=["Appointments"])


@router.get("", response_model=list[AppointmentResponse])
async def list_appointments(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    assigned_to: uuid.UUID | None = None,
    start_date: datetime.datetime | None = None,
    end_date: datetime.datetime | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    # SAAS CHANGE: Tenant is passed to the tenant-aware AppointmentService.
    tenant = await get_current_tenant_from_user(current_user, session)
    service = AppointmentService(session, tenant_id=tenant.id)

    appointments, _ = await service.list(
        assigned_to=assigned_to,
        start_date=start_date,
        end_date=end_date,
        offset=offset,
        limit=limit,
    )
    return [AppointmentResponse.model_validate(a) for a in appointments]


@router.post("", response_model=AppointmentResponse, status_code=201)
async def create_appointment(
    data: AppointmentCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AppointmentResponse:
    # SAAS CHANGE: Resolve the tenant before calling the calendar sync service.
    # NOTE: AppointmentCalendarSyncService was not listed in the CRM audit as
    # requiring tenant_id, so its constructor is intentionally unchanged here.
    tenant = await get_current_tenant_from_user(current_user, session)
    _ = tenant

    service = AppointmentCalendarSyncService(session)
    appt = await service.book_appointment(data, created_by=current_user.id)
    await session.commit()
    return AppointmentResponse.model_validate(appt)


@router.get("/{appt_id}", response_model=AppointmentResponse)
async def get_appointment(
    appt_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AppointmentResponse:
    # SAAS CHANGE: Tenant scopes appointment retrieval through AppointmentService.
    tenant = await get_current_tenant_from_user(current_user, session)
    service = AppointmentService(session, tenant_id=tenant.id)

    return AppointmentResponse.model_validate(await service.get(appt_id))


@router.put("/{appt_id}", response_model=AppointmentResponse)
async def update_appointment(
    appt_id: uuid.UUID,
    data: AppointmentUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AppointmentResponse:
    # SAAS CHANGE: Tenant scopes appointment updates.
    tenant = await get_current_tenant_from_user(current_user, session)
    service = AppointmentService(session, tenant_id=tenant.id)

    return AppointmentResponse.model_validate(await service.update(appt_id, data))


@router.put("/{appt_id}/reschedule", response_model=AppointmentResponse)
async def reschedule_appointment(
    appt_id: uuid.UUID,
    new_start: Annotated[str, "ISO datetime"],
    new_end: Annotated[str, "ISO datetime"],
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AppointmentResponse:
    from datetime import datetime

    # SAAS CHANGE: Resolve the tenant for the authenticated request.
    # AppointmentCalendarSyncService itself is unchanged because it is outside
    # the CRM services listed in the audit.
    tenant = await get_current_tenant_from_user(current_user, session)
    _ = tenant

    service = AppointmentCalendarSyncService(session)
    appt = await service.reschedule_appointment(
        appt_id,
        datetime.fromisoformat(new_start),
        datetime.fromisoformat(new_end),
    )
    await session.commit()
    return AppointmentResponse.model_validate(appt)


@router.put("/{appt_id}/cancel", response_model=AppointmentResponse)
async def cancel_appointment(
    appt_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    reason: str | None = None,
) -> AppointmentResponse:
    # SAAS CHANGE: Resolve the tenant for the authenticated request.
    tenant = await get_current_tenant_from_user(current_user, session)
    _ = tenant

    service = AppointmentCalendarSyncService(session)
    appt = await service.cancel_appointment(appt_id, reason=reason)
    await session.commit()
    return AppointmentResponse.model_validate(appt)
