from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_tenant_from_user, get_current_user
from app.core.database.base import get_db
from app.models.auth import User
from app.schemas.common import PaginatedResponse, SuccessResponse
from app.schemas.crm import NotificationResponse
from app.services.crm import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=PaginatedResponse[NotificationResponse])
async def list_notifications(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    unread_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[NotificationResponse]:
    # SAAS CHANGE: Resolve tenant before constructing NotificationService.
    tenant = await get_current_tenant_from_user(current_user, session)
    service = NotificationService(session, tenant_id=tenant.id)

    offset = (page - 1) * page_size
    items, total = await service.list(
        current_user.id,
        unread_only=unread_only,
        offset=offset,
        limit=page_size,
    )
    return PaginatedResponse.create(
        data=[NotificationResponse.model_validate(n) for n in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.put("/{notification_id}/read", response_model=NotificationResponse)
async def mark_read(
    notification_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> NotificationResponse:
    # SAAS CHANGE: Resolve tenant before marking the notification as read.
    tenant = await get_current_tenant_from_user(current_user, session)
    service = NotificationService(session, tenant_id=tenant.id)

    return NotificationResponse.model_validate(
        await service.mark_read(notification_id)
    )


@router.post("/mark-all-read", response_model=SuccessResponse)
async def mark_all_read(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SuccessResponse:
    # SAAS CHANGE: Resolve tenant before bulk notification update.
    tenant = await get_current_tenant_from_user(current_user, session)
    service = NotificationService(session, tenant_id=tenant.id)

    # NOTE: The NotificationService code supplied earlier did not include
    # mark_all_read(). This route therefore still requires that service method
    # to exist. That is a separate issue from tenant injection.
    await service.mark_all_read(current_user.id)
    return SuccessResponse(message="All notifications marked as read.")
