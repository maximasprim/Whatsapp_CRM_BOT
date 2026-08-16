from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_tenant_from_user, get_current_user
from app.core.database.base import get_db
from app.models.auth import User
from app.schemas.common import PaginatedResponse, SuccessResponse
from app.schemas.crm import TicketCreate, TicketResponse, TicketUpdate
from app.services.crm import TicketService

router = APIRouter(prefix="/tickets", tags=["Tickets"])


@router.post("", response_model=TicketResponse, status_code=201)
async def create_ticket(
    data: TicketCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TicketResponse:
    # SAAS CHANGE: Resolve tenant before constructing TicketService.
    tenant = await get_current_tenant_from_user(current_user, session)
    service = TicketService(session, tenant_id=tenant.id)

    return TicketResponse.model_validate(
        await service.create(data, created_by=current_user.id)
    )


@router.get("", response_model=PaginatedResponse[TicketResponse])
async def list_tickets(
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PaginatedResponse[TicketResponse]:
    # SAAS CHANGE: Tenant scopes ticket listing.
    tenant = await get_current_tenant_from_user(current_user, session)
    service = TicketService(session, tenant_id=tenant.id)

    items, total = await service.list()
    return PaginatedResponse.create(
        data=[TicketResponse.model_validate(t) for t in items],
        total=total,
        page=1,
        page_size=20,
    )


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(
    ticket_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TicketResponse:
    # SAAS CHANGE: Tenant scopes ticket retrieval.
    tenant = await get_current_tenant_from_user(current_user, session)
    service = TicketService(session, tenant_id=tenant.id)

    return TicketResponse.model_validate(await service.get(ticket_id))


@router.put("/{ticket_id}", response_model=TicketResponse)
async def update_ticket(
    ticket_id: uuid.UUID,
    data: TicketUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TicketResponse:
    # SAAS CHANGE: Tenant scopes ticket updates.
    tenant = await get_current_tenant_from_user(current_user, session)
    service = TicketService(session, tenant_id=tenant.id)

    return TicketResponse.model_validate(await service.update(ticket_id, data))
