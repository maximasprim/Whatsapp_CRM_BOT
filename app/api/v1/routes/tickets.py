from __future__ import annotations
import uuid
from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import get_current_user
from app.core.database.base import get_db
from app.models.auth import User
from app.schemas.crm import TicketCreate, TicketResponse, TicketUpdate
from app.schemas.common import PaginatedResponse, SuccessResponse
from app.services.crm import TicketService

router = APIRouter(prefix="/tickets", tags=["Tickets"])

@router.post("", response_model=TicketResponse, status_code=201)
async def create_ticket(data: TicketCreate, session: Annotated[AsyncSession, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)]) -> TicketResponse:
    return TicketResponse.model_validate(await TicketService(session).create(data, created_by=current_user.id))

@router.get("", response_model=PaginatedResponse[TicketResponse])
async def list_tickets(session: Annotated[AsyncSession, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)]) -> PaginatedResponse[TicketResponse]:
    items, total = await TicketService(session).list()
    return PaginatedResponse.create(data=[TicketResponse.model_validate(t) for t in items], total=total, page=1, page_size=20)

@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: uuid.UUID, session: Annotated[AsyncSession, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)]) -> TicketResponse:
    return TicketResponse.model_validate(await TicketService(session).get(ticket_id))

@router.put("/{ticket_id}", response_model=TicketResponse)
async def update_ticket(ticket_id: uuid.UUID, data: TicketUpdate, session: Annotated[AsyncSession, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)]) -> TicketResponse:
    return TicketResponse.model_validate(await TicketService(session).update(ticket_id, data))
