from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.database.base import get_db
from app.models.auth import User
from app.schemas.common import PaginatedResponse, SuccessResponse
from app.schemas.crm import LeadCreate, LeadResponse, LeadUpdate
from app.services.crm import LeadService

router = APIRouter(prefix="/leads", tags=["Leads"])


@router.post("", response_model=LeadResponse, status_code=201)
async def create_lead(data: LeadCreate, session: Annotated[AsyncSession, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)]) -> LeadResponse:
    service = LeadService(session)
    lead = await service.create(data, created_by=current_user.id)
    return LeadResponse.model_validate(lead)


@router.get("", response_model=PaginatedResponse[LeadResponse])
async def list_leads(session: Annotated[AsyncSession, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)], status: str | None = Query(None), assigned_to: uuid.UUID | None = Query(None), page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)) -> PaginatedResponse[LeadResponse]:
    service = LeadService(session)
    offset = (page - 1) * page_size
    items, total = await service.list(status=status, assigned_to=assigned_to, offset=offset, limit=page_size)
    return PaginatedResponse.create(data=[LeadResponse.model_validate(l) for l in items], total=total, page=page, page_size=page_size)


@router.get("/pipeline", response_model=dict)
async def get_pipeline(session: Annotated[AsyncSession, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)]) -> dict:
    service = LeadService(session)
    return await service.get_pipeline_stats()


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(lead_id: uuid.UUID, session: Annotated[AsyncSession, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)]) -> LeadResponse:
    service = LeadService(session)
    return LeadResponse.model_validate(await service.get(lead_id))


@router.put("/{lead_id}", response_model=LeadResponse)
async def update_lead(lead_id: uuid.UUID, data: LeadUpdate, session: Annotated[AsyncSession, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)]) -> LeadResponse:
    service = LeadService(session)
    return LeadResponse.model_validate(await service.update(lead_id, data, updated_by=current_user.id))


@router.delete("/{lead_id}", response_model=SuccessResponse)
async def delete_lead(lead_id: uuid.UUID, session: Annotated[AsyncSession, Depends(get_db)], current_user: Annotated[User, Depends(get_current_user)]) -> SuccessResponse:
    service = LeadService(session)
    await service.delete(lead_id)
    return SuccessResponse(message="Lead deleted.")
